# M1 candidate-pair set — construction notes (Research Engineer, Phase 2 R1)

**Deliverable:** `research/phase2/m1/candidate_pairs.jsonl` (180 pairs) + the
deterministic builder `build_candidate_pairs.py`.
**Built to:** `research/phase2/labeling/CANDIDATE-PAIR-CONTRACT.md` v1.0
(pre-registered intake contract, lead-reviewed; on main via PR #13).
**Hypothesis served:** H-m1 (`docs/research-method-m1-m3.md` §M1) — two
conversations are "about the same problem" iff they share the same underlying
problem shape (intent + resolving constraint), despite different wording,
users, or products. This pair set is what the two-pass agent labeling
(`PROTOCOL-m1-pairs.md`, lab-1-evaluation) turns into the gold set that B0/B1/B2
are scored against. **Nothing in `candidate_pairs.jsonl` is a label.**

## 1. Re-run contract (lab-workflow §8)

```bash
python3 research/phase2/m1/build_candidate_pairs.py \
    --corpus data/abcd/abcd_v1.1.json \
    --out research/phase2/m1/candidate_pairs.jsonl
# seed 20260827 (default; also required in the commit message per contract §6)
```

- Deterministic: byte-identical output across re-runs (verified 2026-08-27).
- Corpus pinned by sha256 (first 16 hex): `005d425e890b30a1` (10,042 convs,
  8034/1004/1004).
- Builder self-checks band-vs-metadata on every pair (same-subflow /
  same-flow-diff-subflow / diff-flow / cross-product product test) before
  writing; a violation aborts the run.

## 2. Composition (pre-registered; contract §3 windows all satisfied)

| band | n | share | window |
|---|---|---|---|
| should-match (same subflow) | 84 | 46.7% | 45–55% |
| ambiguous (diff subflow, same flow) | 42 | 23.3% | 15–25% |
| should-not-match (diff flow) | 54 | 30.0% | 30–40% |
| — cross-product (both products non-empty, different) | 14 | — | ≥10 |
| — cross-flow (diff flow: 12 same non-empty product across flows + 12 both products empty) | 24 | — | ≥20 |
| — other-diff-flow (exactly one product empty) | 16 | — | — |
| **total** | **180** | | 150–200 |

- should-match is stratified over subflow size (large ≥150: 36, mid 50–149: 30,
  small <50: 18) so the band is not dominated by the biggest subflows.
- Each conversation is used in **at most 1 pair** (stricter than the contract's
  max 2); `conv_a != conv_b` always; (a, b) order carries no meaning.
- cross-flow "same non-empty product across flows" is the **hard false-friend**
  slice (same product wording, different problem) — the band the commission
  cares about most; it is deliberately over-represented inside cross-flow.
- cross-product is built from the 7,457 non-empty-product conversations only
  (25.7% of the corpus have `product = {amounts: [], names: []}`;
  `research/phase2/labeling/pair_capacity.md`).

## 3. Display (what the labeler reads; contract §5)

- **Customer turns only**, in order, `CUST:`-prefixed. Agent turns are
  boilerplate (method doc B1 definition); the contract permits their exclusion
  and requires the display stay "honest and minimal".
- First customer turn always present **in full** (the validator's faithfulness
  check). If a conversation's customer text exceeds 600 chars it is truncated
  **with an explicit marker line** (`[... N more customer turns omitted ...]`) —
  never silently (contract §5). 17 of 360 conversations in this set are
  truncated.
- Trailing `ACTIONS: a1, a2, …` line per conversation: the ordered
  action-trace names (`targets[2]` of `speaker: "action"` turns, D11). This is
  corroborating evidence of structure (protocol R4), **not** the label. The
  full trace (up to 8 names + count) is included even when the turns above it
  were truncated.
- No band labels, no oracle/guideline text, no comments in the display.

### FLAGGED DEVIATION — contract §5 header vs protocol R5 (ruling needed BEFORE pass 1)

Contract §5 says the per-conversation header line should carry `flow/subflow`;
protocol R5 (v1.1, LOCKED) forbids the labeler seeing flow/subflow metadata
during a pass, and contract §5 itself states *"Metadata lives in the JSON
fields; the display is the conversation text. Keeping them separate is the whole
point."* A `flow: X; subflow: Y` header would leak the band to the labeler and
invalidate both passes (e.g. "same subflow" ⇒ obvious should-match). **This
build uses neutral headers** (`CONVERSATION 1` / `CONVERSATION 2`). If
evaluation rules the literal §5 header wins, re-run with `--scenario-header` —
pair identities are unchanged (seeded), only display text changes. This is
surfaced per contract §3 ("flag objections BEFORE pass 1").

## 4. Verification evidence (2026-08-27, before handoff)

- `research/phase2/labeling/validate_pairs.py` (evaluation's intake gate, from
  merged main): **verdict `OK_TO_LABEL`**, 0 blocking, 0 warnings, max
  conversation reuse 1.
- Independent spot-check, 15 pairs × 2 conversations: first-turn-in-full,
  verbatim turn presence (truncation-marker aware), ACTIONS line == corpus
  trace, header neutrality — 0 failures.
- Determinism: two consecutive runs byte-identical.
- Rehearsal of evaluation's `split_passes.py` on this file: clean
  (pass inputs = `pair_id` + `display` only; `orders_differ: true`).
- Display length: median 766 chars, p90 1120, max 1312 — under the ~1500 target.

## 5. Pre-registered scoring plan (B0/B1/B2) — for the round after labeling

The gold set (`gold_m1_pairs_agentlabeled.jsonl`, canonical labels) is what the
methods are scored against. Stated now, before any score is looked at:

- **B0 — oracle (ABCD only):** "same" := same `subflow`. Trivially 1.0 within
  the should-match band; reported as the reference ceiling (method doc: it
  measures how much of "same" is already encoded vs. cross-subflow
  generalization). No threshold.
- **B1 — TF-IDF cosine over customer turns only** (agent boilerplate excluded),
  vectorizer and model fit per band at scoring time (the gold set is the only
  supervision; no corpus-level fitting on labeled data).
  **Threshold selection (pre-registered):** report the full
  (recall, false-friend) operating curve over a sweep of cosine thresholds.
  **Bar (frozen, D18):** B1 passes iff ∃ threshold t with
  **false-friend rate ≤ 10%** (share of gold-`unrelated` pairs that B1 pools)
  **at recall ≥ 60% on the should-match band** (share of should-match-band
  pairs pooled). If no such t exists, report the t minimizing false-friend
  rate and the recall at that point; the missed bar is the finding. Per-band
  recall and pairwise F1 vs gold are reported alongside (secondary).
- **B2 — small off-the-shelf embedding: run only if B1 misses the bar**
  (method doc §M1: it exists to falsify "the dumb one is enough"). Same bar,
  same threshold-sweep rule. If B1 passes, B2 is dropped and the finding is
  *"problem shape is lexical on this data."*

**Honesty clause:** all M1 gold labels are `agent-labeled` (two independent
passes of the same agent; protocol §3/§7). The disagreement rate is the
labeler's own consistency, never "human agreement".

## 6. Relation to the lead's phase1 draft

`research/phase1/m1_pairset_extract.py` (170 pairs, A=80/B=50/C=40, seed 42)
is the lead's kickoff draft. It predates the evaluation contract and does not
satisfy it (composition 29.4% ambiguous > 25% window; 23.5% should-not-match
< 30%; no sub_bands; different schema, no `pair_id`/`display`). **The set
delivered here supersedes it** as the pair set for labeling; the draft is
left on main untouched for reference. Flagged to lead in the PR + ping.
