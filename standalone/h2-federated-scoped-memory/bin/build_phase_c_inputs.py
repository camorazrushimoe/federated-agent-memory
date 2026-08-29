#!/usr/bin/env python3
"""Phase C slice-run inputs (D5): adapted pool + slice dialogue files.

Deterministic, NO LLM. Mirrors the D0 labeler's clock exactly:
  pool rows    -> _index 1..1000    (closed_at = T0 + index minutes)
  holdout rows -> _index 1001..1200
so a gold useful id always has closed_at strictly earlier than its query
(C-FUTURE), and the 320-session pool (same-unlock union) precedes every
slice query.

Outputs (SPEC §3 schema, same mapping as adapt_h1_corpus.py):
  data/dialogues_pool.jsonl   the 320 pool-union sessions (pre-tagged by replay)
  data/dialogues_slice.jsonl  the 60 slice queries (measured, replay order)

Both are gitignored run inputs (raw transcripts = PII domain).

Usage:
  python bin/build_phase_c_inputs.py \
      --pool data/abcd_1000_pool.jsonl \
      --holdout data/abcd_200_holdout.jsonl \
      --out-pool data/dialogues_pool.jsonl \
      --out-slice data/dialogues_slice.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
SITE_UNLOCKS = {"slow_speed", "shopping_cart", "search_results"}
NEG_CORE_UNLOCKS = {"bad_price_competitor", "bad_price_yesterday",
                    "refund_initiate", "promo_code_invalid",
                    "promo_code_out_of_date"}
NEG_MANAGE_FILL = 8


def dialogue_id(row: dict) -> str:
    return f"d-{row['chat_id']}"


def closed_at(index: int) -> str:
    return (T0 + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%SZ")


def slice_family(row: dict) -> str | None:
    unlock = row.get("unlock", "")
    if "_how_" in unlock:
        return "howto"
    if unlock in SITE_UNLOCKS:
        return "site"
    if unlock in NEG_CORE_UNLOCKS:
        return "negative"
    if unlock.startswith("manage_"):
        return "negative_manage"
    return None


def build_slice(holdout_rows: list[dict]) -> list[tuple[str, str, str]]:
    howto, site, neg, neg_manage = [], [], [], []
    for row in holdout_rows:
        fam = slice_family(row)
        did = dialogue_id(row)
        if fam == "howto":
            howto.append((did, fam, row["unlock"]))
        elif fam == "site":
            site.append((did, fam, row["unlock"]))
        elif fam == "negative":
            neg.append((did, fam, row["unlock"]))
        elif fam == "negative_manage":
            neg_manage.append((did, fam, row["unlock"]))
    howto.sort(); site.sort(); neg.sort(); neg_manage.sort()
    return howto + site + (neg + neg_manage[:NEG_MANAGE_FILL])


def adapt_row(raw: dict, index: int) -> dict:
    """Same mapping as adapt_h1_corpus.py (SPEC §3, unlock dropped)."""
    turns = []
    for t in raw.get("turns") or []:
        sp = t.get("speaker")
        role = {"customer": "customer", "agent": "agent", "action": "tool"}.get(sp)
        if role is None:
            continue
        item = {"role": role, "text": t.get("text") or ""}
        if role == "tool":
            item["name"] = "action"
        turns.append(item)
    chat_id = raw.get("chat_id")
    return {
        "dialogue_id": f"d-{chat_id}",
        "tenant_id": raw.get("tenant") or "unknown",
        "vertical": raw.get("vertical") or "customer-support",
        "agent_id": "unknown",
        "channel": "web",
        "closed_at": closed_at(index),
        "turns": turns,
        "source_chat_id": chat_id,
        "source_split": raw.get("split"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", default="data/abcd_1000_pool.jsonl")
    ap.add_argument("--holdout", default="data/abcd_200_holdout.jsonl")
    ap.add_argument("--out-pool", default="data/dialogues_pool.jsonl")
    ap.add_argument("--out-slice", default="data/dialogues_slice.jsonl")
    args = ap.parse_args()

    pool_rows = common.read_jsonl(args.pool)
    holdout_rows = common.read_jsonl(args.holdout)
    for i, row in enumerate(pool_rows, start=1):
        row["_index"] = i
    for i, row in enumerate(holdout_rows, start=len(pool_rows) + 1):
        row["_index"] = i

    slice_ = build_slice(holdout_rows)
    by_id = {dialogue_id(r): r for r in holdout_rows}

    # 320-session pool union: same raw unlock + strictly earlier than each query.
    pool_union_ids: set[str] = set()
    for did, _, unlock in slice_:
        qclosed = closed_at(by_id[did]["_index"])
        for row in pool_rows:
            if row.get("unlock") != unlock:
                continue
            if closed_at(row["_index"]) >= qclosed:
                continue
            pool_union_ids.add(dialogue_id(row))

    pool_out = [adapt_row(row, row["_index"])
                for row in pool_rows if dialogue_id(row) in pool_union_ids]
    pool_out.sort(key=lambda d: d["dialogue_id"])
    slice_out = [adapt_row(by_id[did], by_id[did]["_index"]) for did, _, _ in slice_]
    slice_out.sort(key=lambda d: (d["closed_at"], d["dialogue_id"]))

    common.write_jsonl(args.out_pool, pool_out)
    common.write_jsonl(args.out_slice, slice_out)

    common.print_summary({
        "ok": True,
        "step": "build_phase_c_inputs",
        "pool_union": len(pool_out),
        "slice_queries": len(slice_out),
        "out_pool": args.out_pool,
        "out_slice": args.out_slice,
        "pool_sha256": common.sha256_of(args.out_pool),
        "slice_sha256": common.sha256_of(args.out_slice),
        "families": {f: sum(1 for _, fam, _ in slice_ if fam == f)
                     for f in ("howto", "site", "negative", "negative_manage")},
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
