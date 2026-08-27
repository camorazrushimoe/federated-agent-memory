#!/usr/bin/env python3
"""validate_pairs.py — M1 candidate-pair intake check (evaluation, pre-labeling).

Usage:
  python3 validate_pairs.py <candidate_pairs.jsonl> [--corpus /opt/data/fam-r2/data/abcd/abcd_v1.1.json]

Checks (before any labeling; lab-workflow §8 'verify against the file'):
  1. every conv_a/conv_b exists in the ABCD corpus (train+dev+test)
  2. band consistency vs scenario metadata:
       should-match     : same subflow (implies same flow)
       ambiguous        : different subflow, same flow
       should-not-match : different flows (incl. cross-flow / cross-product)
  3. display faithfulness: each conversation's first customer turn must appear
     in the pair display (truncation-tolerant: first 40 chars). WARNING only —
     a mismatch is a finding, never silently fixed.
  4. total count in the pre-registered ~150-200 range; per-band counts.

Exit code 0 = OK to label (warnings allowed); 1 = blocking problems found.
This check is evaluation's: the labeler must not inherit silent construction
errors (protocol §7 limitation 3).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BANDS = ["should-match", "ambiguous", "should-not-match"]
SUB_BANDS = ["cross-flow", "cross-product", "other-diff-flow"]
RANGE = (150, 200)


def load_corpus(path):
    data = json.load(open(path))
    out = {}
    for split in ("train", "dev", "test"):
        for c in data[split]:
            out[str(c["convo_id"])] = (split, c)
    return out


def first_customer_turn(conv):
    for t in conv["delexed"]:
        if t.get("speaker") == "customer" and (t.get("text") or "").strip():
            return t["text"].strip()
    return ""


def prod_empty(p):
    if p is None:
        return True
    if isinstance(p, dict):
        return not any(p.values())
    if isinstance(p, (list, tuple)):
        return len(p) == 0
    return str(p).strip() in ("", "?")


def prod_norm(p):
    if isinstance(p, dict):
        return json.dumps(p, sort_keys=True, default=str)
    return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs")
    ap.add_argument("--corpus", default="/opt/data/fam-r2/data/abcd/abcd_v1.1.json")
    a = ap.parse_args()

    pairs = [json.loads(l) for l in open(a.pairs) if l.strip()]
    corpus = load_corpus(a.corpus)
    blocking, warnings = [], []

    band_counts = {b: 0 for b in BANDS}
    sub_band_counts = {}
    conv_usage = Counter()
    seen = set()
    for p in pairs:
        pid, band = p["pair_id"], p.get("band")
        if pid in seen:
            blocking.append(f"{pid}: duplicate pair_id")
        seen.add(pid)
        if band not in BANDS:
            blocking.append(f"{pid}: unknown band {band!r}")
            continue
        band_counts[band] += 1
        if p.get("sub_band"):
            sub_band_counts[p["sub_band"]] = sub_band_counts.get(p["sub_band"], 0) + 1
        ca, cb = str(p.get("conv_a")), str(p.get("conv_b"))
        if ca == cb:
            blocking.append(f"{pid}: conv_a == conv_b ({ca})")
        for cid, tag in ((ca, "conv_a"), (cb, "conv_b")):
            if cid not in corpus:
                blocking.append(f"{pid}: {tag}={cid} not in corpus")
        if ca in corpus and cb in corpus and ca != cb:
            sa = corpus[ca][1]["scenario"]
            sb = corpus[cb][1]["scenario"]
            # band vs metadata
            same_sub = sa.get("subflow") == sb.get("subflow")
            same_flow = sa.get("flow") == sb.get("flow")
            if band == "should-match" and not same_sub:
                blocking.append(f"{pid}: band=should-match but subflows differ "
                                f"({sa.get('subflow')} vs {sb.get('subflow')})")
            if band == "ambiguous" and (same_sub or not same_flow):
                blocking.append(f"{pid}: band=ambiguous but subflow_same={same_sub} "
                                f"flow_same={same_flow}")
            if band == "should-not-match" and same_flow:
                blocking.append(f"{pid}: band=should-not-match but same flow "
                                f"{sa.get('flow')!r}")
            # sub_band contract (CANDIDATE-PAIR-CONTRACT §3/§4)
            if band == "should-not-match":
                sb_band = p.get("sub_band")
                ea, eb = prod_empty(sa.get("product")), prod_empty(sb.get("product"))
                pa, pb = prod_norm(sa.get("product")), prod_norm(sb.get("product"))
                diff_prod = (not ea) and (not eb) and (pa != pb)
                if sb_band not in ("cross-flow", "cross-product", "other-diff-flow"):
                    blocking.append(f"{pid}: should-not-match pair missing/invalid "
                                    f"sub_band {sb_band!r}")
                if sb_band == "cross-product" and not diff_prod:
                    blocking.append(f"{pid}: sub_band=cross-product but products not "
                                    f"different-non-empty (empty_a={ea}, empty_b={eb})")
                if diff_prod and sb_band != "cross-product":
                    warnings.append(f"{pid}: products are different and non-empty but "
                                    f"sub_band={sb_band!r} (informational; not blocking)")
            # display faithfulness (warning)
            display = p.get("display", "")
            for tag, cid in (("conv_a", ca), ("conv_b", cb)):
                fc = first_customer_turn(corpus[cid][1])
                if fc and fc[:40] not in display:
                    warnings.append(f"{pid}: {tag} first customer turn not found "
                                    f"in display: {fc[:60]!r}")
        # band fields stated by engineer, if present, must match metadata
        if p.get("flow_a") and str(p.get("flow_a")) != str(corpus.get(ca, (None, {"scenario": {}}))[1]["scenario"].get("flow")):
            warnings.append(f"{pid}: stated flow_a {p.get('flow_a')!r} != corpus")
        if p.get("subflow_a") and str(p.get("subflow_a")) != str(corpus.get(ca, (None, {"scenario": {}}))[1]["scenario"].get("subflow")):
            warnings.append(f"{pid}: stated subflow_a {p.get('subflow_a')!r} != corpus")
        conv_usage[str(p.get("conv_a"))] += 1
        conv_usage[str(p.get("conv_b"))] += 1

    n = len(pairs)
    ok_range = RANGE[0] <= n <= RANGE[1]
    max_usage = max(conv_usage.values()) if conv_usage else 0
    print(json.dumps({
        "n_pairs": n,
        "in_pre_registered_range_150_200": ok_range,
        "band_counts": band_counts,
        "sub_band_counts": sub_band_counts,
        "max_conversation_reuse": max_usage,
        "max_conversation_reuse_ok_<=2": max_usage <= 2,
        "blocking": blocking[:30],
        "n_blocking": len(blocking),
        "warnings": warnings[:30],
        "n_warnings": len(warnings),
        "verdict": "OK_TO_LABEL" if not blocking and ok_range else
                   ("RANGE_ISSUE_ONLY" if not blocking else "BLOCKED"),
    }, indent=2))
    sys.exit(0 if not blocking else 1)


if __name__ == "__main__":
    main()
