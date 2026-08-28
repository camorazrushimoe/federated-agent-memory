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

### 6.3 Interpretations flagged for lead confirmation (both non-blocking)

1. **B2 render separators.** The pre-registered "canonical JSON (schema
   key order)" does not fix separators, and the frozen counter is
   whitespace-split. With compact (JCS-style) separators the render has
   NO whitespace → every B2 unit tokenizes to exactly 1 token → the
   pre-registered token bar (tokens(B2) ≤ tokens(B0)/10) passes
   trivially, self-defeating the M2 question. Default JSON separators
   are the only reading under which the counter measures the unit's
   actual cost; they are used here. (Skeleton cost under this reading:
   23–30 tokens; the final number waits for the lead's unit.)
2. **"No flow/band hints" scope.** Read as a constraint on the
   PRESENTATION (no item metadata — convo id, candidate type,
   construction band — accompanies a render). In-unit content such as
   the B2 receipt's `flow`/`subflow` fields is part of the candidate
   being tested and is answered as-is (documented in
   `PROTOCOL-m2-blind.md` §1 scope note).
3. **Scoring call count.** The pre-registration budgets 160 calls for
   this half (80 reference + 80 scoring) and describes the procedure as
   one sequence per convo ("the judge first writes its OWN reference
   answers, then scores each candidate"). The scoring pass implements
   ONE combined call per convo (references + scores, in that order) —
   80 calls, within the frozen bound, no extra calls.

### 6.4 Re-run contract

```bash
# generator (deterministic, byte-identical; stdlib only)
python3 research/phase2/m2/extract.py \
    --corpus data/abcd/abcd_v1.1.json \
    --sample research/phase2/m2/sample.jsonl \
    --ontology data/abcd/ontology.json \
    --out research/phase2/m2/candidates.jsonl
python3 research/phase2/m2/extract.py --selftest   # flag path on synthetic names

# independent verification gate (re-renders everything from the raw corpus)
python3 research/phase2/m2/validate_candidates.py \
    --corpus data/abcd/abcd_v1.1.json \
    --sample research/phase2/m2/sample.jsonl \
    --ontology data/abcd/ontology.json \
    --candidates research/phase2/m2/candidates.jsonl

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

# judge harness (scoring pass)
python3 research/phase2/m2/stage_scoring_pass.py bind \
    --candidates research/phase2/m2/candidates.jsonl \
    --out research/phase2/m2/judge/scoring
python3 research/phase2/m2/stage_scoring_pass.py stage \
    --bind research/phase2/m2/judge/scoring --stage-dir <dir3>
# hand <dir3>/scoring_prompt.md to a FRESH agent session; check with
# <dir3>/scoring_check.py; join via judge/scoring/convo_mapping.json
```

### 6.5 Verification evidence (2026-08-28, pre-handoff)

- `validate_candidates.py` self-run: **VERDICT: PASS — 24/24 checks**,
  including independent re-derivation of every render from the raw
  corpus (B0 byte-identical; B1 re-derived `targets[2]` sequences; B2
  skeleton schema + null judgment fields + mechanical prefill; frozen
  counters on all three).
- B0 tokens: **median 187.0, p95 (nearest-rank) 277, min 65, max 417**
  — identical to the sample meta (the frozen counter is consistent
  end-to-end).
- B1: **286 action turns total** across the 80 sample convos (min 1 /
  max 8 per convo); every name in the canonical 30-name vocab;
  unmapped aggregate **0**.
- B2 skeleton tokens (PROVISIONAL): min 23 / median 25.0 / max 30.
- Judge harness: bind layers committed (240 items/pass blind, 80 items
  scoring); pass inputs carry ONLY the frozen fields (asserted);
  blind pass orders differ (seeds 20260901/20261001); per-convo
  candidate order seeded (scoring seed 20261101); all 240/240+80
  renders byte-identical to candidates.jsonl; codename spaces
  collision-free; selftests green (`extract.py --selftest`,
  `stage_blind_pass.py --selftest`, `stage_scoring_pass.py --selftest`).
- Budget status: 480 blind answering calls + 80 combined scoring calls
  (frozen ceiling 640) — all agent-judged; honesty clause rides with
  every number from the first judge call.
