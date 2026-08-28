#!/usr/bin/env python3
"""serve.py — build the evidence packet and record who saw it (SPEC §6.6).

    python bin/serve.py --dialogue data/live.json --cards data/cards.jsonl \
        [--packets-dir runs/.../packets] [--clock-start ...]

1. match (shared canonical, same scope only)
2. dedupe by cluster_id — if two candidates share a cluster_id, keep the
   highest score only (C-SV2)
3. render the PROMPTS.md §4 packet template (no LLM; C-SV6 line included)
4. append each used card_id to that card's served_to exactly once per serving
   dialogue (C-SV8); serving never increments votes (SPEC §5)
5. stdout: {packet_text, card_ids, scores}
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from clock import RunClock
from match import match_cards
from prompts import Prompts
from store import read_jsonl, write_jsonl


def serve_one(dialogue: dict, cards: list[dict], cfg: dict,
              prompts: Prompts, clock: RunClock,
              cards_path: str | None = None) -> dict:
    matched = match_cards(dialogue, cards, cfg)
    # dedupe by cluster_id: keep highest score (matched is already sorted desc)
    seen_clusters: set[str] = set()
    chosen = []
    for m in matched:
        card = _card_by_id(cards, m["card_id"])
        if card is None:
            continue
        if card["cluster_id"] in seen_clusters:
            continue
        seen_clusters.add(card["cluster_id"])
        chosen.append(m)
        if len(chosen) >= cfg["MAX_PACKET"]:
            break

    scope = f"{dialogue['tenant_id']}/{dialogue['vertical']}"
    chosen_cards = []
    for m in chosen:
        c = _card_by_id(cards, m["card_id"])
        if c is not None:
            chosen_cards.append(c)

    packet_text = prompts.serve_packet(scope=scope, cards=chosen_cards) if chosen_cards else ""

    # record served_to (append exactly once per serving dialogue)
    updated = {c["card_id"]: dict(c) for c in cards}
    for c in chosen_cards:
        entry = {"dialogue_id": dialogue["dialogue_id"], "at": clock.now()}
        served = c.get("served_to", [])
        if not any(s.get("dialogue_id") == dialogue["dialogue_id"] for s in served):
            served = served + [entry]  # no double-append on re-serve (C-SV8)
        c = dict(c)
        c["served_to"] = served
        updated[c["card_id"]] = c
    if cards_path:
        write_jsonl(cards_path, [updated[c["card_id"]] for c in cards])

    return {
        "packet_text": packet_text,
        "card_ids": [c["card_id"] for c in chosen_cards],
        "scores": [m["score"] for m in chosen],
    }


def _card_by_id(cards: list[dict], card_id: str) -> dict | None:
    for c in cards:
        if c["card_id"] == card_id:
            return c
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Serve an evidence packet (SPEC §6.6). No LLM.")
    ap.add_argument("--dialogue", required=True, help="one dialogue record (JSON file)")
    ap.add_argument("--cards", required=True, help="cards.jsonl (written back with served_to)")
    ap.add_argument("--packets-dir", default=None, help="write packets/<dialogue_id>.txt")
    ap.add_argument("--match-threshold", type=float, default=None)
    ap.add_argument("--max-packet", type=int, default=None)
    ap.add_argument("--clock-start", default=None)
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "MATCH_THRESHOLD": args.match_threshold if args.match_threshold is not None
            else cfgmod.DEFAULTS["MATCH_THRESHOLD"],
        "MAX_PACKET": args.max_packet if args.max_packet is not None
            else cfgmod.DEFAULTS["MAX_PACKET"],
    })
    _cards_path_holder = args.cards
    dialogue = json.loads(Path(args.dialogue).read_text(encoding="utf-8"))
    cards = read_jsonl(args.cards)
    clock = RunClock(args.clock_start) if args.clock_start else RunClock(cfgmod.utcnow_iso())
    prompts = Prompts()
    t0 = time.time()
    result = serve_one(dialogue, cards, cfg, prompts, clock,
                       cards_path=_cards_path_holder)
    result["serve_ms"] = int((time.time() - t0) * 1000)
    if args.packets_dir and result["packet_text"]:
        p = Path(args.packets_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / f"{dialogue['dialogue_id']}.txt").write_text(result["packet_text"], encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
