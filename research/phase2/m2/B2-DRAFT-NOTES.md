# B2 DRAFT NOTES — 80 structured experience units (lead, lab-1) · R2/M2

**Artifact:** `b2_draft.jsonl` (80 rows, sha256:16 `5063a85c4ab79465`)
**Schema:** frozen (5449115746 §3; PR #22 skeleton) — key order
`problem_shape, constraint, unlock, what_worked, receipt{corpus, convo_id,
flow, subflow, event_span, scope, confidence}`. `what_failed` is **OUT** of
the R2 unit (pending §4 / R3) and is **not present** — no silent deviation.
**Source:** hand-drafted by the lead (proposal's author drafts the proposal,
5449115746 §4) from the frozen 80-convo sample (`sample.jsonl` sha
`f2195e7a6abe2221`), delexed transcripts read in full, one per convo.
`what_worked` = the mechanical ordered `targets[2]` trace (D11) taken from
the PR #22 B1 render, per the pre-registration definition; the lead's draft
is authoritative at join time.

## 1. Drafting conventions (frozen with this draft)

- **problem_shape** — normalized intent + the structure that drove the
  resolution, in the customer's own lowercase wording (so the R1 lexical key,
  customer-turn TF-IDF, can key it — 5449115746 §3 ties M2 to the R1 result).
  Budget ≤ 12 words (tightening pass; see §3).
- **constraint** — the constraint/symptom that **actually determined the
  outcome**, ≤ 12 words. Conventions:
  - purely informational convos (policy/faq/lookup with no conditioning state
    check) carry `none - <what was answered>`;
  - **denial** convos (return refused — 4332, shipping change impossible —
    5989, order unmodifiable — 7961, no remedy — 5687/9451, stockout —
    8890/8974) name the **blocking condition**: the denial *is* the outcome
    and it is the binding constraint;
  - escalation convos (2969, 8890) name the unfixable cause (site-only
    slowness; supply-side stockout).
- **unlock** — the pivotal customer turn that opened the resolution, ≤ 10
  words; **null** when the resolution followed the standard path (no pivotal
  turn). The field is honest about being often-null: on this corpus the
  binding state (membership level, order status, verify failure) is usually
  what the *agent* checks, not a question the customer opens.
- **receipt** — `corpus=abcd_v1.1`; `convo_id`; `flow`/`subflow` from the
  frozen sample row; `event_span=full_conversation` (the unit summarizes the
  whole delexed transcript — there is no finer event structure in the corpus;
  no wall-clock exists, D11/INGEST fact); `scope=single_conversation`;
  `confidence` = drafting confidence: **high** (resolution directly
  observable in the trace/transcript, 72), **medium** (resolution deferred,
  partly inferred, or multi-part — 5: 1224, 2856, 2969, 3167, 6902),
  **low** (no observable resolution / truncated convo — 3: 274, 755, 7534).
  This is *drafting* confidence, pre-scored; the judge's rubric is the
  measurement.

## 2. Token facts (frozen counter: whitespace-split of `json.dumps(unit)`,
default separators — interpretation #1, confirmed)

> **Numbers corrected (GH #6 5450060638 §3):** recomputed from the pinned
> artifacts (candidates + this draft, `5063a85c4ab79465`). The as-merged
> B0 sum (13,396) and B2 sum (3,202) were a precision error; the corrected
> values are below. The structural conclusion is unchanged.

- **schema floor (empty judgment fields):** 23 tokens (min); the skeleton
  render is **23–30 per convo** (median 25, total 2,046 across 80) — the
  mechanical `what_worked` + receipt prefill varies with the trace, so the
  floor is NOT a flat 23.
- **this draft:** min 37 / median 45 / max 57; **aggregate ratio B2/B0 =
  0.2390** (B0 sum **15,340**; B2 sum **3,667**).
- **per-convo `tokens(B2) ≤ tokens(B0)/10`: 0/80 — stated for the DRAFT.**
  The draft (37–57 tokens) is above the per-convo allowance (6.5–41.7) in
  every one of the 80 convos. The SKELETON (the thinnest conforming unit —
  mechanical prefill with null judgment fields), by contrast, is UNDER the
  per-convo allowance in exactly **7/80** convos (116, 274, 374, 1224, 3161,
  4332, 10059 — all in the large-B0 tail, B0 253–417) and above it in the
  remaining 73/80; in those 7 the allowance exceeds the skeleton by only
  0.3–16.7 tokens, so only token-neutral placeholder strings (no real
  content) would fit. The per-convo bar is therefore not met by the DRAFT
  in any convo — the 0/80 is the draft's, not a floor claim.
- The **median** B0 is 187 → median B2 allowed ≤ 18 tokens — **below the
  23-token empty-schema floor**. The frozen bar is **structurally
  unreachable by any content-bearing unit in the frozen schema**.

## 3. The token-side finding (reported with the round's numbers, not
negotiated — D18)

The pre-registered bar (value(B2) ≥ 0.8 × value(B0) **AND** tokens(B2) ≤
tokens(B0)/10, aggregate ratio ≤ 0.1) contains a token half that no unit in
the frozen schema can meet: the schema floor alone (23–30 tokens per convo)
exceeds the per-convo allowance in **73 of the 80** sampled B0 sizes (it
sits under the allowance only in the 7 large-B0 tail convos — 116, 274,
374, 1224, 3161, 4332, 10059 — which is why the "0/80-at-the-floor" claim
does NOT stand), and the **DRAFT** misses the per-convo bar in **all 80**
(37–57 tokens vs allowance 6.5–41.7). The aggregate ratio floor is
2,046/15,340 = **0.1334 > 0.1** (skeleton total 2,046, not a flat 23×80;
B0 sum 15,340). This is a property of the frozen schema + frozen counter +
frozen sample, independent of drafting effort. The draft therefore sits at
its most content-dense honest form (tightening pass v2) and **does not
hollow the unit toward the token bar** — hollowing would trade the value
side for the token side and falsify the M2 question. The round's numbers
will show, expected, **token half: FAIL (structural); value half: measured
by the blind judge**. B1 (the action trace) carries the token side —
aggregate 0.0186 (≤ 0.1) and 80/80 per-convo — and is the pre-registered
collapse candidate. Per D18 a missed bar is the finding: the expected
finding shape is *"the structured record cannot be 1/10 of the transcript
while carrying the schema; the unit's value is carried by ~44 tokens vs the
187-token median transcript — 2.4×, not 10×"* — unless the B1 trace alone
passes, in which case the pre-registered collapse (trace + label) applies.
This note goes with the m2 report and the #6 round post.

## 4. Falsification posture (unchanged, pre-registered)

- B1 (action trace) is scored **identically**; if B1 already reconstructs
  ≥ 80%, the unit collapses to trace + label — a finding, not a failure.
- If B2 cannot carry a reliable outcome, the §4/R3 collapse rule applies to
  `what_failed` (already OUT of this draft).
- Honesty clause rides with every M2 number: agent-drafted (lead) +
  agent-judged; inter-pass disagreement is a self-consistency floor, not
  human inter-rater agreement.

## 5. Handoff

- Slots straight into `b2_unit` of `candidates.jsonl` (PR #22) at join time
  (5449115746 §4 item 4): schema + key order frozen; `n_tokens_b2` recomputed
  on this unit by the join (frozen counter). **Landed:** the R2 fix-forward
  (GH #6 5450060638 §1) slotted this draft into the committed
  `candidates.jsonl` (final B2 render + final `n_tokens_b2` on the lead's
  unit, frozen counter, default separators — interpretation #1); the judge
  bind layers were re-bound from it, so the scored B2 is now the DRAFT unit,
  not the skeleton.
- Evaluation's blind S1 is unblocked by PR #22's staging (independent of
  this draft landing: the judge scores the **draft** unit — S0 intake says
  wait for the draft; this file IS the draft).
- What this file is NOT: the result line (no bar verdict here — that is the
  join's, with the judge's numbers).
