#!/usr/bin/env python3
"""D3 — audit.json (EVAL-PLAN §7 A1..A6 + ROTATION_BURN_IN).

Deterministic, NO LLM. Reads canonical data on disk:
  data/abcd_1000_pool.jsonl, data/abcd_200_holdout.jsonl,
  data/d0_slice.jsonl, data/gold_useful.jsonl
and writes data/../runs/<run_dir>/audit.json (or --out).

A2/A3/A4: gold_tags is NOT authorized yet (ROUND-0-PLAN §8) — so the audit
states N/A-with-proxy explicitly, per the lead's Phase C dispatch:
  A2 -> N/A (gold_tags pending); unlock-universe proxy reported
  A3 -> N/A (gold_tags pending); S2-tag tag_key distribution comes from the run
  A4 -> proxy on the unlock-universe candidate counts (no tag model needed);
        tag-based candidate counts land in metrics.json.retrieve from the run.

Usage:
  python bin/audit.py --out runs/<run_id>/audit.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
SITE_UNLOCKS = {"slow_speed", "shopping_cart", "search_results"}
NEG_CORE_UNLOCKS = {"bad_price_competitor", "bad_price_yesterday",
                    "refund_initiate", "promo_code_invalid",
                    "promo_code_out_of_date"}
NEG_MANAGE_FILL = 8


def closed_at(index: int) -> str:
    return (T0 + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%SZ")


def dialogue_id(row: dict) -> str:
    return f"d-{row['chat_id']}"


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
    """Deterministic slice per DATA-AUDIT §6 (mirrors label_gold_useful)."""
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


def load_gold(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", default="data/abcd_1000_pool.jsonl")
    ap.add_argument("--holdout", default="data/abcd_200_holdout.jsonl")
    ap.add_argument("--slice", default="data/d0_slice.jsonl")
    ap.add_argument("--gold", default="data/gold_useful.jsonl")
    ap.add_argument("--out", default="runs/2026-08-29_PhaseC_slice_deepseek-v4-flash/audit.json")
    ap.add_argument("--max-packet", type=int, default=config.MAX_PACKET)
    args = ap.parse_args()

    pool_rows = common.read_jsonl(args.pool)
    holdout_rows = common.read_jsonl(args.holdout)
    for i, row in enumerate(pool_rows, start=1):
        row["_index"] = i
    for i, row in enumerate(holdout_rows, start=len(pool_rows) + 1):
        row["_index"] = i

    slice_ = build_slice(holdout_rows)
    slice_ids = [did for did, _, _ in slice_]
    gold = load_gold(Path(args.gold))
    gold_by_id = {r["query_id"]: r for r in gold}

    # --- A1: fraction of slice queries with >= 1 useful session earlier ---
    # Canonical gold (post sign-off): non-empty useful lists.
    non_empty = [r for r in gold if r["useful_dialogue_ids"]]
    a1 = len(non_empty) / len(gold) if gold else 0.0

    # --- A2 proxy (unlock universe): fraction of gold pairs that would split
    # on TAG_FIELDS_MIN under RAW unlock buckets — the labeler's candidate
    # universe is unlock-defined, so the relevant proxy is: are the gold
    # useful ids inside the same-unlock candidate scope? (0 outside already
    # verified; recompute here for the audit file.) gold_tags-based A2 is N/A.
    by_id = {dialogue_id(r): r for r in holdout_rows}
    useful_outside = 0
    n_pairs = 0
    for did, _, unlock in slice_:
        qrow = by_id[did]
        qclosed = closed_at(qrow["_index"])
        cand_ids = set()
        for row in pool_rows:
            if row.get("unlock") != unlock:
                continue
            if closed_at(row["_index"]) >= qclosed:
                continue
            cand_ids.add(dialogue_id(row))
        useful = gold_by_id.get(did, {}).get("useful_dialogue_ids") or []
        for u in useful:
            n_pairs += 1
            if u not in cand_ids:
                useful_outside += 1

    # --- A3 proxy: unique tag_key on the slice (raw unlock buckets, since
    # gold_tags is not authorized). Real S2-tag tag_key distribution is
    # reported from the run (metrics.json.retrieve / run report).
    unlock_counts: dict[str, int] = {}
    for _, _, unlock in slice_:
        unlock_counts[unlock] = unlock_counts.get(unlock, 0) + 1
    med_bucket = sorted(unlock_counts.values())[len(unlock_counts) // 2]

    # --- A4 proxy: fraction of slice queries with > MAX_PACKET candidates
    # under the unlock-universe candidate scope (no tag model needed).
    gt_max = 0
    per_query_cands = {}
    for did, _, unlock in slice_:
        qclosed = closed_at(by_id[did]["_index"])
        n = sum(1 for row in pool_rows
                if row.get("unlock") == unlock
                and closed_at(row["_index"]) < qclosed)
        per_query_cands[did] = n
        if n > args.max_packet:
            gt_max += 1
    a4 = gt_max / len(slice_) if slice_ else 0.0

    # --- A5: gold coverage ---
    n_gold_rows = len(gold)
    n_non_empty = len(non_empty)
    n_pairs_total = sum(len(r["useful_dialogue_ids"]) for r in gold)
    a5_publishable = n_pairs_total >= 40  # EVAL-PLAN §7 A5

    # --- A6: median transcript tokens x MAX_PACKET (len//4 fallback,
    # method recorded). Transcripts = the pool sessions that will actually
    # enter packets (the 320 same-unlock union).
    pool_union_ids = set()
    for did, _, unlock in slice_:
        qclosed = closed_at(by_id[did]["_index"])
        for row in pool_rows:
            if row.get("unlock") == unlock and closed_at(row["_index"]) < qclosed:
                pool_union_ids.add(dialogue_id(row))
    pool_union = [r for r in pool_rows if dialogue_id(r) in pool_union_ids]
    token_lengths = []
    for row in pool_union:
        transcript = common.render_transcript([
            {"role": "customer" if t.get("speaker") == "customer"
             else "agent" if t.get("speaker") == "agent"
             else "tool", "text": t.get("text") or ""}
            for t in row.get("turns") or []
            if t.get("speaker") in ("customer", "agent", "action")])
        token_lengths.append(len(transcript) // 4)
    token_lengths.sort()
    median_tokens = token_lengths[len(token_lengths) // 2] if token_lengths else 0
    a6 = median_tokens * args.max_packet

    # --- ROTATION_BURN_IN: first index (slice queries ordered by closed_at)
    # after which the fraction of queries with >= MAX_PACKET candidates is
    # stably above 0 — computed on the unlock-universe candidate scope.
    ordered = sorted(
        ((closed_at(by_id[did]["_index"]), did, per_query_cands[did])
         for did, _, _ in slice_))
    burn_in = 0
    for i, (_, did, n) in enumerate(ordered):
        if n >= args.max_packet:
            burn_in = i
            break

    audit = {
        "run_id": Path(args.out).parent.name,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "computed_on": {
            "gold": "data/gold_useful.jsonl (canonical, main @ 03121f2, sign-off #60)",
            "gold_rows": n_gold_rows,
            "gold_non_empty": n_non_empty,
            "gold_pairs": n_pairs_total,
        },
        "A1": {
            "question": "share of slice queries with >=1 useful session strictly earlier (oracle ceiling B3)",
            "value": round(a1, 4),
            "n": f"{n_non_empty}/{n_gold_rows}",
            "gate": ">= 0.30 for hit to be about the ranker",
            "verdict": "OK" if a1 >= 0.30 else "LOW",
        },
        "A2": {
            "question": "share of gold pairs splitting < TAG_FIELDS_MIN under gold tags",
            "value": "N/A (gold_tags not authorized — ROUND-0-PLAN §8)",
            "proxy_unlock_universe": {
                "useful_pairs": n_pairs,
                "useful_ids_outside_same_unlock_scope": useful_outside,
            },
        },
        "A3": {
            "question": "unique tag_key count + median bucket size on gold_tags",
            "value": "N/A (gold_tags not authorized)",
            "proxy_raw_unlock": {
                "unique_unlock_buckets": len(unlock_counts),
                "median_bucket": med_bucket,
            },
        },
        "A4": {
            "question": "share of slice queries with > MAX_PACKET candidates (gold tags)",
            "value": "N/A (gold_tags not authorized); proxy below on the unlock-universe",
            "proxy_unlock_universe": round(a4, 4),
            "n": f"{gt_max}/{len(slice_)}",
            "note": "tag-based candidate counts land in metrics.json.retrieve from the run; "
                    "explore_fill gate is about tag candidates",
        },
        "A5": {
            "question": "gold coverage (rows / non-empty / pairs)",
            "value": f"{n_gold_rows} rows / {n_non_empty} non-empty / {n_pairs_total} pairs",
            "publishable_l2": a5_publishable,
            "gate": ">= 40 pairs to publish L2 usefulness",
            "verdict": "OK" if a5_publishable else "NOT PUBLISHABLE",
        },
        "A6": {
            "question": "median transcript tokens x MAX_PACKET (honest packet_tokens_p50 ceiling)",
            "method": "len(text)//4 on pool-union transcripts (fallback per EVAL-PLAN §4.6)",
            "median_transcript_tokens": median_tokens,
            "max_packet": args.max_packet,
            "value": a6,
            "flag_1500": a6 > 1500,
        },
        "ROTATION_BURN_IN": {
            "question": "first query index after which share of queries with >= MAX_PACKET candidates is stably > 0",
            "value": burn_in,
            "basis": "unlock-universe candidate scope (no tag model needed)",
        },
        "pool_union": len(pool_union_ids),
        "slice": {"n": len(slice_), "howto": sum(1 for _, f, _ in slice_ if f == "howto"),
                  "site": sum(1 for _, f, _ in slice_ if f == "site"),
                  "negative": sum(1 for _, f, _ in slice_ if f in ("negative", "negative_manage"))},
    }
    common.write_json(args.out, audit)
    common.print_summary({"ok": True, "step": "audit", "script": "audit.py",
                          "out": args.out, "sha256": common.sha256_of(args.out),
                          "A1": audit["A1"]["value"], "A4_proxy": a4,
                          "A5_pairs": n_pairs_total, "A6": a6,
                          "ROTATION_BURN_IN": burn_in, "pool_union": len(pool_union_ids)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
