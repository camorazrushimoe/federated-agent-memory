# M1 Candidate-Pair Contract — what evaluation needs from the engineer

**For:** Research Engineer (pair-construction code) · **From:** evaluation (labeler)
**Status:** v1.0, 2026-08-27 — this is the intake contract, pre-registered.
My harness (`validate_pairs.py`) enforces the blocking checks; the rest is
documented so we do not burn a round on format.

## 1. File

- Path: any path under `research/phase2/` you choose, e.g.
  `research/phase2/m1/candidate_pairs.jsonl`.
- Format: JSONL — one JSON object per line, UTF-8.
- **One line per pair. No labels, no hints, no "expected" field of any kind.**
  My split step rejects fields beyond the allowed set (leakage guard).

## 2. Per-line schema

| field | type | required | meaning |
|---|---|---|---|
| `pair_id` | string | yes | unique, stable (e.g. `m1-0001`) |
| `band` | string | yes | `should-match` \| `ambiguous` \| `should-not-match` |
| `sub_band` | string | for `should-not-match` only | `cross-flow` \| `cross-product` \| `other-diff-flow` (see §4) |
| `conv_a`, `conv_b` | string | yes | `convo_id`s as they appear in the corpus (string form) |
| `flow_a`, `flow_b`, `subflow_a`, `subflow_b` | string | yes | scenario metadata, exactly as in the corpus |
| `product_a`, `product_b` | any | yes | `scenario.product` verbatim (may be the empty `{amounts:[],names:[]}`) |
| `display` | string | yes | the text both passes will see — see §5 |

Nothing else. Extra fields are rejected by `split_passes.py`.

## 3. Sizes (pre-registered, from the method doc + capacity facts)

- **Total: 150–200 pairs.** I will not label outside this range.
- Capacity (computed, `pair_capacity.json`): should-match ceiling 848,766 ·
  ambiguous 4,246,706 · should-not-match 45,320,389. No band is starved.
- Composition guidance (my call as labeler, to keep the metric's bands
  meaningful — flag objections BEFORE pass 1):
  - `should-match`: 45–55% of the set
  - `ambiguous`: 15–25%
  - `should-not-match`: 30–40%, of which:
    - **cross-flow sub-band ≥ 20 pairs** (different `flow`; this is the
      band the commission cares about most — the false-friend band)
    - **cross-product sub-band ≥ 10 pairs** (different non-empty products;
      note: only 7,457/10,042 conversations have a non-empty product — 25.7%
      are empty, so build this sub-band from the 7,457)
    - remainder: other different-flow pairs

## 4. Band definitions (must match — validated against the corpus)

- `should-match`: `subflow_a == subflow_b` (different conversations)
- `ambiguous`: `subflow_a != subflow_b` AND `flow_a == flow_b`
- `should-not-match`: `flow_a != flow_b`
  - `sub_band=cross-flow`: different flows (any products)
  - `sub_band=cross-product`: different flows AND both products non-empty
    AND not the same product
  - `sub_band=other-diff-flow`: different flows where the above don't hold
    (e.g. one/both products empty)

`validate_pairs.py` recomputes all of this from the corpus and BLOCKS
labeling on any mismatch — so if your band labels and the corpus disagree,
we find out before I label, not after.

## 5. Display content (what I will actually read)

- Both conversations' **customer turns** (agent turns: include only if they
  carry problem-relevant content — boilerplate is excluded by the method
  doc's B1 definition; keep the display honest and minimal).
- Format per conversation: a header line with `flow/subflow`, then the
  customer turns in order, each prefixed `CUST:`. Truncation is allowed per
  turn but the first customer turn must be present in full (my validator
  checks this).
- **Include the action-trace names (D11, `targets[2]`) as a trailing
  `ACTIONS: a1, a2, …` line per conversation if you have them.** They are
  corroborating evidence of structure (protocol rule R4), not the label.
- Do NOT include: subflow labels in the display prose, band labels, any
  oracle/guideline text, or comments about the pair. Metadata lives in the
  JSON fields; the display is the conversation text. (The validator sees
  the JSON fields; the labeler reads the display. Keeping them separate is
  the whole point.)
- Target display length: ≤ ~1,500 chars per pair (median conversation is
  short; long conversations should be sampled from the informative middle,
  not silently cut at the end).

## 6. Sampling rules

- Seed your RNG and record the seed in your PR/commit message (reproducibility,
  workflow §8).
- No conversation may appear in more than **2 pairs** total (limits
  within-set correlation between pairs; I will check and report the max).
- `conv_a != conv_b` always; pair order (a/b) is irrelevant — my passes see
  shuffled pair order anyway, but don't encode meaning in position.

## 7. Acceptance (what I run before pass 1)

1. `validate_pairs.py <file>` → must return `OK_TO_LABEL` (0 blocking;
   warnings reported).
2. Counts within §3 (range + sub-band minimums).
3. Max conversations-per-pair ≤ 2.
4. Spot-check (≥10 pairs) that displays are faithful to the corpus.

If any check fails: I post the exact failing items on #6, and we fix
forward. I do not silently repair pair data — construction errors are the
engineer's to own (workflow §1: roles do not blur).
