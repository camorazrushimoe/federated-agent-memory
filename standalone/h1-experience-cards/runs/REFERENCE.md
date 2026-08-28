# runs/REFERENCE.md — which run is the reference, and why

_(Filled at D8. Skeleton created in D1 so the runs/ layout exists.)_

**Reference run id:** `TBD` — the stage-S2 run on `deepseek-v4-flash` over the
full 1000-dialogue pool + 200-dialogue frozen hold-out.

Why it is the reference:

- stage: **S2** (the full measured run; S0/S1 are wiring and dev only)
- model: `deepseek-v4-flash` (the founder-decided extract model, pass 1)
- date: <run date, UTC>
- checks: **all HARD checks in `checks.json` green**
- replay fuel: `raw/` extract responses (or `raw_extract.jsonl` + sha256 if
  collapsed) are committed in this run dir — that is what makes `--replay`
  work for someone who just cloned the repo
- `--replay <run_id>` reproduces `metrics.json` byte-identically with zero
  LLM calls (proved on <machine>, Python <version>)
