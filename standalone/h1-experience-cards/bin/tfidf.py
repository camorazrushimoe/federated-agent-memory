"""Unigram TF-IDF, sublinear TF, no stoplist — the one matching recipe.

Used by match.py (live query vs card-texts) and cluster.py (card-text vs
card-text), exactly as SPEC.md §6.3/§6.4 describe: sublinear term frequency
(1 + log tf), inverse document frequency, cosine similarity, fitted on the
documents of that scope only. Pure stdlib, deterministic (sorted vocab).

Tokens are lowercase runs of [a-z0-9'] characters (unigram only).
"""

from __future__ import annotations

import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> list[str]:
    """Lowercase unigram tokens; no stoplist, per SPEC §6.3/§6.4."""
    return _TOKEN_RE.findall(text.lower())


class TfidfModel:
    """Fitted once on a corpus; vectorize + cosine for any new doc.

    IDF is add-one smoothed (`log((1+N)/(1+df)) + 1`) so a term appearing in
    EVERY document of the fit corpus still gets idf > 0. Without smoothing,
    a corpus that is mostly near-duplicate cards (the §10.2 clustering case)
    gives every term idf = log(N/N) = 0 -> zero vectors -> cosine 0.0 even for
    identical card-texts -> clustering can never merge -> nothing ever becomes
    `shared`. That is a dead pipeline, not a data finding (caught by the D3
    audit A4 review; recipe fix recorded here, thresholds untouched).
    """

    def __init__(self, docs: list[str]):
        # corpus statistics
        self.df: dict[str, int] = {}
        self.N = len(docs)
        for d in docs:
            for t in set(tokenize(d)):
                self.df[t] = self.df.get(t, 0) + 1
        self.vocab: list[str] = sorted(self.df)  # deterministic iteration

    def _weights(self, text: str) -> dict[str, float]:
        tf: dict[str, int] = {}
        for t in tokenize(text):
            tf[t] = tf.get(t, 0) + 1
        w: dict[str, float] = {}
        for t, c in tf.items():
            df = self.df.get(t, 0)
            if df == 0:
                continue  # token unseen in the fit corpus: no idf, no weight
            idf = math.log((1.0 + self.N) / (1.0 + df)) + 1.0
            w[t] = (1.0 + math.log(c)) * idf
        return w

    @staticmethod
    def _norm(w: dict[str, float]) -> float:
        return math.sqrt(sum(v * v for v in w.values()))

    def vectorize(self, text: str) -> dict[str, float]:
        return self._weights(text)

    def cosine(self, a: str, b: str) -> float:
        wa = self._weights(a)
        wb = self._weights(b)
        if not wa or not wb:
            return 0.0
        dot = sum(v * wb.get(t, 0.0) for t, v in wa.items())
        na, nb = self._norm(wa), self._norm(wb)
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)


def fit_and_cosines(query: str, docs: list[str]) -> list[float]:
    """Fit TF-IDF on [query] + docs, return cosine(query, doc) per doc.

    Mirrors SPEC §6.4: the model is fitted on query ∪ card-texts.
    """
    model = TfidfModel([query] + docs)
    return [model.cosine(query, d) for d in docs]
