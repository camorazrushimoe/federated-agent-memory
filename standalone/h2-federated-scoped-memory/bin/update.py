"""S7 — update.py: move ratings of the sessions that actually went into the packet.

- input:  --outcome data/outcomes.jsonl --ratings data/ratings.jsonl
- output: updated data/ratings.jsonl
- prompt: none.
- deltas ONLY for pairs (session_id from the packet, tag_key of the query):
  shows += 1, last_shown_at = outcome.closed_at, good|bad|unclear += 1,
  score += GOOD_DELTA|BAD_DELTA|UNCLEAR_DELTA (C-DELTA, C-UP1, C-UP2)
- after the delta: if shows % DECAY_EVERY_SHOWS == 0 then score -= DECAY_AMOUNT
  (C-UP3)
- sessions not in the packet get neither delta nor decay; untouched rating
  lines are rewritten byte-for-byte (C-UP4)
- idempotent per query_id (C-UP5): applied query_ids are remembered in
  data/update_state.json; a second run over the same outcomes.jsonl applies
  nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402

DELTA = {"good": config.GOOD_DELTA, "bad": config.BAD_DELTA,
         "unclear": config.UNCLEAR_DELTA}
COUNTER = {"good": "good", "bad": "bad", "unclear": "unclear"}


def _rating_row(session_id: str, tag_key: str) -> dict:
    return {
        "session_id": session_id,
        "tag_key": tag_key,
        "score": 0.0,
        "shows": 0,
        "good": 0,
        "bad": 0,
        "unclear": 0,
        "last_shown_at": None,
    }


def apply_outcome(row: dict, ratings: dict) -> int:
    """Apply one outcome row to the rating map. Returns number of touched pairs."""
    packet_ids = row.get("packet_session_ids") or []
    tag_key = row["tag_key"]
    outcome = row["outcome"]
    closed_at = row.get("closed_at")
    touched = 0
    for sid in packet_ids:
        pair = (sid, tag_key)
        r = ratings.get(pair)
        if r is None:
            r = _rating_row(sid, tag_key)
            ratings[pair] = r
        r["shows"] = int(r.get("shows") or 0) + 1
        r["last_shown_at"] = closed_at
        r[COUNTER[outcome]] = int(r.get(COUNTER[outcome]) or 0) + 1
        r["score"] = round(float(r.get("score") or 0.0) + DELTA[outcome], 6)
        if r["shows"] % config.DECAY_EVERY_SHOWS == 0:  # after the delta
            r["score"] = round(r["score"] - config.DECAY_AMOUNT, 6)
        touched += 1
    return touched


def main() -> int:
    ap = argparse.ArgumentParser(description="S7 update: rating deltas for the packet")
    ap.add_argument("--outcome", default=config.DEFAULT_PATHS["outcomes"])
    ap.add_argument("--ratings", default=config.DEFAULT_PATHS["ratings"])
    ap.add_argument("--state", default=config.DEFAULT_PATHS["update_state"])
    args = ap.parse_args()

    state_path = Path(args.state)
    applied = set()
    if state_path.exists():
        applied = set(common.read_json(state_path).get("applied_query_ids") or [])

    # Preserve untouched lines byte-for-byte (C-UP4).
    lines = []
    if Path(args.ratings).exists():
        for ln in Path(args.ratings).read_text(encoding="utf-8").splitlines():
            if ln.strip():
                lines.append(ln)
    ratings = {}
    for ln in lines:
        row = json.loads(ln)
        ratings[(row["session_id"], row["tag_key"])] = row

    outcome_rows = common.read_jsonl(args.outcome)
    applied_now, touched = [], 0
    for row in outcome_rows:
        qid = row.get("query_id")
        if qid in applied:
            continue
        if row.get("outcome") not in DELTA:
            return common.fail(f"bad outcome in {args.outcome}: {row.get('outcome')!r}")
        touched += apply_outcome(row, ratings)
        applied_now.append(qid)
        applied.add(qid)

    out_path = Path(args.ratings)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written_pairs = set()
    with out_path.open("w", encoding="utf-8") as f:
        for ln in lines:
            row = json.loads(ln)
            pair = (row["session_id"], row["tag_key"])
            current = ratings[pair]
            f.write((_serialized(current) if _serialized(current) != ln
                     else ln) + "\n")
            written_pairs.add(pair)
        for pair, r in ratings.items():  # brand-new pairs created by the deltas
            if pair not in written_pairs:
                f.write(_serialized(r) + "\n")

    common.write_json(state_path, {"applied_query_ids": sorted(applied)})
    common.print_summary({
        "ok": True,
        "step": "S7",
        "script": "update.py",
        "outcome_rows": len(outcome_rows),
        "applied": len(applied_now),
        "skipped_already_applied": len(outcome_rows) - len(applied_now),
        "touched_pairs": touched,
        "out": args.ratings,
        "ratings_rows": len(ratings),
        "sha256": common.sha256_of(args.ratings),
    })
    return 0


def _serialized(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
