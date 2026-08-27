#!/usr/bin/env python3
"""build_candidate_pairs.py — M1 candidate-pair construction (Research Engineer, Phase 2 R1).

Produces research/phase2/m1/candidate_pairs.jsonl per the pre-registered intake
contract: research/phase2/labeling/CANDIDATE-PAIR-CONTRACT.md (v1.0, 2026-08-27,
lead-reviewed; on main via PR #13).

Hypothesis served (H-m1, docs/research-method-m1-m3.md §M1):
  "Two conversations are about the same problem when they share the same
  underlying problem shape (intent + resolving constraint), despite different
  wording, users, or products." This script builds the stratified candidate set
  that the two-pass agent labeling (lab-1-evaluation) turns into the gold set
  against which B0/B1/B2 are scored. Nothing in the output is a label.

Bands (contract §4; recomputed by validate_pairs.py from the corpus):
  should-match      : same subflow, different conversations
  ambiguous         : different subflow, same flow
  should-not-match  : different flows; sub_band in {cross-flow, cross-product,
                      other-diff-flow}

Composition (contract §3 guidance; pre-registered here, seed 20260827):
  total 180 = should-match 84 (46.7%) + ambiguous 42 (23.3%) + should-not-match 54 (30.0%)
  should-not-match sub-bands:
    cross-product   14  (both products non-empty and different)            [>=10]
    cross-flow      24  (12 same non-empty product across flows +
                         12 both products empty)                           [>=20]
    other-diff-flow 16  (exactly one product empty)
  Band windows 45-55 / 15-25 / 30-40 all satisfied.

Display (contract §5):
  - customer turns only (agent turns are boilerplate per method doc B1; the
    contract permits exclusion and says "keep the display honest and minimal");
  - per conversation: neutral header, customer turns in order prefixed "CUST:",
    first customer turn ALWAYS in full, then a trailing "ACTIONS: a1, a2, ..."
    line (action-trace names from targets[2] of speaker=="action" turns — D11;
    corroborating evidence per protocol R4, not the label);
  - per-conversation customer text capped at MAX_CONV_CHARS (truncation after
    the first full turn; the validator checks the first turn's presence only);
  - corpus p90 of per-conversation customer text is ~450 chars, so the cap
    rarely binds; target total display <= ~1500 chars per pair holds.

DEVIATION FLAGGED (to evaluation + lead BEFORE pass 1, per contract §3):
  Contract §5 says the per-conversation header line should carry flow/subflow,
  but protocol R5 (PROTOCOL-m1-pairs.md v1.1, LOCKED) forbids the labeler seeing
  flow/subflow metadata during a pass, and contract §5 itself says "Metadata
  lives in the JSON fields; the display is the conversation text. Keeping them
  separate is the whole point." A flow/subflow header in the display would leak
  the band to the labeler and invalidate the two passes. This build therefore
  uses a NEUTRAL header (no flow/subflow in display prose). If evaluation rules
  the literal §5 header format wins, re-run with --scenario-header; the pair
  identities are unchanged (seeded), only the display text changes.

Determinism:
  - RNG seed 20260827 (recorded in output manifest + commit message);
  - every draw is a seeded choice from an explicitly enumerated candidate pool;
  - each conversation is used in AT MOST 1 pair (stricter than the contract's
    max-2); conv_a != conv_b always; pair order (a/b) carries no meaning.
  Re-running this script with the same seed + same corpus reproduces
  candidate_pairs.jsonl byte-for-byte.

Usage:
  python3 research/phase2/m1/build_candidate_pairs.py \
      --corpus data/abcd/abcd_v1.1.json \
      --out research/phase2/m1/candidate_pairs.jsonl \
      [--seed 20260827] [--scenario-header]
"""
import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict

# ---- pre-registered composition (contract §3) --------------------------------
N_SM = 84        # should-match  (46.7% of 180; band window 45-55%)
N_AMB = 42       # ambiguous     (23.3%; window 15-25%)
N_CF = 24        # cross-flow    (>=20)
N_CP = 14        # cross-product (>=10)
N_ODF = 16       # other-diff-flow
TOTAL = N_SM + N_AMB + N_CF + N_CP + N_ODF   # 180 (window 150-200)
assert TOTAL == 180

MAX_CONV_CHARS = 600     # per-conversation customer-text budget in display
MAX_ACTIONS_SHOWN = 8    # action names shown in the ACTIONS: line

# SM stratification by subflow size (coverage, not power — the gold set is
# scored per pair): large (n>=150) -> 36, mid (50<=n<150) -> 30, small (n<50) -> 18
SM_BUCKET_QUOTA = [("large", 36), ("mid", 30), ("small", 18)]
assert sum(q for _, q in SM_BUCKET_QUOTA) == N_SM


def load_corpus(path):
    data = json.load(open(path))
    convs = []
    for split in ("train", "dev", "test"):
        for c in data[split]:
            c["_split"] = split
            convs.append(c)
    return convs


def cust_turns(conv):
    """Customer turns (non-empty), in order. Delexed text, verbatim."""
    return [t["text"].strip() for t in conv["delexed"]
            if t.get("speaker") == "customer" and (t.get("text") or "").strip()]


def action_names(conv):
    """Ordered action-trace names: targets[2] of speaker=='action' turns (D11).
    Shape: [subflow, "take_action", "<name>", [args], -1]."""
    names = []
    for t in conv["delexed"]:
        if t.get("speaker") == "action":
            tg = t.get("targets") or []
            if len(tg) >= 3 and tg[1] == "take_action" and isinstance(tg[2], str):
                names.append(tg[2])
    return names


def prod_norm(p):
    if p is None:
        return None
    return json.dumps(p, sort_keys=True, default=str)


def prod_empty(p):
    if p is None:
        return True
    return not any(p.values())


def render_conv(conv, index, scenario_header, max_chars):
    lines = []
    if scenario_header:
        sc = conv["scenario"]
        lines.append(f"CONVERSATION {index} (flow: {sc['flow']}; subflow: {sc['subflow']})")
    else:
        lines.append(f"CONVERSATION {index}")
    turns = cust_turns(conv)
    used, shown, omitted = 0, 0, 0
    for i, t in enumerate(turns):
        if i > 0 and used + len(t) + 6 > max_chars:
            omitted = len(turns) - i
            break
        lines.append(f"CUST: {t}")
        used += len(t) + 6
        shown += 1
    if omitted:
        # honest truncation (contract §5: "not silently cut at the end")
        lines.append(f"[... {omitted} more customer turns omitted for length; "
                     f"first {shown} shown in full, action trace below is complete]")
    acts = action_names(conv)
    if acts:
        shown = acts[:MAX_ACTIONS_SHOWN]
        more = f" (+{len(acts) - MAX_ACTIONS_SHOWN} more)" if len(acts) > MAX_ACTIONS_SHOWN else ""
        lines.append("ACTIONS: " + ", ".join(shown) + more)
    return "\n".join(lines)


class Builder:
    def __init__(self, convs, seed):
        self.convs = {str(c["convo_id"]): c for c in convs}
        self.rng = random.Random(seed)
        self.usage = defaultdict(int)   # convo_id -> # pairs used
        self.pairs = []                 # (a, b, band, meta) in build order

    def _try_take(self, a, b):
        """Reserve a,b for a pair (max 1 use each). Returns True on success."""
        if a == b or self.usage[a] > 0 or self.usage[b] > 0:
            return False
        self.usage[a] += 1
        self.usage[b] += 1
        return True

    def _draw(self, candidate_fn, n, band, label):
        """Draw n pairs from candidate_fn() -> (a, b, meta) | None, skipping
        exhausted convos and None. Deterministic under the seeded rng."""
        got, attempts = 0, 0
        while got < n and attempts < n * 1000:
            attempts += 1
            res = candidate_fn()
            if res is None:
                continue
            a, b, meta = res
            if not self._try_take(a, b):
                continue
            self.pairs.append((a, b, band, meta))
            got += 1
        if got < n:
            raise SystemExit(f"pool exhausted for {label}: got {got}/{n} "
                             f"(attempts={attempts})")

    def sm_pairs(self):
        by_sf = defaultdict(list)
        for cid, c in self.convs.items():
            by_sf[c["scenario"]["subflow"]].append(cid)

        buckets = {"large": [], "mid": [], "small": []}
        for sf, ids in sorted(by_sf.items()):
            if len(ids) < 2:
                continue
            k = "large" if len(ids) >= 150 else ("mid" if len(ids) >= 50 else "small")
            buckets[k].append((sf, ids))

        for key, quota in SM_BUCKET_QUOTA:
            pool = buckets[key]
            if not pool:
                raise SystemExit(f"SM bucket {key} empty")
            cands = []
            for sf, ids in pool:
                sh = list(ids)
                self.rng.shuffle(sh)
                m = min(len(sh), 40)
                for i in range(m):
                    cands.append((sh[i], sh[(i + 1) % len(sh)], sf))
                if len(sh) >= 3:
                    cands.append((sh[0], sh[-1], sf))
            self.rng.shuffle(cands)
            state = {"i": 0}

            def draw_one(state=state, cands=cands):
                # advance the cursor, reshuffling deterministically when wrapped
                if state["i"] >= len(cands):
                    self.rng.shuffle(cands)
                    state["i"] = 0
                idx = state["i"]
                state["i"] += 1
                a, b, sf = cands[idx]
                return (a, b, {"subflow": sf})

            self._draw(draw_one, quota, "should-match", f"SM-{key}")

    def amb_pairs(self):
        by_flow = defaultdict(lambda: defaultdict(list))
        for cid, c in self.convs.items():
            by_flow[c["scenario"]["flow"]][c["scenario"]["subflow"]].append(cid)

        flows = sorted(by_flow)
        cands = []   # (flow, sf_a, sf_b, ids_a, ids_b)
        for fl in flows:
            sfs = sorted(by_flow[fl])
            for i in range(len(sfs)):
                for j in range(i + 1, len(sfs)):
                    cands.append((fl, sfs[i], sfs[j],
                                  sorted(by_flow[fl][sfs[i]]),
                                  sorted(by_flow[fl][sfs[j]])))
        if not cands:
            raise SystemExit("no ambiguous candidates")

        def draw_one():
            fl, sfa, sfb, la, lb = self.rng.choice(cands)
            return (self.rng.choice(la), self.rng.choice(lb),
                    {"flow": fl, "subflow_a": sfa, "subflow_b": sfb})

        self._draw(draw_one, N_AMB, "ambiguous", "AMB")

    def snn_pairs(self):
        ne = [cid for cid, c in self.convs.items() if not prod_empty(c["scenario"].get("product"))]
        emp = [cid for cid, c in self.convs.items() if prod_empty(c["scenario"].get("product"))]
        if not ne or not emp:
            raise SystemExit("empty/non-empty product partition failed")
        by_flow_ne = defaultdict(list)
        for cid in ne:
            by_flow_ne[self.convs[cid]["scenario"]["flow"]].append(cid)

        def cross_flow_same_product():
            # both non-empty, SAME product, different flows — the hard false friend
            fl = self.rng.choice(sorted(by_flow_ne))
            a = self.rng.choice(by_flow_ne[fl])
            pn = prod_norm(self.convs[a]["scenario"].get("product"))
            other = [cid for fl2, ids in by_flow_ne.items() if fl2 != fl for cid in ids
                     if prod_norm(self.convs[cid]["scenario"].get("product")) == pn]
            if not other:
                return None
            return (a, self.rng.choice(other), {"sub_band": "cross-flow", "kind": "same-product"})

        def cross_flow_both_empty():
            a, b = self.rng.choice(emp), self.rng.choice(emp)
            if self.convs[a]["scenario"]["flow"] == self.convs[b]["scenario"]["flow"]:
                return None
            return (a, b, {"sub_band": "cross-flow", "kind": "both-empty"})

        def cross_product():
            a = self.rng.choice(ne)
            pa = prod_norm(self.convs[a]["scenario"].get("product"))
            fl_a = self.convs[a]["scenario"]["flow"]
            cands = [cid for fl2, ids in by_flow_ne.items() if fl2 != fl_a for cid in ids
                     if prod_norm(self.convs[cid]["scenario"].get("product")) != pa]
            if not cands:
                return None
            return (a, self.rng.choice(cands), {"sub_band": "cross-product"})

        def other_diff_flow():
            a, b = self.rng.choice(ne), self.rng.choice(emp)
            if self.convs[a]["scenario"]["flow"] == self.convs[b]["scenario"]["flow"]:
                return None
            return (a, b, {"sub_band": "other-diff-flow"})

        self._draw(cross_product, N_CP, "should-not-match", "SNN-cross-product")
        self._draw(cross_flow_same_product, 12, "should-not-match", "SNN-cf-same-product")
        self._draw(cross_flow_both_empty, N_CF - 12, "should-not-match", "SNN-cf-both-empty")
        self._draw(other_diff_flow, N_ODF, "should-not-match", "SNN-other-diff-flow")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--scenario-header", action="store_true",
                    help="contract §5 literal: flow/subflow in display headers "
                         "(DEVIATION — leaks band to labeler vs protocol R5)")
    args = ap.parse_args()

    convs = load_corpus(args.corpus)
    b = Builder(convs, args.seed)
    b.sm_pairs()
    b.amb_pairs()
    b.snn_pairs()

    assert len(b.pairs) == TOTAL, f"expected {TOTAL} pairs, got {len(b.pairs)}"

    lines_out = []
    for idx, (a, c2, band, meta) in enumerate(b.pairs, start=1):
        ca, cb = b.convs[a], b.convs[c2]
        sca, scb = ca["scenario"], cb["scenario"]
        # band-vs-metadata self-check (validator does the authoritative one)
        if band == "should-match":
            assert sca["subflow"] == scb["subflow"]
        elif band == "ambiguous":
            assert sca["subflow"] != scb["subflow"] and sca["flow"] == scb["flow"]
        else:
            assert sca["flow"] != scb["flow"]
            if meta.get("sub_band") == "cross-product":
                ea, eb = prod_empty(sca.get("product")), prod_empty(scb.get("product"))
                assert not ea and not eb and prod_norm(sca.get("product")) != prod_norm(scb.get("product"))
        display = (render_conv(ca, 1, args.scenario_header, MAX_CONV_CHARS) + "\n\n" +
                   render_conv(cb, 2, args.scenario_header, MAX_CONV_CHARS))
        rec = {
            "pair_id": f"m1-{idx:04d}",
            "band": band,
            "conv_a": a, "conv_b": c2,
            "flow_a": sca["flow"], "flow_b": scb["flow"],
            "subflow_a": sca["subflow"], "subflow_b": scb["subflow"],
            "product_a": sca.get("product"), "product_b": scb.get("product"),
            "display": display,
        }
        if band == "should-not-match":
            rec["sub_band"] = meta["sub_band"]
        lines_out.append(json.dumps(rec, ensure_ascii=False))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")

    band_counts, sub_counts, usage_max = {}, {}, 0
    for l in lines_out:
        r = json.loads(l)
        band_counts[r["band"]] = band_counts.get(r["band"], 0) + 1
        if "sub_band" in r:
            sub_counts[r["sub_band"]] = sub_counts.get(r["sub_band"], 0) + 1
        usage_max = max(usage_max, b.usage[r["conv_a"]], b.usage[r["conv_b"]])
    corpus_sha = hashlib.sha256(open(args.corpus, "rb").read()).hexdigest()[:16]
    manifest = {
        "generator": "research/phase2/m1/build_candidate_pairs.py v1",
        "seed": args.seed,
        "corpus": args.corpus,
        "corpus_sha256_16": corpus_sha,
        "n_conversations": len(convs),
        "n_pairs": len(lines_out),
        "band_counts": band_counts,
        "sub_band_counts": sub_counts,
        "max_conversation_reuse": usage_max,
        "display": {"customer_turns_only": True, "max_conv_chars": MAX_CONV_CHARS,
                    "max_actions_shown": MAX_ACTIONS_SHOWN,
                    "scenario_header_in_display": bool(args.scenario_header)},
        "note": "Pre-registered B1 threshold + the flagged contract §5 vs protocol R5 "
                "header tension: see research/phase2/m1/README.md.",
    }
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    sys.exit(main())
