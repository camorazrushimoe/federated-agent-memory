# M2 sample (R2) — construction notes + re-run contract

**Deliverable:** `research/phase2/m2/sample.jsonl` (80 convos) +
`sample.jsonl.meta.json` (deterministic run record) + `sample.py` (generator)
+ `validate_sample.py` (independent re-derivation gate). Extract phase
(R2 downstream, §6): `candidates.jsonl` + `candidates.jsonl.meta.json` +
`extract.py` + `validate_candidates.py` + judge-harness plumbing
(`stage_blind_pass.py` / `stage_scoring_pass.py`, committed bind layers
under `judge/`).
**Pre-registered spec:** GH #6 comment `5449115746` §3 (frozen before the draw).
**Ticket:** BON-42 (M2) under BON-39 · **Hypothesis served:** the M2 unit
question — *does a structured experience record preserve ≥ 80% of the
transcript's rubric value at ≤ 1/10 of its tokens?* (frozen D18 bar; this
artifact is the input to that test, not the test itself).

## 0. The one deviation — read first

The frozen spec pairs **8 convos/flow** with **≤ 2 convos/subflow**. On this
corpus `account_access` has exactly **3 subflows** (recover_username /
recover_password / reset_2fa — see the ontology; the flow is 1,048 convos),
so cap 2 admits at most **6 < 8** convos: the two frozen constraints are
**jointly infeasible** for that flow (and only that flow — every other flow
has ≥ 4 subflows).

Applied minimal relaxation, **flagged, not silent**: per-subflow cap =
`ceil(8 / n_sub)` **only** for flows with `< 4` available subflows
(account_access → 3); all 9 other flows keep the frozen cap 2.
Every other frozen constraint is satisfied exactly (N = 80, 8/flow, seed 42
fresh RNG, R1-318 exclusion, empty-product window 20–32).
`validate_sample.py` checks G2/G3 that the deviation fires **only** where the
infeasibility actually holds. **Lead adjudication requested on the sample PR**
(accept-as-documented or direct a different fix-forward, e.g. 6/aa + 2
top-up elsewhere — the latter would break "8/flow × 10 flows" instead).

## 1. Re-run contract

```bash
# generator (deterministic, byte-identical; stdlib only)
python3 research/phase2/m2/sample.py \
    --corpus data/abcd/abcd_v1.1.json \
    --pairs research/phase2/m1/candidate_pairs.jsonl \
    --out research/phase2/m2/sample.jsonl

# independent verification gate (re-implements the draw without importing sample.py;
# re-derives the 80-convo set, re-checks every frozen invariant, re-computes
# n_action_turns / n_tokens_b0 from the raw corpus; exits non-zero on any failure)
python3 research/phase2/m2/validate_sample.py \
    --corpus data/abcd/abcd_v1.1.json \
    --pairs research/phase2/m1/candidate_pairs.jsonl \
    --sample research/phase2/m2/sample.jsonl
```

**Pinned inputs (checked by both scripts before any draw):**
- corpus `data/abcd/abcd_v1.1.json` sha256:16 **`005d425e890b30a1`** (10,042 convos)
- R1 pair file `research/phase2/m1/candidate_pairs.jsonl` sha256:16 **`42215fc5969e600e`**
  → excluded set = **318** unique convos (re-derived from the file, not trusted)

**Pinned output:** `sample.jsonl` sha256:16 **`f2195e7a6abe2221`**
(verified byte-identical across consecutive runs on 2026-08-28).

## 2. Frozen draw procedure (as implemented; validator re-implements independently)

1. Universe = all 10,042 convos **sorted by `convo_id` (int)**.
2. Excluded = `{int(conv_a), int(conv_b)}` over the pinned R1 pair file.
   (The pair file stores ids as **strings**; the corpus uses **ints** — the
   sampler/validator int-cast; the raw string set intersects the corpus at 0.)
3. Fresh `random.Random(42)`. For `f` in **sorted** flows, `s` in **sorted**
   available subflows: pre-shuffle the (f, s) pool (pre-sorted by convo_id).
   This sorted-order shuffle sequence is the frozen RNG consumption order.
4. Selection, per flow in sorted order: **round-robin** over the flow's
   available subflows (alphabetical), at most one pick per subflow per round,
   cycling until 8 are drawn.
5. Per-subflow cap per §0 (2, or `ceil(8/n_sub)` where infeasible).

Determinism: no timestamps, no unsorted dict iteration, JSON rows written in
convo_id-sorted order with fixed separators; `meta.json` likewise.

## 3. Row schema (frozen 8 fields, exact order)

| field | definition |
|---|---|
| `convo_id` | corpus int id |
| `flow`, `subflow` | `scenario.flow` / `scenario.subflow` (re-verified vs corpus by validator J1) |
| `product_names` | `scenario.product.names` (empty list = the no-product-context slice) |
| `n_action_turns` | count of `delexed` turns with `speaker == "action"` (D11) |
| `n_tokens_b0` | **frozen token counter**: whitespace-split tokens of the B0 render — all `original` turns as `"speaker: text"`, space-joined |
| `seed` | 42 |
| `in_exclusion_set` | true iff id ∈ R1 318-convo set — **false on every sampled row** (validator F1/F2 re-checks both the set and the flags) |

## 4. Verification evidence (2026-08-28, pre-handoff)

`validate_sample.py` self-run: **VERDICT: PASS — 20/20 checks**, including the
independent re-derivation (B): re-derived 80-convo set is **identical** to the
committed file. Summary numbers (also in `sample.jsonl.meta.json`):

- per flow: **8 × 10** (all flows)
- subflow caps: account_access **3** (deviation), all others **2**
- per-flow/subflow counts: see meta.json `subflow_counts` — **63 subflows**
  used in total: 48 with 1 convo, 13 with 2, 2 with 3 (the two
  account_access subflows at the deviation cap)
- empty-`scenario.product`: **22 / 80** (window 20–32; corpus share 25.7%)
- B1 coverage (sample convos with ≥ 1 action turn): **80/80**
  (min 1 action turn; corpus-wide every one of the 10,042 convos has ≥ 1
  action turn — measured, so B1 is scorable on every sampled convo)
- B0 token distribution (frozen counter): **median 187.0, p95 (nearest-rank)
  277, min 65, max 417**
- R1 overlap: **0 / 80**

## 5. What this unlocks (R2 downstream, per #6 5449115746 §4)

- `extract.py` (next, on sample landing): per sample convo → B0 render, B1
  trace (`targets[2]` action names, D11, ontology vocab; unmapped names
  FLAGGED, never dropped), B2 skeleton (schema keys; judgment fields null
  until the lead's 80-unit draft), frozen token counts.
  Corpus fact measured now for that step: **all 36,482 action turns across
  10,042 convos use exactly the 30 ontology action names — 0 unmapped.** The
  #6 §4 tasking's "the 10 unmapped action names FLAGGED, never silently
  dropped" does not trigger on this corpus: no name outside `ontology.json`
  exists in `targets[2]` of any `speaker:"action"` turn. The flagging path
  stays implemented in extract.py and will fire (and be reported) if any
  out-of-vocab name is ever seen — it is a guard, not an expected count.
- Judge harness plumbing reuses the R1 labeling infra pattern
  (`research/phase2/labeling/` — split/stage/collect; shuffle + anonymize for
  blind answering; pass 2 in a fresh context).

**Honesty clause (rides from R1):** every M2 number will carry
*agent-labeled / agent-judged; inter-pass disagreement is a
self-consistency floor, not human inter-rater agreement.*

## 6. Extract phase (R2 downstream) — candidates + judge-harness plumbing

**Deliverables:** `candidates.jsonl` (80 convos × {B0 render, B1 trace,
B2 skeleton, frozen token counts}) + `candidates.jsonl.meta.json` +
`extract.py` (generator, stdlib only) + `validate_candidates.py`
(independent re-derivation gate, re-renders everything from the raw
corpus) + judge-harness plumbing: `stage_blind_pass.py` (blind
Q1–Q3 answering passes 1+2, committed bind layer
`judge/binding/`) and `stage_scoring_pass.py` (scoring pass, committed
bind layer `judge/scoring/`), both following the R1 labeling infra
pattern (seeded shuffled pass inputs in DIFFERENT orders, anti-leak
field-set assertion, per-pass fresh-context stage dir with manifest +
prompt + conformance checker, deterministic 6-hex codenames, mapping
for join-time de-anonymization only).

**Pinned inputs (checked by extract.py and validate_candidates.py
before any work):**
- corpus sha256:16 **`005d425e890b30a1`** (unchanged)
- sample sha256:16 **`f2195e7a6abe2221`** (the frozen sample, PR #21)
- ontology sha256:16 **`2e1c1d763518ba08`** — canonical vocab re-derived
  as the union of `ontology.json['actions']` category keys
  (kb_query 6 ∪ interaction 10 ∪ faq_policy 14 = **30 names**)

**Pinned output:** `candidates.jsonl` sha256:16 **`dd1869a2d72c6b2b`**
(byte-identical across consecutive runs, 2026-08-28).

### 6.1 Render definitions (frozen)

| candidate | render | token count |
|---|---|---|
| B0 | all `original` turns as `"speaker: text"`, space-joined | `n_tokens_b0` — **final** (== sample row, asserted) |
| B1 | ordered `targets[2]` action names (D11), space-joined | `n_tokens_b1` — **final** (== n_action_turns; vocab names are whitespace-free — asserted) |
| B2 | JSON of the unit, schema key order, receipt included, default separators | `n_tokens_b2` — **PROVISIONAL** (skeleton cost; final count computed on the lead's unit at join time) |

Token counter (frozen): whitespace-split of the rendered candidate.

B2 skeleton (judgment fields `null` until the lead's 80-unit draft —
lead is drafting in parallel, nothing blocks on this artifact):
`problem_shape` / `constraint` / `unlock` / `what_worked` /
`receipt{corpus, convo_id, flow, subflow, event_span, scope, confidence}`.
Mechanical prefill: `what_worked` = the ordered `targets[2]` sequence
(the pre-registration defines what_worked as "the resolution action
sequence from `targets[2]`"; the lead's draft is authoritative at join
time) + `receipt.corpus/convo_id/flow/subflow` from the corpus.
`what_failed` stays OUT (pending §4/R3; collapse rule pre-registered).

### 6.2 The unmapped guard (precision note — keep with the number)

`targets[2]` values are normalized to the canonical 30-name vocab.
Out-of-vocab names are **FLAGGED, never dropped** (kept in the trace +
per-row `unmapped` list + meta aggregate). **Measured on this corpus:
0 unmapped** (sample and corpus-wide — 36,482 action turns, all 30
names). The flag path is a guard, not an expected count: it is
implemented and exercised by `extract.py --selftest` on synthetic
out-of-vocab / non-str names. The R1-era "10 unmapped" gap was vs
`guidelines.json` Title-Case button names, **not** vs the canonical
vocab — against the canonical vocab the measured value is 0/30 unmapped.
0 is the number; the guard is the guard.

### 6.3 Interpretations (R2 status; #3 ADJUDICATED by the lead, 5450060638 §2)

1. **B2 render separators — CONFIRMED (default).** The pre-registered
   "canonical JSON (schema key order)" does not fix separators, and the
   frozen counter is whitespace-split. With compact (JCS-style) separators
   the render has NO whitespace → every B2 unit tokenizes to exactly 1
   token → the pre-registered token bar (tokens(B2) ≤ tokens(B0)/10) passes
   trivially, self-defeating the M2 question. Default JSON separators are
   the only reading under which the counter measures the unit's actual cost;
   they are used here and are confirmed. (Skeleton cost under this reading:
   23–30 tokens; the FINAL number is on the lead's unit — total 3,667.)
2. **"No flow/band hints" scope — CONFIRMED (presentation).** Read as a
   constraint on the PRESENTATION (no item metadata — convo id, candidate
   type, construction band — accompanies a render). In-unit content such as
   the B2 receipt's `flow`/`subflow` fields is part of the candidate being
   tested and is answered as-is (documented in `PROTOCOL-m2-blind.md` §1
   scope note).
3. **Scoring call count — ADJUDICATED: the frozen TWO-CALL structure is
   restored (5450060638 §2; the earlier "combined single call" confirmation
   in 5449907074 §2.3 is overridden).** The pre-registration budgets 160
   calls for this half (80 reference + 80 scoring) as a TWO-call structure
   per convo: (a) a **reference** call — transcript ONLY → the judge's
   R1–R3, the anchor formed in a context that has NOT seen the candidates;
   and (b) a **scoring** call — transcript + the 3 anonymized candidates +
   the committed reference → scores. The combined single call (80) was
   confirmed in error and is overridden: with the candidates in the same
   context the reference is no longer formed independently of the candidates
   it anchors. Cost: 480 blind + 80 reference + 80 scoring = **640 — exactly
   the frozen ceiling**. The scoring pass implements the two calls as two
   separate fresh contexts (`stage-reference` then `stage-scoring`); the
   scoring input is built at stage time from the committed reference.

### 6.4 Re-run contract

```bash
# generator (deterministic, byte-identical; stdlib only)
# SKELETON mode (PR #22 artifact; byte-reproduces dd1869a2d72c6b2b):
python3 research/phase2/m2/extract.py \
    --corpus data/abcd/abcd_v1.1.json \
    --sample research/phase2/m2/sample.jsonl \
    --ontology data/abcd/ontology.json \
    --out research/phase2/m2/candidates.jsonl
# FILLED mode (R2 fix-forward, 5450060638 §1 item 1): slot the lead's
# 80-unit draft (b2_draft sha 5063a85c4ab79465) into b2_unit/b2 → the
# committed artifact (sha a54f52a557ce38b5; final B2 render + n_tokens_b2):
python3 research/phase2/m2/extract.py \
    --corpus data/abcd/abcd_v1.1.json \
    --sample research/phase2/m2/sample.jsonl \
    --ontology data/abcd/ontology.json \
    --out research/phase2/m2/candidates.jsonl \
    --draft research/phase2/m2/b2_draft.jsonl
python3 research/phase2/m2/extract.py --selftest   # flag path on synthetic names

# independent verification gate (re-renders everything from the raw corpus)
# FILLED mode (--draft enables the filled-unit F-checks: F2' non-null where
# drafted, unlock null allowed, F6 unit == draft unit) → PASS 29/29:
python3 research/phase2/m2/validate_candidates.py \
    --corpus data/abcd/abcd_v1.1.json \
    --sample research/phase2/m2/sample.jsonl \
    --ontology data/abcd/ontology.json \
    --candidates research/phase2/m2/candidates.jsonl \
    --draft research/phase2/m2/b2_draft.jsonl
# (omit --draft to validate the SKELETON artifact → 26/26)

# judge harness (blind answering passes)
python3 research/phase2/m2/stage_blind_pass.py bind \
    --candidates research/phase2/m2/candidates.jsonl \
    --out research/phase2/m2/judge/binding
python3 research/phase2/m2/stage_blind_pass.py stage \
    --bind research/phase2/m2/judge/binding --pass 1 --stage-dir <dir1>
python3 research/phase2/m2/stage_blind_pass.py stage \
    --bind research/phase2/m2/judge/binding --pass 2 --stage-dir <dir2>
# hand each <dirN>/passN_prompt.md to a FRESH agent session; check with
# <dirN>/passN_check.py; join via judge/binding/candidate_mapping.json

# judge harness (scoring pass — frozen 2-call structure, 5450060638 §2)
python3 research/phase2/m2/stage_scoring_pass.py bind \
    --candidates research/phase2/m2/candidates.jsonl \
    --out research/phase2/m2/judge/scoring
# Call 1 — reference (transcript ONLY, candidate-free context) → R1-R3:
python3 research/phase2/m2/stage_scoring_pass.py stage-reference \
    --bind research/phase2/m2/judge/scoring --stage-dir <dir3>
# hand <dir3>/reference_prompt.md to a FRESH agent session → 
# <dir3>/reference_answers.jsonl (check with <dir3>/reference_check.py)
# Call 2 — scoring (transcript + 3 candidates + the committed reference):
python3 research/phase2/m2/stage_scoring_pass.py stage-scoring \
    --bind research/phase2/m2/judge/scoring --stage-dir <dir4> \
    --reference <dir3>/reference_answers.jsonl
# hand <dir4>/scoring_prompt.md to a FRESH agent session; check with
# <dir4>/scoring_check.py; join via judge/scoring/convo_mapping.json
```

### 6.5 Verification evidence (2026-08-28, R2 fix-forward — the current committed state)

> The R2 fix-forward (GH #6 5450060638) replaced the PR #22 skeleton
> candidates + combined-call scoring with the FILLED draft + frozen 2-call
> scoring. This section reflects the CURRENT committed state; the PR #22
> state (skeleton `dd1869a2d72c6b2b`, 24/24 as recorded then) is preserved
> in git history and remains byte-reproducible via `extract.py` (skeleton
> mode).

- **Pinned inputs (checked before any work):** corpus `005d425e890b30a1`;
  sample `f2195e7a6abe2221`; ontology `2e1c1d763518ba08`; **b2_draft
  `5063a85c4ab79465`** (the lead's 80-unit draft, the join's authority on the
  B2 unit).
- **`candidates.jsonl` (FILLED) sha256:16 `a54f52a557ce38b5`** — the lead's
  draft slotted into `b2_unit`/`b2`; B0/B1 renders byte-unchanged from the
  skeleton artifact (verified 0/0 changed); B2 renders changed 80/80;
  determinism re-run byte-identical. `extract.py --selftest` green (flag
  path on synthetic names).
- **`validate_candidates.py` (FILLED, `--draft`): VERDICT PASS 29/29**,
  including independent re-derivation of every render from the raw corpus
  (B0 byte-identical; B1 re-derived `targets[2]` sequences; B2 frozen schema
  key order + judgment fields non-null where drafted — `problem_shape`/
  `constraint`/`receipt.event_span`/`scope`/`confidence` non-null, `unlock`
  null allowed (53/80) + mechanical prefill + `b2 == json.dumps(b2_unit)`
  round-trip (default separators) + frozen counters; F6 committed unit == the
  pinned draft's unit). SKELETON mode (omit `--draft`): **26/26**.
  (Precision: the as-merged note recorded "24/24"; the validator mechanically
  runs **26** checks in skeleton mode (A4 + B1 + C5 + D3 + E5 + F5 + G3) and
  **29** in filled mode (A6 + B1 + C5 + D3 + E5 + F6 + G3 — adds A5 draft
  sha, A6 draft count, F6 unit-equality; F2 → F2'). The as-merged "24" was a
  write-time miscount of the lettered groups, corrected per D21.)
- **B0 tokens:** median 187.0, p95 (nearest-rank) 277, min 65, max 417
  (identical to the sample meta). **B1:** 286 action turns total (min 1 /
  max 8); every name in the canonical 30-name vocab; unmapped aggregate **0**.
- **B2 draft tokens (FINAL, on the lead's unit):** min 37 / median 45.0 /
  max 57, **total 3,667** (aggregate ratio B2/B0 = 3,667/15,340 = 0.2390).
  Skeleton floor (PROVISIONAL reference only): min 23 / median 25.0 /
  max 30, total 2,046 (23–30/convo, not flat).
- **Judge harness re-bound from the new candidates (new committed bind
  layers):**
  - **Blind:** 240 items/pass, orders differ (seeds 20260901/20261001),
    anti-leak field set {item_id, codename, question, render}; only the B2
    renders changed (80/80 per pass) — B0/B1 unchanged; `pass1_input`
    sha256 `5ef2d7cc…`, `pass2_input` sha256 `17d701f9…`; all 240/240 renders
    byte-identical to the new `candidates.jsonl`; `candidate_mapping.json`
    unchanged (codenames are deterministic — only the renders changed).
  - **Scoring (frozen 2-call structure):** `reference_input.jsonl` (transcript
    ONLY — candidate-free context) sha256 `d3d6ef8a…`; `scoring_base.jsonl`
    (transcript + 3 anonymized candidates, per-convo shuffled, seed 20261101)
    sha256 `6a76e5e7…`; the scoring input is built at `stage-scoring` time
    from the committed reference (not committed). B0/B1 candidate renders
    unchanged vs the old combined input, B2 changed 80/80; codename space
    320 distinct (80 convo + 240 candidate).
- Selftests green: `extract.py --selftest`, `stage_blind_pass.py --selftest`,
  `stage_scoring_pass.py --selftest` (reference candidate-free; scoring base
  + committed reference; stage purity; reference validation rejects partial
  input; deterministic).
- **Budget (frozen ceiling 640):** 480 blind answering calls + 80 reference
  calls + 80 scoring calls = **640 — exactly the frozen ceiling** (the frozen
  2-call structure; 5449115746 §3). All agent-judged; the reference is
  formed in a candidate-free context (the anchor is transcript-derived, not
  corrupted by the candidates); honesty clause rides with every number from
  the first judge call.
- **Evaluation HOLD:** S1/S2/S3 held until the re-bound inputs are merged;
  the blind pass runs exactly once, on the final renders. No judge call
  before the re-bind.
