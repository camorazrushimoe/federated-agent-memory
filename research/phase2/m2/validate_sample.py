#!/usr/bin/env python3
"""M2 sample validator (R2) — independent re-derivation + frozen-invariant checks.

Re-implements the frozen draw procedure (GH #6 5449115746 §3, as frozen in
sample.py's docstring) INDEPENDENTLY (no import of sample.py), re-derives the
expected 80-convo set, and checks the committed sample.jsonl against:

  A. pinned inputs: corpus sha256:16 005d425e890b30a1; R1 pair file sha
     42215fc5969e600e; the R1 excluded set re-derived from the pair file = 318
  B. re-derived set == committed set (exact, order-independent)
  C. schema: exactly the 8 frozen fields per row
  D. N = 80; unique convo_ids; every id present in the corpus
  E. per flow: exactly 8 for all 10 flows
  F. zero overlap with the R1 318-convo excluded set; in_exclusion_set is
     false on every row
  G. subflow cap: count <= cap(flow) for every (flow, subflow), where
     cap = 2 for flows with >= 4 available subflows and ceil(8/n_sub) for
     flows with < 4 (the documented account_access deviation, cap 3); the
     deviation must apply ONLY where infeasibility actually holds
  H. empty scenario.product count in [20, 32]
  I. seed field == 42 on every row
  J. n_action_turns and n_tokens_b0 equal an independent recomputation from
     the corpus (frozen counter: whitespace-split of "speaker: text" over all
     original turns; D11 action turns from delexed speaker=="action")

Stdlib only. Exit 0 with "VERDICT: PASS" iff every check passes; otherwise
lists failures and exits 1.

Usage:
  python3 research/phase2/m2/validate_sample.py \
      --corpus data/abcd/abcd_v1.1.json \
      --pairs research/phase2/m1/candidate_pairs.jsonl \
      --sample research/phase2/m2/sample.jsonl
"""
import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter

CORPUS_SHA = "005d425e890b30a1"
PAIRS_SHA = "42215fc5969e600e"
FROZEN_FIELDS = ["convo_id", "flow", "subflow", "product_names",
                 "n_action_turns", "n_tokens_b0", "seed", "in_exclusion_set"]
N_SAMPLE = 80
PER_FLOW = 8
EMPTY_WINDOW = (20, 32)


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def n_tokens_b0(convo):
    return len(" ".join(f"{sp}: {tx}" for sp, tx in convo["original"]).split())


def n_action_turns(convo):
    return sum(1 for t in convo.get("delexed", []) if t.get("speaker") == "action")


def product_names(convo):
    return list((convo["scenario"].get("product") or {}).get("names") or [])


def independent_draw(convos, excluded, seed=42):
    """Independent re-implementation of the frozen draw (do NOT import sample.py)."""
    universe = sorted(convos, key=lambda c: c["convo_id"])
    flows = sorted({c["scenario"]["flow"] for c in universe})
    rng = random.Random(seed)
    pools = {}
    for f in flows:
        subs = sorted({c["scenario"]["subflow"] for c in universe
                       if c["scenario"]["flow"] == f and c["convo_id"] not in excluded})
        for s in subs:
            lst = [c for c in universe
                   if c["scenario"]["flow"] == f
                   and c["scenario"]["subflow"] == s
                   and c["convo_id"] not in excluded]
            lst.sort(key=lambda c: c["convo_id"])
            rng.shuffle(lst)
            pools[(f, s)] = lst
    chosen = []
    for f in flows:
        subs = sorted({c["scenario"]["subflow"] for c in universe
                       if c["scenario"]["flow"] == f and c["convo_id"] not in excluded})
        cap = 2 if len(subs) >= 4 else math.ceil(8 / len(subs))
        per_sub = Counter()
        idx, drawn = 0, 0
        while drawn < PER_FLOW:
            if idx >= 10 * len(subs):
                raise RuntimeError(f"flow {f}: draw stuck at {drawn}/8")
            s = subs[idx % len(subs)]
            idx += 1
            if per_sub[s] >= cap or not pools[(f, s)]:
                continue
            c = pools[(f, s)].pop(0)
            chosen.append(c)
            per_sub[s] += 1
            drawn += 1
    return chosen, {f: (2 if len([s for s in sorted({c["scenario"]["subflow"] for c in universe
                                                    if c["scenario"]["flow"] == f
                                                    and c["convo_id"] not in excluded})]) >= 4
                       else math.ceil(8 / len([s for s in sorted({c["scenario"]["subflow"] for c in universe
                                                                  if c["scenario"]["flow"] == f
                                                                  and c["convo_id"] not in excluded})]))
                    ) for f in flows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/abcd/abcd_v1.1.json")
    ap.add_argument("--pairs", default="research/phase2/m1/candidate_pairs.jsonl")
    ap.add_argument("--sample", default="research/phase2/m2/sample.jsonl")
    args = ap.parse_args()

    failures = []
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        if not ok:
            failures.append(f"{name}: {detail}")

    # A. pinned inputs
    csha = sha16(args.corpus)
    psha = sha16(args.pairs)
    check("A1 corpus pinned sha", csha == CORPUS_SHA, f"got {csha}, want {CORPUS_SHA}")
    check("A2 R1 pair file pinned sha", psha == PAIRS_SHA, f"got {psha}, want {PAIRS_SHA}")

    corpus = json.load(open(args.corpus))
    convos = corpus["train"] + corpus["dev"] + corpus["test"]
    by_id = {c["convo_id"]: c for c in convos}
    pairs = [json.loads(l) for l in open(args.pairs)]
    excluded = {int(p["conv_a"]) for p in pairs} | {int(p["conv_b"]) for p in pairs}
    check("A3 R1 excluded set size", len(excluded) == 318, f"got {len(excluded)}")

    rows = [json.loads(l) for l in open(args.sample)]

    # C. schema
    schema_ok, bad_rows = True, []
    for i, r in enumerate(rows):
        if list(r.keys()) != FROZEN_FIELDS:
            schema_ok = False
            bad_rows.append((i, list(r.keys())))
    check("C exact 8-field schema (order)", schema_ok, f"bad rows: {bad_rows[:3]}")

    # D. N, uniqueness, corpus membership
    ids = [r["convo_id"] for r in rows]
    check("D1 N == 80", len(rows) == N_SAMPLE, f"got {len(rows)}")
    check("D2 unique convo_ids", len(set(ids)) == len(ids), f"{len(rows) - len(set(ids))} dupes")
    missing = [i for i in ids if i not in by_id]
    check("D3 all ids in corpus", not missing, f"missing: {missing[:5]}")

    # E. per-flow = 8 for all 10 flows
    per_flow = Counter(r["flow"] for r in rows)
    flows = sorted({c["scenario"]["flow"] for c in convos})
    check("E1 exactly 10 flows present", sorted(per_flow) == flows, f"{sorted(per_flow)}")
    check("E2 8 per flow", all(n == PER_FLOW for n in per_flow.values()),
          f"{dict(per_flow)}")

    # F. exclusion
    overlap = set(ids) & excluded
    check("F1 zero overlap with R1 318", not overlap, f"overlap: {sorted(overlap)[:5]}")
    flags = [r["convo_id"] for r in rows if r["in_exclusion_set"] is not False]
    check("F2 in_exclusion_set false on all rows", not flags, f"rows: {flags[:5]}")

    # G. subflow cap (with the documented deviation rule)
    avail_subflows = {}
    for f in flows:
        avail_subflows[f] = sorted({c["scenario"]["subflow"] for c in convos
                                    if c["scenario"]["flow"] == f and c["convo_id"] not in excluded})
    caps = {f: (2 if len(avail_subflows[f]) >= 4 else math.ceil(PER_FLOW / len(avail_subflows[f])))
            for f in flows}
    sub_counts = Counter((r["flow"], r["subflow"]) for r in rows)
    cap_viol = {f"{f}|{s}": n for (f, s), n in sub_counts.items() if n > caps[f]}
    check("G1 per-subflow counts <= cap", not cap_viol, f"violations: {cap_viol}")
    dev_flows = {f: n for f, n in caps.items() if n > 2}
    check("G2 deviation only where infeasible (< 4 subflows)",
          all(len(avail_subflows[f]) < 4 for f in dev_flows), f"dev_flows: {dev_flows}")
    check("G3 no flow has < 4 subflows yet cap left at 2",
          all(caps[f] == 2 for f in flows if len(avail_subflows[f]) >= 4),
          f"caps: {caps}")

    # H. empty-product window
    empty = sum(1 for r in rows if not r["product_names"])
    check("H empty-product in [20, 32]", EMPTY_WINDOW[0] <= empty <= EMPTY_WINDOW[1],
          f"got {empty}")

    # I. seed
    check("I seed == 42 on all rows", all(r["seed"] == 42 for r in rows),
          f"seeds: {sorted({r['seed'] for r in rows})}")

    # J. field values vs independent recompute
    bad_prod, bad_act, bad_tok = [], [], []
    for r in rows:
        c = by_id.get(r["convo_id"])
        if c is None:
            continue
        if r["product_names"] != product_names(c):
            bad_prod.append(r["convo_id"])
        if r["flow"] != c["scenario"]["flow"] or r["subflow"] != c["scenario"]["subflow"]:
            bad_prod.append(r["convo_id"])
        if r["n_action_turns"] != n_action_turns(c):
            bad_act.append(r["convo_id"])
        if r["n_tokens_b0"] != n_tokens_b0(c):
            bad_tok.append(r["convo_id"])
    check("J1 product_names/flow/subflow match corpus", not bad_prod, f"{bad_prod[:5]}")
    check("J2 n_action_turns match recompute", not bad_act, f"{bad_act[:5]}")
    check("J3 n_tokens_b0 match frozen counter recompute", not bad_tok, f"{bad_tok[:5]}")

    # B. re-derived set == committed set
    derived, _ = independent_draw(convos, excluded, seed=42)
    derived_ids = {c["convo_id"] for c in derived}
    only_sample = sorted(set(ids) - derived_ids)
    only_derived = sorted(derived_ids - set(ids))
    check("B re-derived set == committed set", not only_sample and not only_derived,
          f"only_sample={only_sample[:5]} only_derived={only_derived[:5]}")

    # ---- report ----
    print("validate_sample.py — M2 sample (R2), independent re-derivation")
    print(f"  corpus {args.corpus} sha256:16 {csha}")
    print(f"  R1 pairs {args.pairs} sha256:16 {psha} (excluded {len(excluded)})")
    print(f"  sample {args.sample} sha256:16 {sha16(args.sample)}  rows {len(rows)}")
    print("-" * 72)
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail and not ok else ""))
    print("-" * 72)
    # reportable summary (for the #6 report; deterministic)
    toks = sorted(r["n_tokens_b0"] for r in rows)
    median = (toks[39] + toks[40]) / 2
    p95 = toks[math.ceil(0.95 * len(toks)) - 1]
    b1c = sum(1 for r in rows if r["n_action_turns"] >= 1)
    print(f"  per_flow: " + ", ".join(f"{f}={per_flow.get(f, 0)}" for f in flows))
    print(f"  subflow cap rule: " + ", ".join(f"{f}={caps[f]}" for f in flows))
    print(f"  per-flow/subflow counts:")
    for f in flows:
        row = {s: n for (ff, s), n in sorted(sub_counts.items()) if ff == f}
        print(f"    {f:22s} {row}")
    print(f"  empty_product: {empty} (window {EMPTY_WINDOW})")
    print(f"  B1 coverage (>=1 action turn): {b1c}/80")
    print(f"  tokens_b0: median {median}, p95(nearest-rank) {p95}, min {toks[0]}, max {toks[-1]}")
    print(f"  R1 overlap: {len(set(ids) & excluded)}")
    print("-" * 72)
    if failures:
        print(f"VERDICT: FAIL ({len(failures)} failed check(s))")
        for f in failures:
            print(f"  FAIL {f}")
        sys.exit(1)
    print("VERDICT: PASS (all checks; re-derived set identical to committed)")
    sys.exit(0)


if __name__ == "__main__":
    main()
