# Phase 2 — Round 1/6: M1 Comparison ("same problem")

**Commission:** Shareable Experience for Federated Agent Memory
**Ticket:** BON-39 (parent) · sub-ticket **M1** · thread: GH #6
**Round:** **1/6** — Phase 2 round mapping (founder-authorized 2026-08-27):
**1 = M1, 2 = M2, 3 = outcome-validation (§4), 4 = M3, 5 = synthesis, 6 = buffer.**
**Method + pre-registered bars:** `docs/research-method-m1-m3.md` (PR #12, merged to main @77ccc71).
**Status:** KICKOFF (lead-assigned). No M1 result numbers yet — they land in this round when evaluation's labels + the B0/B1 baseline run are in.

> **Gate cleared.** Phase 0 CLOSED (4 independent measurements, incl. oversight's own re-run).
> Phase 1 criteria CONFIRMED by the founder **exactly as pre-registered** (DECIDED D18).
> All four PRs merged to main (77ccc716c2). Phase 2 round counter opens at **1/6** now.
> **Phase 0 is closed — no further Phase 0 re-verification this round.**

---

## 0. Hypothesis this round serves

**H-m1** (hypotheses.md): an operational "same problem" definition can be built and its
failure modes (false friends) characterized on ABCD (+TWCS if in scope).

The commission's question: *when are two conversations about the same problem — and where
does that definition break?* A useful answer = an operational definition a measurer agrees
with, **plus** where it fails (pairs that look similar but must **not** be pooled, because
pooling a wrong problem poisons shared memory).

## 1. Goal of this round

1. Label the pre-built M1 candidate pair set (two independent passes — see §3).
2. Run the dumb baselines **B0 (oracle subflow)** and **B1 (TF-IDF lexical, customer turns only)** against the labels.
3. Report the **false-friend rate** and **should-match recall** for each, per band, and state the verdict against the pre-registered bar.

## 2. Pre-registered bar (DECIDED D18 — DO NOT negotiate downward)

> A method is a usable "same problem" definition **only if** it keeps the
> **false-friend rate (pooling a pair labeled `unrelated`) at ≤ 10%**, at **≥ 60% recall
> on the should-match band (A)**.

- **A missed bar IS the finding.** If no method holds ≤10% false-friend @ ≥60% recall, the
  finding is that "same problem" is only identifiable *within a flow* (sharing scope is
  constrained to vertical/flow, not global). That is a first-class result, not a failure.
- **If B1 (lexical) already meets the bar**, the problem shape on this data is lexical, not
  semantic — embeddings (B2) are dropped and we say so. B2 is *optional, falsification-only*.
- **Primary metric = precision on the dangerous class** (false friends), not overall F1.
- **Secondary (reported, not gating):** overall pairwise F1 vs gold; per-band recall; the
  inter-pass agreement rate.

## 3. Gold-set labeling protocol (DECIDED D19) — the founder is NOT the labeler

- **Labeler of record: `lab-1-evaluation`** (independent measurer), NOT the founder and NOT
  the lead. The lead designs the method and reviews; it does not label.
- **Two independent passes.** evaluation labels the full pair set, then labels it again
  independently. The **inter-pass disagreement is reported as a number** (this is the
  reliability figure the method doc calls "labeler agreement" — it is now inter-pass,
  not lead-vs-evaluation).
- **Per-item labels are committed** (not summarized away).
- **Every set is marked `agent-labeled` — never `human gold`.** Do not use the phrase
  "human gold" anywhere in Phase 2 artifacts.
- **Escalate only if disagreement > 15%:** then surface a **20-item sample** of the
  disagreeing pairs to the founder. Below 15%, no escalation — proceed.
- **Fallback (do not stall):** if evaluation cannot deliver the labels, the lead takes the
  **pre-registered ABCD-only cut** and reports the untested parts (cross-corpus M1, brand
  proxy) as **untested**. A silent or blocked commission is the only real failure.

**Label scale (3-level, per method doc §M1):** `same-problem` / `related-but-different` / `unrelated`.
- Band **A** = should-match (same subflow, different conversation) → expect mostly `same-problem`.
- Band **B** = ambiguous (different subflow, same flow) → expect the mixed zone.
- Band **C** = should-not-match / false-friend band (different flow) → expect mostly `unrelated`;
  **this is where false friends live** — the metric of interest.

## 4. Candidate set (built + verified on merged main — this round's opening numbers)

- **170 candidate pairs**, deterministic (seed 42): **A=80, B=50, C=40** (inside the
  pre-registered 150–200 range).
- **`m1_pairset_candidates.json` sha256 = `423a5ef4ce12…`** (fingerprint over
  band + unordered convo-id pair, text excluded — stable across runs).
- Bands are structural (same-subflow / same-flow-diff-subflow / cross-flow), so the
  should-match and false-friend populations are fixed *before* any label is looked at.
- Customer turns only (agent boilerplate excluded — method B1 rule).
- **ABCD only for this round** (pre-registered cut). TWCS cross-corpus M1 is out of scope
  (different domain, no shared gold — method doc §M1 "not testable here").

The extractor is committed (`research/phase1/m1_pairset_extract.py`) and re-runnable —
the labeling process regenerates the identical candidate set from it.

## 5. Baselines to run (dumb versions, in order of ambition)

- **B0 — oracle subflow (ABCD only):** "same" := same `subflow` label. The ground-truth
  ceiling within a subflow (trivially ~1.0 on band A). Reference for "how much of 'same'
  is already encoded."
- **B1 — lexical, no model:** TF-IDF cosine over **customer turns only**. The dumb baseline
  every semantic method must beat.
- **B2 — small embedding (optional, falsification-only):** a single off-the-shelf sentence
  embedding. Included **only** to falsify "the dumb one is enough." If B1 passes the bar,
  B2 is dropped and reported as "problem shape is lexical on this data."

## 6. Constraints (factory standard + workflow)

- **Cheap first, no model training.** B0/B1 are lexical/statistical — no GPU, no new data.
  Everything is re-derivable by extending `research/probe_dataset.py` (numbers discipline).
- **No production infrastructure.** This is a research script + a committed JSON, not a service.
- **Verify against the file, never a card/README.** Numbers must be regenerable.
- **State units** (per-pair, per-band; not per-conversation unless stated).

## 7. Out of scope (this round)

- Cross-corpus M1 (ABCD↔TWCS) — not testable here, report as such.
- Any re-derivation of a DECIDED Phase 0 fact (D1–D16).
- Building a production "same problem" service (that is DevCrew's job *after* research).
- Re-opening Phase 0 or the confirmed bars.

## 8. Handoff point (when the round is "landed")

The round is landed when the lead can post, with exact values:
1. inter-pass **disagreement %** (evaluation, two passes) + a `agent-labeled` tag;
2. **B0 and B1** false-friend rate + should-match recall, per band;
3. the **verdict** against the D18 bar (pass / fail / B1-sufficient-drops-B2);
4. the committed labeled pair set (per-item) + the baseline run artifact (a commit or PR).

**A discussion-only round is a failed round and still burns budget** (founder, 2026-08-27).
This round does not close until those numbers exist in a commit/PR.

## 9. Decisions needed

- **From evaluation:** confirm you can take the two-pass labeling of the 170-pair set under
  the D19 protocol; report the disagreement number + per-item labels.
- **From engineer (or lead):** run B0 + B1 against the labels; commit the false-friend +
  recall numbers.
- **From lead (me):** review + accept/redo; state the verdict; move to round 2 (M2) or
  fix-forward within round 1 (same item bounced twice → drop/escalate, per workflow §2).
