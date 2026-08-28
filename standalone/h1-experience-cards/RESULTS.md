# H1 Experience Cards — Results

**Status:** round 3 closed. The §7.1 A4 sweep (PR #41) published its NOT FIT
verdict; the pre-authorized §7.2 F5 sweep (alternative cluster key — customer
turns) ran its single round and its verdict is recorded below. Numbers below
are generated from the committed sweep JSONs (`audit.json`, `audit_f5.json`),
never hand-typed (RUN-PROTOCOL §5).

## 1. The hypothesis

Experience cards extracted from past dialogues carry a reusable signal that
helps a fresh dialogue (measured as `unlock_hit_label` on the frozen
hold-out, vs B0/B1/B2 baselines).

Falsifier, pre-registered (EVAL-PLAN §7.1/§7.2): if **no** cluster threshold
in 0.05..0.35 satisfies `cluster_purity >= 0.70` AND
`serve_rate_ceiling >= 0.30` — first for the card-text key, then for the
customer-turns key — the pipeline as configured cannot serve a meaningfully
pure memory, and the verdict is NOT FIT.

## 2. The verdicts

### 2.1 Primary configuration — lexical card-text clustering (EVAL-PLAN §7.1, PR #41)

**NOT FIT for lexical card-text clustering on this data — no threshold in 0.05..0.35 satisfies both gates; do not lower the gates, do not run a full S2 treatment arm**

### 2.2 Alternative cluster key — customer turns (EVAL-PLAN §7.2, F5, one round)

**NOT FIT for customer-turns clustering on this data — no threshold in 0.05..0.35 satisfies both gates; do not lower the gates, do not run a full S2 treatment arm**

### 2.3 The one-line answer

> The signal lived nowhere: neither the card-text key nor the customer-turns key meets the pre-registered gates (cluster_purity >= 0.70 AND serve_rate_ceiling >= 0.30) at any threshold in 0.05..0.35.

## 3. The two curves, side by side

### 3.1 Card-text cluster key (`audit.json`, PR #41)

| threshold | pairs_same_merged | pairs_diff_merged | cluster_purity | shared_rate | serve_rate_ceiling |
|---|--:|--:|--:|--:|--:|
| 0.05 | 0.3663 | 0.0508 | 0.3333 | 0.7000 | 0.0000 |
| 0.06 | 0.2951 | 0.0437 | 0.2812 | 0.7500 | 0.0000 |
| 0.07 | 0.2912 | 0.0409 | 0.3714 | 0.6857 | 0.0250 |
| 0.08 | 0.2701 | 0.0334 | 0.3750 | 0.6000 | 0.0000 |
| 0.09 | 0.2451 | 0.0322 | 0.3902 | 0.6341 | 0.0250 |
| 0.10 | 0.2292 | 0.0293 | 0.4468 | 0.5745 | 0.0250 |
| 0.11 | 0.2174 | 0.0260 | 0.4706 | 0.5686 | 0.0250 |
| 0.12 | 0.2187 | 0.0230 | 0.4717 | 0.6226 | 0.0500 |
| 0.13 | 0.2029 | 0.0201 | 0.5000 | 0.6207 | 0.0500 |
| 0.14 | 0.1910 | 0.0172 | 0.5000 | 0.5968 | 0.0500 |
| 0.15 | 0.1818 | 0.0158 | 0.5224 | 0.5821 | 0.0500 |
| 0.16 | 0.1831 | 0.0139 | 0.5075 | 0.5821 | 0.0250 |
| 0.17 | 0.1660 | 0.0131 | 0.5072 | 0.6232 | 0.0500 |
| 0.18 | 0.1594 | 0.0128 | 0.5479 | 0.5753 | 0.0500 |
| 0.19 | 0.1542 | 0.0106 | 0.6026 | 0.5641 | 0.0750 |
| 0.20 | 0.1462 | 0.0098 | 0.6707 | 0.5366 | 0.0750 |
| 0.21 | 0.1462 | 0.0088 | 0.6977 | 0.5233 | 0.0750 |
| 0.22 | 0.1278 | 0.0076 | 0.6957 | 0.4565 | 0.0750 |
| 0.23 | 0.1094 | 0.0071 | 0.7083 | 0.4375 | 0.0750 |
| 0.24 | 0.1080 | 0.0068 | 0.7677 | 0.4242 | 0.0750 |
| 0.25 | 0.1054 | 0.0065 | 0.7723 | 0.4059 | 0.0750 |
| 0.26 | 0.0975 | 0.0061 | 0.7788 | 0.3846 | 0.0750 |
| 0.27 | 0.0870 | 0.0060 | 0.7778 | 0.3611 | 0.0500 |
| 0.28 | 0.0856 | 0.0051 | 0.7818 | 0.3636 | 0.0500 |
| 0.29 | 0.0738 | 0.0046 | 0.7863 | 0.3333 | 0.1000 |
| 0.30 | 0.0685 | 0.0040 | 0.8130 | 0.3252 | 0.1000 |
| 0.31 | 0.0685 | 0.0037 | 0.8240 | 0.3120 | 0.0750 |
| 0.32 | 0.0698 | 0.0039 | 0.8359 | 0.2812 | 0.1500 |
| 0.33 | 0.0646 | 0.0038 | 0.8485 | 0.2500 | 0.1250 |
| 0.34 | 0.0567 | 0.0036 | 0.8507 | 0.2463 | 0.1500 |
| 0.35 | 0.0553 | 0.0030 | 0.8705 | 0.2302 | 0.1500 |

### 3.2 Customer-turns cluster key (`audit_f5.json`, F5)

| threshold | pairs_same_merged | pairs_diff_merged | cluster_purity | shared_rate | serve_rate_ceiling |
|---|--:|--:|--:|--:|--:|
| 0.05 | 0.9842 | 0.1428 | 0.0909 | 1.0000 | 0.0000 |
| 0.06 | 0.9842 | 0.1428 | 0.0909 | 1.0000 | 0.0000 |
| 0.07 | 0.9816 | 0.1416 | 0.2308 | 0.8462 | 0.0000 |
| 0.08 | 0.9816 | 0.1416 | 0.2308 | 0.8462 | 0.0000 |
| 0.09 | 0.9816 | 0.1406 | 0.1538 | 1.0000 | 0.0000 |
| 0.10 | 0.9605 | 0.1369 | 0.2667 | 0.8667 | 0.0000 |
| 0.11 | 0.9420 | 0.1331 | 0.3333 | 0.7778 | 0.0000 |
| 0.12 | 0.9328 | 0.1311 | 0.4000 | 0.7000 | 0.0000 |
| 0.13 | 0.9130 | 0.1270 | 0.3810 | 0.7619 | 0.0000 |
| 0.14 | 0.8419 | 0.1175 | 0.4815 | 0.5926 | 0.0000 |
| 0.15 | 0.7286 | 0.0996 | 0.4688 | 0.5625 | 0.0000 |
| 0.16 | 0.5942 | 0.0749 | 0.4571 | 0.6571 | 0.0500 |
| 0.17 | 0.5033 | 0.0584 | 0.5333 | 0.5111 | 0.0250 |
| 0.18 | 0.4480 | 0.0487 | 0.4314 | 0.6275 | 0.0500 |
| 0.19 | 0.3491 | 0.0365 | 0.4821 | 0.5893 | 0.0000 |
| 0.20 | 0.2951 | 0.0294 | 0.5373 | 0.5075 | 0.0000 |
| 0.21 | 0.2029 | 0.0223 | 0.5753 | 0.4795 | 0.0500 |
| 0.22 | 0.1739 | 0.0180 | 0.6471 | 0.3882 | 0.0500 |
| 0.23 | 0.1225 | 0.0121 | 0.6848 | 0.4022 | 0.0750 |
| 0.24 | 0.0856 | 0.0084 | 0.6471 | 0.3922 | 0.1250 |
| 0.25 | 0.0843 | 0.0071 | 0.7000 | 0.3727 | 0.1250 |
| 0.26 | 0.0830 | 0.0055 | 0.7815 | 0.3277 | 0.1750 |
| 0.27 | 0.0711 | 0.0039 | 0.8281 | 0.2969 | 0.1750 |
| 0.28 | 0.0685 | 0.0030 | 0.8456 | 0.2647 | 0.1750 |
| 0.29 | 0.0619 | 0.0025 | 0.8904 | 0.1986 | 0.0750 |
| 0.30 | 0.0514 | 0.0021 | 0.9067 | 0.1933 | 0.0750 |
| 0.31 | 0.0487 | 0.0017 | 0.9150 | 0.1765 | 0.1500 |
| 0.32 | 0.0501 | 0.0019 | 0.9211 | 0.1776 | 0.0750 |
| 0.33 | 0.0408 | 0.0019 | 0.9363 | 0.1529 | 0.0500 |
| 0.34 | 0.0382 | 0.0013 | 0.9571 | 0.1166 | 0.0250 |
| 0.35 | 0.0356 | 0.0011 | 0.9515 | 0.1152 | 0.0250 |

## 4. What the audit found (A1–A5)

A1: serve ceiling measured in the §7.1/§7.2 sweeps — `serve_rate_ceiling`
maxes at 0.15 for card-text and 0.175 for customer-turns on the pool tail
slice (see 3.1/3.2), i.e. the `serve_rate >= 0.30` gate is unreachable with
either key. A4: within-label card-to-card cosine median 0.084–0.100, fraction
of pairs >= 0.35 = 0.0 (recorded in EVAL-PLAN §7.1). The separation columns
(`pairs_diff_merged`) stay low for both keys — see the tables above.

## 5. Known limits

- The sweep measures the **ceiling** on serving (would the query get >= 1
  card); it is not an S2 treatment-arm measurement, which is not run while the
  ceiling gate is unmet (EVAL-PLAN §7.1).
- Customer-turns key is a single one-round probe (EVAL-PLAN §7.2), not a
  re-tuned pipeline.
- The customer-turns key merges eagerly at low thresholds — raw customer
  text shares boilerplate across problems (`pairs_diff_merged` 0.143 at
  0.05 vs 0.051 for card-text), so its purity only clears 0.70 where almost
  nothing merges (`shared_rate` collapses), and the serve ceiling is capped
  by the query-to-card match step (`MATCH_THRESHOLD`), not by the cluster
  key.
- Judge block (L3) and calibration remain pending; they are not reached while
  the value gates fail.

## 6. The judge block

_Pending — not reached (no S2 treatment run under NOT FIT)._

## 7. What would change the verdict

The cheapest next experiment would be widening scope (tenant → vertical) to
raise the serve ceiling (A1 contingency, EVAL-PLAN §7), or a different
similarity signal (embeddings are explicitly out of scope for this
experiment, SPEC §7). Both are follow-ups, not re-runs of the frozen rule.
