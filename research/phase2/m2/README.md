# M2 results (R2) — join + re-run contract

**Artifact set:** `m2_results.json` + `m2_report.md`, produced by the join of the
pinned inputs with evaluation's judge numbers, per the frozen contract
(GH #6 `5449115746` §4 item 4; BON-42).

**What the join renders (frozen, not negotiable — D18):**
per-convo table (value B0/B1/B2, tokens B0/B1/B2, per-convo bar), round verdict
vs the frozen bar, B1-vs-B2 falsification outcome, per-field loss ledger from
the judge's per-item scores, two-pass agreement number, honesty clause.

## Re-run contract (one command, when the judge's numbers land)

```bash
python3 research/phase2/m2/join_m2.py \
    --pass1 <evaluation's pass1_answers.jsonl> \
    --pass2 <evaluation's pass2_answers.jsonl> \
    --scoring <evaluation's scoring_answers.jsonl>
# -> research/phase2/m2/m2_results.json + m2_report.md
```

`--m2` defaults to `research/phase2/m2` (run from the repo root).

### What the join verifies before computing anything (gates)

1. **Frozen inputs by sha256:16** — `candidates.jsonl` `dd1869a2d72c6b2b`,
   `b2_draft.jsonl` `5063a85c4ab79465`, `sample.jsonl` `f2195e7a6abe2221`.
2. **candidates ↔ b2_draft integrity** — 80/80 convo_id match, frozen unit key
   order (`problem_shape, constraint, unlock, what_worked, receipt{corpus,
   convo_id, flow, subflow, event_span, scope, confidence}`), `what_worked` ==
   the B1 trace on every row, receipt fields == candidate-row fields.
3. **Blind layer** — pass1/pass2 answers in input order, exact field sets,
   240 items each, item↔codename known to the committed binding mapping,
   orders differ across passes (frozen protocol).
4. **Scoring layer** — 80 rows in scoring-input order, references R1–R3
   non-empty, exactly the 3 row candidate codenames scored, s-values on the
   frozen grid (s1/s2 ∈ {0, 0.5, 1}, s3 ∈ {0, 0.25, 0.5, 1}).
5. **Frozen token counter** — `n_tokens_b2` recomputed on each draft unit
   (whitespace-split of `json.dumps(unit)`, default separators) and required to
   equal the draft's stored value on all 80 rows. The join never trusts a
   precomputed token count; it recomputes it.

Any gate failure aborts with a message — no partial artifacts, no silent
fallbacks. The judge files themselves are pinned by sha in
`m2_results.json → judge_inputs`, so the join is a pure function of them:
re-runnable, auditable, and re-runnable by the lead or oversight without
access to the judging context.

### Determinism

Given the same judge files, the output is byte-identical: fixed date string,
fixed key order, convo_id-sorted per-convo table, no wall-clock or randomness.
`m2_results.json` records the shas of all five inputs (three frozen, three
judge — the judge trio by sha16) so any reader can re-verify provenance.

### What the join does NOT do

- No bar tuning, no threshold selection, no metric substitution — the bar is
  frozen (§3 of 5449115746) and a missed bar is the finding (D18).
- No `m2_results.json` is produced from the frozen inputs alone — that would
  be an empty join (noise). The join runs only with the judge's numbers.
- `--dry-run` artifacts are stamped **SYNTHETIC DRY RUN** and exist only for
  the selftest; they are never the round's result.

### Pipeline selftest (synthetic judge files — proves the pipeline, not a result)

```bash
python3 research/phase2/m2/selftest_join_m2.py
```

Runs the join end-to-end on fabricated-but-structurally-valid judge outputs in
two scenarios (collapse / no-collapse), verifies determinism, re-derives every
headline number independently (plain Python, from the judge files alone), and
proves the gate layer rejects tampered inputs. Outputs go to `/tmp` and are
deleted on success.

### Provenance of this round's inputs

| input | sha256:16 | state |
|---|---|---|
| `candidates.jsonl` | `dd1869a2d72c6b2b` | PR #22, main @601c310 (review 5449907074) |
| `b2_draft.jsonl` | `5063a85c4ab79465` | PR #23, main @d8a8f33 |
| `sample.jsonl` | `f2195e7a6abe2221` | PR #21, main @4d68187 (D22) |
| judge binding layer | (committed under `judge/binding/`) | PR #22 |
| judge scoring layer | (committed under `judge/scoring/`) | PR #22 |

**Honesty clause (rides with every number in this directory's results):** all
M2 numbers are agent-judged; the two-pass agreement is a self-consistency
floor under frozen rules, NOT human inter-rater agreement. The B2 units are
agent-drafted (lead); the falsification is the independent blind judge.
