#!/usr/bin/env python3
"""M2 sample draw (R2) — generates research/phase2/m2/sample.jsonl.

Frozen spec (GH #6 comment 5449115746 §3 — PRE-REGISTERED before this draw):
  - N = 80 = 8 per flow x 10 flows, from the 10,042-convo ABCD corpus
  - seed 42, fresh RNG, draw over the convo_id-sorted universe
  - EXCLUDE the 318 convos used by the pinned R1 pair set
    (candidate_pairs.jsonl sha256:16 42215fc5969e600e)
  - <= 2 convos per subflow
  - empty scenario.product convos in [20, 32]

Draw procedure (frozen here; validate_sample.py re-implements it independently):
  1. universe = all corpus convos sorted by convo_id (int)
  2. excluded = {int(conv_a), int(conv_b)} over the pinned pair file (318)
  3. for f in sorted(flows): for s in sorted(subflows(f) among available):
       rng.shuffle(available convos of (f, s) pre-sorted by convo_id)
     (fresh random.Random(42); shuffle order = sorted flows, then sorted
      subflows — this RNG consumption order is part of the frozen procedure)
  4. selection, per flow in sorted order: round-robin over its available
     subflows (alphabetical), at most one pick per subflow per round,
     cycling until 8 drawn (a subflow is skipped when its pool is empty or
     its per-subflow cap is reached).
  5. per-subflow cap = 2 — EXCEPT when a flow has fewer than 4 available
     subflows, where 2 x n_sub < 8 makes the frozen cap infeasible; then
     cap = ceil(8 / n_sub). On this corpus only account_access hits the
     exception (3 subflows -> cap 3). All other flows satisfy cap 2.
     This is a MEASURED DEVIATION, flagged in sample_meta.json,
     validate_sample.py output, and the #6 report — not silent.

Per-row fields (frozen): convo_id, flow, subflow, product_names,
n_action_turns, n_tokens_b0, seed, in_exclusion_set.

  n_action_turns: count of delexed turns with speaker == "action" (D11).
  n_tokens_b0:    the FROZEN token counter — whitespace-split tokens of the
                  B0 render: all `original` turns as "speaker: text",
                  space-joined.
  in_exclusion_set: true iff the convo_id is in the R1 318-convo excluded
                  set. Every sampled row MUST be false (the validator
                  re-checks this against the pinned pair file).

Deterministic: byte-identical output on re-run (no timestamps, no dicts
iterated without sorting). Stdlib only.

Usage:
  python3 research/phase2/m2/sample.py \
      --corpus data/abcd/abcd_v1.1.json \
      --pairs research/phase2/m1/candidate_pairs.jsonl \
      --out research/phase2/m2/sample.jsonl
"""
import argparse
import hashlib
import json
import math
import random
from collections import Counter


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def n_tokens_b0(convo):
    """Frozen counter: whitespace-split of all original turns as 'speaker: text'."""
    rendered = " ".join(f"{sp}: {tx}" for sp, tx in convo["original"])
    return len(rendered.split())


def n_action_turns(convo):
    return sum(1 for t in convo.get("delexed", []) if t.get("speaker") == "action")


def product_names(convo):
    return list((convo["scenario"].get("product") or {}).get("names") or [])


def draw(corpus, pairs, seed=42):
    """Frozen draw. Returns (chosen convos in draw order, per-flow subflow counts)."""
    universe = sorted(corpus, key=lambda c: c["convo_id"])
    excluded = set()
    for p in pairs:
        excluded.add(int(p["conv_a"]))
        excluded.add(int(p["conv_b"]))

    flows = sorted({c["scenario"]["flow"] for c in universe})
    rng = random.Random(seed)

    # step 3: pre-shuffled per-(flow, subflow) pools (RNG consumption order frozen)
    pools = {}
    for f in flows:
        subs = sorted({c["scenario"]["subflow"] for c in universe
                       if c["scenario"]["flow"] == f and c["convo_id"] not in excluded})
        for s in subs:
            lst = [c for c in universe
                   if c["scenario"]["flow"] == f
                   and c["scenario"]["subflow"] == s
                   and c["convo_id"] not in excluded]
            # universe is convo_id-sorted; sort is stable-explicit for clarity
            lst.sort(key=lambda c: c["convo_id"])
            rng.shuffle(lst)
            pools[(f, s)] = lst

    chosen = []
    subflow_counts = Counter()
    caps = {}
    for f in flows:
        subs = sorted({c["scenario"]["subflow"] for c in universe
                       if c["scenario"]["flow"] == f and c["convo_id"] not in excluded})
        cap = 2 if len(subs) >= 4 else math.ceil(8 / len(subs))
        caps[f] = cap
        per_sub = Counter()
        idx = 0
        drawn = 0
        while drawn < 8:
            if idx >= 10 * len(subs):  # safety: pool exhaustion -> hard error below
                raise RuntimeError(
                    f"flow {f}: draw stuck at {drawn}/8 (pools exhausted or caps infeasible)")
            s = subs[idx % len(subs)]
            idx += 1
            if per_sub[s] >= cap or not pools[(f, s)]:
                continue
            c = pools[(f, s)].pop(0)
            chosen.append(c)
            per_sub[s] += 1
            subflow_counts[(f, s)] += 1
            drawn += 1
    return chosen, subflow_counts, caps, excluded, len(excluded)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/abcd/abcd_v1.1.json")
    ap.add_argument("--pairs", default="research/phase2/m1/candidate_pairs.jsonl")
    ap.add_argument("--out", default="research/phase2/m2/sample.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    # pinned-input integrity (pre-registration pins)
    corpus_sha = sha16(args.corpus)
    pairs_sha = sha16(args.pairs)
    assert corpus_sha == "005d425e890b30a1", f"corpus sha mismatch: {corpus_sha}"
    assert pairs_sha == "42215fc5969e600e", f"R1 pair file sha mismatch: {pairs_sha}"

    corpus = json.load(open(args.corpus))
    convos = corpus["train"] + corpus["dev"] + corpus["test"]
    pairs = [json.loads(l) for l in open(args.pairs)]

    chosen, subflow_counts, caps, excluded, n_excluded = draw(convos, pairs, args.seed)

    rows = []
    for c in sorted(chosen, key=lambda c: c["convo_id"]):
        rows.append({
            "convo_id": c["convo_id"],
            "flow": c["scenario"]["flow"],
            "subflow": c["scenario"]["subflow"],
            "product_names": product_names(c),
            "n_action_turns": n_action_turns(c),
            "n_tokens_b0": n_tokens_b0(c),
            "seed": args.seed,
            "in_exclusion_set": c["convo_id"] in excluded,
        })
    assert len(rows) == 80 and len({r["convo_id"] for r in rows}) == 80

    with open(args.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    sample_sha = sha16(args.out)

    # ---- meta (deterministic content; no timestamps) ----
    per_flow = Counter(r["flow"] for r in rows)
    empty = sum(1 for r in rows if not r["product_names"])
    toks = sorted(r["n_tokens_b0"] for r in rows)
    median = (toks[39] + toks[40]) / 2
    p95 = toks[math.ceil(0.95 * len(toks)) - 1]  # nearest-rank
    meta = {
        "artifact": "research/phase2/m2/sample.jsonl",
        "round": "R2 (M2 extraction) — sample pre-registered on GH #6 5449115746 §3",
        "created": "2026-08-28",
        "seed": args.seed,
        "n_universe": len(convos),
        "n_excluded_r1": n_excluded,
        "n_sample": len(rows),
        "corpus": args.corpus,
        "corpus_sha256_16": corpus_sha,
        "r1_pair_file": args.pairs,
        "r1_pair_file_sha256_16": pairs_sha,
        "draw_procedure": (
            "fresh random.Random(seed); universe convo_id-sorted; per-(flow,subflow) "
            "available pools pre-sorted by convo_id then rng.shuffle'd in sorted-flow/"
            "sorted-subflow order; per flow in sorted order: round-robin over "
            "alphabetical available subflows, 1 pick/subflow/round, cycle to 8"
        ),
        "per_subflow_cap": 2,
        "caps": caps,
        "per_flow": dict(sorted(per_flow.items())),
        "subflow_counts": {f"{f}|{s}": n for (f, s), n in sorted(subflow_counts.items())},
        "empty_product": empty,
        "empty_product_window": [20, 32],
        "b1_coverage": {
            "convo_with_ge1_action_turn": sum(1 for r in rows if r["n_action_turns"] >= 1),
            "n": len(rows),
        },
        "tokens_b0": {
            "median": median, "p95_nearest_rank": p95, "min": toks[0], "max": toks[-1],
        },
        "deviations": [
            "account_access per-subflow cap = 3 (ceil(8/3)) instead of frozen 2: the "
            "flow has exactly 3 subflows, so cap 2 admits at most 6 < 8 convos — the "
            "frozen pair (8/flow, <=2/subflow) is jointly infeasible for that flow on "
            "this corpus. Minimal relaxation: per-subflow cap raised to ceil(8/n_sub) "
            "ONLY for flows with < 4 subflows. All other 9 flows satisfy cap 2. "
            "Flagged for lead adjudication on the sample PR; every other frozen "
            "constraint (N=80, 8/flow, seed 42, R1-318 exclusion, empty window) is "
            "satisfied exactly."
        ],
        "sample_sha256_16": sample_sha,
    }
    meta_path = args.out + ".meta.json"
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, indent=1, sort_keys=False)
        fh.write("\n")

    print(f"sample:        {args.out}  (sha256:16 {sample_sha})")
    print(f"meta:          {meta_path}")
    print(f"n_sample=80  n_excluded={n_excluded}  empty_product={empty}  "
          f"median={median}  p95={p95}")
    for f in sorted(per_flow):
        row = {s: n for (ff, s), n in subflow_counts.items() if ff == f}
        print(f"  {f:22s} {row}")


if __name__ == "__main__":
    main()
