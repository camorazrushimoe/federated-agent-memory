"""S6 — outcome.py: label how the query ended after the packet.

- input:  --query ... --packet data/packet.json
- output: one row in data/outcomes.jsonl (upsert by query_id)
- prompt: none for --source gold|rule and for manual --outcome. The LLM helper
  (PROMPTS.md §6) is only for --source llm, which is NOT part of this pass:
  the flag exists but errors out (brief: "not in this pass").
- gold mapping (C-OC2): packet ∩ useful_dialogue_ids non-empty -> good;
  packet non-empty and intersection empty -> bad; empty packet -> unclear
- outcome ∈ {good, bad, unclear} (C-OC3); row carries query_id,
  packet_session_ids, tag_key, outcome, source, closed_at (C-OC4)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402

OUTCOMES = {"good", "bad", "unclear"}


def main() -> int:
    ap = argparse.ArgumentParser(description="S6 outcome: gold/manual label (C-OC2)")
    ap.add_argument("--query", required=True)
    ap.add_argument("--packet", default=config.DEFAULT_PATHS["packet"])
    ap.add_argument("--source", choices=["gold", "rule", "llm", "manual"],
                    default="gold")
    ap.add_argument("--gold", default=None, help="gold_useful.jsonl for --source gold")
    ap.add_argument("--pool", default=config.DEFAULT_PATHS["sessions"],
                    help="session -> dialogue_id mapping + query tag_key")
    ap.add_argument("--meta", default=config.DEFAULT_PATHS["query_meta"])
    ap.add_argument("--outcome", default=None, choices=sorted(OUTCOMES),
                    help="manual label for --source manual|rule")
    ap.add_argument("--out", default=config.DEFAULT_PATHS["outcomes"])
    args = ap.parse_args()

    if args.source == "llm":
        return common.fail(
            "--source llm is not in this pass: the lab run uses gold "
            "(C-OC1). The prompt exists in prompts.py for a later pass.")

    query = common.read_json(args.query)
    packet = common.read_json(args.packet)
    query_id = query.get("dialogue_id") or query.get("source_dialogue_id")
    closed_at = query.get("closed_at") or ""
    packet_ids = list(packet.get("packet_session_ids") or [])

    # tag_key of the query: from the pool session, else query_meta, else query.
    pool = common.read_jsonl(args.pool)
    tag_key = None
    for s in pool:
        if s.get("source_dialogue_id") == query_id:
            tag_key = s.get("tag_key")
            break
    if not tag_key:
        try:
            tag_key = common.read_json(args.meta)["tag_key"]
        except Exception:
            pass
    if not tag_key and isinstance(query.get("tags"), dict):
        tag_key = query.get("tag_key")
    if not tag_key:
        return common.fail(f"query {query_id} has no tag_key (not tagged?)")

    if args.source in ("manual", "rule"):
        outcome = args.outcome
        useful = []
        if outcome is None:
            return common.fail(f"--source {args.source} requires --outcome")
    else:  # gold
        if not args.gold:
            return common.fail("--source gold requires --gold gold_useful.jsonl")
        useful = []
        for row in common.read_jsonl(args.gold):
            if row.get("query_id") == query_id:
                useful = list(row.get("useful_dialogue_ids") or [])
                break
        # map packet session ids -> source dialogue ids
        by_session = {s["session_id"]: s.get("source_dialogue_id")
                      for s in pool}
        packet_dialogue_ids = [by_session.get(sid) for sid in packet_ids]
        packet_dialogue_ids = [d for d in packet_dialogue_ids if d]
        hit = [d for d in packet_dialogue_ids if d in useful]
        if not packet_ids:
            outcome = "unclear"          # empty packet (C-OC2)
        elif hit:
            outcome = "good"
        else:
            outcome = "bad"

    row = {
        "query_id": query_id,
        "packet_session_ids": packet_ids,
        "tag_key": tag_key,
        "outcome": outcome,
        "source": args.source,
        "closed_at": closed_at,
    }

    # upsert by query_id (idempotent; never append-duplicates)
    rows = common.read_jsonl(args.out)
    rows = [r for r in rows if r.get("query_id") != query_id]
    rows.append(row)
    common.write_jsonl(args.out, rows)

    common.print_summary({
        "ok": True,
        "step": "S6",
        "script": "outcome.py",
        "query_id": query_id,
        "packet_session_ids": packet_ids,
        "useful_dialogue_ids": useful if args.source == "gold" else None,
        "outcome": outcome,
        "source": args.source,
        "closed_at": closed_at,
        "tag_key": tag_key,
        "out": args.out,
        "outcome_rows": len(rows),
        "sha256": common.sha256_of(args.out),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
