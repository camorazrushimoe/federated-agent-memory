#!/usr/bin/env python3
"""join_verify.py — oversight re-derivation of the M1 round-1 join.

Independently re-derives the R1 numbers (no import of score_m1.py, no
reused computation from either PR report):
  b1_scores.jsonl (PR #17)  JOIN  gold_m1_pairs_agentlabeled.jsonl (PR #18)
  on pair_id.

Plain Python (json/math/collections only). Deterministic, fixed order.
Emits: join_verify_results.json + printed audit lines for every claim
in the oversight message.
"""
import json
import math
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCORES = HERE / "b1_scores.jsonl"
GOLD = HERE / "gold" / "gold_m1_pairs_agentlabeled.jsonl"
OUT = HERE / "join_verify_results.json"

FFR_BAR = 0.10
RECALL_BAR = 0.60


def load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def frac(x):
    # round to 4 dp then to the nearest .1% presentation string
    return round(x, 4)


def pct(x):
    return f"{x * 100:.1f}%"


def main():
    scores = load(SCORES)
    gold = load(GOLD)

    # ---------- 0. join integrity ----------
    s_ids = [r["pair_id"] for r in scores]
    g_ids = [r["pair_id"] for r in gold]
    assert len(set(s_ids)) == len(s_ids), "duplicate pair_id in scores"
    assert len(set(g_ids)) == len(g_ids), "duplicate pair_id in gold"
    n = len(scores)
    matched = len(set(s_ids) & set(g_ids))
    only_scores = sorted(set(s_ids) - set(g_ids))
    only_gold = sorted(set(g_ids) - set(s_ids))
    print(f"join: scores={n} gold={len(gold)} matched={matched} "
          f"only_scores={only_scores} only_gold={only_gold}")
    assert matched == 170 and not only_scores and not only_gold

    # field consistency across the two files (only fields present in BOTH;
    # flow_a/flow_b live only in the gold file — gold is the richer display file)
    smap = {r["pair_id"]: r for r in scores}
    gmap = {r["pair_id"]: r for r in gold}
    field_mismatch = []
    for pid in s_ids:
        s, g = smap[pid], gmap[pid]
        for f in ("band", "conv_a", "conv_b", "sub_band"):
            if s.get(f) != g.get(f):
                field_mismatch.append((pid, f, s.get(f), g.get(f)))
    # flows: gold-only — sanity that they exist and are non-empty strings
    flow_missing = [p for p in s_ids
                    if not (gmap[p].get("flow_a") and gmap[p].get("flow_b"))]
    print(f"cross-file field mismatches (shared fields): {len(field_mismatch)} "
          f"{field_mismatch[:5]} | gold flow fields missing: {len(flow_missing)}")
    assert not field_mismatch and not flow_missing

    # ---------- 1. gold census ----------
    canon = {pid: gmap[pid]["canonical_label"] for pid in s_ids}
    n_by_band = Counter(smap[pid]["band"] for pid in s_ids)
    n_same = sum(1 for v in canon.values() if v == "same-problem")
    n_unrel = sum(1 for v in canon.values() if v == "unrelated")
    n_rbd = sum(1 for v in canon.values() if v == "related-but-different")
    n_agreed = sum(1 for pid in s_ids if gmap[pid]["agreed"])
    n_dis = n - n_agreed
    print(f"canonical: same={n_same} rbd={n_rbd} unrelated={n_unrel} | "
          f"bands={dict(n_by_band)} | agreed={n_agreed} dis={n_dis} "
          f"rate={frac(1 - n_agreed / n)}")

    # ---------- 2. B1 operating curve over full sweep ----------
    sc = {pid: smap[pid]["b1_cosine"] for pid in s_ids}
    sm_set = {pid for pid in s_ids if smap[pid]["band"] == "should-match"}
    unrel_set = {pid for pid in s_ids if canon[pid] == "unrelated"}
    same_set = {pid for pid in s_ids if canon[pid] == "same-problem"}

    def metrics(pooled):
        tp = len(pooled & same_set)
        fp = len(pooled - same_set)
        fn = len(same_set - pooled)
        f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        return {
            "n_pooled": len(pooled),
            "recall_sm": frac(len(pooled & sm_set) / len(sm_set)),
            "ffr": frac(len(pooled & unrel_set) / len(unrel_set)),
            "ffr_abs": (len(pooled & unrel_set), len(unrel_set)),
            "recall_gold_same": frac(len(pooled & same_set) / len(same_set)),
            "recall_by_band": {b: frac(len(pooled & {p for p in s_ids
                                    if smap[p]["band"] == b}) / n_by_band[b])
                               for b in sorted(n_by_band)},
            "precision": frac(tp / (tp + fp)) if (tp + fp) else 0.0,
            "f1": frac(f1), "tp": tp, "fp": fp, "fn": fn,
        }

    curve = [dict(threshold="none (pool nothing)", **metrics(set()))]
    for t in sorted(set(sc.values())):
        pooled = {pid for pid, s in sc.items() if s >= t}
        curve.append(dict(threshold=f">= {t:.6f}", **metrics(pooled)))

    # ---------- 3. the two thresholds quoted by oversight ----------
    # 3a. t = 0.1965 (oversight's pass point; find the exact unique score
    #     nearest 0.1965, and also evaluate at exactly 0.1965)
    uniq = sorted(set(sc.values()))
    near = min(uniq, key=lambda t: abs(t - 0.1965))
    m_1965 = next(c for c in curve if c["threshold"] == f">= {near:.6f}")
    m_1965_exact = metrics({pid for pid, s in sc.items() if s >= 0.1965})
    print(f"t≈0.1965: exact unique score = {near:.6f} -> "
          f"recall_sm={m_1965['recall_sm']} ffr={m_1965['ffr']} "
          f"({m_1965['ffr_abs'][0]}/{m_1965['ffr_abs'][1]}) "
          f"| at literal 0.1965: recall_sm={frac(m_1965_exact['recall_sm'])} "
          f"ffr={frac(m_1965_exact['ffr'])}")

    # 3b. t = 0.1717
    near2 = min(uniq, key=lambda t: abs(t - 0.1717))
    m_1717 = next(c for c in curve if c["threshold"] == f">= {near2:.6f}")
    m_1717_exact = metrics({pid for pid, s in sc.items() if s >= 0.1717})
    print(f"t≈0.1717: exact unique score = {near2:.6f} -> "
          f"recall_sm={m_1717['recall_sm']} ffr={m_1717['ffr']} "
          f"({m_1717['ffr_abs'][0]}/{m_1717['ffr_abs'][1]}) "
          f"recall_gold_same={m_1717['recall_gold_same']} "
          f"| at literal 0.1717: recall_sm={frac(m_1717_exact['recall_sm'])} "
          f"ffr={frac(m_1717_exact['ffr'])}")

    # ---------- 4. bar verdict per pre-registered selection rule ----------
    passing = [c for c in curve if c["ffr"] <= FFR_BAR and c["recall_sm"] >= RECALL_BAR]
    bar_met = bool(passing)
    if passing:
        best = max(c["f1"] for c in passing)
        cands = [c for c in passing if c["f1"] == best]

        def tkey(c):
            if c["threshold"].startswith("none"):
                return (0, 0.0)
            return (1, float(c["threshold"].split(" ", 1)[1]))
        sel = min(cands, key=tkey)
    else:
        sel = min((c for c in curve if not c["threshold"].startswith("none")),
                  key=lambda c: (c["ffr"], -c["recall_sm"]))
    print(f"bar_met={bar_met} n_passing_thresholds={len(passing)} "
          f"selected(=argmax F1 in pass region, tiebreak lowest t) = "
          f"{sel['threshold']} recall_sm={sel['recall_sm']} ffr={sel['ffr']} "
          f"F1={sel['f1']}")

    # ---------- 5. FFR decomposition: cross-flow vs same-flow ----------
    for t_label in (f">= {near:.6f}", f">= {near2:.6f}"):
        c = next(x for x in curve if x["threshold"] == t_label)
        pooled = {pid for pid, s in sc.items() if s >= float(t_label.split(" ", 1)[1])}
        bad = pooled & unrel_set
        xf = [p for p in bad if gmap[p].get("sub_band") == "cross-flow"]
        xp = [p for p in bad if gmap[p].get("sub_band") == "cross-product"]
        of = [p for p in bad if gmap[p].get("sub_band") == "other-diff-flow"]
        amb = [p for p in bad if smap[p]["band"] == "ambiguous"]
        smu = [p for p in bad if smap[p]["band"] == "should-match"]
        denom_xf = sum(1 for p in unrel_set if gmap[p].get("sub_band") == "cross-flow")
        denom_xp = sum(1 for p in unrel_set if gmap[p].get("sub_band") == "cross-product")
        denom_of = sum(1 for p in unrel_set if gmap[p].get("sub_band") == "other-diff-flow")
        denom_amb = sum(1 for p in unrel_set if smap[p]["band"] == "ambiguous")
        denom_smu = sum(1 for p in unrel_set if smap[p]["band"] == "should-match")
        print(f"  [{t_label}] FFR breakdown: cross-flow {len(xf)}/{denom_xf}="
              f"{frac(len(xf) / denom_xf)} {sorted(xf)} | "
              f"cross-product {len(xp)}/{denom_xp}={frac(len(xp) / denom_xp)} | "
              f"other-diff-flow {len(of)}/{denom_of}={frac(len(of) / denom_of)} | "
              f"ambiguous band {len(amb)}/{denom_amb}={frac(len(amb) / denom_amb)} {sorted(amb)} | "
              f"should-match band {len(smu)}/{denom_smu}")

    # ---------- 6. B0 oracle ----------
    b0_pooled = {pid for pid in s_ids if smap[pid]["b0_pool"]}
    b0 = metrics(b0_pooled)
    print(f"B0: n_pooled={b0['n_pooled']} recall_sm={b0['recall_sm']} "
          f"ffr={b0['ffr']} ({b0['ffr_abs'][0]}/{b0['ffr_abs'][1]}) "
          f"recall_by_band={b0['recall_by_band']} F1={b0['f1']}")
    b0_bad = sorted(b0_pooled & unrel_set)
    print(f"B0 false friends: {b0_bad}")
    for p in b0_bad:
        print(f"  {p}: band={smap[p]['band']} sub_band={gmap[p].get('sub_band')} "
              f"flows={gmap[p]['flow_a']}->{gmap[p]['flow_b']} "
              f"subflows={gmap[p]['subflow_a']}->{gmap[p]['subflow_b']}")

    # ---------- 7. oracle-pooled but gold-unrelated (the 3 manage* pairs) ----------
    print("oracle-pooled gold-unrelated detail (expect the 3 manage* pairs):")
    for p in b0_bad:
        print(f"  {p} B1={sc[p]:.6f} band={smap[p]['band']} "
              f"subflow={gmap[p]['subflow_a']}-> {gmap[p]['subflow_b']}")

    # ---------- 8. cross-flow same-problem coverage of the gold set ----------
    crossflow_same = [p for p in s_ids
                      if canon[p] == "same-problem" and gmap[p].get("sub_band") == "cross-flow"]
    crossprod_same = [p for p in s_ids
                      if canon[p] == "same-problem" and gmap[p].get("sub_band") == "cross-product"]
    snm_same = [p for p in s_ids
                if canon[p] == "same-problem" and smap[p]["band"] == "should-not-match"]
    same_flows = Counter((gmap[p]["flow_a"], gmap[p]["flow_b"]) for p in same_set)
    print(f"gold same-problem: n={n_same} | cross-flow={len(crossflow_same)} "
          f"cross-product={len(crossprod_same)} should-not-match-band={len(snm_same)} "
          f"(all same-flow: {all(a == b for a, b in same_flows)})")
    print(f"distinct same-problem flows: {sorted({a for a, b in same_flows})}")

    # ---------- 9. band-vs-canonical disagreements ----------
    # The oversight claim: "18 of 170 canonical labels disagree with the
    # construction band." Compute the natural candidate definitions and
    # report which (if any) yields 18; list the pairs either way.
    ct = Counter((smap[p]["band"], canon[p]) for p in s_ids)
    n_sm_unrel = ct[("should-match", "unrelated")]
    n_sm_rbd = ct[("should-match", "related-but-different")]
    n_amb_unrel = ct[("ambiguous", "unrelated")]
    n_amb_same = ct[("ambiguous", "same-problem")]
    n_snm_rbd = ct[("should-not-match", "related-but-different")]
    n_snm_same = ct[("should-not-match", "same-problem")]
    defs = {
        # D1: label contradicts the band's construction direction
        # (sm built to match -> labeled unrelated; amb built middle ->
        # labeled unrelated; snm built false-friend/unrelated -> labeled rbd)
        "D1 (sm->unrel + amb->unrel + snm->rbd)": n_sm_unrel + n_amb_unrel + n_snm_rbd,
        # D2: any non-same label in sm + any same label in amb + rbd/same in snm
        "D2 (sm->rbd/unrel + amb->same + snm->rbd/same)":
            n_sm_rbd + n_sm_unrel + n_amb_same + n_snm_rbd + n_snm_same,
        # D3: sm labeled rbd + amb labeled same + snm labeled rbd
        "D3 (sm->rbd + amb->same + snm->rbd)": n_sm_rbd + n_amb_same + n_snm_rbd,
        # D4: band's center class vs label class, middle mapped middle
        # (sm<->same, amb<->rbd, snm<->unrelated); any mismatch = disagree
        "D4 (center-class mismatch)": n_sm_rbd + n_sm_unrel + n_amb_unrel
            + n_amb_same + n_snm_rbd + n_snm_same,
        # D5: only sm->unrelated + snm->same (hard contradictions both ways)
        "D5 (sm->unrel + snm->same)": n_sm_unrel + n_snm_same,
    }
    print("band-vs-canonical disagreement definitions (crosstab: "
          + ", ".join(f"{k}={v}" for k, v in sorted(ct.items())) + "):")
    for k, v in defs.items():
        print(f"  {k} = {v}")
    d1_pairs = sorted([p for p in s_ids
                       if (smap[p]["band"], canon[p]) in
                       {("should-match", "unrelated"),
                        ("ambiguous", "unrelated"),
                        ("should-not-match", "related-but-different")}])
    print("D1 pairs (18 expected):")
    for p in d1_pairs:
        print(f"  {p} band={smap[p]['band']} sub_band={gmap[p].get('sub_band')} "
              f"-> {canon[p]} (B1={sc[p]:.6f})")
    n_disagree = len(d1_pairs)
    disagree = [(p, smap[p]["band"], canon[p]) for p in d1_pairs]

    # also: sub_band present iff should-not-match (schema check)
    subband_bad = [p for p in s_ids
                   if (smap[p]["band"] == "should-not-match") != (smap[p].get("sub_band") is not None)]
    print(f"sub_band schema violations: {len(subband_bad)}")

    # ---------- 10. write results ----------
    out = {
        "join": {"n": n, "matched": matched, "only_scores": only_scores,
                 "only_gold": only_gold,
                 "field_mismatches": field_mismatch},
        "gold_census": {"canonical": {"same-problem": n_same,
                                      "related-but-different": n_rbd,
                                      "unrelated": n_unrel},
                        "bands": dict(n_by_band),
                        "agreed": n_agreed, "disagreed": n_dis,
                        "disagreement_rate": frac(1 - n_agreed / n)},
        "bar": {"ffr_max": FFR_BAR, "recall_sm_min": RECALL_BAR,
                "met": bar_met, "n_passing_thresholds": len(passing),
                "selected": sel},
        "t_0.1965": {"exact_unique_score": near, "at_unique": m_1965,
                     "at_literal": m_1965_exact},
        "t_0.1717": {"exact_unique_score": near2, "at_unique": m_1717,
                     "at_literal": m_1717_exact},
        "b0_oracle": b0,
        "crossflow_same_problem": {"n": len(crossflow_same), "pairs": crossflow_same,
                                   "cross_product_same": len(crossprod_same),
                                   "snm_band_same": snm_same},
        "band_vs_canonical_disagreements": {"n": n_disagree, "pairs": disagree},
        "curve": curve,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
