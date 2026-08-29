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

State lives under data/replay/ (gitignored). Per-dialogue progress is printed
as one compact JSON line each, plus a final summary object.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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


def main() -> int:
    ap = argparse.ArgumentParser(description="H2 replay: pipeline in SPEC §8 order")
    ap.add_argument("--dialogues", default=config.DEFAULT_PATHS["dialogues"])
    ap.add_argument("--gold-tags", default=None,
                    help="gold_tags.jsonl (accepted; tag agreement is a later deliverable)")
    ap.add_argument("--gold-useful", required=True,
                    help="gold_useful.jsonl (S6 --source gold)")
    ap.add_argument("--stage", default="S0", choices=sorted(STAGES))
    ap.add_argument("--until", type=int, default=None,
                    help="process only the first N dialogues by closed_at")
    ap.add_argument("--arm", default="T", choices=sorted(ARMS),
                    help="only T is implemented in this pass (B-arms are D4)")
    ap.add_argument("--seed", type=int, default=0,
                    help="accepted for B1 later; recorded only in this pass")
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--base-url", default=None)
    args = ap.parse_args()

    if args.arm != "T":
        return common.fail(
            f"--arm {args.arm} is not implemented in this pass (D4 adds B-arms)")

    dialogues = common.read_jsonl(args.dialogues)
    dialogues.sort(key=lambda d: (d.get("closed_at") or "", d["dialogue_id"]))
    if args.until is not None:
        dialogues = dialogues[: args.until]

    rd = Path("data/replay")
    rd.mkdir(parents=True, exist_ok=True)
    pool, ratings, candidates, ranked, packet, serves, outcomes, state = (
        rd / "sessions.jsonl", rd / "ratings.jsonl", rd / "candidates.jsonl",
        rd / "ranked.jsonl", rd / "packet.json", rd / "serves.jsonl",
        rd / "outcomes.jsonl", rd / "update_state.json")
    query_tags = rd / "query_tags.jsonl"
    meta = rd / "query_meta.json"
    raw_dir = rd / "raw" / "tag"

    llm_args = ["--model", args.model]
    if args.base_url:
        llm_args += ["--base-url", args.base_url]

    processed = []
    c_future_fail = False
    for d in dialogues:
        dialogue_id = d["dialogue_id"]
        qf = rd / f"query_{dialogue_id}.json"
        common.write_json(qf, d)
        if query_tags.exists():
            query_tags.unlink()  # fresh scratch per dialogue

        # 1. S3 -> S4 -> S5 against the already-laid pool
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
        # 2. S6 outcome (gold in the lab run)
        s6 = run_step("outcome.py",
                      ["--query", str(qf), "--packet", str(packet),
                       "--source", "gold", "--gold", args.gold_useful,
                       "--pool", str(pool), "--meta", str(meta),
                       "--out", str(outcomes)],
                      dialogue_id)
        # 3. S7 update ratings of the packet
        s7 = run_step("update.py",
                      ["--outcome", str(outcomes), "--ratings", str(ratings),
                       "--state", str(state)],
                      dialogue_id)
        # 4. S2 lay the (already tagged) dialogue into the pool — no extra LLM
        s2 = run_step("tag.py",
                      ["--in", str(query_tags), "--out", str(pool),
                       "--ratings-out", str(ratings), "--raw-dir", str(raw_dir),
                       *llm_args],
                      dialogue_id)

        # C-FUTURE verification (report field): no future session in candidates.
        query_closed = d.get("closed_at") or ""
        future = []
        for s in common.read_jsonl(candidates):
            if (s.get("closed_at") or "") >= query_closed:
                future.append(s["session_id"])
        if future:
            c_future_fail = True

        entry = {
            "dialogue_id": dialogue_id,
            "closed_at": query_closed,
            "order": STEP_ORDER,
            "n_candidates": s3.get("candidates"),
            "candidate_ids": s3.get("candidate_ids"),
            "ranked_ids": s4.get("ranked_ids"),
            "packet_session_ids": s5.get("packet_session_ids"),
            "outcome": s6.get("outcome"),
            "tag_key": s6.get("tag_key"),
            "c_future_ok": not future,
            "pool_size_after": s2.get("pool_rows"),
            # tags came from the S3 delegation (PROMPTS.md §7); step-4 lay
            # makes no extra call
            "s2_lay_llm_calls": 0,
        }
        processed.append(entry)
        print(json.dumps(entry, ensure_ascii=False, sort_keys=True))

    summary = {
        "ok": True,
        "step": "replay",
        "script": "replay.py",
        "stage": args.stage,
        "arm": args.arm,
        "seed": args.seed,
        "until": args.until,
        "dialogues_total": len(common.read_jsonl(args.dialogues)),
        "processed": len(processed),
        "packets_nonempty": sum(1 for e in processed if e["packet_session_ids"]),
        "c_future_ok": not c_future_fail,
        "order": STEP_ORDER,
        "gold_tags": args.gold_tags,
        "gold_useful": args.gold_useful,
    }
    common.print_summary(summary)
    return 0 if not c_future_fail else 3


if __name__ == "__main__":
    raise SystemExit(main())
