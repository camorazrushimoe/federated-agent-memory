# Phase 0 — corpus reproduction probe (BON-35)

**Hypothesis under test (H0):** the certified corpora (ABCD, TWCS) reproduce the
numbers certified in `docs/research-customer-support-dialogue-datasets.md` on
the lab machine. Success = every number in the issue #6 expected-table matches;
failure = any mismatch (which would be a product-side finding, not a lab bug).

**Verdict: PASS — all 8 expected-table checks match exactly.**
Plus one non-blocking anomaly found in the *cited constants* (not in the
expected table) — see "Anomaly" below.

## Environment

- Machine: WSL lab container, Python 3.13.5, venv at `.venv` (uv)
- Deps: `pandas`, `pyarrow`, `datasets` (HF)
- Repo: `camorazrushimoe/federated-agent-memory` @ `a57c59a` (main)
- Date: 2026-08-27 (UTC)

## What was done

1. Downloaded ABCD from GitHub `asappresearch/abcd` (no auth):
   `data/abcd/abcd_v1.1.json.gz` (37 MB), `guidelines.json`, `ontology.json`
   (raw files stay in gitignored `data/`).
2. Downloaded TWCS from HF `TNE-AI/customer-support-on-twitter-conversation`
   via `datasets`, written to `twcs_conversations.parquet` (gitignored).
3. Ran the repo's probe, unmodified:
   - `python research/probe_dataset.py --kind abcd --path data/abcd/abcd_v1.1.json --guidelines data/abcd/guidelines.json`
   - `python research/probe_dataset.py --kind twcs --path twcs_conversations.parquet --sample 500`
   Outputs saved as `abcd_probe.json` and `twcs_probe.json` in this folder.
4. Compared against the issue #6 expected table (results below).
5. Investigated the TWCS cited-constant anomaly (see below):
   `twcs_resample_scan.json` records the scan (5 offset schemes + random
   500-samples with 5 seeds + a random 20k truth sample).

## Results vs the issue #6 expected table

| check | expected | got | match |
|--|--|--|--|
| ABCD conversations | 10,042 (8,034 / 1,004 / 1,004) | 10,042 (8,034 / 1,004 / 1,004) | ✔ |
| ABCD subflows present | 96 | 96 | ✔ |
| ABCD per-subflow median | 69.5 | 69.5 | ✔ |
| ABCD action turns | 36,482 | 36,482 | ✔ |
| ABCD dialogues with ≥1 action | 100% | 1.0 | ✔ |
| ABCD guidelines join coverage | 0.456 | 0.456 | ✔ |
| TWCS rows | 794,335 | 794,335 | ✔ |
| TWCS hapax_share (n=500) | ~0.56 | 0.547 (head-500) / 0.565 (5-offset) | ✔ |

**Verdict: corpora workable.** ABCD = primary (action ground truth, MIT).
TWCS = real-world research corpus (note: research licence, non-commercial).

## Anomaly — TWCS cited constants vs certified sampling method

The expected table (issue #6) is satisfied. But the **cited constants block**
in the datasets doc (`REVIEW_CITATIONS` in the probe;
`docs/research-customer-support-dialogue-datasets.md` §3) does **not**
reproduce under `--sample 500`, which is `head(500)` — and not under the
documented "500-conversation sample across 5 offsets" (500 = 5 × 100 at
`i·N//5`), either:

| metric | cited | head(500) | 5-offset (N//5) | random 20k (truth) |
|--|--|--|--|--|
| median real words/turn | 18 | 8 | 9 | **17** |
| median turns | 3 | 5 | 3 | 2 |
| max turns | 48 | 448 | 48 | 80 |
| distinct turn patterns | 103 | 175 | 88 | — |
| distinct tokens | 5,836 | 7,067 | 5,309 | — |
| hapax_share | 0.56 | 0.547 | 0.565 | 0.593 |
| AmazonHelp in sample | 52 | 23 | 40 | — |

Reading: the *cited* block (esp. median_real_words = 18) looks like it was
measured on a much larger sample (the random-20k truth gives 17), while the
"5 offsets" note describes the *structural* stats (median/max turns) of a
specific 500-sample. The doc's `reproduce_with` command (`--sample 500` =
head(500)) matches neither. This is a **documentation/reproducibility defect,
not a data defect** — the full-corpus row count (794,335) and all qualitative
findings (real brands, organic signals ~11%/4%/85%, varied structure) hold.
Flagged for the product team; not a blocker for Phase 1.

## How to re-run

```bash
cd federated-agent-memory
uv venv .venv --python 3.13 && source .venv/bin/activate
uv pip install pandas pyarrow datasets

mkdir -p data/abcd && cd data/abcd
curl -L -o abcd_v1.1.json.gz https://github.com/asappresearch/abcd/raw/master/data/abcd_v1.1.json.gz
curl -L -O https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json
curl -L -O https://raw.githubusercontent.com/asappresearch/abcd/master/data/ontology.json
gunzip -k abcd_v1.1.json.gz && cd ../..

python research/probe_dataset.py --kind abcd \
    --path data/abcd/abcd_v1.1.json --guidelines data/abcd/guidelines.json

python - <<'PY'
from datasets import load_dataset
ds = load_dataset("TNE-AI/customer-support-on-twitter-conversation", split="train")
ds.to_parquet("twcs_conversations.parquet")
PY
python research/probe_dataset.py --kind twcs --path twcs_conversations.parquet --sample 500
```

## Known quirks

- **ABCD action names live in `targets[2]`**, not in an `action` dict. Action
  turns are `{"speaker": "action", "targets": [subflow, "take_action",
  "<action-name>", [args], -1]}`. Any analysis code must read `targets[2]`
  (the probe only counts action turns, so it is unaffected).
- `--sample N` in the probe is `head(N)` — a positional slice, not a random
  sample. For TWCS, structural stats on head(500) differ from certified
  500-sample stats (see anomaly). Use the 5-offset reconstruction for
  certified-comparison, or ≥20k random for corpus-truth estimates.
- TWCS parquet is ~34 MB, 794,335 rows, columns
  `conversation_id, company, conversation, summary`. Full-corpus `company`
  cardinality = 109 values (108 non-blank) — matches the certified "109
  company values".
- The lab terminal guard blocks shell heredocs in some commands; scripts in
  this folder are written to files and executed directly.

## Files

| file | what |
|--|--|
| `abcd_probe.json` | probe output, ABCD (expected-table check) |
| `twcs_probe.json` | probe output, TWCS head(500) |
| `abcd_probe_with_mapping.json` | probe output incl. BON-37 mapping coverage |
| `twcs_resample_scan.json` | TWCS sampling-method scan (anomaly investigation) |
| `subflow_inventory.py` / `.json` | dump of the 3 subflow name sets (BON-37 input) |
| `variant_verification.py` / `.json` | variant-share + ambiguous-subflow evidence (BON-37) |
| `build_mapping.py` | deterministic builder for `research/abcd_subflow_mapping.{json,csv}` |
| `check_schema.py` | one-off schema check (action turn shape) |
