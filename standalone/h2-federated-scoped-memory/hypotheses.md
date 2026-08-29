# Hypotheses — H2 federated scoped memory (whole past session as a hint)

**CLOSED 2026-08-29 (founder decision): H2 v1 FINAL — NOT FIT.** Whole-session
hints via tag-overlap retrieval do not beat a random similar past session,
because the tag schema has no discriminating axis. This is a result, not a bug.
All v1 work stopped: no R5, no full-corpus run, no further fixes (recorded on
main @ 7e4fe9f, PRs #53–#64 merged). v2 = new tag schema design (consulting);
this log + `h2_research_report.md` are preserved on branch `h2/v2-context`.

Source of truth for hypothesis status. Live board: issue #51.
Round plan: `standalone/h2-federated-scoped-memory/ROUND-0-PLAN.md` (docs/h2-round0-plan, PR #52).

| ID | Statement | Status | Confidence | Linked experiments | Notes |
|----|-----------|--------|------------|--------------------|-------|
| H2-D0 | An agent labeler (deepseek-v4-pro) reading transcripts produces usefulness gold that is a valid H2 measurement target — i.e. transferable-move labels, NOT collinear with H1's unlock_guideline (C-GD7 ≤ 20% H1-signature rows) | supported | low→medium | Phase B D0 run (slice = 60 hold-out queries) | Founder 2026-08-28: gold is agent-labeled, NOT human gold; labeler never sees unlock (adapter drops it). Phase B DONE: canonical gold = eval PR #59 (merged 5f12c7d; header-compliant; supersedes interim 30e6b83); QA C-GD1..5/7/8 HARD PASS, C-GD6 SOFT FAIL 3/6 (d-3219, d-5711, d-4815 — labeler more generous on promo/refund action sequences); C-GD7 3/48 non-empty = 6.25% ≤ 20%. **LEAD VERDICT 2026-08-29: ACCEPT as canonical — no re-execution, no revision** (lead re-exec on 5f12c7d: 82 checks, 68 pass / 13 deferred / 1 SOFT fail, exit 0; replica 60/60 identical → deterministic; re-run adds zero info; C-GD6 is SOFT by design, direction documented; caveat rides every L2 line). Final validation of the gold as measurement target = Phase C usefulness signal. |
| H2-TAG | S2 tag on deepseek-v4-flash matches gold tags on the slice: ending_exact ≥ 0.80, constraint_exact ≥ 0.60, problem_shape_exact ≥ 0.35 (or jaccard ≥ 0.60) | in-progress | low | Phase C S2 slice run | **Tag-vs-gold_tags metrics NOT publishable yet: gold_tags decision still open (ROUND-0-PLAN §8)** — founder must authorize human gold_tags before §4.1 numbers are reported. Usefulness L2 not blocked. S2 tag run itself (flash, pinned) is part of the measured loop regardless. |
| H2-USEFUL | T.hit > B1.hit on the audit slice (ranker beats a random similar past session) | rejected (on slice) | low | Phase C T vs B1 | **Phase C RESULT: T=2 vs B1=5 on n=60 → T ≤ B1 → NOT FIT** (EVAL-PLAN §4.3: "ранкер не добавляет ничего сверх случайной похожей сессии. Это результат"). Mechanism verified on run data: S7 ratings keyed (session, query tag_key), 60/60 query tag_keys UNIQUE (median bucket 1) → ratings never transfer → ranker degenerates to tie-break (same 3 smallest ids served all 60 queries, unique_served=3); S3 non-filter (channel+vertical constant → 320/320 candidates). A3 predicted this. B3 oracle 46/60=0.77 (pool had the material; loss is in S4/S7 axis, not data). **ROUND 3 (coarse tag_key problem_shape\|ending, replay, zero LLM): CLOSED — v2 also fails.** metrics.json byte-identical to R1 (sha 6ac43ff0…), T packet ids 0/60 changed: 58/60 unique buckets → S7 still has no second query to transfer to; T 4/56/0 vs B1 2/58/0 is a 2-query margin inside the R1 cross-check noise (merged D4 run T 2/B1 5 ↔ cross-check T 4/B1 2) → no stable gap → ranker-vs-random gate not met → **NOT FIT** (per §6.4, lead verdict 2026-08-29; report.md + eval.py rule corrected). **ROUND 4 (founder-approved S3 matching fix, replay, zero LLM): EXHAUSTED — steps 1+2 fail the gates, step 3 not applicable** (step 1: median 274 not tens, unique_served DOWN/top3_share UP, T 0.05 < B1 0.0667; step 2: recall collapse 0.033). T ≈ B1 inside noise in every configuration → **NOT FIT, full stop**; 1000+200 run = founder decision (would exercise repeated buckets, but no further slice spend and no further mechanical fixes). |
| H2-HARM | T.wrong ≤ 0.25 on the slice (a whole past session pushed as a hint rarely hurts) | rejected (on slice) | low | Phase C | **Phase C RESULT: T.wrong=58/60=0.97 → FAIL** — with the ranker stuck on 3 ids, T pushes a wrong whole session on 97% of queries. In the degenerate state T.wrong reflects the ranker failure, not the idea's intrinsic harm; re-test after the tag_key fix. **ROUND 3: T.wrong 56/60 = 0.93 → FAIL again** (coarse tag_key changed 0/60 packets; metrics byte-identical). Whole-session harm is the verdict-driving gate (§6.2 ≤ 0.25) behind the R3 NOT FIT. |
| H2-ROTATION | top3_share ≤ 0.55 after burn-in and explore_fill ≥ 0.15 where candidates > MAX_PACKET | in-progress | low | Phase C long replay | Stale top-1/3 = rotation broken even with a pretty hit. CAVEAT: n=60 slice is short for rotation stats — report honestly, burn-in per EVAL-PLAN §7; full-length rotation only meaningful on 1000+200 run. |
| H2-COST | Whole-session packet cost is honestly priced: packet_tokens_p50 recorded; > 1500 ⇒ FIT WITH LIMITS flag | in-progress | low | Phase C cost.json | Cost is a limit, not a failure of the idea. |

Status values: proposed | in-progress | supported | rejected | inconclusive | parked

## Round log
- ROUND 4 RESULT (2026-08-29): **S3 matching fix (founder-approved R4) EXHAUSTED — NOT FIT, full stop; 1000+200 decision goes to the founder.**
  Runs (both replay of the frozen Phase C raw/tag, zero new LLM, `tag_calls=0`,
  C-REPLAY byte-identical): `runs/2026-08-29_PhaseC3_s3match-3fields` (step 1:
  overlap counts `problem_shape|constraint|ending`, TAG_FIELDS_MIN=2) and
  `runs/2026-08-29_PhaseC3_s3match-shape-req` (step 2: + require exact
  `problem_shape` match). Step 1: candidates 320–380 → median **274** (12/60 →
  0), but gates fail in the wrong direction — unique_served **5** (down from 7),
  top3_share **0.986** (up from 0.9667), T 0.05 ≤ B1 0.0667. Step 2: exact shape
  match collapses retrieval — median **0** candidates, 54/60 zero, recall
  **0.0331** (gate: must NOT collapse), empty 0.6667, T == B1 == 0.0833.
  Step 3 (min overlap 3) NOT applicable — dispatch condition "(1)+(2) still
  dump hundreds" is false. **Diagnostic (frozen pool, 320 sessions):**
  `constraint='none'` in 260/320 (81%), `ending='resolved'` in 297/320 (93%) →
  2-of-3 overlap still admits ~everything; `problem_shape` is free-text
  near-unique (278 unique pool shapes, only **7 shared** with the 60 query
  shapes) → exact match admits almost nothing. S3 granularity is not the
  binding lever on this slice: the queries simply share no tag structure with
  the pool (A3-predicted). **Verdict: candidates shrink, T ≈ B1 inside noise
  ⇒ NOT FIT, full stop** (founder boundary: R4 is the LAST mechanical fix; no
  prompt edits / threshold moves / new model / slicing). Full 1000+200 corpus
  = founder decision (only a corpus with repeated shape buckets can exercise
  rating transfer). Branch `h2/r4-s3match` (4 commits: 19c8518, 91783dd,
  ae3b7e5, 78ac1b3) pushed; PR opened.
- ROUND 3 RESULT (2026-08-29): **H2-USEFUL-v2 CLOSED — NOT FIT, no stable gap vs B1.**
  Run `runs/2026-08-29_PhaseC2_tagkey_shape-ending` (replay of R1, zero LLM;
  manifest `replay_of` + `TAG_KEY_FIELDS=[problem_shape, ending]`, coarse S4/S7 rating key;
  S3 matching unchanged 5 TAG_FIELDS / TAG_FIELDS_MIN=2). Lead re-execution (2026-08-29,
  PR #63 review): re-derived every arm class from the committed per_query.jsonl via the ONE
  classify_packet semantics — 0 mismatches on 5 arms × 60 queries; arm totals **T 4/56/0 ·
  B1 2/58/0 · B2 4/56/0 · B3 46/0/14 · B0 0/0/60** (T=4, B1=2, B3=46 confirmed); metrics.json
  byte-identical to R1 (sha 6ac43ff0…); **T packet ids changed 0/60** (all five arms 0/60).
  The coarse key IS applied in the run state (58/60 unique problem_shape|ending buckets) but
  the fix has ZERO effect: no repeated buckets → S7 ratings still never transfer → ranker
  degenerates to the same tie-break. **Verdict CORRECTED by lead before merge: NOT FIT — no
  stable gap vs B1; whole-session harm wrong=0.93 (gate ≤ 0.25).** Grounds (§6.4/§6.2):
  (1) T.hit 0.0667 > B1.hit 0.0333 is a 2-query margin inside the R1 cross-check noise (merged
  D4 run T 2/B1 5 ↔ cross-check T 4/B1 2 → margin flips), ranker-vs-random gate not met;
  (2) T.wrong 0.9333 > 0.25 whole-session harm (a wrong foreign whole session is expensive
  harm). eval.py verdict rule fixed (T.wrong > 0.25 ⇒ NOT FIT; §6.2 thresholds untouched) so
  the committed artifacts re-produce NOT FIT; report.md verdict lines corrected in both R1
  (branch) and R3 run dirs. PR #63: READY for merge. H2-USEFUL + H2-HARM rejected on slice;
  full 1000+200 run remains GATED (only a run with repeated shape/ending buckets could
  exercise the coarse-key transfer; no further slice spend).
- ROUND 2 PHASE C RESULT (2026-08-29): **First measurement DONE — verdict NOT FIT on the slice.**
  Run `runs/2026-08-29_PhaseC_slice_deepseek-v4-flash` (60 queries, pool = 320 same-unlock
  union, S2 tag deepseek-v4-flash temp 0, 380 calls, 221,591 in / 96,492 out tokens).
  Arms (one scoring function bin/eval.py, EVAL-PLAN §10): **T 2/58/0 · B0 0/0/60 · B1 5/55/0 ·
  B2 2/58/0 · B3 46/0/14**. B0 sanity PASS, B3 oracle 46/60 = 0.77 = A1 (pool had the
  material), retrieve recall 1.0 / empty 0.0. **H2-USEFUL FAIL (T=2 ≤ B1=5)** → per §4.3
  "ранкер не добавляет ничего сверх случайной похожей сессии. Это результат" → §6.4 NOT FIT.
  H2-HARM FAIL (T.wrong 58/60 = 0.97). Cost: packet_tokens_p50 1101 (≤1500, no cost flag;
  ~28× a 40-word H1 card). **Mechanism (verified on run data):** S7 ratings keyed
  (session, query tag_key) and 60/60 query tag_keys are UNIQUE (median bucket 1) → ratings
  never transfer → ranker degenerates to deterministic tie-break (same 3 smallest ids served
  for all 60 queries: unique_served=3, top3_share=1.0). S3 is a non-filter (channel+vertical
  constant → 320/320 candidates per query). This is exactly A3's predicted failure. The
  slice does NOT kill whole-session hints; it kills the current ranking axis. Cheapest next
  test: tag_key = problem_shape|ending (drop constraint/channel/vertical) re-run on the SAME
  frozen tags (zero new LLM) before any new data spend. Determinism verified: fresh run vs
  zero-LLM resume byte-identical (metrics/cost/audit/per_query shas match); independent eval
  cross-check PASS. Result comment 5462472045; engineer cross-check 5462555923 (B0/B3
  byte-identical, T/B1/B2 flip direction → no stable gap, NOT FIT robust); FINAL VERDICT +
  ROUND 3 dispatch comment 5462711578; doc-fix PR #62 reviewed + MERGED 8e54b805.
- ROUND 3 (2026-08-29): **DISPATCHED — forcing arithmetic, zero new LLM** (verdict comment
  5462711578): hypothesis **H2-USEFUL-v2** — coarser `tag_key = problem_shape|ending` (drop
  constraint; channel+vertical constant → zero signal) lets S7 ratings accumulate → T.hit >
  B1.hit on the SAME slice, SAME frozen S2 tags. Verified feasible: raw/tag records store S2
  response JSON incl. problem_shape + ending. Scope (engineer): NEW run dir
  `runs/2026-08-29_PhaseC2_tagkey_shape-ending`, replay S3–S7 with bin/eval.py UNCHANGED
  (same slice/gold/seed), never mutate the completed Phase C run dir, cost.json tag_calls=0
  (method=recompute-from-frozen-tags), + A3 recheck. Success: (1) median tag_key bucket > 1
  AND unique_served > 3; (2) T.hit > B1.hit n=60; (3) B2 improves over 2/60; (4) T.wrong ≤ 15.
  Fail ⇒ H2-USEFUL closed on slice, full 1000+200 stays gated, next levers §8. Eval: QA new
  run dir (C-EV1..7, C-REPLAY, A3) + overdue ROUND 2 L2 card. Gate: lead re-executes,
  oversight merges.
- ROUND 2 PHASE C (2026-08-29): **LEAD SIGN-OFF on the curated gold** (comment 5462141906, PR #60 merged `03121f2`): C-GD6 resolved — d-5711 OVERRIDE→empty (promo-code exception teaches opposite policy; query resolution verified "prices cannot be changed"), d-4815 OVERRIDE→empty (refund sequence already visible in query; candidates PII-heavy), d-3219 ACCEPT pro empty (seed misread query: zipper-material allergy, not width), d-1789/d-5551 ACCEPT empty (query already contains the answer). checks re-run: HARD 65/0/11 deferred, SOFT 6/0, C-GD1..8 all PASS. Gold rows 60 (48→46 non-empty), C-GD7 3/46=7%. Manifest carries `signoff` block. **Phase C OPEN** (plan comment 5462159237): pool = 320 same-unlock union, S2 tag deepseek-v4-flash 380 calls, T/B0/B1/B2/B3 through ONE scoring function (bin/eval.py), one run dir `runs/2026-08-29_PhaseC_slice_deepseek-v4-flash`. Dispatched engineer+eval on bus (11:36:54Z). D4 runner `bin/run_slice.py` (B-arms, cost, audit A1-A6, manifest, report). Tag-vs-gold metrics (H2-TAG) stay unpublished — gold_tags decision still open (ROUND-0-PLAN §8).
- ROUND 1 PHASE B→C (2026-08-29): **D0 LEAD VERDICT — ACCEPT as canonical; no re-execution, no revision of the gold.** Lead re-execution on merged tree @ 5f12c7d: `bin/checks.py` → 82 checks, 68 passed / 13 deferred / 1 failed (C-GD6 SOFT), exit 0; C-GD1..5, C-GD7 (3/48=6.25%≤20%), C-GD8 HARD PASS; C-GD6 SOFT FAIL d-3219/d-5711/d-4815 (d-3219: seed annotation mismatches transcript — labeler's empty correct; d-5711/d-4815: rubric-interpretation gap, labeler more generous on promo/refund step sequences — documented bias direction). Gold verified: 60 rows == 60 slice ids (C-GD4), header caveat on file+manifest (C-GD1), 12 empty-useful valid rows, 408 useful pairs (A5 ≥ 40 ✓), A1 ceiling 48/60 = 0.80. Reproducibility: independent replica 60/60 identical lists + identical token counts (deterministic at temp 0) → same-prompt re-run adds zero information; rubric-emphasis re-run would be a frozen-prompt edit + new run id + full QA cycle at known-bias direction — rejected. Phase C OPEN (plan comment 5462108221): D3 audit.json (A1–A6) + D4 eval.py (five arms, one class path, C-EV1..5, C-REPLAY) + D5 slice run (S2 tag deepseek-v4-flash temp 0 → T/B0/B1/B2/B3, n=60) → metrics/cost/per_query/report.md → verdict §6.4. Doc fixes folded into Phase C PR: D0-GOLD.md canonical commit 30e6b83→5f12c7d + C-GD6 ACCEPTED note + slice_sha header note (header 167418c3 = labeler internal slice build; canonical slice file 56b5bfc0, ids identical). Open items: gold_tags decision (blocks §4.1 tag metrics only); rotation stats need the longer run.
- ROUND 1 PHASE B (2026-08-29): PR #57 (`h2/s0-run-cert`) lead-verified + MERGED as
  squash `97d3d9c`. checks.json byte-identical to lead re-exec (sha
  e5bf164f85f9…, 668 lines): HARD 58/0/11 deferred, SOFT 3/0/2 deferred, S0
  block 56/56, zero LLM; sign-off comment 5461551985 (formal APPROVE blocked:
  author's own PR — same convention as #54/#55). Hygiene fix folded into #57
  (`data/raw_gold_useful/`, `data/abcd_*.jsonl`, `data/preview_10.jsonl`) —
  verified ignored on main via `git check-ignore`. PR #58 (`h2/hygiene-gitignore`)
  byte-identical duplicate → commented superseded + closed. D0 labeler: dry-run
  slice = 60 (34 howto / 6 site / 12 neg / 8 manage); pilot 10/10 labeled
  (deepseek-v4-pro temp 0, key via h2_env.py); full-60 run launched ~09:22Z →
  `data/gold_useful.jsonl` + manifest + raw/ (gitignored). D0 artifact
  COMPLETE 09:40Z: 60/60 labeled, prompt_sha 14e5d5c7… frozen (matches dry-run),
  deepseek-v4-pro temp 0, 60 calls / 209,782 prompt tokens; 12 empty-useful
  rows (valid); raw records (60) contain ZERO "unlock" (C-GD7 anti-H1 holds
  end-to-end); committed to main as `30e6b83` (gold + manifest only; raw/
  stays gitignored). Evaluation PR #59 (D0 run + C-GD1..8 checks + slice
  packaging) lead-verified + MERGED as squash `5f12c7d` (comment 5461594791).
  checks.py on merged tree: 82 total, HARD 65/0/11 deferred, SOFT 5/1 —
  C-GD6 SOFT FAIL (seed direction 3/6: d-3219/d-5711/d-4815; labeler more
  generous on promo/refund action sequences); C-GD7 PASS (H1-signature 3/50 =
  6% ≤ 20%). Canonical gold = PR #59 (header-compliant); interim `30e6b83`
  superseded. Cross-run agreement 58/60 ids (temp-0 variance ~3%; d-1789
  self-flip between my pilot and full run). Phase B D0 GATE: PASS, 1 soft flag.
- ROUND 1 PHASE A→B (2026-08-29): Phase A CLOSED, Phase B OPEN. S0 gate
  certified on main @ f8a9e04 (engineer card 5460837114: exit 0, HARD 58/0 +
  11 deferred, SOFT 3/0 + 2 deferred, S0 block 56/56 green, zero LLM). Lead
  re-execution PASS on main (runs/2026-08-29_S0_checks_leadverify, checks.json
  byte-identical sha e5bf164f85f9…). Round plan posted (comment 5460962362);
  dispatches sent 07:06:13Z (engineer: push run dir + Phase B infra C-GD1..8 +
  frozen labeler prompt; evaluation: D0 gold labeling, pilot 10 → full 60,
  deepseek-v4-pro temp 0; bus readback verified, wakes delivered). Corpus
  synced into data/ (pool 28b77a32…, holdout e8f453e1…, dialogues.jsonl
  1bf94112…, 1200 rows, unlock dropped); labeler dry-run verified slice = 60
  (34 howto + 6 site + 12 negative + 8 negative_manage), prompt_sha
  14e5d5c7…, temp 0. Next: engineer PR (run dir + Phase B infra) → lead
  confirms → oversight merges; evaluation D0 card.
- ROUND 0 PHASE A (2026-08-29): D2 checks harness delivered + reviewed + MERGED.
  PR #55 (`h2/d2-checks`, head `173cb56`, +1936/−0): `bin/checks.py` +
  RUN-PROTOCOL §1.1 + S0 fixtures. Lead re-execution PASS (PR comment
  5460579829): clean re-run HARD 58 passed / 0 failed / 11 deferred, SOFT 5/5,
  S0 block 56/56 green, checks.json byte-identical across two runs (sha
  e5bf164f…); EVAL-PLAN §3 HARD gates all implemented (C-REPLAY deferred to
  D4/D5 runner, legit per CHECKS.md); §3 SOFT "empty candidates share" has no
  CHECKS.md id — must land in eval.py `retrieve.empty` (D4 note). Merged as
  squash `f8a9e04` 05:30:10Z, read-back verified. S0 smoke gate run dispatched
  (issue #51 comment 5460582879; bus dispatch + agent.wake 05:30:50Z, durable
  stream readback verified; engineer idle — stream is the signal). Next: D4
  (runner + eval.py §10 + audit A1–A6 + cost.json §4.6).
- ROUND 0 PHASE A (2026-08-29): D1 delivered + verified + MERGED. PR #54
  `h2(d1): bin/ scripts S1-S7 + replay per SPEC` (head `c0b15f6`; merged to
  main 02:54:21Z as squash `bf715452c`, read-back verified) — engineer
  fixture run at /opt/data/work/h2run. Lead clean-
  worktree re-run at /opt/data/work/h2run-verify: ingest byte-identical
  (sha 35d8d22f…); candidate sets / ranked order / packet ids / S6 outcome
  (good) / S7 deltas identical; C-UP5 ✓ (rerun applies 0), C-FUTURE ✓ all 10,
  C-RP2 ✓ (d-001 empty→unclear), C-RT2/C-SELF/C-ISO4 ✓. Caveat: S2 free-text
  tags NOT byte-stable at temp 0 (phrasing variance only; structured fields
  stable) — pin sessions.jsonl if D2 needs byte-stable tags. Verdict PASS
  (PR comment 5459303743). D0 gate: PR #53 (labeler) merged to main.
- ROUND 0 PHASE A (2026-08-29): D2 dispatch sent — checks harness + S0 smoke
  block → engineer. Brief: issue #51 comment 5459905598 (build CHECKS.md,
  RUN-PROTOCOL.md, eval.py §4/§10, audit.json A1–A6, cost.json §4.6; replay
  byte-identical; gate: all HARD green + B0.hit==0 on 10–20 fixtures). Bus
  verified: dispatch + agent.wake on office:events 02:56:52Z (0 live
  subscribers — engineer idle; durable stream is the signal). PR #54 merge
  commit bf715452c on main.
- ROUND 0 (2026-08-28): original plan posted on issue #51 (comment 5458916287,
  pre-decision) — **superseded**. Founder decision 2026-08-28 (D0 gold
  agent-labeled on pro): updated plan committed on `docs/h2-round0-plan`
  (PR #52, `ROUND-0-PLAN.md`), comment 5458941785 + reconciliation note
  5458949597. D0 gold = agent-labeled `deepseek-v4-pro`, NOT human gold; slice
  = 60 hold-out queries (34 FAQ how-to + 6 site-troubleshoot + 20 negatives);
  labeler never sees `unlock` (adapter drops it; C-GD7 anti-H1 check); caveat
  in file header / manifest / every L2-usefulness report line; S2 tag stays
  `deepseek-v4-flash` pinned. Phase A (D1+D2, fixtures) unchanged — engineer
  D1 work already dispatched in parallel.

## Discipline
- Update as soon as evidence changes (D0 QA numbers, A1–A6 audit, slice run metrics).
- Every finished experiment updates its linked hypothesis.
- Details live in the Research Report / run dirs, not here.
