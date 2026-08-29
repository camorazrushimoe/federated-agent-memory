# D0 — gold_useful, agent-labeled (deepseek-v4-pro)

**STATUS: agent-labeled (deepseek-v4-pro), not human gold.**
Prepared per founder decision (issue #51). Labeling does NOT run on the
hold-out until the lead opens Phase B (after D2 green).

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
