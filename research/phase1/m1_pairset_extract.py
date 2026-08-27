#!/usr/bin/env python3
"""PHASE 2 / R1 prep — M1 pair-set extractor (lead-owned, BON-38).

Builds the candidate set for the human gold labeling (method doc §M1).
Deterministic: fixed seed, fixed band sizes, stable sort — the same machine
always produces the same candidate pairs. Nothing here is a *label*; the
labels come from the two-pass human process (lead + evaluation).

Bands (method doc §M1, pre-registered):
  A  should-match        : same subflow, different conversation
  B  ambiguous           : different subflow, same flow
  C  should-not-match    : different flow (the false-friend band)

Pre-registered band sizes: A=80, B=50, C=40  (total 170, inside 150–200).

Usage (post-merge main; also runs against local findings/ dir):
  python m1_pairset_extract.py --abcd data/abcd/abcd_v1.1.json \
      [--seed 42] [--band-a 80 --band-b 50 --band-c 40] [--no-text]
  -> writes research/phase1/m1_pairset_candidates.json

Reproducibility: output carries seed + band sizes + generator version; the
labeling process re-runs this file to regenerate the identical candidate set.
"""
import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict


def load_convos(path):
    data = json.load(open(path))
    convos = []
    for split in ("train", "dev", "test"):
        if split in data:
            convos.extend(data[split])
    return convos


def customer_text(c):
    """Customer turns only, delexed (agent boilerplate excluded — method B1 rule)."""
    turns = [t.get("text", "").strip()
             for t in c.get("delexed", [])
             if isinstance(t, dict) and t.get("speaker") == "customer"
             and t.get("text")]
    return " | ".join(t for t in turns if t)


def band_pairs(convos_by_subflow, convos_by_flow, rng, size_a, size_b, size_c):
    """Draw (convo_id_a, convo_id_b, band) triples deterministically."""
    pairs = []

    # Band A — same subflow, different conversation.
    a_candidates = []
    for sf, lst in sorted(convos_by_subflow.items()):
        ids = sorted(c["convo_id"] for c in lst)
        if len(ids) < 2:
            continue
        for i in range(len(ids) - 1):
            a_candidates.append((ids[i], ids[i + 1], sf, "adjacent"))
        # also some long-range pairs for surface diversity
        if len(ids) >= 3:
            a_candidates.append((ids[0], ids[-1], sf, "longrange"))
    rng.shuffle(a_candidates)
    for a, b, sf, _ in a_candidates[:size_a]:
        pairs.append({"band": "A", "convo_id_a": a, "convo_id_b": b,
                      "subflow": sf})

    # Band B — different subflow, same flow.
    b_candidates = []
    for fl, lst in sorted(convos_by_flow.items()):
        by_sf = defaultdict(list)
        for c in lst:
            by_sf[c["scenario"]["subflow"]].append(c["convo_id"])
        sf_ids = sorted(s for s, v in by_sf.items() if len(v) >= 1)
        for i in range(len(sf_ids)):
            for j in range(i + 1, len(sf_ids)):
                la, lb = sorted(by_sf[sf_ids[i]]), sorted(by_sf[sf_ids[j]])
                b_candidates.append((la[0], lb[0], sf_ids[i], sf_ids[j], fl))
    rng.shuffle(b_candidates)
    for a, b, sfa, sfb, fl in b_candidates[:size_b]:
        pairs.append({"band": "B", "convo_id_a": a, "convo_id_b": b,
                      "subflow_a": sfa, "subflow_b": sfb, "flow": fl})

    # Band C — different flow.
    flows = sorted(convos_by_flow.keys())
    flow_ids = {fl: sorted(c["convo_id"] for c in convos_by_flow[fl]) for fl in flows}
    c_candidates = []
    for i in range(len(flows)):
        for j in range(i + 1, len(flows)):
            la, lb = flow_ids[flows[i]], flow_ids[flows[j]]
            for pos in (0, len(la) // 2, len(la) - 1):
                c_candidates.append((la[pos], lb[min(pos, len(lb) - 1)],
                                     flows[i], flows[j]))
    rng.shuffle(c_candidates)
    for a, b, fi, fj in c_candidates[:size_c]:
        pairs.append({"band": "C", "convo_id_a": a, "convo_id_b": b,
                      "flow_a": fi, "flow_b": fj})

    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--abcd", required=True)
    ap.add_argument("--out", default="research/phase1/m1_pairset_candidates.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--band-a", type=int, default=80)
    ap.add_argument("--band-b", type=int, default=50)
    ap.add_argument("--band-c", type=int, default=40)
    ap.add_argument("--no-text", action="store_true",
                    help="omit customer text (for a compact candidate manifest)")
    args = ap.parse_args()

    convos = load_convos(args.abcd)
    by_id = {c["convo_id"]: c for c in convos}
    by_sf, by_fl = defaultdict(list), defaultdict(list)
    for c in convos:
        sc = c["scenario"]
        by_sf[sc["subflow"]].append(c)
        by_fl[sc["flow"]].append(c)

    rng = random.Random(args.seed)
    pairs = band_pairs(by_sf, by_fl, rng,
                       args.band_a, args.band_b, args.band_c)

    # de-dupe on (a,b) unordered, keep first band hit, stable order
    seen, uniq = set(), []
    for p in pairs:
        key = (min(p["convo_id_a"], p["convo_id_b"]),
               max(p["convo_id_a"], p["convo_id_b"]))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)

    # Identity hash = f(band, unordered convo-id pair) ONLY — text excluded so the
    # candidate set's fingerprint is stable regardless of --no-text.
    ident = sorted((p["band"],
                    min(p["convo_id_a"], p["convo_id_b"]),
                    max(p["convo_id_a"], p["convo_id_b"])) for p in uniq)
    h = hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()

    for p in uniq:
        a, b = by_id[p["convo_id_a"]], by_id[p["convo_id_b"]]
        p["flow_a"] = p.get("flow_a") or a["scenario"]["flow"]
        p["flow_b"] = p.get("flow_b") or b["scenario"]["flow"]
        p["n_turns_a"] = len(a["delexed"])
        p["n_turns_b"] = len(b["delexed"])
        if not args.no_text:
            p["customer_text_a"] = customer_text(a)
            p["customer_text_b"] = customer_text(b)

    out = {
        "description": (
            "M1 candidate pair set for the two-pass gold labeling "
            "(BON-38, method doc §M1; labeling protocol per DECIDED D19). "
            "Candidate set only — labels are added by the labeling process, "
            "never here. Labeler of record: lab-1-evaluation (independent "
            "measurer, DECIDED D19): two independent passes, per-item labels "
            "committed, inter-pass disagreement reported as a number; "
            "escalate a 20-item sample to a human only if disagreement > 15%. "
            "All sets are marked 'agent-labeled' — never 'human gold'."),
        "generator": "m1_pairset_extract.py v1",
        "seed": args.seed,
        "band_sizes": {"A": args.band_a, "B": args.band_b, "C": args.band_c},
        "label_scale": ["same-problem", "related-but-different", "unrelated"],
        "labeler_agreement": "reported as a first-class number (method doc §M1)",
        "n_candidates": len(uniq),
        "n_conversations": len(convos),
        "pairs": uniq,
    }
    out["candidates_sha256"] = h
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"wrote {args.out}: {len(uniq)} candidate pairs "
          f"(A={sum(1 for p in uniq if p['band']=='A')}, "
          f"B={sum(1 for p in uniq if p['band']=='B')}, "
          f"C={sum(1 for p in uniq if p['band']=='C')}); sha256={h[:12]}")


if __name__ == "__main__":
    sys.exit(main())
