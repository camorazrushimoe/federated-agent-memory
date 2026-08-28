# M2 sample (R2) — construction notes + re-run contract

**Deliverable:** `research/phase2/m2/sample.jsonl` (80 convos) +
`sample.jsonl.meta.json` (deterministic run record) + `sample.py` (generator)
+ `validate_sample.py` (independent re-derivation gate).
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
