# M2 Reconstruction — Scoring Protocol (pre-registered, v1.0)

**Round:** R2 (M2 extraction) · frozen on GH #6 5449115746 §3.
**Role:** independent judge (agent-judged). The transcript IS visible in
this pass. This is a **two-call** procedure per conversation (the frozen
structure, restored per the lead adjudication, GH #6 5450060638 §2):

- **Call 1 — the reference.** The judge reads the TRANSCRIPT ONLY (no
  candidates in context) and writes its own reference answers R1–R3. The
  reference is the anchor of the rubric; it MUST be formed in a context that
  has NOT seen the candidates, so it is derived purely from the transcript.
- **Call 2 — the scoring.** In a fresh context the judge reads the transcript
  + the three anonymized candidates + its COMMITTED reference (Call 1's
  output), and scores each candidate against that reference with the frozen
  rubric.

The two calls are separate fresh agent contexts: Call 1 never sees the
candidates; Call 2 receives the committed reference as input.

## 1. What each call sees

- **Call 1 (reference):** `convo_codename` (an anonymized id — identifies
  nothing) + `transcript` (the full conversation, "speaker: text" turns).
  NOTHING else — no candidates.
- **Call 2 (scoring):** `convo_codename` + `transcript` + `reference`
  (the committed R1–R3 from Call 1) + `candidates` — three renders, each
  with a `codename`. The codenames are random; they do NOT identify the
  candidate type. The candidate order is shuffled. Do not infer candidate
  type from the codename or the order (rule R2 below).

## 2. Call 1 — the reference (transcript ONLY)

From the transcript ONLY:
- **R1 — the problem.** Intent (what the customer wants done) and the
  structure (the symptom/constraint that drove the resolution).
- **R2 — the binding constraint.** The constraint/symptom that actually
  determined the resolution (or `not identifiable`).
- **R3 — what worked.** The resolution actions, in order.

The reference is formed BEFORE and APART FROM any candidate. It is the
independent anchor; nothing about a candidate may influence it.

## 3. Call 2 — score each candidate against your committed reference (rubric, frozen)

- **s1 (Q1 — the problem):** 1 = intent + structure both correct vs R1;
  0.5 = exactly one axis correct; 0 = wrong.
- **s2 (Q2 — the binding constraint):** 1 = the binding constraint (R2);
  0.5 = a real but non-binding constraint; 0 = none / wrong.
- **s3 (Q3 — what worked):** 1 = all resolution actions present and in
  order vs R3; 0.5 = all present, wrong order; 0.25 = at least half
  present; 0 = else.
- `value = (s1 + s2 + s3) / 3`.

Rules:
- **R1 — Reference from the transcript only.** R1–R3 must be derivable from
  the transcript; no outside knowledge; formed apart from the candidates.
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

**Call 1** — one JSON object per line, one per item, in the order the input
file presents the items:
```
{"convo_codename": "<codename>", "r1": "...", "r2": "...", "r3": "..."}
```

**Call 2** — one JSON object per line, one per item, in the order the input
file presents the items:
```
{"convo_codename": "<codename>",
 "scores": {"<candidate codename>": {"s1": <v>, "s2": <v>, "s3": <v>}, ...}}
```
`scores` must contain ALL THREE candidate codenames. s-values: s1 ∈
{0, 0.5, 1}, s2 ∈ {0, 0.5, 1}, s3 ∈ {0, 0.25, 0.5, 1}.

## 5. Budget (frozen)

Per conversation: 1 reference call + 1 scoring call = 2 calls. 80
conversations → 160 calls. The whole round is 480 blind answering calls +
160 scoring calls = **640 — exactly the frozen ceiling** (5449115746 §3).

## 6. Honesty clause (read before quoting any number from this protocol)

All judging is AGENT-JUDGED. The reference and the scores are produced in
separate fresh contexts (the reference is candidate-free by design). The
agreement numbers reported in this round are the BLIND answering passes'
inter-pass disagreement. Nothing here is "human gold" or "human agreement".
