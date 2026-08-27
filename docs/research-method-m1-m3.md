# Phase 1 — Method Proposal for M1–M3

**Commission:** Shareable Experience for Federated Agent Memory (`docs/research-commission-shareable-experience.md`)
**Ticket:** BON-38 · thread: GH #6
**Author:** research-lead (lab-1) · **Date:** 2026-08-27
**Status:** PROPOSAL — pre-registered before any result is looked at. Per the commission, the method and criteria are the lab's; the product's old numeric thresholds were removed on purpose and are **not** used here. Each criterion below is stated *before* the relevant experiment runs, names a baseline, and says what would change the verdict.

> **Gate honored (DECIDED D13):** this is a *method* document, no results. It proceeds now on the strength of the lead-accepted Phase 0. **No data-dependent experiment in this plan runs until BON-36 posts REPRODUCE.** Everything measured in Phase 2 will be re-derivable by extending `research/probe_dataset.py` (numbers discipline, workflow §8).

---

## 0. The one spine every M shares

Before splitting into M1/M2/M3, the three experiments share four fixed choices that come out of the Phase 0 facts (DECIDED list). Fixing these up front is what keeps the three M's from re-deriving the same ground truth three times.

1. **Group at flow level, not subflow.** (D5) 96 subflows, median 69.5, 54/96 under 100 — underpowered. 10 flows, 713–1,094 each — healthy. All comparison/valuation statistics are computed at flow level; subflow is used only to build and *inspect* examples.
2. **The action trace is the ground truth for "what was done."** Action names live in `targets[2]` of `speaker:"action"` turns — `[subflow, "take_action", "<name>", [args], -1]`. (D11) Every M's notion of "what the agent did" reads this field, never a free-text guess.
3. **The playbook is now joinable at 100%.** The 96→55 mapping (PR #9, `research/abcd_subflow_mapping.json`) lifts naive-join coverage from 0.456 to 1.0. So "what the agent *should* have done" (the documented playbook sequence per subflow) can be compared against "what they did" (the trace) across the **whole** corpus, not 45.6%.
4. **Outcome is a first-class research problem, not preprocessing.** No accepted corpus hands a reliable outcome column. Wherever a method needs "did it go well?", it uses an explicit, pre-registered derivation (§4) and reports that derivation's own error — it does not assume a label.

**The echo trap is a global constraint (commission §2/M3).** Anything that counts evidence for a unit MUST distinguish *independent confirmation* from *the unit's own echo* (the counter feeding on its own downstream influence). This is not one M's problem; it is baked into the spine so M1's "pool" and M3's "promote" cannot silently re-introduce it.

---

## M1 — Comparison: when are two conversations "about the same thing"?

### Working definition
Two conversations are **about the same problem** when they share the same *underlying problem shape* — the intent (what the customer wants done) **and** the problem-structure that actually drove the resolution (the symptom/constraint that mattered) — *despite* different wording, users, or products.

I deliberately split this into two testable axes, because the commission cares about the **definition and its failure modes**, not the vendor:
- **Axis A — intent match:** what is being requested (refund / shipping / defect / troubleshoot / …).
- **Axis B — structure match:** the constraint/symptom that actually determined the fix (e.g. "item too small for the child" vs "item damaged on arrival" are both returns, different problem shapes).

"A useful answer" per the commission = an operational definition a human agrees with, **plus** where it breaks (pairs that look similar but must **not** be pooled).

### Baselines (dumb versions, in order of ambition)
- **B0 — oracle label (ABCD only):** "same" := same `subflow` label. This is the ground-truth ceiling *within* a subflow (trivially 1.0) and is the reference the real test is judged against. It exists so we can measure how much of "same" is *already* encoded vs how much is cross-subflow/cross-product generalization.
- **B1 — lexical, no model:** TF-IDF cosine over **customer turns only** (agent boilerplate excluded). The dumb baseline every semantic method must beat.
- **B2 — small embedding (optional):** a single off-the-shelf sentence embedding. **Included only to falsify "the dumb one is enough."** If B1 already passes the bar, B2 is dropped and we report *"problem shape is lexical on this data"* — a finding, not a vendor pick.

### What we measure + pre-registered criteria (BEFORE looking)
Build a **human gold set** of ~150–200 labeled pairs, stratified across three difficulty bands:
- **should-match:** same subflow, different surface.
- **ambiguous:** different subflow, same flow.
- **should-not-match:** different flows / different products (the false-friend band).

Each pair is labeled by two passes (lead + a second pass by evaluation) as **same-problem / related-but-different / unrelated**. Agreement between the two labelers is itself a reported number (if we can't agree, the "definition" is not operational).

For each candidate method (B1, and B2 only if warranted):
- **Primary metric — precision on the dangerous class.** The commission weighs false friends as heavily as true matches, because pooling a wrong problem poisons shared memory. **Bar: a method is a usable "same problem" definition only if it keeps the false-friend rate (pooling a pair labeled *unrelated*) at ≤ 10%, at ≥ 60% recall on the should-match band.**
- **Secondary:** pairwise F1 vs gold overall; per-band recall; the labeler agreement rate.

**What would change my mind:**
- If **B1 (lexical) already meets the bar**, the problem shape on this data is lexical, not semantic — embeddings add cost, not value. We say so and stop.
- If **no method keeps the cross-flow / cross-product false-friend rate ≤ 10%**, then "same problem" is only identifiable *within* a flow, and the sharing scope (commission §8.1 — open empirical question) is **constrained to vertical/flow**, not global. That is a first-class finding, not a failure.

### Hard vs impossible (this data)
- **Hard:** cross-flow, cross-product generalization (same shape, different product wording).
- **Not testable here (report as such):** M1 *across corpora* (ABCD ↔ TWCS) — different domains; we do not pool a definition learned on one onto the other without its own gold set. Treat as a separate, likely-negative, out-of-scope-for-Phase-2 item.

---

## M2 — Extraction: what is the unit worth keeping?

### Working definition (the unit I propose — to be falsified, not inherited)
A structured **experience record**, not a transcript:

```
{
  problem_shape:    normalized intent + structure (the M1 key)
  constraint:       the constraint/symptom that actually mattered
  unlock:           the question/turn that opened the resolution (if identifiable)
  what_worked:      the resolution action sequence (from targets[2])
  what_failed:      the deviation from the expected playbook (§4) — only if §4 is sound
  receipt:          source span/trace id, flow, event index, scope, confidence
}
```

The commission's own guess is exactly the middle fields; my job is to **draft it by hand from real conversations and test whether it survives the transcript being dropped.** The `receipt` field is what makes the echo trap (M3) and provenance auditable.

### Baselines
- **B0 — keep the full transcript:** the thing we're trying to avoid. Sets the irrelevance/size upper bound (median transcript length is measured, not assumed).
- **B1 — action trace only:** the ordered `targets[2]` action-name sequence, no natural language. Cheap, fully reproducible, the "what was done" skeleton.
- **B2 — the structured record above (my proposal).**

### What we measure + pre-registered criteria (BEFORE looking)
Hand-draft experience records for a **stratified sample (~60–100 conversations across all 10 flows)**. For each, run a **reconstruction test**: hide the transcript; a second reader (or a rubric-scored LLM judge) must, from the unit alone:
1. re-identify the problem (the M1 key),
2. state the constraint that mattered,
3. state what worked, and (if §4 is sound) what failed.

- **Bar — preservation with shrinkage:** the unit is worth keeping if, for **≥ 70% of sampled conversations**, it preserves **≥ 80%** of the rubric-scored value of the full transcript, **while being ≤ 1/10 of the transcript's token count.** If it can't be that much smaller, there is no point.
- **Honest loss ledger:** for every field, document what is *lost* when the transcript is dropped (the commission explicitly wants this). E.g. tone, the customer's actual words, multi-constraint interactions.
- **Falsification probe on the outcome field:** the commission's unit includes "what worked / what failed." That field *is* the outcome label — the known weak point. **Pre-registered:** if `what_failed` (deviation-from-playbook, §4) is unreliable for a majority of the sample (low §4 agreement), the unit **collapses to {problem_shape, constraint, resolution-action}** and that collapse is a reported finding — we do not force an outcome field the data can't support.

**What would change my mind:**
- If **B1 (action trace alone) already reconstructs ≥ 80%** for the sample, the natural-language record is overhead and the unit is *the action sequence + a label*.
- If the structured record **cannot carry a reliable outcome**, M2 and M3 merge into: *"on this data we cannot separate 'what was done' from 'what worked'"* — a complete, usable negative.

### New Phase-0 fact that shapes this
**TWCS's `summary` column is 100% empty (0 / 794,335 non-empty)** — verified on the downloaded parquet, 2026-08-27. "Use the dataset's own summary" is therefore **not** a usable M2 baseline; the unit must be built from transcript + trace. Recorded so it is not rediscovered.

---

## M3 — Valuation: what earns a place in shared memory, on what evidence?

### Working definition
A unit earns publication if it is **(a) independently confirmed** (recurs in multiple conversations **not** attributable to a single source or to the unit's own downstream echo) **and (b) action-relevant** (it would change a consequential next step). Rank rises with *independent* confirmations and with confirmed-outcome strength (§4); the counter is kept honest against the echo trap.

### Baselines
- **B0 — publish everything:** the no-valuation baseline. Measures the pollution (share that is one-off / session-specific noise).
- **B1 — frequency-only:** publish if the unit appears in ≥ N conversations. **This is the naive rule the commission warns about** — we run it specifically to *document what it wrongly promotes*.
- **B2 — frequency + independence + outcome gate:** require independent (non-echo, and — where a source identity exists — non-single-source) confirmations, and gate rank on §4 outcome strength.

### Where each piece can be tested (honest scoping)
- **ABCD — no persistent agent identity** (D-list). So *source-based* independence is **not testable** on ABCD. On ABCD we test **frequency + outcome gate** (B2 minus the source term) and the **echo-honesty** design test below.
- **TWCS — brands recur (109 companies, e.g. AmazonHelp ×52).** Brands are a **loose** source proxy. On TWCS we test **source-independence** (does a unit confirmed by *multiple* brands rank above one confirmed by a *single* brand?) and report how weak a proxy brands are.
- This split is deliberate: we do not pretend source-reputation was tested where the data can't test it.

### What we measure + pre-registered criteria (BEFORE looking)
- **Separation bar:** against a small human-labeled **value set** (~50–100 units marked *publish / do-not-publish* by two passes), the valuation rule must separate publish-worthy from noise with **≥ 0.80 AUC** (or an equivalently clean, pre-stated threshold).
- **Trap-documentation bar (the commission wants this explicit):** run B1 (frequency-only) on the same set and **measure the share of units it promotes that a human would not publish.** **If that wrongful-promotion share is ≥ 30%, that is the documented trap** — "frequency alone promotes ≥30% of human-rejected units" — and it is a finding, not a bug.
- **Echo-honesty design test (proof, not data):** construct a synthetic echo — take one unit, inject it into a downstream conversation, and check the counter. **Pre-registered:** the naive counter (B1) **must be shown to** double-count its own echo, and the independence rule (B2) **must be shown not to.** If B2 *also* counts the echo, the design fails and we report the echo trap as **not solvable by this rule** on static data — which would push the honest answer toward "evidence-accumulation needs live traffic, not a dump."

**What would change my mind:**
- If **no threshold cleanly separates value from noise (AUC < 0.70)**, then "minimum evidence to publish" is **not answerable on this data** — and that is the complete deliverable the commission invites. We name it and state what would make it answerable (a real outcome label + recurrence, §5 of the report).
- If **TWCS brand recurrence proves a usable independence signal** (multi-brand-confirmed units are meaningfully better than single-brand), then reputation/evidence-accumulation **has a home after all** (at least a proxy one) — a positive that flips the §5 "blocked" line.

---

## 4. Outcome derivation — the cross-cutting weak point (shared by M2/M3)

This is where "how do we even know it went well" is answered **or killed**. It is a pre-registered derivation with its own error, not a preprocessing assumption.

**ABCD — actions vs playbook (proposed, unproven):**
- For each conversation, take the performed action sequence (from `targets[2]`, D11) and the **expected** ordered action sequence from `guidelines.json` for its mapped subflow (PR #9 mapping, 100% coverage).
- **Success candidate:** performed sequence agrees with the expected playbook sequence (pre-registered measure: ordered set-agreement / edit-distance, threshold stated before scoring). **Deviation = candidate failure signal.**
- **Validation (the part that decides if this is real):** hand-label **50 conversations** with a human "did this go well" judgment, then measure whether **deviation-from-playbook actually correlates** with the human judgment (report the correlation / AUC).
- **Pre-registered kill condition:** if deviation **does not** correlate with human "went well" (AUC ≤ 0.60), the outcome derivation **fails** → *outcome is not answerable on ABCD* → M2's `what_failed` and M3's outcome gate both collapse to "unavailable." That is a first-class negative.

**TWCS — organic but sparse (no derivation, just honest accounting):**
- Final-customer-turn polarity gives 11% clearly positive / 4% clearly negative / **85% no signal** (Phase 0). We **do not** pretend keyword polarity is an outcome label. We report the 15% that carry a signal as a *small, non-random* usable slice and flag that the other 85% is unlabeled. An LLM judge on that slice is the only defensible upgrade, and it is a cost we state, not assume.

**Why this matters to the whole commission:** the commission's §2/M3 echo trap and §8.2 "definition of success is yours" both land here. If §4's derivation survives its 50-conversation validation, we have a *defensible, reproducible* outcome signal and M2/M3 are fully testable. If it dies, we hand back an explicit: *"outcome is not answerable on a static dump; here is exactly what would be"* — the deliverable the commission pre-authorized.

---

## 5. What we expect to be hard vs impossible (stated up front)

| Item | Expectation | Basis |
|------|-------------|-------|
| M1 within a flow (same subflow) | easy | oracle B0 is near-perfect; lexical should hold |
| M1 cross-flow / cross-product | **hard** | different wording, same shape; the false-friend band |
| M1 across corpora (ABCD↔TWCS) | not tested (likely negative) | different domains, no shared gold |
| M2 unit preserving outcome field | **hard / may collapse** | depends entirely on §4 |
| M3 outcome gate (ABCD) | testable if §4 survives | needs the 50-conv validation |
| M3 source-reputation (ABCD) | **impossible** | no persistent agent identity (D-list) |
| M3 source-reputation (TWCS) | **hard / proxy only** | brands are a loose stand-in |
| Echo-honesty on static data | **may be impossible** | needs live traffic to observe real echoes |
| Outcome anywhere | **the open problem** | no corpus hands a reliable column |

**Name the early answer to commission §9.2:** *M3's source-reputation component is effectively blocked on ABCD (no recurrence) and only proxy-testable on TWCS (brands).* M1 and M2 are fully answerable; M3 is answerable **except** the reputation/evidence-accumulation-from-source-history part, which we report as blocked with the specific missing input (a persistent agent/tenant id).

---

## 6. Answers to the commission's three questions back (§9)

1. **Does the ABCD action trace + guidelines support a defensible outcome signal once the mapping exists?**
   The mapping now exists (PR #9, 100% coverage). The derivation (actions vs playbook, §4) is **designed but unproven**; Phase 2 measures its agreement rate and validates correlation on 50 hand-labeled conversations. If that validation fails, outcome is not answerable on ABCD. Answer: *partially — and the 50-conversation test is the gate.*
2. **Given §5, is any of M1–M3 simply not answerable with what we have?**
   Yes — **M3's source-reputation / evidence-accumulation-from-source-history** (no recurrence on ABCD; brands as a loose proxy on TWCS). Everything else is testable. This is named now, per the commission's request.
3. **What would you want that we don't have — buyable, or from our own traffic?**
   - (a) **A persistent agent/tenant identity** → makes M3 source-reputation real. (From our own traffic; not buyable as a public corpus.)
   - (b) **A real outcome label, even on a small set** → calibrates §4. (Partly buyable via annotation; partly our own traffic.)
   - (c) **Our own agent traffic** → the only home for the echo trap and for true evidence-accumulation. (Not buyable.)
   For the **first pass**, the two certified corpora are sufficient for M1 (fully), M2 (fully, outcome-field pending §4), and M3 (all except source-reputation).

---

## 7. Rough cost of Phase 2 (so the human can scope it)

- **Data:** already downloaded on the lab machine (ABCD 37 MB; TWCS parquet, 794,335 rows). **No new acquisition** for the first pass.
- **Compute:** cheap. Everything is lexical/statistical + a bounded number of LLM-judge calls. **No model training.** Estimate < 1 GPU-hour total; LLM-judge call count is the variable (a few hundred).
- **The real cost is human labeling — this is the bottleneck.** Four small gold sets, each two-pass:
  1. M1 pair set (~150–200 pairs)
  2. M2 reconstruction set (~60–100 conversations)
  3. M3 value set (~50–100 units)
  4. §4 outcome-validation set (50 conversations)

  Estimate **2–4 hours of careful human labeling.** If that is the constraint, the cut is: **drop the TWCS cross-corpus test and the brand-proxy M3**, keep ABCD-only, and report cross-corpus M1 + M3-reputation as *not tested* (both are already named as the likely-negative / blocked items). That keeps Phase 2 inside the round budget.
- **Rounds (hard budget = 6 per phase):**
  - R1 — M1 gold set + B1/B2 run + false-friend audit
  - R2 — M2 hand-drafted unit + reconstruction test + loss ledger
  - R3 — §4 outcome derivation + 50-conv validation (this gates M2.outcome and M3.outcome)
  - R4 — M3 valuation (B1 trap + B2 + echo-honesty design test)
  - R5 — synthesis + negative results ("checked and killed")
  - R6 — buffer / report (if R5 needs a fix-forward)

  **Pre-registered scope decision:** if labeling is at risk of blowing past ~4 h by R3, we cut to ABCD-only per the rule above rather than burn the round budget on a partial cross-corpus pass.

---

## 8. What this proposal is **not**

- Not a claim that injected memory helps a later conversation (that is #5, out of scope, and unanswerable on a static dump).
- Not a vendor/embedding-model selection (B2 exists only to falsify the lexical baseline).
- Not production code or a pipeline (factory standard: that is DevCrew's job *after* research succeeds).
- Not a re-derivation of any DECIDED fact (D1–D13); the proposal builds on them.

**Decision requested from the product/founders (Phase 1 gate):** confirm this method + pre-registered criteria, or push back on any bar (the ≤10% false-friend rate, the §4 50-conversation kill condition, the AUC 0.80 valuation bar, the ABCD-only cut). Per the commission, we would rather argue now than after the main pass.
