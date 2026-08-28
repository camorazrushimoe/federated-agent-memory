#!/usr/bin/env python3
"""match.py — score shared canonical cards against a live dialogue (SPEC §6.4).

Usage:
  python bin/match.py --dialogue data/one.json --cards data/cards.jsonl

Deterministic. No LLM. Query = all customer turns (lowercased). Candidates =
same-scope, status=shared, role=canonical. Unigram TF-IDF (sublinear, no
stoplist) on {query} ∪ card-texts; cosine >= MATCH_THRESHOLD; sorted desc;
cut to MAX_PACKET. Empty candidate set -> [].

Print JSON [{card_id, score, votes}].
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402


def match(dialogue, cards, cfg):
    query_text = " ".join(t["text"] for t in dialogue["turns"]
                          if t["role"] == "customer").lower()
    scope = H.scope_of(dialogue["tenant_id"], dialogue["vertical"])
    cands = [c for c in cards
             if c["receipt"]["scope"] == scope
             and c["status"] == "shared" and c["role"] == "canonical"]
    if not cands:
        return []
    docs = [query_text] + [H.card_text(c) for c in cands]
    vecs, _ = H.build_tfidf(docs)
    qvec = vecs[0]
    scored = []
    for c, v in zip(cands, vecs[1:]):
        s = H.cosine(qvec, v)
        if s >= cfg["MATCH_THRESHOLD"]:
            scored.append((s, c["card_id"], c.get("votes", 0)))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = [{"card_id": cid, "score": round(score, 6), "votes": votes}
           for score, cid, votes in scored[:cfg["MAX_PACKET"]]]
    return out


def main():
    ap = argparse.ArgumentParser(description="Match a live dialogue (SPEC §6.4)")
    ap.add_argument("--dialogue", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--config", action="append", default=[])
    args = ap.parse_args()
    cfg = H.load_config(args.config)
    dialogue = H.load_json(args.dialogue)
    cards = H.read_jsonl(args.cards)
    H.print_json(match(dialogue, cards, cfg))


if __name__ == "__main__":
    main()
