# H1 Experience Cards — Evaluation Plan

**Status:** proposal for the lab. Nothing here is measured yet.
**Companion to:** `SPEC.md` (implementation contract), `RUN-PROTOCOL.md` (how a
run is executed and recorded), `CHECKS.md` (per-step contract assertions),
`LAB-BRIEF.md` (the task hand-off).

This document answers one question: **how do we know whether the experience-card
pipeline works, step by step, and whether it is worth using at all.**

---

## 0. Four layers, four different things

The word "eval" gets used for all four. They are not the same and they fail
differently. Build them in this order.

| Layer | Question it answers | Name | Verdict shape |
|--|--|--|--|
| **L0** | Is the run reproducible? | reproducibility harness | byte-identical re-run |
| **L1** | Does each step obey its contract? | contract / golden checks | pass / fail per assertion |
| **L2** | Is the output any good against ground truth? | offline evaluation | metrics + baselines |
| **L3** | Is it good where no label exists? | LLM-as-judge (**auto-eval**) | scores + agreement floor |
| **L4** | Should we use this? | **fitness for purpose** | go / no-go rubric |

Two rules that decide whether the whole exercise is honest:

1. **L1 is not quality.** A green L1 means the wiring is correct, nothing more.
   Never report L1 as evidence that cards help.
2. **L2 without baselines is not a result.** A number like `unlock_hit = 0.42`
   means nothing until B0/B1/oracle are measured on the same hold-out (§4).

---

## 1. What is measured, and on what data

- Data pack: `standalone/h1-experience-cards/data/` (already on `main`).
  - `abcd_1000_pool.jsonl` — 1000 dialogues, the **pool** (ingest → extract → cluster).
  - `abcd_200_holdout.jsonl` — 200 dialogues, the **hold-out** (serve → score).
  - Provenance, schema and limits: `data/README.md`.
- Ground truth: `unlock_guideline` (55-value ontology) on every row.
- **Leakage rule (hard):** `unlock`, `unlock_guideline` and `split` MUST be
  stripped from the dialogue records before `extract.py` sees them. They exist
  only inside `eval.py`. Enforced by check `C-L2` in `CHECKS.md`.

The pack is not the spec's dialogue schema; the mapping (and the two fields the
pack does not have) is defined in `RUN-PROTOCOL.md` §2. Read it before coding —
one of those gaps silently disables the `K_INDEPENDENT` gate.

---

## 2. L0 — reproducibility harness

Non-negotiable, because every later number is meaningless without it.

- One command per run, one output directory, one `manifest.json` (§`RUN-PROTOCOL.md` §3).
- Deterministic steps (`ingest`, `match`, `cluster`, `promote`, `serve`) MUST be
  **byte-identical** across re-runs on the same inputs.
- The one non-deterministic step is `extract` (LLM). Pin it as far as it goes:
  `temperature=0`, fixed prompt text, fixed model id, and **record the raw
  request/response for every dialogue** in `raw/extract/<dialogue_id>.json`.
- `manifest.json` records the sha256 of: input files, prompt file, config object,
  and each produced artifact. A run with a missing sha is void.
- **Replay mode is required:** `--replay <run_id>` re-runs the whole pipeline
  from recorded extract responses, with zero LLM calls. That is how the
  deterministic half gets tested without burning tokens, and how a reviewer
  re-derives your metrics.

---

## 3. L1 — per-step contract checks

Full assertion list with ids in `CHECKS.md`. Shape of the thing:

- Every check is a boolean on files that already exist on disk.
- Every check is either **HARD** (a violation aborts the run and the run is
  reported as failed — no metrics are published from it) or **SOFT** (recorded
  as a warning and carried into the report).
- `checks.json` in the run dir holds `{check_id, step, hard, passed, observed, expected}`.
- The four HARD invariants that must never be waived, because they are the
  safety story of the whole design:
  - `scope_leak == 0` — no packet ever contains a card from another scope.
  - `duplicate_in_packet == 0` — never two cards of one cluster in one packet.
  - **anti-echo** — a served dialogue never becomes a vote for the card it saw.
  - **no PII in card fields** after the scrub, on the §10.1 fixture and on a
    scan of the whole card store.

Grounding check worth calling out (`C-EX4`): every non-empty `unlock`,
`constraint` and `problem_shape` must be **traceable to the source transcript**
— at least one content word (≥5 chars) of each field must appear in the
dialogue text. This catches invention without needing a judge, and it is the
cheapest hallucination detector we have.

---

## 4. L2 — offline evaluation against ground truth

### 4.1 The one primary metric

`unlock_hit_label` on the hold-out, scored against `unlock_guideline`:

> For hold-out dialogue *d*, build a packet from the pool store. The packet
> **hits** iff at least one served canonical card carries the same
> `unlock_guideline` as *d*.

A card's label = the majority `unlock_guideline` of the dialogues in its
cluster (canonical + members), ties broken by the canonical's own dialogue.
Labels are attached in `eval.py` only, never inside a card.

The spec's own `unlock_hit` (word overlap ≥5 chars) stays as a **smoke signal
only**, reported under its own name `unlock_hit_smoke`. Do not mix the two.

### 4.2 Outcome classes (every hold-out dialogue lands in exactly one)

| class | condition | why it matters |
|--|--|--|
| `hit` | packet non-empty, ≥1 card label == d's label | the win |
| `wrong` | packet non-empty, **no** card label == d's label | **the harm** — the agent was handed a confident irrelevant precedent |
| `abstain` | packet empty | safe: no memory, no harm |

Report all three. `hit + wrong + abstain = 1.0`. **`wrong` is weighted above
misses in the fitness rubric** (§6): a system that stays quiet when unsure is
better than one that guesses.

### 4.3 Baselines — mandatory, same hold-out, same scoring code

| id | what it does | what it proves |
|--|--|--|
| **B0** | no memory: packet always empty | floor; also proves the metric cannot fire on nothing |
| **B1** | **no cards**: TF-IDF over raw customer text of pool dialogues, in-scope, threshold 0.18, return top-1 dialogue's label as the packet claim | **the only baseline that matters** — does the card add anything over plain retrieval of the raw past chat? |
| **B2** | oracle: serve d's true `unlock_guideline` | ceiling; if B2 < 1.0 the scoring code is broken, not the pipeline |
| **T** | the card pipeline | the treatment |

Pre-registered interpretation, written before the run:

- **T ≤ B1** → cards add nothing over raw retrieval. That is a finding, and the
  honest conclusion is "extraction is not where the value is". Do not fix it by
  loosening thresholds.
- **T > B1** → report the delta with the cost difference (extraction costs LLM
  calls, B1 costs none).
- **B2 < 0.98** → stop, fix the metric, discard the run's L2 numbers.

### 4.4 Supporting metrics (from `SPEC.md` §6.8, kept as-is)

`extract_yield`, `reject_rate`, `cluster_rate`, `shared_rate`, `serve_rate`,
`unlock_conflict`, `independence`, plus:

- `packet_size_hist` — 1/2/3 cards per served packet.
- `cluster_purity` — fraction of clusters whose member dialogues all share one
  `unlock_guideline`. This is the direct measurement of the false-friend
  chaining the spec warns about in §5.
- `votes_hist` — distribution of `votes` at promotion time.

---

## 5. L3 — auto-eval (LLM-as-judge), only where labels do not exist

Labels tell us whether the packet named the right unlock. They do **not** tell
us whether the card is *useful, faithful and readable*. That is what the judge
is for, and nothing else.

Judge scope: a random sample of 60 cards (stratified over tenants), three
binary questions per card, fixed rubric, `temperature=0`:

1. **faithful** — is every claim in the card supported by the source transcript?
2. **actionable** — would this card let another agent act without re-reading the chat?
3. **scoped** — is it free of customer identity and of one-off specifics?

Protocol, taken straight from the lab's own hard lesson on M2:

- Two independent passes; report **inter-pass agreement as a self-consistency
  floor**, never as human agreement.
- Judge model MUST differ from the extract model in the same run, and this MUST
  be stated in `metrics.json` (`judge_model`, `extract_model`).
- **Calibration is required, not optional:** 30 of the 60 cards get labelled by
  the founder (or by whoever owns the decision). Report judge-vs-human agreement
  on those 30. If agreement < 0.7, the judge numbers are reported as
  **uncalibrated** and carry no weight in §6.
- Honesty clause on every judge number: *agent-drafted, agent-judged; this is a
  self-consistency floor, not human inter-rater agreement.*

---

## 6. L4 — fitness for purpose

Not a metric. A rubric, evaluated once per model, after L1–L3 are in.

### 6.1 Hard gates (any failure = NOT FIT, regardless of accuracy)

| gate | threshold |
|--|--|
| `scope_leak` | `== 0` |
| `duplicate_in_packet` | `== 0` |
| anti-echo (`C-PR3`) | holds |
| PII in card fields | none found in the full store scan |
| deterministic replay | byte-identical on `--replay` |
| `B2` oracle | `≥ 0.98` (metric sanity) |

### 6.2 Value gates

| gate | threshold | rationale |
|--|--|--|
| `unlock_hit_label` (T) | **> B1 by a margin the run reports with its own n** | cards must beat plain retrieval |
| `wrong` rate | `≤ 0.10` | a confident wrong precedent is the real damage |
| `serve_rate` | `≥ 0.30` | below this the system is silent and cannot pay for itself |
| `cluster_purity` | `≥ 0.70` | mixed clusters mean the card lies about its own support |
| judge `faithful` | `≥ 0.90` (calibrated) | an unfaithful card is worse than none |

### 6.3 Cost gates

| gate | what to record |
|--|--|
| extract cost | tokens in/out and **USD per 1000 dialogues** |
| extract latency | p50 / p95 per dialogue |
| serve latency | p50 / p95 (must be usable inline in a live chat) |
| non-LLM cost | wall-clock of the deterministic half on 1000 dialogues |

### 6.4 Verdict, written as one of exactly three lines

- **FIT** — all hard gates pass, all value gates pass, cost recorded and acceptable.
- **FIT WITH LIMITS** — hard gates pass, one or more value gates miss; name
  each miss, its number, and the smallest change that would plausibly fix it.
- **NOT FIT** — any hard gate fails, or T ≤ B1. State which, with the number.

**Thresholds in §6.2 are provisional and must survive §7 before the full run.**
If the audit shows a threshold is unreachable by construction, it is amended
*before* any measurement, in this file, with the reason. Amending a threshold
after seeing the result is forbidden.

---

## 7. Floor / ceiling audit — do this BEFORE the full run

This section exists because of a real failure we already paid for: a
pre-registered criterion of `≤ 0.1` against a metric whose arithmetic floor was
`0.1199` — 61 of 80 cases could not pass no matter how good the work was, and a
whole round was spent measuring against an impossible bar.

For each item: compute it on the pool, record it in `audit.json`, and apply the
contingency if it fires. Cheap — all five are minutes of arithmetic on data we
already have.

| id | question | contingency if it fires |
|--|--|--|
| **A1** | What fraction of hold-out dialogues have **any** in-scope pool dialogue with customer-text cosine ≥ `MATCH_THRESHOLD` (0.18)? That is the ceiling on `serve_rate`. | If < 0.30, the `serve_rate` gate is unreachable: report the ceiling, and either widen scope (tenant → vertical) or lower the gate — **before** the run, with the number written down. |
| **A2** | Does the oracle B2 score 1.0 with the scoring code as written? | If not, the metric is broken. Fix the metric first. |
| **A3** | Does `K_INDEPENDENT = 2` ever **bind**? With `agent_id` absent, independence degrades to `dialogue-only` (SPEC §5.1) and any two similar dialogues promote a card — the anti-echo/independence story is not being tested at all. | Synthesize `agent_id` deterministically (`RUN-PROTOCOL.md` §2.2) and report the fraction of clusters blocked by the gate. If the gate blocks nothing, say so — an untested gate is not a passed gate. |
| **A4** | Distribution of card-to-card cosine **within** one `unlock_guideline` vs **across** two, on ~50 extracted cards. Is the within-label median above `CLUSTER_THRESHOLD` (0.35)? | If the within-label median is below 0.35, clustering will essentially never fire, `votes` stays 1, nothing is ever `shared`, and the pipeline's whole promote path is dead on this data. Report it as the finding and re-derive the threshold from the measured distribution (documented, once, in this file). |
| **A5** | Can the staleness rule fire at all? The pack has no `closed_at`. | Use the two timelines in `RUN-PROTOCOL.md` §2.3: `compressed` for the main run (age-stale off by construction, stated), `aged` only for the staleness contract test. |

`CLUSTER_EVERY_N_CHATS = 100` with a 1000-dialogue pool means exactly 10
cluster passes. Note the count in the report; do not switch to per-scope
counting silently (SPEC §5).

---

## 8. Model matrix

The pipeline touches an LLM in exactly one place — `call_llm` inside
`extract.py`. Everything downstream is deterministic. That is a gift: **any
difference between models is a difference in extraction quality**, with nothing
else to confound it.

Run the identical protocol per model, same data, same seeds, same prompts, same
thresholds. One run dir per model.

| slot | model | role in the comparison | status |
|--|--|--|--|
| `extract` | **`deepseek-v4-flash`** | the measured arm — founder decision, 2026-08-28 | **decided, pass 1** |
| `judge` | **`deepseek-v4-pro`** | L3 only; differs from the extract model as §5 requires, same API key | **decided** |
| `cheap` | _not assigned_ | can a smaller model carry extraction? | deferred |
| `strong` | _not assigned_ | how much is left on the table? | deferred |

**Pass 1 is single-arm.** Extraction runs on `deepseek-v4-flash` only, so
`MODEL-MATRIX.md` is a one-row table and D7 in `LAB-BRIEF.md` collapses to that
single row. Do **not** invent a second model to fill the matrix — the comparison
opens only when the founder names one, and the harness already takes `--model`,
so adding an arm later costs one run and no code.

Deliverable: `MODEL-MATRIX.md`, one row per extract model, columns =
`unlock_hit_label`, `wrong`, `abstain`, `serve_rate`, `cluster_purity`,
`reject_rate`, judge `faithful`, USD/1000 dialogues, p50 latency, verdict.

With one arm, that table is still worth writing: it is the record a second arm
is later compared against, and building it now means the comparison costs
nothing but a run. When a second model arrives, the question is deliberately
**not** "which model wins" but:

> Does the cheap model lose enough quality to matter, given that it is the only
> component that costs money per dialogue?

If `cheap` and `mid` land inside each other's noise, the honest conclusion is
"extraction is not model-bound on this task" — which is a finding about the
design, worth more than a leaderboard.

---

## 9. Staged execution

Never run 1000 dialogues to discover a wiring bug.

| stage | data | purpose | gate to advance |
|--|--|--|--|
| **S0 smoke** | the `SPEC.md` §10 fixtures + 20 pool dialogues | wiring, all HARD checks, replay works | every HARD check green |
| **S1 dev** | 200 pool dialogues + 40 hold-out (from the pool's own tail — **not** the real hold-out) | tune nothing, verify metrics compute and audit A1–A5 | `audit.json` complete, all thresholds confirmed reachable or amended |
| **S2 full** | 1000 pool + 200 hold-out | the measured run, per model | one full run dir per model, `checks.json` green |
| **S3 judge** | 60 cards from the S2 run of each model | L3 + calibration | 30 founder-labelled cards in |
| **S4 verdict** | all of the above | `MODEL-MATRIX.md` + fitness verdict per model | one of the three §6.4 lines, per model |

**The real hold-out is frozen.** It is opened exactly once per model, at S2.
Iteration happens on a tail slice of the pool. Any accidental hold-out
exposure voids the run and it is reported as void.

---

## 10. Definition of done for the eval work

- [ ] `bin/eval.py` computes every metric in §4 and writes `metrics.json` to the schema in `RUN-PROTOCOL.md` §4.
- [ ] Baselines B0, B1, B2 implemented in the **same** scoring path as T (no second copy of the metric).
- [ ] `checks.json` covers every id in `CHECKS.md`, with HARD failures aborting the run.
- [ ] `audit.json` answers A1–A5 with numbers, before S2 is run.
- [ ] `--replay` reproduces a run's metrics byte-identically with zero LLM calls.
- [ ] One run dir per model, plus `MODEL-MATRIX.md`.
- [ ] A fitness verdict per model in exactly one of the three §6.4 forms.
- [ ] Every threshold amendment (if any) recorded in this file with its reason and the number that forced it.

## 11. Out of scope for this experiment

- No embeddings, anywhere (SPEC §7).
- No database, no service, no API: JSONL files in the folder, one writer.
- No touching `research/`, `openspec/`, Memory Bank, or any other package.
- No cross-tenant experiments: this data cannot test leakage, only prove we
  never leak within it.
- No prompt tuning between S2 runs. Prompts are frozen at S0 and hashed in the
  manifest; a prompt change starts a new run id and is disclosed.
