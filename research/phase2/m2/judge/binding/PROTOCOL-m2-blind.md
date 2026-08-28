# M2 Blind Reconstruction — Answering Protocol (pre-registered, v1.0)

**Round:** R2 (M2 extraction) · frozen on GH #6 5449115746 §3.
**Role:** independent judge (agent-judged). You answer per item, exactly
once per pass, from the item's `render` ONLY.

## 1. What you see

Each item carries: `item_id`, a `codename` (an anonymized identity — it
does NOT identify the conversation or the candidate type), `question`,
and `render` (the item's full text).

You are told NOTHING else: no conversation id, no candidate type, no
flow/subflow, no product, no transcript. Different passes present the
same items in different orders. You have no access to any other pass's
answers — that is by design (pass independence).

> **Scope note (interpretation, flagged for lead confirmation):** "no
> flow/band hints" means no hints attached to the PRESENTATION — the judge
> never receives item metadata (convo id, candidate type, construction
> band) alongside a render. A render that contains flow/subflow fields as
> part of its own content (the B2 unit's receipt, a frozen unit field) is
> the candidate being tested and is answered AS-IS; any value carried by
> those in-unit fields is part of the unit's measured value, not a
> presentation leak.

## 2. The three questions (answer each item on all three)

- **Q1 — the problem.** State the customer's problem: the intent (what the
  customer wants done) and the structure (the symptom/constraint that
  drove the resolution). One or two sentences.
- **Q2 — the binding constraint.** State the constraint/symptom that
  actually determined the resolution. If it cannot be identified from the
  render, answer exactly: `not identifiable`.
- **Q3 — what worked.** State the resolution actions, IN ORDER, as listed
  or described in the render. If none are present, answer exactly: `none`.

## 3. Rules

- **R1 — Answer from the render only.** No outside knowledge of the
  corpus, the product, or the item's provenance.
- **R2 — Do not infer from codename or order.** They are random.
- **R3 — Fidelity over plausibility.** If the render is thin (e.g. a bare
  action list), answer only what it supports; `not identifiable` is a
  legitimate Q2 answer and is NOT a failure.
- **R4 — English, concise.** Q1 ≤ 40 words, Q2 ≤ 25 words, Q3 ≤ 40 words.

## 4. Output contract

Write one JSON object per line, in the order the input file presents the
items:
`{"item_id": "<id>", "pass": <1|2>, "q1": "...", "q2": "...", "q3": "..."}`
One line per item, every item exactly once, in input order.

## 5. Honesty clause (read before quoting any number from this protocol)

All answering is AGENT-JUDGED. The inter-pass disagreement rate measures
the judge's OWN consistency under frozen rules — a self-consistency floor,
NOT human inter-rater agreement. It is never cited as "human agreement".
