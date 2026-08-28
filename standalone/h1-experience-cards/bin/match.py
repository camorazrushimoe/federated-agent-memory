#!/usr/bin/env python3
"""match.py — lexical match of a live dialogue against the card store (SPEC §6.4).

    python bin/match.py --dialogue data/live.json --cards data/cards.jsonl

Deterministic, no LLM:
1. query = all customer turns of the live dialogue, lowercased
2. candidates = cards with receipt.scope == live scope AND status=shared AND
   role=canonical (members / private / stale / rejected never score — C-SV3)
3. unigram TF-IDF (sublinear, no stoplist) fitted on {query} ∪ card-texts
   (problem_shape + constraint + unlock); cosine >= MATCH_THRESHOLD, sort desc,
   cut to MAX_PACKET
4. stdout: [{card_id, score, votes}]

Cross-scope / cross-vertical matches are impossible by construction (scope key
on the candidate set). Empty candidate set -> [].
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from schema import card_text
from store import read_jsonl
from tfidf import TfidfModel


def match_cards(dialogue: dict, cards: list[dict], cfg: dict) -> list[dict]:
    """Return [{card_id, score, votes}] sorted desc (tie: card_id asc)."""
    query = " ".join(
        t.get("text", "") for t in dialogue.get("turns", [])
        if t.get("role") == "customer").lower()
    scope = f"{dialogue['tenant_id']}/{dialogue['vertical']}"
    candidates = [c for c in cards
                  if c.get("receipt", {}).get("scope") == scope
                  and c.get("status") == "shared"
                  and c.get("role") == "canonical"]
    if not candidates or not query:
        return []
    texts = [card_text(c) for c in candidates]
    model = TfidfModel([query] + texts)
    scored = []
    for c, text in zip(candidates, texts):
        s = model.cosine(query, text)
        if s >= cfg["MATCH_THRESHOLD"]:
            scored.append({"card_id": c["card_id"], "score": round(s, 6),
                           "votes": c.get("votes", 0)})
    scored.sort(key=lambda x: (-x["score"], x["card_id"]))
    return scored[:cfg["MAX_PACKET"]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Match a live dialogue to shared canonical cards (SPEC §6.4).")
    ap.add_argument("--dialogue", required=True, help="one dialogue record (JSON file)")
    ap.add_argument("--cards", required=True, help="cards.jsonl")
    ap.add_argument("--match-threshold", type=float, default=None)
    ap.add_argument("--max-packet", type=int, default=None)
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "MATCH_THRESHOLD": args.match_threshold if args.match_threshold is not None
            else cfgmod.DEFAULTS["MATCH_THRESHOLD"],
        "MAX_PACKET": args.max_packet if args.max_packet is not None
            else cfgmod.DEFAULTS["MAX_PACKET"],
    })
    dialogue = json.loads(Path(args.dialogue).read_text(encoding="utf-8"))
    cards = read_jsonl(args.cards)
    print(json.dumps(match_cards(dialogue, cards, cfg), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
