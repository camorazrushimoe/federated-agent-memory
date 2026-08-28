#!/usr/bin/env python3
"""feedback.py — human feedback on a served packet (SPEC §6.7).

    python bin/feedback.py --card-id c-001 --label helpful|wrong|stale \\
        --dialogue d-099 [--cards data/cards.jsonl] \\
        [--feedback data/feedback.jsonl] [--now ISO]

- Appends one row {dialogue_id, card_id, label, at} to feedback.jsonl
  (append only).
- wrong / stale → flip that card's CANONICAL to stale (members stay merged;
  if the cited id is a member, its canonical is resolved via cluster_id).
  helpful → no status change.
- --card-id is always required here: a packet always cites card ids, so the
  C-FB4 rule ("required when the packet had >1 card") is subsumed.

Prints {dialogue_id, card_id, label, at, status_after}.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import os
import sys

import jsonio as hio
from common import now_iso


def run_feedback(cards_path, feedback_path, dialogue_id, card_id, label,
                 pinned_now=None):
    if pinned_now is None:
        pinned_now = now_iso()
    if label not in ("helpful", "wrong", "stale"):
        raise ValueError(f"label must be helpful|wrong|stale, got {label!r}")

    status_after = None
    if label in ("wrong", "stale"):
        store = {}
        if os.path.exists(cards_path):
            for c in hio.read_jsonl(cards_path):
                store[c["card_id"]] = c
        if card_id not in store:
            raise ValueError(f"unknown card_id {card_id!r}")
        card = store[card_id]
        # resolve the cited id to its canonical (members stay merged, C-FB1)
        canonical = store.get(card.get("cluster_id"), card)
        if canonical.get("role") != "canonical":
            canonical = card
        canonical["status"] = "stale"
        canonical["updated_at"] = pinned_now
        status_after = "stale"
        ordered = [store[k] for k in sorted(store)]
        hio.write_jsonl(cards_path, ordered)

    row = {"dialogue_id": dialogue_id, "card_id": card_id, "label": label,
           "at": pinned_now}
    os.makedirs(os.path.dirname(feedback_path) or ".", exist_ok=True)
    with open(feedback_path, "a", encoding="utf-8") as fh:
        fh.write(hio.dumps(row) + "\n")

    return {"dialogue_id": dialogue_id, "card_id": card_id, "label": label,
            "at": pinned_now, "status_after": status_after}


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="feedback.py",
        description="Record human feedback on a served card (SPEC §6.7).")
    ap.add_argument("--card-id", dest="card_id", required=True)
    ap.add_argument("--label", choices=("helpful", "wrong", "stale"),
                    required=True)
    ap.add_argument("--dialogue", dest="dialogue_id", required=True)
    ap.add_argument("--cards", dest="cards_path", default="data/cards.jsonl")
    ap.add_argument("--feedback", dest="feedback_path",
                    default="data/feedback.jsonl")
    ap.add_argument("--now", default=None)
    args = ap.parse_args(argv)

    summary = run_feedback(args.cards_path, args.feedback_path,
                           args.dialogue_id, args.card_id, args.label,
                           args.now)
    print(hio.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
