# M2 R2 canonical re-run — provenance & budget record

**Run id:** `m2-r2-rerun-20260828-lead`
**Date:** 2026-08-28 (UTC)
**Executor:** lab-1 research-lead (single canonical executor) — per ruling
`5451978604` (canonical = the m2-r2 run) and reconciliation `5452083284`
(competing ruling `5452069703` withdrawn). The eval container is
down/quarantined; oversight directed the lead seat to execute.
**Frozen state measured:** `origin/main @ 3b3b296` (S0-gate verified
2026-08-28T11:46Z, see `s0_report.json` in the run dir).

## Judge

- Model: `deepseek-v4-pro`, `temperature=0`, one fresh, independent API call
  per item/conversation (maximal isolation — each context contains only the
  frozen protocol text + that item's staged fields, plus the committed
  reference for scoring Call 2; no candidate mapping, no candidate type, no
  cross-item content).
- Independence: the judge model is independent of the session model
  (qwen3-8-27b) that authored the B2 draft units.
- Staged artifacts byte-identical to the frozen repo pins (sha256:16 match
  on protocol + all four judge inputs, verified 2026-08-28T11:50Z).

## Budget (frozen: 640 logical = 480 blind + 80 reference + 80 scoring)

- Logical spend: 640/640 across 4 assembled stages (see BUDGET-LEDGER.jsonl).
- Raw API calls: productive + wasted. **Incident inc-1** (2026-08-28T11:52Z):
  a smoke invocation piped through `head` sent SIGPIPE to the runner;
  orphaned workers issued 310 calls whose responses were lost. 10 answers
  survived checkpointing and were kept (fresh, valid, isolated). Full
  record: `INCIDENT-1.json`. No answer in the committed result files comes
  from any other executor or from the discarded pre-run chunks (ruling
  salvage rule: conformance + isolation re-verification was impossible for
  the quarantined contexts → all 240 blind items and all 80 convos re-run
  fresh).

## Conformance

Each answer file passes its staged checker (field set, input order, grid
values, coverage) and the join's gate layer (gates 1–5 of
`research/phase2/m2/README.md`). The join records the sha16 of all 7
inputs (3 frozen + 4 judge) in `m2_results.json`.

## Honesty clause (binds every number in m2_results.json / m2_report.md)

All M2 numbers are agent-judged. The two-pass agreement is a self-consistency
floor under frozen rules, NOT human inter-rater agreement. B2 units are
agent-drafted; the falsification is the independent blind judge.

## Post-join operations (this round)

- `evaluation/m2-r2 @ 0e4350a` (void zombie ref; 2 answer files, per-item
  400-line cap, contaminated carry-over pass-2 `24dcbbf7c3c2cabe`) —
  **removed from origin** by the lead seat (eval session request #2, comment
  5452325015; verified: `git ls-remote` returns 0 refs). This run's committed
  answers are byte-distinct from it (same item_ids, different shas:
  pass1 `62ad3fe9b8b7c09c` / pass2 `4ddcffb8a86b805f`).
- **PR #30 opened** (`m2/r2-results` → `main`, base verified `3b3b296`).
  Lead verification note posted on the PR: join independently re-run
  (5 gates GREEN), all input shas match the frozen pins, contamination check
  clean.
- **PR #30 MERGE held** by the consent gate at 12:25Z — not merged by me
  (same behavior as H1 PR #29: the gate blocks; no retry loop).
- **Result-line POST to issue #6 held** by the consent gate at 12:26Z —
  draft saved at `/opt/data/work/fam-research/gh6_r2_measured_result_line.md`
  (publish on next consent window).
- **No second 640 fired** from this seat: the eval session (5452325015) asked
  the lead to confirm canonical status before a fresh full budget. This run
  IS the canonical measurement. An independent cross-validation re-run, if
  wanted, is a NEW pre-registered budget — founder/oversight decision.
- Stale zombie session `9463ab65`: no killable handle from this seat (not in
  my subagent tree; another container's process) — flagged to the owning
  seat / oversight.

## Verdict

**R2 round: FAIL (0/80).** B2 is not a viable token reduction: it loses the
binding-constraint and resolution-order judgment fields faster than it saves
tokens (aggregate ratio 0.239 vs bar ≤0.1; per-convo value(B2) ≥
0.8·value(B0) met on 35/80 but the token half met on 0/80). B1 stays
falsified (identical to R1). No collapse (B0 1.000 / B1 0.000 / B2 0.413).
Recommendation: do not run §4 outcome work (R3) on the current B2 unit;
re-scope R3 per the result line.
