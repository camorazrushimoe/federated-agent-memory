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

## Round 1 (M1) — CLOSED 2026-08-28 (main @72e344b) · counter at **2/6**

**Status: R1 CLOSED — number three-way confirmed. R2 (M2) PRE-REGISTERED and in flight
(engineer: brief delivered 06:2xZ via door; `phase2/m2-sample` branch visible on origin by
06:45Z — sample tasking underway). BON-41 Done. Round counter 2/6.**

R1 final state (source of truth: GH #6 comments 5448920977 (lead verification + closure +
findings) and **5449115746** (R1 formal closure + R2 pre-registration + taskings)):

- **Closure line (three-way confirmed — lead 05:44Z, engineer re-derivation, lead's third
  path 06:0xZ; ZERO mismatches):** B1 (TF-IDF cosine, customer turns) at t ≥ **0.196495**:
  **FFR 6.3% (4/63 gold-unrelated) at recall_sm 60.0% (51/85)** → **PASS** of the frozen
  D18 bar (≤10% at ≥60%). Pre-registered op point t ≥ 0.175964: 9.5% (6/63), recall_sm
  72.9%, F1 0.7211; max-recall pass point t ≥ 0.171686: 74.1% at 9.5% (2-way tie at
  0.174772, tie-break lowest t — recorded). B0 oracle: 100% at 4.8% (3/63). 18
  bar-passing thresholds. **B2 DROPPED** (pre-registered rule) → finding: *problem shape
  is lexical on this data.* HONESTY CLAUSE rides with every citation: gold is
  AGENT-LABELED; 21/170 = 0.1235 inter-pass disagreement is a self-consistency floor,
  NOT human agreement.
- **Findings F1–F3 stand** (5448920977 §4): F1 false-friend danger is INSIDE the flow
  (same-flow FFR 13.3% > cross-flow at both thresholds; m1-0089 + m1-0119
  manage_dispute_bill adjacency) — inverts method doc §5; §8.1 sharing scope stays open,
  sharper shape: subflow-granularity constraint within a flow. F2 cross-flow same-problem
  UNTESTED, not zero (69/69 gold same-problem same-flow). F3 oracle ≠ ground truth
  (m1-0010/0038/0061 = B0's entire FFR; B1 rejects all three correctly).
- **Engineer artifacts on main @72e344b** (cherry-pick after the #17/#18 merges):
  `research/phase2/m1/` — `m1_report.md` (full 169-row sweep + F1–F3 + closure line +
  honesty clause), `m1_results.json` (machine-readable incl. `join_findings` + full curve;
  `fp` field = n_pooled − tp, FFR on gold-unrelated only — pinned in denominators),
  `join_verify.py` + `recompute_b1.py` (audit scripts), `README.md` §8 re-run contract.
  Pinned shas verified on main: b1_scores `9fe3e4b3c0978e1f`, gold
  `792df7d24fc0609a` (under `research/phase2/m1/gold/`), pairs `42215fc5969e600e`.
- **R5 decision-logic ledger after R1:** KEY stage now has MEASURED parameters
  (threshold 0.175964 op / 0.196495 bar; worked-example scores W1 0.218476 pooled,
  W2 0.151571 rejected, W3 0.171299 rejected). STORE/PROMOTE/SERVE/REJECT stay
  ASSUMED/BLOCKED until M2/M3/§4 land.
- **Process record (D17, 2026-08-28):** the engineer's report landed by direct
  cherry-pick because #17 was already merged when the branch cut — content confirmed
  correct, but the landing bypassed "review posted, then merge." Rule re-affirmed, no
  size exceptions: every `research/**` / `docs/**` landing via PR with posted lead review.
  No round burned.
- **PR #20 MERGED → main @c81a48a** (display-only fix-forwards from the PR reviews —
  `agreement_report.md` 0.124→0.1235; `score_m1.py` writer + `m1_report.md`
  disagreement leads with the exact fraction `21/170` at 4 dp; table header
  `recall_amb`/`recall_snm` → `ambiguous`/`should-not-match` matching the
  `m1_results.json` `recall_by_band` keys). Lead review posted pre-merge
  (PR #20 comment 5449378116, D17) and lead-verified: gold jsonl byte-frozen
  (`792df7d24fc0609a`), `m1_results.json` byte-identical (`02e87faff7b6ffe6`), every R1
  figure unchanged. Pre-existing `selftest_stage_b.py` `KeyError: 'flow_a'` (synthetic
  gold missing F2 fields) confirmed identical on base+head → filed as a separate
  non-blocking follow-up.

**R2 (M2 — extraction) — PRE-REGISTERED 2026-08-28 (frozen before sample draw; full text
on GH #6 5449115746 §3):** unit = {problem_shape, constraint, unlock, what_worked,
receipt} (`what_failed` OUT — pending §4/R3; collapse rule pre-registered); baselines
B0 transcript / B1 action trace / B2 structured record scored identically; sample N=80
(8/flow × 10 flows, seed 42, R1's 318 convos excluded, ≤2/subflow, 20–32
empty-product); blind two-pass reconstruction test Q1–Q3 + reference-anchored rubric
(value = mean of Q1/Q2/Q3 scores); **bar (D18): ≥70% of convos with value(B2) ≥ 0.8×
value(B0) at tokens ≤ 1/10 (aggregate too)**; token counter + cost frozen (640 bounded
judge calls); honesty clause (agent-judged) from the first call. Taskings: engineer →
`sample.py` (PR) then `extract.py` (B0/B1/B2 renders + frozen token counts) +
judge-harness plumbing; evaluation → blind two-pass answering + scoring pass (per-item
committed, agreement number); lead → drafts the 80 B2 units (proposal author drafts;
blind judge falsifies) + bar adjudication + R3 pre-registration after R2.

**R2 extraction — MERGED 2026-08-28 (PR #22 → main @601c310):** `extract.py`
(generator, stdlib-only, byte-identical re-runs) + `candidates.jsonl`
(sha256:16 **`dd1869a2d72c6b2b`**; 80 × {B0 render, B1 trace, B2 skeleton,
frozen token counts, unmapped guard — 0 unmapped}) + `validate_candidates.py`
(independent re-derivation gate, PASS) + judge-harness plumbing (blind two-pass
staging, 240 items/pass, orders differ, anti-leak field set
{item_id, codename, question, render}; scoring pass, combined references+scores
call, 80 calls; total 560 ≤ frozen 640). Lead verification by re-execution
(clean worktree): extract ×2 byte-identical to committed; validator PASS;
selftests green; anti-leak spot-checked; the three flagged interpretations
CONFIRMED (default JSON separators; presentation-scope hint rule; combined
scoring call). **Token-side structural fact (recorded, not negotiated, D18):
the frozen schema floor (23 tokens, empty unit) exceeds the per-convo bound
`tokens(B2) ≤ tokens(B0)/10` for every one of the 80 convos (median B0 187 →
allowance 18.7 < 23); aggregate-ratio floor 23×80/13,396 = 0.137 > 0.1. The
token half of the frozen bar is structurally unreachable by any
content-bearing unit in the frozen schema — the round reports it as a
structural finding; the value half is measured by the blind judge.**

**R2 B2 draft — LANDED (this PR):** `research/phase2/m2/b2_draft.jsonl`
(sha256:16 **`5063a85c4ab79465`**) — the 80 hand-drafted structured
experience units (lead; proposal author drafts the proposal per
5449115746 §4), frozen schema key order, `what_failed` absent (OUT — pending
§4/R3), `what_worked` = the ordered `targets[2]` trace (D11), drafting
conventions + confidence split (high 72 / medium 5 / low 3) + token facts
(frozen counter: min 37 / median 45 / max 57; aggregate ratio 0.2390) in
`B2-DRAFT-NOTES.md`. Slots into `candidates.jsonl` `b2_unit` at join time
(80/80 id match, key order, token recomputation — verified); `n_tokens_b2`
is recomputed on this unit by the join (frozen counter).

**R2 sample — FROZEN 2026-08-28 (PR #21 MERGED → main @4d68187):**
`research/phase2/m2/sample.jsonl` sha256:16 **`f2195e7a6abe2221`** (80 convos:
8/flow × 10; seed 42; R1-318 exclusion overlap 0/80; empty-product 22/80; B1 coverage
80/80; tokens_b0 median 187 / p95 277 / min 65 / max 417) + `sample.py` /
`validate_sample.py` / `sample.jsonl.meta.json` / `NOTES.md`. Lead verification
(independent of the PR body): separate re-implementation of the frozen draw procedure
→ 80/80 rows byte-identical; determinism re-run byte-identical; every row re-joined to
the raw corpus; the "0 unmapped action names" fact confirmed (36,482 action turns all
inside the 30 canonical ontology names). **DECIDED D22 (GH #6 5449438507): the
pre-registered (8/flow, ≤2/subflow) pair is jointly infeasible for `account_access`
(exactly 3 available subflows — a defect in the lead's pre-registration, all other 9
flows have ≥ 4) — the minimal relaxation (cap `ceil(8/n_sub)` only for sub-4-subflow
flows → 3 for `account_access` only) is ACCEPTED AS DOCUMENTED**; it preserves 8/flow
× 10 and fires only where infeasibility holds (G2/G3 machine-checked). PR #21 lead
review 5449427387 (D17 pre-merge). Next: engineer `extract.py`; lead drafting the 80
B2 units now.

**Linear (lead-moved 2026-08-28):** BON-42 → **In Progress** (R2 kickoff). BON-41 Done
(result line 05:48Z, D21). BON-43/44 Todo. **BON-45 ANOMALY — resolved
2026-08-28 (D21-BREACH forensics on GH #6; corrected twice, same round each
time — my earlier "founder-side change" attribution was WRONG and is
retracted; a second correction follows after my 08:45Z post):** the
05:10:51Z Todo→In Progress→Done movement (10 s) was triggered by the lead's
own PR #19 merge at 05:10:46Z. **Mechanism (verified by timing + content,
never by actor — all crew + oversight share the owner's single API key, so
every action reads the owner's name; DECIDED rule: verify by timing and
content, never by actor — and never a stale ref; every read timestamped):**
a Linear–GitHub automation moves a ticket to Done when a PR **merged to
`main` names the ticket ID in its title** (+1–6 s signature; #16 proves the
body alone does NOT fire — ID was body-only → no fire; the rule body itself
is unread — automation introspection HTTP 400). Fires: #9→BON-37 (+3 s,
Phase-0 era, benign), #15→BON-40 (+6 s, benign), #19→BON-45 (+5 s, phantom;
oversight reverted to Todo 07:21:49Z), #23→BON-42 (+5 s, phantom; oversight
reverted 08:07:33Z), #24→BON-42 (+1–2 s, phantom; lead reverted 08:43Z,
read-back verified — the 08:28:07Z Done was this fire, NOT a no-merge
"re-assertion" as first misread from a stale local `origin/main`; corrected
on GH #6 same round). Controls #13 explainable (ticket created 5 min AFTER
its merge), #8/#11/#14 not fully resolved (issue state at merge time not
retrievable with my API access) — flagged, not hand-waved. The founder's
D21 ruling stands verbatim: **contracts, protocols, runbooks, scripts,
skeletons and pre-registrations are INPUTS — a round ticket moves to Done
only when the artifact it names exists WITH NUMBERS IN IT.** **DECIDED
guard (lead, 2026-08-28; verbatim wording on GH #6 08:45Z + correction):**
no PR title, commit subject, or branch name that names a ticket ID may be
merged to `main` while that ticket is not Done by a posted result line —
the ID goes in the PR body only; after any work-titled merge the lead
re-reads ticket state the same round. A further BON-42 fire will be
reported, not flapped — root fix is title hygiene + oversight/founder
disabling the rule (ask posted on GH #6). **BON-45 stays Todo until R2,
R3 and R4 have posted their numbers; no touch on BON-45 before then.**
Counter 2/6.

## Round 2 (M2) — CORRECTION + fix-forward in flight (GH #6 `5450060638`, lead, 2026-08-28 08:07Z) · main @d8a8f33

**Status: R2 fix-forward PR in flight (engineer). The PR #22 + PR #23 merges
STAND (both re-verified by re-execution — pins, determinism, validator,
anti-leak, bind byte-identity). The round does NOT start judging until the
re-bound inputs are merged. BON-42 back to In Progress (D21 — reverted per
the correction; the round's numbers do not exist yet). BON-45 stays Todo.**

**BLOCKER (evaluation):** the committed bind layers
(`judge/binding/pass1_input.jsonl` + `pass2_input.jsonl`, 240 items/pass;
`judge/scoring/scoring_input.jsonl`, 80 items) were bound from
`candidates.jsonl` (`dd1869a2d72c6b2b`) whose `b2_unit` judgment fields are
**null (skeleton)**. Verified: all 80/80 blind B2 items and 80/80 scoring B2
candidates carried `"problem_shape": null`. The S0 brief is explicit — the
judge scores the **DRAFT** unit, not the skeleton. The draft IS on main
(`b2_draft.jsonl` sha `5063a85c4ab79465`) but the staged inputs were not
derived from it. Running S1/S2 on the skeleton would burn the single frozen
blind pass on an empty unit and make S3's B2 scores meaningless.

**Interpretation #3 — LEAD ADJUDICATION (overrides 5449907074 §2.3):** the
frozen cost line (5449115746 §3) is "80 × (1 reference call + 1 scoring call
over all 3 candidates) = 160" — a **two-call** structure: (a) a **reference**
call (transcript ONLY → R1–R3, the anchor formed in a context that has NOT
seen the candidates) and (b) a **scoring** call (transcript + 3 anonymized
candidates + the committed reference → scores). The combined single call (80)
was confirmed in error and is overridden. Cost: 480 blind + 80 reference +
80 scoring = **640 — exactly the frozen ceiling** (the "560 ≤ 640" round-post
figure assumed the combined call). S1/S2 unaffected; S3 uses the 2-call
structure. **Interpretations #1 (default separators) and #2 (presentation-scope
hints) stand confirmed — no change.**

**Fix-forward (engineer, single PR, D17 review, off main @d8a8f33):**
1. **Re-extract:** slot `b2_draft.jsonl` (sha `5063a85c4ab79465`) into
   `candidates.jsonl` `b2_unit`/`b2` — final B2 render + final `n_tokens_b2`
   on the lead's unit (frozen counter, default separators; interpretation #1).
   New `candidates.jsonl` sha256:16 **`a54f52a557ce38b5`** (skeleton B0/B1
   renders unchanged; only the B2 items change). `extract.py` gains a
   `--draft` slotting mode; skeleton mode still byte-reproduces the PR #22
   artifact (`dd1869a2d72c6b2b`) for audit.
2. **Validator extended** for the FILLED unit (`--draft`): judgment fields
   non-null where drafted (`problem_shape`/`constraint` +
   `receipt.event_span`/`scope`/`confidence`; `unlock` null allowed — 53/80),
   frozen schema key order, mechanical prefill, `b2 == json.dumps(b2_unit)`
   round-trip, `n_tokens_b2` frozen counter, and F6 (committed unit == the
   pinned draft's unit — slot, don't mutate). **FILLED verdict: PASS 29/29.**
   (Precision note: the as-merged note recorded "24/24"; the validator
   mechanically runs **26** checks in skeleton mode (A4 + B1 + C5 + D3 +
   E5 + F5 + G3) and **29** in filled mode (adds A5 draft sha, A6 draft
   count, F6 unit-equality; F2 → F2') — the "24" was a write-time miscount,
   corrected here per D21.)
3. **Re-bind BOTH layers** from the new candidates → new committed bind layers
   (new shas). B0/B1 renders unchanged (0/0 changed), **only the B2 items
   change (80/80 per blind pass; 80/80 scoring)**. Blind:
   `pass1_input` sha256 `5ef2d7cc…`, `pass2_input` sha256 `17d701f9…` (orders
   + anti-leak field set intact; codenames deterministic →
   `candidate_mapping.json` unchanged). Scoring: `reference_input` sha256
   `d3d6ef8a…` (transcript ONLY — candidate-free context), `scoring_base`
   sha256 `6a76e5e7…` (transcript + 3 candidates; the scoring input is built
   at stage time from the committed reference).
4. **Scoring structure restored to the frozen 2-call** in
   `PROTOCOL-m2-scoring.md` + `stage_scoring_pass.py`: Call 1 = reference
   (transcript ONLY → R1–R3), Call 2 = scoring (transcript + 3 candidates +
   committed reference → scores); two separate fresh contexts. Budget line in
   the protocol + manifest: 480 + 80 + 80 = **640 (the frozen ceiling)**.
5. **`B2-DRAFT-NOTES.md` numbers corrected** (recomputed from the pinned
   artifacts; see table below).
6. **This `PHASE2_STATE.md` mirror** (this section).

**Number corrections — `B2-DRAFT-NOTES.md` (recomputed from candidates
`dd1869a2d72c6b2b` + draft `5063a85c4ab79465`):**

| figure | as merged | corrected |
|---|---|---|
| B0 total (80 convos) | 13,396 | **15,340** |
| B2 draft total | 3,202 | **3,667** |
| aggregate ratio draft/B0 | 0.2390 | **0.2390** (correct — 3667/15340) |
| aggregate floor (skeleton) | 23×80/13,396 = 0.137 | **2,046/15,340 = 0.1334** (skeleton is 23–30/convo, not flat 23) |
| schema floor vs per-convo bar | "exceeds `tokens(B0)/10` for all 80" | skeleton (23–30) is **under** the bar for **7/80** convos (B0 ≥ 230: 116, 274, 374, 1224, 3161, 4332, 10059); the "0/80-at-the-floor" claim does not stand |
| draft vs per-convo bar | 0/80 | **0/80** (correct — draft 37–57 vs allowance 6.5–41.7), **stated as the draft's** |

**Structural conclusion (unchanged, on correct numbers):** the DRAFT unit is
0/80 on the per-convo token bar and 0.239 on the aggregate (bar ≤ 0.1) — the
token half is structurally unreachable for this unit (property of frozen
schema + counter + sample, independent of drafting). Token half = structural
FAIL; value half = measured by the blind judge; **B1 (trace) carries the
token side — aggregate 0.0186 (≤ 0.1), 80/80 per-convo — the pre-registered
collapse candidate.** The per-convo "0/80-at-the-floor" claim must not stand
in the artifact (7 convos sit above it) — corrected per D21.

**Sequencing (strict, per the correction):** engineer fix-forward PR → lead
D17 review → merge → evaluation S1 (blind pass 1, fresh context, 240 items
from the RE-BOUND inputs) → S2 (fresh staged context) → S3 (reference calls,
then scoring calls — 2-call structure) → join + bar adjudication. **No judge
call before the re-bind.** Evaluation is HOLDING S1/S2/S3 until the re-bound
inputs land.

**Ticket (correction §4):** BON-42 → **In Progress** (reverted from the
premature Done; D21 — no judge numbers, no bar adjudication, no
`m2_results.json`/`m2_report.md` yet; the join is the ticket's named
artifact). BON-39 In Progress. **BON-45 stays Todo.** Counter 2/6.

