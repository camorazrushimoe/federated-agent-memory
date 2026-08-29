"""D4 — eval.py: the ONE scoring function for Phase C (EVAL-PLAN §10).

Single classifier used by EVERY arm (T, B0, B1, B2, B3) — the same code
that the runner imports, so baselines are counted by the same rule as the
treatment (EVAL-PLAN §4.3 / §10). Plus the aggregation into metrics.json.

classify(packet_session_ids, useful_dialogue_ids, pool) -> "hit"|"wrong"|"abstain"
  mirrors outcome.py --source gold (C-OC2):
  - empty packet                     -> abstain
  - packet ∩ useful (by dialogue id) -> hit
  - non-empty, no useful             -> wrong
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402

CLASSES = ("hit", "wrong", "abstain")


def classify(packet_session_ids: list, useful_dialogue_ids: list,
             pool: list[dict]) -> str:
    """EVAL-PLAN §4.2 class for one (query, arm) packet. ONE rule for all arms."""
    if not packet_session_ids:
        return "abstain"
    by_session = {s["session_id"]: s.get("source_dialogue_id") for s in pool}
    packet_dialogue_ids = [by_session.get(sid) for sid in packet_session_ids]
    packet_dialogue_ids = [d for d in packet_dialogue_ids if d]
    if any(d in useful_dialogue_ids for d in packet_dialogue_ids):
        return "hit"
    return "wrong"


def outcome_of(cls: str) -> str:
    """Lab outcome for S7 (EVAL-PLAN §4.2): hit->good, wrong->bad, abstain->unclear."""
    return {"hit": "good", "wrong": "bad", "abstain": "unclear"}[cls]


def aggregate(per_query: list[dict]) -> dict:
    """metrics.json arms table from per_query rows (EVAL-PLAN §10 schema).

    per_query rows carry: query_id, arm, class, packet_session_ids.
    Sums per arm MUST hit + wrong + abstain == n_queries (hard gate §6.1).
    """
    n = len({r["query_id"] for r in per_query})
    arms = {a: {"hit": 0, "wrong": 0, "abstain": 0} for a in ("T", "B0", "B1", "B2", "B3")}
    for r in per_query:
        cls = r["class"]
        if cls not in CLASSES:
            raise ValueError(f"bad class {cls!r}")
        arms[r["arm"]][cls] += 1
    for a in arms:
        total = sum(arms[a].values())
        if total != n:
            raise ValueError(f"arm {a}: classes sum {total} != n_queries {n}")
    return {"n_queries": n, "arms": arms}


def main() -> int:
    ap = argparse = __import__("argparse")
    p = ap.ArgumentParser(description="D4 eval: score a Phase C run dir")
    p.add_argument("--per-query", required=True, help="run dir per_query.jsonl")
    p.add_argument("--out", required=True, help="metrics.json output path")
    args = p.parse_args()

    rows = common.read_jsonl(args.per_query)
    metrics = aggregate(rows)
    common.write_json(args.out, metrics)
    common.print_summary({"ok": True, "step": "eval", "script": "eval.py",
                          "n_queries": metrics["n_queries"],
                          "arms": metrics["arms"], "out": args.out})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
