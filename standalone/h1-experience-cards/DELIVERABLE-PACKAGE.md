# H1 Experience Cards — Deliverable Package

What the lab hands back. Written for a specific consumer: **someone who did not
build this, clones the repo, and needs to re-run the experiment — including on a
model we never tried.** A hackathon participant, a reviewer, or us in a month.

This is deliverable **D8** in `LAB-BRIEF.md`. It is not documentation added at
the end: the package layout is created in D1 and filled as the run stages land.

---

## 1. What "packaged and reproducible" means here

Three claims must hold for a stranger with the repo and an API key:

| claim | proof |
|--|--|
| **I can re-run it** | one command, no code edits, no hidden state |
| **I get the same numbers as you** | `--replay` on the committed reference run reproduces `metrics.json` byte-identically, zero LLM calls |
| **I can run it on a different model** | one flag; nothing in `bin/` names a model or a provider |

If any of the three fails, the package is not done, regardless of how good the
result is.

---

## 2. Folder layout

```
standalone/h1-experience-cards/
  README.md              quickstart first, then the file map
  SPEC.md                the contract
  PROMPTS.md             frozen prompts (hashed in every manifest)
  EVAL-PLAN.md           how the result is judged
  RUN-PROTOCOL.md        how a run is executed and recorded
  CHECKS.md              per-step assertions
  LAB-BRIEF.md           the commission
  DELIVERABLE-PACKAGE.md this file
  RESULTS.md             ← the headline: reference run, numbers, verdict
  MODEL-MATRIX.md        one row per extract model + how to add a row
  data/                  committed input pack (pool, hold-out, generator)
  bin/                   the scripts + run_experiment.py
  fixtures/              SPEC §10 fixtures as JSON, used by stage S0
  runs/
    REFERENCE.md         which run id is the reference, and why
    <run_id>/            the committed reference run (§4)
```

One folder, self-contained, no imports from the rest of the repo (`C-L3`).

---

## 3. Quickstart that MUST work verbatim

`README.md` opens with this, and the lead MUST verify it in a **clean clone**
before D8 is called done — not in a working tree that already has state:

```bash
git clone https://github.com/camorazrushimoe/federated-agent-memory
cd federated-agent-memory/standalone/h1-experience-cards

export H1_API_KEY=<your key>
export H1_BASE_URL=https://api.deepseek.com/v1     # any OpenAI-compatible endpoint

# 1. reproduce our numbers without spending a token
python bin/run_experiment.py --replay runs/<reference_run_id>

# 2. smoke the wiring on fixtures + 20 dialogues (a few LLM calls)
python bin/run_experiment.py --stage S0 --model deepseek-v4-flash --out runs/my-s0

# 3. the full measured run
python bin/run_experiment.py --stage S2 --model deepseek-v4-flash --out runs/my-s2
```

Requirements: Python 3.11+, stdlib only except one HTTP client. No Docker, no
database, no service, no repo-wide install. State the exact Python version the
reference run used.

**Print the price of each command in the README**: number of LLM calls, tokens,
USD at the stated rate, and wall-clock. A stranger must know that step 3 costs
~1000 extract calls before starting it, not after.

---

## 4. The committed reference run

Exactly one run is the reference: the S2 run on `deepseek-v4-flash`. It is
committed in full **including the raw extract responses**, because those are the
replay fuel — without them `--replay` only works for the person who has the
local cache, which is nobody after a `git clone`.

Committed:

```
runs/<run_id>/
  manifest.json      identity + every sha256
  metrics.json       T, and one file per baseline arm (B0, B1, B2)
  checks.json        every CHECKS.md id, pass/fail
  audit.json         A1-A5 with numbers
  cost.json          tokens, USD, latency percentiles
  report.md          the run's own narrative + fitness verdict
  per_dialogue.jsonl one row per hold-out dialogue
  data/cards.jsonl   the card store the packets were built from
  raw/extract/*.json 1000 recorded request/response pairs   ← required for replay
  packets/*.txt      the exact text served for each hold-out dialogue
```

Size guard: if `raw/` exceeds ~25 MB, commit it as a single
`raw_extract.jsonl` (one JSON object per line, `dialogue_id` as key) instead of
1000 files, and record its sha256 in the manifest. Do not solve size by dropping
the raw responses — that breaks claim 2 in §1.

`runs/REFERENCE.md` names the reference run id in one line and states what makes
it the reference (stage, model, date, and that all HARD checks passed).

---

## 5. `RESULTS.md` — the one file a stranger reads first

Short. Numbers, not narrative. Structure:

1. **The hypothesis in one sentence**, and what would falsify it.
2. **The verdict** — exactly one of the three `EVAL-PLAN.md` §6.4 lines
   (FIT / FIT WITH LIMITS / NOT FIT), with the numbers that produced it.
3. **The primary table**, T next to every baseline:

   | arm | unlock_hit_label | wrong | abstain | serve_rate | USD/1k |
   |--|--|--|--|--|--|
   | B0 no memory | | | | | |
   | B1 raw retrieval, no cards | | | | | |
   | **T card pipeline** | | | | | |
   | B2 oracle | | | | | |

4. **What the audit found** (A1-A5), especially any threshold amended and why.
5. **Known limits**, copied honestly from `data/README.md` and the run:
   no PII to test the PII gate, single vertical, single language, `unlock` is a
   dataset label rather than a human judgement, age-stale disabled by
   construction under `timeline=compressed`, and whether the `K=2` independence
   gate actually bound anything.
6. **The judge block** with inter-pass agreement and calibration status, or the
   word `uncalibrated`.
7. **What would change the verdict** — the single cheapest next experiment.

A negative result is a complete deliverable. "Cards add nothing over B1 raw
retrieval, here are the numbers" is a finished experiment, and it is more useful
to carry into a hackathon than a tuned number nobody can reproduce.

---

## 6. Model portability — the hackathon requirement

The pipeline calls an LLM in exactly one place (`call_llm` in `extract.py`) and
everything downstream is deterministic. Keep it that way and adding a model
costs one command.

Hard requirements on `bin/`:

- Model id, base URL and API key come from **CLI flags or environment
  variables** (`--model`, `H1_BASE_URL` / `--base-url`, `H1_API_KEY`). No model
  name, endpoint or key literal anywhere in the code, not even as a default that
  silently works.
- `call_llm(system, user) -> str` is the only network surface. One place to swap.
- Any OpenAI-compatible `/chat/completions` endpoint must work without a code
  change. If a provider needs a different shape, that goes in one adapter
  function next to `call_llm`, not scattered.
- `temperature=0` and the prompt text are fixed and hashed into the manifest, so
  a model comparison cannot be contaminated by a prompt edit.
- A model that returns unparseable JSON is a **recorded result**
  (`C-EX11` rate), not a crash and not a silent retry loop. A weak model failing
  to produce valid cards is a finding about the model.

`MODEL-MATRIX.md` ends with a literal "add an arm in three steps" block:

```
1. python bin/run_experiment.py --stage S2 --model <new-model> --out runs/<date>_S2_<model>
2. python bin/compare.py runs/*/ > MODEL-MATRIX.md
3. read the new row next to B1 — if the new arm is at or below B1, the cards
   add nothing on that model, and that is the finding
```

`compare.py` builds the table from `metrics.json` + `cost.json` in each run dir.
No hand-typed numbers in `MODEL-MATRIX.md`, ever.

---

## 7. Definition of done for D8

- [ ] `runs/<reference_run_id>/` committed with everything in §4, including raw responses.
- [ ] `runs/REFERENCE.md` names it.
- [ ] `RESULTS.md` exists with the §5 structure and a verdict line.
- [ ] `MODEL-MATRIX.md` exists (one row is fine) with the three-step block.
- [ ] `README.md` opens with the §3 quickstart, **verified in a fresh clone**, with call counts, tokens, USD and wall-clock per command.
- [ ] `--replay <reference_run_id>` in that fresh clone reproduces `metrics.json` byte-identically with zero LLM calls, and the lead states the machine and Python version where they proved it.
- [ ] `grep -rn` over `bin/` finds no model name, no endpoint, no key.
- [ ] A second model can be added with the §6 three steps and no code edit — proven by running stage S0 (cheap, ~20 dialogues) against a *different* model id, and committing that S0 run as evidence of portability.
- [ ] Total size of the committed package stated in `RESULTS.md`.

The last two are the ones that make this portable rather than merely finished.
Do not tick them from reading the code — run them.
