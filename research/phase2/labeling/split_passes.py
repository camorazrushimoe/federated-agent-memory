#!/usr/bin/env python3
"""split_passes.py — M1 pair-set pass inputs (mechanical separation of passes).

Usage:
  python3 split_passes.py <candidate_pairs.jsonl> <outdir> [--seed1 20260827] [--seed2 20260927]
  python3 split_passes.py --selftest   (synthetic 6-pair set, verifies the pipeline)

Reads the engineer's candidate pairs and writes:
  pass1_input.jsonl  — pair_id + display only (seed1-shuffled order)
  pass2_input.jsonl  — pair_id + display only (seed2-shuffled order, DIFFERENT order)
  passes_manifest.json — seeds, counts, sha256 of each input, field-set audit

Pass 2's input is guaranteed to contain no pass-1 fields (field-set assertion)
and is in a different order, so positional priming is impossible.
"""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

# Fields a pass input may carry. Anything else in candidate pairs is metadata
# that must NOT leak into the labeling display.
DISPLAY_FIELDS = ["pair_id", "band", "conv_a", "conv_b", "flow_a", "flow_b",
                  "subflow_a", "subflow_b", "product_a", "product_b", "display"]
SEED1_DEFAULT, SEED2_DEFAULT = 20260827, 20260927


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def split(pairs_path: Path, outdir: Path, seed1: int, seed2: int):
    pairs = [json.loads(l) for l in pairs_path.read_text().splitlines() if l.strip()]
    outdir.mkdir(parents=True, exist_ok=True)

    # Field-set audit: reject metadata the labeler must not see.
    allowed = set(DISPLAY_FIELDS) | {"id"}  # `id` tolerated as alias of pair_id
    for p in pairs:
        extra = set(p.keys()) - allowed
        if extra:
            raise SystemExit(f"pair {p.get('pair_id')}: disallowed fields would leak into pass input: {sorted(extra)}")

    def render(p):
        return {
            "pair_id": p["pair_id"],
            "band": p["band"],
            "conv_a": p.get("conv_a"), "conv_b": p.get("conv_b"),
            "flow_a": p.get("flow_a"), "flow_b": p.get("flow_b"),
            "subflow_a": p.get("subflow_a"), "subflow_b": p.get("subflow_b"),
            "product_a": p.get("product_a"), "product_b": p.get("product_b"),
            "display": p["display"],
        }

    r1 = random.Random(seed1)
    r2 = random.Random(seed2)
    p1 = [render(p) for p in pairs]; r1.shuffle(p1)
    p2 = [render(p) for p in pairs]; r2.shuffle(p2)

    # Different-order guarantee.
    order1 = [x["pair_id"] for x in p1]
    order2 = [x["pair_id"] for x in p2]
    if order1 == order2:
        raise SystemExit("FATAL: both pass inputs in identical order (seeds collided?)")

    def dump(path, rows):
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        return sha256_file(path)

    s1 = dump(outdir / "pass1_input.jsonl", p1)
    s2 = dump(outdir / "pass2_input.jsonl", p2)

    manifest = {
        "source": str(pairs_path),
        "n_pairs": len(pairs),
        "seeds": {"pass1": seed1, "pass2": seed2},
        "sha256": {"pass1_input": s1, "pass2_input": s2},
        "orders_differ": order1 != order2,
        "band_counts": {b: sum(1 for p in pairs if p["band"] == b) for b in
                        sorted({p["band"] for p in pairs})},
        "rule": "pass2 input contains no pass1 fields and uses a different seeded order",
    }
    (outdir / "passes_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return manifest


def selftest():
    tmp = Path("/tmp/m1_selftest")
    tmp.mkdir(parents=True, exist_ok=True)
    pairs = [
        {"pair_id": f"p{i:03d}", "band": ["should-match", "ambiguous", "should-not-match"][i % 3],
         "conv_a": f"c{i}a", "conv_b": f"c{i}b",
         "flow_a": "f1", "flow_b": "f2" if i % 3 else "f1",
         "subflow_a": "s1", "subflow_b": "s2" if i % 3 else "s1",
         "product_a": "P", "product_b": "P",
         "display": f"CONV A: I want a refund for item {i}.\nCONV B: My item {i} never arrived, please refund."}
        for i in range(6)]
    src = tmp / "candidate_pairs.jsonl"
    src.write_text("\n".join(json.dumps(p) for p in pairs) + "\n")
    m = split(src, tmp / "out", 20260827, 20260927)
    assert m["n_pairs"] == 6 and m["orders_differ"]
    print("SELFTEST OK: 6 synthetic pairs split, orders differ, manifest written.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="?")
    ap.add_argument("outdir", nargs="?")
    ap.add_argument("--seed1", type=int, default=SEED1_DEFAULT)
    ap.add_argument("--seed2", type=int, default=SEED2_DEFAULT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        if not a.pairs or not a.outdir:
            ap.error("pairs and outdir required (or --selftest)")
        split(Path(a.pairs), Path(a.outdir), a.seed1, a.seed2)
