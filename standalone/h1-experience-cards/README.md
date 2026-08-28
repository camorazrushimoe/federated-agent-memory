# Hypothesis 1 — Experience cards (standalone)

Isolated slice. Do not import, call, or depend on anything else in this
repository: not `openspec/`, not Google Memory Bank, not the DSPy compiler,
not the M1–M3 lab code under `research/`.

Issue: [#28](https://github.com/camorazrushimoe/federated-agent-memory/issues/28)
PR: [#29](https://github.com/camorazrushimoe/federated-agent-memory/pull/29)

## What you implement

A handful of scripts that turn finished customer chats into short cards,
merge the ones that are the same story, and — when a later chat looks the
same — hand the next agent a **recommendation packet**, never a rule.

```
chat closed
    → tick.py               ingest + extract + (cluster if 100 new chats)
    → extract               private canonical, votes = 1
    → cluster               same-scope cards collapse; inherit better fields
    →                       votes ≥ K and independent agents → shared
    → live chat             match+serve top-3 shared canonical cards
    → feedback              wrong/stale expires the canonical card
```

Clustering is a **volume trigger**, not a timer. `tick.py` is the only entry
point an operator needs. `--force` exists for fixtures.

## Files

| file | role |
|--|--|
| `SPEC.md` | contract: data, states, scripts, clustering, eval |
| `PROMPTS.md` | frozen prompts: extract, serve, feedback-label |
| `EVAL-PLAN.md` | how the result is judged: four layers, metrics, baselines, floor/ceiling audit, fitness-for-purpose rubric, model matrix |
| `RUN-PROTOCOL.md` | how a run is executed and recorded: data mapping, run dir, manifest + metrics schemas, replay mode |
| `CHECKS.md` | per-step contract assertions with ids, HARD/SOFT, plus negative controls |
| `LAB-BRIEF.md` | the hand-off: roles, deliverables D1–D7, round budget, reporting format, honesty rules |
| `DELIVERABLE-PACKAGE.md` | what "packaged and reproducible" means: folder layout, quickstart, the committed reference run, model portability (D8) |
| `data/` | committed input pack: 1000-dialogue pool + 200-dialogue frozen hold-out, with ground-truth `unlock_guideline` |
| `fixtures/` | added when scripts land |
| `RESULTS.md`, `MODEL-MATRIX.md`, `runs/` | added when the experiment runs: the headline numbers, the per-model table, the committed reference run |

## Order of work

1. Read `SPEC.md` + `PROMPTS.md`. Do not invent extra fields.
2. Read `EVAL-PLAN.md`, then `RUN-PROTOCOL.md`, then `CHECKS.md`. The plan is
   written **before** the code on purpose: a step whose success condition is not
   defined yet cannot be implemented honestly.
3. Implement the script list in `SPEC.md` §6 plus `bin/run_experiment.py`.
4. Stage S0 on the `SPEC.md` §10 fixtures — every HARD check in `CHECKS.md` green.
5. Run the floor/ceiling audit (`EVAL-PLAN.md` §7) **before** measuring against
   any threshold.
6. Stage S1 → S2 per model, then the judge pass, then the fitness verdict.

No service, no database, no vector DB. JSONL on disk is enough for this hypothesis.

## Quickstart

Requirements: Python 3.11+ (stdlib only + the OS HTTP client — no pip
install), an API key for any OpenAI-compatible endpoint.

```bash
git clone https://github.com/camorazrushimoe/federated-agent-memory
cd federated-agent-memory/standalone/h1-experience-cards

export H1_API_KEY=<your key>
export H1_BASE_URL=https://api.deepseek.com/v1     # any OpenAI-compatible endpoint

# 1. reproduce our numbers without spending a token
python bin/run_experiment.py --replay runs/<reference_run_id>

# 2. smoke the wiring on fixtures + 20 dialogues (a few LLM calls)
python bin/run_experiment.py --stage S0 --model deepseek-v4-flash --out runs/my-s0

# 3. the full measured run (~1000 extract calls)
python bin/run_experiment.py --stage S2 --model deepseek-v4-flash --out runs/my-s2
```

**Cost of each command (measured on the reference run — filled at D8 when the
reference S2 run is committed; no number is hand-typed):**

| command | LLM calls | prompt tokens | completion tokens | USD | wall-clock |
|--|--|--|--|--|--|
| `--replay <reference_run_id>` | 0 | 0 | 0 | $0.00 | <measured at D8> |
| `--stage S0 --model deepseek-v4-flash` | <measured at D8> | <measured at D8> | <measured at D8> | <measured or N/A> | <measured at D8> |
| `--stage S2 --model deepseek-v4-flash` | ~1000 | <measured at D8> | <measured at D8> | <measured or N/A> | <measured at D8> |

USD is null if no published price exists for the model (recorded, never
guessed). The full run costs ~1000 extract calls before you start — the S0
smoke exists exactly so a wiring bug never costs you that.

Layer names matter here: the per-step checks are **contract tests**, the metrics
against `unlock_guideline` are **offline eval**, the judge over card quality is
**auto-eval**, and the go/no-go at the end is **fitness for purpose**. They fail
differently, so they are reported separately.
