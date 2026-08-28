# M2 Reconstruction — Scoring Protocol (pre-registered, v1.0)

**Round:** R2 (M2 extraction) · frozen on GH #6 5449115746 §3.
**Role:** independent judge (agent-judged). The transcript IS visible in
this pass. For each item you: (1) write your own reference answers R1–R3
from the transcript, (2) score each of the three candidates against your
reference.

## 1. What you see

Each item carries: `convo_codename` (an anonymized conversation id — it
identifies nothing), `transcript` (the full conversation, "speaker: text"
turns), and `candidates` — three renders, each with a `codename`. The
codenames are random; they do NOT identify the candidate type. The
candidate order is shuffled. Do not infer candidate type from the codename
or the order (R2 below).

## 2. Step 1 — your own references (write these FIRST, before scoring)

From the transcript ONLY:
- **R1 — the problem.** Intent (what the customer wants done) and the
  structure (the symptom/constraint that drove the resolution).
- **R2 — the binding constraint.** The constraint/symptom that actually
  determined the resolution (or `not identifiable`).
- **R3 — what worked.** The resolution actions, in order.

## 3. Step 2 — score each candidate against your reference (rubric, frozen)

- **s1 (Q1 — the problem):** 1 = intent + structure both correct vs R1;
  0.5 = exactly one axis correct; 0 = wrong.
- **s2 (Q2 — the binding constraint):** 1 = the binding constraint (R2);
  0.5 = a real but non-binding constraint; 0 = none / wrong.
- **s3 (Q3 — what worked):** 1 = all resolution actions present and in
  order vs R3; 0.5 = all present, wrong order; 0.25 = at least half
  present; 0 = else.
- `value = (s1 + s2 + s3) / 3`.

Rules:
- **R1 — References from the transcript only.** Your R1–R3 must be
  derivable from the transcript; no outside knowledge.
- **R2 — No candidate-type inference.** Score by content only; the
  codenames are random.
- **R3 — Fidelity of the candidate decides.** Score what the candidate
  SAYS, not what you think it intended. A thin candidate that gets the
  one axis it carries right gets 0.5, not 0 (Q1 rule); Q2 `not
  identifiable` when your R2 is `not identifiable` scores 1.
- **R4 — Same standard for all three candidates.** The transcript itself
  is one of the candidates; score it by the same rubric as the others —
  its value is MEASURED, not assumed.
- **R5 — English.** R1–R3 and any notes in English; scores are exactly
  one of the frozen values above (no other numbers).

## 4. Output contract

One JSON object per line, one per item, in the order the input file
presents the items:
```
{"convo_codename": "<codename>",
 "r1": "...", "r2": "...", "r3": "...",
 "scores": {"<candidate codename>": {"s1": <v>, "s2": <v>, "s3": <v>}, ...}}
```
`scores` must contain ALL THREE candidate codenames. s-values: s1 ∈
{0, 0.5, 1}, s2 ∈ {0, 0.5, 1}, s3 ∈ {0, 0.25, 0.5, 1}.

## 5. Honesty clause (read before quoting any number from this protocol)

All judging is AGENT-JUDGED (single scoring pass, references + scores in
one fresh context). This pass has no "pass 2" — the agreement numbers
reported in this round are the BLIND answering passes' inter-pass
disagreement. Nothing here is "human gold" or "human agreement".
