# H2 — Round-0 Plan (updated 2026-08-28)

Working plan for the first round of the H2 experiment
(`standalone/h2-federated-scoped-memory/`). Committed; the issue copy lives on
[#51](https://github.com/camorazrushimoe/federated-agent-memory/issues/51).

**Supersedes:** the round-0 reading from the original commission where they
differ. **Reason:** founder decision 2026-08-28 — **D0 GOLD, AGENT-LABELED ON
PRO** — which updates issue #51 and DATA-AUDIT §6: lab-evaluation produces
`data/gold_useful.jsonl` instead of a human.

---

## 1. Decision reference

| doc | what the founder pinned |
|---|---|
| LAB-BRIEF / issue #51 | roles, deliverables D1–D7, stops, report format |
| DATA-AUDIT §6 | the slice: hold-out FAQ how-to + site-troubleshoot + 20 negative dispute/promo |
| EVAL-PLAN §1, §4.2 | gold format & rules, `useful_hit`, classes |
| **Founder decision 2026-08-28** | **D0 gold = agent-labeled (deepseek-v4-pro), NOT human gold** |

### The six rules of the D0 decision (binding)

1. **Agent-labeled, explicitly NOT human gold.** Caveat in three places:
   (a) header of `data/gold_useful.jsonl`, (b) the run manifest
   (`manifest.json`), (c) **every** report line citing an L2 usefulness number.
2. **Labeling model = `deepseek-v4-pro`** (not flash). Committed labeling script
   reuses the `call_llm` wrapper with `--model deepseek-v4-pro`; same key
   (`H2_API_KEY`) and base URL (`H2_BASE_URL`), no new secret. The S2 tag in the
   measured loop **stays `deepseek-v4-flash` — unchanged, pinned**.
3. **The labeler reads the transcript** and judges *"does this past session
   carry a transferable move the label does not contain?"* It MUST NOT derive
   `useful_dialogue_ids` from `unlock` / `unlock_guideline` — that re-measures
   H1 and voids the finding. (Enforced structurally: the labeler only ever sees
   the *adapted* corpus, where the adapter has already dropped
   `unlock`/`unlock_guideline`; plus QA check C-GD7.)
4. **Format = `data/gold_useful.seed.jsonl`** (the committed seed is the schema
   template): one JSON object per line `{query_id, useful_dialogue_ids,
   notes}`. On dispute/refund/promo pairs an **empty `useful_dialogue_ids` is a
   valid (and often correct) answer, not a hole**.
5. **Slice = hold-out FAQ how-to + site-troubleshoot + 20 negative
   dispute/promo** (DATA-AUDIT §6). Exact membership frozen in a slice manifest
   at Phase B open.
6. **Phase A (D1–D2, S0 on fixtures, flash) is unchanged.** Phase B (corpus
   sync + D0 gold) opens **only after D2 is green**. The hold-out is not
   touched before Phase B opens.

---

## 2. Who takes what

| role | owns |
|---|---|
| **Research Engineer** | `bin/` S1–S7 + `replay.py` + `eval.py` + checks harness (D1/D2); Phase B infra: corpus sync, slice manifest builder, **`bin/label_gold_useful.py`**, frozen labeler prompt, C-GD checks; Phase C runner + slice run |
| **Research Lead** | this plan; review **by re-execution** (never by reading); audits A1–A6; **D0 gold QA sign-off** (incl. anti-H1 collinearity C-GD7); fitness verdict |
| **Evaluation** | **the D0 gold labeling run** (pilot 10 → full slice, `deepseek-v4-pro`), D0 QA numbers, eval metrics, L2 numbers (with the NOT-HUMAN-GOLD caveat), cost |
| **Founder / oversight** | gates (D2 green → Phase B; D0 committed → Phase C), merges, freeze of slice / gold / hold-out |

One module — one owner. No second `bin/`. The author never approves their own
deliverable.

---

## 3. Reading of the four numbers (EVAL-PLAN §4, §6)

| # | number | where | gate (EVAL-PLAN §6.2) |
|---|---|---|---|
| 1 | **Tags** (S2 flash vs `gold_tags`) | §4.1 | `ending_exact` ≥ 0.80, `constraint_exact` ≥ 0.60, `problem_shape_exact` ≥ 0.35 or jaccard ≥ 0.60 |
| 2 | **Usefulness** (packet vs `gold_useful`) | §4.2 | `T.hit` > `B1.hit` on the same n; `T.wrong` ≤ 0.25 |
| 3 | **Rotation** (long replay) | §4.5 | `top3_share` ≤ 0.55 after burn-in; `explore_fill` ≥ 0.15 where candidates > `MAX_PACKET` |
| 4 | **Cost** (whole-session packet) | §4.6 | `packet_tokens_p50` recorded; > 1500 ⇒ FIT WITH LIMITS flag |

Plus hard gates §6.1 (`C-SELF`, `C-FUTURE`, `C-PII`, `C-PROMPT`, `C-SIZE`,
`C-DELTA`, `C-REPLAY`, `B0.hit == 0`, class sums == 1.0). Verdict = exactly one
of FIT / FIT WITH LIMITS / NOT FIT (§6.4).

**Reading:** the experiment stands or falls on number 2 (usefulness) — whether
the ranker beats a random similar past session on the audit slice. Numbers 1,
3, 4 explain *why* the usefulness number looks the way it does and set its
limits; none of them is a substitute for 2, and 2 is meaningless without B1 on
the same tail.

---

## 4. Order — phases and gates

```
Phase A  (NOW, unblocked, UNCHANGED)
   D1: bin/ per SPEC (S1–S7 + replay) + one call_llm wrapper
   D2: checks harness — every CHECKS id, HARD aborts the run
   Gate: S0 HARD green on fixtures/ (tag model deepseek-v4-flash, temp 0)
   → STOP, READY for the D0 checkpoint. Corpus untouched. Hold-out untouched.

Phase B  (GATED on D2 green + founder checkpoint)
   1. corpus sync:  bin/sync_h1_data.sh → data/abcd_*.jsonl (local, gitignored)
                     bin/adapt_h1_corpus.py → data/dialogues.jsonl (drops unlock)
   2. slice manifest: data/d0_slice.jsonl — 60 hold-out queries, FROZEN (sha)
                     = 34 FAQ how-to + 6 site-troubleshoot + 20 negatives
                     (deterministic rule below; built from RAW unlock fields;
                      this is slice composition, not usefulness labeling)
   3. committed labeler: bin/label_gold_useful.py + frozen prompt
                     (new PROMPTS.md section; S2 §2–§3 byte-untouched)
                     + C-GD1..C-GD8 in CHECKS.md
   4. Evaluation runs the labeler: pilot 10 → full 60, deepseek-v4-pro, temp 0
                     → data/gold_useful.jsonl (header + seed-format rows)
                     + raw/label_gold/<query_id>.json + D0 manifest
   5. QA gates green (C-GD1..C-GD8, incl. anti-H1 C-GD7)
   Gate: gold committed (one PR: script + prompt + checks + slice + gold)

Phase C  (GATED on D0 committed)
   S2 tag on the slice (flash, pinned) → T / B0 / B1 / B2 / B3 on the slice
   → one run dir → metrics/cost/per_query → report.md (caveat on every L2
   usefulness line) → verdict §6.4
   Full 1000+200 only if the slice shows a gap vs B1, or the report honestly
   says there is none.
```

**4 rounds max for Phase A** (D1+D2), then a founder checkpoint. Every round
ends in a committed artifact. Nobody merges — oversight merges after verifying.

---

## 5. D0 gold — agent labeler contract (Phase B deliverable)

### 5.1 Script

```
python bin/label_gold_useful.py \
    --dialogues data/dialogues.jsonl \     # adapted corpus, NO unlock fields
    --slice data/d0_slice.jsonl \          # frozen query manifest
    --out data/gold_useful.jsonl \
    --raw-dir raw/label_gold \
    --model deepseek-v4-pro \              # the ONLY live model here
    --k 16 \                               # candidate budget per query
    [--limit 10]                           # pilot mode
```

- Reuses the shared `bin/call_llm` wrapper with `--model deepseek-v4-pro`
  (wrapper contract already requires model/base-url/key only via flag and
  `H2_*` env — C-ISO3). Same key, same base URL, **no new secret**.
- Temperature 0. Raw request/response/usage saved per query
  (`raw/label_gold/<query_id>.json`) — D0 is replayable without new LLM calls.
- **S2 tag is never touched** by this script or by the D0 run.

### 5.2 Inputs the labeler sees

- Query transcript (adapted, PII as-is in the raw text; the labeler's *notes*
  MUST NOT copy identifiers — C-GD3).
- Candidate past sessions: `closed_at < query.closed_at`, bounded to the top-K
  (default 16) by deterministic lexical overlap on customer turns (unlock-free
  prefilter — no LLM, no H1 fields). All pool sessions precede hold-out
  queries in the adapted `closed_at` order, so candidates are plentiful.
- **No `unlock` / `unlock_guideline` anywhere in the input** — the adapter
  drops them, so the labeler physically cannot re-derive H1 labels.

### 5.3 Judgment rubric (frozen prompt, new PROMPTS.md section)

For each past session: *does it carry a transferable move — a concrete
procedure, step sequence, or troubleshooting hint — that would help this query
and that the query's own transcript (its label) does not already contain?*

- FAQ how-to (paint stain / gum / width / wear-in under one guideline):
  only sessions with **the same procedure's move** are useful; same-guideline,
  different-procedure sessions are NOT (seed rows d-7892, d-3219).
- Site-troubleshoot: only sessions with the **right hint** (e.g. close-tabs,
  not ISP diagnosis) — seed row d-7731.
- Dispute / refund / promo: the transferable bit is usually a **rule**, not a
  transcript; a whole session with foreign ids and a one-off exception is not a
  hint ⇒ **empty list is the correct gold** (seed rows d-5711, d-4815).
- Output: `{"useful_dialogue_ids": [...], "notes": "≤ 200 chars"}`.
  Empty list is valid. No markdown fences; one JSON retry on parse failure;
  second failure → row marked `label_error` in the D0 manifest (no invented
  labels).

### 5.4 Output file

```
# AGENT-LABELED GOLD — NOT HUMAN GOLD — labeler=deepseek-v4-pro —
# prompt_sha=<...> corpus_sha=<...> slice_sha=<...> created_at=<...>
{"query_id": "d-7892", "useful_dialogue_ids": ["d-9523"], "notes": "..."}
...
```

First line(s): `#`-prefixed header, mandatory (C-GD1). Then seed-format rows
(rule 4). Consumers (`replay.py`, `eval.py`, checks) MUST skip `#` lines.

### 5.5 D0 manifest (`runs/<date>_D0_gold_useful/manifest.json`)

```json
{
  "run_id": "2026-08-30_D0_gold_useful",
  "kind": "gold_useful",
  "human_gold": false,
  "agent_labeled": true,
  "labeler_model": "deepseek-v4-pro",
  "base_url": "https://api.deepseek.com/v1",
  "temperature": 0,
  "k": 16,
  "prompts_sha": "...",
  "dialogues_sha": "...",
  "slice_sha": "...",
  "gold_out_sha": "...",
  "rows": 60,
  "label_error_rows": 0,
  "calls": 60,
  "tokens_in": 0,
  "tokens_out": 0,
  "usd": null,
  "caveat": "AGENT-LABELED GOLD — NOT HUMAN GOLD"
}
```

D0 labeling cost lives here — **never mixed** into the S2-loop `cost.json`
(EVAL-PLAN §4.6 stays about the measured loop).

---

## 6. Slice manifest rule (frozen at Phase B open)

Built from the RAW hold-out (`abcd_200_holdout.jsonl`), deterministic, no LLM:

| group | rule (raw unlock fields) | n (computed on the frozen corpus) |
|---|---|---|
| FAQ how-to | `unlock_guideline ∈ {Boots, Jacket, Jeans, Shirt FAQ}` AND `unlock` matches `*_how_*` | **34** |
| site-troubleshoot | `unlock_guideline ∈ {Website Too Slow, Cart Not Updating, Search Not Working}` | **6** |
| negatives | dispute/promo families: `Bad Price Competitor`, `Bad Price Yesterday`, `Initiate Refund`, `Promo Code *`, `Manage *`; **first 20 by `chat_id` asc** | **20** |

**Total: 60 hold-out queries.** All 6 seed rows are among them (they are
hold-out ids). Pool/chat ids confirmed disjoint (pool 114–10583, hold-out
229–10568). The raw-unlock rule is used **only** to compose the frozen slice
— never to produce `useful_dialogue_ids`.

---

## 7. D0 QA gates (new HARD checks, added to CHECKS.md with Phase B)

| id | hard | rule |
|---|---|---|
| C-GD1 | HARD | `gold_useful.jsonl` has the `#` header marking agent-labeled / NOT human gold; all consumers skip `#` lines |
| C-GD2 | HARD | every `useful_dialogue_id` has `closed_at` < query's (no future leak) |
| C-GD3 | HARD | no PII in gold output (`notes`, ids): email / phone / ≥10 digits / cvv / iban / ssn |
| C-GD4 | HARD | rows == slice rows; `query_id` unique and ⊆ slice |
| C-GD5 | HARD | `raw/label_gold/` has one file per row; count == rows |
| C-GD6 | SOFT | seed agreement: on the 6 seed rows the labeler's lists do not contradict the seed's direction (report; investigate if contradictory) |
| C-GD7 | HARD | **anti-H1 collinearity** (rule 3 enforcement): the labeler's useful sets are strictly finer than `unlock_guideline` buckets. Check on raw corpus: rows where `useful == all past same-guideline sessions` (H1 signature) must be ≤ 20% of non-empty rows, and every FAQ how-to row's useful set must exclude at least one same-guideline session when one exists. Fail ⇒ labeler re-derived H1 ⇒ re-run with rubric emphasis (new run id) |
| C-GD8 | HARD | D0 manifest `labeler_model == deepseek-v4-pro`; the S2 measured-loop model is unchanged (`deepseek-v4-flash`) |

---

## 8. Not in this decision / open items

- **`gold_tags` on the corpus slice**: the founder decision authorizes
  **`gold_useful` only**. `gold_tags` remains human-authored (EVAL-PLAN §1
  unchanged for it) — needs its own decision before Phase C tagging metrics
  are published. Usefulness L2 is **not** blocked on it.
- Full 1000+200 run: still gated on the slice result (DATA-AUDIT §6).
- L3 judge: closed (EVAL-PLAN §5).
- Session slicing: a later lever, not this pass.

---

## 9. Hypothesis log

See `workspace/h2-federated-scoped-memory/hypotheses.md` (lab-internal living
log). Central hypotheses tracked there: H2-D0 (agent gold is a valid H2
measurement target — not collinear with H1), H2-TAG, H2-USEFUL, H2-HARM,
H2-ROTATION, H2-COST.

---

## 10. Next action

Post this as the round-0 comment on issue #51, then start **Phase A — D1
(`bin/` per SPEC) on the fixtures branch**. Stop and report READY for the D0
checkpoint when D2 S0 HARD is green.
