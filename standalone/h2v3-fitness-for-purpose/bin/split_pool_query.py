#!/usr/bin/env python3
"""Split sessions_all.jsonl into pool sessions.jsonl + query_tags.jsonl.

Needed by eval_live_d4.py when the live S2 wrote a single combined file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def read_gold_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            rows.append(json.loads(s))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--slice", default=str(ROOT / "data" / "d0_slice.jsonl"))
    args = ap.parse_args()
    run = Path(args.run_dir)
    if not run.is_absolute():
        run = ROOT / run
    src = run / "data" / "sessions_all.jsonl"
    if not src.exists():
        alt = run / "data" / "sessions.jsonl"
        if not alt.exists():
            raise SystemExit(f"no sessions at {src} or {alt}")
        src = alt
    slice_ids = {r["query_id"] for r in read_gold_rows(Path(args.slice))}
    rows = common.read_jsonl(src)
    pool, queries = [], []
    for s in rows:
        did = s.get("source_dialogue_id") or s.get("dialogue_id")
        if did in slice_ids:
            queries.append(s)
        else:
            pool.append(s)
    out = run / "data"
    out.mkdir(parents=True, exist_ok=True)
    common.write_jsonl(out / "sessions.jsonl", pool)
    common.write_jsonl(out / "query_tags.jsonl", queries)
    print(json.dumps({"pool": len(pool), "queries": len(queries),
                      "slice": len(slice_ids)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
