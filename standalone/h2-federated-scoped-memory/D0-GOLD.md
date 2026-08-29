# D0 — gold_useful, agent-labeled (deepseek-v4-pro)

**STATUS: agent-labeled (deepseek-v4-pro), not human gold.**
Prepared per founder decision (issue #51).

## Canonical gold (on main, commit 30e6b83)

The D0 gold on main is the **lead-curated** output of the labeler run
(2026-08-29, slice = 60 queries):

- `data/gold_useful.jsonl` — 60 rows + mandatory `#` header (C-GD1; header
  added by the engineer on top of the lead's committed file, which the
  pre-header labeler did not write).
- `data/gold_useful.manifest.json` — run manifest (model `deepseek-v4-pro`,
  temperature 0, prompt sha `14e5d5c7…`, 60 calls, 209,782 prompt / 5,981
  completion tokens).
- **Lead curation:** 2 list overrides (d-1789, d-5551 → empty, where the
  model's own note said the query already contains the answer but its list
  was non-empty — a labeler self-contradiction) and ~46 note rewrites for
  clarity. Raw labeler output for these rows is preserved in
  `runs/2026-08-29_D0_gold_useful/gold_useful.jsonl` (the replica run).

## Reproducibility (independent replica run, engineer, 09:28Z)

A second, fully independent run of `bin/label_gold_useful.py` (same prompt,
same slice, temp 0) produced **60/60 identical useful lists and identical
token counts** — the labeler is deterministic on this workload; the D0 gold
is a reproducible measurement, not a one-off draw. Raw records
(`data/raw_gold_useful/<query_id>.json`, gitignored) replay without new
LLM calls (`--replay-dir`).

## QA (C-GD1..8, in `bin/checks.py`)

- C-GD1 (header), C-GD2 (no future leak), C-GD3 (no PII), C-GD4 (rows ==
  slice), C-GD5 (raw per row), C-GD7 (anti-H1: 3/50 whole-bucket rows = 6%
  ≤ 20% gate), C-GD8 (labeler `deepseek-v4-pro`, S2 `deepseek-v4-flash`
  untouched): **HARD PASS**.
- **C-GD6 SOFT FAIL** — 3/6 seed rows contradict in direction. The lead's
  curation kept the labeler's direction on all 3 (d-3219 empty, d-5711 /
  d-4815 non-empty), which is an implicit accept; **explicit sign-off still
  requested** (accept as-is vs re-run with rubric emphasis, new run id).

### C-GD6 investigation (report item, per ROUND-0-PLAN §7)

| seed row | seed direction | labeler | analysis |
|---|---|---|---|
| d-3219 | non-empty (width) | empty | Query actually asks about **zipper material** (allergy); candidates are width chats. Seed annotation mismatches this transcript — labeler's empty list is defensible. |
| d-5711 | empty | non-empty (9) | Labeler: "offer promo code to appease" is a transferable move. Seed: one-off exception must not transfer (empty is gold). Rubric-interpretation gap. |
| d-4815 | empty | non-empty (6) | Labeler: refund step sequence (validate → method → record → issue) is transferable. Seed: identifier-heavy transcript is not a hint. Rubric-interpretation gap. |

The labeler consistently treats "transcript contains the reusable step
sequence" as useful even when the seed's negatives call for empty lists
(identifiers + one-off exceptions). **Decision needed (lead): accept as-is
with the SOFT flag documented, or re-run with rubric emphasis (new run id).**
Prompt stays frozen either way — no silent edits (CHECKLIST stop rule).

## What this is

`data/gold_useful.jsonl` on the DATA-AUDIT §6 slice, written by
[`bin/label_gold_useful.py`](./bin/label_gold_useful.py) calling
`deepseek-v4-pro` through the factory `call_llm` wrapper (reused from H1
per the founder decision; copied into `bin/llm.py` so C-ISO1 holds — no
import from H1).

Every row and every report line carries the marker:
`agent-labeled (deepseek-v4-pro), not human gold`.

## Slice (60 queries, deterministic)

| family | rule | n |
|---|---|---|
| how-to | hold-out unlock contains `_how_` | 34 |
| site | hold-out unlock in {slow_speed, shopping_cart, search_results} | 6 |
| negative | all core dispute/promo (bad price ×6, refund ×2, promo ×4) + first 8 `manage_*` by dialogue_id | 20 |

The audit text says "20 отрицательных"; the exact `manage_*` subset is a
documented deterministic choice (first 8 by dialogue_id) — flagged to the
lead for sign-off at Phase B.

## Labeling rule (from the prompt, frozen; sha256 in manifest)

For each slice query: candidates = pool sessions with the same raw unlock
and strictly earlier `closed_at` (C-FUTURE). The model reads transcripts
ONLY — `unlock` / `unlock_guideline` never enter the prompt, the output, or
the notes. Judgment: does the candidate carry a transferable move (step
sequence / procedure / workaround) the query's label does not contain?
Empty list is valid. Same topic ≠ useful; identifiers + one-time exceptions
≠ useful.

## How to run (Phase B, after the lead opens it)

```bash
cd standalone/h2-federated-scoped-memory
python bin/label_gold_useful.py \
    --pool data/abcd_1000_pool.jsonl \
    --holdout data/abcd_200_holdout.jsonl \
    --out data/gold_useful.jsonl \
    --manifest data/gold_useful.manifest.json \
    --raw-dir data/raw_gold_useful \
    --model deepseek-v4-pro
```

- `--dry-run` builds slice + candidates, no LLM, no gold file.
- `--self-test TMPDIR` runs on a synthetic pack (never the hold-out).
- `--replay-dir DIR` re-runs from saved raw records, zero LLM calls.

## Constraints honored

- NOT derived from `unlock` / `unlock_guideline` (no H1 re-measure).
- Useful ids only point at strictly earlier sessions (C-FUTURE).
- Empty useful list on dispute/refund/promo is a valid answer.
- Same key / base_url as the factory (config.yaml or H2_*/H1_* env); no new secret.
- Model is a flag (`--model deepseek-v4-pro` default, founder decision #51), not an edit.
