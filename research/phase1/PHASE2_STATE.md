# Phase 2 — state (lead-maintained)

**Thread:** GH #6 · **Ticket:** BON-39 (parent; sub-tickets M1 / M2 / outcome-validation /
M3 / synthesis) · **Method:** `docs/research-method-m1-m3.md` (PR #12)

> This file is the in-repo mirror of the DECIDED state for Phase 2. The GH #6 thread is the
> source of truth; this file must not drift from it.

## Phase status

- **Phase 0 — CLOSED.** 4 independent measurements (lead + BON-36 re-run + D14 pin +
  oversight's own re-run 2026-08-27). No further Phase 0 re-verification — that is a failed
  round now.
- **Phase 1 — CONFIRMED.** Method + pre-registered criteria confirmed by the founder
  **exactly as pre-registered** (2026-08-27). Do not re-open the bars to negotiate downward
  after seeing results. A missed bar is the finding.
- **Phase 2 — OPEN, round counter at 1/6.** Mapping (founder-authorized):
  **1 = M1 · 2 = M2 · 3 = outcome-validation (§4) · 4 = M3 · 5 = synthesis · 6 = buffer.**
  Every round lands a commit or PR with numbers. A discussion-only round is a failed round
  and still burns budget.

## Merge authority (2026-08-27)

- The crew **merges its own PRs after the lead's review is posted** for paths under
  `research/**` and `docs/**`. Human merge stays required **only** for `openspec/**` and
  product code.
- main is not branch-protected; the earlier no-self-merge rule was self-imposed and is
  LIFTED for the above paths (founder decision).
- **Operational discipline (unchanged):** review first, then merge; a 202 from the door is
  DELIVERED — never retry on 202 (the duplicate-ping loop must not repeat); serialize
  hosted requests (10 concurrent per workspace, shared across keys — 429s otherwise).

## Labeling protocol (2026-08-27)

- The **founder is NOT the labeler.** `lab-1-evaluation` labels the gold sets as the
  independent measurer: **two independent passes**, inter-pass **disagreement reported as a
  number**, **per-item labels committed**, every set marked **`agent-labeled`** (never
  "human gold").
- **Escalate a 20-item sample to the founder only if disagreement > 15%.**
- **Fallback:** if evaluation cannot deliver, the lead takes the **pre-registered ABCD-only
  cut** and reports the untested parts as untested. Do not stall.

## Confirmed bars (D18 — frozen)

| Experiment | Bar |
|---|---|
| M1 | false-friend ≤ 10% at ≥ 60% recall (should-match band) |
| §4 outcome-kill | AUC ≤ 0.60 on the 50-conv validation kills the outcome derivation |
| M2 | ≥ 80% rubric value at ≤ 1/10 transcript tokens (collapse rule pre-registered) |
| M3 | valuation AUC ≥ 0.80 + ≥ 30% wrongful-promotion trap documentation |
| Scope | ABCD-only cut pre-registered if labeling at risk of > 4 h by round 3 |

## Round 1 (M1) — opening numbers (verified on merged main @77ccc71, 2026-08-27)

- M1 candidate pair set: **170 pairs** (A=80 same-subflow / B=50 same-flow-diff-subflow /
  C=40 cross-flow), seed 42, **sha256 `423a5ef4ce12…`** (stable fingerprint, text excluded).
  Extractor: `research/phase1/m1_pairset_extract.py` (re-runnable; deterministic).
- §4 derivation dry-run (for round 3; recorded so it is not rediscovered): 10,042 convos,
  agreement median **0.600** / mean **0.536**, exact 947, dev>0.5 = 3,946 — the signal has
  the spread the 50-conv AUC test needs.
- Brief: `docs/research-phase2-round1-m1.md` (H-m1, bars, labeling protocol, handoff point).
