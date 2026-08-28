#!/usr/bin/env python3
"""Independent A4 re-derivation — per-scope TF-IDF, mirroring cluster.py.

The committed a4 audit fits ONE cross-scope TfidfModel (bin/audit.py:138),
but SPEC §6.3 clusters per-scope. This script extracts ~50 pool dialogues,
builds cards, and computes the within/across-label cosine distribution BOTH
ways (cross-scope fit vs per-scope fit) so the difference is visible.

Zero trust in thread comments: numbers are re-derived from a fresh extraction.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent


def main() -> int:
    pool = ROOT / "data" / "abcd_1000_pool.jsonl"
    rows = [json.loads(l) for l in pool.read_text().splitlines() if l.strip()][:50]
    labels = {f"d-{r['chat_id']}": r["unlock_guideline"] for r in rows}

    # ingest -> extract (live, pinned model from env) -> cluster --force
    import subprocess
    import tempfile
    td = Path(tempfile.mkdtemp(prefix="h1_a4_verify_"))
    raw = td / "raw"
    inp = td / "pool50.jsonl"
    inp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    dial = td / "dialogues.jsonl"
    cards = td / "cards.jsonl"
    env = None
    r = subprocess.run([sys.executable, str(BIN / "ingest.py"), "--in", str(inp), "--out", str(dial)],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        print("ingest failed:", r.stderr[-500:]); return 1
    # extract needs H1_API_KEY/H1_BASE_URL/H1_MODEL from the caller's env
    import os as _os
    r = subprocess.run([sys.executable, str(BIN / "extract.py"),
                        "--in", str(dial), "--out", str(cards),
                        "--model", _os.environ.get("H1_MODEL", ""),
                        "--base-url", _os.environ.get("H1_BASE_URL", ""),
                        "--raw-dir", str(raw), "--now", "2026-08-28T12:00:00Z"],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        print("extract failed:", r.stderr[-800:]); return 1
    r = subprocess.run([sys.executable, str(BIN / "cluster.py"),
                        "--cards", str(cards), "--dialogues", str(dial),
                        "--force", "--now", "2026-08-28T12:00:00Z"],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        print("cluster failed:", r.stderr[-500:]); return 1

    from common import TFIDF
    from schema import card_text
    cards_l = [json.loads(l) for l in cards.read_text().splitlines() if l.strip()]
    canon = [c for c in cards_l if c.get("role") == "canonical"]
    keyed = [(c["card_id"], card_text(c), labels.get(c["receipt"]["source_dialogue_id"]),
              c["receipt"]["scope"]) for c in canon]

    def dist(pairs):
        if not pairs:
            return {"n": 0, "median": 0.0, "p75": 0.0, "max": 0.0, "frac_ge": 0.0}
        xs = sorted(pairs)
        n = len(xs)
        med = xs[n//2] if n % 2 else (xs[n//2-1] + xs[n//2]) / 2
        return {"n": n, "median": round(med, 4),
                "p75": round(xs[int(n*0.75)], 4), "max": round(xs[-1], 4),
                "frac_ge": round(sum(1 for v in xs if v >= 0.35)/n, 4)}

    # A) cross-scope fit (what bin/audit.py does)
    model_x = TFIDF().fit([t for _, t, _, _ in keyed])
    w_x, a_x = [], []
    for i in range(len(keyed)):
        for j in range(i+1, len(keyed)):
            s = model_x.score(keyed[i][1], keyed[j][1])
            (w_x if keyed[i][2] == keyed[j][2] else a_x).append(s)
    # B) per-scope fit (what cluster.py does)
    w_p, a_p = [], []
    scopes = {}
    for i, k in enumerate(keyed):
        scopes.setdefault(k[3], []).append((i, k))
    for scope, members in scopes.items():
        texts = [k[1] for _, k in members]
        m = TFIDF().fit(texts)
        for a in range(len(members)):
            for b in range(a+1, len(members)):
                s = m.score(texts[a], texts[b])
                (w_p if members[a][1][2] == members[b][1][2] else a_p).append(s)

    print(json.dumps({
        "n_cards": len(keyed),
        "cross_scope_fit (audit.py as committed)": {
            "within": dist(w_x), "across": dist(a_x)},
        "per_scope_fit (cluster.py recipe)": {
            "within": dist(w_p), "across": dist(a_p)},
        "scopes": {k: len(v) for k, v in scopes.items()},
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
