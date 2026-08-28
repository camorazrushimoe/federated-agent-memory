# H1 Experience Cards — Results

> Status: **D3 gate fired — verdict published, no S2 treatment run** (the §7.1
> sweep and the §7.2 F5 fallback both returned NOT FIT under the
> pre-registered rule; per the rule no S2 treatment arm was run and no gate was
> lowered). The gate does not block the LLM-free baselines: the final round
> (2026-08-28) measured **B1 and B2 on the real 200-dialogue hold-out** (§3);
> B0 and T remain unrun. Numbers below come from run dirs (`metrics.json` /
> `cost.json`), `audit.json` or `compare.py` — never hand-typed.

## 1. Hypothesis

Experience cards extracted from finished chats, clustered into shared
canonical stories, and served as evidence packets to a later agent beat raw
retrieval of the past chat (B1) on naming the right `unlock_guideline` for a
hold-out dialogue.

**What would falsify it:** `T ≤ B1` on `unlock_hit_label` — the cards add
nothing over plain retrieval. That is a complete result.

## 2. Verdict

**NOT FIT for lexical card-text clustering on this data.** The D3 audit gate
(§7.1) fired before any S2 run: the pre-registered threshold sweep found **no
threshold in 0.05..0.35 with `cluster_purity >= 0.70` AND
`serve_rate_ceiling >= 0.30`** — `serve_rate_ceiling` peaks at **0.15**
(needs 0.30). Per the pre-registered rule, no S2 treatment arm was run and the
gates were not lowered. Curve: `audit_threshold_sweep.md` (raw rows in
`audit.json`). The F5 fallback (customer-turns key) also failed the same rule
— see §8. One line: **the signal did not live in the card text, and it did
not live in the raw text either — as lexical clustering keys, the signal is
nowhere; plain raw-text retrieval (B1, no cards) remains the only path that
serves.**

## 3. Primary table (T next to every baseline)

Measured 2026-08-28 in the final round on the real 200-dialogue hold-out
(`runs/2026-08-28_S2_B1`, `runs/2026-08-28_S2_B2`). B1 and B2 are LLM-free by
construction (cost.json: extract.calls=0, usd_total=0.0); B2 = 1.0 confirms the
scoring code (C-EV4). B0 and T were **not run** (D3 gate): B1/B2 are the only
arms the gate does not block, and no T number is fabricated from the sweep.

| arm | unlock_hit_label | wrong | abstain | serve_rate | USD/1k |
|--|--|--|--|--|--|
| B0 no memory | not run (D3 gate) | not run (D3 gate) | not run (D3 gate) | not run (D3 gate) | 0 |
| B1 raw retrieval, no cards | **0.735** | 0.26 | 0.005 | 0.995 | 0 |
| **T card pipeline** | not run (D3 gate) | not run (D3 gate) | not run (D3 gate) | not run (D3 gate) | — |
| B2 oracle | **1.0** | 0.0 | 0.0 | 1.0 | 0 |

> **T ≤ B1 — resolved by measurement: YES (B1 wins).** B1 = **0.735**
> (147/200) on the real hold-out; T was not run, so the comparison uses T's
> own measured serving ceiling from the pre-registered §7.1/F5 sweeps —
> `serve_rate_ceiling` peaks at **0.175** (customer-turns) / 0.15 (card-text),
> and a hit requires a served packet, so T ≤ 0.175 < 0.735 = B1. The card
> pipeline cannot beat plain raw retrieval on this data, even before its
> extraction cost is counted.

## 4. What the audit found (A1–A5)

A1–A5 computed on the pool (`audit.json`, `bin/audit.py`): A1 serve ceiling
**0.995** (raw customer text matches fine — the data has the coverage),
A2 B2 oracle **1.0**, A3 K-gate binds on 0 clusters in the sweep store,
A4 within-label card-text cosine median **0.084–0.100** — far below the
guessed 0.35 (A4 FIRED), A5 staleness off by construction under
`timeline=compressed`.

The A4 firing triggered the pre-registered §7.1 sweep, which found **no**
threshold satisfying both gates (see §2 and §8). Thresholds were **not**
amended after seeing results; the curve is the evidence.

## 5. Known limits

Copied honestly from `data/README.md` and the run (no PII to test the PII
gate; single vertical; single language; `unlock` is a dataset label, not a
human judgement; age-stale disabled by construction under
`timeline=compressed`; whether the `K=2` independence gate actually bound).

## 6. Judge block

_Inter-pass agreement and calibration status, or the word `uncalibrated`
(EVAL-PLAN §5). Pending D6._

## 7. What would change the verdict

Nothing within lexical clustering. The F5 run (§8) already separated the two
explanations for the primary NOT FIT: the key was not the problem. Within the
experiment's own rules (no embeddings, no threshold loosening — EVAL-PLAN
§11), no single cheap next experiment flips the verdict; the remaining open
question is whether the card concept adds anything over raw retrieval at all,
which only an embedding-based or semantic key could test — out of scope here.

---

## 8. F5 — alternative cluster key: customer turns

Pre-authorised fallback (EVAL-PLAN §7.2, decided 2026-08-28 BEFORE the sweep
result). One change only: the cluster key = the source dialogue's customer
turns (lowercased, concatenated) instead of `problem_shape + constraint +
unlock`. Same cards, same extraction, same scopes, same `K_INDEPENDENT`,
same serve path, same scoring code, same hold-out discipline. Run-time switch
`--cluster-key card-text|customer-turns` (default `card-text`); `SPEC.md`
not edited. The card-text default reproduces the committed sweep
byte-identically (31 rows × 5 columns, 0 diffs).

### 8.1 Both curves, same rule, same range (0.05..0.35 step 0.01)

| threshold | pairs_same_merged (CT / CC) | pairs_diff_merged (CT / CC) | cluster_purity (CT / CC) | shared_rate (CT / CC) | serve_rate_ceiling (CT / CC) |
|---|--:|--:|--:|--:|--:|
| 0.05 | 0.984 / 0.366 | 0.143 / 0.051 | 0.091 / 0.333 | 1.000 / 0.700 | 0.000 / 0.000 |
| 0.10 | 0.961 / 0.229 | 0.137 / 0.029 | 0.267 / 0.447 | 0.867 / 0.574 | 0.000 / 0.025 |
| 0.18 | 0.448 / 0.159 | 0.049 / 0.013 | 0.431 / 0.548 | 0.628 / 0.575 | 0.050 / 0.050 |
| 0.25 | 0.084 / 0.105 | 0.007 / 0.007 | 0.700 / 0.772 | 0.373 / 0.406 | 0.125 / 0.075 |
| 0.30 | 0.051 / 0.069 | 0.002 / 0.004 | 0.907 / 0.813 | 0.193 / 0.325 | 0.075 / 0.100 |
| 0.35 | 0.036 / 0.055 | 0.001 / 0.003 | 0.952 / 0.871 | 0.115 / 0.230 | 0.025 / 0.150 |

Full table: `audit_threshold_sweep_customer_turns.md` (raw rows in
`audit_f5_customer_turns.json`); the primary curve is
`audit_threshold_sweep.md` (`audit.json`).

### 8.2 Verdict (same pre-registered rule, one round)

**NOT FIT for lexical customer-turns clustering on this data** — no threshold
satisfies `cluster_purity >= 0.70` AND `serve_rate_ceiling >= 0.30`;
`serve_rate_ceiling` peaks at **0.175** (needs 0.30). This is the end of this
line: the finding is stronger, not weaker.

### 8.3 The one-line answer (EVAL-PLAN §7.2 reporting duty)

> **Did the signal live in the cards, in the raw text, or nowhere?**
> **Nowhere as a lexical clustering key.** Customer turns merge more eagerly
> (same 0.984 at t=0.05 vs card-text 0.366) but carry no better separation
> (diff rises with same — 0.143 vs 0.051 at the same threshold), so purity
> and serve coverage never co-satisfy the rule. The binding constraint is
> the serve path, not the key: the ~36-word card paraphrase matches a live
> query's customer turns at `>= 0.18` for at most **17.5%** of queries even
> under the alternative key, while raw-text-vs-raw-text coverage is 0.995
> (A1) — i.e. the data's signal lives in the raw text and is already
> harvested by the card-free baseline B1, which is exactly what the primary
> verdict's `T ≤ B1` interpretation predicts.

### 8.4 Primary verdict unaffected

The §2 verdict stands as written. `MODEL-MATRIX.md` still refers to the
primary configuration (`card-text`). No gate was relaxed for F5.

---

## Package facts

- Total size of the committed package: _stated at D8_.
- Machine + Python version where `--replay` was proven byte-identical:
  _stated at D8_.
