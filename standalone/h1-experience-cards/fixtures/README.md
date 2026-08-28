# H1 fixtures — SPEC §10 scenarios, runnable with zero LLM calls

Everything the S0 gate and the check harness need, committed so a fresh clone
can run the fixture suite without a live API key.

## Files

| file | what it tests |
|--|--|
| `build_fixtures.py` | deterministic generator for all `*.jsonl` below |
| `bake_fixtures.py` | one real LLM call per extracted dialogue; writes `raw/extract/*.json` |
| `raw/extract/*.json` | baked request/response pairs from the pinned extract model — the replay fuel for the fixture suite |
| `d001.jsonl` | SPEC §10.1 worked example (C-EX6) |
| `ten_dupes_2agents.jsonl` | SPEC §10.2: ten near-dupes, agents a/b (C-CL10) |
| `ten_dupes_1agent.jsonl` | SPEC §10.3: the same ten, all agent-a (C-CL10) |
| `live_d011.jsonl` | same-scope live query (serve must return one card) |
| `live_d012.jsonl` | vertical=billing (cross-vertical serve must be empty) |
| `live_d013.jsonl` | agent-c, same story (anti-echo, C-PR3) |
| `gift_card.jsonl` | bare word "card" must not set contains_pii (C-EX7) |
| `freshness_new_member.jsonl` | canonical 40d old + member closed yesterday -> not stale (C-CL6) |
| `freshness_quiet.jsonl` | single card quiet 35d -> stale (C-CL6) |
| `two_clusters.jsonl` | two stories x two agents -> 2 shared canonicals (C-FB4) |
| `live_two_clusters.jsonl` | bridges both stories -> multi-card packet (C-FB4) |

## Pinned staleness clock

The suite passes `--now 2026-08-28T00:00:00Z` (FIXTURE_NOW in `bin/checks.py`)
so the freshness cases are exact: 40 days, 35 days and 1 day before that clock.

## Re-baking

```bash
export H1_API_KEY=<key> H1_MODEL=<model> H1_BASE_URL=<url>
python fixtures/build_fixtures.py     # regenerate the dialogue files
python fixtures/bake_fixtures.py      # re-run extraction, rewrite raw/extract
```

Any change to `PROMPTS.md` or the fixture dialogues invalidates the baked
responses — re-bake and commit the new files together.
