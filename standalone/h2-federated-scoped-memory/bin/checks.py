#!/usr/bin/env python3
"""checks.py — the H2 Layer-1 contract harness (CHECKS.md).

Every id in CHECKS.md MUST appear in checks.json on every run — a missing id
is a failure (CHECKS.md preamble). HARD failures invalidate the run: the
harness exits non-zero and no L2 numbers may be published from it.

What the harness does, at any stage:
- FIXTURE SUITE: drives the REAL bin/ scripts (S1 ingest, S2 tag replay from
  the baked committed S2 output, S3 retrieve, S4 rank, S5 mix, S6 outcome,
  S7 update) over fixtures/ inside a scratch workdir, then asserts the
  CHECKS.md contract on the produced artifacts. Deterministic, zero LLM
  calls: S2 runs in replay mode over fixtures/tagged_sessions.jsonl (the
  committed output of one real S2 run) with --model/--base-url placeholders
  as a tripwire — an accidental live call fails loudly instead of spending
  the key.
- SCENARIOS: small synthetic stores inside the workdir for the checks that
  need a crafted shape (fx-rotate, fx-decay, empty-pool NC1, C-RK6).
- IN-PROCESS: the S2 parse/reject and S3-delegation paths are exercised
  against the REAL tag.py/retrieve.py functions with common.call_llm
  monkeypatched to deterministic fakes (no network).
- STATIC: source scans of bin/ for C-ISO1..3/5, C-PROMPT, C-RP1, C-IN6,
  C-RT4, C-OC1.

Rows deferred until runner/eval/corpus exist (C-REPLAY, C-RP3, C-EV1..7,
C-NC2..5) are still present in checks.json with passed=null and a note — they
do not fail an S0 run, and the S0 gate is the "Что прогонять на S0" block of
CHECKS.md.

Row schema (CHECKS.md): {check_id, step, hard, passed, observed, expected, note}.
Exit: 0 all in-scope HARDs green; 1 some in-scope HARD failed; 2 harness bug.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

sys.path.insert(0, str(HERE))

import common  # noqa: E402
import config  # noqa: E402
import prompts  # noqa: E402

# ---------------------------------------------------------------------------
# Registry: every CHECKS.md id, its step and hard flag. An id not implemented
# for this stage is still emitted (passed=null, note=deferred).
# ---------------------------------------------------------------------------

REGISTRY: list[tuple[str, str, bool]] = [
    # Изоляция
    ("C-ISO1", "iso", True), ("C-ISO2", "iso", True), ("C-ISO3", "iso", True),
    ("C-ISO4", "iso", True), ("C-ISO5", "iso", True),
    # S1 ingest
    ("C-IN1", "S1", True), ("C-IN2", "S1", True), ("C-IN3", "S1", True),
    ("C-IN4", "S1", True), ("C-IN5", "S1", True), ("C-IN6", "S1", True),
    # S2 tag
    ("C-PROMPT", "S2", True), ("C-TG1", "S2", True), ("C-TG2", "S2", True),
    ("C-TG3", "S2", True), ("C-TG4", "S2", True), ("C-TG5", "S2", True),
    ("C-TG6", "S2", True), ("C-PII", "S2", True), ("C-TG7", "S2", True),
    ("C-TG8", "S2", True), ("C-TG9", "S2", True), ("C-TG10", "S2", True),
    ("C-TG11", "S2", True), ("C-TG12", "S2", False), ("C-TG13", "S2", False),
    # S3 retrieve
    ("C-SELF", "S3", True), ("C-RT1", "S3", True), ("C-RT2", "S3", True),
    ("C-RT3", "S3", True), ("C-RT4", "S3", True), ("C-RT5", "S3", True),
    # S4 rank
    ("C-RK1", "S4", True), ("C-RK2", "S4", True), ("C-RK3", "S4", True),
    ("C-RK4", "S4", True), ("C-RK5", "S4", True), ("C-RK6", "S4", False),
    # S5 mix
    ("C-SIZE", "S5", True), ("C-MX1", "S5", True), ("C-MX2", "S5", True),
    ("C-MX3", "S5", True), ("C-MX4", "S5", True), ("C-MX5", "S5", True),
    ("C-MX6", "S5", True),
    # S6 outcome
    ("C-OC1", "S6", True), ("C-OC2", "S6", True), ("C-OC3", "S6", True),
    ("C-OC4", "S6", True), ("C-OC5", "S6", True),
    # S7 update
    ("C-DELTA", "S7", True), ("C-UP1", "S7", True), ("C-UP2", "S7", True),
    ("C-UP3", "S7", True), ("C-UP4", "S7", True), ("C-UP5", "S7", True),
    # replay
    ("C-FUTURE", "replay", True), ("C-RP1", "replay", True),
    ("C-RP2", "replay", True), ("C-REPLAY", "replay", True),
    ("C-RP3", "replay", True),
    # eval
    ("C-EV1", "eval", True), ("C-EV2", "eval", True), ("C-EV3", "eval", True),
    ("C-EV4", "eval", True), ("C-EV5", "eval", True), ("C-EV6", "eval", True),
    ("C-EV7", "eval", False),
    # controls
    ("C-NC1", "control", True), ("C-NC2", "control", True),
    ("C-NC3", "control", True), ("C-NC4", "control", True),
    ("C-NC5", "control", False),
    # D0 gold-useful (Phase B; deferred until the D0 artifacts exist)
    ("C-GD1", "D0", True), ("C-GD2", "D0", True), ("C-GD3", "D0", True),
    ("C-GD4", "D0", True), ("C-GD5", "D0", True), ("C-GD6", "D0", False),
    ("C-GD7", "D0", True), ("C-GD8", "D0", True),
]

ALL_IDS = [cid for cid, _, _ in REGISTRY]
HARD_IDS = {cid for cid, _, h in REGISTRY if h}
GD_IDS = {"C-GD1", "C-GD2", "C-GD3", "C-GD4", "C-GD5", "C-GD6", "C-GD7", "C-GD8"}

# Checks whose full contract needs the runner / eval.py / corpus gold. They are
# part of the registry (present in checks.json) but deferred at S0.
DEFERRED_S0 = {
    "C-REPLAY": "needs runner + metrics.json (D4/D5); C-REPLAY closes when the runner appears (CHECKS.md)",
    "C-RP3": "manifest.json with input/artifact shas is written by the runner (D5), not at S0",
    "C-EV1": "needs eval.py class counting + a run (D4)",
    "C-EV2": "needs eval.py B0 arm (D4)",
    "C-EV3": "needs eval.py single scoring path (D4)",
    "C-EV4": "needs eval.py B1 --seed (D4)",
    "C-EV5": "needs eval.py per_query.jsonl + metrics.json (D4/D5)",
    "C-EV6": "needs corpus gold + audit.json (D3/S1)",
    "C-EV7": "needs cost.json from a measured run (D5)",
    "C-NC2": "future-closed_at control needs the runner order (S1); C-FUTURE data-level check runs at S0",
    "C-NC3": "gold_useful empty control needs eval.py T arm on corpus (D4/S1)",
    "C-NC4": "TAG_FIELDS_MIN=5 control needs corpus pairs (S1)",
    "C-NC5": "EXPLORE_SLOTS=0 vs B2 needs eval.py (D4)",
    "C-GD1": "needs D0 gold artifacts (data/gold_useful.jsonl header)",
    "C-GD2": "needs D0 gold + raw corpus closed_at (Phase B run)",
    "C-GD3": "needs D0 gold notes (Phase B run)",
    "C-GD4": "needs D0 gold + data/d0_slice.jsonl (Phase B run)",
    "C-GD5": "needs data/raw_gold_useful/ from a D0 run",
    "C-GD6": "needs D0 gold vs data/gold_useful.seed.jsonl (Phase B run)",
    "C-GD7": "needs D0 gold vs raw unlock_guideline buckets (Phase B run)",
    "C-GD8": "needs data/gold_useful.manifest.json + S2 model pin (Phase B run)",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def expect(rows: list[dict], check_id: str, step: str, hard: bool,
           passed: bool | None, observed, expected, note: str = "") -> None:
    rows.append({"check_id": check_id, "step": step, "hard": hard,
                 "passed": passed if passed is None else bool(passed),
                 "observed": str(observed), "expected": str(expected),
                 "note": note})


def _run(args: list[str], cwd: Path, expect_fail: bool = False,
         env: dict | None = None) -> tuple[int, str]:
    """Run one bin/ script. Returns (returncode, stdout). Fails loudly unless
    expect_fail — the harness itself must not silently skip a step."""
    proc = subprocess.run([sys.executable, *args], capture_output=True,
                          text=True, cwd=str(cwd), env=env or None)
    if proc.returncode != 0 and not expect_fail:
        raise RuntimeError(
            f"step failed: {' '.join(args)}\n"
            f"stdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}")
    return proc.returncode, proc.stdout


def _read_jsonl(path: Path) -> list[dict]:
    return common.read_jsonl(path)


def _scratch(root: Path, name: str) -> Path:
    p = root / name
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# fixture suite — the real scripts over fixtures/ inside the workdir
# ---------------------------------------------------------------------------

class FixtureSuite:
    """Drives S1..S7 over fixtures/ with the REAL bin/ CLIs. No LLM calls:
    S2 runs in replay mode over the committed baked S2 output. All artifacts
    land under work/data (the RUN-PROTOCOL §3 layout)."""

    def __init__(self, fixtures: Path, work: Path):
        self.fx = fixtures
        self.work = work
        self.data = _scratch(work, "data")
        self.results: dict = {}
        self.model_args = ["--model", "replay-fixture", "--base-url", "replay-fixture"]
        # snapshots for C-ISO5 (fixtures must stay untouched)
        self.fx_before = {str(p): p.read_bytes()
                          for p in fixtures.rglob("*") if p.is_file()}

    # -- one real step -------------------------------------------------------
    def step(self, script: str, args: list[str]) -> dict:
        rc, out = _run([str(HERE / script), *args], cwd=self.work)
        try:
            # every step prints exactly ONE JSON document on stdout (indent=2)
            return json.loads(out.strip())
        except Exception:
            return {"rc": rc, "stdout": out.strip()[-500:]}

    # -- the pipeline --------------------------------------------------------
    def run_all(self) -> dict:
        r: dict = {}
        fx = self.fx
        d = self.data

        # --- S1 ingest ---
        s1 = self.step("ingest.py", ["--in", str(fx / "dialogues.jsonl"),
                                     "--out", str(d / "dialogues.jsonl")])
        r["s1"] = s1
        r["dialogues"] = _read_jsonl(d / "dialogues.jsonl")

        # C-IN5: re-ingest is byte-identical
        before = (d / "dialogues.jsonl").read_bytes()
        self.step("ingest.py", ["--in", str(fx / "dialogues.jsonl"),
                                "--out", str(d / "dialogues.jsonl")])
        r["ingest_rerun_identical"] = before == (d / "dialogues.jsonl").read_bytes()

        # --- S2 tag in replay mode over the baked S2 output (zero LLM) ---
        s2 = self.step("tag.py", ["--in", str(fx / "tagged_sessions.jsonl"),
                                  "--out", str(d / "sessions.jsonl"),
                                  "--ratings-out", str(d / "ratings.jsonl"),
                                  "--raw-dir", str(d / "raw" / "tag"),
                                  *self.model_args])
        r["s2"] = s2
        r["pool"] = _read_jsonl(d / "sessions.jsonl")
        r["ratings"] = _read_jsonl(d / "ratings.jsonl")

        # C-TG5: re-tag the same dialogues -> same session ids, no second row
        s2b = self.step("tag.py", ["--in", str(fx / "tagged_sessions.jsonl"),
                                   "--out", str(d / "sessions.jsonl"),
                                   "--ratings-out", str(d / "ratings.jsonl"),
                                   "--raw-dir", str(d / "raw" / "tag"),
                                   *self.model_args])
        r["s2_rerun"] = s2b
        r["pool_rerun"] = _read_jsonl(d / "sessions.jsonl")

        # --- S3/S4/S5/S6/S7 for the fixture query d-007 ---
        r["query_meta"], r["candidates"], r["ranked"], r["packet"], \
            r["serves"], r["outcomes"], r["ratings_after"], \
            r["rk5_rerun_identical"], r["mx6_rerun_identical"] = \
            self.run_query("d-007", fx / "queries" / "d-007.json", d)

        # C-RT5: deterministic re-run of retrieve (pool unchanged by S6/S7)
        r["rt5_rerun"] = self.retrieve_ids(fx / "queries" / "d-007.json", d)

        # C-UP5: second update over the same outcomes applies nothing
        ratings_before = (d / "ratings.jsonl").read_bytes()
        self.step("update.py", ["--outcome", str(d / "outcomes.jsonl"),
                                "--ratings", str(d / "ratings.jsonl"),
                                "--state", str(d / "update_state.json")])
        r["up5_rerun_identical"] = ratings_before == (d / "ratings.jsonl").read_bytes()

        # C-ISO5: fixture inputs untouched by the whole run
        r["fx_untouched"] = {str(p): (p.read_bytes() if p.exists() else b"MISSING")
                             for p in self.fx.rglob("*") if p.is_file()}
        r["fx_untouched_ok"] = all(
            str(p) in self.fx_before and self.fx_before[str(p)] == (p.read_bytes()
            if p.exists() else b"MISSING") for p in self.fx.rglob("*") if p.is_file())

        # baked raw/tag (the S2 log of the bake run) into the run dir
        raw_tag = d / "raw" / "tag"
        raw_tag.mkdir(parents=True, exist_ok=True)
        if (fx / "raw" / "tag").exists():
            for p in (fx / "raw" / "tag").glob("*.json"):
                (raw_tag / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        r["raw_files"] = sorted(p.name for p in raw_tag.glob("*.json"))
        r["tag_summary"] = json.loads((fx / "tag_summary.json").read_text()) \
            if (fx / "tag_summary.json").exists() else {}

        return r

    def retrieve_ids(self, query_file: Path, d: Path) -> list[str]:
        out = d / "candidates_rt5.jsonl"
        self.step("retrieve.py", ["--query", str(query_file),
                                  "--pool", str(d / "sessions.jsonl"),
                                  "--out", str(out),
                                  "--tag-out", str(d / "query_tags_rt5.jsonl"),
                                  "--ratings-out", str(d / "ratings.jsonl"),
                                  "--meta", str(d / "query_meta_rt5.json"),
                                  "--raw-dir", str(d / "raw" / "tag"),
                                  *self.model_args])
        return sorted(s["session_id"] for s in _read_jsonl(out))

    def run_query(self, qid: str, query_file: Path, d: Path) -> tuple:
        """S3 -> S4 -> S5 -> S6 -> S7 for one query. C-RK5/C-MX6 re-runs are
        interleaved BEFORE S6/S7 so the deterministic steps are re-run on the
        exact same inputs they first saw (S7 mutates ratings.jsonl)."""
        self.step("retrieve.py", ["--query", str(query_file),
                                  "--pool", str(d / "sessions.jsonl"),
                                  "--out", str(d / "candidates.jsonl"),
                                  "--tag-out", str(d / "query_tags.jsonl"),
                                  "--ratings-out", str(d / "ratings.jsonl"),
                                  "--meta", str(d / "query_meta.json"),
                                  "--raw-dir", str(d / "raw" / "tag"),
                                  *self.model_args])
        self.step("rank.py", ["--candidates", str(d / "candidates.jsonl"),
                              "--ratings", str(d / "ratings.jsonl"),
                              "--out", str(d / "ranked.jsonl"),
                              "--meta", str(d / "query_meta.json")])
        ranked_before = (d / "ranked.jsonl").read_bytes()
        self.step("rank.py", ["--candidates", str(d / "candidates.jsonl"),
                              "--ratings", str(d / "ratings.jsonl"),
                              "--out", str(d / "ranked.jsonl"),
                              "--meta", str(d / "query_meta.json")])
        rk5_ok = ranked_before == (d / "ranked.jsonl").read_bytes()
        self.step("mix.py", ["--ranked", str(d / "ranked.jsonl"),
                             "--pool", str(d / "sessions.jsonl"),
                             "--out", str(d / "packet.json"),
                             "--serves", str(d / "serves.jsonl"),
                             "--meta", str(d / "query_meta.json")])
        packet_before = (d / "packet.json").read_bytes()
        self.step("mix.py", ["--ranked", str(d / "ranked.jsonl"),
                             "--pool", str(d / "sessions.jsonl"),
                             "--out", str(d / "packet.json"),
                             "--serves", str(d / "serves.jsonl"),
                             "--meta", str(d / "query_meta.json")])
        mx6_ok = packet_before == (d / "packet.json").read_bytes()
        self.step("outcome.py", ["--query", str(query_file),
                                 "--packet", str(d / "packet.json"),
                                 "--source", "gold",
                                 "--gold", str(self.fx / "gold_useful.jsonl"),
                                 "--pool", str(d / "sessions.jsonl"),
                                 "--meta", str(d / "query_meta.json"),
                                 "--out", str(d / "outcomes.jsonl")])
        self.step("update.py", ["--outcome", str(d / "outcomes.jsonl"),
                                "--ratings", str(d / "ratings.jsonl"),
                                "--state", str(d / "update_state.json")])
        meta = json.loads((d / "query_meta.json").read_text())
        return (meta, _read_jsonl(d / "candidates.jsonl"),
                _read_jsonl(d / "ranked.jsonl"),
                json.loads((d / "packet.json").read_text()),
                _read_jsonl(d / "serves.jsonl"),
                _read_jsonl(d / "outcomes.jsonl"),
                _read_jsonl(d / "ratings.jsonl"), rk5_ok, mx6_ok)


# ---------------------------------------------------------------------------
# synthetic scenarios (real CLIs, crafted stores)
# ---------------------------------------------------------------------------

def scenario_rotate(fixtures: Path, work: Path) -> dict:
    """fx-rotate (C-RK4): five candidates with identical tags -> packet of 3,
    the third slot is the explore pick and must not be forced to be the third
    by score. Scores A=5 B=4 C=3 D=2 E=1; explore tie-break by session_id,
    with C's id the largest of the remainder, so the explore pick is D."""
    d = _scratch(work, "fx_rotate")
    tag_key = "login fails after password reset|none|unknown|web|retail-support"
    tags = {"problem_shape": "login fails after password reset", "constraint": "none",
            "ending": "unknown", "channel": "web", "vertical": "retail-support"}
    ids = {"A": "s-000000000001", "B": "s-000000000002", "C": "s-000000000005",
           "D": "s-000000000003", "E": "s-000000000004"}
    scores = {"A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0, "E": 1.0}
    cands, ratings = [], []
    for k, sid in ids.items():
        cands.append({"session_id": sid, "source_dialogue_id": f"rx-{k}",
                      "closed_at": "2026-08-01T09:00:00Z", "channel": "web",
                      "vertical": "retail-support", "agent_id": "a",
                      "turns": [{"role": "customer", "text": "login fails"}],
                      "tags": tags, "tag_key": tag_key, "contains_pii": False})
        ratings.append({"session_id": sid, "tag_key": tag_key, "score": scores[k],
                        "shows": 0, "good": 0, "bad": 0, "unclear": 0,
                        "last_shown_at": None})
    common.write_jsonl(d / "candidates.jsonl", cands)
    common.write_jsonl(d / "ratings.jsonl", ratings)
    rc, out = _run([str(HERE / "rank.py"),
                    "--candidates", str(d / "candidates.jsonl"),
                    "--ratings", str(d / "ratings.jsonl"),
                    "--tag-key", tag_key, "--out", str(d / "ranked.jsonl")],
                   cwd=work)
    ranked = _read_jsonl(d / "ranked.jsonl")
    return {"ranked_ids": [r["session_id"] for r in ranked],
            "explore_slot": ranked[2]["session_id"] if len(ranked) > 2 else None,
            "third_by_score": "s-000000000005",  # C
            "scores": scores}


def scenario_decay(fixtures: Path, work: Path) -> dict:
    """fx-decay (C-UP3): shows=4 + a good outcome -> shows=5 -> decay fires:
    score = 0 + GOOD_DELTA(1.0) - DECAY_AMOUNT(0.1) = 0.9."""
    d = _scratch(work, "fx_decay")
    sid, tag_key = "s-decay0001", "login fails after password reset|none|unknown|web|retail-support"
    common.write_jsonl(d / "ratings.jsonl", [{
        "session_id": sid, "tag_key": tag_key, "score": 0.0, "shows": 4,
        "good": 0, "bad": 0, "unclear": 0, "last_shown_at": None}])
    common.write_jsonl(d / "outcomes.jsonl", [{
        "query_id": "q-decay", "packet_session_ids": [sid], "tag_key": tag_key,
        "outcome": "good", "source": "gold", "closed_at": "2026-08-01T12:00:00Z"}])
    _run([str(HERE / "update.py"), "--outcome", str(d / "outcomes.jsonl"),
          "--ratings", str(d / "ratings.jsonl"),
          "--state", str(d / "update_state.json")], cwd=work)
    rows = _read_jsonl(d / "ratings.jsonl")
    row = next(r for r in rows if r["session_id"] == sid)
    return {"shows": row["shows"], "score": row["score"], "good": row["good"],
            "last_shown_at": row["last_shown_at"]}


def scenario_nc1(fixtures: Path, work: Path) -> dict:
    """C-NC1 (S0 part): empty pool -> S3-S5 yield an empty packet, no
    self-mix, S6 says unclear, S7 touches nothing. B0==T closes with eval."""
    d = _scratch(work, "nc1")
    (d / "pool.jsonl").write_text("", encoding="utf-8")
    # session-shaped query (tags+tag_key) so S3 never delegates to the LLM
    baked = _read_jsonl(fixtures / "tagged_sessions.jsonl")
    query = next(s for s in baked if s["source_dialogue_id"] == "d-007")
    common.write_json(d / "query.json", query)
    rc, _ = _run([str(HERE / "retrieve.py"), "--query", str(d / "query.json"),
                  "--pool", str(d / "pool.jsonl"),
                  "--out", str(d / "candidates.jsonl"),
                  "--tag-out", str(d / "qt.jsonl"),
                  "--ratings-out", str(d / "ratings.jsonl"),
                  "--meta", str(d / "query_meta.json"),
                  "--raw-dir", str(d / "raw" / "tag"),
                  *["--model", "replay-fixture", "--base-url", "replay-fixture"]],
                 cwd=work)
    _run([str(HERE / "rank.py"), "--candidates", str(d / "candidates.jsonl"),
          "--ratings", str(d / "ratings.jsonl"), "--out", str(d / "ranked.jsonl"),
          "--meta", str(d / "query_meta.json")], cwd=work)
    _run([str(HERE / "mix.py"), "--ranked", str(d / "ranked.jsonl"),
          "--pool", str(d / "pool.jsonl"), "--out", str(d / "packet.json"),
          "--serves", str(d / "serves.jsonl"), "--meta", str(d / "query_meta.json")],
         cwd=work)
    packet = json.loads((d / "packet.json").read_text())
    return {"candidates": len(_read_jsonl(d / "candidates.jsonl")),
            "ranked": len(_read_jsonl(d / "ranked.jsonl")),
            "packet_ids": packet.get("packet_session_ids"),
            "header_only": packet.get("packet_text", "").strip()
                           == prompts.PACKET_HEADER.strip()}


def scenario_rk6(fixtures: Path, work: Path) -> dict:
    """C-RK6 (SOFT): candidates <= MAX_PACKET -> packet is all candidates in
    score order, no separate explore slot."""
    d = _scratch(work, "fx_rk6")
    tag_key = "k|none|unknown|web|retail-support"
    tags = {"problem_shape": "k", "constraint": "none", "ending": "unknown",
            "channel": "web", "vertical": "retail-support"}
    cands = [
        {"session_id": "s-0000000000aa", "source_dialogue_id": "rk6-a",
         "closed_at": "2026-08-01T09:00:00Z", "channel": "web",
         "vertical": "retail-support", "agent_id": "a",
         "turns": [{"role": "customer", "text": "x"}], "tags": tags,
         "tag_key": tag_key, "contains_pii": False},
        {"session_id": "s-0000000000bb", "source_dialogue_id": "rk6-b",
         "closed_at": "2026-08-01T09:01:00Z", "channel": "web",
         "vertical": "retail-support", "agent_id": "a",
         "turns": [{"role": "customer", "text": "y"}], "tags": tags,
         "tag_key": tag_key, "contains_pii": False}]
    ratings = [
        {"session_id": "s-0000000000aa", "tag_key": tag_key, "score": 1.0,
         "shows": 0, "good": 0, "bad": 0, "unclear": 0, "last_shown_at": None},
        {"session_id": "s-0000000000bb", "tag_key": tag_key, "score": 2.0,
         "shows": 0, "good": 0, "bad": 0, "unclear": 0, "last_shown_at": None}]
    common.write_jsonl(d / "candidates.jsonl", cands)
    common.write_jsonl(d / "ratings.jsonl", ratings)
    _run([str(HERE / "rank.py"), "--candidates", str(d / "candidates.jsonl"),
          "--ratings", str(d / "ratings.jsonl"), "--tag-key", tag_key,
          "--out", str(d / "ranked.jsonl")], cwd=work)
    ranked = _read_jsonl(d / "ranked.jsonl")
    return {"ranked_ids": [r["session_id"] for r in ranked],
            "len": len(ranked),
            "top_by_score": "s-0000000000bb"}


# ---------------------------------------------------------------------------
# in-process contract tests (real functions, fake call_llm, zero network)
# ---------------------------------------------------------------------------

def _fake_llm(responses: list[dict]):
    """Monkeypatch common.call_llm with a queue of canned responses.
    Returns (captured, restore)."""
    import common as cm
    orig = cm.call_llm
    queue = list(responses)
    captured = {"system": None, "user": None, "n": 0}

    def fake(system, user, **kw):
        captured["system"], captured["user"] = system, user
        captured["n"] += 1
        if not queue:
            raise RuntimeError("fake call_llm exhausted")
        return queue.pop(0)

    cm.call_llm = fake
    return captured, (lambda: setattr(cm, "call_llm", orig))


def _good_response(text: str) -> dict:
    return {"content": text, "raw": {"choices": [{"message": {"content": text}}],
                                     "usage": {"total_tokens": 1}}, "usage": {},
            "model": "fake"}


def test_tg9(fixtures: Path, work: Path) -> dict:
    """C-TG9: two consecutive unparseable answers -> reject, no invented
    tags; one bad + one good -> session returned after a retry."""
    import tag
    d = _scratch(work, "fx_tg9")
    dialogue = {"dialogue_id": "x-tg9", "channel": "web", "vertical": "v",
                "closed_at": "2026-08-01T00:00:00Z",
                "turns": [{"role": "customer", "text": "help"}]}
    cap, restore = _fake_llm([{"content": "not json at all", "raw": {}, "usage": None,
                               "model": "fake"}] * 2)
    session, stats = tag.tag_dialogue(dialogue, model="fake", base_url=None,
                                      raw_dir=d)
    out = {"rejected": stats["rejected"], "tag_calls": stats["tag_calls"],
           "unparseable": stats["unparseable"], "session": session is not None,
           "raw_files": len(list(d.glob("*.json")))}
    restore()
    # one bad then one good -> retry succeeds
    d2 = _scratch(work, "fx_tg9_retry")
    cap2, restore2 = _fake_llm([{"content": "nope", "raw": {}, "usage": None,
                                 "model": "fake"},
                                _good_response('{"problem_shape":"login fails","constraint":"none","ending":"unknown"}')])
    session2, stats2 = tag.tag_dialogue(dialogue, model="fake", base_url=None,
                                        raw_dir=d2)
    out["retry_ok"] = (session2 is not None and stats2["tag_calls"] == 2
                       and session2["tags"]["problem_shape"] == "login fails")
    out["prompt_is_frozen"] = cap["system"] == prompts.TAG_SYSTEM \
        and cap2["system"] == prompts.TAG_SYSTEM
    restore2()
    return out


def test_tg6(fixtures: Path, work: Path) -> dict:
    """C-TG6: PII alone does NOT reject; reject only when problem_shape is
    empty after the scrub."""
    import tag
    d = _scratch(work, "fx_tg6")
    base = {"dialogue_id": "x-pii", "channel": "web", "vertical": "v",
            "closed_at": "2026-08-01T00:00:00Z",
            "turns": [{"role": "customer",
                       "text": "replacement to ada@example.com, call +1-617-555-0199"}]}
    cap, restore = _fake_llm([_good_response(
        '{"problem_shape":"replacement to ada@example.com","constraint":"none","ending":"resolved"}')])
    s, st = tag.tag_dialogue(base, model="fake", base_url=None, raw_dir=d)
    pii_ok = s is not None and s["contains_pii"] is True \
        and st["rejected"] is False
    # scrubbed? raw identifiers gone from tags and turns
    blob = json.dumps(s["tags"], ensure_ascii=False) + json.dumps(s["turns"], ensure_ascii=False)
    scrubbed = "ada@example.com" not in blob and "+1-617-555-0199" not in blob
    restore()
    d2 = _scratch(work, "fx_tg6_reject")
    cap2, restore2 = _fake_llm([_good_response('{"problem_shape":"   ","constraint":"none","ending":"unknown"}')])
    s2, st2 = tag.tag_dialogue(base, model="fake", base_url=None, raw_dir=d2)
    reject_ok = s2 is None and st2["rejected"] is True
    restore2()
    return {"pii_no_reject": pii_ok, "scrubbed": scrubbed,
            "empty_shape_rejects": reject_ok,
            "contains_pii": s["contains_pii"] if s else None}


def test_rt4(fixtures: Path, work: Path) -> dict:
    """C-RT4: an untagged query is delegated to tag.py with the SAME prompts
    (PROMPTS.md §2-§3) — retrieve.py has no text of its own."""
    import retrieve
    d = _scratch(work, "fx_rt4")
    query = {"dialogue_id": "q-untagged", "channel": "web", "vertical": "v",
             "closed_at": "2026-08-02T00:00:00Z",
             "turns": [{"role": "customer", "text": "login fails"}]}
    cap, restore = _fake_llm([_good_response(
        '{"problem_shape":"login fails","constraint":"none","ending":"unknown"}')])
    qid, tags, meta = retrieve.resolve_query(
        query, pool=[], tag_out=str(d / "sessions.jsonl"),
        ratings_out=str(d / "ratings.jsonl"), raw_dir=str(d / "raw"),
        model="fake", base_url=None)
    out = {"delegated_calls": cap["n"], "qid": qid,
           "system_is_frozen": cap["system"] == prompts.TAG_SYSTEM,
           "user_has_frozen_head": cap["user"].startswith(
               "Channel: web\nVertical: v\n\nTranscript:"),
           "tags": tags}
    restore()
    return out


# ---------------------------------------------------------------------------
# static source scans
# ---------------------------------------------------------------------------

# The S1-S7 measured loop (D1 lane). Isolation checks (C-ISO1..5) scope to
# these scripts; bin/llm.py + bin/label_gold_useful.py are the D0 gold-labeler
# lane (founder decision #51, merged in #53) — not part of the loop, reported
# transparently, never imported by the pipeline.
PIPELINE_SCRIPTS = {"common.py", "config.py", "prompts.py", "ingest.py",
                    "tag.py", "retrieve.py", "rank.py", "mix.py", "outcome.py",
                    "update.py", "replay.py"}


def _bin_sources(pipeline_only: bool = False) -> list[tuple[str, str]]:
    """Every script in bin/ — the harness itself is excluded from its own
    source scans (it legitimately mentions keys/forbidden tokens)."""
    return [(p.name, p.read_text(encoding="utf-8"))
            for p in sorted(HERE.glob("*.py"))
            if p.name != "checks.py"
            and (not pipeline_only or p.name in PIPELINE_SCRIPTS)]


def scan_iso1() -> dict:
    """C-ISO1: bin/ imports nothing from research/, openspec/, H1, GitLab-POC."""
    bad = []
    for name, src in _bin_sources():
        for m in re.finditer(r"^\s*(?:import|from)\s+([\w\.]+)", src, re.M):
            mod = m.group(1)
            if mod.startswith(("research", "openspec", "h1", "gitlab")):
                bad.append(f"{name}: {mod}")
    return {"bad": bad}


def scan_iso2() -> dict:
    """C-ISO2: no embeddings, vector stores, DB drivers, or network outside
    the sanctioned wrappers (common.call_llm for the pipeline, llm.call_llm
    for the D0 labeler). The forbidden module names appear nowhere in bin/;
    urllib appears only in common.py and llm.py (the two wrappers)."""
    forbidden = ["qdrant", "neo4j", "psycopg", "chromadb", "openai",
                 "requests", "httpx", "aiohttp", "socket"]
    hits = []
    for name, src in _bin_sources():
        for tok in forbidden:
            if re.search(rf"\b{re.escape(tok)}\b", src, re.I):
                hits.append(f"{name}: {tok}")
    urllib_files = [name for name, src in _bin_sources() if "urllib" in src]
    return {"forbidden_tokens": hits, "urllib_files": urllib_files,
            "non_pipeline_files": sorted(
                {name for name, _ in _bin_sources()} - PIPELINE_SCRIPTS)}


def common_file_text() -> str:
    return (HERE / "common.py").read_text(encoding="utf-8")


def scan_iso3() -> dict:
    """C-ISO3 (pipeline scope): no key/base-url literals beyond the --model
    default in config; key from H2_API_KEY only; call_llm defined once, in
    common.py, and called only from common.py (def) and tag.py (the
    sanctioned S2 path). bin/llm.py is the D0 labeler's own wrapper — a
    separate lane, reported but not part of the pipeline contract."""
    issues = []
    for name, src in _bin_sources():
        if re.search(r"sk-[A-Za-z0-9]{8,}", src):
            issues.append(f"{name}: key literal")
        if re.search(r"https?://", src):
            issues.append(f"{name}: base-url literal")
        if re.search(r"os\.environ\.get\(\"H1_API_KEY\"\)|os\.getenv\(\"H1_API_KEY\"\)",
                     src):
            issues.append(f"{name}: reads the H1 key")
    defs = [name for name, src in _bin_sources(pipeline_only=True)
            if "def call_llm" in src]
    callers = [name for name, src in _bin_sources(pipeline_only=True)
               if "call_llm(" in src]
    return {"issues": issues, "call_llm_defs": defs, "call_llm_callers": callers,
            "non_pipeline_files": sorted(
                {name for name, _ in _bin_sources()} - PIPELINE_SCRIPTS)}


def scan_iso5() -> dict:
    """C-ISO5 (pipeline scope): the pipeline must not write into H1 data/ or
    absolute foreign paths. (D0's llm.py cites its H1 provenance in a
    docstring — that is not a write and not part of the pipeline.)"""
    hits = []
    for name, src in _bin_sources(pipeline_only=True):
        if "h1-experience-cards" in src:
            hits.append(f"{name}: references the H1 pack")
        for m in re.finditer(r'"(/[^"]*)"', src):
            p = m.group(1)
            if p.startswith("/") and not p.startswith(("/opt", "/tmp")):
                hits.append(f"{name}: absolute path {p}")
    return {"hits": hits}


def scan_in6() -> dict:
    """C-IN6: S1 must not set tags and must not call the LLM."""
    src = (HERE / "ingest.py").read_text(encoding="utf-8")
    return {"calls_llm": "call_llm" in src, "imports_tag": "import tag" in src
            or "from tag" in src}


def scan_rt4_src() -> dict:
    src = (HERE / "retrieve.py").read_text(encoding="utf-8")
    return {"calls_llm_directly": "call_llm(" in src,
            "imports_tag": "import tag" in src}


def scan_oc1() -> dict:
    src = (HERE / "outcome.py").read_text(encoding="utf-8")
    return {"llm_flag_guarded": "--source llm is not in this pass" in src}


def scan_rp1() -> dict:
    """C-RP1: replay.py has no prompts, no search/rank logic — it only calls
    the step scripts."""
    src = (HERE / "replay.py").read_text(encoding="utf-8")
    own = [tok for tok in ("call_llm", "overlap_count", "rank_candidates",
                           "build_packet", "render_transcript")
           if re.search(rf"\b{re.escape(tok)}\b", src)]
    if re.search(r"import prompts|from prompts|prompts\.", src):
        own.append("prompts")
    steps = sorted(set(re.findall(r"run_step\(\"(\w+)\.py\"", src)))
    return {"own_logic_tokens": own, "steps_called": steps,
            "uses_subprocess": "subprocess" in src}


def check_prompt_fidelity() -> dict:
    """C-PROMPT: prompts.py strings are exact copies of the PROMPTS.md fenced
    blocks (§2 system, §3 user, §5 header+block, §6 system+user)."""
    md = (ROOT / "PROMPTS.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```\n(.*?)```", md, re.S)
    blocks = [b.strip("\n") for b in blocks]
    # the §5 header fence ends with a {sessions} placeholder line; prompts.py
    # keeps the header alone and the block separately
    normalized = []
    for b in blocks:
        lines = b.splitlines()
        if lines and lines[-1].strip() == "{sessions}":
            lines = lines[:-1]
        normalized.append("\n".join(lines).strip())
    expect_map = [
        ("TAG_SYSTEM", prompts.TAG_SYSTEM),
        ("TAG_USER", prompts.TAG_USER),
        ("PACKET_HEADER", prompts.PACKET_HEADER),
        ("PACKET_SESSION_BLOCK", prompts.PACKET_SESSION_BLOCK),
        ("OUTCOME_SYSTEM", prompts.OUTCOME_SYSTEM),
        ("OUTCOME_USER", prompts.OUTCOME_USER),
    ]
    # order-independent: every constant must equal one fenced block verbatim
    mismatches = []
    for name, const in expect_map:
        if const.strip() not in normalized:
            mismatches.append(f"{name}: prompts.py != PROMPTS.md")
    # transcript render §1
    tr = common.render_transcript([
        {"role": "customer", "text": "hi"},
        {"role": "agent", "text": "ok"},
        {"role": "tool", "name": "purge_session", "text": "done"}])
    render_ok = tr == "customer: hi\nagent: ok\ntool purge_session: done"
    return {"mismatches": mismatches, "render_ok": render_ok}


# ---------------------------------------------------------------------------
# the check builder — every registry id
# ---------------------------------------------------------------------------

def build_checks(ctx: dict) -> list[dict]:
    rows: list[dict] = []
    fx: Path = ctx["fixtures"]
    f: FixtureSuite = ctx["suite"]
    r = f.results
    d = f.data
    pool = r["pool"]
    ratings = r["ratings"]
    dialogues = r["dialogues"]
    qtags = r["query_meta"]["tag_key"]
    query_tags = next(s["tags"] for s in pool
                      if s["source_dialogue_id"] == "d-007")
    cands, ranked, packet, serves, outcomes, ratings_after = (
        r["candidates"], r["ranked"], r["packet"], r["serves"], r["outcomes"],
        r["ratings_after"])
    cand_ids = [c["session_id"] for c in cands]
    cand_srcs = [c["source_dialogue_id"] for c in cands]
    packet_ids = list(packet.get("packet_session_ids") or [])
    by_sid = {s["session_id"]: s for s in pool}
    by_src = {s["source_dialogue_id"]: s for s in pool}

    # ---------------- Изоляция ----------------
    iso1 = scan_iso1()
    expect(rows, "C-ISO1", "iso", True, not iso1["bad"],
           _j(iso1["bad"]), "no imports from research/, openspec/, H1, GitLab-POC in bin/")
    iso2 = scan_iso2()
    expect(rows, "C-ISO2", "iso", True,
           not iso2["forbidden_tokens"]
           and set(iso2["urllib_files"]) <= {"common.py", "llm.py"},
           _j(iso2), "no embeddings/vector stores/DB drivers; urllib only inside the sanctioned "
           "wrappers (common.call_llm for the pipeline, llm.call_llm for the D0 labeler)")
    iso3 = scan_iso3()
    expect(rows, "C-ISO3", "iso", True,
           not iso3["issues"] and iso3["call_llm_defs"] == ["common.py"]
           and set(iso3["call_llm_callers"]) <= {"common.py", "tag.py"},
           _j(iso3), "no key/base-url literals; H2_API_KEY only; the pipeline calls call_llm only "
           "via common.py's single wrapper (tag.py S2). D0's llm.py is a separate lane, reported "
           "but outside the pipeline contract")
    d001_in = any(s.get("source_dialogue_id") == "d-001" for s in cands)
    d014_in = any(s.get("source_dialogue_id") == "d-014" for s in cands)
    expect(rows, "C-ISO4", "iso", True, d001_in and d014_in,
           f"fx-tenant: d-001 in candidates={d001_in}, d-014 (other tenant) in candidates={d014_in}",
           "two dialogues with different tenant_id and same tags are both candidates (fixtures d-001/d-014)")
    expect(rows, "C-ISO5", "iso", True, r["fx_untouched_ok"],
           f"fixtures byte-identical after the run: {r['fx_untouched_ok']}",
           "the run writes only into the workdir; fixtures/ and H1 data/ untouched",
           "fixture files snapshotted before/after the fixture suite")

    # ---------------- S1 ----------------
    in_rows = int(r["s1"].get("input_rows", 0))
    kept = int(r["s1"].get("kept", 0))
    dropped = int(r["s1"].get("dropped", 0))
    expect(rows, "C-IN1", "S1", True, kept + dropped == in_rows,
           f"kept {kept} + dropped {dropped} vs input rows {in_rows}",
           "kept + dropped == rows in the input file")
    n_cust = [sum(1 for t in dl.get("turns", []) if t.get("role") == "customer")
              for dl in dialogues]
    expect(rows, "C-IN2", "S1", True,
           all(n >= 1 for n in n_cust) and dropped == 1,
           f"dropped {dropped} (fixture d-006 has no customer turn); "
           f"customer-turn counts: {n_cust}",
           "only the no-customer chat is dropped; every kept row has >=1 customer turn (fx-drop)")
    bad_keys = [dl["dialogue_id"] for dl in dialogues
                if not all(k in dl for k in ("dialogue_id", "vertical", "agent_id",
                                             "channel", "closed_at", "turns"))
                or any(t.get("role") not in ("customer", "agent", "tool")
                       for t in dl.get("turns", []))]
    expect(rows, "C-IN3", "S1", True, not bad_keys,
           f"rows failing schema: {bad_keys}", "required keys + turns[].role in {customer, agent, tool}")
    ids = [dl["dialogue_id"] for dl in dialogues]
    expect(rows, "C-IN4", "S1", True, len(set(ids)) == len(ids),
           f"rows {len(ids)}, unique {len(set(ids))}", "dialogue_id unique")
    expect(rows, "C-IN5", "S1", True, r["ingest_rerun_identical"],
           "re-ingest rewrote the same bytes", "re-running ingest is byte-identical (upsert, no append-dupes)")
    in6 = scan_in6()
    no_tags = all("tags" not in dl for dl in dialogues)
    expect(rows, "C-IN6", "S1", True,
           not in6["calls_llm"] and not in6["imports_tag"] and no_tags,
           f"ingest.py calls_llm={in6['calls_llm']}, imports_tag={in6['imports_tag']}, "
           f"tags on S1 output={not no_tags}",
           "S1 sets no tags and never calls the LLM")

    # ---------------- S2 ----------------
    pf = check_prompt_fidelity()
    expect(rows, "C-PROMPT", "S2", True,
           not pf["mismatches"] and pf["render_ok"],
           _j(pf), "prompts.py == PROMPTS.md §2/§3/§5/§6; transcript render per §1")
    tg1_bad = [s["session_id"] for s in pool
               if s["session_id"] != common.session_id_of(s["source_dialogue_id"])]
    expect(rows, "C-TG1", "S2", True, not tg1_bad,
           f"bad session_ids: {tg1_bad}",
           "session_id == 's-' + sha256(source_dialogue_id)[:12]")
    tg2_bad = [s["source_dialogue_id"] for s in pool
               if s.get("channel") != "web" or s.get("vertical") != "retail-support"]
    expect(rows, "C-TG2", "S2", True, not tg2_bad,
           f"sessions with wrong channel/vertical: {tg2_bad}",
           "channel/vertical copied from the dialogue, not from the model answer")
    tg3_bad = [s["source_dialogue_id"] for s in pool
               if s["tag_key"] != common.make_tag_key(s["tags"])]
    expect(rows, "C-TG3", "S2", True, not tg3_bad,
           f"tag_key mismatches: {tg3_bad}",
           "tag_key == problem_shape|constraint|ending|channel|vertical, no edge spaces")
    tg4_bad = []
    for s in pool:
        t = s["tags"]
        if t.get("ending") not in {"resolved", "unresolved", "escalated", "unknown"}:
            tg4_bad.append(f"{s['source_dialogue_id']}:ending")
        if len(str(t.get("constraint", "")).split()) > 12 and t.get("constraint") != "none":
            tg4_bad.append(f"{s['source_dialogue_id']}:constraint")
        if len(str(t.get("problem_shape", "")).split()) > 12:
            tg4_bad.append(f"{s['source_dialogue_id']}:problem_shape")
    expect(rows, "C-TG4", "S2", True, not tg4_bad,
           _j(tg4_bad), "ending in enum; constraint <=12 words or 'none'; problem_shape <=12 words")
    dupes = [s["source_dialogue_id"] for s in r["pool_rerun"]
             if sum(1 for x in r["pool_rerun"]
                    if x["source_dialogue_id"] == s["source_dialogue_id"]) > 1]
    stable = all(s["session_id"] == next(
        x["session_id"] for x in r["pool_rerun"]
        if x["source_dialogue_id"] == s["source_dialogue_id"])
        for s in pool)
    expect(rows, "C-TG5", "S2", True, not dupes and stable,
           f"dup source rows after re-tag: {dupes}; session_ids stable={stable}",
           "re-tagging the same dialogue_id updates the same session_id; no second pool row")
    tg6 = test_tg6(fx, ctx["workdir"])
    expect(rows, "C-TG6", "S2", True,
           tg6["pii_no_reject"] and tg6["empty_shape_rejects"],
           _j(tg6), "reject only when problem_shape is empty after the scrub; PII alone never rejects (fx-pii)")
    pii_hits = []
    blob_all = []
    for s in pool:
        blob_all.append(json.dumps(s.get("tags", {}), ensure_ascii=False))
        for t in s.get("turns", []):
            blob_all.append(str(t.get("text", "")))
    blob = "\n".join(blob_all)
    for pat in (r"\S+@\S+", r"\d{10,}", r"\bcvv\b", r"\biban\b", r"\bssn\b"):
        if re.search(pat, blob, re.I):
            pii_hits.append(pat)
    phone = re.findall(r"(?:\+?\d[\d\s\-\.\(\)]{5,}\d)", blob)
    if phone:
        pii_hits.append("phone")
    expect(rows, "C-PII", "S2", True, not pii_hits,
           _j({"patterns": pii_hits, "sessions": len(pool)}),
           "no email/phone/>=10 digits/cvv/iban/ssn anywhere in tags and turns of the whole pool")
    s5 = by_src.get("d-005")
    s5_ok = s5 is not None and s5.get("contains_pii") is True
    if s5 is not None:
        s5_blob = json.dumps(s5["tags"], ensure_ascii=False) + \
            "".join(str(t.get("text", "")) for t in s5.get("turns", []))
        s5_ok = s5_ok and "ada@example.com" not in s5_blob \
            and "+1-617-555-0199" not in s5_blob \
            and not re.search(r"\d{10,}", s5_blob)
    expect(rows, "C-TG7", "S2", True, bool(s5_ok),
           f"d-005 alive={s5 is not None}, contains_pii={s5.get('contains_pii') if s5 else None}, "
           f"raw identifiers gone={s5_ok}",
           "fx-pii: session alive, contains_pii=true, raw email/phone/long number absent")
    s3 = by_src.get("d-003")
    s3_ok = False
    s3_has_gift = False
    if s3 is not None:
        s3_blob = json.dumps(s3["tags"], ensure_ascii=False) + \
            "".join(str(t.get("text", "")) for t in s3.get("turns", []))
        s3_has_gift = "gift card" in s3_blob
        s3_ok = s3.get("contains_pii") is False and s3_has_gift
    expect(rows, "C-TG8", "S2", True, s3_ok,
           f"d-003 contains_pii={s3.get('contains_pii') if s3 else None}, "
           f"transcript has 'gift card'={s3_has_gift}",
           "the word 'card' in 'gift card' alone does not set contains_pii")
    tg9 = test_tg9(fx, ctx["workdir"])
    expect(rows, "C-TG9", "S2", True,
           tg9["rejected"] and tg9["retry_ok"] and tg9["prompt_is_frozen"],
           _j(tg9), "two consecutive unparseable model answers -> reject, no invented tags; "
           "one bad + one good -> retry succeeds with the same prompt")
    raw_files = r["raw_files"]
    tag_calls = int(r["tag_summary"].get("tag_calls", 0)) if r["tag_summary"] else 0
    raw_ok = len(raw_files) == tag_calls
    raw_bad = []
    for fname in raw_files:
        rec = json.loads((d / "raw" / "tag" / fname).read_text())
        for key in ("request", "response", "model", "usage"):
            if key not in rec:
                raw_bad.append(f"{fname}: missing {key}")
    raw_ok = raw_ok and not raw_bad
    expect(rows, "C-TG10", "S2", True, raw_ok,
           f"raw files {len(raw_files)} vs bake tag_calls {tag_calls}; bad keys {raw_bad}",
           "raw/tag/<dialogue_id>.json with request/response/model/usage for every S2 call")
    rating_pairs = {(x["session_id"], x["tag_key"]) for x in ratings}
    missing_start = [s["session_id"] for s in pool
                     if (s["session_id"], s["tag_key"]) not in rating_pairs]
    bad_start = [x for x in ratings
                 if x.get("score") != 0.0 or x.get("shows") != 0]
    expect(rows, "C-TG11", "S2", True, not missing_start and not bad_start,
           f"sessions without a starter rating row: {missing_start}; non-zero starters: {bad_start}",
           "every new session gets a starter rating row under its own tag_key with score=0, shows=0")
    expect(rows, "C-TG12", "S2", False,
           r["tag_summary"].get("unparseable") is not None,
           _j({"tag_calls": tag_calls,
               "unparseable": r["tag_summary"].get("unparseable"),
               "rejected": r["tag_summary"].get("rejected")}),
           "share of unparseable JSON and reject rate are recorded (bake summary)", "SOFT")
    ground = {"with_shape": 0, "with_constraint": 0, "grounded": 0}
    for s in pool:
        shape = str(s["tags"].get("problem_shape", "")).strip()
        cons = str(s["tags"].get("constraint", "")).strip()
        trans = " ".join(str(t.get("text", "")) for t in s.get("turns", []))
        if shape:
            ground["with_shape"] += 1
            if any(len(w) >= 5 and w in trans for w in shape.split()):
                ground["grounded"] += 1
        if cons and cons != "none":
            ground["with_constraint"] += 1
    expect(rows, "C-TG13", "S2", False, ground["with_shape"] > 0,
           _j(ground), "grounding: a >=5-char word of problem_shape present in the transcript; "
           "counted, never fails the run", "SOFT")

    # ---------------- S3 ----------------
    expect(rows, "C-SELF", "S3", True,
           common.session_id_of("d-007") not in cand_ids and "d-007" not in cand_srcs,
           f"query session {common.session_id_of('d-007')} / source d-007 in candidates: "
           f"{common.session_id_of('d-007') in cand_ids or 'd-007' in cand_srcs}",
           "the query never appears among its own candidates")
    rt1_bad = [c["source_dialogue_id"] for c in cands
               if retrieve_overlap(query_tags, c["tags"]) < config.TAG_FIELDS_MIN]
    expect(rows, "C-RT1", "S3", True, not rt1_bad,
           f"candidates below TAG_FIELDS_MIN={config.TAG_FIELDS_MIN}: {rt1_bad}",
           "a candidate must share >= TAG_FIELDS_MIN tag fields with the query; zero overlap is not a candidate")
    expect(rows, "C-RT2", "S3", True,
           "d-001" in cand_srcs and "d-002" in cand_srcs,
           f"d-001 in candidates={'d-001' in cand_srcs}, d-002 in candidates={'d-002' in cand_srcs}",
           "fx-similar: d-007's candidates include d-001 and d-002")
    d3 = by_src["d-003"]
    d3_ov = retrieve_overlap(query_tags, d3["tags"])
    expect(rows, "C-RT3", "S3", True,
           (d3_ov < config.TAG_FIELDS_MIN) == ("d-003" not in cand_srcs),
           f"d-003 overlap {d3_ov} vs TAG_FIELDS_MIN {config.TAG_FIELDS_MIN}; "
           f"in candidates={'d-003' in cand_srcs}",
           "fx-far: d-003 is not required in d-007's candidates when shared fields < TAG_FIELDS_MIN")
    rt4_src = scan_rt4_src()
    rt4 = test_rt4(fx, ctx["workdir"])
    expect(rows, "C-RT4", "S3", True,
           not rt4_src["calls_llm_directly"] and rt4_src["imports_tag"]
           and rt4["delegated_calls"] == 1 and rt4["system_is_frozen"],
           _j({"src": rt4_src, "delegate": rt4}), "S3 calls no LLM itself; an untagged query is "
           "delegated to tag.py with the same PROMPTS.md §2-§3 strings")
    expect(rows, "C-RT5", "S3", True,
           r["rt5_rerun"] == sorted(cand_ids),
           f"first run {sorted(cand_ids)} vs re-run {r['rt5_rerun']}",
           "re-running retrieve on the same pool and query yields the same candidate id set")

    # ---------------- S4 ----------------
    expected_ranked = rank_candidates_ids(cands, ratings, qtags)
    rk1_ok = expected_ranked is not None and expected_ranked[:len(expected_ranked)] == \
        [x["session_id"] for x in ranked]
    top_slots = [x["session_id"] for x in ranked[:config.MAX_PACKET - config.EXPLORE_SLOTS]]
    rk1_scores = [(sid, rating_score(sid, qtags, ratings)) for sid in top_slots]
    expect(rows, "C-RK1", "S4", True, rk1_ok and len(top_slots) == 2,
           f"top slots {top_slots} with (score,shows) {rk1_scores}; "
           f"full recompute matches={rk1_ok}",
           "first MAX_PACKET-EXPLORE_SLOTS slots are max-score pairs for (session_id, query tag_key); "
           "missing rating row -> score=0, shows=0")
    explore = ranked[config.MAX_PACKET - config.EXPLORE_SLOTS]["session_id"] \
        if len(ranked) > config.MAX_PACKET - config.EXPLORE_SLOTS else None
    expected_explore = explore_pick(cands, ratings, qtags)
    expect(rows, "C-RK2", "S4", True,
           explore is not None and explore == expected_explore,
           f"explore slot {explore} vs recomputed {expected_explore}",
           "the last slot is exploration: fewer shows, then older last_shown_at (null oldest), "
           "then smaller session_id")
    expect(rows, "C-RK3", "S4", True,
           len({x["session_id"] for x in ranked}) == len(ranked),
           f"ranked ids {[x['session_id'] for x in ranked]}",
           "exploration never duplicates an already selected id")
    rot = scenario_rotate(fx, ctx["workdir"])
    expect(rows, "C-RK4", "S4", True,
           len(rot["ranked_ids"]) == 3 and rot["explore_slot"] != rot["third_by_score"],
           _j(rot), "fx-rotate: five same-tag candidates -> packet of 3 and the third id is not "
           "forced to be the third by score")
    expect(rows, "C-RK5", "S4", True, r["rk5_rerun_identical"],
           "ranked.jsonl byte-identical on re-run", "no LLM; re-ranking the same ratings is byte-identical")
    rk6 = scenario_rk6(fx, ctx["workdir"])
    expect(rows, "C-RK6", "S4", False,
           rk6["len"] == 2 and rk6["ranked_ids"][0] == rk6["top_by_score"],
           _j(rk6), "candidates <= MAX_PACKET -> the packet is all candidates in score order, "
           "no invented explore slot", "SOFT")

    # ---------------- S5 ----------------
    expect(rows, "C-SIZE", "S5", True,
           len(packet_ids) <= config.MAX_PACKET,
           f"packet sessions {len(packet_ids)} (MAX_PACKET={config.MAX_PACKET})",
           "no more than MAX_PACKET sessions; empty ranked -> header-only packet, no invented sessions")
    mx1_bad = []
    for sid in packet_ids:
        s = by_sid.get(sid)
        if s is None:
            mx1_bad.append(f"{sid}: not in pool")
            continue
        for t in s.get("turns", []):
            if str(t.get("text", "")).strip() and \
               str(t.get("text", "")) not in packet["packet_text"]:
                mx1_bad.append(f"{sid}: turn text missing from packet")
    expect(rows, "C-MX1", "S5", True, not mx1_bad,
           _j(mx1_bad), "the packet carries whole turns, not summaries or cards")
    blocks = re.split(r"\n\n", packet["packet_text"])
    mx2_blocks_ok = all(
        re.match(r"^\[s-[0-9a-f]{12}\] tags: ", b) for b in blocks[1:])
    mx2_ok = packet["packet_text"].strip().startswith(
        prompts.PACKET_HEADER.strip().splitlines()[0]) and mx2_blocks_ok
    expect(rows, "C-MX2", "S5", True, mx2_ok,
           f"header ok={packet['packet_text'].strip().startswith(prompts.PACKET_HEADER.strip().splitlines()[0])}, "
           f"blocks start with [session_id]={mx2_blocks_ok}",
           "packet text is the PROMPTS.md §5 template: header on top, every block starts with [session_id]")
    expect(rows, "C-MX3", "S5", True,
           set(packet_ids) <= {x["session_id"] for x in ranked} and
           common.session_id_of("d-007") not in packet_ids,
           f"packet ids {packet_ids} vs ranked ids {[x['session_id'] for x in ranked]}",
           "self-mix forbidden; no id outside ranked (C-SELF on the mix output)")
    srv = serves[-1] if serves else {}
    expect(rows, "C-MX4", "S5", True,
           srv.get("query_id") == "d-007" and srv.get("session_ids") == packet_ids
           and srv.get("tag_key") == qtags,
           _j(srv), "serves.jsonl holds query_id, tag_key and the packet session_ids in packet order")
    expect(rows, "C-MX5", "S5", True,
           "packet_text" in packet and "packet_session_ids" in packet,
           f"packet keys: {sorted(packet.keys())}",
           "packet.json holds both packet_text and the session id list")
    expect(rows, "C-MX6", "S5", True, r["mx6_rerun_identical"],
           "packet.json byte-identical on re-run", "re-mixing the same ranked yields the same packet_text")

    # ---------------- S6 ----------------
    oc1_src = scan_oc1()
    expect(rows, "C-OC1", "S6", True,
           oc1_src["llm_flag_guarded"] and all(o.get("source") == "gold"
                                               for o in outcomes),
           _j({"llm_guard": oc1_src["llm_flag_guarded"],
               "sources": sorted({o.get("source") for o in outcomes})}),
           "the lab run uses --source gold; the LLM helper is not called in this mode")
    oc2 = recompute_outcome(packet_ids, by_sid, fx, "d-007")
    expect(rows, "C-OC2", "S6", True,
           outcomes and outcomes[-1]["outcome"] == oc2,
           f"outcome.py {outcomes[-1]['outcome'] if outcomes else None} vs gold rule {oc2}",
           "gold outcome: packet ∩ useful non-empty -> good; non-empty packet, empty ∩ -> bad; "
           "empty packet -> unclear")
    expect(rows, "C-OC3", "S6", True,
           all(o.get("outcome") in {"good", "bad", "unclear"} for o in outcomes),
           _j([o.get("outcome") for o in outcomes]),
           "outcome ∈ {good, bad, unclear} only")
    oc4_ok = all(all(k in o for k in ("query_id", "packet_session_ids", "tag_key",
                                      "outcome", "source", "closed_at"))
                 for o in outcomes)
    expect(rows, "C-OC4", "S6", True, oc4_ok,
           _j([sorted(o.keys()) for o in outcomes]),
           "outcome row carries query_id, packet_session_ids, tag_key, outcome, source, closed_at")
    rc_llm, _ = _run([str(HERE / "outcome.py"), "--query",
                      str(fx / "queries" / "d-007.json"), "--source", "llm"],
                     cwd=ctx["workdir"], expect_fail=True)
    expect(rows, "C-OC5", "S6", True, rc_llm != 0,
           f"--source llm exit code {rc_llm}",
           "--source llm is guarded out in this pass (LAB-BRIEF §3); llm-mode rows never mix with "
           "gold aggregates. Full separation re-opens if L3 opens")

    # ---------------- S7 ----------------
    touched_pairs = {(sid, qtags) for sid in packet_ids}
    untouched = []
    for x in ratings:
        if (x["session_id"], x["tag_key"]) not in touched_pairs:
            old = next((y for y in ratings_after
                        if y["session_id"] == x["session_id"]
                        and y["tag_key"] == x["tag_key"]), None)
            if old is not None and old != x:
                untouched.append(f"{x['session_id']}|{x['tag_key']}")
    expect(rows, "C-DELTA", "S7", True, not untouched,
           f"changed non-packet rows: {untouched}",
           "delta and shows+=1 apply only to (packet session, query tag_key) pairs; other rows stand")
    up1_bad = []
    for sid in packet_ids:
        new = next((y for y in ratings_after
                    if y["session_id"] == sid and y["tag_key"] == qtags), None)
        old = next((y for y in ratings if y["session_id"] == sid
                    and y["tag_key"] == qtags), None)
        if new is None:
            up1_bad.append(f"{sid}: no new row")
            continue
        delta = {"good": config.GOOD_DELTA, "bad": config.BAD_DELTA,
                 "unclear": config.UNCLEAR_DELTA}[outcomes[-1]["outcome"]]
        exp_score = round((old["score"] if old else 0.0) + delta, 6)
        if abs(new["score"] - exp_score) > 1e-9:
            up1_bad.append(f"{sid}: score {new['score']} != {exp_score}")
        if new[outcomes[-1]["outcome"]] != (old[outcomes[-1]["outcome"]] if old else 0) + 1:
            up1_bad.append(f"{sid}: outcome counter")
        if new["shows"] != (old["shows"] if old else 0) + 1:
            up1_bad.append(f"{sid}: shows")
    expect(rows, "C-UP1", "S7", True, not up1_bad,
           _j(up1_bad), "good -> GOOD_DELTA, bad -> BAD_DELTA, unclear -> UNCLEAR_DELTA; "
           "the matching outcome counter += 1")
    exp_shown_at = outcomes[-1].get("closed_at")
    up2_bad = [sid for sid in packet_ids
               if next((y for y in ratings_after if y["session_id"] == sid
                        and y["tag_key"] == qtags), {}).get("last_shown_at") != exp_shown_at]
    expect(rows, "C-UP2", "S7", True, not up2_bad,
           f"last_shown_at rows: {up2_bad}", "last_shown_at = outcome.closed_at")
    decay = scenario_decay(fx, ctx["workdir"])
    expect(rows, "C-UP3", "S7", True,
           decay["shows"] == 5 and abs(decay["score"] - 0.9) < 1e-9,
           _j(decay), "fx-decay: when shows % DECAY_EVERY_SHOWS == 0 the score drops by "
           "DECAY_AMOUNT after the outcome delta")
    up4_bad = [x["session_id"] for x in ratings
               if (x["session_id"], x["tag_key"]) not in touched_pairs
               and any(y["session_id"] == x["session_id"] and y["tag_key"] == x["tag_key"]
                       and y != x for y in ratings_after)]
    expect(rows, "C-UP4", "S7", True, not up4_bad,
           f"non-packet rows with delta/decay: {up4_bad}",
           "sessions outside the packet get neither delta nor decay")
    expect(rows, "C-UP5", "S7", True, r["up5_rerun_identical"],
           "second update over the same outcomes.jsonl applied nothing (ratings byte-identical)",
           "update is idempotent per query_id (update_state.json); a second pass does not re-apply")

    # ---------------- replay ----------------
    qc = by_src["d-007"]["closed_at"]
    future = [c["source_dialogue_id"] for c in cands
              if (c.get("closed_at") or "") >= qc]
    rp1 = scan_rp1()
    expect(rows, "C-FUTURE", "replay", True, not future,
           f"future candidates: {future} (query closed_at {qc})",
           "no session with closed_at >= query.closed_at in candidates/packet. The replay-order "
           "half (S3-S5 before S2 lay) is enforced by replay.py's loop and closes with the runner",
           "data-level check at S0; ordering verified statically in C-RP1")
    expect(rows, "C-RP1", "replay", True,
           not rp1["own_logic_tokens"]
           and rp1["steps_called"] == ["mix", "outcome", "rank", "retrieve", "tag", "update"]
           and rp1["uses_subprocess"],
           _j(rp1), "replay.py has no own prompts/search/rank logic; it only calls the step scripts")
    nc1 = scenario_nc1(fx, ctx["workdir"])
    expect(rows, "C-RP2", "replay", True,
           nc1["candidates"] == 0 and nc1["ranked"] == 0 and nc1["packet_ids"] == []
           and nc1["header_only"],
           _j(nc1), "an empty pool/early dialogues yield a valid empty packet — not an error")

    # ---------------- D0 gold-useful (Phase B) ----------------
    # When the D0 artifacts exist, real C-GD1..8 rows replace the deferred
    # placeholders; otherwise the ids stay deferred (S0 unaffected).
    if run_d0_checks(rows, ctx):
        for cid in GD_IDS:
            DEFERRED_S0.pop(cid, None)

    # ---------------- deferred ----------------
    for cid, step, hard in REGISTRY:
        if cid in DEFERRED_S0:
            expect(rows, cid, step, hard, None, "deferred at S0",
                   "full contract closes at S1/D4/D5", DEFERRED_S0[cid])

    # ---------------- NC1 (S0 part, hard) ----------------
    expect(rows, "C-NC1", "control", True,
           nc1["candidates"] == 0 and nc1["ranked"] == 0 and nc1["packet_ids"] == []
           and nc1["header_only"],
           _j(nc1),
           "empty pool -> all packets empty, no self-mix (B0==T closes with eval.py at D4)")

    # completeness: every registry id emitted exactly once
    seen = [row["check_id"] for row in rows]
    dup = sorted({c for c in seen if seen.count(c) > 1})
    missing = [c for c in ALL_IDS if c not in seen]
    expect(rows, "C-REGISTRY", "harness", True, not dup and not missing,
           f"rows {len(seen)}, duplicate ids {dup}, missing ids {missing}",
           "every CHECKS.md id appears in checks.json exactly once (missing id = fail)")

    return rows


# ---------------------------------------------------------------------------
# D0 gold-useful QA (C-GD1..C-GD8, ROUND-0-PLAN §7) — runs on the Phase B
# artifacts when they exist; otherwise the ids stay deferred at S0.
# ---------------------------------------------------------------------------

PII_RE = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")),
    ("digits10+", re.compile(r"\d{10,}")),
    ("ssn", re.compile(r"\d{3}-\d{2}-\d{4}")),
    ("iban", re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}")),
    ("phone", re.compile(r"\+?\d{1,3}[\s().-]?\d{3}[\s().-]?\d{3}[\s().-]?\d{2,4}")),
]


def _read_gold(path: Path) -> list[dict]:
    """Read a gold-format jsonl, skipping the mandatory `#` header lines."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        rows.append(json.loads(s))
    return rows


def run_d0_checks(rows: list[dict], ctx: dict) -> bool:
    """Emit C-GD1..8 against data/{gold_useful,d0_slice,raw_gold_useful,...}.

    Returns True when the artifacts existed (real rows emitted, deferred
    placeholders must be dropped by the caller).
    """
    h2 = Path(__file__).resolve().parent.parent
    gold_path = h2 / "data" / "gold_useful.jsonl"
    slice_path = h2 / "data" / "d0_slice.jsonl"
    if not (gold_path.exists() and slice_path.exists()):
        return False

    import label_gold_useful as lg  # deferred: only when D0 artifacts exist

    gold = _read_gold(gold_path)
    slice_rows = _read_gold(slice_path)
    by_q = {r["query_id"]: r for r in slice_rows}
    manifest_path = h2 / "data" / "gold_useful.manifest.json"
    manifest = (json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.exists() else {})
    raw_dir = h2 / "data" / "raw_gold_useful"

    # corpus maps on the same synthetic clock as the labeler
    pool = lg.load_raw(h2 / "data" / "abcd_1000_pool.jsonl")
    holdout = lg.load_raw(h2 / "data" / "abcd_200_holdout.jsonl")
    for i, r in enumerate(pool, start=1):
        r["_index"] = i
    for i, r in enumerate(holdout, start=len(pool) + 1):
        r["_index"] = i
    pool_closed = {lg.dialogue_id(r): lg.synthetic_closed_at(r["_index"]) for r in pool}
    pool_guideline = {lg.dialogue_id(r): r.get("unlock_guideline", "") for r in pool}
    hold_guideline = {lg.dialogue_id(r): r.get("unlock_guideline", "") for r in holdout}

    # C-GD1 — mandatory `#` header
    head = gold_path.read_text(encoding="utf-8").splitlines()[:2]
    hdr_ok = (len(head) >= 2
              and head[0].startswith("#")
              and "NOT HUMAN GOLD" in head[0].upper()
              and "AGENT-LABELED" in head[0].upper()
              and all(tok in head[1] for tok in ("prompt_sha=", "corpus_sha=",
                                                 "slice_sha=", "created_at=")))
    expect(rows, "C-GD1", "D0", True, hdr_ok, " | ".join(head[:2]),
           "# header marking agent-labeled / NOT human gold + sha/created line")

    # C-GD2 — no future leak
    leak = []
    for r in gold:
        qc = by_q.get(r["query_id"], {}).get("closed_at", "")
        for uid in r.get("useful_dialogue_ids", []):
            pc = pool_closed.get(uid)
            if pc is None or pc >= qc:
                leak.append(f"{r['query_id']}->{uid}")
    expect(rows, "C-GD2", "D0", True, not leak,
           f"future/unknown refs: {leak[:5]}",
           "every useful id has closed_at strictly earlier than the query's")

    # C-GD3 — no PII in the gold output (notes + ids)
    pii_hits = []
    for r in gold:
        text = (r.get("notes") or "") + " " + " ".join(r.get("useful_dialogue_ids", []))
        for name, rx in PII_RE:
            m = rx.search(text)
            if m and (name != "phone"
                      or len(re.sub(r"[^\d]", "", m.group(0))) >= 10):
                pii_hits.append(f"{r['query_id']}:{name}:{m.group(0)[:20]}")
    expect(rows, "C-GD3", "D0", True, not pii_hits,
           f"hits: {pii_hits[:6]}",
           "no email / phone / >=10 digits / cvv / iban / ssn in gold output")

    # C-GD4 — rows == slice, ids unique and within the slice
    gold_ids = [r["query_id"] for r in gold]
    slice_ids = [r["query_id"] for r in slice_rows]
    gd4_ok = (len(gold) == len(slice_rows)
              and len(set(gold_ids)) == len(gold_ids)
              and set(gold_ids) == set(slice_ids))
    expect(rows, "C-GD4", "D0", True, gd4_ok,
           f"gold rows {len(gold)} vs slice {len(slice_rows)}; "
           f"unique {len(set(gold_ids))}; extra {sorted(set(gold_ids) - set(slice_ids))[:5]}",
           "rows == 60 slice rows; query_id unique and ⊆ d0_slice.jsonl")

    # C-GD5 — one raw record per row
    raw_files = sorted(raw_dir.glob("*.json")) if raw_dir.is_dir() else []
    raw_ids = {p.stem for p in raw_files}
    expect(rows, "C-GD5", "D0", True,
           len(raw_files) == len(gold) and set(gold_ids) <= raw_ids,
           f"raw files {len(raw_files)} vs gold rows {len(gold)}; "
           f"missing {sorted(set(gold_ids) - raw_ids)[:5]}",
           "data/raw_gold_useful/ has one <query_id>.json per gold row")

    # C-GD6 (SOFT) — seed direction agreement on the 6 seed rows
    seed_path = h2 / "data" / "gold_useful.seed.jsonl"
    seed_by = {}
    if seed_path.exists():
        seed_by = {r["query_id"]: bool(r.get("useful_dialogue_ids"))
                   for r in _read_gold(seed_path)}
    gold_by = {r["query_id"]: bool(r.get("useful_dialogue_ids")) for r in gold}
    contrad = [qid for qid, sdir in seed_by.items()
               if qid in gold_by and sdir != gold_by[qid]]
    expect(rows, "C-GD6", "D0", False, not contrad,
           f"seed queries with opposite direction: {contrad}",
           "on the 6 seed rows the empty/non-empty direction matches the seed")

    # C-GD7 — anti-H1 collinearity (useful sets strictly finer than guideline buckets)
    non_empty = [r for r in gold if r.get("useful_dialogue_ids")]
    h1_sig, howto_viol = [], []
    for r in non_empty:
        q = by_q.get(r["query_id"], {})
        g = hold_guideline.get(r["query_id"], "")
        qc = q.get("closed_at", "")
        same_g = [did for did, pc in pool_closed.items()
                  if pool_guideline.get(did) == g and pc < qc]
        n_useful = len(r["useful_dialogue_ids"])
        if same_g and n_useful == len(same_g):
            h1_sig.append(r["query_id"])
        if q.get("family") == "howto" and same_g and n_useful >= len(same_g):
            howto_viol.append(r["query_id"])
    gd7_ok = (len(h1_sig) <= 0.2 * max(len(non_empty), 1) and not howto_viol)
    expect(rows, "C-GD7", "D0", True, gd7_ok,
           f"H1-signature rows {len(h1_sig)}/{len(non_empty)} non-empty "
           f"({h1_sig[:5]}); howto no-exclusion {howto_viol[:5]}",
           "<=20% of non-empty rows equal the whole same-guideline bucket; "
           "every FAQ how-to row excludes >=1 same-guideline session when one exists")

    # C-GD8 — D0 manifest model + S2 loop model untouched
    gd8_ok = (manifest.get("model") == "deepseek-v4-pro"
              and lg.MODEL_DEFAULT == "deepseek-v4-pro"
              and config.DEFAULT_MODEL == "deepseek-v4-flash")
    expect(rows, "C-GD8", "D0", True, gd8_ok,
           f"manifest model={manifest.get('model')} "
           f"labeler_default={lg.MODEL_DEFAULT} S2_default={config.DEFAULT_MODEL}",
           "labeler_model == deepseek-v4-pro; the S2 measured-loop model stays deepseek-v4-flash")

    return True


# ---------------------------------------------------------------------------
# pure recomputations used by the checks (same rules as bin/, independent impl)
# ---------------------------------------------------------------------------

def retrieve_overlap(query_tags: dict, session_tags: dict) -> int:
    return sum(1 for f in config.TAG_FIELDS
               if str(query_tags.get(f, "")).strip() != ""
               and str(query_tags.get(f, "")).strip()
               == str(session_tags.get(f, "")).strip())


def rating_score(session_id: str, tag_key: str, ratings: list[dict]) -> tuple:
    r = next((x for x in ratings
              if x["session_id"] == session_id and x["tag_key"] == tag_key), None)
    if r is None:
        return (0.0, 0, None)
    return (float(r.get("score") or 0.0), int(r.get("shows") or 0),
            r.get("last_shown_at"))


def rank_candidates_ids(cands: list[dict], ratings: list[dict],
                        tag_key: str) -> list[str] | None:
    """Independent re-implementation of rank.py's pick for the query tag_key."""
    scored = [(c["session_id"], *rating_score(c["session_id"], tag_key, ratings))
              for c in cands]
    ordered = sorted(scored, key=lambda t: (-t[1], t[2], t[3] is not None,
                                            t[3] or "", t[0]))
    if len(ordered) <= config.MAX_PACKET:
        return [t[0] for t in ordered]
    top = ordered[:config.MAX_PACKET - config.EXPLORE_SLOTS]
    top_ids = {t[0] for t in top}
    rest = [t for t in ordered if t[0] not in top_ids]
    explore = sorted(rest, key=lambda t: (t[2], t[3] is not None, t[3] or "", t[0]))
    explore = explore[:config.EXPLORE_SLOTS]
    return [t[0] for t in top] + [t[0] for t in explore]


def explore_pick(cands: list[dict], ratings: list[dict], tag_key: str) -> str | None:
    """The recomputed explore slot (fewest shows, oldest last_shown_at, smallest id)."""
    scored = [(c["session_id"], *rating_score(c["session_id"], tag_key, ratings))
              for c in cands]
    ordered = sorted(scored, key=lambda t: (-t[1], t[2], t[3] is not None,
                                            t[3] or "", t[0]))
    if len(ordered) <= config.MAX_PACKET:
        return None
    top_ids = {t[0] for t in ordered[:config.MAX_PACKET - config.EXPLORE_SLOTS]}
    rest = [t for t in ordered if t[0] not in top_ids]
    explore = sorted(rest, key=lambda t: (t[2], t[3] is not None, t[3] or "", t[0]))
    return explore[0][0] if explore else None


def recompute_outcome(packet_ids: list[str], by_sid: dict, fx: Path,
                      qid: str) -> str:
    useful = []
    for row in common.read_jsonl(fx / "gold_useful.jsonl"):
        if row.get("query_id") == qid:
            useful = list(row.get("useful_dialogue_ids") or [])
            break
    pd = [by_sid[sid]["source_dialogue_id"] for sid in packet_ids
          if sid in by_sid]
    pd = [d for d in pd if d]
    if not packet_ids:
        return "unclear"
    return "good" if any(d in useful for d in pd) else "bad"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="H2 Layer-1 contract harness (CHECKS.md). "
                    "Deterministic, zero LLM calls: S2 replays the committed "
                    "baked output. Writes checks.json + report.md into the "
                    "workdir; exits non-zero when an in-scope HARD fails.")
    ap.add_argument("--fixtures", default=str(ROOT / "fixtures"))
    ap.add_argument("--workdir", default=None,
                    help="scratch/run dir; default: a fresh tempdir")
    ap.add_argument("--out", default=None, help="checks.json path (default: <workdir>/checks.json)")
    ap.add_argument("--report", default=None, help="report.md path (default: <workdir>/report.md)")
    args = ap.parse_args(argv)

    fx = Path(args.fixtures).resolve()
    work = Path(args.workdir).resolve() if args.workdir \
        else Path(tempfile.mkdtemp(prefix="h2_checks_"))
    work.mkdir(parents=True, exist_ok=True)
    checks_out = Path(args.out).resolve() if args.out else work / "checks.json"
    report_out = Path(args.report).resolve() if args.report else work / "report.md"

    suite = FixtureSuite(fx, work)
    suite.results = suite.run_all()
    ctx = {"fixtures": fx, "workdir": work, "suite": suite}
    rows = build_checks(ctx)

    # sort rows in CHECKS.md order for stable output
    order = {cid: i for i, cid in enumerate(ALL_IDS)}
    rows.sort(key=lambda r: (order.get(r["check_id"], 999), r["check_id"]))

    checks_out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")

    hard = [r for r in rows if r["hard"]]
    hard_failed = [r for r in hard if r["passed"] is False]
    hard_passed = [r for r in hard if r["passed"] is True]
    hard_deferred = [r for r in hard if r["passed"] is None]
    soft = [r for r in rows if not r["hard"]]
    soft_failed = [r for r in soft if r["passed"] is False]

    write_report(report_out, rows, hard_passed, hard_failed, hard_deferred,
                 soft_failed, work)

    summary = {
        "ok": len(hard_failed) == 0,
        "step": "checks",
        "script": "checks.py",
        "stage": "S0",
        "checks_total": len(rows),
        "hard_passed": len(hard_passed),
        "hard_failed": len(hard_failed),
        "hard_deferred": len(hard_deferred),
        "soft_total": len(soft),
        "soft_failed": len(soft_failed),
        "failed_ids": [r["check_id"] for r in hard_failed],
        "workdir": str(work),
        "checks_out": str(checks_out),
        "report": str(report_out),
        "note": "S0 gate: all HARDs of the CHECKS.md 'Что прогонять на S0' block green",
    }
    common.print_summary(summary)
    return 1 if hard_failed else 0


def write_report(report_out: Path, rows: list[dict], hard_passed: list[dict],
                 hard_failed: list[dict], hard_deferred: list[dict],
                 soft_failed: list[dict], work: Path) -> None:
    lines = [
        "# H2 — checks report (S0)",
        "",
        f"- run dir: `{work}`",
        f"- stage: S0 smoke · fixtures only · zero LLM calls (S2 replays the committed bake)",
        f"- HARD: {len(hard_passed)} passed, {len(hard_failed)} failed, "
        f"{len(hard_deferred)} deferred · SOFT: {len(rows) - len([r for r in rows if r['hard']])} "
        f"total, {len(soft_failed)} failed",
        "",
        "## Чеки",
        "",
        "| id | step | hard | passed | observed | expected | note |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        passed = "PASS" if r["passed"] is True else ("FAIL" if r["passed"] is False else "deferred")
        lines.append(f"| {r['check_id']} | {r['step']} | {'HARD' if r['hard'] else 'SOFT'} | "
                     f"{passed} | {r['observed'][:90]} | {r['expected'][:90]} | {r['note'][:60]} |")
    if hard_failed:
        lines += ["", "## HARD failures", ""]
        for r in hard_failed:
            lines.append(f"- **{r['check_id']}**: {r['observed']}")
    if hard_deferred:
        lines += ["", "## Deferred (needs runner/eval/corpus)", ""]
        for r in hard_deferred:
            lines.append(f"- {r['check_id']}: {r['note']}")
    lines += ["", "Аудит A1–A6 и вердикт §6.4 — на S1/S2, не на S0 (мало n)."]
    report_out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
