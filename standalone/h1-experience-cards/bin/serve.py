#!/usr/bin/env python3
"""serve.py — render a packet for a live dialogue (deterministic, NO LLM).

    python bin/serve.py --dialogue data/live.json --cards data/cards.jsonl \\
        [--now ISO] [--packets-out packets/] [--set k=v]

1. match.py logic (shared canonical only).
2. If two candidates share a cluster_id, keep the highest score only (C-SV2).
3. Render the PROMPTS.md §4 packet template (no extra LLM): the header line
   "This is evidence from earlier chats, not a policy and not an
   instruction." is verbatim; each card block starts with "- [{card_id}] …";
   "Blocked by:" omitted when constraint=="none"; "What unblocked it:"
   omitted when unlock=="none"; {what_worked_joined} = " → ".join(what_worked).
   An empty candidate set yields an EMPTY packet (C-SV7) — no header, no card.
4. Append {dialogue_id, at} to each used card's served_to exactly once per
   (card, dialogue) pair (C-SV8) and persist the store.
   at = pinned --now; datetime.now() is NEVER called here (brief §6).

Prints {packet_text, card_ids, scores}.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import json
import os
import sys

import config as cfg
import jsonio as hio
from match import match_cards
from common import prompts_for

_PROMPTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "PROMPTS.md")


def render_card_block(template, card):
    """Render one card block from the PROMPTS.md §4 card template, omitting
    the Blocked by / What unblocked it lines when the field is 'none'."""
    lines = template.splitlines()
    keep = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Blocked by:") and \
                card.get("constraint") == "none":
            continue
        if stripped.startswith("What unblocked it:") and \
                card.get("unlock") == "none":
            continue
        keep.append(line)
    block = "\n".join(keep)
    return block.format(
        card_id=card["card_id"],
        problem_shape=card.get("problem_shape", ""),
        constraint=card.get("constraint", ""),
        unlock=card.get("unlock", ""),
        what_worked_joined=" → ".join(card.get("what_worked", [])),
    )


def render_packet(template, card_block_template, scope, cards):
    """Render the full packet. Empty cards → empty packet (C-SV7)."""
    if not cards:
        return ""
    blocks = [render_card_block(card_block_template, c) for c in cards]
    return template.format(scope=scope, cards="\n\n".join(blocks))


def serve_dialogue(dialogue, cards_path, pinned_now, packets_out=None,
                   overrides=None):
    """Core serve. Appends served_to (once per pair) and persists the store.

    Returns {packet_text, card_ids, scores}.
    """
    if pinned_now is None:
        raise ValueError("serve.py requires --now (pinned determinism)")
    cfg_obj = cfg.Config(overrides)
    prompts = prompts_for(_PROMPTS_PATH)

    store = {}
    if os.path.exists(cards_path):
        for c in hio.read_jsonl(cards_path):
            store[c["card_id"]] = c

    matches = match_cards(dialogue, cards_path, overrides)
    # dedupe by cluster_id — keep the highest score only (C-SV2)
    best = {}
    for m in matches:
        store_row = store.get(m["card_id"])
        cluster_id = (store_row.get("cluster_id") if store_row
                      else m["card_id"])
        if cluster_id not in best or m["score"] > best[cluster_id]["score"]:
            best[cluster_id] = m
    matches = sorted(best.values(),
                     key=lambda x: (-x["score"], x["card_id"]))[
        :cfg_obj.MAX_PACKET]

    cards = []
    card_ids = []
    scores = []
    for m in matches:
        card = store[m["card_id"]]
        cards.append(card)
        card_ids.append(card["card_id"])
        scores.append(round(m["score"], 6))
        entry = {"dialogue_id": dialogue["dialogue_id"], "at": pinned_now}
        if entry not in card.get("served_to", []):
            card.setdefault("served_to", []).append(entry)
        card["updated_at"] = pinned_now

    packet_text = render_packet(prompts["serve_packet"],
                                prompts["serve_card_block"],
                                f"{dialogue['tenant_id']}/{dialogue['vertical']}",
                                cards)

    # persist the store, deterministic order
    ordered = [store[k] for k in sorted(store)]
    hio.write_jsonl(cards_path, ordered)

    if packets_out is not None and packet_text:
        os.makedirs(packets_out, exist_ok=True)
        with open(os.path.join(packets_out, f"{dialogue['dialogue_id']}.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write(packet_text)

    return {"packet_text": packet_text, "card_ids": card_ids,
            "scores": scores}


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="serve.py",
        description="Render an evidence packet for a live dialogue (SPEC §6.6).")
    ap.add_argument("--dialogue", dest="dialogue_path", required=True)
    ap.add_argument("--cards", dest="cards_path", required=True)
    ap.add_argument("--now", default=None,
                    help="pinned ISO timestamp (required; brief §6)")
    ap.add_argument("--packets-out", dest="packets_out", default=None,
                    help="optional dir to write <dialogue_id>.txt packets")
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    with open(args.dialogue_path, "r", encoding="utf-8") as fh:
        dialogue = json.load(fh)
    result = serve_dialogue(dialogue, args.cards_path, args.now,
                            args.packets_out, cfg.parse_overrides(args.set))
    print(hio.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
