#!/usr/bin/env python3
"""promote.py — the vote→status + age-stale tail of cluster.py, WITHOUT
rebuilding clusters (SPEC §6.5, C-PR1).

    python bin/promote.py --cards data/cards.jsonl --dialogues data/dialogues.jsonl \\
        --now ISO

For each canonical card with status ∈ {private, shared}: recompute votes per
SPEC §5.1 from the EXISTING cluster membership, set shared iff
votes >= K_INDEPENDENT (and not stale), set stale iff the age rule fires.
NEVER writes cluster_id / members / votes — status changes only.

Prints {promoted, already_shared, stale}.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import os
import sys

import config as cfg
import jsonio as hio
from cluster import (_dialogue_lookup, _sort_key, compute_last_closed_at,
                     compute_votes)
from common import days_since


def run_promote(cards_path, dialogues_path, pinned_now, overrides=None):
    cfg_obj = cfg.Config(overrides)
    if pinned_now is None:
        raise ValueError("promote.py requires --now (pinned determinism)")

    store = {}
    if os.path.exists(cards_path):
        for c in hio.read_jsonl(cards_path):
            store[c["card_id"]] = c
    dialogues = _dialogue_lookup(dialogues_path)

    promoted = 0
    already_shared = 0
    stale = 0

    for card in store.values():
        if card.get("role") != "canonical":
            continue
        if card.get("status") not in ("private", "shared"):
            continue
        members = [store[mid] for mid in card.get("members", [])
                   if mid in store]
        lca = compute_last_closed_at(card, members, dialogues)
        if lca is not None:
            card["receipt"]["last_closed_at"] = lca
        votes, _mode = compute_votes(card, members, dialogues)
        stale_now = False
        if lca is not None:
            d = days_since(pinned_now, lca)
            if d is not None and d > cfg_obj.STALE_AFTER_DAYS:
                stale_now = True
        prev = card.get("status")
        if stale_now:
            card["status"] = "stale"
            if prev != "stale":
                stale += 1
        elif votes >= cfg_obj.K_INDEPENDENT:
            if prev == "shared":
                already_shared += 1
            else:
                promoted += 1
            card["status"] = "shared"
        else:
            card["status"] = "private"
        card["updated_at"] = pinned_now

    ordered = [store[k] for k in sorted(store)]
    hio.write_jsonl(cards_path, ordered)
    return {"promoted": promoted, "already_shared": already_shared,
            "stale": stale}


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="promote.py",
        description="Vote → status + age-stale tail of cluster.py (SPEC §6.5).")
    ap.add_argument("--cards", dest="cards_path", required=True)
    ap.add_argument("--dialogues", dest="dialogues_path", required=True)
    ap.add_argument("--now", default=None,
                    help="pinned ISO timestamp (required; brief §6)")
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    summary = run_promote(args.cards_path, args.dialogues_path, args.now,
                          cfg.parse_overrides(args.set))
    print(hio.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
