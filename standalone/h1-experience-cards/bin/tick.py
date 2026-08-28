#!/usr/bin/env python3
"""tick.py — the operator entry point (SPEC §6.0).

    python bin/tick.py --in chats.jsonl --out-dir runs/<run_id>/data \
        [--model M --base-url URL] [--force-cluster] [--raw-dir ...] \
        [--replay] [--clock-start ISO] [--start-index N]

Runs, in order: ingest.py -> extract.py -> cluster.py (cluster only if the
100-chat cursor fires, or --force-cluster). Prints the concatenated JSON
summaries. This is what a cron-less loop calls; inner scripts stay for tests
and the runner.

All model configuration arrives via flags (--model, --base-url) exactly like
every other script; H1_API_KEY is read from the environment by llm.py.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _run(cmd: list[str]) -> dict:
    """Run an inner script, return its stdout JSON (fail loudly otherwise)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"tick: inner script failed: {' '.join(cmd)}\n"
            f"stdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}")
    if not proc.stdout.strip():
        return {}
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Operator entry point: ingest -> extract -> cluster (SPEC §6.0).")
    ap.add_argument("--in", dest="inp", required=True, help="input chats.jsonl (pack or spec format)")
    ap.add_argument("--out-dir", required=True, help="run data dir (dialogues.jsonl, cards.jsonl, cursor live here)")
    ap.add_argument("--model", required=True, help="extract model id (no default)")
    ap.add_argument("--base-url", required=True, help="OpenAI-compatible base URL (no default)")
    ap.add_argument("--force-cluster", action="store_true", help="cluster even if the cursor gate has not fired")
    ap.add_argument("--raw-dir", default=None, help="record raw extract responses here")
    ap.add_argument("--replay", action="store_true", help="read recorded responses instead of calling the LLM")
    ap.add_argument("--clock-start", default=None, help="pinned run clock ISO (default: now)")
    ap.add_argument("--start-index", type=int, default=0, help="absolute ingestion index offset (chunked runs)")
    ap.add_argument("--agent-pool-size", type=int, default=None)
    ap.add_argument("--timeline", choices=("compressed", "aged"), default=None)
    ap.add_argument("--t0", default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dialogues = str(out_dir / "dialogues.jsonl")
    cards = str(out_dir / "cards.jsonl")
    this = Path(__file__).resolve().parent

    # 1. ingest
    ingest_cmd = [sys.executable, str(this / "ingest.py"),
                  "--in", args.inp, "--out", dialogues]
    for flag, val in (("--agent-pool-size", args.agent_pool_size),
                      ("--timeline", args.timeline), ("--t0", args.t0)):
        if val is not None:
            ingest_cmd += [flag, str(val)]
    summary = _run(ingest_cmd)

    # 2. extract (only dialogues we have not extracted yet are LLM calls; the
    #    upsert skips cards already in a cluster, so re-running a tick is safe)
    extract_cmd = [sys.executable, str(this / "extract.py"),
                   "--in", dialogues, "--out", cards,
                   "--model", args.model, "--base-url", args.base_url]
    if args.raw_dir:
        extract_cmd += ["--raw-dir", args.raw_dir]
    if args.replay:
        extract_cmd.append("--replay")
    if args.clock_start:
        extract_cmd += ["--clock-start", args.clock_start]
    if args.start_index:
        extract_cmd += ["--start-index", str(args.start_index)]
    if args.max_tokens:
        extract_cmd += ["--max-tokens", str(args.max_tokens)]
    summary["extract"] = _run(extract_cmd)

    # 3. cluster (cursor-gated; --force-cluster bypasses)
    cluster_cmd = [sys.executable, str(this / "cluster.py"),
                   "--cards", cards, "--dialogues", dialogues]
    if args.force_cluster:
        cluster_cmd.append("--force")
    if args.clock_start:
        cluster_cmd += ["--now", args.clock_start]
    summary["cluster"] = _run(cluster_cmd)

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
