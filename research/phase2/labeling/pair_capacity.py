#!/usr/bin/env python3
"""pair_capacity.py — M1 pair-construction feasibility from the ABCD corpus.

Answer, BEFORE the engineer builds pairs: how many pairs can each band
actually supply, from which flows/subflows, and what is thin.

Usage: python3 pair_capacity.py [--corpus ...] [--mapping ...] [--out ...]

Deterministic; output is committed (research/phase2/labeling/pair_capacity.json
+ .md) so the engineer's stratification can be checked against the ceiling.
"""
import argparse
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

CORPUS = "/opt/data/fam-r2/data/abcd/abcd_v1.1.json"
MAPPING = "/opt/data/fam-r2/research/abcd_subflow_mapping.json"
OUT = Path(__file__).parent / "pair_capacity.json"


def prod_key(s):
    p = s.get("product")
    if p is None:
        return "?"
    if isinstance(p, (list, dict)):
        return json.dumps(p, sort_keys=True, default=str)[:80]
    return str(p)


def prod_empty(s):
    p = s.get("product")
    if p is None:
        return True
    if isinstance(p, dict):
        return not any(p.values())
    if isinstance(p, (list, tuple)):
        return len(p) == 0
    return str(p).strip() in ("", "?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--mapping", default=MAPPING)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    data = json.load(open(a.corpus))
    convs = []
    for split in ("train", "dev", "test"):
        for c in data[split]:
            convs.append((split, c))

    by_sub, by_flow, by_prod = Counter(), Counter(), Counter()
    flow_subs = {}
    for split, c in convs:
        s = c["scenario"]
        by_sub[s["subflow"]] += 1
        by_flow[s["flow"]] += 1
        by_prod[prod_key(s)] += 1
        flow_subs.setdefault(s["flow"], set()).add(s["subflow"])

    empty_prod = sum(1 for _, c in convs if prod_empty(c["scenario"]))

    n = len(convs)
    # ceilings (combinations, no reuse across pairs in practice — these are
    # theoretical maxima; the engineer will sample, not exhaust)
    sm_max = sum(v * (v - 1) // 2 for v in by_sub.values())
    amb_max = 0
    for f, subs in flow_subs.items():
        c = Counter()
        for split, c_ in convs:
            if c_["scenario"]["flow"] == f:
                c[c_["scenario"]["subflow"]] += 1
        tot = sum(c.values())
        same_sub = sum(v * (v - 1) // 2 for v in c.values())
        amb_max += tot * (tot - 1) // 2 - same_sub
    snm_max = n * (n - 1) // 2 - sum(v * (v - 1) // 2 for v in by_flow.values())

    subflow_stats = sorted(
        ({"subflow": k, "conversations": v,
          "max_pairs_same_subflow": v * (v - 1) // 2,
          "flow": next(c["scenario"]["flow"] for _, c in convs
                       if c["scenario"]["subflow"] == k)}
         for k, v in by_sub.items()),
        key=lambda x: -x["conversations"])

    out = {
        "corpus": a.corpus,
        "n_conversations": n,
        "splits": {s: sum(1 for x, _ in convs if x == s)
                   for s in ("train", "dev", "test")},
        "n_flows": len(by_flow),
        "n_subflows": len(by_sub),
        "products": dict(by_prod.most_common()),
        "flows": {f: {"conversations": v, "n_subflows": len(flow_subs[f])}
                  for f, v in sorted(by_flow.items(), key=lambda kv: -kv[1])},
        "subflows": subflow_stats,
        "pair_ceiling_theoretical": {
            "should-match (same subflow)": sm_max,
            "ambiguous (diff subflow, same flow)": amb_max,
            "should-not-match (cross-flow, includes cross-product)": snm_max,
            "note": "theoretical max without reusing conversations; engineer samples a stratified ~150-200",
        },
        "thin_subflows_under_5": sum(1 for s in subflow_stats if s["conversations"] < 5),
        "thin_subflows_under_2": sum(1 for s in subflow_stats if s["conversations"] < 2),
        "empty_product_conversations": empty_prod,
        "flows_with_single_subflow": [f for f in flow_subs if len(flow_subs[f]) == 1],
        "mapping_rows": (len(json.load(open(a.mapping)).get("mapping", []))
                         if isinstance(json.load(open(a.mapping)), dict)
                         else len(json.load(open(a.mapping)))),
    }
    Path(a.out).write_text(json.dumps(out, indent=2) + "\n")

    md = ["# M1 Pair-Construction Capacity (computed from the corpus, not assumed)",
          "",
          f"- conversations: **{n}** ({out['splits']['train']}/{out['splits']['dev']}/{out['splits']['test']}) · flows **{out['n_flows']}** · subflows **{out['n_subflows']}**",
          "- products (distinct `scenario.product` values): " +
          ", ".join(f"`{k[:40]}`={v}" for k, v in by_prod.most_common(10)) +
          (f" (+{len(by_prod)-10} more)" if len(by_prod) > 10 else ""),
          f"- subflows with <5 conversations: **{out['thin_subflows_under_5']}** (of {out['n_subflows']}); <2 (cannot form any same-subflow pair): **{out['thin_subflows_under_2']}**",
          f"- flows with a single subflow (no ambiguous-band pairs inside): {out['flows_with_single_subflow']}",
          f"- **FINDING — empty `scenario.product`: {empty_prod} conversations "
          f"({empty_prod/n:.1%}) have `product = {{amounts: [], names: []}}`. A "
          f"cross-*product* sub-band can only be constructed from the "
          f"{n-empty_prod} conversations that carry a non-empty product. Pre-registered rule "
          f"for evaluation: a pair whose either side has an empty product is judged "
          f"on problem shape only (rule R3) and is NOT auto-assigned to the "
          f"cross-product sub-band.",
          "",
          "## Pair ceilings (theoretical max, no conversation reuse)",
          "",
          "| band | ceiling |",
          "|---|---|",
          f"| should-match (same subflow) | {sm_max:,} |",
          f"| ambiguous (diff subflow, same flow) | {amb_max:,} |",
          f"| should-not-match (cross-flow, incl. cross-product) | {snm_max:,} |",
          "",
          "## Flows",
          "",
          "| flow | conversations | subflows |",
          "|---|---|---|"]
    for f, v in sorted(by_flow.items(), key=lambda kv: -kv[1]):
        md.append(f"| {f} | {v} | {len(flow_subs[f])} |")
    md += ["", "## Subflows (sorted by size)", "",
           "| subflow | flow | conversations | max same-subflow pairs |",
           "|---|---|---|---|"]
    for s in subflow_stats:
        md.append(f"| {s['subflow']} | {s['flow']} | {s['conversations']} | {s['max_pairs_same_subflow']} |")
    md += ["",
           "_Computed by `pair_capacity.py` (deterministic; re-run to reproduce). "
           "Purpose: the engineer's stratification must fit under these ceilings; "
           "evaluation checks the delivered `candidate_pairs.jsonl` against them._"]
    Path(str(a.out).replace(".json", ".md")).write_text("\n".join(md) + "\n")
    print(json.dumps(out["pair_ceiling_theoretical"], indent=2))
    print("flows:", out["n_flows"], "subflows:", out["n_subflows"],
          "thin<5:", out["thin_subflows_under_5"], "thin<2:", out["thin_subflows_under_2"])
    print("wrote", a.out)


if __name__ == "__main__":
    main()
