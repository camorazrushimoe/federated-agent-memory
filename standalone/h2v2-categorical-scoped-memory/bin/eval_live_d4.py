#!/usr/bin/env python3
"""D4 gates + T/B0-B3 on already-tagged S2 output. No new LLM calls."""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import config  # noqa: E402
import eval as ev  # noqa: E402
import mix  # noqa: E402
import rank  # noqa: E402
import retrieve  # noqa: E402
import update  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def read_gold(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            rows.append(json.loads(s))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="runs/2026-08-29_PhaseC_live_deepseek-v4-flash")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    run = Path(args.run_dir)
    if not run.is_absolute():
        run = ROOT / run

    pool = common.read_jsonl(run / "data" / "sessions.jsonl")
    queries = {s["source_dialogue_id"]: s
               for s in common.read_jsonl(run / "data" / "query_tags.jsonl")}
    if not pool:
        tags = json.loads((run / "tags_only.json").read_text())
        def row(item):
            tags_d = {"problem_shape": item["shape"], "constraint": item.get("constraint", "none"),
                      "ending": item.get("ending", "unknown")}
            return {
                "session_id": common.session_id_of(item["id"]),
                "source_dialogue_id": item["id"],
                "closed_at": item.get("closed_at") or "",
                "tags": tags_d,
                "tag_key": common.make_tag_key(tags_d),
            }
        pool = [row(x) for x in tags["pool_tags"]]
        queries = {x["id"]: row(x) for x in tags["query_tags"]}

    slice_rows = read_gold(ROOT / "data" / "d0_slice.jsonl")
    gold = {r["query_id"]: list(r.get("useful_dialogue_ids") or [])
            for r in read_gold(ROOT / "data" / "gold_useful.jsonl")}

    shapes = Counter(s["tags"]["problem_shape"] for s in pool)
    used = [k for k in shapes if k != "other"]
    other_share = shapes.get("other", 0) / max(len(pool), 1)
    top1_id, top1_n = shapes.most_common(1)[0]
    top1_share = top1_n / max(len(pool), 1)

    order = sorted(slice_rows, key=lambda q: (q.get("closed_at") or "", q["query_id"]))
    ratings_path = run / "data" / "ratings.jsonl"
    ratings = {(r["session_id"], r["tag_key"]): dict(r)
               for r in (common.read_jsonl(ratings_path) if ratings_path.exists() else [])}
    rng = random.Random(args.seed)

    n_cands, empty_q = [], 0
    gold_pairs = retrieved_useful = 0
    arms_count = {a: {"hit": 0, "wrong": 0, "abstain": 0}
                  for a in ("T", "B0", "B1", "B2", "B3")}
    per_query = []
    cost_packet_tokens = []

    for q in order:
        qid = q["query_id"]
        qs = queries[qid]
        qtags = qs["tags"]
        qkey = qs["tag_key"]
        qclosed = q.get("closed_at") or ""
        useful = gold[qid]
        candidates = []
        for s in pool:
            if s.get("source_dialogue_id") == qid:
                continue
            if s.get("closed_at") and qclosed and s["closed_at"] >= qclosed:
                continue
            if retrieve.overlap_count(qtags, s.get("tags") or {}) >= config.TAG_FIELDS_MIN:
                candidates.append(s)
        n = len(candidates)
        n_cands.append(n)
        if n == 0:
            empty_q += 1
        cand_src = {c["source_dialogue_id"] for c in candidates}
        useful_set = set(useful)
        gold_pairs += len(useful_set)
        retrieved_useful += len(useful_set & cand_src)

        ratings_list = list(ratings.values())
        cand_ids = [c["session_id"] for c in candidates]
        b1 = rng.sample(cand_ids, min(config.MAX_PACKET, len(cand_ids))) if cand_ids else []
        saved = config.EXPLORE_SLOTS
        try:
            config.EXPLORE_SLOTS = 0
            b2_ranked = rank.rank_candidates(candidates, ratings_list, qkey)
        finally:
            config.EXPLORE_SLOTS = saved
        b2 = [s["session_id"] for s in b2_ranked[: config.MAX_PACKET]]
        src_to_sid = [(s.get("source_dialogue_id"), s["session_id"]) for s in pool]
        b3 = [sid for src, sid in src_to_sid if src in useful_set][: config.MAX_PACKET]
        t_ranked = rank.rank_candidates(candidates, ratings_list, qkey)
        t = [s["session_id"] for s in t_ranked[: config.MAX_PACKET]]
        pkts = {"T": t, "B0": [], "B1": b1, "B2": b2, "B3": b3}

        by_sid = {s["session_id"]: s["source_dialogue_id"] for s in pool}
        row = {
            "query_id": qid, "tag_key": qkey, "shape": qtags.get("problem_shape"),
            "n_candidates": n, "n_useful": len(useful),
            "retrieved_useful": len(useful_set & cand_src),
        }
        for arm, ids in pkts.items():
            dids = [by_sid.get(i, i) for i in ids]
            cls = ev.classify_packet(dids, useful)
            arms_count[arm][cls] += 1
            row[f"arm_{arm}_class"] = cls
            row[f"arm_{arm}_ids"] = ids
            if arm == "T":
                ranked_for_t = [c for c in candidates if c["session_id"] in ids]
                try:
                    packet_text, _ = mix.build_packet(ranked_for_t, pool)
                    cost_packet_tokens.append(len(packet_text) // 4)
                except Exception:
                    pass
                outcome = {"hit": "good", "wrong": "bad", "abstain": "unclear"}[cls]
                update.apply_outcome({
                    "query_id": qid, "tag_key": qkey,
                    "packet_session_ids": ids, "outcome": outcome,
                    "closed_at": qclosed,
                }, ratings)
        per_query.append(row)

    nq = len(order)
    med = statistics.median(n_cands) if n_cands else 0
    recall = retrieved_useful / gold_pairs if gold_pairs else 0.0
    gates = {
        "used_ids": len(used),
        "used_ids_ok": 24 <= len(used) <= 32,
        "other_share": other_share,
        "other_ok": other_share < 0.10,
        "top1_id": top1_id,
        "top1_n": top1_n,
        "top1_share": top1_share,
        "top1_ok": top1_share < 0.20,
        "median_n_candidates": med,
        "median_ok": 8 <= med <= 20,
        "empty_query_share": empty_q / nq if nq else 0,
        "empty_ok": (empty_q / nq) < 0.15 if nq else False,
        "retrieve_recall": recall,
        "recall_ok": recall >= 0.70,
    }
    gates["D4"] = all(gates[k] for k in (
        "used_ids_ok", "other_ok", "top1_ok", "median_ok", "empty_ok", "recall_ok"))

    def verdict(arms, cost):
        hard_ok = arms["B0"]["hit"] == 0 and all(sum(a.values()) == nq for a in arms.values())
        if not hard_ok:
            return "NOT FIT (hard gate: B0.hit != 0 or classes do not sum to n)"
        if arms["T"]["hit"] <= arms["B1"]["hit"]:
            return "NOT FIT (T.hit <= B1.hit)"
        fails = []
        if arms["T"]["wrong"] > 0.25 * nq:
            fails.append(f"T.wrong {arms['T']['wrong']} > 0.25*n")
        if (cost.get("packet_tokens_p50") or 0) > 1500:
            fails.append("packet_tokens_p50 > 1500")
        return "FIT WITH LIMITS (" + "; ".join(fails) + ")" if fails else "FIT"

    cp = sorted(cost_packet_tokens)
    cost = {
        "packet_tokens_p50": cp[len(cp) // 2] if cp else None,
        "packet_tokens_p95": cp[min(len(cp) - 1, int(0.95 * len(cp)))] if cp else None,
        "packet_tokens_max": cp[-1] if cp else None,
        "tag_calls": 380,
        "model": "deepseek-v4-flash",
    }
    out = {
        "mode": "live-S2-deepseek-v4-flash",
        "pool_n": len(pool),
        "query_n": nq,
        "gold_pairs": gold_pairs,
        "pool_shape_counts": dict(shapes),
        "gates": gates,
        "arms_counts": arms_count,
        "arms_share": {a: {k: v / nq for k, v in c.items()} for a, c in arms_count.items()},
        "verdict": verdict(arms_count, cost),
        "cost": cost,
        "empty_gold_queries": sum(1 for q in slice_rows if not gold[q["query_id"]]),
    }
    run.mkdir(parents=True, exist_ok=True)
    (run / "metrics.json").write_text(json.dumps(out, indent=2) + "\n")
    common.write_jsonl(run / "per_query.jsonl", per_query)
    print(json.dumps({"D4": gates["D4"], "verdict": out["verdict"],
                      "arms": arms_count, "gates": gates}, indent=2))
    return 0 if gates["D4"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
