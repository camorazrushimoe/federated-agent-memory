"""replay.py — the operator's single entry point (SPEC §8, RUN-PROTOCOL §1).

replay.py MUST NOT contain its own prompts, search or ranking logic (C-RP1).
It only calls the step scripts (S3->S4->S5 -> S6 -> S7 -> S2 per dialogue) as
subprocesses, in SPEC §8 order, so a session never mixes itself and never
learns from the future (C-FUTURE):

  per dialogue d, ordered by (closed_at, dialogue_id):
    1. S3-S5  against the already-laid pool (empty for the first dialogues —
              that is normal, C-RP2)
    2. S6     outcome of d (lab mode: --source gold)
    3. S7     update ratings of the packet, if there was one
    4. S2     tag d and lay it into the pool

Tagging inside replay follows PROMPTS.md §7: S3 delegates to S2 (the same
tag.py, same prompts) when the query is untagged; the tagged row is then laid
into the pool by S2 at step 4 — one LLM call per dialogue.

Phase C slice run (D4/D5, per lead dispatch 2026-08-29 11:36Z):
- Pool = the 320 same-unlock union sessions (the labeler's candidate
  universe; all gold useful ids are inside). Pre-tagged FIRST via
  --pool-dialogues (tag.py, 320 calls) so the pool is memory, not measured.
- Then the 60 slice queries are replayed (S3-S7-S2, 60 calls) against that
  pool. Per-query state (candidates, ratings snapshot, T packet, explore
  slot, C-FUTURE/C-SELF, serve latency, decay) is written to
  per_query_state.jsonl so eval.py can reconstruct B0/B1/B2/B3 packets
  through the SAME class-counting function without letting baselines touch
  ratings (only T learns).
- --replay <run_dir>: re-run from the run dir's raw/tag records, ZERO LLM
  calls (C-REPLAY); the operator passes --state-dir to a fresh dir and
  compares metrics.json byte-for-byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402

STAGES = {"S0", "S1", "S2", "S3", "S4"}
ARMS = {"T", "B0", "B1", "B2", "B3"}
STEP_ORDER = ["S3", "S4", "S5", "S6", "S7", "S2"]


def run_step(script: str, args: list[str], dialogue_id: str) -> dict:
    """Run one bin/ script, capture its JSON summary, fail loudly on error."""
    here = Path(__file__).resolve().parent
    cmd = [sys.executable, str(here / script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=here.parent)
    if proc.returncode != 0:
        sys.stderr.write(f"replay: {script} failed for {dialogue_id}:\n"
                         f"{proc.stderr or proc.stdout}\n")
        raise SystemExit(proc.returncode)
    try:  # each step prints exactly one JSON summary on stdout
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"stdout": proc.stdout.strip()}


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return "MISSING"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _git_head_and_dirty() -> tuple[str, bool]:
    try:
        here = Path(__file__).resolve().parents[2]
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, cwd=here).stdout.strip() or "unknown"
        dirty = bool(subprocess.run(["git", "status", "--porcelain"],
                                    capture_output=True, text=True,
                                    cwd=here).stdout.strip())
        return head, dirty
    except Exception:  # noqa: BLE001
        return "unknown", True


def write_manifest(run_dir: Path, args, dialogues: list[dict],
                   gold_path: str) -> None:
    """RUN-PROTOCOL §3.1 manifest. No sha -> run is void (C-RP3)."""
    head, dirty = _git_head_and_dirty()
    rd = run_dir / "data"
    man = {
        "run_id": run_dir.name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage": args.stage,
        "git_commit": head + (" (dirty)" if dirty else ""),
        "tag_model": args.model,
        "base_url": args.base_url or os.environ.get("H2_BASE_URL", "env"),
        "temperature": config.TEMPERATURE,
        "seed": args.seed,
        "arm": "T+B0+B1+B2+B3 (eval.py reconstructs B-arms; only T learns)",
        "config": {
            "MAX_PACKET": config.MAX_PACKET,
            "EXPLORE_SLOTS": config.EXPLORE_SLOTS,
            "TAG_FIELDS_MIN": config.TAG_FIELDS_MIN,
            "DECAY_EVERY_SHOWS": config.DECAY_EVERY_SHOWS,
            "DECAY_AMOUNT": config.DECAY_AMOUNT,
            "GOOD_DELTA": config.GOOD_DELTA,
            "BAD_DELTA": config.BAD_DELTA,
            "UNCLEAR_DELTA": config.UNCLEAR_DELTA,
        },
        "inputs": {
            "dialogues": {"path": args.dialogues, "sha256": sha256_file(args.dialogues),
                          "rows": len(common.read_jsonl(args.dialogues))},
            "gold_useful": {"path": gold_path, "sha256": sha256_file(gold_path),
                            "rows": len(common.read_jsonl(gold_path))},
            "prompts": {"path": "PROMPTS.md", "sha256": sha256_file("PROMPTS.md")},
        },
        "outputs": {
            "sessions.jsonl": str(rd / "sessions.jsonl"),
            "per_query_state.jsonl": str(rd / "per_query_state.jsonl"),
        },
        "replay_of": args.replay_of,
    }
    if args.pool_dialogues:
        man["inputs"]["pool_dialogues"] = {
            "path": args.pool_dialogues,
            "sha256": sha256_file(args.pool_dialogues),
            "rows": len(common.read_jsonl(args.pool_dialogues)),
        }
    common.write_json(run_dir / "manifest.json", man)


def _count_decay_fired(before: list[dict], after: list[dict]) -> int:
    """Number of pairs whose shows crossed a DECAY_EVERY_SHOWS multiple."""
    after_by = {(r["session_id"], r["tag_key"]): r for r in after}
    fired = 0
    for r in before:
        pair = (r["session_id"], r["tag_key"])
        a = after_by.get(pair)
        if a is None:
            continue
        sb = int(r.get("shows") or 0)
        sa = int(a.get("shows") or 0)
        for s in range(sb + 1, sa + 1):
            if s % config.DECAY_EVERY_SHOWS == 0:
                fired += 1
    return fired


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dialogues", default=config.DEFAULT_PATHS["dialogues"])
    ap.add_argument("--gold-tags", default=None,
                    help="gold_tags.jsonl (accepted; tag agreement is a later deliverable)")
    ap.add_argument("--gold-useful", default=None,
                    help="gold_useful.jsonl (S6 --source gold); required unless --replay")
    ap.add_argument("--stage", default="S0", choices=sorted(STAGES))
    ap.add_argument("--until", type=int, default=None,
                    help="process only the first N dialogues by closed_at")
    ap.add_argument("--arm", default="T", choices=sorted(ARMS),
                    help="only T is implemented in replay; B-arms are reconstructed "
                         "by eval.py from per-query state (D4)")
    ap.add_argument("--seed", type=int, default=0,
                    help="B1 seed (recorded; used by eval.py)")
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--pool-dialogues", default=None,
                    help="Phase C: pre-tag these dialogues into the pool first "
                         "(S2 only, no measurement; e.g. the 320-session universe)")
    ap.add_argument("--state-dir", default="data/replay",
                    help="where sessions/ratings/candidates/... live (run dir data/)")
    ap.add_argument("--run-dir", default=None,
                    help="run dir root (default: parent of --state-dir)")
    ap.add_argument("--replay", default=None, metavar="RUN_DIR",
                    help="re-run from RUN_DIR raw/tag records, zero LLM (C-REPLAY)")
    args = ap.parse_args()
    args.replay_of = args.replay

    replay_dir = None
    if args.replay:
        replay_dir = Path(args.replay) / "data" / "raw" / "tag"
        if not replay_dir.is_dir():
            return common.fail(f"--replay {args.replay}: no data/raw/tag dir found")
        # inputs come from the recorded manifest
        try:
            man = common.read_json(Path(args.replay) / "manifest.json")
            args.dialogues = man["inputs"]["dialogues"]["path"]
            args.gold_useful = man["inputs"]["gold_useful"]["path"]
            if "pool_dialogues" in man["inputs"]:
                args.pool_dialogues = man["inputs"]["pool_dialogues"]["path"]
            args.model = man["tag_model"]
            args.stage = man["stage"]
            args.seed = int(man.get("seed", 0))
        except Exception as exc:  # noqa: BLE001
            return common.fail(f"--replay manifest read failed: {exc!r}")
    if not args.gold_useful:
        return common.fail("--gold-useful is required (unless --replay reads it from the manifest)")

    rd = Path(args.state_dir)
    rd.mkdir(parents=True, exist_ok=True)
    run_dir = Path(args.run_dir) if args.run_dir else rd.parent
    run_dir.mkdir(parents=True, exist_ok=True)

    pool = rd / "sessions.jsonl"
    ratings = rd / "ratings.jsonl"
    candidates = rd / "candidates.jsonl"
    ranked = rd / "ranked.jsonl"
    packet = rd / "packet.json"
    serves = rd / "serves.jsonl"
    outcomes = rd / "outcomes.jsonl"
    state_f = rd / "update_state.json"
    query_tags = rd / "query_tags.jsonl"
    meta = rd / "query_meta.json"
    raw_dir = rd / "raw" / "tag"
    per_query_state = rd / "per_query_state.jsonl"
    packets_dir = run_dir / "packets"

    llm_args = ["--model", args.model]
    if args.base_url:
        llm_args += ["--base-url", args.base_url]
    if replay_dir is not None:
        llm_args += ["--replay-dir", str(replay_dir)]

    # ---- Phase C step 0: pre-tag the pool (S2 only, no measurement) ----
    if args.pool_dialogues:
        s2 = run_step("tag.py",
                      ["--in", args.pool_dialogues, "--out", str(pool),
                       "--ratings-out", str(ratings), "--raw-dir", str(raw_dir),
                       *llm_args],
                      "pool-pre-tag")
        pool_rows_before = s2.get("pool_rows", 0)
    else:
        pool_rows_before = len(common.read_jsonl(pool))

    # ---- measured dialogues ----
    dialogues = common.read_jsonl(args.dialogues)
    dialogues.sort(key=lambda d: (d.get("closed_at") or "", d["dialogue_id"]))
    if args.until is not None:
        dialogues = dialogues[: args.until]

    processed = []
    c_future_fail = False
    c_self_fail = False
    for d in dialogues:
        dialogue_id = d["dialogue_id"]
        qf = rd / f"query_{dialogue_id}.json"
        common.write_json(qf, d)
        if query_tags.exists():
            query_tags.unlink()  # fresh scratch per dialogue

        # 1. S3 -> S4 -> S5 against the already-laid pool
        t0 = time.time()
        s3 = run_step("retrieve.py",
                      ["--query", str(qf), "--pool", str(pool),
                       "--out", str(candidates), "--tag-out", str(query_tags),
                       "--ratings-out", str(ratings), "--meta", str(meta),
                       "--raw-dir", str(raw_dir), *llm_args],
                      dialogue_id)
        s4 = run_step("rank.py",
                      ["--candidates", str(candidates), "--ratings", str(ratings),
                       "--out", str(ranked), "--meta", str(meta)],
                      dialogue_id)
        s5 = run_step("mix.py",
                      ["--ranked", str(ranked), "--pool", str(pool),
                       "--out", str(packet), "--serves", str(serves),
                       "--meta", str(meta)],
                      dialogue_id)
        serve_ms = int((time.time() - t0) * 1000)
        # 2. S6 outcome (gold in the lab run)
        s6 = run_step("outcome.py",
                      ["--query", str(qf), "--packet", str(packet),
                       "--source", "gold", "--gold", args.gold_useful,
                       "--pool", str(pool), "--meta", str(meta),
                       "--out", str(outcomes)],
                      dialogue_id)
        # 3. S7 update ratings of the packet
        ratings_before = common.read_jsonl(ratings)
        s7 = run_step("update.py",
                      ["--outcome", str(outcomes), "--ratings", str(ratings),
                       "--state", str(state_f)],
                      dialogue_id)
        ratings_after = common.read_jsonl(ratings)
        decay_fired = _count_decay_fired(ratings_before, ratings_after)
        # 4. S2 lay the (already tagged) dialogue into the pool — no extra LLM
        s2 = run_step("tag.py",
                      ["--in", str(query_tags), "--out", str(pool),
                       "--ratings-out", str(ratings), "--raw-dir", str(raw_dir),
                       *llm_args],
                      dialogue_id)

        # C-FUTURE verification (report field): no future session in candidates.
        query_closed = d.get("closed_at") or ""
        future = []
        self_hit = []
        for s in common.read_jsonl(candidates):
            if (s.get("closed_at") or "") >= query_closed:
                future.append(s["session_id"])
            if s["session_id"] == common.session_id_of(dialogue_id) or \
               s.get("source_dialogue_id") == dialogue_id:
                self_hit.append(s["session_id"])
        if future:
            c_future_fail = True
        if self_hit:
            c_self_fail = True

        packet_ids = s5.get("packet_session_ids") or []
        entry = {
            "dialogue_id": dialogue_id,
            "closed_at": query_closed,
            "order": STEP_ORDER,
            "n_candidates": s3.get("candidates"),
            "candidate_ids": s3.get("candidate_ids"),
            "ranked_ids": s4.get("ranked_ids"),
            "packet_session_ids": packet_ids,
            "explore_session_id": s4.get("explore_slot"),
            "outcome": s6.get("outcome"),
            "tag_key": s6.get("tag_key"),
            "c_future_ok": not future,
            "c_self_ok": not self_hit,
            "pool_size_after": s2.get("pool_rows"),
            "s2_lay_llm_calls": 0,
        }
        processed.append(entry)
        print(json.dumps(entry, ensure_ascii=False, sort_keys=True))

        # per-query state for eval.py (D4): everything the B-arms need,
        # captured at query time, without touching ratings.
        common.append_jsonl(per_query_state, {
            "query_id": dialogue_id,
            "closed_at": query_closed,
            "tag_key": s6.get("tag_key"),
            "candidate_session_ids": s3.get("candidate_ids") or [],
            "candidate_noise": 0,  # retrieve.py enforces TAG_FIELDS_MIN (C-RT1)
            "ratings_snapshot": ratings_before,
            "packet_session_ids": packet_ids,
            "ranked_session_ids": s4.get("ranked_ids") or [],
            "explore_session_id": s4.get("explore_slot"),
            "outcome": s6.get("outcome"),
            "c_future_ok": not future,
            "c_self_ok": not self_hit,
            "serve_ms": serve_ms,
            "decay_fired": decay_fired,
            "seed": args.seed,
        })
        pkt = common.read_json(packet)
        packets_dir.mkdir(parents=True, exist_ok=True)
        (packets_dir / f"{dialogue_id}.txt").write_text(
            pkt.get("packet_text", ""), encoding="utf-8")

    if args.replay is None:
        write_manifest(run_dir, args, dialogues, args.gold_useful)

    summary = {
        "ok": True,
        "step": "replay",
        "script": "replay.py",
        "stage": args.stage,
        "arm": args.arm,
        "seed": args.seed,
        "until": args.until,
        "replay_of": args.replay,
        "dialogues_total": len(common.read_jsonl(args.dialogues)),
        "processed": len(processed),
        "packets_nonempty": sum(1 for e in processed if e["packet_session_ids"]),
        "c_future_ok": not c_future_fail,
        "c_self_ok": not c_self_fail,
        "order": STEP_ORDER,
        "gold_tags": args.gold_tags,
        "gold_useful": args.gold_useful,
        "pool_rows_after_pre_tag": pool_rows_before,
        "state_dir": str(rd),
    }
    common.print_summary(summary)
    return 0 if not c_future_fail else 3


if __name__ == "__main__":
    raise SystemExit(main())
