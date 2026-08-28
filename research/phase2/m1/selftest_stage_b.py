#!/usr/bin/env python3
"""selftest_stage_b.py — prove score_m1.py's gold-join + metric math is correct.

Strategy: build a SYNTHETIC gold set over the REAL 170 scored pairs with a
known label assignment, then independently recompute (with plain Python, no
sklearn) the metrics that stage B reports and assert they match. This verifies:
  1. the pair-id join,
  2. the canonical-label -> FFR/recall/F1 mapping,
  3. the operating-curve threshold sweep,
  4. the bar decision + operating-point selection,
  5. the B0 oracle metrics.
Run: .venv/bin/python research/phase2/m1/selftest_stage_b.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_m1 as M

M1 = Path(__file__).resolve().parent
ROWS = M.load_jsonl(M1 / "b1_scores.jsonl")
assert len(ROWS) == 170, len(ROWS)

# --- synthetic gold: known assignment (deterministic, not a real label) -------
def synth_canon(r):
    if r["band"] == "should-match":
        return "same-problem" if r["b1_cosine"] >= 0.10 else "related-but-different"
    if r["band"] == "ambiguous":
        return "related-but-different"
    return "unrelated"  # should-not-match

gold_rows = []
for i, r in enumerate(ROWS):
    lab = synth_canon(r)
    gold_rows.append({
        "pair_id": r["pair_id"], "band": r["band"],
        "pass1_label": lab, "pass2_label": lab, "agreed": True,
        "canonical_label": lab, "flag": None, "provenance": "agent-labeled",
        "pass1_rationale": "synth", "pass2_rationale": "synth",
    })

# --- independent metric computation (plain python) ----------------------------
canon = {g["pair_id"]: g["canonical_label"] for g in gold_rows}
sm = [r["pair_id"] for r in ROWS if r["band"] == "should-match"]
unrel = [r["pair_id"] for r in ROWS if canon[r["pair_id"]] == "unrelated"]
same = [r["pair_id"] for r in ROWS if canon[r["pair_id"]] == "same-problem"]
cos = {r["pair_id"]: r["b1_cosine"] for r in ROWS}

def indep(t_label, pooled):
    tp = len(pooled & set(same)); fp = len(pooled - set(same)); fn = len(set(same) - pooled)
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    return {
        "recall_sm": round(len(pooled & set(sm)) / len(sm), 4),
        "ffr": round(len(pooled & set(unrel)) / len(unrel), 4),
        "f1": round(f1, 4),
        "n_pooled": len(pooled),
        "tp": tp, "fp": fp, "fn": fn,
    }

# --- run stage B's operate() and compare --------------------------------------
res = M.operate(ROWS, canon)
curve = {c["threshold"]: c for c in res["b1_curve"]}

checks = 0
# sentinel + a spread of real thresholds
probe_ts = ["none (pool nothing)"]
all_t = sorted(set(cos.values()))
probe_ts += [f">= {t:.6f}" for t in [all_t[len(all_t)//4], all_t[len(all_t)//2],
                                     all_t[3*len(all_t)//4], all_t[-1]]]
for tl in probe_ts:
    if tl.startswith("none"):
        pooled = set()
    else:
        t = float(tl.split(" ", 1)[1])
        pooled = {pid for pid, s in cos.items() if s >= t}
    exp = indep(tl, pooled)
    got = curve[tl]
    for k in ("recall_sm", "ffr", "f1", "n_pooled", "tp", "fp", "fn"):
        assert abs(got[k] - exp[k]) < 1e-9, (tl, k, got[k], exp[k])
        checks += 1

# --- B0 oracle independent ----------------------------------------------------
b0_pooled = {r["pair_id"] for r in ROWS if r["b0_pool"]}
exp_b0 = indep("same subflow (oracle)", b0_pooled)
got_b0 = res["b0"]
for k in ("recall_sm", "ffr", "f1", "n_pooled"):
    assert abs(got_b0[k] - exp_b0[k]) < 1e-9, ("b0", k, got_b0[k], exp_b0[k])
    checks += 1
# on the synthetic gold, every should-match is same-problem only when cosine>=0.10
# B0 pools ALL 85 should-match (same subflow) -> recall_sm must be 1.0
assert got_b0["recall_sm"] == 1.0, got_b0
# B0 pools 0 ambiguous + 0 should-not-match -> FFR = 0/51 = 0.0
assert got_b0["ffr"] == 0.0, got_b0

# --- bar decision + selection: independent recomputation ----------------------
passing = [c for c in res["b1_curve"]
           if c["ffr"] <= M.FFR_BAR and c["recall_sm"] >= M.RECALL_BAR]
if passing:
    assert res["bar_met"] is True, "should be bar_met"
    best = max(c["f1"] for c in passing)
    cands = [c for c in passing if c["f1"] == best]
    sel = res["b1_selected"]
    assert sel in cands, "selected op point must be a max-F1 bar-passing threshold"
else:
    assert res["bar_met"] is False
    # fallback = min-FFR real threshold (tie -> highest recall_sm)
    real = [c for c in res["b1_curve"] if not c["threshold"].startswith("none")]
    exp_sel = min(real, key=lambda c: (c["ffr"], -c["recall_sm"]))
    assert res["b1_selected"]["threshold"] == exp_sel["threshold"], (res["b1_selected"], exp_sel)
checks += 1

# --- stage B end-to-end (write gold to a tmp file, call stage_score) ----------
tmp = Path("/tmp/m1_stageb_selftest"); tmp.mkdir(parents=True, exist_ok=True)
goldf = tmp / "gold.jsonl"
goldf.write_text("\n".join(json.dumps(g) for g in gold_rows) + "\n")
sj = tmp / "res.json"; smd = tmp / "rep.md"
M.stage_score(goldf, M1 / "b1_scores.jsonl", sj, smd)
res2 = json.loads(sj.read_text())
assert res2["b1"]["bar_met"] == res["bar_met"]
assert res2["b1"]["selected_operating_point"] == res["b1_selected"]
assert res2["agreement"]["canonical_counts"] == dict(Counter(canon.values()))
assert "AGENT-LABELED" in smd.read_text(), "report must carry the provenance banner"
checks += 3

print(f"STAGE-B SELFTEST OK — {checks} assertions passed.")
print(f"  synthetic gold: same={len(same)} related={sum(1 for v in canon.values() if v=='related-but-different')} "
      f"unrelated={len(unrel)}")
print(f"  curve rows: {len(res['b1_curve'])}  bar_met(synth)={res['bar_met']}")
print(f"  selected: {res['b1_selected']['threshold']} recall_sm={res['b1_selected']['recall_sm']} "
      f"ffr={res['b1_selected']['ffr']} f1={res['b1_selected']['f1']}")
print(f"  B0 oracle: recall_sm={res['b0']['recall_sm']} ffr={res['b0']['ffr']} f1={res['b0']['f1']}")
print("  (synthetic labels are a pipeline test, NOT real gold — do not cite)")
