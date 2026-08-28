#!/usr/bin/env python3
"""promote.py — the vote->status + age-stale tail of cluster.py, without
rebuilding clusters (SPEC §6.5).

    python bin/promote.py --cards data/cards.jsonl --dialogues data/dialogues.jsonl

Alias: recomputes votes (§5.1) and status (§5) for every canonical card, sets
shared iff votes >= K (and not stale), stale iff the age rule fires. It MUST
NOT change cluster_id, members or votes composition logic — votes are rebuilt
from the existing cluster membership (C-PR1).

Print {promoted, already_shared, stale}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from clock import RunClock
from cluster import compute_votes, last_closed_at
from store import read_jsonl, write_jsonl


def promote_pass(cards: list[dict], cfg: dict, clock: RunClock) -> dict:
    out = {c["card_id"]: dict(c) for c in cards}
    promoted = already_shared = stale_count = 0
    for c in out.values():
        if c.get("role") != "canonical":
            continue
        members = [out[m] for m in c.get("members", []) if m in out]
        votes, mode = compute_votes(c, members)
        c["votes"] = votes
        lca = last_closed_at(c, members)
        if lca:
            c["receipt"]["last_closed_at"] = lca
        stale = False
        if lca and c["receipt"].get("last_closed_at"):
            age = clock.age_days(c["receipt"]["last_closed_at"])
            if age is not None and age > cfg["STALE_AFTER_DAYS"]:
                stale = True
        was_shared = c.get("status") == "shared"
        if votes >= cfg["K_INDEPENDENT"] and not stale:
            if not was_shared:
                promoted += 1
            c["status"] = "shared"
        else:
            if stale:
                stale_count += 1
                c["status"] = "stale"
            else:
                c["status"] = "private"
        if was_shared and c.get("status") == "shared":
            already_shared += 1
    return {"cards": [out[c["card_id"]] for c in cards],
            "promoted": promoted, "already_shared": already_shared,
            "stale": stale_count}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Promote/stale tail of cluster.py (SPEC §6.5).")
    ap.add_argument("--cards", required=True)
    ap.add_argument("--dialogues", required=True)
    ap.add_argument("--now", default=None)
    ap.add_argument("--k-independent", type=int, default=None)
    ap.add_argument("--stale-after-days", type=int, default=None)
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "K_INDEPENDENT": args.k_independent if args.k_independent is not None
            else cfgmod.DEFAULTS["K_INDEPENDENT"],
        "STALE_AFTER_DAYS": args.stale_after_days if args.stale_after_days is not None
            else cfgmod.DEFAULTS["STALE_AFTER_DAYS"],
    })
    cards = read_jsonl(args.cards)
    clock = RunClock(args.now) if args.now else RunClock(cfgmod.utcnow_iso())
    result = promote_pass(cards, cfg, clock)
    write_jsonl(args.cards, result["cards"])
    print(json.dumps({k: v for k, v in result.items() if k != "cards"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
