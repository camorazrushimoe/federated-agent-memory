# H1 Experience Cards — Task Brief for lab-1

Hand-off document. Read `SPEC.md`, `EVAL-PLAN.md`, `RUN-PROTOCOL.md`,
`CHECKS.md` in that order before writing a line of code. Everything you need is
in this folder; the input data is already committed under `data/`.

**Commission:** build the runnable experiment for Hypothesis 1 (experience
cards), then measure it and answer one question: **is this worth using?**

**What you are NOT doing:** research on new ideas, new datasets, new metrics of
your own invention, embeddings, databases, services, or anything outside
`standalone/h1-experience-cards/`.

---

## 1. Roles

| role | owns |
|--|--|
| **Research Engineer** | the seven scripts in `bin/`, the runner, the harness, the runs |
| **Research Lead** | review by **re-execution** (never by reading), the audit numbers, the fitness verdict, the report |
| **Evaluation** | Layer 3 only: the judge passes, their agreement, the calibration sample |

Rule that does not bend: **the person who wrote a thing does not approve it.**
Lead reviews the engineer's code by re-running it in a clean worktree and
comparing shas. Engineer reviews the lead's verdict against `per_dialogue.jsonl`.

---

## 2. Deliverables, in order

| # | deliverable | gate to move on |
|--|--|--|
| **D1** | `bin/` scripts per `SPEC.md` §6 (`tick`, `ingest`, `extract`, `cluster`, `match`, `promote`, `serve`, `feedback`, `eval`) + `bin/run_experiment.py` | `SPEC.md` §9 definition-of-done checklist fully ticked, one PR |
| **D2** | The check harness: every id in `CHECKS.md` implemented, HARD failures abort the run | S0 stage green on the §10 fixtures + 20 dialogues, `checks.json` complete |
| **D3** | `audit.json` — the floor/ceiling audit A1–A5 (`EVAL-PLAN.md` §7) on the pool | every threshold in §6.2 confirmed reachable, **or** amended in `EVAL-PLAN.md` with the number that forced it, before any S2 run |
| **D4** | Baselines B0/B1/B2 in the same scoring path as T | `C-EV3`, `C-EV4`, `C-EV5` green |
| **D5** | S2 measured run per model, one run dir each | `metrics.json`, `cost.json`, `per_dialogue.jsonl`, `report.md` per run |
| **D6** | Judge pass (L3) + calibration on the 30 founder-labelled cards | agreement reported; `uncalibrated` stated if the founder sample is not in yet |
| **D7** | `MODEL-MATRIX.md` built by `compare.py` from the run dirs — no hand-typed numbers | one fitness verdict per model in exactly one of the three `EVAL-PLAN.md` §6.4 forms |

**D3 is a hard gate, not paperwork.** We already burned a full round on a
pre-registered criterion whose arithmetic floor made it unreachable (`≤ 0.1`
against a floor of `0.1199`, 61/80 cases impossible by construction). Compute
the ceiling before you measure against it. If A4 shows the within-label card
cosine median sits below `CLUSTER_THRESHOLD = 0.35`, then nothing will ever
cluster, nothing will ever be `shared`, and the honest output is that finding
plus a threshold re-derived from the measured distribution — not a tuned knob
and not a rerun until it looks better.

---

## 3. Model matrix

The pipeline touches an LLM in exactly one place: `call_llm` inside
`extract.py`. Everything else is deterministic. So a difference between models
is a difference in extraction quality with nothing else confounding it — keep it
that way (same data, same seeds, same prompts, same thresholds, one run dir per
model).

| slot | model | status |
|--|--|--|
| `cheap` | **the founder will name it** — do not pick one yourself | awaiting founder |
| `mid` | `deepseek-v4-flash` (factory default since 2026-08-28) | ready |
| `strong` | **the founder may name one** as a ceiling reference | awaiting founder |
| `judge` | must differ from the extract model of the run it judges | assign per run |

Start D1–D4 now with `mid`. Do not wait for the model list — the harness is
model-agnostic by construction, and `--model` is a flag.

---

## 4. How to run and report

- One command, one run dir, one manifest (`RUN-PROTOCOL.md` §1, §3).
- Stages: **S0 smoke** (fixtures + 20) → **S1 dev** (200 pool + 40 from the
  pool tail) → **S2 full** (1000 pool + 200 hold-out, per model) → **S3 judge**
  → **S4 verdict**. Never skip a stage to save time; S0 exists so that a wiring
  bug does not cost 1000 LLM calls.
- **The hold-out is frozen.** It is opened once per model, at S2. Iterate on the
  pool's tail. Accidental exposure voids the run — report the run as void rather
  than quietly reusing it.
- Every run publishes: `manifest.json`, `checks.json`, `metrics.json`,
  `cost.json`, `audit.json` (S1+), `per_dialogue.jsonl`, `report.md`.
- Commit those. Keep `raw/` local; record its shas in the manifest.

Report format on the GitHub issue thread, per round, no prose padding:

```
ROUND n/4 · FROM: <role>
DELIVERABLE: D<k> — <one line>
ARTIFACT: <PR # or commit sha or run_id>
NUMBERS: <only measured ones, with n>
CHECKS: <hard passed>/<hard total>, soft warnings: <n>
BLOCKED: <what, or "nothing">
NEXT: <the single next action>
```

---

## 5. Budget and stop conditions

- **4 rounds maximum** for D1–D4, then a review checkpoint with the founder.
- Every round MUST end in a committed artifact: a commit, a PR, a run dir, or a
  review comment with numbers. A round that ends in discussion is a failed round.
- **No self-merge.** No merging at all without the founder's approval on this
  commission.
- One branch per deliverable, opened by that deliverable's owner. Do not open
  three parallel PRs for one task — we have already paid for that mistake.
- If two of you disagree, report **both positions with their numbers**. Do not
  average them, do not let the lead's seniority settle a measurable question.

Stop and escalate to the founder immediately if:

- an audit item (A1–A5) shows a pre-registered threshold is unreachable;
- a HARD check cannot be made to pass without changing `SPEC.md`;
- the LLM provider fails or rate-limits in a way that makes a run
  non-reproducible (note: the factory moved to `deepseek-v4-flash` on
  `api.deepseek.com` on 2026-08-28 — the old provider's 429s are gone, so a
  429 now is news);
- you are about to spend more than one round on infrastructure archaeology
  rather than the experiment. That is the founder's call, not yours.

---

## 6. Honesty rules

These are not style preferences. They are the difference between a result and a
story.

- A metric without its baseline is not reported. `T` alone means nothing; `T` vs
  `B1` means something.
- A judge number without its inter-pass agreement and its calibration status is
  not reported.
- Every claim carries the artifact that proves it: a run id, a sha, a file path.
- `wrong` (a confident irrelevant precedent handed to an agent) is reported
  **above** misses. Do not bury it in an aggregate.
- A missed threshold is a finding. Publish it. Do not negotiate the bar
  downward after seeing the number — amend a threshold only in D3, only before
  measuring, and only with the arithmetic that forced it.
- If the answer is "cards add nothing over plain retrieval", that is a complete
  and valuable result. Say it in one line and stop.
