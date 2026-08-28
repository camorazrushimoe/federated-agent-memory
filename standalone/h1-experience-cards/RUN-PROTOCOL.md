# H1 Experience Cards — Run Protocol

How a run is set up, executed and recorded so that two runs are comparable and
any reviewer can re-derive the numbers. Companion to `EVAL-PLAN.md` (what is
measured), `CHECKS.md` (what must hold), `SPEC.md` (what is built).

---

## 1. One command, one run

```
python bin/run_experiment.py \
    --pool    data/abcd_1000_pool.jsonl \
    --holdout data/abcd_200_holdout.jsonl \
    --model   deepseek-v4-flash \
    --stage   S2 \
    --out     runs/2026-08-28_S2_deepseek-v4-flash
```

- `--stage` ∈ `S0 | S1 | S2 | S3 | S4` (`EVAL-PLAN.md` §9). The stage decides
  the data slice; the code path is identical.
- `--replay <run_id>` re-runs everything from that run's recorded extract
  responses, with **zero** LLM calls. Required, not optional.
- `--baseline B0|B1|B2` runs a baseline through the same scoring path instead of
  the card pipeline.
- The runner MUST refuse to start if the output dir exists and is non-empty.
- The runner MUST refuse to touch the hold-out in `S0`/`S1`.

Everything the runner does is `tick.py` → `cluster --force` (S1/S2 use the
natural 100-chat cursor and log how many passes fired) → per-hold-out
`serve.py` → `eval.py`. No new pipeline logic lives in the runner.

---

## 2. Mapping the data pack to the spec's dialogue schema

The pack (`data/README.md`) is **not** the spec's §3 record. Convert on ingest,
deterministically, and write the result to `data/dialogues.jsonl`.

### 2.1 Field mapping

| pack field | dialogue field | rule |
|--|--|--|
| `chat_id` | `dialogue_id` | `f"d-{chat_id}"` |
| `tenant` (ABCD flow, 10 values) | `tenant_id` | `f"abcd-{tenant}"` |
| `vertical` (`customer-support`) | `vertical` | verbatim |
| `turns[].speaker` (`agent`/`customer`) | `turns[].role` | verbatim; the pack has no `tool` turns, so `what_worked` comes from agent phrasing only — state this in the report |
| `turns[].text` | `turns[].text` | verbatim, no normalisation, no truncation |
| — | `channel` | constant `"web"` |
| `unlock`, `unlock_guideline`, `split`, `n_turns` | **dropped** | ground truth. MUST NOT reach `extract.py` (check `C-L2`) |

Scope key = `tenant_id` + `vertical` → 10 scopes, all inside one vertical.

### 2.2 `agent_id` — synthesized, and this matters

The pack has no agent identity. Left absent, `SPEC.md` §5.1 falls back to
`independence=dialogue-only`: any two similar dialogues promote a card, so
`K_INDEPENDENT = 2` never actually blocks anything and the anti-echo /
independence design is **not under test**.

Therefore synthesize, deterministically:

```
agent_id = "agent-" + chr(ord('a') + int(sha256(dialogue_id).hexdigest(), 16) % A)
A = 4          # default; configurable as AGENT_POOL_SIZE
```

- Deterministic, so re-runs are stable and the assignment is reproducible from
  the dialogue id alone.
- Report `independence=agent+dialogue` and the number the gate actually blocks
  (audit **A3**). If the gate blocks nothing even with `A=4`, say so plainly —
  an untested gate is not a passed gate.
- Run S1 once with `A=1` (all dialogues from one agent) as a **negative
  control**: `votes` must stay 1 and nothing may become `shared`. That is the
  §10.3 fixture at scale.

### 2.3 `closed_at` — two timelines, chosen explicitly

The pack has no timestamps, so the age-stale rule cannot fire on real data.
Synthesize with `--timeline`:

| timeline | rule | use |
|--|--|--|
| `compressed` (**default for S1/S2**) | `closed_at = T0 + (index mod 20) days`, all within `STALE_AFTER_DAYS` | main measured runs; age-stale is off **by construction** and this MUST be stated next to every reported metric |
| `aged` | `closed_at` spread over 0–60 days by index | staleness contract tests only (`C-CL5`, `C-CL6`), never for headline metrics |

`T0` is fixed in the config and recorded in the manifest. Ordering within the
pool follows file order, which is the pack's subflow round-robin — so a
`compressed` timeline does not accidentally cluster one topic into one week.

---

## 3. Run directory layout

```
runs/<run_id>/
  manifest.json            # identity + every input/output sha256
  audit.json               # A1..A5 answers (EVAL-PLAN §7), required before S2
  checks.json              # every CHECKS.md assertion, pass/fail
  metrics.json             # the numbers (schema §4)
  cost.json                # tokens, USD, latency percentiles
  report.md                # human-readable: numbers, verdict, honesty clause
  data/
    dialogues.jsonl        # normalized pool (post-mapping, ground truth stripped)
    cards.jsonl            # card store after the final cluster pass
    cluster_cursor.json
    feedback.jsonl
    holdout_dialogues.jsonl
  per_dialogue.jsonl       # one row per hold-out dialogue (schema §4.2)
  raw/
    extract/<dialogue_id>.json    # {request, response, model, usage, ms}
    judge/<card_id>_pass{1,2}.json
  packets/<dialogue_id>.txt       # exact served packet text
```

`run_id` = `<UTC date>_<stage>_<model>[_<variant>]`. Never reuse one.

### 3.1 `manifest.json`

```json
{
  "run_id": "2026-08-28_S2_deepseek-v4-flash",
  "created_at": "2026-08-28T14:00:00Z",
  "stage": "S2",
  "git_commit": "<sha of the repo at run time, dirty flag included>",
  "extract_model": "deepseek-v4-flash",
  "judge_model": null,
  "base_url": "https://api.deepseek.com/v1",
  "temperature": 0,
  "timeline": "compressed",
  "agent_pool_size": 4,
  "config": { "K_INDEPENDENT": 2, "MAX_PACKET": 3, "STALE_AFTER_DAYS": 30,
              "MATCH_THRESHOLD": 0.18, "CLUSTER_THRESHOLD": 0.35,
              "CLUSTER_EVERY_N_CHATS": 100 },
  "cluster_passes_fired": 10,
  "inputs":  { "pool": {"path": "...", "sha256": "...", "rows": 1000},
               "holdout": {"path": "...", "sha256": "...", "rows": 200},
               "prompts": {"path": "PROMPTS.md", "sha256": "..."} },
  "outputs": { "cards.jsonl": "sha256", "metrics.json": "sha256",
               "per_dialogue.jsonl": "sha256" },
  "replay_of": null
}
```

A run whose manifest is missing any sha, or whose `git_commit` is dirty without
a stated reason, is **void** and its numbers are not reported.

---

## 4. Result schemas (so runs are machine-comparable)

### 4.1 `metrics.json`

```json
{
  "run_id": "...",
  "arm": "T",                        // T | B0 | B1 | B2
  "n_holdout": 200,
  "primary": {
    "unlock_hit_label": 0.0,
    "wrong": 0.0,
    "abstain": 0.0
  },
  "secondary": {
    "unlock_hit_smoke": 0.0,
    "serve_rate": 0.0,
    "extract_yield": 0.0,
    "reject_rate": 0.0,
    "cluster_rate": 0.0,
    "shared_rate": 0.0,
    "cluster_purity": 0.0,
    "unlock_conflict": 0,
    "duplicate_in_packet": 0,
    "scope_leak": 0,
    "independence": "agent+dialogue",
    "votes_hist": {"1": 0, "2": 0, "3+": 0},
    "packet_size_hist": {"1": 0, "2": 0, "3": 0}
  },
  "judge": null,
  "notes": ["age-stale disabled by construction: timeline=compressed"]
}
```

`primary.unlock_hit_label + primary.wrong + primary.abstain == 1.0` exactly.
`eval.py` MUST assert that and fail loudly otherwise.

### 4.2 `per_dialogue.jsonl`

One row per hold-out dialogue — this is what makes a disagreement debuggable
instead of an argument:

```json
{
  "dialogue_id": "d-4412",
  "true_unlock_guideline": "Bad Price Competitor",
  "packet_card_ids": ["c-1a2b3c4d5e6f"],
  "packet_scores": [0.31],
  "card_labels": ["Bad Price Competitor"],
  "card_votes": [3],
  "outcome": "hit",
  "smoke_overlap_words": ["competitor"]
}
```

### 4.3 `cost.json`

```json
{
  "extract": {"calls": 1000, "prompt_tokens": 0, "completion_tokens": 0,
              "usd_total": 0.0, "usd_per_1000_dialogues": 0.0,
              "ms_p50": 0, "ms_p95": 0},
  "serve":   {"ms_p50": 0, "ms_p95": 0},
  "deterministic_half_wall_clock_s": 0,
  "price_source": "provider price list URL or the operator-stated rate, dated"
}
```

USD is computed from a **stated** price, not guessed. If the rate is unknown,
report tokens and write `usd_total: null` — never invent a number.

---

## 5. Reporting

`report.md` per run, in this order, no padding:

1. Identity: run id, stage, model, data shas, config deltas from default.
2. **Checks:** count of HARD passed/failed, every SOFT warning listed.
3. **Audit:** A1–A5 with numbers, and any threshold amended because of them.
4. **Primary table:** T vs B0 vs B1 vs B2 on `unlock_hit_label` / `wrong` /
   `abstain` / `serve_rate`.
5. Secondary metrics.
6. Judge block, with the honesty clause and the calibration agreement, or the
   word `uncalibrated`.
7. Cost.
8. **Fitness verdict** — exactly one of the three `EVAL-PLAN.md` §6.4 lines.
9. What would change the verdict: the single cheapest experiment that could
   flip it.

Cross-model comparison goes in `MODEL-MATRIX.md` at the folder root, one row per
model, built by a `compare.py` that reads `metrics.json` + `cost.json` from each
run dir. No hand-typed numbers in that table.

---

## 6. Hygiene

- JSONL only. One writer. No DB, no service, no daemon (`SPEC.md` §2).
- The card store of a run lives **inside** the run dir. Never write into
  `standalone/h1-experience-cards/data/` — that folder holds the committed input
  pack and must stay unmodified (`C-L1`).
- Commit run artifacts that are small and decisive: `manifest.json`,
  `metrics.json`, `checks.json`, `audit.json`, `cost.json`, `report.md`,
  `per_dialogue.jsonl`. Keep `raw/` and `cards.jsonl` local unless a reviewer
  asks — state their sha256 in the manifest either way.
- A run that changed prompts, thresholds or mapping mid-flight is void. Start a
  new run id and disclose the change.
