#!/usr/bin/env python3
"""match.py — lexical serve matching (deterministic, NO LLM, SPEC §6.4).

    python bin/match.py --dialogue data/one.json --cards data/cards.jsonl

- Query = concatenation of the live dialogue's customer turns, lowercased
  (C-SV5).
- Candidates = cards with receipt.scope == live scope AND status=shared AND
  role=canonical. Empty candidate set → [] (C-SV7).
- TF-IDF fitted on {query} ∪ {candidate card-texts} (the ONE recipe,
  SPEC §6.3/§6.4); cosine(query, card_text); keep ≥ MATCH_THRESHOLD; sort
  desc (tie: card_id); cut to MAX_PACKET.

Stdout: [{card_id, score, votes}].

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import json
import os
import sys

import config as cfg
import jsonio as hio
from common import TFIDF, card_text


def live_query(dialogue):
    """Concatenation of customer turns, lowercased (SPEC §7, C-SV5)."""
    parts = [t.get("text", "")
             for t in dialogue.get("turns", [])
             if t.get("role") == "customer"]
    return " ".join(parts).lower()


def live_scope(dialogue):
    return f"{dialogue['tenant_id']}/{dialogue['vertical']}"


def match_cards(dialogue, cards_path, overrides=None):
    """Return [{card_id, score, votes}] for the live dialogue."""
    cfg_obj = cfg.Config(overrides)
    query = live_query(dialogue)
    scope = live_scope(dialogue)

    store = []
    if os.path.exists(cards_path):
        store = hio.read_jsonl(cards_path)
    candidates = [c for c in store
                  if (c.get("receipt") or {}).get("scope") == scope
                  and c.get("status") == "shared"
                  and c.get("role") == "canonical"]
    if not candidates:
        return []

    texts = [card_text(c) for c in candidates]
    tfidf = TFIDF().fit([query] + texts)
    scored = []
    for c in candidates:
        s = tfidf.score(query, card_text(c))
        if s >= cfg_obj.MATCH_THRESHOLD:
            scored.append({"card_id": c["card_id"], "score": s,
                           "votes": c.get("votes", 0)})
    scored.sort(key=lambda x: (-x["score"], x["card_id"]))
    return scored[:cfg_obj.MAX_PACKET]


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="match.py",
        description="Score shared canonical cards against a live dialogue.")
    ap.add_argument("--dialogue", dest="dialogue_path", required=True)
    ap.add_argument("--cards", dest="cards_path", required=True)
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    with open(args.dialogue_path, "r", encoding="utf-8") as fh:
        dialogue = json.load(fh)
    result = match_cards(dialogue, args.cards_path, cfg.parse_overrides(args.set))
    print(hio.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
