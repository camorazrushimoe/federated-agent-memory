"""S4 — rank.py: order candidates and fill the exploration slot.

- input:  --candidates data/candidates.jsonl --ratings data/ratings.jsonl
          --tag-key <tag_key of the query> (fallback: data/query_meta.json)
- output: data/ranked.jsonl
- prompt: none. Deterministic (C-RK5).
- rating for the pair (session_id, tag_key query); missing row -> score=0,
  shows=0 (SPEC §7 S4)
- first MAX_PACKET - EXPLORE_SLOTS slots: highest score (C-RK1). Ties are
  broken deterministically by (shows asc, last_shown_at asc, session_id asc)
  — same tuple as the explore slot, so a re-run is byte-identical.
- last slot: exploration from the remaining candidates (C-RK2): fewest shows,
  then oldest last_shown_at (null is oldest), then smallest session_id.
- exploration MUST NOT duplicate an already-selected id (C-RK3).
- if candidates <= MAX_PACKET the packet is just all candidates sorted by
  score (C-RK6, soft).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402


def _sort_key(item: tuple) -> tuple:
    """(score desc, shows asc, last_shown_at asc with None oldest, id asc)."""
    sid, score, shows, last_shown_at = item
    return (-score, shows, last_shown_at is not None, last_shown_at or "", sid)


def rank_candidates(candidates: list[dict], ratings: list[dict],
                    tag_key: str) -> list[dict]:
    rating_by_pair = {(r["session_id"], r["tag_key"]): r for r in ratings}
    scored = []
    for c in candidates:
        r = rating_by_pair.get((c["session_id"], tag_key))
        if r is None:
            scored.append((c["session_id"], 0.0, 0, None))
        else:
            scored.append((c["session_id"], float(r.get("score") or 0.0),
                           int(r.get("shows") or 0), r.get("last_shown_at")))
    ordered = sorted(scored, key=_sort_key)
    by_id = {c["session_id"]: c for c in candidates}

    if len(ordered) <= config.MAX_PACKET:
        return [by_id[sid] for sid, *_ in ordered]  # C-RK6

    top = ordered[: config.MAX_PACKET - config.EXPLORE_SLOTS]
    top_ids = {sid for sid, *_ in top}
    rest = [t for t in ordered if t[0] not in top_ids]
    explore = sorted(rest, key=lambda t: (t[2], t[3] is not None, t[3] or "", t[0]))
    explore = explore[: config.EXPLORE_SLOTS]  # C-RK3: ids disjoint from top
    ranked_ids = [t[0] for t in top] + [t[0] for t in explore]
    return [by_id[sid] for sid in ranked_ids]


def main() -> int:
    ap = argparse.ArgumentParser(description="S4 rank: score order + explore slot")
    ap.add_argument("--candidates", default=config.DEFAULT_PATHS["candidates"])
    ap.add_argument("--ratings", default=config.DEFAULT_PATHS["ratings"])
    ap.add_argument("--tag-key", default=None,
                    help="default: read data/query_meta.json")
    ap.add_argument("--meta", default=config.DEFAULT_PATHS["query_meta"])
    ap.add_argument("--out", default=config.DEFAULT_PATHS["ranked"])
    args = ap.parse_args()

    candidates = common.read_jsonl(args.candidates)
    ratings = common.read_jsonl(args.ratings)
    tag_key = args.tag_key
    if not tag_key:
        meta = common.read_json(args.meta)
        tag_key = meta["tag_key"]

    ranked = rank_candidates(candidates, ratings, tag_key)
    common.write_jsonl(args.out, ranked)
    n_top = config.MAX_PACKET - config.EXPLORE_SLOTS
    common.print_summary({
        "ok": True,
        "step": "S4",
        "script": "rank.py",
        "tag_key": tag_key,
        "candidates": len(candidates),
        "ranked": len(ranked),
        "ranked_ids": [s["session_id"] for s in ranked],
        "top_slots": [s["session_id"] for s in ranked[:n_top]],
        "explore_slot": (ranked[n_top]["session_id"]
                         if len(ranked) > n_top else None),
        "out": args.out,
        "sha256": common.sha256_of(args.out),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
