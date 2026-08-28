# Hypothesis 1 — Experience cards (standalone)

Isolated slice. Do not import, call, or depend on anything else in this
repository: not `openspec/`, not Google Memory Bank, not the DSPy compiler,
not the M1–M3 lab code under `research/`.

Issue: [#28](https://github.com/camorazrushimoe/federated-agent-memory/issues/28)
PR: [#29](https://github.com/camorazrushimoe/federated-agent-memory/pull/29)

---

## Quickstart

Requirements: Python 3.11+ (the S0 runs used Python 3.13.5), stdlib only.
No Docker, no database, no service, no repo-wide install.

```bash
git clone https://github.com/camorazrushimoe/federated-agent-memory
cd federated-agent-memory/standalone/h1-experience-cards

export H1_API_KEY=<your key>
export H1_BASE_URL=https://api.deepseek.com/v1     # any OpenAI-compatible endpoint

# 1. reproduce our numbers without spending a token
python bin/run_experiment.py --replay runs/2026-08-28_S0_deepseek-v4-flash

# 2. smoke the wiring on fixtures + 20 dialogues (a few LLM calls)
python bin/run_experiment.py --stage S0 --model deepseek-v4-flash --out runs/my-s0

# 3. the full measured run
python bin/run_experiment.py --stage S2 --model deepseek-v4-flash --out runs/my-s2
```

**What each command costs** (measured on 2026-08-28, model `deepseek-v4-flash`,
rates from the dated sheet in `prices.json` — cache-miss, off-peak):

| command | LLM calls | tokens (in/out) | USD | wall-clock |
|--|--|--|--|--|
| 1. `--replay runs/2026-08-28_S0_deepseek-v4-flash` | **0** | 0 | $0.00 | ~30 s |
| 2. `--stage S0 --model deepseek-v4-flash` | 43 (16 pool + 27 fixture track) | 17,761 / 3,083 | **≈ $0.006** | ~65 s |
| 3. `--stage S2 --model deepseek-v4-flash` | **≈ 1000** (pool extract only) | ≈ 0.49 M / 0.06 M | **≈ $0.15** (off-peak) / $0.30 (peak) | ≈ 25–30 min |

Step 2's numbers are measured (the committed S0 run `runs/2026-08-28_S0_deepseek-v4-flash`
records every raw request/response). Step 3's are construction-known: ~1000
extract calls at the S0-measured 493 prompt + 62 completion tokens per
dialogue (p50 1.37 s/call), USD at the dated price sheet
(https://api-docs.deepseek.com/quick_start/pricing/, retrieved 2026-08-28,
flash $0.22/M input cache-miss / $0.66/M output off-peak). If your run lands
in peak hours (Mon–Fri 01:00–04:00 and 06:00–10:00 UTC) the cost roughly
doubles; `cost.json` states which window was used. `--replay` proves
reproducibility: `metrics.json` comes back byte-identical with zero LLM calls
(C-EV6).

`--model` has **no default**: a model swap is a flag, never an edit. A
different model id runs the same commands (the committed portability run
`runs/2026-08-28_S0_deepseek-v4-pro-portability` is stage S0 on a second
model id, same key, same endpoint — no code change).

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
| `fixtures/` | SPEC §10 fixture dialogues (used by stage S0's fixture track) |
| `prices.json` | dated provider price sheet (the only place a model name appears outside `bin/`) |
| `bin/` | the scripts + `run_experiment.py`; no model/endpoint/key literal anywhere in it (D8) |
| `runs/` | run dirs: `REFERENCE.md` names the reference run (D8); S0 runs committed as wiring + portability evidence |
| `RESULTS.md`, `MODEL-MATRIX.md` | the headline numbers and the per-model table — skeletons until the measured runs land; numbers are generated, never hand-typed |

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

Layer names matter here: the per-step checks are **contract tests**, the metrics
against `unlock_guideline` are **offline eval**, the judge over card quality is
**auto-eval**, and the go/no-go at the end is **fitness for purpose**. They fail
differently, so they are reported separately.
