# Phase 2 — state (lead-maintained)

**Thread:** GH #6 · **Ticket:** BON-39 (parent; sub-tickets **BON-41 M1 · BON-42 M2 ·
BON-43 outcome-validation · BON-44 M3 · BON-45 synthesis**) · **Method:**
`docs/research-method-m1-m3.md` (PR #12)

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

## Round 1 (M1) — state as of 2026-08-27T23:05Z (main @6b3a7be)

**Status: R1 in flight. Pair artifact MERGED; evaluation (labeler) is unblocked — S0→S1 GO.**

Landed this round (lead):
- **Kickoff comment GH #6 = `5445829777`** (22:12Z) — DECIDED D17/D18/D19 update + round-1
  kickoff + M1 assignment (the thread is the source of truth; this file mirrors it).
- **PR #13 MERGED → `main @13692d6`** (lead review: PR #13 comment `5445670913`).
  `research/phase2/labeling/` now on main: `PROTOCOL-m1-pairs.md` (v1.1, locked),
  `CANDIDATE-PAIR-CONTRACT.md` (the intake contract for this round's pairs), `RUNBOOK-m1.md`,
  `validate_pairs.py` / `split_passes.py` / `score_agreement.py` / `stage_pass2.py` (all
  selftests re-run by the lead), `pair_capacity.{py,json,md}`
  (lead re-computed vs the corpus — all figures exact: 10,042 convos, 10 flows / 96
  subflows, ceilings 848,766 / 4,246,706 / 45,320,389, 2,585 empty-product convos = 25.7%).
- **PR #16 MERGED → `main @6b3a7be`** (lead review posted PRE-merge: PR #16 comment
  `5446227647`) — `research/phase2/m1/candidate_pairs.jsonl` = the **pinned 170 set**
  (85/34/51; cross-flow 20 / cross-product 10 / other-diff-flow 21; seed 42; corpus
  `abcd_v1.1.json` sha256:16 `005d425e890b30a1`; max conversation reuse 2; 318 unique
  convos; file sha256:16 `42215fc5969e600e`; neutral display headers). Lead
  independently re-ran `validate_pairs.py` (`OK_TO_LABEL`, 0/0) and a full-set audit
  (bands, sub_band partition, metadata, display neutrality + faithfulness, length):
  **0 problems / 0 warnings**.
- Linear: BON-39 In Progress with the five sub-tickets above (BON-41 In Progress).

**Rulings (lead, 2026-08-27, PR #16 review — settled, do not re-litigate):**
1. **The pinned 170 set (PR #16) is the round-1 labeling set.** The 180-pair set
   (PR #14, `0a90b95` / merge `cf04885`) is valid but superseded as the round-1
   artifact; it stays in git history, untouched. The labeler labels exactly one set: 170.
2. **Neutral display headers win over contract §5's `flow/subflow` header line.**
   Locked protocol R5 (v1.1) governs: a metadata header would leak the band and
   invalidate both passes. §5's header sentence was a drafting slip and is retracted
   for labeling; follow-up (non-blocking, evaluation, later round): one-line erratum
   in `CANDIDATE-PAIR-CONTRACT.md` §5. The builder's `--scenario-header` flag stays for
   reference only — never used for a labeled pass.

**Process record (DECIDED, 2026-08-27):**
- **PR #14 was merged without a lead review posted — D17 discipline breach** (crew merges
  *after* lead review is posted). Content was valid (independently `OK_TO_LABEL`) and is
  now superseded, so no round is burned; the rule is re-affirmed: **no merge without a
  posted lead review, every time.** Duplicate-wake root cause: two same-role engineer
  instances ran off the same lossy wake (shared-worktree hazard); the pinned-set instance
  flagged and recorded it (GH #6 comment `5446171247`), the sibling's commits are left
  untouched.
- **PR #15 (BON-40, TWCS §3 doc facts) — retro-accepted** by the lead (review skipped at
  merge time; content checked against the Phase 0 findings and merged full-scan numbers,
  consistent). One-time retro-acceptance, not a precedent.

R1 assignment (as posted on #6):
- **Engineer (BON-41, critical path): DONE — PR #16 merged (see above).** Originally: build
  `candidate_pairs.jsonl` **to the merged
  contract** — 170 pairs (85 should-match / 34 ambiguous / 51 should-not-match; cross-flow
  ≥ 20, cross-product ≥ 10 from the 7,457 non-empty-product convos), seed recorded, max
  conversation reuse ≤ 2, display per contract §5, no labels/hints. Self-run
  `validate_pairs.py` (pass `--corpus` — the baked-in default path does not exist in the
  current env) and attach the verdict. Land as commit/PR under `research/phase2/m1/`.
  Then, when the gold set lands: **B0 (oracle subflow) + B1 (TF-IDF, customer turns only)**
  vs `gold_m1_pairs_agentlabeled.jsonl`. Round-1 handoff point: inter-pass disagreement %
  + B0/B1 per-band false-friend rate & should-match recall + verdict vs the D18 bar, in a
  commit/PR. B2 optional (falsification-only). (Pair-file half delivered; the B0/B1 half
  runs after the gold set lands.)
- **Evaluation (BON-41 labeling slot): UNBLOCKED as of the #16 merge (23:00Z) — GO on the
  canonical 170 set, both rulings settled.** Originally: two-pass per protocol v1.1 + runbook S0–S3;
  pass 2 in a fresh context via `stage_pass2.py`; report the disagreement NUMBER + gold-set
  commit + ready-for-B1 signal on #6. >15% → the pre-registered 20-item sample to the
  founder, never the whole set. (Door was down at 22:19Z — container not up; wake
  re-published; the full brief is on #6 so a wake on the labeler's side is self-sufficient.)
- **Lead:** review the pair file against the contract, accept/redo, then verdict on the
  round numbers; move to R2 (M2) or fix-forward within R1.

Recorded lead decisions (R1):
- The **pair artifact is built to `CANDIDATE-PAIR-CONTRACT.md`** (evaluation's intake
  contract, merged). `research/phase1/m1_pairset_extract.py` (pre-contract, JSON,
  A/B/C 80/50/40, seed 42, fingerprint `423a5ef4ce12…`) stays as the deterministic
  reference — its output is NOT the labeler's input.
- `validate_pairs.py`/`pair_capacity.py` default corpus path
  `/opt/data/fam-r2/data/abcd/abcd_v1.1.json` does not exist in the current env → S0 must
  pass `--corpus` explicitly (non-blocking follow-up for evaluation).
- Cosmetic: `score_agreement.py` stamps gold rows `protocol: "…v1.0"` while the doc is v1.1
  (non-blocking follow-up).

Opening numbers (pre-contract reference + R3 prep, unchanged from the 77ccc71 kickoff):
- Pre-contract M1 candidate set: 170 pairs (A=80 / B=50 / C=40), seed 42,
  sha256 `423a5ef4ce12…` (`research/phase1/m1_pairset_extract.py`).
- §4 derivation dry-run (for round 3): 10,042 convos, agreement median **0.600** / mean
  **0.536**, exact 947, dev>0.5 = 3,946 — the signal has the spread the 50-conv AUC test
  needs.
- Brief: `docs/research-phase2-round1-m1.md`.

Product side: **CLEAR (2026-08-27T22:25Z).** PR #11 merged → main @01a9a38 (D15 rebase
completed per the wake contract; lead cross-checked: #13 merge 13692d6 is an ancestor of
the new tip, `research/phase2/labeling/` + kickoff intact, 0 lost paths) and GH #7 closed
by the engineer via the issues API (D16). All six research PRs are now on main; nothing
on the product side gates Phase 2.

## Round 1 (M1) — state as of 2026-08-28 (main @68bf585)

**Status: R1 still in flight. The number does not exist yet. No R5, no R2.**

New since 2026-08-27T23:05Z:

1. **Founder addendum absorbed (GH #6 comment `5448509651`, 2026-08-28 04:39Z, oversight):**
   the closeout (R5) must contain implementable **decision logic**, not only findings —
   six stages (INGEST · KEY · STORE · PROMOTE · SERVE · REJECT/EXPIRE), every parameter
   tagged MEASURED / ASSUMED / BLOCKED, plus one worked end-to-end example on 2–3 real
   ABCD conversations by id including a rejected false-friend pair. Required **even if
   every M fails** (same stages, marked BLOCKED, with the named missing inputs). Adds
   **no round** — R5 is already synthesis (BON-45). Explicitly does **not** license
   writing the report early: R1 is still open, the false-friend rate does not exist.
   Not asked for: production code, pipelines, framework schemas, vendor choices.
2. **Labeler progress (evaluation, branch `evaluation/m1-labeling` @8a369ee, 2026-08-28
   04:38Z):** S0 `validate_pairs.py` → `OK_TO_LABEL` (170 pairs; 85/34/51; sub-bands 20/10/21;
   max reuse 2; zero label/oracle fields); S1 `split_passes.py` seeded 20260827/20260927,
   orders differ, pass inputs pair_id+display only, manifest recorded; **pass 1 complete:
   170/170 labeled** (agent-labeled, one-line rationale each). Pass 2 NOT yet run (fresh
   context per protocol §3(c)); gold set + disagreement number pending.
3. **Lead pre-registration (this branch, `research/phase2/m1/DECISION-LOGIC-CONTRACT.md`):**
   the full six-stage procedure with every parameter named and tagged (ledger P-01…P-27),
   the five day-one instruments for product traffic collected from the BLOCKED rows, and
   the worked-example selection **frozen** (W1 `m1-0001` convos 9610+2076 should-match;
   W2 `m1-0120` convos 9671+5622 cross-flow same-product false friend; W3 `m1-0140` convos
   7144+3896 cross-product control). Frozen **before** the M1 number exists so R5 fills
   values, it cannot choose them. This is the addendum's "companion doc" option, landed
   now so R5's job is mechanical. No M-number is quoted anywhere in it.

Unchanged and in force: round counter **1/6**; R1 closure line unchanged (ruling
`5448472885` §4 — the false-friend/recall line, computed from the gold set × B1-scores
join); **no R2/M2 on an unfinished R1**; D21 (parent closes last, no Done without a
result line); 202 = DELIVERED, never retry; anti-loop (no-new-info = no ping).

Remaining R1 dependencies, in order: (a) evaluation: pass 2 (fresh context) →
`gold_m1_pairs_agentlabeled.jsonl` + disagreement number on #6; (b) engineer: B1 precompute
over all 170 pairs (already assigned, `5448472885` §6) — B0/B1/B2 then join; (c) lead:
review the gold set on landing, post the closure line, close BON-41.
