# M1 Labeling Runbook — the exact steps when candidate pairs land

Owner: evaluation (lab-1) · Pre-registered 2026-08-27 (v1.1 protocol).
Purpose: make the real labeling run turnkey and auditable. Each step lands a
committed artifact; nothing in this runbook is skipped silently.

## S0 — Intake (when the engineer's pairs arrive)

1. Pull the engineer's branch/commit; confirm `candidate_pairs.jsonl` path.
2. Run `python3 research/phase2/labeling/validate_pairs.py <pairs-file>`
   (default corpus path is baked in).
   - `OK_TO_LABEL` → proceed.
   - `RANGE_ISSUE_ONLY` → post the range mismatch on #6, ask engineer to
     adjust; do NOT label out-of-range.
   - `BLOCKED` → post the exact failing items on #6; fix-forward by the
     engineer. Stop; do not silently repair.
3. Record in the PR/commit: pair count, band counts, sub_band counts, max
   conversation reuse (all from the validator's JSON output).

## S1 — Pass 1 (this session)

1. `python3 split_passes.py <pairs> research/phase2/m1/passes`
   → `pass1_input.jsonl` + `pass2_input.jsonl` + `passes_manifest.json`
   (seeds 20260827 / 20260927; verify `orders_differ: true`).
2. Read `pass1_input.jsonl` (pair_id + display ONLY — no metadata).
3. Label every pair per PROTOCOL §2 (scale + rules R1–R6), one line rationale
   each. Write `research/phase2/m1/pass1_labels.jsonl`:
   `{"pair_id", "pass": 1, "label", "rationale"}`.
4. Commit: "research(phase2): M1 pass-1 labels (N pairs, agent-labeled)" —
   commit ONLY pass1 artifacts (input, labels, manifest).
   **Do not open or summarize pass1 labels from here on out in this context.**

## S2 — Pass 2 (fresh context)

1. Stage exactly two files in a clean directory:
   `PROTOCOL-m1-pairs.md` + `pass2_input.jsonl`.
2. Spawn a fresh agent session (delegate_task) whose prompt contains ONLY:
   the scale + rules from the protocol, the path to pass2_input.jsonl, the
   output spec. No pass-1 file, no pass-1 summary, no prior labeling context.
   (Mechanism tested 2026-08-27 on the 6-pair synthetic set: fresh-context
   subagent produced conforming `pass2_labels.jsonl` — the mechanism works.)
3. Verify the returned file: 6..N lines, all pair_ids present exactly once,
   labels in the 3-class set, rationales non-empty.
4. Commit: "research(phase2): M1 pass-2 labels (N pairs, agent-labeled,
   fresh context — no pass-1 access)".

## S3 — Score + report

1. `python3 score_agreement.py --pairs <pairs> --pass1 pass1_labels.jsonl
   --pass2 pass2_labels.jsonl --outdir research/phase2/m1/gold`
   → `gold_m1_pairs_agentlabeled.jsonl` (per-item, provenance `agent-labeled`)
   + `agreement.json` + `agreement_report.md` (+ `escalation_sample.md` iff
   the rate > 15%).
2. Read the report. The headline number is
   `inter_pass_disagreement_rate` per set and per band.
3. **If escalation fired:** STOP the set. Post the 20-item
   `escalation_sample.md` on #6 for founder review (not the whole set).
   The set is `HOLDED-ESCALATED` until founder disposition.
4. Commit the gold set + report. Post on #6 (handoff format):
   - the disagreement rate NUMBER (set + per band) with the honesty clause
     (agent self-consistency, not human agreement),
   - canonical label counts,
   - gold-set commit hash,
   - ready-for-B1 signal (the gold set is what the engineer scores B1/B2
     against; B1 scoring itself is the engineer's round artifact).

## S4 — Handoff to B1/B2 scoring (next round)

- Gold set: `gold_m1_pairs_agentlabeled.jsonl`, canonical labels = scoring
  labels. Band/sub_band metadata is on each line for per-band metrics.
- Bar (pre-registered, unchanged): false-friend rate ≤ 10% at ≥ 60% recall on
  the should-match band. B1 (TF-IDF on customer turns) first; B2 only if
  warranted by the method doc.

## Failure modes and pre-registered responses

| failure | response |
|---|---|
| engineer's pairs fail validation | post exact items on #6; engineer fixes; no labeling |
| pass 2 returns malformed/missing labels | regenerate the fresh pass-2 run once (new context); a second malformed run → escalate to lead |
| disagreement > 15% | STOP + 20-item sample escalation (never the whole set) |
| I cannot deliver a set (context/time) | pre-registered ABCD-only cut applies; report untested parts as untested; do not stall the crew |
| rubric doubt mid-pass | rule R6 + frozen rubric govern; a doubt that can't be resolved by the rubric → label per conservative default, record the doubt in the rationale; protocol change only via version bump, never mid-set |
