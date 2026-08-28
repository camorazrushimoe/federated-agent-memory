#!/usr/bin/env python3
"""tick.py — the operator entry point (SPEC §6.0). No cron anywhere.

    python bin/tick.py --in chats.jsonl [--force-cluster] [--model MODEL] \\
        [--out data/dialogues.jsonl] [--cards data/cards.jsonl] \\
        [--raw-dir data/raw/extract] [--now ISO] [--set k=v]

Runs, in order: ingest.py → extract.py → cluster.py. cluster.py is invoked on
every tick; it enforces the global cursor itself (no-op + {ran:false,
remaining:N} when fewer than CLUSTER_EVERY_N_CHATS new dialogues landed),
unless --force-cluster is passed (then --force is forwarded). The JSON
summaries of the inner scripts are concatenated on stdout.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import os
import subprocess
import sys

import config as cfg
import jsonio as hio
from common import now_iso

BIN_DIR = os.path.dirname(os.path.abspath(__file__))


def _run_script(name, argv):
    proc = subprocess.run([sys.executable, os.path.join(BIN_DIR, name)] + argv,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(f"{name} failed (rc={proc.returncode}):\n"
                         f"{proc.stderr}\n{proc.stdout}\n")
        sys.exit(proc.returncode)
    sys.stdout.write(proc.stdout)
    if proc.stdout and not proc.stdout.endswith("\n"):
        sys.stdout.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="tick.py",
        description="Operator entry point: ingest → extract → cluster.")
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", default="data/dialogues.jsonl")
    ap.add_argument("--cards", dest="cards_path", default="data/cards.jsonl")
    ap.add_argument("--raw-dir", dest="raw_dir", default="data/raw/extract")
    ap.add_argument("--model", required=True)
    ap.add_argument("--force-cluster", action="store_true")
    ap.add_argument("--timeline", choices=cfg.TIMELINE_MODES,
                    default="compressed")
    ap.add_argument("--agent-pool-size", type=int, default=None)
    ap.add_argument("--now", default=None,
                    help="pinned ISO timestamp (default: real UTC now — tick "
                         "is the operator entry point, brief §6)")
    ap.add_argument("--base-url", default=None)
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    pinned_now = args.now or now_iso()
    base_args = ["--set", *args.set] if args.set else []

    ingest_argv = ["--in", args.in_path, "--out", args.out_path,
                   "--timeline", args.timeline] + base_args
    if args.agent_pool_size is not None:
        ingest_argv += ["--agent-pool-size", str(args.agent_pool_size)]
    _run_script("ingest.py", ingest_argv)

    extract_argv = ["--in", args.out_path, "--out", args.cards_path,
                    "--model", args.model, "--raw-dir", args.raw_dir,
                    "--now", pinned_now] + base_args
    if args.base_url:
        extract_argv += ["--base-url", args.base_url]
    _run_script("extract.py", extract_argv)

    cluster_argv = ["--cards", args.cards_path, "--dialogues", args.out_path,
                    "--now", pinned_now] + base_args
    if args.force_cluster:
        cluster_argv.append("--force")
    _run_script("cluster.py", cluster_argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
