#!/usr/bin/env python3
"""recall_preview.py — label-free recall-half analysis of the B1 curve.

Band = engineer's construction metadata (NOT a gold label). This is the
pre-gold half of the D18 operating curve: the recall axis. The FFR axis and
the bar verdict need the gold set (stage B).
"""
import json

d = json.load(open("/tmp/precompute_out.json"))
rows = [json.loads(l) for l in open("research/phase2/m1/b1_scores.jsonl")]
rc = d["b1_recall_curve_label_free"]

print(f"curve rows: {len(rc)} (1 sentinel + {len(rc)-1} unique thresholds)")
print("band sizes: " + ", ".join(f"{k}={v['n']}" for k, v in d["score_preview_by_band"].items()))
print()
print("Label-free recall half (band = engineer metadata, NOT gold):")
print(f"{'threshold':>12} | {'n_pool':>6} | {'R_sm':>6} | {'R_amb':>6} | {'R_snm':>6}")
# highest threshold (excluding pool-everything) at which recall_sm >= 60% —
# the tightest recall-meeting operating point on the label-free curve
first60 = None
for c in rc:
    if c["n_pooled"] == 0:
        continue
    if c["recall"]["should-match"] >= 0.60:
        first60 = c
if first60:
    idx = rc.index(first60)
    print("  recall_sm first reaches 60% at threshold " + first60["threshold"])
    for c in rc[max(0, idx-2): idx+4]:
        r = c["recall"]
        print(f"{c['threshold']:>12} | {c['n_pooled']:>6} | "
              f"{r['should-match']:>6.3f} | {r['ambiguous']:>6.3f} | {r['should-not-match']:>6.3f}")

sm = sorted([r["b1_cosine"] for r in rows if r["band"] == "should-match"], reverse=True)
snm = sorted([r["b1_cosine"] for r in rows if r["band"] == "should-not-match"], reverse=True)
amb = sorted([r["b1_cosine"] for r in rows if r["band"] == "ambiguous"], reverse=True)
t60 = sm[50]  # 51st-highest -> pools 51/85 = 60.0%
n_snm = sum(1 for x in snm if x >= t60)
n_amb = sum(1 for x in amb if x >= t60)
print()
print(f"crossing detail: 51st-highest should-match score = {t60:.6f} (pools 51/85 = 60.0%)")
print(f"at t={t60:.6f} also pools {n_snm}/51 should-not-match-band pairs "
      f"(label-free overlap; NOT the FFR — the FFR denominator is gold-`unrelated`) "
      f"and {n_amb}/34 ambiguous")

best = None
for t in sorted({x for x in sm} | {x for x in snm}):
    rsm = sum(1 for x in sm if x >= t) / 85
    rsnm = sum(1 for x in snm if x >= t) / 51
    if best is None or (rsm - rsnm) > best[1]:
        best = (t, rsm - rsnm, rsm, rsnm)
print()
print(f"best sm/snm separation (label-free): t={best[0]:.6f} "
      f"recall_sm={best[2]:.3f} R_snm={best[3]:.3f} gap={best[1]:.3f}")
# overlap: how many snm scores sit inside the sm recall region (cosine >= t60)?
overlap = sum(1 for x in snm if x >= t60)
print(f"should-not-match-band pairs with cosine >= t60: {overlap}/51 "
      f"= {overlap/51:.3f} of the false-friend band scores in the should-match region "
      f"(label-free; the real FFR is computed in stage B against gold-`unrelated`)")
