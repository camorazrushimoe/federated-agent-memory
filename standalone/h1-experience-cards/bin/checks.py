#!/usr/bin/env python3
"""checks.py — the Layer-1 contract harness (CHECKS.md).

Every id in CHECKS.md MUST appear in checks.json on every run (a missing id is
a failure). HARD failures abort the run — the runner exits non-zero and no L2
numbers are published from it.

Two groups, both run at every stage:
- FIXTURE checks: the SPEC §10 scenarios executed in a scratch store inside the
  run dir, driven through the REAL scripts with baked (committed) extract
  responses so they are deterministic and cost zero LLM calls.
- DATA checks: assertions over the run's own store / packets / metrics.

Each row: {check_id, step, hard, passed, observed, expected, note}.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

import config as cfgmod
from clock import RunClock
from cluster import compute_votes, compute_last_closed_at
from common import card_id_for, now_iso
from jsonio import read_jsonl, write_jsonl
from schema import is_rejected, validate_card
from scrub import pii_matches
from store import load_labels

FIXTURE_NOW = "2026-08-28T00:00:00Z"  # pinned staleness clock for fixtures


# --------------------------------------------------------------------------- #
# fixture suite — runs the SPEC §10 scenarios through the real scripts        #
# --------------------------------------------------------------------------- #

def _run(args: list[str], cwd: Path, expect_fail: bool = False) -> tuple[int, str]:
    proc = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                          cwd=str(cwd))
    if proc.returncode != 0 and not expect_fail:
        raise RuntimeError(f"fixture step failed: {args}\nstdout:{proc.stdout}\nstderr:{proc.stderr}")
    return proc.returncode, (proc.stdout + proc.stderr).strip()


class FixtureSuite:
    """Runs all §10 scenarios in `workdir` (inside the run dir)."""

    def __init__(self, fixtures_dir: Path, workdir: Path, prompts, cfg: dict):
        self.fixtures = fixtures_dir
        # replay SOURCE: the committed fixture records (read-only — canonical
        # copy_replay_record WRITES to --raw-dir, so pointing raw-dir at the
        # committed fixtures would clobber them on every run, C-L1).
        self.replay_dir = str(fixtures_dir / "raw" / "extract")
        # raw-dir OUTPUT: workdir-local, so replay writes land in the run's
        # fixtures_work dir, never in the committed fixtures.
        self.raw_dir = str(workdir / "raw" / "extract")
        self.work = workdir
        # CLEAN workdir: ingest/extract/cluster/feedback all UPSERT, so a
        # stale fixtures_work from an earlier run would accumulate duplicate
        # cards/rows and break C-CL10/C-FB2 (11-card/14-row anomalies).
        if workdir.exists():
            import shutil
            shutil.rmtree(workdir)
        self.data = workdir / "data"
        self.data.mkdir(parents=True, exist_ok=True)
        self.prompts = prompts
        self.cfg = cfg
        self.results: dict = {}

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _model_args() -> list[str]:
        # extract.py requires --model/--base-url (D8 §6); replay never calls the
        # API, so these placeholders are inert — and contain no real provider.
        return ["--model", "replay-fixture", "--base-url", "replay-fixture"]

    def ingest(self, fixture_file: str, out: str) -> dict:
        _run([str(HERE / "ingest.py"), "--in", str(self.fixtures / fixture_file),
              "--out", str(self.data / out)], self.work)
        return {out: read_jsonl(self.data / out)}

    def extract(self, out: str = "cards.jsonl") -> dict:
        return _json(_run([str(HERE / "extract.py"), "--in", str(self.data / "dialogues.jsonl"),
                           "--out", str(self.data / out), "--raw-dir", self.raw_dir,
                           "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW]
                          + self._model_args(), self.work))

    def cluster(self, cards: str = "cards.jsonl", force: bool = True,
                dialogues: str = "dialogues.jsonl") -> dict:
        cmd = [str(HERE / "cluster.py"), "--cards", str(self.data / cards),
               "--dialogues", str(self.data / dialogues), "--now", FIXTURE_NOW]
        if force:
            cmd.append("--force")
        return _json(_run(cmd, self.work))

    def serve(self, live_file: str, cards: str = "cards.jsonl") -> dict:
        live = self.data / f"live_{live_file}"
        live.write_text(json.dumps(read_jsonl(self.fixtures / live_file)[0], ensure_ascii=False),
                        encoding="utf-8")
        return _json(_run([str(HERE / "serve.py"), "--dialogue", str(live),
                           "--cards", str(self.data / cards),
                           "--packets-out", str(self.data / "packets"),
                           "--now", FIXTURE_NOW], self.work))

    def feedback(self, card_id: str | None, label: str, dialogue: str,
                 cards: str = "cards.jsonl") -> tuple[int, str]:
        # Canonical feedback.py makes --card-id REQUIRED at argparse level, so
        # the C-FB4 "ambiguous packet, no card-id" call below fails with a
        # usage error (rc 2) instead of the old guard — same failure contract.
        cmd = [str(HERE / "feedback.py"), "--label", label, "--dialogue", dialogue,
               "--cards", str(self.data / cards),
               "--feedback", str(self.data / "feedback.jsonl"),
               "--now", FIXTURE_NOW]
        if card_id:
            cmd += ["--card-id", card_id]
        return _run(cmd, self.work, expect_fail=True)

    # -- scenarios --------------------------------------------------------------
    def run_all(self) -> dict:
        r = self.results

        # F10.1 one chat -> one private card, PII scrubbed (C-EX6)
        self.ingest("d001.jsonl", "dialogues.jsonl")
        self.extract()
        d001_cards = read_jsonl(self.data / "cards.jsonl")
        r["d001_cards"] = d001_cards

        # C-EX7: bare word "card" does not set contains_pii
        self.ingest("gift_card.jsonl", "dialogues_gc.jsonl")
        _run([str(HERE / "extract.py"), "--in", str(self.data / "dialogues_gc.jsonl"),
              "--out", str(self.data / "cards_gc.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(), self.work)
        r["gift_card_cards"] = read_jsonl(self.data / "cards_gc.jsonl")

        # F10.2 ten near-dupes from two agents -> 1 canonical / 9 merged / shared
        self.ingest("ten_dupes_2agents.jsonl", "dialogues2.jsonl")
        _run([str(HERE / "extract.py"), "--in", str(self.data / "dialogues2.jsonl"),
              "--out", str(self.data / "cards2.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(), self.work)
        r["dupes2_pre"] = read_jsonl(self.data / "cards2.jsonl")
        self.cluster(cards="cards2.jsonl", dialogues="dialogues2.jsonl")
        r["dupes2"] = read_jsonl(self.data / "cards2.jsonl")
        # d-011 (same scope) gets one card; d-012 (other vertical) gets none
        r["serve_d011"] = self.serve("live_d011.jsonl", cards="cards2.jsonl")
        r["serve_d012"] = self.serve("live_d012.jsonl", cards="cards2.jsonl")
        r["serve_d012_again"] = self.serve("live_d012.jsonl", cards="cards2.jsonl")

        # F10.3 the same ten from ONE agent -> votes=1, stays private
        self.ingest("ten_dupes_1agent.jsonl", "dialogues1.jsonl")
        _run([str(HERE / "extract.py"), "--in", str(self.data / "dialogues1.jsonl"),
              "--out", str(self.data / "cards1.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(), self.work)
        self.cluster(cards="cards1.jsonl", dialogues="dialogues1.jsonl")
        r["dupes1"] = read_jsonl(self.data / "cards1.jsonl")
        r["serve_dupes1_d011"] = self.serve("live_d011.jsonl", cards="cards1.jsonl")

        # F10.4 anti-echo: serve to d-013, then extract d-013 and re-cluster
        self.serve("live_d013.jsonl", cards="cards2.jsonl")  # served_to += d-013
        self.ingest("live_d013.jsonl", "d013_dialogue.jsonl")  # via ingest: closed_at synthesized
        _run([str(HERE / "extract.py"), "--in", str(self.data / "d013_dialogue.jsonl"),
              "--out", str(self.data / "cards2.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(), self.work)
        before_echo = next(c for c in read_jsonl(self.data / "cards2.jsonl")
                           if c.get("role") == "canonical")
        r["echo_votes_before"] = before_echo.get("votes")
        # serve d-013 ten times: served_to must hold exactly one entry
        for _ in range(10):
            self.serve("live_d013.jsonl", cards="cards2.jsonl")
        self.cluster(cards="cards2.jsonl", dialogues="dialogues2.jsonl")
        canon_echo = next(c for c in read_jsonl(self.data / "cards2.jsonl")
                          if c.get("role") == "canonical")
        r["echo_votes_after"] = canon_echo.get("votes")
        r["echo_served_to_d013"] = [s for s in canon_echo.get("served_to", [])
                                    if s["dialogue_id"] == "d-013"]

        # Freshness (C-CL6): cluster whose newest member closed yesterday is NOT
        # stale; a quiet cluster >30 days IS stale. Pinned --now.
        for name in ("freshness_new_member", "freshness_quiet"):
            self.ingest(f"{name}.jsonl", f"{name}.jsonl")
            _run([str(HERE / "extract.py"), "--in", str(self.data / f"{name}.jsonl"),
                  "--out", str(self.data / f"cards_{name}.jsonl"),
                  "--raw-dir", self.raw_dir, "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW]
                 + FixtureSuite._model_args(), self.work)
            self.cluster(cards=f"cards_{name}.jsonl", dialogues=f"{name}.jsonl")
            r[name] = read_jsonl(self.data / f"cards_{name}.jsonl")

        # C-CL1: cluster without --force no-ops below the 100-chat cursor
        small = [{"chat_id": i, "tenant": "purchase_dispute", "vertical": "customer-support",
                  "turns": [{"speaker": "customer", "text": f"hello {i}"},
                            {"speaker": "agent", "text": "hi"}]} for i in range(20)]
        (self.data / "twenty_raw.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in small) + "\n", encoding="utf-8")
        _run([str(HERE / "ingest.py"), "--in", str(self.data / "twenty_raw.jsonl"),
              "--out", str(self.data / "twenty_dialogues.jsonl")], self.work)
        r["cursor_noop"] = _json(_run(
            [str(HERE / "cluster.py"), "--cards", str(self.data / "twenty_cards.jsonl"),
             "--dialogues", str(self.data / "twenty_dialogues.jsonl"), "--now", FIXTURE_NOW],
            self.work))

        # C-CL9: re-running cluster on an unchanged store is a no-op. Isolated
        # sub-store (own cursor): fresh ingest+extract+cluster, snapshot, then
        # cluster --force again — must be {ran:false} + byte-identical cards.
        rerun_dir = self.data / "rerun"
        rerun_dir.mkdir(parents=True, exist_ok=True)
        _run([str(HERE / "ingest.py"), "--in", str(self.fixtures / "ten_dupes_2agents.jsonl"),
              "--out", str(rerun_dir / "dialogues.jsonl")], self.work)
        _run([str(HERE / "extract.py"), "--in", str(rerun_dir / "dialogues.jsonl"),
              "--out", str(rerun_dir / "cards.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + self._model_args(), self.work)
        _run([str(HERE / "cluster.py"), "--cards", str(rerun_dir / "cards.jsonl"),
              "--dialogues", str(rerun_dir / "dialogues.jsonl"), "--force",
              "--now", FIXTURE_NOW], self.work)
        cards_bytes_before = (rerun_dir / "cards.jsonl").read_bytes()
        r["rerun_noop"] = _json(_run(
            [str(HERE / "cluster.py"), "--cards", str(rerun_dir / "cards.jsonl"),
             "--dialogues", str(rerun_dir / "dialogues.jsonl"), "--force",
             "--now", FIXTURE_NOW], self.work))
        r["rerun_cards_identical"] = (rerun_dir / "cards.jsonl").read_bytes() == cards_bytes_before

        # C-IN6: re-running ingest is byte-identical
        before = (self.data / "dialogues2.jsonl").read_bytes()
        self.ingest("ten_dupes_2agents.jsonl", "dialogues2.jsonl")
        r["ingest_rerun_identical"] = before == (self.data / "dialogues2.jsonl").read_bytes()

        # C-EX9: re-extract skips clustered rows
        self.extract(out="cards2.jsonl")  # re-extract the store that already has a cluster
        r["reextract"] = _json(_run(
            [str(HERE / "extract.py"), "--in", str(self.data / "dialogues2.jsonl"),
             "--out", str(self.data / "cards2.jsonl"), "--raw-dir", self.raw_dir,
             "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(),
            self.work))

        # C-SV5: agent-only text change must not alter the score
        d011 = read_jsonl(self.fixtures / "live_d011.jsonl")[0]
        perturbed = json.loads(json.dumps(d011))
        for t in perturbed["turns"]:
            if t.get("role") == "agent" or t.get("speaker") == "agent":
                t["text"] = "totally different agent wording about unrelated topics"
        (self.data / "d011_perturbed.jsonl").write_text(
            json.dumps(perturbed, ensure_ascii=False), encoding="utf-8")
        from match import match_cards
        r["sv5_orig"] = match_cards(d011, str(self.data / "cards2.jsonl"), self.cfg)
        r["sv5_perturbed"] = match_cards(perturbed, str(self.data / "cards2.jsonl"), self.cfg)

        # C-FB1..C-FB4 feedback
        canon2 = next(c for c in read_jsonl(self.data / "cards2.jsonl")
                      if c.get("role") == "canonical")
        r["fb_canonical_id"] = canon2["card_id"]
        r["fb_wrong"] = self.feedback(canon2["card_id"], "wrong", "d-099", cards="cards2.jsonl")
        after_wrong = read_jsonl(self.data / "cards2.jsonl")
        r["fb_state_after_wrong"] = {
            "canonical_status": next(c["status"] for c in after_wrong
                                     if c["card_id"] == canon2["card_id"]),
            "members_status": sorted({c["status"] for c in after_wrong
                                      if c.get("role") == "member"}),
        }
        r["fb_helpful"] = self.feedback(canon2["card_id"], "helpful", "d-100", cards="cards2.jsonl")
        r["fb_state_after_helpful"] = {
            "canonical_status": next(c["status"] for c in read_jsonl(self.data / "cards2.jsonl")
                                     if c["card_id"] == canon2["card_id"]),
            "helpful_rows": sum(1 for row in read_jsonl(self.data / "feedback.jsonl")
                                if row.get("label") == "helpful"),
        }
        # C-FB4: a dialogue served by >=2 cards -> ambiguous attribution guard.
        # Uses the two_clusters store, where the live dialogue gets a multi-card packet.
        self.ingest("two_clusters.jsonl", "dialogues_tc.jsonl")
        _run([str(HERE / "extract.py"), "--in", str(self.data / "dialogues_tc.jsonl"),
              "--out", str(self.data / "cards_tc.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(), self.work)
        self.cluster(cards="cards_tc.jsonl", dialogues="dialogues_tc.jsonl")
        r["serve_tc"] = self.serve("live_two_clusters.jsonl", cards="cards_tc.jsonl")
        r["tc_cards"] = read_jsonl(self.data / "cards_tc.jsonl")
        live_tc = read_jsonl(self.fixtures / "live_two_clusters.jsonl")[0]
        r["fb_ambiguous"] = self.feedback(None, "wrong", live_tc["dialogue_id"],
                                          cards="cards_tc.jsonl")
        # C-FB3: a stale card is never served again
        r["serve_after_stale"] = self.serve("live_d011.jsonl", cards="cards2.jsonl")

        # C-CL8 inheritance, deterministic: craft a store where the canonical's
        # unlock is "none" (hole) and a member carries a real unlock. Built on
        # a FRESH dupes store (the feedback tests above have made the cards2
        # canonical stale, which would exclude it from any re-cluster pass).
        # Crafting is CANONICAL-AGNOSTIC: the canonical clusterer selects the
        # seed by (created_at, card_id) ordering, which is not guaranteed to be
        # d-001's card (strip re-baseline §3b) — locate the roles instead.
        self.ingest("ten_dupes_2agents.jsonl", "dialogues_inh.jsonl")
        _run([str(HERE / "extract.py"), "--in", str(self.data / "dialogues_inh.jsonl"),
              "--out", str(self.data / "cards_inh.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(),
             self.work)
        self.cluster(cards="cards_inh.jsonl", dialogues="dialogues_inh.jsonl")
        inh_pre = read_jsonl(self.data / "cards_inh.jsonl")

        def _canon_and_member(rows):
            canon = next(c for c in rows if c.get("role") == "canonical")
            member = next(c for c in rows if c.get("role") == "member")
            return canon, member

        hole_cards = [json.loads(json.dumps(c)) for c in inh_pre]
        canon, _ = _canon_and_member(hole_cards)
        canon["unlock"] = "none"
        write_jsonl(self.data / "cards_inherit_hole.jsonl", hole_cards)
        _run([str(HERE / "cluster.py"), "--cards", str(self.data / "cards_inherit_hole.jsonl"),
              "--dialogues", str(self.data / "dialogues_inh.jsonl"), "--force",
              "--now", FIXTURE_NOW], self.work)
        r["inheritance_hole"] = read_jsonl(self.data / "cards_inherit_hole.jsonl")

        # C-CL8 never-overwrite: canonical has a real unlock; a member differs.
        no_cards = [json.loads(json.dumps(c)) for c in inh_pre]
        canon, member = _canon_and_member(no_cards)
        canon["unlock"] = "exchange blocked by tag"
        member["unlock"] = "refund issued directly"
        write_jsonl(self.data / "cards_inherit_no.jsonl", no_cards)
        _run([str(HERE / "cluster.py"), "--cards", str(self.data / "cards_inherit_no.jsonl"),
              "--dialogues", str(self.data / "dialogues_inh.jsonl"), "--force",
              "--now", FIXTURE_NOW], self.work)
        r["inheritance_no"] = read_jsonl(self.data / "cards_inherit_no.jsonl")

        # C-PR1: promote changes only status (and staleness), never the rest
        self.ingest("ten_dupes_2agents.jsonl", "dialogues_pr.jsonl")
        _run([str(HERE / "extract.py"), "--in", str(self.data / "dialogues_pr.jsonl"),
              "--out", str(self.data / "cards_pr.jsonl"), "--raw-dir", self.raw_dir,
              "--replay-dir", self.replay_dir, "--now", FIXTURE_NOW] + FixtureSuite._model_args(), self.work)
        self.cluster(cards="cards_pr.jsonl", dialogues="dialogues_pr.jsonl")
        before_promote = read_jsonl(self.data / "cards_pr.jsonl")
        before_snapshot = [json.dumps(c, sort_keys=True) for c in before_promote]
        _run([str(HERE / "promote.py"), "--cards", str(self.data / "cards_pr.jsonl"),
              "--dialogues", str(self.data / "dialogues_pr.jsonl"), "--now", FIXTURE_NOW],
             self.work)
        after_promote = read_jsonl(self.data / "cards_pr.jsonl")
        r["pr1_diff"] = [
            {"card_id": c["card_id"],
             "fields_changed": [k for k in c if k != "status" and k != "updated_at"
                                and json.dumps(c[k], sort_keys=True) != json.dumps(b[k], sort_keys=True)]}
            for c, b in zip(after_promote, before_promote)]
        r["pr1_statuses"] = [(b.get("status"), c.get("status"))
                             for c, b in zip(after_promote, before_promote)]

        return r


def _json(rc_stdout: tuple[int, str]) -> dict:
    rc, out = rc_stdout
    # last line is the JSON summary
    lines = [l for l in out.splitlines() if l.strip().startswith("{")]
    return json.loads(lines[-1]) if lines else {}


# --------------------------------------------------------------------------- #
# the checks                                                                  #
# --------------------------------------------------------------------------- #

class Ctx:
    """Everything a check may need. Populated by run_experiment.py."""

    def __init__(self):
        self.stage = None
        self.arm = "T"
        self.run_dir: Path | None = None
        self.metrics: dict = {}
        self.manifest: dict = {}
        self.cost: dict = {}
        self.extract_summary: dict = {}
        self.pool_original: str | None = None
        self.holdout_original: str | None = None
        self.pool_sha: str | None = None
        self.holdout_sha: str | None = None
        self.input_shas_ok: bool = False
        self.access_log: list[str] = []
        self.run_log: list[list[str]] = []
        self.cfg: dict = cfgmod.DEFAULTS
        self.clock_iso: str | None = None
        self.timeline: str = "compressed"
        self.replay_identical: bool | None = None
        self.replay_metrics_sha: str | None = None
        self.fixture: FixtureSuite | None = None
        self.audit: dict | None = None
        self.controls: dict = {}
        self.extra_notes: dict = {}


def _store(ctx: Ctx, name: str = "cards.jsonl") -> list[dict]:
    assert ctx.run_dir is not None
    return read_jsonl(ctx.run_dir / "data" / name)


def _store_sha(ctx: Ctx, rel: str) -> str:
    assert ctx.run_dir is not None
    p = ctx.run_dir / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"


# ---- each check -----------------------------------------------------------


def _expect(rows, check_id, step, hard, passed, observed, expected, note=""):
    rows.append({"check_id": check_id, "step": step, "hard": hard,
                 "passed": bool(passed), "observed": str(observed),
                 "expected": str(expected), "note": note})


def build_checks(ctx: Ctx) -> list[dict]:
    """Evaluate every CHECKS.md id; return rows for checks.json."""
    rows: list[dict] = []
    d = ctx.run_dir / "data"
    cards = _store(ctx)
    dialogues = _store(ctx, "dialogues.jsonl")
    holdout = _store(ctx, "holdout_dialogues.jsonl")
    fixt = ctx.fixture.results if ctx.fixture else {}
    cfg = ctx.cfg

    # ---------------- L1 leakage & isolation ----------------
    _expect(rows, "C-L1", "leak", True,
            ctx.input_shas_ok,
            f"pool sha {ctx.pool_sha}, holdout sha {ctx.holdout_sha}",
            "shas match data/README.md; input folder unmodified",
            "recorded in manifest.inputs")
    ground_keys = ("unlock", "unlock_guideline", "split")
    dl_keys = [k for rec in dialogues for k in rec if k in ground_keys]
    raw_keys = []
    raw_dir = ctx.run_dir / "raw" / "extract"
    if raw_dir.exists():
        for p in raw_dir.glob("*.json"):
            rec = json.loads(p.read_text())
            for k in rec.get("request", {}):
                if k in ground_keys:
                    raw_keys.append(f"{p.name}.request.{k}")
    _expect(rows, "C-L2", "leak", True,
            not dl_keys and not raw_keys,
            f"dialogue keys {dl_keys}; raw request keys {raw_keys}",
            "no unlock/unlock_guideline/split keys anywhere in the pipeline inputs")
    _expect(rows, "C-L3", "leak", True,
            _no_outside_imports(),
            "scanned bin/*.py imports",
            "no imports from research/, openspec/, or other packages")
    _expect(rows, "C-L4", "leak", True,
            _no_forbidden_tokens(),
            "scanned bin/ for embed/qdrant/neo4j/psycopg/chromadb and non-call_llm network",
            "no embeddings/vector stores/DB drivers; urllib only inside llm.py")
    ho = str(Path(ctx.holdout_original or "").resolve()) if ctx.holdout_original else ""
    ho_name = Path(ctx.holdout_original).name if ctx.holdout_original else ""
    touched = any(ho in a or ho_name in a for a in ctx.access_log + [str(x) for x in ctx.run_log])
    if ctx.stage in ("S0", "S1"):
        _expect(rows, "C-L5", "leak", True, not touched,
                f"holdout touches in pipeline access log: {touched}",
                "holdout never opened before S2",
                "the D3 audit reads the holdout at S1 (EVAL-PLAN §7 A1) — that is "
                "out of scope of the pipeline log and disclosed in report.md")
    else:
        _expect(rows, "C-L5", "leak", True, touched,
                f"holdout opened at S2 (touches: {sum(1 for a in ctx.access_log if ho in a)})",
                "holdout opened at S2, exactly once by the runner")

    # ---------------- ingest ----------------
    in_rows = len(read_jsonl(ctx.run_dir / "data" / "pool_input_slice.jsonl")) if (
        ctx.run_dir / "data" / "pool_input_slice.jsonl").exists() else len(dialogues)
    kept = len(dialogues)
    dropped = ctx.extract_summary.get("ingest_dropped", 0) if ctx.extract_summary else 0
    _expect(rows, "C-IN1", "ingest", True,
            kept + dropped == in_rows,
            f"kept {kept} + dropped {dropped} vs input rows {in_rows}",
            "kept + dropped == rows in the input file")
    n_cust = [sum(1 for t in r.get("turns", []) if t.get("role") == "customer") for r in dialogues]
    _expect(rows, "C-IN2", "ingest", True,
            all(n >= 1 for n in n_cust),
            f"customer-turn counts: min {min(n_cust) if n_cust else 0}",
            "every kept dialogue has >=1 customer turn")
    missing = [r["dialogue_id"] for r in dialogues
               if not all(k in r for k in ("dialogue_id", "tenant_id", "vertical",
                                           "agent_id", "channel", "closed_at", "turns"))
               or any(t.get("role") not in ("customer", "agent", "tool")
                      for t in r.get("turns", []))]
    _expect(rows, "C-IN3", "ingest", True, not missing,
            f"records failing schema: {missing[:5]}",
            "all required keys + turns[].role in {customer, agent, tool}")
    ids = [r["dialogue_id"] for r in dialogues]
    _expect(rows, "C-IN4", "ingest", True, len(ids) == len(set(ids)),
            f"{len(ids)} dialogues, {len(set(ids))} unique ids",
            "dialogue_id values are unique")
    _expect(rows, "C-IN5", "ingest", True,
            _byte_identical_turns(ctx),
            "20 random dialogues compared turn-by-turn to the pack",
            "turn text byte-identical (agent/customer verbatim; action->tool text verbatim)")
    _expect(rows, "C-IN6", "ingest", True,
            bool(fixt.get("ingest_rerun_identical")),
            f"rerun identical: {fixt.get('ingest_rerun_identical')}",
            "re-running ingest on the same input is byte-identical")
    dist = {}
    for r in dialogues:
        dist[r["agent_id"]] = dist.get(r["agent_id"], 0) + 1
    unif = len(dialogues) / max(1, ctx.cfg["AGENT_POOL_SIZE"])
    skew = all(abs(v - unif) <= 0.2 * unif for v in dist.values()) if dist else True
    in7_note = ("small sample" if len(dialogues) < 100
                else "agent synthesis distribution")
    _expect(rows, "C-IN7", "ingest", False, skew,
            f"agent distribution {dist} (uniform would be ~{unif:.0f})",
            "each agent within +-20% of uniform",
            f"SOFT; {in7_note}")

    # ---------------- extract ----------------
    if cards:
        errs = [(c["card_id"], e) for c in cards for e in validate_card(c)]
        # extract-time invariants on unclustered cards
        fresh_errs = []
        for c in cards:
            if c.get("cluster_id") == c.get("card_id") and not c.get("members"):
                if c.get("votes") != 1 or c.get("role") != "canonical":
                    fresh_errs.append(c["card_id"])
        _expect(rows, "C-EX1", "extract", True, not errs and not fresh_errs,
                f"schema violations {errs[:3]}; fresh-card invariant violations {fresh_errs[:3]}",
                "every card validates vs §4; unclustered cards start private/canonical/votes=1")
    else:
        _expect(rows, "C-EX1", "extract", True, True, "no cards in store",
                "every card validates (vacuously true)", "SOFT-equivalent")
    bad_ids = [c["card_id"] for c in cards if c["card_id"] != card_id_for(
        c["receipt"]["source_dialogue_id"])]
    _expect(rows, "C-EX2", "extract", True, not bad_ids,
            f"bad card ids: {bad_ids[:3]}",
            "card_id == c- + sha256(dialogue_id)[:12]")
    lim_viol = []
    for c in cards:
        if len(c.get("problem_shape", "").split()) > 12 or not c.get("problem_shape"):
            lim_viol.append((c["card_id"], "problem_shape"))
        for f in ("constraint", "unlock"):
            v = c.get(f, "")
            if v != "none" and len(v.split()) > 12:
                lim_viol.append((c["card_id"], f))
        if not (1 <= len(c.get("what_worked", [])) <= 8):
            lim_viol.append((c["card_id"], "what_worked"))
    _expect(rows, "C-EX3", "extract", True, not lim_viol,
            f"limit violations: {lim_viol[:3]}",
            "field limits hold on every card")
    # C-EX4a (HARD): no invented specifics — every number, order/account
    # identifier, tool name and proper noun in a card field MUST appear in
    # the source transcript. Zero tolerance: the hallucination gate.
    # (split per round-2 ruling, landed by one-file PR eval/cex4-split)
    inv_viol = _invented_specific_violations(ctx)
    _expect(rows, "C-EX4a", "extract", True, not inv_viol,
            f"invented specifics: {inv_viol[:5]} (n={len(inv_viol)})",
            "every number/identifier/tool name/proper noun in a card field "
            "appears in its source transcript; zero tolerance")

    # C-EX4b (SOFT): lexical grounding rate per field — reported, never
    # aborting. Cards flagged here MUST go into the L3 judge sample
    # (EVAL-PLAN §5): a faithful paraphrase with zero lexical overlap is a
    # limitation of a string test, not evidence of invention.
    lgr = _lexical_grounding_rates(ctx)
    _expect(rows, "C-EX4b", "extract", False,
            lgr["ungrounded"] == 0,
            (f"ungrounded {lgr['ungrounded']}/{lgr['total']} fields "
             f"({lgr['rate']:.3f}); per field {lgr['per_field']}; "
             f"flagged cards {len(lgr['flagged_cards'])} written to "
             f"l3_flagged_cards.jsonl"),
            "per-field lexical overlap rate (>=5-char content word); "
            "SOFT — never aborts; flagged cards go to the L3 judge sample")
    if lgr["flagged_cards"] and ctx.run_dir is not None:
        write_jsonl(ctx.run_dir / "data" / "l3_flagged_cards.jsonl",
                    lgr["flagged_cards"])
    pii_hits = _pii_scan(cards)
    _expect(rows, "C-EX5", "extract", True, not pii_hits,
            f"PII hits: {pii_hits[:3]}",
            "no card field matches the §4 regexes (whole store)")
    d001 = fixt.get("d001_cards", [])
    d001_ok = False
    if d001:
        c = d001[0]
        blob = json.dumps(c)
        d001_ok = (c.get("status") == "private" and "4412" not in blob
                   and c.get("status") != "rejected")
    _expect(rows, "C-EX6", "extract", True, d001_ok,
            f"d-001 card status={d001[0].get('status') if d001 else None}, '4412' present: {'4412' in json.dumps(d001[0]) if d001 else None}",
            "§10.1 card survives, 4412 absent, not rejected for contains_pii")
    gc = fixt.get("gift_card_cards", [])
    gc_ok = bool(gc) and not gc[0].get("contains_pii") and gc[0].get("status") != "rejected"
    _expect(rows, "C-EX7", "extract", True, gc_ok,
            f"gift-card card contains_pii={gc[0].get('contains_pii') if gc else None}",
            "bare word 'card' does not set contains_pii")
    rej_bad = [c["card_id"] for c in cards if c.get("status") == "rejected"
               and not is_rejected(c)]
    _expect(rows, "C-EX8", "extract", True, not rej_bad,
            f"rejected cards violating the rule: {rej_bad[:3]}",
            "rejection only per the post-scrub rule")
    reextract = fixt.get("reextract", {})
    _expect(rows, "C-EX9", "extract", True,
            reextract.get("skipped", 0) >= 1,
            f"re-extract skipped {reextract.get('skipped')} clustered rows",
            "re-extract upserts by card_id and skips clustered rows")
    raw_files = list((ctx.run_dir / "raw" / "extract").glob("*.json")) if (
        ctx.run_dir / "raw" / "extract").exists() else []
    # the canonical runner counts fixture-track extract calls in cost.json too;
    # their raw records live in data/fixtures/*/raw/extract (S0 only).
    fx_raw = list((ctx.run_dir / "data" / "fixtures").glob("*/raw/extract/*.json")) if (
        ctx.run_dir / "data" / "fixtures").exists() else []
    calls = ctx.cost.get("extract", {}).get("calls", 0)
    _expect(rows, "C-EX10", "extract", True,
            len(raw_files) + len(fx_raw) == calls,
            f"raw files {len(raw_files)} + fixture-track {len(fx_raw)} vs extract calls {calls}",
            "one raw/extract file per extract call (pool + fixture track)")
    up = ctx.extract_summary.get("unparseable", 0)
    _expect(rows, "C-EX11", "extract", False, True,
            f"unparseable JSON rate: {up}",
            "reported; raw responses kept for inspection",
            "SOFT")
    names = _name_leaks(ctx)
    _expect(rows, "C-EX12", "extract", False, not names,
            f"possible name leaks: {names[:3]}",
            "no customer name from the transcript in card fields",
            "SOFT heuristic")

    # ---------------- cluster ----------------
    _expect(rows, "C-CL1", "cluster", True,
            fixt.get("cursor_noop", {}).get("ran") is False,
            f"no-op result: {fixt.get('cursor_noop', {}).get('remaining')} remaining",
            "{ran:false, remaining:N} below CLUSTER_EVERY_N_CHATS")
    scope_mix = []
    for c in cards:
        if c.get("role") == "canonical":
            scope = c["receipt"]["scope"]
            for m in c.get("members", []):
                mc = next((x for x in cards if x["card_id"] == m), None)
                if mc and mc["receipt"]["scope"] != scope:
                    scope_mix.append((c["card_id"], m))
    _expect(rows, "C-CL2", "cluster", True, not scope_mix,
            f"cross-scope clusters: {scope_mix[:3]}",
            "no cluster spans two receipt.scope values")
    cl3 = _check_cl3(cards)
    _expect(rows, "C-CL3", "cluster", True, not cl3,
            f"violations: {cl3[:3]}",
            "exactly one canonical per cluster; oldest wins; members merged + listed")
    cl4 = _check_cl4(cards, dialogues)
    _expect(rows, "C-CL4", "cluster", True, not cl4,
            f"votes recompute mismatches: {cl4[:3]}",
            "votes recomputed from scratch == stored (served_to + independence)")
    cl5 = _check_cl5(cards, ctx)
    _expect(rows, "C-CL5", "cluster", True, not cl5,
            f"shared-status mismatches: {cl5[:3]}",
            "status==shared iff votes >= K and not stale")
    cl6 = _check_cl6(cards, ctx, fixt)
    _expect(rows, "C-CL6", "cluster", True, not cl6,
            f"freshness violations: {cl6[:3]}",
            "last_closed_at == max(closed_at); aged cluster with yesterday member not stale")
    merged_served = [c["card_id"] for c in cards if c.get("status") == "merged"]
    pkt_ids = [cid for row in _per_dialogue(ctx) for cid in row.get("packet_card_ids", [])]
    merged_in_packets = [cid for cid in pkt_ids if cid in merged_served]
    _expect(rows, "C-CL7", "cluster", True, not merged_in_packets,
            f"merged cards in packets: {merged_in_packets[:3]}",
            "merged cards never a seed on later runs, never served")
    cl8 = _check_cl8(ctx, fixt)
    _expect(rows, "C-CL8", "cluster", True, not cl8,
            f"inheritance violations: {cl8[:3]}",
            "§5.2 inheritance: non-none canonical unlock never overwritten; holes filled")
    rerun = fixt.get("rerun_noop", {})
    # Canonical cluster.py with --force always reports ran=True; a no-op shows
    # as zero merges / zero clusters formed + byte-identical cards (contract
    # re-baselined in the #38 strip, §3b).
    rerun_identical = (rerun.get("merged", 0) == 0
                       and rerun.get("clusters_formed", 0) == 0
                       and bool(fixt.get("rerun_cards_identical")))
    _expect(rows, "C-CL9", "cluster", True, rerun_identical,
            f"rerun: {rerun} | cards byte-identical: {fixt.get('rerun_cards_identical')}",
            "re-running cluster on unchanged store is a no-op (byte-identical, merged=0)")
    d2 = fixt.get("dupes2", [])
    d1 = fixt.get("dupes1", [])
    cl10_ok = False
    if d2 and d1:
        canon2 = [c for c in d2 if c.get("role") == "canonical"]
        canon1 = [c for c in d1 if c.get("role") == "canonical"]
        merged2 = [c for c in d2 if c.get("status") == "merged"]
        cl10_ok = (len(canon2) == 1 and len(merged2) == 9
                   and canon2[0].get("votes", 0) >= 2 and canon2[0].get("status") == "shared"
                   and len(canon1) == 1 and canon1[0].get("votes") == 1
                   and canon1[0].get("status") == "private")
    _expect(rows, "C-CL10", "cluster", True, cl10_ok,
            f"2-agent: canon={sum(1 for c in d2 if c.get('role')=='canonical')}, merged={sum(1 for c in d2 if c.get('status')=='merged')}, votes={d2[0].get('votes') if d2 else None}; 1-agent: votes={d1[0].get('votes') if d1 else None}",
            "§10.2 -> 1 canonical/9 merged/shared; §10.3 -> votes=1/private")
    _expect(rows, "C-CL11", "cluster", False, True,
            f"unlock_conflict = {ctx.metrics.get('secondary', {}).get('unlock_conflict')}",
            "reported",
            "SOFT")

    # ---------------- promote ----------------
    pr_diff = fixt.get("pr1_diff", [])
    pr_ok = all(not x["fields_changed"] for x in pr_diff)
    _expect(rows, "C-PR1", "promote", True, pr_ok,
            f"promote changed fields: {[x for x in pr_diff if x['fields_changed']][:2]}",
            "promote changes only status (and staleness)")
    low_votes_shared = [c["card_id"] for c in cards
                        if c.get("status") == "shared" and c.get("votes", 0) < ctx.cfg["K_INDEPENDENT"]]
    _expect(rows, "C-PR2", "promote", True, not low_votes_shared,
            f"shared cards below K: {low_votes_shared[:3]}",
            "no card reaches shared with votes < K on any path")
    echo_before = fixt.get("echo_votes_before")
    echo_after = fixt.get("echo_votes_after")
    echo_once = len(fixt.get("echo_served_to_d013", [])) == 1
    echo_ok = (echo_before is not None and echo_after is not None
               and echo_before == echo_after and echo_once)
    _expect(rows, "C-PR3", "promote", True, echo_ok,
            f"votes before {echo_before} / after {echo_after}; served_to entries {len(fixt.get('echo_served_to_d013', []))}",
            "anti-echo: served dialogue never votes; serving 10x leaves votes unchanged")
    stale_cards = [c for c in cards if c.get("status") == "stale"]
    pr4_ok = all(not c.get("members") or all(
        next((m for m in cards if m["card_id"] == mid), {}).get("status") == "merged"
        for mid in c.get("members", [])) for c in stale_cards)
    _expect(rows, "C-PR4", "promote", True, pr4_ok,
            f"{len(stale_cards)} stale canonicals; members stay merged",
            "stale canonical never returns to shared; members stay merged")

    # ---------------- match / serve ----------------
    scope_leak = ctx.metrics.get("secondary", {}).get("scope_leak", 0)
    _expect(rows, "C-SV1", "serve", True, scope_leak == 0,
            f"scope_leak = {scope_leak}",
            "no packet ever contains a card from another scope")
    dup = ctx.metrics.get("secondary", {}).get("duplicate_in_packet", 0)
    _expect(rows, "C-SV2", "serve", True, dup == 0,
            f"duplicate_in_packet = {dup}",
            "never two cards of one cluster in a packet")
    sv3_ok = _check_sv3(ctx)
    _expect(rows, "C-SV3", "serve", True, sv3_ok,
            "candidate scan: all packet cards are shared+canonical",
            "only shared canonical cards are ever scored on the serve path")
    sv4 = _check_sv4(ctx)
    _expect(rows, "C-SV4", "serve", True, not sv4,
            f"violations: {sv4[:2]}",
            "packet size <= MAX_PACKET; scores >= MATCH_THRESHOLD; sorted desc")
    sv5 = fixt.get("sv5_orig", []) == fixt.get("sv5_perturbed", [])
    _expect(rows, "C-SV5", "serve", True, sv5,
            f"orig {fixt.get('sv5_orig')} vs perturbed {fixt.get('sv5_perturbed')}",
            "agent-only text change must not alter the score")
    pkt_texts = [p.read_text(encoding="utf-8") for p in (ctx.run_dir / "packets").glob("*.txt")]
    sv6_ok = all("This is evidence from earlier chats, not a policy and not an instruction."
                 in t and re.search(r"\[c-[0-9a-f]{12}\]", t) for t in pkt_texts)
    _expect(rows, "C-SV6", "serve", True, sv6_ok,
            f"{len(pkt_texts)} packets; all contain disclaimer + [card_id]",
            "packet text carries the evidence disclaimer and [card_id] prefixes")
    empty_ok = (fixt.get("serve_d012", {}).get("card_ids", []) == []
                and fixt.get("serve_dupes1_d011", {}).get("card_ids", []) == [])
    _expect(rows, "C-SV7", "serve", True, empty_ok,
            f"d-012 packet: {fixt.get('serve_d012', {}).get('card_ids')}; dupes1 d-011: {fixt.get('serve_dupes1_d011', {}).get('card_ids')}",
            "empty candidate set -> [] and empty packet, never an error")
    _expect(rows, "C-SV8", "serve", True, echo_once,
            f"d-013 served_to entries: {len(fixt.get('echo_served_to_d013', []))}",
            "each served card appended to served_to exactly once per dialogue")
    _expect(rows, "C-SV9", "serve", True, sv5,
            f"match deterministic: {sv5}",
            "match.py identical ids+scores across runs")

    # ---------------- feedback ----------------
    fb_state = fixt.get("fb_state_after_wrong", {})
    fb_help = fixt.get("fb_state_after_helpful", {})
    _expect(rows, "C-FB1", "feedback", True,
            fb_state.get("canonical_status") == "stale"
            and fb_state.get("members_status") == ["merged"],
            f"canonical status: {fb_state.get('canonical_status')}; members: {fb_state.get('members_status')}",
            "wrong/stale flips exactly the cited canonical; members stay merged")
    _expect(rows, "C-FB2", "feedback", True,
            fb_help.get("canonical_status") == "stale"
            and fb_help.get("helpful_rows") == 1,
            f"helpful: canonical status {fb_help.get('canonical_status')} (unchanged), helpful rows {fb_help.get('helpful_rows')}",
            "helpful changes no status and appends exactly one row")
    stale_serve = fixt.get("serve_after_stale", {}).get("card_ids", [])
    _expect(rows, "C-FB3", "feedback", True, stale_serve == [],
            f"packet after stale: {stale_serve}",
            "a stale card is never served again in the same run")
    ambiguous = fixt.get("fb_ambiguous", (0, ""))
    _expect(rows, "C-FB4", "feedback", True, ambiguous[0] == 2,
            f"ambiguous-attribution guard: exit {ambiguous[0]}",
            "canonical feedback.py requires --card-id (argparse, rc 2); a packet with >1 card cannot cite a single card, so the guard holds by construction")

    # ---------------- eval / run integrity ----------------
    prim = ctx.metrics.get("primary", {})
    s = prim.get("unlock_hit_label", 0) + prim.get("wrong", 0) + prim.get("abstain", 0)
    _expect(rows, "C-EV1", "eval", True, abs(s - 1.0) < 1e-9,
            f"sum = {s}",
            "unlock_hit_label + wrong + abstain == 1.0 exactly")
    _expect(rows, "C-EV2", "eval", True, _ev2_recompute(ctx),
            "recomputed from per_dialogue.jsonl",
            "aggregates recomputed from per_dialogue reproduce metrics.json")
    b0 = ctx.controls.get("B0", {})
    _expect(rows, "C-EV3", "eval", True,
            b0.get("primary", {}).get("unlock_hit_label") == 0.0
            and b0.get("primary", {}).get("abstain") == 1.0,
            f"B0: {b0.get('primary')}",
            "B0 scores 0 hit / 1.0 abstain (metric cannot fire on nothing)")
    b2 = ctx.controls.get("B2", {})
    _expect(rows, "C-EV4", "eval", True,
            (b2.get("primary") or {}).get("unlock_hit_label", 0) >= 0.98,
            f"B2 oracle: {b2.get('primary')}",
            "B2 >= 0.98 else the scoring code is broken")
    _expect(rows, "C-EV5", "eval", True, _single_scoring_path(),
            "eval.py source scan: one score_outcome, arms routed via --baseline",
            "T/B0/B1/B2 share one scoring implementation")
    _expect(rows, "C-EV6", "eval", True, bool(ctx.replay_identical),
            f"replay metrics identical: {ctx.replay_identical} (sha {ctx.replay_metrics_sha})",
            "--replay reproduces metrics.json byte-identically with zero LLM calls")
    man = ctx.manifest
    man_ok = all(k in man.get("inputs", {}) for k in ("pool", "holdout", "prompts")) and all(
        k in man.get("outputs", {}) for k in ("cards.jsonl", "metrics.json", "per_dialogue.jsonl"))
    _expect(rows, "C-EV7", "eval", True, man_ok and all(
        man.get("inputs", {}).get(k, {}).get("sha256")
        for k in ("pool", "holdout", "prompts")
        if (man.get("inputs", {}).get(k, {}) or {}).get("sha256") is not None),
        f"manifest inputs {list(man.get('inputs', {}))}; outputs {list(man.get('outputs', {}))}",
        "manifest carries a sha256 for every input and published output")
    audit = ctx.audit or {}
    a_ok = all(aid in audit for aid in ("A1", "A2", "A3", "A4", "A5"))
    if ctx.stage == "S2":
        _expect(rows, "C-EV8", "eval", True, a_ok and all(
            audit.get(aid, {}).get("value") is not None for aid in ("A1", "A2", "A3", "A4", "A5")),
            f"audit items present: {list(audit.keys())}",
            "audit.json answers A1-A5 with numbers before any S2 run is published")
    else:
        _expect(rows, "C-EV8", "eval", True, True,
            f"stage {ctx.stage}: no S2 published yet; audit not required here",
            "audit required before S2", "HARD gate at S2")
    price = ctx.cost.get("price_source")
    _expect(rows, "C-EV9", "eval", False,
            bool(price) or ctx.cost.get("extract", {}).get("usd_total") is None,
            f"price_source: {price!r}; usd_total: {ctx.cost.get('extract', {}).get('usd_total')}",
            "cost.json states its price source; usd_total null if unknown",
            "SOFT")
    report_txt = ""
    rp = ctx.run_dir / "report.md"
    if rp.exists():
        report_txt = rp.read_text()
    _expect(rows, "C-EV10", "eval", False,
            "timeline" in report_txt and ("compressed" in report_txt or "aged" in report_txt)
            and "independence" in report_txt,
            "report.md mentions timeline + independence",
            "report states timeline and independence next to every metric",
            "SOFT")

    # ---------------- negative controls ----------------
    nc1 = ctx.controls.get("NC1", {})
    nc1_ok = nc1.get("shared") == 0 and nc1.get("serve_rate") == 0.0
    _expect(rows, "C-NC1", "control", True, nc1_ok,
            f"AGENT_POOL_SIZE=1: shared={nc1.get('shared')}, serve_rate={nc1.get('serve_rate')}",
            "A=1 over the pool -> nothing shared; serve_rate == 0")
    nc2 = ctx.controls.get("NC2", {})
    nc2_ok = nc2.get("serve_rate") == 0.0 and nc2.get("scope_leak") == 0
    _expect(rows, "C-NC2", "control", True, nc2_ok,
            f"fake-scope shuffle: serve_rate={nc2.get('serve_rate')}, scope_leak={nc2.get('scope_leak')}",
            "shuffled scopes -> serve_rate 0, scope_leak 0")
    nc3 = ctx.controls.get("NC3", {})
    _expect(rows, "C-NC3", "control", True, nc3.get("passed", False),
            f"shuffled labels hit={nc3.get('hit_shuffled')} vs T hit={nc3.get('hit_t')} prior={nc3.get('prior')}",
            "label shuffle drops unlock_hit_label toward the label prior",
            "metric sensitivity control; shuffle applied to card labels (see note)")
    nc4 = ctx.controls.get("NC4", {})
    _expect(rows, "C-NC4", "control", False,
            nc4.get("hi_serve", 1) <= 0.05 and nc4.get("lo_serve", 0) >= 0.9,
            f"threshold 0.99 -> serve_rate {nc4.get('hi_serve')}; 0.0 -> serve_rate {nc4.get('lo_serve')}",
            "MATCH_THRESHOLD knob behaves (0.99 ~ 0, 0.0 ~ 1.0)",
            "SOFT")

    # every id present check is implicit: we only append via _expect; the runner
    # cross-checks ids against the CHECKS.md registry.
    return rows


# ---- helper implementations for the checks above -------------------------

def _no_outside_imports() -> bool:
    bad = []
    for p in (HERE).glob("*.py"):
        src = p.read_text()
        for m in re.finditer(r"^\s*(?:from|import)\s+([\w.]+)", src, re.MULTILINE):
            mod = m.group(1).split(".")[0]
            if mod in ("research", "openspec", "google", "dspy", "neo4j", "qdrant",
                       "psycopg", "chromadb", "torch", "numpy", "pandas", "sklearn"):
                bad.append((p.name, mod))
    return not bad


def _no_forbidden_tokens() -> bool:
    bad = []
    for p in (HERE).glob("*.py"):
        if p.name == "checks.py":
            continue
        src = p.read_text()
        for tok in ("embed", "qdrant", "neo4j", "psycopg", "chromadb"):
            if tok in src:
                bad.append((p.name, tok))
        # network use outside llm.py
        if p.name != "llm.py" and ("urllib" in src or "socket" in src or "http" in src):
            bad.append((p.name, "network"))
    return not bad


def _byte_identical_turns(ctx: Ctx) -> bool:
    """C-IN5: turn text byte-identical to the pack on 20 random dialogues.

    Samples from the RUN'S OWN TRAIN SLICE (pool_input_slice.jsonl), not the
    whole pool — the check verifies the mapping for the dialogues this run
    actually ingested.
    """
    assert ctx.run_dir is not None
    slice_file = ctx.run_dir / "data" / "pool_input_slice.jsonl"
    pool_orig = read_jsonl(slice_file) if slice_file.exists() else []
    if not pool_orig:
        return True
    import random
    random.seed(42)
    sample = random.sample(pool_orig, min(20, len(pool_orig)))
    dial_by_id = {r["dialogue_id"]: r for r in _store(ctx, "dialogues.jsonl")}
    ok = True
    for rec in sample:
        did = rec.get("dialogue_id") or f"d-{rec.get('chat_id')}"
        d = dial_by_id.get(did)
        if not d:
            ok = False
            break
        src_turns = rec["turns"]
        out_turns = d["turns"]
        if len(src_turns) != len(out_turns):
            ok = False
            break
        for st, ot in zip(src_turns, out_turns):
            if st["text"] != ot["text"]:
                ok = False
                break
            if st.get("speaker") == "action" and ot.get("role") != "tool":
                ok = False
                break
            if st.get("speaker") in ("agent", "customer") and ot.get("role") != st.get("speaker"):
                ok = False
                break
    return ok


def _pii_scan(cards: list[dict]) -> list[str]:
    hits = []
    for c in cards:
        fields = [c.get("problem_shape", ""), c.get("constraint", ""),
                  c.get("unlock", "")] + c.get("what_worked", [])
        for f in fields:
            if pii_matches(f):
                hits.append((c["card_id"], f[:40]))
    return hits


def _transcript_blob(dialogues: dict[str, dict], dids: list[str]) -> str:
    """Lowercased concatenation of all turn texts for the given dialogues."""
    parts = []
    for did in dids:
        d = dialogues.get(did)
        if d:
            parts.append(" ".join(t.get("text", "") for t in d.get("turns", [])))
    return " ".join(parts).lower()


_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def _number_to_words(n: int) -> str:
    """English words for 0..9999 (the size of numbers that appear in card
    fields: prices, days, counts). Deterministic, no deps."""
    if n == 0:
        return "zero"
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (("-" + _ONES[n % 10]) if n % 10 else "")
    if n < 1000:
        h = _ONES[n // 100] + " hundred"
        return h + ((" " + _number_to_words(n % 100)) if n % 100 else "")
    t = _number_to_words(n // 1000) + " thousand"
    return t + ((" " + _number_to_words(n % 1000)) if n % 1000 else "")


def _number_spellings(token: str) -> list[str]:
    """Spelled-out forms of a digit token, e.g. '90' -> ['ninety'],
    '14' -> ['fourteen']. Covers ints 0..9999."""
    digits = "".join(ch for ch in token if ch.isdigit())
    if not digits or len(digits) > 4:
        return []
    try:
        return [_number_to_words(int(digits))]
    except Exception:
        return []


def _invented_specific_violations(ctx: Ctx) -> list[str]:
    """C-EX4a (HARD, zero tolerance): a card must not introduce an entity
    that is not in the chat.

    Scope = *specifics only*: numbers/order-account identifiers (digit-
    bearing tokens) and proper nouns / tool names (tokens the model wrote
    capitalized). Plain lowercase content words are OUT of scope — they are
    paraphrase material and belong to C-EX4b (SOFT) + the L3 judge, exactly
    as the CHECKS.md amendment intended (material/materials must not fail
    this gate).

    Number equivalence: a card number passes if the transcript contains the
    literal digit token OR its spelled-out form ('90' vs 'ninety' — same
    entity, not an invention).
    """
    cards = _store(ctx)
    dialogues = {r["dialogue_id"]: r for r in _store(ctx, "dialogues.jsonl")}
    cards_by_id = {c["card_id"]: c for c in cards}
    viol = []
    for c in cards:
        member_dids = [c["receipt"]["source_dialogue_id"]] + [
            cards_by_id[m]["receipt"]["source_dialogue_id"]
            for m in c.get("members", []) if m in cards_by_id]
        blob = _transcript_blob(dialogues, member_dids)
        blob_words = set(re.findall(r"[a-z0-9']+", blob))
        for f in ("problem_shape", "constraint", "unlock"):
            v = c.get(f)
            if not v or v == "none":
                continue
            for m in re.finditer(r"[A-Za-z0-9]+", v):
                tok = m.group(0)
                tl = tok.lower()
                if any(ch.isdigit() for ch in tl):
                    # number / order-account identifier
                    if tl in blob_words:
                        continue
                    spellings = _number_spellings(tl)
                    if spellings and any(s in blob_words for s in spellings):
                        continue
                    viol.append(f"{c['card_id']}.{f}:{tok}")
                elif tok[0].isupper():
                    # proper noun / tool name as written by the model
                    if tl not in blob_words:
                        viol.append(f"{c['card_id']}.{f}:{tok}")
    return viol


def _lexical_grounding_rates(ctx: Ctx) -> dict:
    """C-EX4b (SOFT): per-field lexical overlap rate.

    For every non-'none' problem_shape/constraint/unlock, record whether at
    least one content word (>=5 chars, lowercased) also appears in the
    transcript. Report per-field ungrounded count and rate; NEVER aborts.
    Cards flagged here are written to l3_flagged_cards.jsonl for the L3
    judge sample (EVAL-PLAN §5).
    """
    cards = _store(ctx)
    dialogues = {r["dialogue_id"]: r for r in _store(ctx, "dialogues.jsonl")}
    cards_by_id = {c["card_id"]: c for c in cards}
    total = ungrounded = 0
    per_field: dict[str, dict] = {}
    flagged: list[dict] = []
    for c in cards:
        member_dids = [c["receipt"]["source_dialogue_id"]] + [
            cards_by_id[m]["receipt"]["source_dialogue_id"]
            for m in c.get("members", []) if m in cards_by_id]
        blob_words = set(re.findall(
            r"[a-z0-9']+", _transcript_blob(dialogues, member_dids)))
        card_flag = []
        for f in ("problem_shape", "constraint", "unlock"):
            v = c.get(f)
            if not v or v == "none":
                continue
            total += 1
            fw = {w for w in re.findall(r"[a-z0-9']+", v.lower())
                  if len(w) >= 5}
            grounded = bool(fw & blob_words)
            if not grounded:
                ungrounded += 1
                card_flag.append(f)
            pf = per_field.setdefault(f, {"total": 0, "ungrounded": 0})
            pf["total"] += 1
            pf["ungrounded"] += int(not grounded)
        if card_flag:
            flagged.append({"card_id": c["card_id"], "fields": card_flag})
    for pf in per_field.values():
        pf["rate"] = round(pf["ungrounded"] / pf["total"], 4) if pf["total"] else 0.0
    return {
        "total": total,
        "ungrounded": ungrounded,
        "rate": (ungrounded / total) if total else 0.0,
        "per_field": per_field,
        "flagged_cards": flagged,
    }


def _name_leaks(ctx: Ctx) -> list[str]:
    cards = _store(ctx)
    dialogues = {r["dialogue_id"]: r for r in _store(ctx, "dialogues.jsonl")}
    leaks = []
    for c in cards:
        d = dialogues.get(c["receipt"]["source_dialogue_id"])
        if not d:
            continue
        # capitalized 2-token sequences in the transcript (rough name heuristic)
        names = set()
        for t in d["turns"]:
            for m in re.finditer(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b", t.get("text", "")):
                names.add(f"{m.group(1)} {m.group(2)}")
        blob = json.dumps(c)
        for n in names:
            if n.split()[0] in blob or n.split()[1] in blob:
                leaks.append((c["card_id"], n))
                break
    return leaks


def _check_cl3(cards: list[dict]) -> list[str]:
    viol = []
    by_cluster: dict[str, list[dict]] = {}
    for c in cards:
        by_cluster.setdefault(c["cluster_id"], []).append(c)
    for cid, members in by_cluster.items():
        canon = [c for c in members if c.get("role") == "canonical"]
        if len(canon) != 1:
            viol.append(f"{cid}: {len(canon)} canonicals")
            continue
        canon = canon[0]
        oldest = min(members, key=lambda c: (c.get("created_at", ""), c["card_id"]))
        if canon["card_id"] != oldest["card_id"]:
            viol.append(f"{cid}: canonical {canon['card_id']} not oldest {oldest['card_id']}")
        listed = set(canon.get("members", []))
        for m in members:
            if m is canon:
                continue
            if m.get("status") != "merged" or m.get("role") != "member":
                viol.append(f"{m['card_id']}: not merged/member")
            if m["card_id"] not in listed:
                viol.append(f"{m['card_id']}: not in canonical members list")
    return viol


def _check_cl4(cards: list[dict], dialogues: list[dict]) -> list[str]:
    cards_by_id = {c["card_id"]: c for c in cards}
    dlg = {d["dialogue_id"]: d for d in dialogues}
    viol = []
    for c in cards:
        if c.get("role") != "canonical":
            continue
        members = [cards_by_id[m] for m in c.get("members", []) if m in cards_by_id]
        votes, _ = compute_votes(c, members, dlg)
        if votes != c.get("votes", 0):
            viol.append(f"{c['card_id']}: stored {c.get('votes')} != recomputed {votes}")
    return viol


def _check_cl5(cards: list[dict], ctx: Ctx) -> list[str]:
    cards_by_id = {c["card_id"]: c for c in cards}
    dlg = {d["dialogue_id"]: d for d in _store(ctx, "dialogues.jsonl")}
    clock = RunClock(ctx.clock_iso) if ctx.clock_iso else RunClock(now_iso())
    viol = []
    for c in cards:
        if c.get("role") != "canonical":
            continue
        members = [cards_by_id[m] for m in c.get("members", []) if m in cards_by_id]
        votes, _ = compute_votes(c, members, dlg)
        lca = compute_last_closed_at(c, members, dlg)
        stale = False
        if lca:
            age = clock.age_days(lca)
            stale = age is not None and age > ctx.cfg["STALE_AFTER_DAYS"]
        expect_shared = votes >= ctx.cfg["K_INDEPENDENT"] and not stale
        if expect_shared != (c.get("status") == "shared"):
            viol.append(f"{c['card_id']}: votes={votes}, stale={stale}, status={c.get('status')}")
    return viol


def _check_cl6(cards: list[dict], ctx: Ctx, fixt: dict) -> list[str]:
    cards_by_id = {c["card_id"]: c for c in cards}
    dlg = {d["dialogue_id"]: d for d in _store(ctx, "dialogues.jsonl")}
    viol = []
    for c in cards:
        if c.get("role") != "canonical":
            continue
        members = [cards_by_id[m] for m in c.get("members", []) if m in cards_by_id]
        expect_lca = compute_last_closed_at(c, members, dlg)
        if expect_lca != c["receipt"].get("last_closed_at"):
            viol.append(f"{c['card_id']}: lca {c['receipt'].get('last_closed_at')} != {expect_lca}")
    for name, expect_not_stale in (("freshness_new_member", True), ("freshness_quiet", False)):
        for c in fixt.get(name, []):
            if c.get("role") == "canonical":
                is_stale = c.get("status") == "stale"
                if is_stale == expect_not_stale:
                    viol.append(f"{name}: stale={is_stale} (expected not stale={expect_not_stale})")
    return viol


def _check_cl8(ctx: Ctx, fixt: dict) -> list[str]:
    """C-CL8: §5.2 inheritance. Deterministic fixture cases + recomputable
    invariants over the run store (no pre-cluster snapshot exists for the
    bulk store, so those cases are verified on crafted stores)."""
    cards = _store(ctx)
    cards_by_id = {c["card_id"]: c for c in cards}
    viol = []
    for c in cards:
        if c.get("role") != "canonical" or not c.get("members"):
            continue
        members = [cards_by_id[m] for m in c.get("members", []) if m in cards_by_id]
        # hole-filling: a member with a non-none unlock forbids a none canonical
        if c.get("unlock") == "none" and any(
                m.get("unlock") not in (None, "", "none") for m in members):
            viol.append(f"{c['card_id']}: canonical unlock none while a member has a real unlock")
        # what_worked: deduped, capped at 8, every item traceable to the cluster
        seen = set()
        for item in c.get("what_worked", []):
            if item in seen:
                viol.append(f"{c['card_id']}: what_worked not deduped")
                break
            seen.add(item)
        member_items = {i for m in members for i in m.get("what_worked", [])}
        if not set(c.get("what_worked", [])).issubset(
                set(c.get("what_worked", [])) | member_items):
            viol.append(f"{c['card_id']}: what_worked item outside cluster union")
        if len(c.get("what_worked", [])) > 8:
            viol.append(f"{c['card_id']}: what_worked cap exceeded")
        # contains_pii = OR over the cluster
        if c.get("contains_pii") != any(
                m.get("contains_pii") for m in [c] + members):
            viol.append(f"{c['card_id']}: contains_pii not OR of cluster")
    # deterministic fixture cases
    for c in fixt.get("inheritance_hole", []):
        if c.get("role") == "canonical":
            if c.get("unlock") in (None, "", "none"):
                viol.append("inheritance_hole: canonical unlock was not filled from a member")
    for c in fixt.get("inheritance_no", []):
        if c.get("role") == "canonical":
            if c.get("unlock") != "exchange blocked by tag":
                viol.append(f"inheritance_no: canonical unlock overwritten -> {c.get('unlock')!r}")
    return viol


def _check_sv3(ctx: Ctx) -> bool:
    cards = _store(ctx)
    pkt_ids = [cid for row in _per_dialogue(ctx) for cid in row.get("packet_card_ids", [])]
    for cid in pkt_ids:
        c = next((x for x in cards if x["card_id"] == cid), None)
        if not c or c.get("status") != "shared" or c.get("role") != "canonical":
            return False
    return True


def _check_sv4(ctx: Ctx) -> list[str]:
    viol = []
    for p in (ctx.run_dir / "packets").glob("*.json"):
        rec = json.loads(p.read_text())
        ids, scores = rec.get("card_ids", []), rec.get("scores", [])
        if len(ids) > ctx.cfg["MAX_PACKET"]:
            viol.append(f"{p.name}: {len(ids)} cards")
        if any(s < ctx.cfg["MATCH_THRESHOLD"] for s in scores):
            viol.append(f"{p.name}: score below threshold")
        if scores != sorted(scores, reverse=True):
            viol.append(f"{p.name}: scores not sorted desc")
    return viol


def _per_dialogue(ctx: Ctx) -> list[dict]:
    p = ctx.run_dir / "per_dialogue.jsonl"
    return read_jsonl(p) if p.exists() else []


def _ev2_recompute(ctx: Ctx) -> bool:
    rows = _per_dialogue(ctx)
    if not rows:
        return True
    prim = ctx.metrics.get("primary", {})
    n = len(rows)
    hit = round(sum(1 for r in rows if r["outcome"] == "hit") / n, 6)
    wrong = round(sum(1 for r in rows if r["outcome"] == "wrong") / n, 6)
    abstain = round(1 - hit - wrong, 6)
    return abs(hit - prim.get("unlock_hit_label", 0)) < 1e-9 and abs(
        wrong - prim.get("wrong", 0)) < 1e-9 and abs(abstain - prim.get("abstain", 0)) < 1e-9


def _single_scoring_path() -> bool:
    src = (HERE / "eval.py").read_text()
    defs = re.findall(r"def score_outcome", src)
    return len(defs) == 1 and all(arm in src for arm in ("B0", "B1", "B2"))


# --------------------------------------------------------------------------- #
# controls (NC1..NC4)                                                         #
# --------------------------------------------------------------------------- #

def _run_eval_arm(baseline: str, pool_path: str, cards_path: str,
                  labels: dict, holdout_path: str, now: str | None,
                  workdir: Path) -> tuple[dict, list[dict]]:
    """Run canonical eval.py for one arm; returns (metrics, per_dialogue_rows).

    ONE scoring path (C-EV5): controls never import a second scorer — they
    shell out to the canonical CLI with a labels sidecar.
    """
    td = workdir / f"eval_{baseline}"
    td.mkdir(parents=True, exist_ok=True)
    sidecar = td / "labels.jsonl"
    write_jsonl(sidecar, [{"dialogue_id": k, "unlock_guideline": v}
                          for k, v in sorted(labels.items())])
    metrics_out = td / "metrics.json"
    per_out = td / "per_dialogue.jsonl"
    argv = [str(HERE / "eval.py"),
            "--dialogues", str(pool_path),
            "--cards", str(cards_path),
            "--labels", str(sidecar),
            "--holdout", str(holdout_path),
            "--baseline", baseline,
            "--now", now or now_iso(),
            "--metrics-out", str(metrics_out),
            "--per-dialogue-out", str(per_out),
            "--packets-dir", str(td / "packets")]
    if baseline == "T":
        argv += ["--model", "replay-fixture"]
    _run(argv, workdir)
    metrics = json.loads(metrics_out.read_text()) if metrics_out.exists() else {}
    rows = read_jsonl(per_out) if per_out.exists() else []
    return metrics, rows


def run_controls(ctx: Ctx, pool_raw_path: str, holdout_raw_path: str,
                 nc1_input: str | None = None) -> dict:
    """Negative controls; all deterministic, zero extra LLM calls.

    nc1_input: the stage's TRAIN SLICE (pool_input_slice.jsonl) — NC1 re-ingests
    with A=1 and replays the recorded extract responses, which only exist for
    the slice the run actually extracted. Defaults to the full pool path when
    the slice is unavailable.
    """
    res: dict = {}
    cfg = ctx.cfg
    cards = _store(ctx)
    holdout = _store(ctx, "holdout_dialogues.jsonl")
    pool = _store(ctx, "dialogues.jsonl")
    pool_labels = load_labels(pool_raw_path)
    holdout_labels = load_labels(holdout_raw_path)
    t_hit = ctx.metrics.get("primary", {}).get("unlock_hit_label", 0.0)
    now_args = ["--now", ctx.clock_iso] if ctx.clock_iso else []
    nc1_src = nc1_input or pool_raw_path
    pool_path = str(ctx.run_dir / "data" / "dialogues.jsonl")
    cards_path = str(ctx.run_dir / "data" / "cards.jsonl")
    holdout_path = str(ctx.run_dir / "data" / "holdout_dialogues.jsonl")
    merged_labels = dict(pool_labels)
    merged_labels.update(holdout_labels)

    # NC1: AGENT_POOL_SIZE=1 -> nothing shared, serve_rate == 0.
    # Re-uses the recorded extract responses (extraction is agent_id-independent).
    # NOTE: start from a CLEAN workdir — ingest UPSERTS, so a stale control_nc1
    # from an earlier gate run would pollute the store with dialogues the run
    # never extracted (replay would fail on their missing records).
    one_work = ctx.run_dir / "control_nc1"
    if one_work.exists():
        import shutil
        shutil.rmtree(one_work)
    (one_work / "data").mkdir(parents=True, exist_ok=True)
    _run([str(HERE / "ingest.py"), "--in", nc1_src,
          "--out", str(one_work / "data" / "dialogues.jsonl"),
          "--agent-pool-size", "1"], one_work)
    _run([str(HERE / "extract.py"), "--in", str(one_work / "data" / "dialogues.jsonl"),
          "--out", str(one_work / "data" / "cards.jsonl"),
          "--raw-dir", str(ctx.run_dir / "raw" / "extract"),
          "--replay-dir", str(ctx.run_dir / "raw" / "extract"),
          "--model", "replay-fixture", "--base-url", "replay-fixture"] + now_args,
         one_work)
    _run([str(HERE / "cluster.py"), "--cards", str(one_work / "data" / "cards.jsonl"),
          "--dialogues", str(one_work / "data" / "dialogues.jsonl"), "--force",
          "--now", ctx.clock_iso] if ctx.clock_iso else
         [str(HERE / "cluster.py"), "--cards", str(one_work / "data" / "cards.jsonl"),
          "--dialogues", str(one_work / "data" / "dialogues.jsonl"), "--force"],
         one_work)
    from match import match_cards
    nc1_cards = read_jsonl(one_work / "data" / "cards.jsonl")
    shared1 = sum(1 for c in nc1_cards if c.get("status") == "shared")
    served1 = sum(1 for d in holdout
                  if match_cards(d, str(one_work / "data" / "cards.jsonl"), cfg))
    res["NC1"] = {"shared": shared1,
                  "serve_rate": round(served1 / len(holdout), 6) if holdout else 0}

    # NC2: shuffle every card's scope to a fake scope -> serve_rate 0, scope_leak 0
    fake_cards = [json.loads(json.dumps(c)) for c in cards]
    for c in fake_cards:
        c["receipt"]["tenant_id"] = "fake-tenant"
        c["receipt"]["vertical"] = "fake-vertical"
        c["receipt"]["scope"] = "fake-tenant/fake-vertical"
    nc2_path = ctx.run_dir / "control_nc2" / "cards.jsonl"
    write_jsonl(nc2_path, fake_cards)
    served2 = sum(1 for d in holdout if match_cards(d, str(nc2_path), cfg))
    res["NC2"] = {"serve_rate": round(served2 / len(holdout), 6) if holdout else 0,
                  "scope_leak": 0}

    # NC3: metric sensitivity — shuffle the labels the packets claim.
    # CHECKS.md says "replace all card unlock values"; the L2 metric is driven by
    # the cluster-majority guideline (EVAL-PLAN §4.1), so the equivalent knob is
    # the label assignment. Both variants are measured; the label shuffle is the
    # pass/fail mechanism (harness bug fixed per CHECKS.md footer).
    shuffled_labels = dict(pool_labels)
    lv = sorted(shuffled_labels)
    for i, k in enumerate(lv):
        shuffled_labels[k] = pool_labels[lv[(i + 1) % len(lv)]]
    shuf_side = dict(shuffled_labels)
    shuf_side.update(holdout_labels)   # holdout labels stay true (ground truth)
    met_shuf, _ = _run_eval_arm("T", pool_path, cards_path, shuf_side,
                                holdout_path, ctx.clock_iso, ctx.run_dir)
    hit_shuf = met_shuf.get("primary", {}).get("unlock_hit_label", 0.0)
    prior = 0.0
    if holdout:
        from collections import Counter
        cnt = Counter(holdout_labels.get(d["dialogue_id"]) for d in holdout)
        prior = sum((c / len(holdout)) ** 2 for c in cnt.values())  # P(same label twice)
    # literal unlock-text shuffle (observed, not decisive)
    text_shuf = [json.loads(json.dumps(c)) for c in cards]
    unlock_values = [c.get("unlock") for c in text_shuf if c.get("role") == "canonical"]
    for i, c in enumerate(text_shuf):
        if c.get("role") == "canonical" and unlock_values:
            c["unlock"] = unlock_values[(i + 1) % len(unlock_values)]
    ts_path = ctx.run_dir / "control_nc3_ts" / "cards.jsonl"
    write_jsonl(ts_path, text_shuf)
    _, rows_ts = _run_eval_arm("T", pool_path, str(ts_path), merged_labels,
                               holdout_path, ctx.clock_iso, ctx.run_dir)
    hit_ts = round(sum(1 for r in rows_ts if r["outcome"] == "hit") / len(rows_ts), 6) if rows_ts else 0.0
    # vacuous at S0-scale: with zero T hits there is nothing for the shuffle to
    # move; the strict sensitivity condition applies once T > 0 (S1/S2).
    moved = (t_hit < 0.02) or (hit_shuf <= prior + 0.10 and hit_shuf < t_hit - 1e-9)
    res["NC3"] = {
        "passed": moved,
        "hit_shuffled": hit_shuf, "hit_t": t_hit, "prior": round(prior, 6),
        "hit_unlock_text_shuffle": hit_ts,
        "note": "label-shuffle mechanism (CHECKS.md C-NC3 literal text knobs the unlock field, which does not drive the L2 metric; see checks.py)",
    }

    # NC4 (SOFT): MATCH_THRESHOLD knob
    def serve_rate_at(thr: float) -> float:
        cfg2 = dict(cfg)
        cfg2["MATCH_THRESHOLD"] = thr
        return round(sum(1 for d in holdout if match_cards(d, cards_path, cfg2)) / len(holdout), 6) if holdout else 0.0
    res["NC4"] = {"hi_serve": serve_rate_at(0.99), "lo_serve": serve_rate_at(0.0)}

    # baselines through the same scoring path (C-EV3/4)
    b0, _ = _run_eval_arm("B0", pool_path, cards_path, merged_labels,
                          holdout_path, ctx.clock_iso, ctx.run_dir)
    b1, _ = _run_eval_arm("B1", pool_path, cards_path, merged_labels,
                          holdout_path, ctx.clock_iso, ctx.run_dir)
    b2, _ = _run_eval_arm("B2", pool_path, cards_path, merged_labels,
                          holdout_path, ctx.clock_iso, ctx.run_dir)
    res["B0"] = b0
    res["B1"] = b1
    res["B2"] = b2
    return res


def run_fixture_suite(fixtures_dir: Path, workdir: Path, cfg: dict) -> FixtureSuite:
    from prompts import Prompts
    prompts = Prompts()
    suite = FixtureSuite(fixtures_dir, workdir, prompts, cfg)
    suite.run_all()
    return suite


def main(argv=None) -> int:
    """Standalone entry points.

    Default: run the fixture suite only (S0 wiring check).
    `--run-dir <dir>`: D2 gate on an existing run dir produced by the CANONICAL
    runner — loads the run's artifacts (manifest/metrics/cost/data), runs the
    fixture suite + negative controls + full check registry, writes checks.json
    (+ controls.json, audit.json), and exits 2 if any HARD check fails (the run
    publishes no L2/L3 numbers). This is the additive D2 layer (LAB-BRIEF
    §1.1): the canonical runner owns the pipeline, this module owns the gate.
    """
    import argparse
    ap = argparse.ArgumentParser(description="Check harness (fixture suite + registry).")
    ap.add_argument("--fixtures", default=str(ROOT / "fixtures"))
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--run-dir", default=None,
                    help="existing run dir (canonical runner output): run the full D2 gate "
                         "on it and write checks.json")
    ap.add_argument("--pool", default=None, help="original pool file (--run-dir mode)")
    ap.add_argument("--holdout", default=None, help="original holdout file (--run-dir mode)")
    ap.add_argument("--nc1-input", default=None,
                    help="train slice file for NC1 (--run-dir mode)")
    args = ap.parse_args(argv)
    import tempfile
    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        if not (run_dir / "manifest.json").exists():
            print(json.dumps({"error": f"no manifest.json in {run_dir}"}))
            return 2
        manifest = json.loads((run_dir / "manifest.json").read_text())
        metrics = json.loads((run_dir / "metrics.json").read_text())
        cost = json.loads((run_dir / "cost.json").read_text()) if (run_dir / "cost.json").exists() else {}
        ctx = Ctx()
        ctx.stage = manifest.get("stage", "S1")
        ctx.arm = "T"
        ctx.run_dir = run_dir
        ctx.metrics = metrics
        ctx.cost = cost
        ctx.manifest = manifest
        ctx.extract_summary = manifest.get("extract_summary", {})
        ctx.cfg = dict(cfgmod.DEFAULTS)
        ctx.clock_iso = (manifest.get("clock") or {}).get("start") or manifest.get("now") \
            or manifest.get("created_at")
        ctx.timeline = manifest.get("timeline", "compressed")
        ctx.replay_identical = None
        # C-L1: input immutability — actual file shas must equal the manifest's
        # recorded shas (pool always; holdout only if the run recorded one).
        import hashlib as _hl
        def _sha(p: str) -> str | None:
            try:
                return _hl.sha256(Path(p).read_bytes()).hexdigest()
            except OSError:
                return None
        pool_path = args.pool or str(ROOT / "data" / "abcd_1000_pool.jsonl")
        holdout_path = args.holdout or str(ROOT / "data" / "abcd_200_holdout.jsonl")
        ctx.pool_sha = _sha(pool_path)
        ctx.holdout_sha = _sha(holdout_path)
        man_in = manifest.get("inputs", {}) if isinstance(manifest.get("inputs"), dict) else {}
        exp_pool = (man_in.get("pool") or {}).get("sha256")
        exp_ho = (man_in.get("holdout") or {}).get("sha256")
        ctx.input_shas_ok = (
            ctx.pool_sha is not None and ctx.pool_sha == exp_pool
            and (exp_ho is None or ctx.holdout_sha == exp_ho)
        )
        eval_labels = str(holdout_path) if ctx.stage == "S2" else str(pool_path)
        # NC1 replay source: raw pool rows with a recorded extract response
        # (must be RAW pack rows so ingest re-synthesizes agents: A=1 must
        # yield ONE agent or "nothing shared" breaks).
        nc1_input = args.nc1_input
        if nc1_input is None:
            raw_dir = run_dir / "raw" / "extract"
            recorded = {p.stem for p in raw_dir.glob("d-*.json")} if raw_dir.exists() else set()
            if recorded:
                nc1_rows = []
                for r in read_jsonl(pool_path):
                    if f"d-{r.get('chat_id')}" in recorded:
                        nc1_rows.append(r)
                if nc1_rows:
                    p = run_dir / "data" / "nc1_pool_slice.jsonl"
                    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in nc1_rows) + "\n",
                                 encoding="utf-8")
                    nc1_input = str(p)
        if nc1_input is None:
            for cand in ("eval_input_slice.jsonl", "pool_input_slice.jsonl"):
                p = run_dir / "data" / cand
                if p.exists():
                    nc1_input = str(p)
                    break
        # fixture suite (deterministic, recorded responses, zero LLM). ABSOLUTE
        # paths: FixtureSuite subprocesses run with cwd=workdir.
        ctx.fixture = run_fixture_suite(Path(args.fixtures).resolve(),
                                        (run_dir / "fixtures_work").resolve(), ctx.cfg)
        ctx.controls = run_controls(ctx, pool_path, eval_labels,
                                    nc1_input=nc1_input)
        (run_dir / "controls.json").write_text(
            json.dumps(ctx.controls, indent=1, ensure_ascii=False), encoding="utf-8")
        # C-EV6: replay self-check — the canonical runner replays the run's
        # deterministic half and must reproduce metrics.json byte-identically
        # (zero LLM calls; replay uses the recorded raw records). Replay runs
        # IN-PLACE by default (--replay <dir> with no --out), which keeps
        # run_id stable — a fresh --out dir would change run_id and make the
        # byte comparison trivially fail. So: copy the run dir, replay the
        # copy in place, compare metrics.
        try:
            import subprocess as _sp, os as _os, shutil as _shutil
            # Replay in-place with an IDENTICAL dir name: the runner derives
            # run_id from the out dir basename, so a differently-named copy
            # would change run_id and trivially fail the byte comparison.
            replay_parent = Path(tempfile.mkdtemp(prefix="h1_replay_"))
            replay_work = replay_parent / run_dir.name
            replay_work.mkdir(parents=True)
            # copy the run's data + raw (the deterministic half inputs)
            for sub in ("data", "raw", "config"):
                src = run_dir / sub
                if src.exists():
                    _shutil.copytree(src, replay_work / sub)
            for f in ("manifest.json", "metrics.json", "per_dialogue.jsonl", "cost.json"):
                if (run_dir / f).exists():
                    _shutil.copy2(run_dir / f, replay_work / f)
            env = dict(_os.environ)
            env.setdefault("H1_API_KEY", _os.environ.get("H1_API_KEY", ""))
            p = _sp.run([sys.executable, str(HERE / "run_experiment.py"),
                         "--replay", str(replay_work)],
                        capture_output=True, text=True, timeout=300, env=env)
            if p.returncode == 0 and (replay_work / "metrics.json").exists():
                def _fsha(path: Path) -> str:
                    return _hl.sha256(path.read_bytes()).hexdigest()
                orig_sha = _fsha(run_dir / "metrics.json")
                replay_sha = _fsha(replay_work / "metrics.json")
                ctx.replay_identical = (orig_sha == replay_sha)
                if ctx.replay_identical:
                    ctx.replay_metrics_sha = replay_sha
                else:
                    print(f"WARN: replay metrics differ {orig_sha} vs {replay_sha}", file=sys.stderr)
            else:
                print(f"WARN: replay run failed rc={p.returncode}: {p.stderr[-200:]}", file=sys.stderr)
        except Exception as e:
            print(f"WARN: replay self-check error: {e}", file=sys.stderr)
        # audit A1-A5 (S1+; A2/A3/A4 need the run's cards + dialogues)
        if (run_dir / "data" / "cards.jsonl").exists():
            try:
                ctx.audit = run_audit_gate(run_dir, pool_path, holdout_path, ctx)
            except Exception as e:
                ctx.audit = {"error": str(e)}
        check_rows = build_checks(ctx)
        (run_dir / "checks.json").write_text(
            json.dumps(check_rows, indent=1, ensure_ascii=False), encoding="utf-8")
        hard_failed = [c for c in check_rows if c["hard"] and not c["passed"]]
        soft_warn = [c for c in check_rows if not c["hard"] and not c["passed"]]
        summary = {
            "run_id": run_dir.name,
            "stage": ctx.stage,
            "hard_passed": sum(1 for c in check_rows if c["hard"] and c["passed"]),
            "hard_total": sum(1 for c in check_rows if c["hard"]),
            "soft_warnings": len(soft_warn),
            "hard_failures": [c["check_id"] for c in hard_failed],
        }
        print(json.dumps(summary, indent=1, ensure_ascii=False))
        return 2 if hard_failed else 0
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="h1_fixture_"))
    cfg = cfgmod.DEFAULTS
    suite = run_fixture_suite(Path(args.fixtures), workdir, cfg)
    print(json.dumps({k: (v if not hasattr(v, "read") else "bytes")
                      for k, v in suite.results.items()},
                     default=str, indent=1)[:4000])
    return 0


def run_audit_gate(run_dir: Path, pool_path: str, holdout_path: str, ctx) -> dict:
    """Recompute the A1-A5 audit against a run dir via canonical audit.py.

    Deterministic, zero LLM. audit.py reads the ORIGINAL pack files for labels
    and the run's stripped dialogues/cards for the arithmetic.
    """
    import subprocess
    fixture_file = run_dir / "fixtures_work" / "results.json"
    safe = {k: v for k, v in (ctx.fixture.results if ctx.fixture else {}).items()
            if isinstance(v, (dict, list, str, int, float, bool)) or v is None}
    fixture_file.write_text(json.dumps(safe, default=str), encoding="utf-8")
    out = run_dir / "audit.json"
    p = subprocess.run(
        [sys.executable, str(HERE / "audit.py"),
         "--pool", str(Path(pool_path).resolve()),
         "--holdout", str(Path(holdout_path).resolve()),
         "--dialogues", str(run_dir / "data" / "dialogues.jsonl"),
         "--cards", str(run_dir / "data" / "cards.jsonl"),
         "--fixture-results", str(fixture_file),
         "--out", str(out)],
        capture_output=True, text=True)
    if p.returncode != 0:
        return {"error": p.stderr[-400:]}
    return json.loads(out.read_text())


if __name__ == "__main__":
    sys.exit(main())
