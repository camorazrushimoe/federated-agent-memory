#!/usr/bin/env python3
"""Oracle D4: MAP.md unlock → problem_shape. Zero LLM."""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "runs" / "2026-08-29_oracle_D4"

MAP = {
    "boots_how_1": "stain_paint",
    "boots_how_2": "fit_width",
    "boots_how_3": "stain_gum",
    "boots_how_4": "break_in",
    "jacket_how_1": "stain_wine",
    "jacket_how_2": "wash_low_heat",
    "jacket_how_3": "wash_jacket",
    "jacket_how_4": "product_spec",
    "jeans_how_1": "stain_grass",
    "jeans_how_2": "wash_frequency",
    "jeans_how_3": "fit_inseam",
    "jeans_how_4": "tailoring",
    "shirt_how_1": "stain_food",
    "shirt_how_2": "wash_color_guard",
    "shirt_how_3": "fit_sleeve",
    "shirt_how_4": "fit_collar",
    "shopping_cart": "cart_not_updating",
    "slow_speed": "site_slow",
    "search_results": "search_broken",
    "bad_price_competitor": "price_competitor",
    "bad_price_yesterday": "price_changed",
    "promo_code_out_of_date": "promo_expired",
    "promo_code_invalid": "promo_invalid",
    "refund_initiate": "refund_process",
    "manage_change_phone": "change_phone",
    "manage_change_address": "change_address",
    "manage_change_name": "change_name",
    "manage_cancel": "cancel_order",
    "manage_dispute_bill": "dispute_bill",
    "manage_downgrade": "subscription_change",
}


def read_gold(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            rows.append(json.loads(s))
    return rows


def shape_of(row: dict) -> str:
    unlock = row.get("unlock") or row.get("unlock_guideline") or ""
    return MAP.get(unlock, "other")


def main() -> int:
    pool_path = ROOT / "data" / "dialogues_pool.jsonl"
    slice_path = ROOT / "data" / "d0_slice.jsonl"
    gold_path = ROOT / "data" / "gold_useful.jsonl"
    if not pool_path.exists():
        raise SystemExit("need data/dialogues_pool.jsonl (bin/sync_h1_data.sh + adapt)")
    pool_raw = common.read_jsonl(pool_path)
    queries = read_gold(slice_path)
    gold = {r["query_id"]: list(r.get("useful_dialogue_ids") or [])
            for r in read_gold(gold_path)}

    pool = []
    for d in pool_raw:
        did = d.get("dialogue_id") or d.get("source_dialogue_id")
        pool.append({
            "id": did,
            "unlock": d.get("unlock") or d.get("unlock_guideline") or "",
            "shape": shape_of(d),
            "closed_at": d.get("closed_at") or "",
        })
    shapes = Counter(p["shape"] for p in pool)
    used = [k for k in shapes if k != "other"]
    other_share = shapes.get("other", 0) / max(len(pool), 1)
    top1_id, top1_n = shapes.most_common(1)[0]

    n_cands, per_query = [], []
    gold_pairs = retrieved_useful = empty_q = 0
    precisions = []
    for q in queries:
        qid = q["query_id"]
        qshape = shape_of(q) if q.get("unlock") or q.get("unlock_guideline") else None
        if not qshape:
            qshape = next((p["shape"] for p in pool if p["id"] == qid), "other")
            qunlock = next((p["unlock"] for p in pool if p["id"] == qid), "")
        else:
            qunlock = q.get("unlock") or q.get("unlock_guideline") or ""
        qclosed = q.get("closed_at") or ""
        useful = set(gold.get(qid) or [])
        cands = []
        for p in pool:
            if p["id"] == qid:
                continue
            if p["closed_at"] and qclosed and p["closed_at"] >= qclosed:
                continue
            if p["shape"] == qshape:
                cands.append(p)
        n = len(cands)
        n_cands.append(n)
        if n == 0:
            empty_q += 1
        cand_ids = {c["id"] for c in cands}
        gold_pairs += len(useful)
        retrieved_useful += len(useful & cand_ids)
        rec = (len(useful & cand_ids) / len(useful)) if useful else 1.0
        prec = (len(useful & cand_ids) / n) if n else 0.0
        precisions.append(prec)
        per_query.append({
            "query_id": qid, "unlock": qunlock, "shape": qshape,
            "n_candidates": n, "n_useful": len(useful),
            "retrieved_useful": len(useful & cand_ids),
            "recall": rec, "precision": prec,
        })

    nq = len(queries)
    med = statistics.median(n_cands) if n_cands else 0
    recall = retrieved_useful / gold_pairs if gold_pairs else 0.0
    gates = {
        "used_ids": len(used),
        "used_ids_ok": 24 <= len(used) <= 32,
        "other_share": other_share,
        "other_ok": other_share < 0.10,
        "top1_id": top1_id,
        "top1_share": top1_n / max(len(pool), 1),
        "top1_ok": (top1_n / max(len(pool), 1)) < 0.20,
        "median_n_candidates": med,
        "median_ok": 8 <= med <= 20,
        "empty_query_share": empty_q / nq if nq else 0,
        "empty_ok": (empty_q / nq) < 0.15 if nq else False,
        "retrieve_recall": recall,
        "recall_ok": recall >= 0.70,
    }
    gates["D4"] = all(gates[k] for k in (
        "used_ids_ok", "other_ok", "top1_ok", "median_ok", "empty_ok", "recall_ok"))
    nonempty = [p for p in per_query if p["n_useful"]]
    out = {
        "mode": "oracle-unlock-map",
        "note": "NOT live S2. Ceiling if tagger recovers MAP.md from transcript.",
        "pool_n": len(pool),
        "query_n": nq,
        "gold_pairs": gold_pairs,
        "pool_shape_counts": dict(shapes),
        "gates": gates,
        "precision_pairs": retrieved_useful / max(sum(p["n_candidates"] for p in per_query), 1),
        "query_mean_precision": sum(precisions) / nq if nq else 0,
        "query_mean_precision_nonempty_gold": (
            sum(p["precision"] for p in nonempty) / len(nonempty) if nonempty else 0
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metrics.json").write_text(json.dumps(out, indent=2) + "\n")
    common.write_jsonl(OUT / "per_query.jsonl", per_query)
    print(json.dumps({"D4": gates["D4"], "gates": gates}, indent=2))
    return 0 if gates["D4"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
