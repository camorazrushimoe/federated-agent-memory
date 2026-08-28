#!/usr/bin/env python3
"""feedback.py — record feedback on a served card (SPEC §6.7).

    python bin/feedback.py --card-id c-001 --label helpful|wrong|stale --dialogue d-099

- appends one row to data/feedback.jsonl: {card_id, label, dialogue_id, at}
- label wrong|stale flips the cited CANONICAL card to stale (members stay
  merged; no other card changes — C-FB1)
- label helpful changes no status (C-FB2)
- --card-id is required when the serving dialogue appears in more than one
  card's served_to (no ambiguous attribution — C-FB4)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from clock import RunClock
from store import read_jsonl, write_jsonl

LABELS = ("helpful", "wrong", "stale")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Record packet feedback (SPEC §6.7).")
    ap.add_argument("--card-id", default=None, help="cited card (required if the packet had >1 card)")
    ap.add_argument("--label", required=True, choices=LABELS)
    ap.add_argument("--dialogue", required=True)
    ap.add_argument("--cards", required=True, help="cards.jsonl (flip status in place)")
    ap.add_argument("--feedback-out", default="data/feedback.jsonl")
    ap.add_argument("--clock-start", default=None)
    args = ap.parse_args(argv)

    clock = RunClock(args.clock_start) if args.clock_start else RunClock(cfgmod.utcnow_iso())
    cards = read_jsonl(args.cards)

    # C-FB4: ambiguous attribution guard
    if not args.card_id:
        served_dialogue_count = sum(
            1 for c in cards
            if any(s.get("dialogue_id") == args.dialogue for s in c.get("served_to", [])))
        if served_dialogue_count > 1:
            print(json.dumps({"error": "ambiguous attribution: --card-id required "
                                       f"({served_dialogue_count} cards served to {args.dialogue})"}))
            return 2

    if args.card_id:
        target = next((c for c in cards if c["card_id"] == args.card_id), None)
        if target is None:
            print(json.dumps({"error": f"unknown card_id {args.card_id}"}))
            return 2
        # flip the canonical of the cluster the cited card belongs to
        if target.get("role") == "member" and target.get("cluster_id"):
            canonical_id = target["cluster_id"]
        else:
            canonical_id = target["card_id"]
        if args.label in ("wrong", "stale"):
            for c in cards:
                if c["card_id"] == canonical_id and c["role"] == "canonical":
                    c["status"] = "stale"
                    break
        write_jsonl(args.cards, cards)

    row = {"card_id": args.card_id, "label": args.label,
           "dialogue_id": args.dialogue, "at": clock.now()}
    fb_path = Path(args.feedback_out)
    rows = read_jsonl(fb_path) + [row]
    write_jsonl(fb_path, rows)

    print(json.dumps({"appended": row, "cards_flipped": 1 if args.label in ("wrong", "stale") else 0}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
