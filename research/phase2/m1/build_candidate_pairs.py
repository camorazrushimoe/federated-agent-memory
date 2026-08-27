#!/usr/bin/env python3
"""build_candidate_pairs.py — M1 candidate pair set, LEAD-PINNED 170 composition.

Phase 2, round 1/6, BON-41 (M1). Builds `candidate_pairs.jsonl` to the intake
contract `research/phase2/labeling/CANDIDATE-PAIR-CONTRACT.md` (on main via #13).

COMPOSITION — lead-pinned (lead, 2026-08-27, GH #6 comment 5445829777), inside the
labeler's §3 windows:
    170 total
      85  should-match      (same subflow, different conversation)
      34  ambiguous         (different subflow, same flow)
      51  should-not-match  (different flow), sub_band:
            20 cross-flow        different flow, both products NON-EMPTY and the
                                 SAME product  (diff_prod False -> validator
                                 warning-free; the "hard" false friend: same
                                 product, different flow)
            10 cross-product     different flow, both products NON-EMPTY and
                                 DIFFERENT (the contract §4 cross-product slice)
            21 other-diff-flow   different flow, at least one product EMPTY
    (cross-flow >= 20, cross-product >= 10, remainder other-diff-flow — as pinned)

Sub-band partition rationale (unique clean partition): unordered different-flow
pairs split into EXACTLY three mutually exclusive, exhaustive classes:
    (1) both non-empty + same product   -> cross-flow
    (2) both non-empty + different      -> cross-product   (contract §4)
    (3) at least one empty              -> other-diff-flow (contract §4)
So with cross-product = (2) and other-diff-flow = (3), cross-flow is forced to be
(1). That is also the only assignment that keeps `validate_pairs.py` at
0 warnings (it warns when a pair has diff_prod=True but is not labeled
cross-product).

DETERMINISM: single seed, stable sort. Same corpus + seed => byte-identical file.
Seed default = 42 (matches the lead's phase-1 draft + method doc default). The
corpus is the canonical `data/abcd/abcd_v1.1.json`.

CONSTRAINTS (contract §6):
  - a conversation appears in <= 2 pairs TOTAL (tracked globally across bands)
  - conv_a != conv_b always

DISPLAY (contract §5, R5-safe): per conversation a NEUTRAL header, customer turns
in order each prefixed "CUST:" (first turn always in full; long tails truncated at
a word boundary), and a trailing "ACTIONS: ..." line of the D11 action-trace names
(targets[2] of speaker:"action" turns, order-preserving dedupe). Agent boilerplate
is excluded (method B1 rule). No band, no flow/subflow id, no product, no oracle —
none of that in the display prose (protocol R5 is LOCKED: the labeler must never
see band/oracle cues during a pass). Target <= ~1,500 chars per pair.

  NOTE on contract §5's "header line with flow/subflow": that literal reading
  CONFLICTS with the LOCKED protocol R5 ("the labeler never sees the band,
  sub_band, flow/subflow ids, or product metadata during a pass") and with §5's
  own "Do NOT include: subflow labels in the display prose". A flow/subflow header
  would leak the band structure (same subflow => should-match, etc.) to the
  labeler and invalidate the two passes. This builder therefore defaults to a
  NEUTRAL header (the R5-safe choice, and the call the labeler's own pre-merge
  180-set made). If the lead/evaluation rule that the literal §5 header wins,
  re-run with --scenario-header (pair identities are unchanged; only the display
  text changes). Flagged for adjudication before pass 1 (contract §3).

Usage:
  python3 build_candidate_pairs.py --abcd data/abcd/abcd_v1.1.json \
      --out research/phase2/m1/candidate_pairs.jsonl [--seed 42] [--scenario-header]
"""
import argparse
import json
import random
from collections import Counter, defaultdict

RANGE = (150, 200)
# Lead-pinned composition (2026-08-27, comment 5445829777).
N_SM = 85          # should-match
N_AMB = 34         # ambiguous
N_CF = 20          # should-not-match / cross-flow  (both non-empty, same product)
N_CP = 10          # should-not-match / cross-product (both non-empty, different)
N_ODF = 21         # should-not-match / other-diff-flow (>=1 empty)
TOTAL = N_SM + N_AMB + N_CF + N_CP + N_ODF   # 170

# Per-conversation display budget; a pair = two convos so 2*740 keeps every pair
# under the contract §5 target of ~1,500 chars/pair. First customer turn is always
# kept in full; only long tails are word-boundary truncated.
CONVO_BUDGET = 740
HARD_CAP = 1600    # safety cap per pair
MAX_REUSE = 2      # contract §6


# ---------- corpus helpers (mirror validate_pairs.py exactly) ----------
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


def load_convos(path):
    data = json.load(open(path))
    convos = []
    for split in ("train", "dev", "test"):
        if split in data:
            convos.extend(data[split])
    return convos


def customer_turns(c):
    """Customer turns only, delexed, in order (agent boilerplate excluded)."""
    return [t["text"].strip() for t in c.get("delexed", [])
            if isinstance(t, dict) and t.get("speaker") == "customer"
            and (t.get("text") or "").strip()]


def action_names(c):
    """D11: action-trace names = targets[2] of speaker:'action' turns,
    order-preserving dedupe. Corroborating evidence of structure (protocol R4)."""
    seen = []
    for t in c.get("delexed", []):
        if not (isinstance(t, dict) and t.get("speaker") == "action"):
            continue
        tg = t.get("targets")
        if isinstance(tg, list) and len(tg) > 2 and tg[2] is not None:
            name = tg[2]
            if name not in seen:
                seen.append(name)
    return seen


# ---------- display ----------
def render_convo(c, index, scenario_header):
    sc = c["scenario"]
    turns = customer_turns(c)
    acts = action_names(c)
    if scenario_header:
        header = f"CONVERSATION {index} (flow: {sc['flow']}; subflow: {sc['subflow']})"
    else:
        header = f"CONVERSATION {index}"
    lines = [header]
    if turns:
        lines.append("CUST: " + turns[0])  # first turn ALWAYS in full
    if acts:
        lines.append("ACTIONS: " + ", ".join(str(a) for a in acts))
    body = "\n".join(lines) + "\n"
    rest = turns[1:]
    for t in rest:
        candidate = "CUST: " + t + "\n"
        if len(body) + len(candidate) <= CONVO_BUDGET:
            body += candidate
        else:
            room = CONVO_BUDGET - len(body)
            if room < 8:
                break
            allow = max(1, room - len("CUST: ") - len(" ..."))
            cut = t[:allow]
            sp = cut.rfind(" ")
            if sp > allow * 0.5:
                cut = cut[:sp]
            body += "CUST: " + cut + " ...\n"
    return body


def build_display(a, b, scenario_header):
    da, db = render_convo(a, 1, scenario_header), render_convo(b, 2, scenario_header)
    if len(da) + len(db) + 1 > HARD_CAP:
        keep = (HARD_CAP - len(db) - 1) if len(da) > len(db) else (HARD_CAP - len(da) - 1)
        if len(da) > len(db) and keep > 200:
            da = da[:keep].rsplit("\n", 1)[0] + "\n"
        elif len(db) > len(da) and keep > 200:
            db = db[:keep].rsplit("\n", 1)[0] + "\n"
    return da + "\n" + db


# ---------- construction ----------
class Pool:
    """Global conversation usage tracker (max 2 pairs total, contract §6)."""

    def __init__(self):
        self.usage = Counter()

    def can(self, i, j):
        return i != j and self.usage[i] < MAX_REUSE and self.usage[j] < MAX_REUSE

    def take(self, i, j):
        self.usage[i] += 1
        self.usage[j] += 1


def build(abc_path, seed, scenario_header):
    convos = load_convos(abc_path)
    by_id = {c["convo_id"]: c for c in convos}
    rng = random.Random(seed)

    by_sub = defaultdict(list)   # (flow, subflow) -> [ids]
    by_flow = defaultdict(list)  # flow -> [ids]
    prod_flows = defaultdict(lambda: defaultdict(list))  # prod_norm -> flow -> [ids]
    ne_ids_by_flow = defaultdict(list)    # flow -> [ids] non-empty product
    empty_ids_by_flow = defaultdict(list)  # flow -> [ids] empty product
    for c in convos:
        sc = c["scenario"]
        fl, sf = sc["flow"], sc["subflow"]
        by_sub[(fl, sf)].append(c["convo_id"])
        by_flow[fl].append(c["convo_id"])
        p = sc["product"]
        if prod_empty(p):
            empty_ids_by_flow[fl].append(c["convo_id"])
        else:
            ne_ids_by_flow[fl].append(c["convo_id"])
            prod_flows[prod_norm(p)][fl].append(c["convo_id"])
    for lst in by_sub.values():
        lst.sort()
    for lst in by_flow.values():
        lst.sort()
    for fdict in prod_flows.values():
        for lst in fdict.values():
            lst.sort()

    pool = Pool()
    triples = []  # (band, sub_band, a, b)

    # ---- should-match (85): same subflow, different conversation ----
    subkeys = sorted(by_sub.keys(), key=lambda k: (-len(by_sub[k]), k[1], k[0]))
    per_sub = {k: 0 for k in subkeys}
    i, placed = 0, 0
    while placed < N_SM:
        k = subkeys[i % len(subkeys)]
        if per_sub[k] < (2 if len(by_sub[k]) >= 4 else 1):
            per_sub[k] += 1
            placed += 1
        i += 1
    for k in subkeys:
        ids = by_sub[k]
        for _ in range(per_sub[k]):
            for _ in range(50):
                a, b = rng.sample(ids, 2)
                if pool.can(a, b):
                    pool.take(a, b)
                    triples.append(("should-match", None, a, b))
                    break
            else:
                raise RuntimeError(f"could not place should-match pair in {k}")

    # ---- ambiguous (34): same flow, different subflow ----
    placed = 0
    while placed < N_AMB:
        fl = rng.choice(sorted(by_flow.keys()))
        subs = sorted({sf for (f, sf) in by_sub if f == fl and by_sub[(f, sf)]})
        if len(subs) < 2:
            continue
        sa, sb = rng.sample(subs, 2)
        for _ in range(60):
            a = rng.choice(by_sub[(fl, sa)])
            b = rng.choice(by_sub[(fl, sb)])
            if pool.can(a, b):
                pool.take(a, b)
                triples.append(("ambiguous", None, a, b))
                placed += 1
                break
        else:
            raise RuntimeError(f"could not place ambiguous pair in flow {fl}")

    # ---- should-not-match (51) ----
    # (a) cross-flow (20): both non-empty, SAME product, different flow
    same_prod = []
    for pn, fdict in prod_flows.items():
        flows = [f for f in fdict if fdict[f]]
        if len(flows) >= 2:
            same_prod.append((pn, flows, fdict))
    rng.shuffle(same_prod)
    placed_cf = 0
    for pn, flows, fdict in same_prod:
        if placed_cf >= N_CF:
            break
        for xi in range(len(flows)):
            for xj in range(xi + 1, len(flows)):
                if placed_cf >= N_CF:
                    break
                for _ in range(40):
                    a = rng.choice(fdict[flows[xi]])
                    b = rng.choice(fdict[flows[xj]])
                    if pool.can(a, b):
                        pool.take(a, b)
                        triples.append(("should-not-match", "cross-flow", a, b))
                        placed_cf += 1
                        break
    if placed_cf < N_CF:
        raise RuntimeError(f"only placed {placed_cf} cross-flow pairs")

    # (b) cross-product (10): both non-empty, DIFFERENT product, different flow
    ne_flows = sorted(f for f in by_flow if ne_ids_by_flow.get(f))
    placed_cp = 0
    while placed_cp < N_CP:
        fa, fb = rng.sample(ne_flows, 2)
        for _ in range(80):
            a = rng.choice(ne_ids_by_flow[fa])
            b = rng.choice(ne_ids_by_flow[fb])
            if pool.can(a, b) and prod_norm(by_id[a]["scenario"]["product"]) != \
               prod_norm(by_id[b]["scenario"]["product"]):
                pool.take(a, b)
                triples.append(("should-not-match", "cross-product", a, b))
                placed_cp += 1
                break
    if placed_cp < N_CP:
        raise RuntimeError(f"only placed {placed_cp} cross-product pairs")

    # (c) other-diff-flow (21): different flow, >=1 product empty
    empty_flows = sorted(f for f in by_flow if empty_ids_by_flow.get(f))
    all_flows = sorted(by_flow.keys())
    placed_odf = 0
    while placed_odf < N_ODF:
        fa = empty_flows[rng.randrange(len(empty_flows))]
        fb = all_flows[rng.randrange(len(all_flows))]
        if fa == fb:
            continue
        a = rng.choice(empty_ids_by_flow[fa])
        for _ in range(60):
            b = (rng.choice(empty_ids_by_flow[fb]) if empty_ids_by_flow[fb]
                 else rng.choice(by_flow[fb])) if rng.random() < 0.5 \
                else rng.choice(by_flow[fb])
            ea = prod_empty(by_id[a]["scenario"]["product"])
            eb = prod_empty(by_id[b]["scenario"]["product"])
            if pool.can(a, b) and (ea or eb):
                pool.take(a, b)
                triples.append(("should-not-match", "other-diff-flow", a, b))
                placed_odf += 1
                break
    if placed_odf < N_ODF:
        raise RuntimeError(f"only placed {placed_odf} other-diff-flow pairs")

    # ---- dedupe on unordered convo-id pair, assign ids, build lines ----
    seen = set()
    lines = []
    n = 0
    for band, sub_band, a, b in triples:
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        n += 1
        ca, cb = by_id[a], by_id[b]
        rec = {"pair_id": f"m1-{n:04d}", "band": band}
        if sub_band is not None:
            rec["sub_band"] = sub_band
        rec["conv_a"] = str(a)
        rec["conv_b"] = str(b)
        rec["flow_a"] = ca["scenario"]["flow"]
        rec["flow_b"] = cb["scenario"]["flow"]
        rec["subflow_a"] = ca["scenario"]["subflow"]
        rec["subflow_b"] = cb["scenario"]["subflow"]
        rec["product_a"] = ca["scenario"]["product"]
        rec["product_b"] = cb["scenario"]["product"]
        rec["display"] = build_display(ca, cb, scenario_header)
        lines.append(rec)
    return lines, pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--abcd", default="data/abcd/abcd_v1.1.json")
    ap.add_argument("--out", default="research/phase2/m1/candidate_pairs.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scenario-header", action="store_true",
                    help="use the literal contract §5 flow/subflow header (NOT "
                         "the default; conflicts with LOCKED protocol R5)")
    a = ap.parse_args()
    lines, pool = build(a.abcd, a.seed, a.scenario_header)

    bc = Counter(l["band"] for l in lines)
    sbc = Counter(l.get("sub_band") for l in lines if l.get("sub_band"))
    max_use = max(pool.usage.values())
    total = len(lines)
    assert RANGE[0] <= total <= RANGE[1], total
    assert bc["should-match"] == N_SM, bc
    assert bc["ambiguous"] == N_AMB, bc
    assert bc["should-not-match"] == N_CF + N_CP + N_ODF, bc
    assert sbc["cross-flow"] == N_CF, sbc
    assert sbc["cross-product"] == N_CP, sbc
    assert sbc["other-diff-flow"] == N_ODF, sbc
    assert max_use <= MAX_REUSE, max_use

    import os
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        for l in lines:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")

    dlen = sorted(len(l["display"]) for l in lines)
    print(json.dumps({
        "out": a.out,
        "n_pairs": total,
        "band_counts": dict(bc),
        "sub_band_counts": dict(sbc),
        "max_conversation_reuse": max_use,
        "n_unique_conversations": len(pool.usage),
        "display_len_p50": dlen[len(dlen)//2],
        "display_len_max": max(dlen),
        "display_len_over_1500": sum(1 for x in dlen if x > 1500),
        "scenario_header": a.scenario_header,
        "seed": a.seed,
    }, indent=2))


if __name__ == "__main__":
    main()
