#!/usr/bin/env python3
"""Parallel S2 wrapper around tag.tag_dialogue. Same CLI as tag.py plus --workers."""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import config  # noqa: E402
import tag  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="S2 tag in parallel (H2v2)")
    ap.add_argument("--in", dest="inp", default=config.DEFAULT_PATHS["dialogues"])
    ap.add_argument("--out", default=config.DEFAULT_PATHS["sessions"])
    ap.add_argument("--ratings-out", default=config.DEFAULT_PATHS["ratings"])
    ap.add_argument("--raw-dir", default=config.DEFAULT_PATHS["raw_tag"])
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--replay-dir", default=None)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    rows = common.read_jsonl(args.inp)
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    replay = Path(args.replay_dir) if args.replay_dir else None

    already = {s.get("source_dialogue_id") for s in common.read_jsonl(args.out)}
    todo = []
    reused = 0
    for row in rows:
        did = row.get("dialogue_id") or row.get("source_dialogue_id")
        if did in already:
            reused += 1
        else:
            todo.append(row)

    stats = {"sessions": 0, "rejected": 0, "tag_calls": 0, "unparseable": 0, "reused": reused}
    new_rows: list[dict] = []

    def one(row: dict):
        return tag.tag_dialogue(
            row, model=args.model, base_url=args.base_url,
            raw_dir=raw_dir, replay_dir=replay,
        )

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = {pool.submit(one, row): row for row in todo}
            for fut in as_completed(futs):
                session, call_stats = fut.result()
                stats["tag_calls"] += call_stats["tag_calls"]
                stats["unparseable"] += call_stats["unparseable"]
                if session is None:
                    stats["rejected"] += 1
                else:
                    stats["sessions"] += 1
                    new_rows.append(session)

    persist_input = new_rows
    if persist_input:
        tag.process_rows(
            persist_input,
            sessions_path=args.out, ratings_path=args.ratings_out,
            raw_dir=raw_dir, model=args.model, base_url=args.base_url,
            replay_dir=replay,
        )
    pool_n = len(common.read_jsonl(args.out))
    rating_n = len(common.read_jsonl(args.ratings_out))
    summary = {
        "ok": True, "step": "S2", "script": "tag_parallel.py",
        "in": args.inp, "in_rows": len(rows),
        "sessions": stats["sessions"], "reused": stats["reused"],
        "rejected": stats["rejected"], "tag_calls": stats["tag_calls"],
        "unparseable": stats["unparseable"],
        "out": args.out, "pool_rows": pool_n,
        "ratings_out": args.ratings_out, "rating_rows": rating_n,
        "workers": args.workers,
    }
    print(json.dumps(summary, indent=2))
    return 0 if stats["rejected"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
