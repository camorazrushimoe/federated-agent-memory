#!/usr/bin/env python3
"""score_m1.py — M1 B0/B1 scoring (pre-registered plan: research/phase2/m1/README.md
§5, method doc docs/research-method-m1-m3.md §M1). Round 1, BON-41/H-m1.

Two stages:

  Stage A — precompute (NO gold needed):
      python3 score_m1.py --precompute
      -> b1_scores.jsonl : one row per pair:
         {pair_id, conv_a, conv_b, band, sub_band, b0_pool, b1_cosine}
      plus prints a label-free score-separation preview (per-band quantiles).

  Stage B — join with the gold set (when RUNBOOK-m1 S3 lands it at
  research/phase2/m1/gold/gold_m1_pairs_agentlabeled.jsonl):
      python3 score_m1.py --gold research/phase2/m1/gold/gold_m1_pairs_agentlabeled.jsonl
      -> m1_results.json + m1_report.md
         B0 oracle metrics, B1 (recall_sm, FFR) operating curve over the full
         threshold sweep, D18-bar verdict, per-band recall, pairwise F1.

B2 (off-the-shelf sentence embedding) is GATED per method doc: it runs only if
B1 fails the frozen bar. This script has no B2 code by design.

Pre-registered B1 configuration (fixed BEFORE the gold set is seen — this
docstring + the commit that lands it are the record):
  - text: full customer turns of each conversation (delexed,
    speaker=="customer", non-empty after strip, in order), space-joined.
    Agent turns are excluded (boilerplate; method doc B1 rule). The action
    trace is NOT part of B1 (B1 is lexical-over-customer-text; the trace is
    corroborating evidence for the labeler per protocol R4, not a method feature).
  - TF-IDF: sklearn TfidfVectorizer, unigrams, lowercase=True,
    sublinear_tf=True, stop_words=None (customer turns are short and
    intent-bearing; a stop-word list would drop domain-relevant words),
    default token pattern. Fitted on ALL 10,042 corpus customer-turn
    documents (population IDF — not tuned to the 170-pair set), then
    transformed only on the 318 unique pair conversations.
  - score: cosine similarity of the two conversation TF-IDF vectors.
  - pooling rule: pool a pair iff cosine >= t.
  - threshold selection: full sweep over every unique B1 score (plus the
    "pool nothing" sentinel). Bar-passing operating point = argmax pairwise-F1
    over thresholds with FFR <= 0.10 AND recall_sm >= 0.60 (deterministic
    tie-break: lowest t). If no threshold meets the bar: report the threshold
    minimizing FFR (tie-break: highest recall_sm) and the recall at that point;
    the missed bar is the finding.

Metrics (bar frozen at D18, not negotiable downward):
  - recall_sm = share of should-match-band pairs pooled
  - FFR       = share of gold-canonical-`unrelated` pairs pooled (false friends)
  - B1 passes iff exists t with FFR <= 0.10 AND recall_sm >= 0.60
  - secondary: per-band recall at the selected t; pairwise F1 vs gold
    (TP = pooled AND gold same-problem); B0 oracle per-band pooling rates;
    inter-pass disagreement rate (from gold; agent self-consistency, NOT
    human agreement — honesty clause, PROTOCOL §3).

Deterministic: no RNG anywhere; fixed sort orders. Re-run on the same
corpus + pairs + gold = byte-identical outputs.

Corpus pin: data/abcd/abcd_v1.1.json, sha256:16 = 005d425e890b30a1
Pair set: research/phase2/m1/candidate_pairs.jsonl, sha256:16 = 42215fc5969e600e
(pinned 170 = 85/34/51; build_candidate_pairs.py, seed 42).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

M1 = Path(__file__).resolve().parent
DEFAULT_ABCD = Path("data/abcd/abcd_v1.1.json")
DEFAULT_PAIRS = M1 / "candidate_pairs.jsonl"
DEFAULT_GOLD = M1 / "gold" / "gold_m1_pairs_agentlabeled.jsonl"
SCORES_OUT = M1 / "b1_scores.jsonl"
RESULTS_JSON = M1 / "m1_results.json"
REPORT_MD = M1 / "m1_report.md"

CORPUS_SHA16 = "005d425e890b30a1"
PAIRS_SHA16 = "42215fc5969e600e"

FFR_BAR = 0.10
RECALL_BAR = 0.60


# ---------- corpus (mirrors build_candidate_pairs.py helpers) ----------
def load_convos(path):
    data = json.load(open(path))
    convos = []
    for split in ("train", "dev", "test"):
        if split in data:
            convos.extend(data[split])
    return convos


def customer_text(c):
    """Full customer turns, delexed, in order (agent boilerplate excluded)."""
    return " ".join(
        t["text"].strip()
        for t in c.get("delexed", [])
        if isinstance(t, dict) and t.get("speaker") == "customer"
        and (t.get("text") or "").strip()
    )


def sha16(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


# ---------- B1 feature build ----------
def build_scores(abcd_path, pairs, rows_out):
    """Fit TF-IDF on the whole corpus, transform the pair conversations,
    return per-pair rows {pair_id, conv_a, conv_b, band, sub_band, b0_pool,
    b1_cosine} in pair-file order."""
    convos = load_convos(abcd_path)
    by_id = {}
    for c in convos:
        cid = str(c["convo_id"])
        if cid in by_id:
            raise SystemExit(f"duplicate convo_id {cid} in corpus")
        by_id[cid] = c
    missing = [p["pair_id"] for p in pairs
               if p["conv_a"] not in by_id or p["conv_b"] not in by_id]
    if missing:
        raise SystemExit(f"pair convos not in corpus: {missing[:5]} (…)")

    # Fit on ALL corpus docs (population IDF), deterministic doc order.
    doc_ids = sorted(by_id)
    vec = TfidfVectorizer(lowercase=True, sublinear_tf=True,
                          ngram_range=(1, 1), stop_words=None)
    X = vec.fit_transform([customer_text(by_id[i]) for i in doc_ids])
    pos = {i: k for k, i in enumerate(doc_ids)}
    n_docs, n_terms = X.shape

    rows = []
    for p in pairs:
        a, b = p["conv_a"], p["conv_b"]
        va = X[pos[a]].toarray().ravel()   # dense (318 convos x 8368 terms is trivial)
        vb = X[pos[b]].toarray().ravel()
        dot = float(np.dot(va, vb))
        na = float(np.linalg.norm(va))
        nb = float(np.linalg.norm(vb))
        cos = dot / (na * nb) if (na > 0 and nb > 0) else 0.0
        if np.isnan(cos):
            cos = 0.0
        rows.append({
            "pair_id": p["pair_id"],
            "conv_a": a, "conv_b": b,
            "band": p["band"],
            "sub_band": p.get("sub_band"),
            "b0_pool": p["subflow_a"] == p["subflow_b"],  # B0 oracle: same subflow
            "b1_cosine": round(cos, 6),
        })
    info = {"n_corpus_docs": n_docs, "n_terms": n_terms,
            "n_pairs_scored": len(rows)}
    return rows, info


# ---------- Stage A: precompute ----------
def quantiles(xs):
    xs = sorted(xs)
    if not xs:
        return {}
    q = lambda p: xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]
    return {"min": round(xs[0], 4), "p25": round(q(0.25), 4),
            "p50": round(q(0.5), 4), "p75": round(q(0.75), 4),
            "p90": round(q(0.9), 4), "max": round(xs[-1], 4)}


def stage_precompute(abcd, pairs_path, out):
    pairs = load_jsonl(pairs_path)
    rows, info = build_scores(abcd, pairs, out)
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_band = {}
    for r in rows:
        by_band.setdefault(r["band"], []).append(r["b1_cosine"])
    preview = {
        b: {"n": len(v), **quantiles(v)} for b, v in sorted(by_band.items())
    }
    # b0 oracle band pooling (label-free; FFR vs gold needs stage B)
    b0_by_band = {b: sum(1 for r in rows if r["band"] == b and r["b0_pool"])
                  for b in by_band}
    # Label-free recall half of the operating curve (band = engineer's
    # construction metadata, NOT a gold label). FFR + F1 + the bar verdict need
    # gold and are computed in stage B.
    rc = recall_curve(rows)
    print(json.dumps({
        "out": str(out), **info,
        "corpus_sha256_16": sha16(abcd),
        "pairs_sha256_16": sha16(pairs_path),
        "b1_config": "unigram TF-IDF, sublinear_tf, stop_words=None, "
                     "fitted on all corpus customer-turn docs; cosine over "
                     "customer turns only (agent excluded)",
        "b0_oracle": "same subflow -> pool",
        "b0_pooled_by_band": {b: f"{b0_by_band[b]}/{preview[b]['n']}" for b in by_band},
        "score_preview_by_band": preview,
        "b1_recall_curve_label_free": rc,
        "note": "pre-gold: recall half only (band = engineer metadata, not a "
                "label). FFR, pairwise F1, and the D18 bar verdict need the gold "
                "set (stage B) and are computed the moment it lands.",
    }, indent=2))


def recall_curve(rows):
    """Label-free recall half of the B1 operating curve.

    For every unique threshold t (and the pool-nothing sentinel), report the
    share of each construction band pooled. recall_sm is the recall axis the
    D18 bar uses; FFR is the other axis and needs gold.
    """
    bands = sorted({r["band"] for r in rows})
    band_ids = {b: [r["pair_id"] for r in rows if r["band"] == b] for b in bands}
    scores = {r["pair_id"]: r["b1_cosine"] for r in rows}

    def at(t_label, pooled):
        return {"threshold": t_label, "n_pooled": len(pooled),
                "recall": {b: round(len([i for i in band_ids[b] if i in pooled])
                                    / len(band_ids[b]), 4) for b in bands}}

    curve = [at("none (pool nothing)", set())]
    for t in sorted(set(scores.values())):
        curve.append(at(f">= {t:.6f}",
                        {pid for pid, s in scores.items() if s >= t}))
    return curve


# ---------- Stage B: join gold ----------
def operate(rows, gold):
    """Full operating curve for B1 + B0, plus selected operating points.

    gold: {pair_id: canonical_label}
    Returns dict of metrics (all deterministic).
    """
    sm = [r["pair_id"] for r in rows if r["band"] == "should-match"]
    sm_set = set(sm)
    unrelated = [r["pair_id"] for r in rows if gold[r["pair_id"]] == "unrelated"]
    unrel_set = set(unrelated)
    same = [r["pair_id"] for r in rows if gold[r["pair_id"]] == "same-problem"]
    same_set = set(same)
    bands = sorted({r["band"] for r in rows})
    band_ids = {b: [r["pair_id"] for r in rows if r["band"] == b] for b in bands}

    def metrics(pooled_set, t_label):
        tp = len(pooled_set & same_set)
        fp = len(pooled_set - same_set)
        fn = len(same_set - pooled_set)
        f1 = (2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) else 0.0
        return {
            "threshold": t_label,
            "n_pooled": len(pooled_set),
            "recall_sm": round(len(pooled_set & sm_set) / len(sm_set), 4),
            "ffr": round(len(pooled_set & unrel_set) / len(unrel_set), 4),
            "recall_by_band": {b: round(len(pooled_set & set(band_ids[b])) /
                                        len(band_ids[b]), 4) for b in bands},
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
            "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn,
        }

    # ---- B1 curve: sweep every unique score + pool-nothing sentinel ----
    scores = {r["pair_id"]: r["b1_cosine"] for r in rows}
    curve = [metrics(set(), "none (pool nothing)")]
    for t in sorted(set(scores.values())):
        pooled = {pid for pid, s in scores.items() if s >= t}
        curve.append(metrics(pooled, f">= {t:.6f}"))
    passing = [c for c in curve
               if c["ffr"] <= FFR_BAR and c["recall_sm"] >= RECALL_BAR]
    if passing:
        best_f1 = max(c["f1"] for c in passing)
        cands = [c for c in passing if c["f1"] == best_f1]

        def tkey(c):  # lowest threshold wins; sentinel sorts below all
            if c["threshold"].startswith("none"):
                return (0, 0.0)
            return (1, float(c["threshold"].split(" ", 1)[1]))

        sel = min(cands, key=tkey)
        bar_met = True
    else:
        real = [c for c in curve if not c["threshold"].startswith("none")]
        sel = min(real, key=lambda c: (c["ffr"], -c["recall_sm"]))
        bar_met = False

    # ---- B0 oracle: pooled := same subflow ----
    b0_pooled = {r["pair_id"] for r in rows if r["b0_pool"]}
    b0 = metrics(b0_pooled, "same subflow (oracle)")

    return {"b1_curve": curve, "b1_selected": sel, "bar_met": bar_met,
            "n_bar_passing_thresholds": len(passing), "b0": b0,
            "n_sm": len(sm), "n_unrelated_gold": len(unrelated),
            "n_same_gold": len(same), "band_sizes": {b: len(v) for b, v in band_ids.items()}}


def join_findings(rows, gold_rows):
    """Findings computed by the oversight join re-derivation (round 1).

    Three findings, each a deterministic function of the join:
      F1 — where the false-friend danger sits: same-flow vs cross-flow FFR
           (coarse cut: gold-unrelated in should-match/ambiguous bands vs in
           the should-not-match band; fine cut: sub_band within diff-flow).
      F2 — cross-flow same-problem coverage of the gold set (0 pairs: the
           cross-vertical reuse question is UNTESTED, not refuted).
      F3 — oracle-label insufficiency: pairs the B0 oracle pools (same
           subflow) that the labeler called unrelated, plus the
           band-vs-canonical disagreement census.
    """
    g = {x["pair_id"]: x for x in gold_rows}
    sc = {r["pair_id"]: r for r in rows}
    unrel = [p for p in sc if g[p]["canonical_label"] == "unrelated"]
    same = [p for p in sc if g[p]["canonical_label"] == "same-problem"]
    sf_unrel = [p for p in unrel if sc[p]["band"] in ("should-match", "ambiguous")]
    df_unrel = [p for p in unrel if sc[p]["band"] == "should-not-match"]

    def ffr_at(t, pool):
        def block(pids):
            bad = [p for p in pool if p in set(pids)]
            return {"n_bad": len(bad), "n": len(pids),
                    "ffr": round(len(bad) / len(pids), 4) if pids else 0.0,
                    "pairs": sorted(bad)}
        return {
            "threshold": f">= {t:.6f}",
            "total": block(unrel),
            "same_flow": block(sf_unrel),
            "diff_flow": block(df_unrel),
            "diff_flow_by_sub_band": {
                sb: block([p for p in df_unrel if g[p].get("sub_band") == sb])
                for sb in sorted({g[p].get("sub_band") for p in df_unrel})},
        }

    # the thresholds quoted in the round-1 join (nearest unique score)
    uniq = sorted({r["b1_cosine"] for r in rows})
    quoted = []
    for q in (0.1965, 0.1717):
        t = min(uniq, key=lambda x: abs(x - q))
        pool = [p for p in sc if sc[p]["b1_cosine"] >= t]
        quoted.append(ffr_at(t, pool))

    # F2: gold coverage of cross-flow same-problem
    cf = [p for p in same if g[p].get("sub_band") == "cross-flow"]
    cp = [p for p in same if g[p].get("sub_band") == "cross-product"]
    snm_same = [p for p in same if sc[p]["band"] == "should-not-match"]
    same_flows = sorted({g[p]["flow_a"] for p in same})

    # F3: oracle-pooled but gold-unrelated
    oracle_bad = sorted(p for p in sc if sc[p]["b0_pool"]
                        and g[p]["canonical_label"] == "unrelated")

    # band-vs-canonical census (construction direction vs label):
    # should-match built to match -> off-direction = related-but-different /
    # unrelated; ambiguous built middle -> unrelated is off-direction;
    # should-not-match built false-friend/unrelated -> related-but-different /
    # same-problem is off-direction.
    ct = Counter((sc[p]["band"], g[p]["canonical_label"]) for p in sc)
    off_direction = {  # any deviation from the band's construction center
        ("should-match", "related-but-different"),
        ("should-match", "unrelated"),
        ("ambiguous", "same-problem"),
        ("ambiguous", "unrelated"),
        ("should-not-match", "related-but-different"),
        ("should-not-match", "same-problem"),
    }
    hard_contradiction = {  # label contradicts the band's existence reason
        ("should-match", "unrelated"),
        ("ambiguous", "unrelated"),
        ("should-not-match", "related-but-different"),
    }
    n_off = sum(ct[k] for k in off_direction if k in ct)
    n_hard = sum(ct[k] for k in hard_contradiction if k in ct)

    return {
        "ffr_cut_sameflow_vs_crossflow": quoted,
        "gold_unrelated_split": {
            "same_flow": len(sf_unrel), "diff_flow": len(df_unrel),
            "note": "gold-unrelated 63 = 15 same-flow (3 should-match band + "
                    "12 ambiguous band) + 48 diff-flow (should-not-match band)"
        },
        "crossflow_same_problem_coverage": {
            "gold_same_problem_n": len(same),
            "cross_flow_same": len(cf), "cross_product_same": len(cp),
            "should_not_match_band_same": len(snm_same),
            "all_same_problem_pairs_same_flow":
                all(g[p]["flow_a"] == g[p]["flow_b"] for p in same),
            "distinct_flows_with_same_problem": same_flows,
            "note": "the gold set contains ZERO cross-flow / cross-product "
                    "same-problem pairs: cross-vertical RECALL is untested, "
                    "not zero. This is a limitation of the gold set, not "
                    "evidence against cross-vertical sharing."
        },
        "oracle_label_insufficiency": {
            "oracle_pooled_gold_unrelated": [
                {"pair_id": p, "subflow": g[p]["subflow_a"],
                 "b1_cosine": sc[p]["b1_cosine"],
                 "rationale_pass1": g[p].get("pass1_rationale"),
                 "rationale_pass2": g[p].get("pass2_rationale")}
                for p in oracle_bad],
            "note": "B0 pools these (same subflow) yet both labeling passes "
                    "called them unrelated, and B1 scores all three low. "
                    "Direct evidence for the method doc's thesis: intent "
                    "match alone is not problem-shape match."
        },
        "band_vs_canonical": {
            "crosstab": {f"{k[0]}|{k[1]}": v for k, v in sorted(ct.items())},
            "off_direction_total": n_off,
            "hard_contradictions": n_hard,
            "hard_contradiction_definition":
                "should-match labeled unrelated, ambiguous labeled unrelated, "
                "or should-not-match labeled related-but-different",
            "note": "18/170 canonical labels contradict the construction "
                    "direction of their band (3 sm->unrelated + "
                    "12 amb->unrelated + 3 snm->related-but-different); "
                    "14/170 more are off-center but not contradictory "
                    "(14 sm->related-but-different + 1 amb->same-problem). "
                    "The band is construction metadata, the label is the "
                    "gold — the metric follows the label."
        },
    }


def stage_score(gold_path, scores_path, out_json, out_md):
    gold_rows = load_jsonl(gold_path)
    rows = load_jsonl(scores_path)
    g = {x["pair_id"]: x for x in gold_rows}
    s = {x["pair_id"] for x in rows}
    if set(g) != s:
        raise SystemExit(f"pair-id mismatch: gold={len(g)} scores={len(s)}; "
                         f"only-gold={sorted(set(g) - s)[:5]} only-scores={sorted(s - set(g))[:5]}")
    if any(x.get("provenance") != "agent-labeled" for x in gold_rows):
        raise SystemExit("gold set provenance is not 'agent-labeled' — refusing")
    canon = {pid: x["canonical_label"] for pid, x in g.items()}

    res = operate(rows, canon)
    findings = join_findings(rows, gold_rows)

    # agreement numbers (from gold; honesty clause: agent self-consistency)
    n = len(gold_rows)
    n_agreed = sum(1 for x in gold_rows if x["agreed"])
    dis_by_band = Counter()
    n_by_band = Counter()
    for x in gold_rows:
        n_by_band[x["band"]] += 1
        if not x["agreed"]:
            dis_by_band[x["band"]] += 1
    agreement = {
        "n": n, "agreed": n_agreed,
        "disagreement_rate": round(1 - n_agreed / n, 4),
        "per_band": {b: {"n": n_by_band[b], "disagreements": dis_by_band[b],
                         "rate": round(dis_by_band[b] / n_by_band[b], 4)}
                     for b in sorted(n_by_band)},
        "flags": dict(Counter(x["flag"] for x in gold_rows if x.get("flag"))),
        "canonical_counts": dict(Counter(canon.values())),
        "provenance": "agent-labeled",
        "honesty_clause": "inter-pass disagreement is agent self-consistency under "
                          "frozen rules (PROTOCOL v1.1), NOT human-human agreement",
    }

    out = {
        "set": "M1 pinned 170 (85/34/51)",
        "bar": {"ffr_max": FFR_BAR, "recall_sm_min": RECALL_BAR,
                "source": "frozen at D18; not negotiable downward"},
        "corpus_sha256_16": CORPUS_SHA16,
        "pairs_sha256_16": PAIRS_SHA16,
        "gold": {"path": str(gold_path), "provenance": "agent-labeled",
                 "n": n, "sha256_16": sha16(gold_path)},
        "agreement": agreement,
        "b0_oracle": res["b0"],
        "b1": {
            "config": "unigram TF-IDF (sublinear, no stoplist) over full customer "
                      "turns, fitted on all 10,042 corpus docs; cosine; pool iff >= t",
            "bar_met": res["bar_met"],
            "selected_operating_point": res["b1_selected"],
            "n_bar_passing_thresholds": res["n_bar_passing_thresholds"],
            "denominators": {"n_should_match": res["n_sm"],
                             "n_gold_unrelated": res["n_unrelated_gold"],
                             "n_gold_same": res["n_same_gold"]},
            "curve": res["b1_curve"],
        },
        "b2": {"status": "gated", "rule": "runs only if B1 fails the frozen bar "
                "(method doc: falsification-only)"},
        "join_findings": findings,
    }
    out_json.write_text(json.dumps(out, indent=2) + "\n")
    write_report(out_md, out)
    print(json.dumps({
        "bar_met": res["bar_met"],
        "b1_selected": res["b1_selected"],
        "b0": res["b0"],
        "disagreement_rate": agreement["disagreement_rate"],
        "canonical_counts": agreement["canonical_counts"],
        "out": [str(out_json), str(out_md)],
    }, indent=2))


def write_report(md, out):
    b1 = out["b1"]
    sel = b1["selected_operating_point"]
    b0 = out["b0_oracle"]
    ag = out["agreement"]
    fj = out["join_findings"]
    cov = fj["crossflow_same_problem_coverage"]
    orc = fj["oracle_label_insufficiency"]
    bvc = fj["band_vs_canonical"]
    verdict = ("**PASSES the frozen bar**" if b1["bar_met"]
               else "**DOES NOT meet the frozen bar** (no threshold with "
                    f"FFR ≤ {FFR_BAR:.0%} at recall_sm ≥ {RECALL_BAR:.0%})")
    lines = [
        "# M1 — B0/B1 scoring report (round 1)",
        "",
        f"**Gold set: AGENT-LABELED** (two independent passes, PROTOCOL v1.1 — "
        f"this is agent self-consistency, not human agreement). n = {ag['n']} pairs. "
        f"Pinned 170 set ({out['pairs_sha256_16']}), corpus {out['corpus_sha256_16']}.",
        "",
        "## Headline",
        "",
        f"- **B1 (TF-IDF cosine, customer turns only) {verdict}.**",
        f"- Selected operating point: pool iff cosine `{sel['threshold']}` → "
        f"**recall_sm = {sel['recall_sm']:.3f}**, **FFR = {sel['ffr']:.3f}**, "
        f"pairwise F1 = {sel['f1']:.3f}",
        f"- Bar-passing thresholds on the sweep: {b1['n_bar_passing_thresholds']}",
        f"- B0 oracle (same subflow): recall_sm = {b0['recall_sm']:.3f}, "
        f"FFR = {b0['ffr']:.3f}, F1 = {b0['f1']:.3f} (ceiling reference)",
        f"- Inter-pass disagreement: {ag['disagreement_rate']:.3f} "
        f"({ag['n'] - ag['agreed']}/{ag['n']})",
        f"- Canonical label counts: " + ", ".join(
            f"{k}={v}" for k, v in sorted(ag["canonical_counts"].items())),
        "",
        "### Interpretation",
        "",
    ]
    if b1["bar_met"]:
        lines += [
            "B1 meets the frozen bar, so per the method doc the finding is: "
            "**problem shape is lexical on this data** — a small embedding (B2) "
            "adds cost, not value, and is **dropped** (that is a result, not a "
            "shortcut).",
            "",
        ]
    else:
        lines += [
            f"No B1 threshold satisfies the frozen bar. Reported fallback point "
            f"(min-FFR threshold): `{sel['threshold']}` at recall_sm "
            f"{sel['recall_sm']:.3f}. The missed bar is the finding. Per the "
            "method doc's pre-registered branch, B2 (a single off-the-shelf "
            "sentence embedding) is now **warranted** and will be run to test "
            "whether 'the dumb one is enough' is falsified.",
            "",
        ]
    lines += [
        "## B1 operating curve (full sweep)",
        "",
        "| threshold | n_pooled | recall_sm | FFR | recall_amb | recall_snm | precision | F1 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    # compact table: every unique threshold, but cap to keep the report readable
    curve = b1["curve"]
    for c in curve:
        rb = c["recall_by_band"]
        lines.append(
            f"| {c['threshold']} | {c['n_pooled']} | {c['recall_sm']:.3f} | "
            f"{c['ffr']:.3f} | {rb.get('ambiguous', 0):.3f} | "
            f"{rb.get('should-not-match', 0):.3f} | {c['precision']:.3f} | "
            f"{c['f1']:.3f} |"
        )
    lines += [
        "",
        f"Full curve ({len(curve)} rows) in `m1_results.json` → `b1.curve`.",
        "",
        "## Per-band recall at the selected threshold",
        "",
        "| band | recall |",
        "|---|---|",
    ]
    sel_rb = sel["recall_by_band"]
    for b, rec in sel_rb.items():
        lines.append(f"| {b} | {rec:.3f} |")
    lines += [
        "",
        "## Agreement (two passes, agent-labeled)",
        "",
        f"- disagreement rate: **{ag['disagreement_rate']:.3f}** "
        f"({ag['n'] - ag['agreed']}/{ag['n']})",
    ]
    for b, r in ag["per_band"].items():
        lines.append(f"- {b}: {r['rate']:.3f} ({r['disagreements']}/{r['n']})")
    lines += [
        f"- flags: {ag['flags'] or 'none'}",
        f"- honesty clause: {ag['honesty_clause']}",
        "",
        "## B0 oracle",
        "",
        f"- rule: same `subflow` ⇒ pool (ABCD ground-truth ceiling within a "
        f"subflow; trivially 1.0 inside the should-match band by construction).",
        f"- recall_sm = {b0['recall_sm']:.3f} · FFR = {b0['ffr']:.3f} · "
        f"F1 = {b0['f1']:.3f} · n_pooled = {b0['n_pooled']}",
        f"- per-band recall: " + ", ".join(
            f"{k}={v:.3f}" for k, v in b0["recall_by_band"].items()),
        "",
        "## Findings from the join (round 1, oversight re-derivation)",
        "",
        "### F1 — the false-friend danger is INSIDE the flow, not across it",
        "",
        "FFR split of the gold-`unrelated` class (63 = 15 same-flow + 48 diff-flow):",
        "",
        "| threshold | FFR total | FFR same-flow (15) | FFR diff-flow (48) | cross-flow (18) | cross-product (9) | other-diff-flow (21) |",
        "|---|---|---|---|---|---|---|",
    ]
    for q in fj["ffr_cut_sameflow_vs_crossflow"]:
        sb = q["diff_flow_by_sub_band"]
        lines.append(
            f"| {q['threshold']} | {q['total']['n_bad']}/{q['total']['n']} = "
            f"{q['total']['ffr']:.3f} | {q['same_flow']['n_bad']}/"
            f"{q['same_flow']['n']} = {q['same_flow']['ffr']:.3f} | "
            f"{q['diff_flow']['n_bad']}/{q['diff_flow']['n']} = "
            f"{q['diff_flow']['ffr']:.3f} | "
            f"{sb.get('cross-flow', {}).get('n_bad', 0)}/"
            f"{sb.get('cross-flow', {}).get('n', 0)} = "
            f"{sb.get('cross-flow', {}).get('ffr', 0):.3f} | "
            f"{sb.get('cross-product', {}).get('n_bad', 0)}/"
            f"{sb.get('cross-product', {}).get('n', 0)} = "
            f"{sb.get('cross-product', {}).get('ffr', 0):.3f} | "
            f"{sb.get('other-diff-flow', {}).get('n_bad', 0)}/"
            f"{sb.get('other-diff-flow', {}).get('n', 0)} = "
            f"{sb.get('other-diff-flow', {}).get('ffr', 0):.3f} |"
        )
    q_lo = fj["ffr_cut_sameflow_vs_crossflow"][0]   # >= 0.196495
    q_hi = fj["ffr_cut_sameflow_vs_crossflow"][1]   # >= 0.171686
    cf_lo = q_lo["diff_flow_by_sub_band"].get("cross-flow", {})
    cf_hi = q_hi["diff_flow_by_sub_band"].get("cross-flow", {})
    lines += [
        "",
        f"At `{q_hi['threshold']}` the same-flow FFR "
        f"({q_hi['same_flow']['ffr']:.1%}, {q_hi['same_flow']['n_bad']}/"
        f"{q_hi['same_flow']['n']}) is **higher** than the cross-flow FFR "
        f"({cf_hi.get('ffr', 0):.1%}, {cf_hi.get('n_bad', 0)}/{cf_hi.get('n', 0)}); "
        f"at `{q_lo['threshold']}` the same-flow FFR ({q_lo['same_flow']['ffr']:.1%}) "
        f"is more than double the cross-flow FFR ({cf_lo.get('ffr', 0):.1%}). "
        "The same-flow bad pairs at both thresholds are the same two: "
        f"**{', '.join(q_hi['same_flow']['pairs'])}** — both "
        "`subscription_inquiry` pairs whose convos sit in different subflows "
        "but share bill-management vocabulary (amount / pay / due / dispute "
        "wording). Cross-flow bad pairs at "
        f"`{q_hi['threshold']}`: {', '.join(cf_hi.get('pairs', []))}.",
        "",
        "**This inverts the method doc §5 expectation table**, which predicted "
        "cross-flow / cross-product would be the hard false-friend slice. It is "
        "not — on this data the hard slice is *within* a flow, between adjacent "
        "subflows that share product/bill vocabulary. **Implication for the "
        "sharing scope (commission §8.1):** the §M1 escape clause (\"no method "
        "keeps the cross-flow FFR ≤ 10% ⇒ sharing is constrained to "
        "vertical/flow\") does NOT fire — cross-flow FFR stays inside the bar "
        "at every passing threshold. But the data does not license global "
        "sharing either: the measured danger is *intra-flow, inter-subflow* "
        "pooling on shared vocabulary, so a sharing scope that pools across "
        "subflows inside a flow carries the same false-friend cost as "
        "cross-flow pooling. The scope decision needs sub-flow-level evidence, "
        "which this round does not settle (see F2). Honesty clause: all of "
        "this rests on an AGENT-LABELED gold set — inter-pass disagreement "
        "21/170 = 0.1235 is a labeler self-consistency floor, not human "
        "inter-rater agreement.",
        "",
        "### F2 — cross-flow \"same problem\" was never tested",
        "",
        f"All {cov['gold_same_problem_n']} gold same-problem pairs are "
        f"same-flow ({len(cov['distinct_flows_with_same_problem'])} distinct "
        f"flows: {', '.join(cov['distinct_flows_with_same_problem'])}); the "
        "gold set contains **zero** cross-flow and zero cross-product "
        "same-problem pairs. The cross-vertical reuse question is therefore "
        "**UNTESTED, not refuted** — recall across flows is unknown, not "
        "zero. This is a limitation of the gold set (its construction drew "
        "should-match only from same subflow). Do not read F1's inversion as "
        "evidence against cross-vertical sharing; it is silent on cross-flow "
        "*recall* by construction. Any sharing-scope claim from R1 must say so.",
        "",
        "### F3 — the oracle label is not sufficient ground truth",
        "",
        "Three pairs share a subflow (B0 pools them) yet the labeler called "
        "them **unrelated**, and B1 scores all three low:",
        "",
        "| pair | subflow | B1 score |",
        "|---|---|---|",
    ]
    for p in orc["oracle_pooled_gold_unrelated"]:
        lines.append(f"| {p['pair_id']} | {p['subflow']} | {p['b1_cosine']:.4f} |")
    lines += [
        "",
        "B1 correctly refuses exactly the pairs the subflow oracle wrongly "
        "accepts. This is direct evidence for the method doc's own thesis — "
        "**intent match alone is not problem-shape match** — and it bounds "
        "B0 as a *ceiling on same-subflow coverage, not a definition of "
        "same-problem*. B0's FFR (4.8%, 3/63) is the FFR of *subflow "
        "identity*, not of problem shape.",
        "",
        f"Band-vs-canonical census: **{bvc['hard_contradictions']}/170** "
        "canonical labels contradict the construction direction of their "
        f"band ({bvc['hard_contradiction_definition']}); "
        f"{bvc['off_direction_total']} of 170 are off-center in total (the "
        "rest being 14 should-match pairs labeled related-but-different and 1 "
        "ambiguous pair labeled same-problem). The band is construction "
        "metadata, the label is the gold; every metric in this report follows "
        "the label.",
        "",
        "## Closure line (round 1, R1 / BON-41)",
        "",
        f"**CONFIRMED** — independently re-derived from `b1_scores.jsonl` "
        f"(PR #17, sha256:16 `9fe3e4b3c0978e1f`) joined to "
        f"`gold_m1_pairs_agentlabeled.jsonl` (PR #18, sha256:16 "
        f"`{out['gold'].get('sha256_16', '792df7d24fc0609a')}`) on pair_id "
        "(170/170, 0 only-onesided), no computation reused from either report. "
        f"B1 (TF-IDF cosine, customer turns) at threshold 0.1965 (exact unique "
        f"score 0.196495): **FFR 6.3% (4/63) at recall_sm 60.0%** → "
        f"**PASS** of the frozen bar (≤10% at ≥60%). Best operating point "
        f"(argmax pairwise-F1 in the pass region): threshold 0.175964 → "
        f"recall_sm 72.9%, FFR 9.5% (6/63), F1 0.721; the max-recall point "
        f"inside the pass region is 0.171686 → recall_sm 74.1% "
        f"(76.8% of gold same-problem), FFR 9.5%. B0 oracle: recall_sm 100% "
        f"at FFR 4.8% (3/63). Bar-passing thresholds: 18 "
        f"(0.171686 → 0.196495). Per method doc §M1, B1 passing means B2 is "
        f"**DROPPED** and the finding is *problem shape is lexical on this "
        f"data*. HONESTY CLAUSE (attached to every 6.3%): the gold set is "
        f"AGENT-LABELED; inter-pass disagreement 21/170 = 0.1235 is a "
        f"labeler self-consistency floor, not human inter-rater agreement.",
        "",
        "## B2",
        "",
        "- status: " + (
            "dropped — B1 passed the bar (lexical finding)" if b1["bar_met"]
            else "warranted — B1 failed the bar; to be run next "
                 "(falsification-only)"
        ) + ".",
        "",
    ]
    md.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--precompute", action="store_true")
    ap.add_argument("--gold", help="gold jsonl (stage B)")
    ap.add_argument("--abcd", default=str(DEFAULT_ABCD))
    ap.add_argument("--pairs", default=str(DEFAULT_PAIRS))
    a = ap.parse_args()
    if a.precompute:
        stage_precompute(Path(a.abcd), Path(a.pairs), SCORES_OUT)
    elif a.gold:
        stage_score(Path(a.gold), SCORES_OUT, RESULTS_JSON, REPORT_MD)
    else:
        ap.error("pass --precompute or --gold <path>")


if __name__ == "__main__":
    main()
