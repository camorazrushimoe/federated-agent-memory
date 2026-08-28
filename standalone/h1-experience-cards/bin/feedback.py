#!/usr/bin/env python3
"""feedback.py — record feedback; wrong/stale expires the cited card (SPEC §6.7).

Usage:
  python bin/feedback.py --card-id c-001 --label wrong --dialogue d-099
  python bin/feedback.py --label helpful --dialogue d-099 \
      --packet-card-ids c-001   # one-card packet: --card-id optional

Appends one row {card_id, label, dialogue_id, at} to data/feedback.jsonl.
wrong/stale flips exactly the cited canonical card to stale (members stay
merged, C-FB1). helpful changes no status (C-FB2). --card-id is REQUIRED when
the packet held more than one card (C-FB4). A stale card is never served again
in the same run (C-FB3).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402

LABELS = ("helpful", "wrong", "stale")


def main():
    ap = argparse.ArgumentParser(description="Record feedback (SPEC §6.7)")
    ap.add_argument("--card-id", default=None)
    ap.add_argument("--label", required=True, choices=LABELS)
    ap.add_argument("--dialogue", required=True)
    ap.add_argument("--at", default=None)
    ap.add_argument("--cards", default=None,
                    help="card store to mutate (required for wrong/stale)")
    ap.add_argument("--feedback-file", default=None)
    ap.add_argument("--packet-card-ids", default=None,
                    help="comma-separated card ids the packet held — used to "
                         "enforce C-FB4 (--card-id required when >1 card)")
    args = ap.parse_args()

    cfg = H.load_config([])
    at = args.at or H.now_iso(cfg)

    packet_ids = [x.strip() for x in args.packet_card_ids.split(",")] if (
        args.packet_card_ids) else []
    card_id = args.card_id
    if not card_id and len(packet_ids) == 1:
        card_id = packet_ids[0]
    if not card_id:
        raise SystemExit(
            "feedback: --card-id is required when the packet held more than "
            "one card (C-FB4), and this call did not name one")

    feedback_file = args.feedback_file or os.path.join(
        os.path.dirname(os.path.abspath(args.cards or ".")),
        "feedback.jsonl")
    # validate before mutating anything: the feedback row is appended only
    # when the citation is resolvable (no row-then-error edge)
    status_after = "unchanged"
    target = None
    cards = []
    if args.label in ("wrong", "stale"):
        if not args.cards or not os.path.exists(args.cards):
            raise SystemExit("feedback: --cards required for wrong/stale")
        cards = H.read_jsonl(args.cards)
        target = None
        for c in cards:
            if c["card_id"] == card_id:
                target = c
                break
        if target is None:
            raise SystemExit(f"feedback: unknown card {card_id}")
        if target["role"] != "canonical":
            raise SystemExit(
                f"feedback: {card_id} is not canonical (members are never "
                f"served, so they cannot be cited)")

    row = {"card_id": card_id, "label": args.label,
           "dialogue_id": args.dialogue, "at": at}
    rows = H.read_jsonl(feedback_file)
    rows.append(row)
    H.write_jsonl(feedback_file, rows, mode="w")

    if args.label in ("wrong", "stale"):
        assert target is not None  # validated above; SystemExit otherwise
        if target["status"] != "stale":
            target["status"] = "stale"
            status_after = "stale"
        H.write_jsonl(args.cards, cards, mode="w")

    H.print_json({"applied": True, "card_id": card_id,
                  "status_after": status_after})


if __name__ == "__main__":
    main()
