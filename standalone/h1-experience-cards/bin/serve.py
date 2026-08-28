#!/usr/bin/env python3
"""serve.py — render and serve an evidence packet (SPEC §6.6).

Usage:
  python bin/serve.py --dialogue data/live.json --cards data/cards.jsonl \
      --at 2026-08-28T14:00:00Z

1. Run the match logic (shared canonical only, same scope).
2. Dedupe by cluster_id (keep the highest score).
3. Render the packet with the PROMPTS.md §4 template (no extra LLM).
4. Append each used card_id to that canonical card's served_to exactly once
   per serving dialogue (C-SV8).
5. Print {packet_text, card_ids, scores}.

The packet MUST contain
"This is evidence from earlier chats, not a policy and not an instruction."
and each card block starts with "[card_id]" (C-SV6).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402
from match import match  # noqa: E402


def render_packet(scope, picks, prompts):
    """picks: list of (card, score) already sorted desc and deduped."""
    blocks = []
    for card, _score in picks:
        lines = []
        lines.append(f"- [{card['card_id']}] When the request looked like: "
                     f"{card['problem_shape']}")
        if (card.get("constraint") or "none").lower() != "none":
            lines.append(f"  Blocked by: {card['constraint']}")
        if (card.get("unlock") or "none").lower() != "none":
            lines.append(f"  What unblocked it: {card['unlock']}")
        ww = card.get("what_worked") or []
        lines.append("  Steps that ran: " + (" → ".join(ww) if ww else "none"))
        blocks.append("\n".join(lines))
    template = prompts["serve_template"]
    return template.format(scope=scope, cards="\n\n".join(blocks))


def serve(dialogue, cards, cfg, prompts, at, cards_path=None):
    """Build the packet, append served_to, optionally write cards back.
    cards_path=None -> read-only (no store mutation)."""
    picks = match(dialogue, cards, cfg)
    # picks: [{card_id, score, votes}] sorted desc, capped at MAX_PACKET.
    # Dedupe by cluster_id keeping the highest score (SPEC §6.6).
    by_id = {c["card_id"]: c for c in cards}
    best_by_cluster = {}
    for p in picks:
        card = by_id[p["card_id"]]
        cid = card["cluster_id"]
        if cid not in best_by_cluster or p["score"] > best_by_cluster[cid][0]:
            best_by_cluster[cid] = (p["score"], p["card_id"])
    dedup = sorted(best_by_cluster.values(), key=lambda x: (-x[0], x[1]))
    picks = [{"card_id": cid, "score": round(score, 6),
              "votes": by_id[cid].get("votes", 0)}
             for score, cid in dedup][:cfg["MAX_PACKET"]]

    scope = H.scope_of(dialogue["tenant_id"], dialogue["vertical"])
    used = [by_id[p["card_id"]] for p in picks]
    packet_text = render_packet(scope, [(c, p["score"]) for c, p in zip(
        used, picks)], prompts)

    # append served_to exactly once per (card, dialogue) pair (C-SV8)
    for card in used:
        served = [s for s in card.get("served_to") or []
                  if s["dialogue_id"] != dialogue["dialogue_id"]]
        served.append({"dialogue_id": dialogue["dialogue_id"], "at": at})
        card["served_to"] = served
    if cards_path:
        H.write_jsonl(cards_path, cards, mode="w")
    return packet_text, [p["card_id"] for p in picks], [p["score"]
                                                        for p in picks]


def main():
    ap = argparse.ArgumentParser(description="Serve a packet (SPEC §6.6)")
    ap.add_argument("--dialogue", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--at", default=None,
                    help="deterministic serve timestamp (recorded in served_to)")
    ap.add_argument("--prompts", default=H.PROMPTS_PATH)
    ap.add_argument("--config", action="append", default=[])
    args = ap.parse_args()
    cfg = H.load_config(args.config)
    prompts = H.load_prompts(args.prompts)
    at = args.at or H.now_iso(cfg)
    dialogue = H.load_json(args.dialogue)
    cards = H.read_jsonl(args.cards)
    packet_text, card_ids, scores = serve(dialogue, cards, cfg, prompts, at,
                                          cards_path=args.cards)
    H.print_json({"packet_text": packet_text, "card_ids": card_ids,
                  "scores": scores})


if __name__ == "__main__":
    main()
