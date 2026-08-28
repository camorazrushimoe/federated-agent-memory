#!/usr/bin/env python3
"""recompute_b1.py — independent B1 re-score from raw corpus (pipeline check).

Recomputes B1 TF-IDF cosine for all 170 pairs straight from
data/abcd/abcd_v1.1.json + candidate_pairs.jsonl using the pre-registered
config (score_m1.py docstring / README §7), and diffs against the committed
b1_scores.jsonl from PR #17. No import of score_m1.py; mirrors the config:
  - text: customer turns only (delexed, speaker==customer, non-empty, in order)
  - TfidfVectorizer(lowercase, sublinear_tf, unigrams, stop_words=None)
  - fitted on ALL corpus docs (sorted convo_id order), transformed on pairs
  - cosine, rounded to 6 dp
"""
import json
import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

REPO = Path(__file__).resolve().parents[3]
ABCD = REPO / "data/abcd/abcd_v1.1.json"
PAIRS = REPO / "research/phase2/m1/candidate_pairs.jsonl"
COMMITTED = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "research/phase2/m1/b1_scores.jsonl"


def customer_text(c):
    return " ".join(
        t["text"].strip()
        for t in c.get("delexed", [])
        if isinstance(t, dict) and t.get("speaker") == "customer"
        and (t.get("text") or "").strip()
    )


def main():
    data = json.load(open(ABCD))
    convos = {}
    for split in ("train", "dev", "test"):
        for c in data.get(split, []):
            convos[str(c["convo_id"])] = c
    pairs = [json.loads(l) for l in open(PAIRS) if l.strip()]

    doc_ids = sorted(convos)
    vec = TfidfVectorizer(lowercase=True, sublinear_tf=True,
                          ngram_range=(1, 1), stop_words=None)
    X = vec.fit_transform([customer_text(convos[i]) for i in doc_ids])
    pos = {i: k for k, i in enumerate(doc_ids)}

    rows = {}
    for p in pairs:
        a, b = p["conv_a"], p["conv_b"]
        va = X[pos[a]].toarray().ravel()
        vb = X[pos[b]].toarray().ravel()
        na, nb = (va ** 2).sum() ** 0.5, (vb ** 2).sum() ** 0.5
        cos = float(va @ vb) / (na * nb) if na and nb else 0.0
        rows[p["pair_id"]] = round(cos, 6)

    committed = {}
    for l in open(COMMITTED):
        d = json.loads(l)
        committed[d["pair_id"]] = d["b1_cosine"]

    assert set(rows) == set(committed), "pair id sets differ"
    diffs = [(pid, rows[pid], committed[pid]) for pid in sorted(rows)
             if abs(rows[pid] - committed[pid]) > 1e-9]
    exact = sum(1 for pid in rows if rows[pid] == committed[pid])
    print(f"n_pairs={len(rows)} exact_6dp_match={exact} "
          f"differ(>1e-9)={len(diffs)}")
    for d in diffs[:10]:
        print("  DIFF", d)
    # band-level check on my recomputation
    band = {p["pair_id"]: p["band"] for p in pairs}
    from collections import Counter
    print("band counts:", dict(Counter(band.values())))


if __name__ == "__main__":
    main()
