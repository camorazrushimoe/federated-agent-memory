#!/usr/bin/env python3
"""D0 slice manifest writer — Phase B infra (ROUND-0-PLAN §6).

Builds data/d0_slice.jsonl, the FROZEN 60-query slice, with the SAME
deterministic rule as the labeler (bin/label_gold_useful.py build_slice):
34 FAQ how-to + 6 site-troubleshoot + 20 negatives (12 core dispute/promo
+ first 8 manage_* by dialogue_id). Rows: {query_id, family, unlock,
closed_at}. sha256 printed on stdout is the freeze hash — record it in the
D0 manifest. No LLM, no writes outside data/d0_slice.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from label_gold_useful import (  # same deterministic rule as the labeler
    build_slice, dialogue_id, load_raw, synthetic_closed_at,
)

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def main() -> int:
    pool = load_raw(DATA / "abcd_1000_pool.jsonl")
    holdout = load_raw(DATA / "abcd_200_holdout.jsonl")
    for i, row in enumerate(pool, start=1):
        row["_index"] = i
    for i, row in enumerate(holdout, start=len(pool) + 1):
        row["_index"] = i
    by_id = {dialogue_id(r): r for r in holdout}
    slice_ = build_slice(holdout)
    rows = [{"query_id": did, "family": fam, "unlock": unlock,
             "closed_at": synthetic_closed_at(by_id[did]["_index"])}
            for did, fam, unlock in slice_]
    out = DATA / "d0_slice.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                           for r in rows), encoding="utf-8")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print(json.dumps({
        "rows": len(rows),
        "families": {f: sum(1 for r in rows if r["family"] == f)
                     for f in ("howto", "site", "negative", "negative_manage")},
        "sha256": sha,
        "out": str(out),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
