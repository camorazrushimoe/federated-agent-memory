# eval-inputs — shared pack for the auto-evaluation framework

Not an experiment. Shared inputs and the auto-eval spec, next to the H2 / H2v2 labs.

Read `AUTOEVAL.md` first. That is what the engineer builds.

## One-command pack

Sources already live in this repo (do not re-download):

- pool raw: `standalone/h1-experience-cards/data/abcd_1000_pool.jsonl` (1000)
- hold-out raw: `standalone/h1-experience-cards/data/abcd_200_holdout.jsonl` (200)
- gold: `standalone/h2-federated-scoped-memory/data/gold_useful.jsonl`

```bash
python3 standalone/eval-inputs/build_ready_pack.py
```

Writes into this folder:

| file | rows | role |
|---|---:|---|
| `dialogues_pool_320.jsonl` | 320 | memory pool to tag (cold start) |
| `dialogues_slice_60.jsonl` | 60 | eval questions, with transcripts |
| `gold_useful.jsonl` | 60 | oracle usefulness labels |
| `d0_slice.jsonl` | 60 | question ids only |

The live D4 run does **not** ingest all 1000. It tags the 320-session same-unlock union, then evaluates 60 questions.

`unlock` is present on the raw / packed rows so the oracle path can be audited. The tagger must **not** see `unlock`.

Gold is agent-labeled (`deepseek-v4-pro`), not human gold. Do not relabel.
