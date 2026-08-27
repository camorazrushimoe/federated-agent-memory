# M1 candidate-pair set (pinned 170) — construction notes

**Deliverable:** `research/phase2/m1/candidate_pairs.jsonl` (**170 pairs**) + the
deterministic builder `build_candidate_pairs.py`.
**Built to:** `research/phase2/labeling/CANDIDATE-PAIR-CONTRACT.md` v1.0 (on main
via PR #13) and the **lead-pinned composition** from the round-1 kickoff
(lead, 2026-08-27, GH #6 comment 5445829777): **170 = 85 should-match / 34
ambiguous / 51 should-not-match (cross-flow ≥ 20, cross-product ≥ 10, remainder
other-diff-flow)**.
**Ticket:** BON-41 (M1) under BON-39 · **Hypothesis served:** H-m1
(`docs/research-method-m1-m3.md` §M1). **Nothing in `candidate_pairs.jsonl` is a
label or a hint.**

## 0. Coordination note — read first (duplicate wake, two pair sets exist)

This branch was cut from `main @cf04885`. While this set was being built, a
**concurrent same-role instance** (spawned by the same round-1 wake) landed an
**180-pair set** on main via **PR #14 (merged, commit `0a90b95`, merge `cf04885`)**
plus PR #15 (BON-40, TWCS §3). Both sets validate `OK_TO_LABEL`. The two differ:

| | this set (pinned) | PR #14 set (on main) |
|---|---|---|
| total | **170** (lead-pinned) | 180 (within §3 windows, not the pin) |
| bands | **85 / 34 / 51** (lead-pinned) | 84 / 42 / 54 |
| sub-bands | cross-flow 20 / cross-product 10 / other-diff-flow 21 | cross-flow 24 / cross-product 14 / other-diff-flow 16 |
| seed | **42** (method-doc default; matches lead's phase-1 draft) | 20260827 |
| max convo reuse | 2 | 1 |
| display header | neutral (R5-safe; `--scenario-header` available) | neutral (same call) |

This PR updates the **canonical path** `research/phase2/m1/candidate_pairs.jsonl`
to the lead's pinned 170 set. The 180 set remains fully recoverable in git
history (`0a90b95` / `cf04885`) and is **not** destroyed. **The labeler must label
exactly one set** — the pinned 170 set is the round-1 artifact per the lead's
explicit assignment; a one-line lead ruling on GH #6 (which set pass 1 runs on)
is enough, and if the 180 set is chosen the labeler should `git checkout 0a90b95
-- research/phase2/m1/candidate_pairs.jsonl` instead. The two sets share no
labeling work: pass inputs are rebuilt per set by `split_passes.py`.

Also flagged for the lead: **PR #14 was merged without a lead review being
posted** on it (D17: crew merges after lead review). Not re-litigating here —
just recording it for the record.

## 1. Re-run contract (lab-workflow §8)

```bash
python3 research/phase2/m1/build_candidate_pairs.py \
    --abcd data/abcd/abcd_v1.1.json \
    --out research/phase2/m1/candidate_pairs.jsonl \
    --seed 42
```

- **Deterministic:** byte-identical output across re-runs (verified 2026-08-27,
  sha256 `42215fc5969e…` for this file).
- **Corpus pinned by sha256 (first 16 hex): `005d425e890b30a1`** (10,042 convos;
  8034/1004/1004) — identical file to the one PR #14 pinned.
- **Seed: 42** (recorded here + in the commit message, contract §6). 42 is the
  seed the method doc and the lead's phase-1 draft already use, so the pinned set
  and the phase-1 reference share seed semantics.
- Builder self-checks the full pinned composition (band counts, sub-band counts,
  max reuse ≤ 2, range 150–200) before writing; any deviation aborts the run.

## 2. Composition (lead-pinned; contract §3 windows all satisfied)

| band | n | share | §3 window |
|---|---|---|---|
| should-match (same subflow, diff convo) | 85 | 50.0% | 45–55% |
| ambiguous (diff subflow, same flow) | 34 | 20.0% | 15–25% |
| should-not-match (diff flow) | 51 | 30.0% | 30–40% |
| — sub_band cross-flow | 20 | — | ≥ 20 |
| — sub_band cross-product | 10 | — | ≥ 10 (from the 7,457 non-empty-product convos) |
| — sub_band other-diff-flow | 21 | — | remainder |
| **total** | **170** | | 150–200 |

**Sub-band partition (unique clean partition, documented):** unordered
different-flow pairs split into exactly three mutually exclusive classes:
(1) both products non-empty + same product → **cross-flow**; (2) both non-empty +
different product → **cross-product** (contract §4 definition, verbatim);
(3) at least one product empty → **other-diff-flow** (contract §4). This is the
only assignment that keeps `validate_pairs.py` at 0 warnings (it warns whenever a
pair has two different non-empty products but is not labeled cross-product).
cross-flow = same non-empty product across different flows is deliberately the
**hard false-friend slice** (identical product wording, different problem) — the
band the commission cares about most.

- should-match is spread across subflows (size-descending cycle, 1–2 pairs per
  subflow) so the band is not dominated by the biggest subflows.
- Each conversation is used in **at most 2 pairs total** (contract max; tracked
  globally across bands; this run: max = 2, 318 unique conversations).
- `conv_a != conv_b` always; (a, b) order carries no meaning.
- Cross-flow/cross-product pools are vast (24.1M / 96.8k candidate pairs;
  `research/phase2/labeling/pair_capacity.json`), so the draw is effectively
  uniform-random under the seed.

## 3. Display (what the labeler reads; contract §5)

- **Customer turns only**, in order, `CUST:`-prefixed. Agent turns are excluded
  (boilerplate; method doc B1 definition; contract §5 permits the exclusion and
  requires the display stay honest and minimal).
- First customer turn always present **in full** (the validator's faithfulness
  check). Longer customer turns are truncated at a word boundary with a trailing
  ` ...` marker (13 of 170 pairs contain at least one truncated turn; truncation
  only ever hits late turns, never the first).
- Trailing `ACTIONS: a1, a2, …` line per conversation: the ordered action-trace
  names (`targets[2]` of `speaker:"action"` turns — D11). Corroborating evidence
  of structure (protocol R4), **not** the label.
- No band labels, no oracle/guideline text, no comments in the display.
- Display length: min 338 / median ~813 / **max 1415** chars (target ≤ ~1,500).

### FLAGGED DEVIATION — contract §5 header vs protocol R5 (ruling needed BEFORE pass 1)

Contract §5 says the per-conversation header line should carry `flow/subflow`;
protocol R5 (v1.1, **LOCKED**) forbids the labeler seeing flow/subflow metadata
during a pass, and contract §5 itself states *"Metadata lives in the JSON fields;
the display is the conversation text. Keeping them separate is the whole point."*
A `flow: X; subflow: Y` header would leak the band structure to the labeler
("same subflow" ⇒ obvious should-match; "diff flow" ⇒ obvious should-not-match)
and invalidate both passes. **This build therefore uses a neutral header**
(`CONVERSATION 1` / `CONVERSATION 2`) — the R5-safe choice, and the same call the
pre-merged PR #14 set made. If the lead/evaluation rule that the literal §5
header wins, re-run with `--scenario-header` (pair identities are unchanged;
only the display text changes). Surfaced per contract §3 ("flag objections
BEFORE pass 1"). **Until a ruling lands, the neutral display is the default and
the one the labeler should use.**

## 4. Verification evidence (2026-08-27, before handoff)

- `research/phase2/labeling/validate_pairs.py` (evaluation's intake gate, from
  merged main; run with `--corpus data/abcd/abcd_v1.1.json` since the baked-in
  default path does not exist in the current env):
  **verdict `OK_TO_LABEL`, 0 blocking, 0 warnings**, max conversation reuse 2,
  band counts 85/34/51, sub-band counts 20/10/21, in pre-registered range.
- **Full-set audit (all 170 pairs × 2 convos, not a sample):** exact contract
  field set per line (nothing extra; `sub_band` present iff should-not-match);
  R5 neutrality (no `flow:`/`subflow:`/band/label-class tokens in any display);
  display faithfulness (every `CUST:` line an in-order exact-or-truncated prefix
  of the corresponding corpus customer turn; first turn in full; `ACTIONS:` line
  == corpus `targets[2]` trace). **0 problems.**
- Determinism: consecutive runs byte-identical (sha256 match).
- Rehearsal of evaluation's `split_passes.py` on this file: clean
  (`orders_differ: true`; pass inputs carry only `pair_id` + `display`).
- The parallel 180-set on main was also independently re-validated in this
  session: `OK_TO_LABEL`, 0 blocking/0 warnings (recorded in §0).

## 5. Pre-registered scoring plan (B0/B1/B2) — for this round, after the gold set lands

The gold set (`gold_m1_pairs_agentlabeled.jsonl`, canonical labels) is what the
methods are scored against. Stated now, before any score is looked at
(preserving the pre-registration already made in the PR #14 README, adapted to
this set):

- **B0 — oracle (ABCD only):** "same" := same `subflow`. Trivially 1.0 within the
  should-match band; reported as the reference ceiling (how much of "same" is
  already encoded vs cross-subflow generalization). No threshold.
- **B1 — TF-IDF cosine over customer turns only** (agent boilerplate excluded).
  **Threshold selection (pre-registered):** report the full
  (recall, false-friend) operating curve over a sweep of cosine thresholds.
  **Bar (frozen, D18):** B1 passes iff ∃ threshold t with **false-friend rate
  ≤ 10%** (share of gold-`unrelated` pairs that B1 pools) **at recall ≥ 60% on
  the should-match band** (share of should-match-band pairs pooled). If no such
  t exists, report the t minimizing false-friend rate and the recall at that
  point; the missed bar is the finding. Per-band recall and pairwise F1 vs gold
  reported alongside (secondary). Inter-pass disagreement % reported with the
  honesty clause (agent self-consistency, not human agreement).
- **B2 — small off-the-shelf embedding: run only to falsify** "the dumb one is
  enough" (falsification-only, per lead's round-1 brief). If B1 passes, B2 is
  dropped and the finding is *problem shape is lexical on this data.*

**Round-1 handoff point (brief §8):** inter-pass disagreement % + B0/B1
per-band false-friend rate & should-match recall + verdict vs the D18 bar, in a
commit/PR.

## 6. Relation to the lead's phase1 draft

`research/phase1/m1_pairset_extract.py` (170 pairs, A=80/B=50/C=40, seed 42) is
the lead's kickoff **pre-contract reference** (JSON, A/B/C, no schema/display).
The lead's kickoff explicitly says its output is **not** to be shipped as the
pair artifact; the pinned composition (85/34/51 + sub-bands) **replaces** its
80/50/40. That script is left on main untouched for reference.
