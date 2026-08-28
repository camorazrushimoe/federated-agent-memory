#!/usr/bin/env python3
"""tick.py — the operator entry point (SPEC §6.0).

Usage:
  python bin/tick.py --in chats.jsonl
  python bin/tick.py --in chats.jsonl --force-cluster

Runs, in order, ingest.py -> extract.py -> cluster.py (cluster only if the
cursor says so, or --force-cluster). Prints the concatenated JSON summaries,
one line per step: {step:"ingest", ...}, {step:"extract", ...},
{step:"cluster", ...}.

There is no cron; operators run tick.py, not the inner scripts (SPEC §5).
"""

import argparse
import json
import os
import subprocess
import sys

BIN = os.path.dirname(os.path.abspath(__file__))


def run(script, args):
    out = subprocess.run([sys.executable, os.path.join(BIN, script)] + args,
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
        raise SystemExit(f"tick: {script} failed (rc={out.returncode})")
    try:
        return json.loads(out.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.stderr.write(out.stdout)
        raise SystemExit(f"tick: {script} printed no JSON summary")


def main():
    ap = argparse.ArgumentParser(description="Ingest+extract+cluster (SPEC §6.0)")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default=None,
                    help="run dir; defaults to the folder of --cards/--dialogues")
    ap.add_argument("--dialogues", default=None,
                    help="normalized dialogue store (default: <out>/data/dialogues.jsonl)")
    ap.add_argument("--cards", default=None,
                    help="card store (default: <out>/data/cards.jsonl)")
    ap.add_argument("--delta-out", default=None)
    ap.add_argument("--force-cluster", action="store_true")
    ap.add_argument("--model", required=True,
                    help="extract model id (no default in bin/ — D8)")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--agent-pool-size", type=int, default=4)
    ap.add_argument("--timeline", choices=["compressed", "aged"],
                    default="compressed")
    ap.add_argument("--t0", default=None)
    ap.add_argument("--at", default=None)
    ap.add_argument("--now", default=None)
    ap.add_argument("--replay-dir", default=None)
    ap.add_argument("--config", action="append", default=[])
    args = ap.parse_args()

    out_dir = args.out or os.path.dirname(
        os.path.abspath(args.cards or os.path.join("data", "cards.jsonl")))
    dialogues = args.dialogues or os.path.join(out_dir, "data",
                                               "dialogues.jsonl")
    cards = args.cards or os.path.join(out_dir, "data", "cards.jsonl")
    delta = args.delta_out or os.path.join(out_dir, "data",
                                           "dialogues_delta.jsonl")

    ingest = run("ingest.py", ["--in", args.inp, "--out", dialogues,
                               "--append", "--delta-out", delta,
                               "--agent-pool-size",
                               str(args.agent_pool_size),
                               "--timeline", args.timeline,
                               "--cursor-file", os.path.join(
                                   out_dir, "data", "cluster_cursor.json")] +
                              ([ "--t0", args.t0] if args.t0 else []) +
                              [c for kv in args.config for c in
                               ("--config", kv)])
    ingest["step"] = "ingest"

    extract = run("extract.py",
                  ["--in", delta, "--out", cards, "--model", args.model,
                   "--raw-dir", os.path.join(out_dir, "raw", "extract")] +
                  (["--base-url", args.base_url] if args.base_url else []) +
                  (["--api-key", args.api_key] if args.api_key else []) +
                  (["--at", args.at] if args.at else []) +
                  (["--replay-dir", args.replay_dir]
                   if args.replay_dir else []) +
                  [c for kv in args.config for c in ("--config", kv)])
    extract["step"] = "extract"

    cluster = run("cluster.py",
                  ["--cards", cards, "--dialogues", dialogues,
                   "--cursor-file", os.path.join(out_dir, "data",
                                                 "cluster_cursor.json")] +
                  (["--force"] if args.force_cluster else []) +
                  (["--now", args.now] if args.now else []) +
                  [c for kv in args.config for c in ("--config", kv)])
    cluster["step"] = "cluster"

    for s in (ingest, extract, cluster):
        print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
