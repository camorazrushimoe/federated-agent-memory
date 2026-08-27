# M1 Pair Set — Labeling Protocol (pre-registered, v1.0)

**Ticket:** BON-39 (Phase 2) · **Set:** M1 pair set (first of four gold sets)
**Labeler:** lab-1-evaluation, acting as independent measurer per the founder's
2026-08-27 decision on GH #6 (comment 5444338044, §4). The founder is **not** the
labeler; the lab lead is **not** the labeler. Both passes are performed by this
role.
**Provenance (non-negotiable):** this set is **agent-labeled**. Every artifact,
file, commit message, report line, and table that cites it MUST say
`agent-labeled`. It is NEVER "human gold" and is never cited as human gold.
**Date:** 2026-08-27 · **Status:** LOCKED before any pair is labeled.
Changes to the rules below require a version bump (v1.1, …) committed **with the
reason**, and apply to no item already labeled.

> Deviation note (recorded, not hidden): the Phase 1 method doc
> (`docs/research-method-m1-m3.md`, M1) proposed "two passes (lead + a second
> pass by evaluation)". The founder's decision of 2026-08-27 supersedes that
> logistics: both independent passes are performed by evaluation. **No
> pre-registered bar changes** (false-friend ≤ 10% at ≥ 60% recall; the
> disagreement rate remains a reported number).

---

## 1. What is labeled

Candidate pairs of ABCD conversations produced by the Research Engineer's
pair-construction code (lands before labeling starts). Each pair carries
machine metadata: `pair_id`, `band`, conversation ids, flow/subflow ids, and
display content (customer turns and, where the engineer includes them, the
action-trace fields per D11).

Bands (per the method doc, stratification is the engineer's job; I label what
is given, band stated per item):

| band | definition | role in the metric |
|---|---|---|
| `should-match` | same subflow, different surface | recall denominator |
| `ambiguous` | different subflow, same flow | secondary |
| `should-not-match` | different flows / different products — **includes the cross-flow band** | false-friend denominator |

## 2. The scale (3 classes, fixed)

1. **`same-problem`** — the pair shares the same *underlying problem shape*:
   the intent (what the customer wants done) **and** the problem structure that
   actually drove the resolution (the symptom/constraint that mattered),
   despite different wording, users, or products.
2. **`related-but-different`** — the two problems sit in the same or
   overlapping area (e.g. both are returns) but the constraint/symptom that
   determined the resolution differs (e.g. "item too small for the child" vs
   "item damaged on arrival"). Same intent, different problem shape.
3. **`unrelated`** — different problem shapes; pooling these two conversations
   into one memory entry is a **false friend** (different flows / different
   product domains).

### Adjudication rules (applied identically in both passes)

- **R1 — Intent alone is not `same-problem`.** Same intent with a different
  resolving constraint → `related-but-different`.
- **R2 — Structure trumps surface.** Different wording of the same intent +
  same resolving constraint → `same-problem`.
- **R3 — Product identity is never the label.** Product match alone ≠
  `same-problem`; product mismatch alone ≠ `unrelated`. Label the problem
  shape, and only from problem shape. (Cross-flow / cross-product pairs are
  judged on shape exactly like same-flow pairs.)
- **R4 — Evidence order.** Judge from the customer's stated problem and the
  constraint that drove the resolution, as visible in the pair display. The
  action trace (what was done) is corroborating evidence of structure, not the
  label: if the customer statements show different symptoms, the symptom
  difference wins over identical action sequences.
- **R5 — No peeking at band or oracle labels as evidence.** Band metadata is
  recorded, not used as adjudication input: a `should-match` pair whose two
  conversations genuinely describe different problem shapes is
  `related-but-different` or `unrelated`. The oracle (same subflow) is the B0
  reference for the *methods*, not a label source.
- **R6 — Borderline default.** When a pair is genuinely borderline between
  `same-problem` and `related-but-different`, label
  `related-but-different` (conservative against pooling — the commission weighs
  false friends as heavily as true matches). When genuinely borderline between
  `related-but-different` and `unrelated`, label `unrelated`.

## 3. Two independent passes — mechanism

- **Pass 1** and **Pass 2** are separate runs. Pass 2 is performed without
  access to pass 1's labels: the mechanical guarantees are
  (a) pass 2's input file contains **no** pass 1 fields — enforced by
  `split_passes.py` asserting the field set; (b) the two input files present
  pairs in **different, seeded orders** (seeds `20260827` / `20260927`) so no
  positional priming; (c) the pass 2 run starts from the raw pair displays
  only — pass 1's output file is not open, not referenced, and not in context
  when pass 2 is produced.
- Each item is labeled exactly once per pass, with a one-line rationale.
- **Honesty clause (read before quoting any number from this protocol):**
  both passes are produced by the same agent (same model, two independent
  runs). The inter-pass disagreement rate therefore measures *the labeler's
  own consistency*, not human–human inter-rater agreement. It is a necessary
  consistency floor and an early warning that the definition is not
  operational; it must never be cited as "human agreement". The human anchor
  is the founder-review escalation in §5.

## 4. The reported numbers

- **Inter-pass disagreement rate (the headline number, per set):**
  `disagreement_rate = (# pairs where pass1_label != pass2_label) / (total pairs)`
  reported per set **and** per band, as a number (e.g. `0.083 (12/144)`).
- **Direction breakdown** (disagreements split into):
  - `adjacent` — `same-problem` vs `related-but-different`;
  - `cross-unrelated` — any pass `unrelated` vs the other pass
    `same-problem` (the dangerous direction: it moves a pair in/out of the
    false-friend class).
- **Canonical label** (pre-registered rule for downstream B1/B2 scoring):
  - passes agree → that label;
  - passes disagree and either pass said `unrelated` → `unrelated`
    (conservative: protects the pre-registered false-friend bar; flagged
    `disagreed-upgraded`);
  - passes disagree between `same-problem` and `related-but-different` →
    `related-but-different` (conservative against pooling; flagged
    `disagreed-downgraded`).
- Canonical labels are used for method scoring; the per-pass labels are
  committed in full so anyone can re-derive every number.

## 5. Escalation (pre-registered)

If the inter-pass disagreement rate **exceeds 15%** (strictly > 0.15) on any
set: **STOP** that set and escalate a **20-item sample** for founder review —
not the whole set. Sample construction (deterministic, seed `20260827`):
all disagreement items (up to 20, band-stratified so every band with a
disagreement appears), padded with seeded agreement items to reach 20 if
fewer than 20 disagreements exist. The sample ships as
`escalation_sample.md` with both passes' labels + rationales side by side.

## 6. Artifacts (all committed, per-item, regenerable — lab-workflow §8)

| artifact | content |
|---|---|
| `candidate_pairs.jsonl` | engineer's pairs (input; metadata, no labels) |
| `pass1_input.jsonl` / `pass2_input.jsonl` | seeded, shuffled displays (manifest: seeds, sha256, counts) |
| `pass1_labels.jsonl` / `pass2_labels.jsonl` | per-item: `pair_id, pass, label, rationale` |
| `gold_m1_pairs_agentlabeled.jsonl` | **per-item full record**: pair metadata + both pass labels + rationales + `agreed` + `canonical_label` + flag. This is the committed gold set. Provenance field: `agent-labeled`. |
| `agreement_report.md` / `agreement.json` | the numbers of §4, per set and per band, with the >15% check and escalation flag |
| `escalation_sample.md` | only if §5 fires |

Re-run contract: `split_passes.py` (pairs → pass inputs) and
`score_agreement.py` (pass labels → gold set + report) are deterministic;
re-running them on the committed files reproduces every number. The pair
metadata in `gold_m1_pairs_agentlabeled.jsonl` is a snapshot at label time, so
the gold set is frozen even if upstream data files move.

## 7. Self-critique (what this design can and cannot support)

- **Strength:** frozen definitions + mechanical pass separation + per-item
  commit + pre-registered escalation = the disagreement number is honest and
  re-derivable.
- **Limitation 1 (named):** one agent, two passes. The disagreement rate
  under-covers human variability; a founder-reviewed 20-item sample is the
  only human signal. If disagreement is low, that says *the agent is
  consistent with itself under frozen rules*, not that humans agree.
- **Limitation 2 (named):** the canonical-label rule is conservative toward
  `unrelated` on disagreement. It biases the false-friend rate **up** on
  disputed pairs — the safe direction for the pre-registered bar, but it means
  the gold set slightly over-represents `unrelated` relative to a
  lenient-adjudication gold set. Recorded so a later reader does not mistake
  it for a corpus property.
- **Limitation 3 (named):** band labels come from the engineer's construction
  code (subflow/flow ids), not from me. If the construction mislabels a band,
  per-band numbers inherit the error. I verify band consistency spot-wise at
  split time (counts vs the engineer's stated stratification) and report any
  mismatch rather than silently fixing it.
- **What would change this protocol:** nothing short of a founder instruction.
  Rubric changes mid-labeling are forbidden without a version bump and apply
  only forward.
