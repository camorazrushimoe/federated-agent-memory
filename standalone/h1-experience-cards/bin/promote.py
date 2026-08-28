#!/usr/bin/env python3
"""promote.py — the vote -> status + age-stale tail of cluster.py (SPEC §6.5).

Usage:
  python bin/promote.py --cards data/cards.jsonl

Alias. MUST NOT rebuild clusters and MUST NOT change cluster_id, members or
votes (C-PR1) — it only rewrites `status` (shared iff votes >= K_INDEPENDENT
and not stale; stale per the age rule). Stale is absorbing (C-PR4).

Print JSON {promoted, already_shared, stale}.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402


def main():
    ap = argparse.ArgumentParser(
        description="Promote cards: vote->status tail (SPEC §6.5)")
    ap.add_argument("--cards", required=True)
    ap.add_argument("--now", default=None,
                    help="ISO 'now' for the age rule (deterministic runs)")
    ap.add_argument("--config", action="append", default=[])
    args = ap.parse_args()

    cfg = H.load_config(args.config)
    now = args.now or H.now_iso(cfg)
    cards = H.read_jsonl(args.cards)
    by_id = {c["card_id"]: c for c in cards}
    promoted = already_shared = stale = 0
    for c in cards:
        if c["role"] != "canonical":
            continue
        if c["status"] not in ("private", "shared"):
            continue
        members = [by_id[m] for m in c.get("members") or [] if m in by_id]
        new = H.apply_status(c, members, cfg, now)
        if new == c["status"]:
            if new == "shared":
                already_shared += 1
            continue
        if new == "stale":
            stale += 1
        elif new == "shared":
            promoted += 1
        c["status"] = new
    H.write_jsonl(args.cards, cards, mode="w")
    H.print_json({"promoted": promoted, "already_shared": already_shared,
                  "stale": stale})


if __name__ == "__main__":
    main()
