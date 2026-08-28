# H1 Experience Cards — Step Checks (Layer 1)

Contract assertions, one per line, machine-checkable on files that already exist
on disk. This is **not** quality measurement (`EVAL-PLAN.md` §0) — it is proof
that the wiring obeys `SPEC.md`.

- **HARD** — a failure aborts the run; the run publishes no L2/L3 numbers.
- **SOFT** — recorded as a warning in `checks.json` and carried into `report.md`.

`checks.json` row: `{check_id, step, hard, passed, observed, expected, note}`.
Every id below MUST appear in `checks.json` on every run, including the ones that
are trivially satisfied — a missing id is treated as a failure.

---

## Leakage and isolation

| id | hard | assertion |
|--|--|--|
| `C-L1` | HARD | The committed input pack (`data/abcd_1000_pool.jsonl`, `data/abcd_200_holdout.jsonl`) has the sha256 recorded in `data/README.md` **after** the run — the run never writes into the input folder. |
| `C-L2` | HARD | No record in `data/dialogues.jsonl` (nor any extract request in `raw/extract/`) contains the keys `unlock`, `unlock_guideline` or `split`. Ground truth never reaches the model. |
| `C-L3` | HARD | No file under `bin/` imports from `research/`, `openspec/`, or any package outside `standalone/h1-experience-cards/` (`SPEC.md` §2). |
| `C-L4` | HARD | No embedding model, vector store, DB driver or network call other than `call_llm` appears in `bin/` (grep for `embed`, `qdrant`, `neo4j`, `psycopg`, `chromadb`). |
| `C-L5` | HARD | The hold-out file is opened exactly once per run, at S2, and never in S0/S1 (assert on the runner's own access log). |

## Ingest (`ingest.py`)

| id | hard | assertion |
|--|--|--|
| `C-IN1` | HARD | `kept + dropped == rows in the input file`. Nothing vanishes silently. |
| `C-IN2` | HARD | Every kept dialogue has ≥1 `customer` turn (`SPEC.md` §3); every dropped one has 0. |
| `C-IN3` | HARD | Every kept dialogue has `dialogue_id`, `tenant_id`, `vertical`, `agent_id`, `channel`, `closed_at`, and `turns[].role ∈ {customer, agent, tool}`. |
| `C-IN4` | HARD | `dialogue_id` values are unique. |
| `C-IN5` | HARD | Turn text is byte-identical to the pack (no normalisation, no truncation) — verify on 20 random dialogues. |
| `C-IN6` | HARD | Re-running ingest on the same input produces a byte-identical `dialogues.jsonl`. |
| `C-IN7` | SOFT | `agent_id` distribution over the pool is within ±20% of uniform for `AGENT_POOL_SIZE` (the synthesis is not skewed). |

## Extract (`extract.py`, the only LLM step)

| id | hard | assertion |
|--|--|--|
| `C-EX1` | HARD | Every card validates against the `SPEC.md` §4 schema, including `status=private`, `role=canonical`, `votes=1`, `members=[]`, `cluster_id == card_id`, `receipt.last_closed_at == receipt.closed_at`. |
| `C-EX2` | HARD | `card_id == "c-" + sha256(dialogue_id)[:12]`, for every card. |
| `C-EX3` | HARD | Field limits hold: `problem_shape` ≤12 words and non-empty; `constraint`/`unlock` ≤12 words or exactly `none`; `what_worked` has 1–8 items. |
| `C-EX4a` | HARD | **No invented specifics.** Every number, order/account identifier, tool name and proper noun appearing in any card field MUST also appear in the source transcript. A card may paraphrase; it may not introduce an entity that is not in the chat. Zero tolerance — this is the hallucination gate. |
| `C-EX4b` | SOFT | **Lexical grounding rate.** For every non-`none` `problem_shape` / `constraint` / `unlock`, record whether at least one content word (≥5 chars, lowercased) also appears in the transcript. Report the per-field ungrounded **count and rate**; do not abort the run. Cards flagged here MUST be included in the L3 judge sample (`EVAL-PLAN.md` §5) — a faithful paraphrase with zero lexical overlap is a limitation of a string test, not evidence of invention, and only the judge can tell the two apart. |
| `C-EX5` | HARD | **PII:** no card field matches `\S+@\S+`, `\+?\d[\d\-\s]{7,}\d`, `\d{10,}`, `\bcvv\b`, `\biban\b`, `\bssn\b` — scanned across the entire store, not just the fixture. |
| `C-EX6` | HARD | On the §10.1 fixture: the card survives, `4412` is absent from every field, and it is **not** rejected merely because `contains_pii=true`. |
| `C-EX7` | HARD | A transcript containing the bare word `card` (e.g. "gift card") does not set `contains_pii` on that ground alone. |
| `C-EX8` | HARD | Rejection happens **only** per the post-scrub rule (`problem_shape` empty, or both `constraint` and `unlock` are `none` **and** `what_worked` empty). Every rejected card must satisfy that rule. |
| `C-EX9` | HARD | Re-extract upserts by `card_id`: no duplicate ids, and a card that already has `cluster_id != card_id` or `status=merged` is skipped, not overwritten (`SPEC.md` §6.2). |
| `C-EX10` | HARD | Every dialogue has a matching file in `raw/extract/` with request, response, model id and usage. Count equals the number of extract calls in `cost.json`. |
| `C-EX11` | SOFT | Unparseable-JSON rate from the model is reported; each occurrence keeps its raw response for inspection. |
| `C-EX12` | SOFT | No card field contains a customer name present in the transcript (identity leak beyond the regex gate). |

> **Why `C-EX4` was split (amended 2026-08-28, pre-registered before re-measuring):**
> the original single check conflated two different questions and failed a card
> whose `constraint` read *"payment rejected despite retry"* against a transcript
> saying *"credit card won't work, says invalid"* plus two retries — a correct
> paraphrase with no shared ≥5-char word. Relaxing the string rule (e.g. to
> shared 4-char prefixes) would have let real invention through in order to
> excuse one false positive. So invention stays HARD and exact (`C-EX4a`),
> paraphrase quality moves to the L3 judge, and the lexical overlap rate survives
> as a reported SOFT number (`C-EX4b`). The n=16 readings taken at S0 are
> draw-dependent; the rate that counts is measured at S1 on 200 dialogues.
> Any run that reports `C-EX4` as a single check is running stale code.

## Cluster (`cluster.py`, deterministic)

| id | hard | assertion |
|--|--|--|
| `C-CL1` | HARD | Without `--force`, the run no-ops when fewer than `CLUSTER_EVERY_N_CHATS` new dialogues landed, printing `{ran: false, remaining: N}`. |
| `C-CL2` | HARD | No cluster ever spans two `receipt.scope` values. |
| `C-CL3` | HARD | Exactly one `role=canonical` per `cluster_id`; it is the oldest by `created_at` (tie: smaller `card_id`); every other member is `status=merged, role=member` and appears in the canonical's `members`. |
| `C-CL4` | HARD | `votes` recomputed from scratch equals the stored value for every canonical card, per `SPEC.md` §5.1 — including the `served_to` subtraction and the independence rule. |
| `C-CL5` | HARD | `status=shared` **iff** `votes >= K_INDEPENDENT` (and not stale). |
| `C-CL6` | HARD | `receipt.last_closed_at == max(closed_at)` over canonical + members; with `timeline=aged`, a cluster whose newest member closed yesterday is **not** stale, and one quiet for >30 days **is**. |
| `C-CL7` | HARD | `merged` cards are never a cluster seed on a later run and never appear on the serve path. |
| `C-CL8` | HARD | Field inheritance follows §5.2: a non-`none` canonical `unlock` is never overwritten; holes are filled from the oldest member that has a value; `what_worked` is the de-duplicated union capped at 8. |
| `C-CL9` | HARD | Re-running cluster on unchanged inputs is a no-op: `cards.jsonl` byte-identical, `clusters_formed=0`, `merged=0`. |
| `C-CL10` | HARD | §10.2 fixture: ten near-duplicates from ≥2 agents → 1 canonical, 9 merged, `votes>=2`, `shared`. §10.3 fixture: the same ten from one agent → `votes=1`, stays `private`. |
| `C-CL11` | SOFT | `unlock_conflict` count reported (clusters holding two different non-`none` unlocks). |

## Promote (`promote.py`)

| id | hard | assertion |
|--|--|--|
| `C-PR1` | HARD | `promote.py` changes only `status` (and staleness), never `cluster_id`, `members` or `votes` — it is the vote→status tail of `cluster.py`, not a second loop (`SPEC.md` §6.5). |
| `C-PR2` | HARD | No card reaches `shared` with `votes < K_INDEPENDENT`, on any path. |
| `C-PR3` | HARD | **Anti-echo:** serve a canonical card to dialogue D, then re-cluster — D is in `served_to` and **not** counted in `votes`. Serving the same card 10 times leaves `votes` unchanged. |
| `C-PR4` | HARD | A `stale` canonical never returns to `shared` within the run; its members stay `merged`. |

## Match / Serve (`match.py`, `serve.py`)

| id | hard | assertion |
|--|--|--|
| `C-SV1` | HARD | **`scope_leak == 0`**: no packet ever contains a card whose `receipt.scope` differs from the live dialogue's scope. A different `vertical` returns an empty packet. |
| `C-SV2` | HARD | **`duplicate_in_packet == 0`**: never two cards with the same `cluster_id`; the higher score wins. |
| `C-SV3` | HARD | Candidates are `status=shared` **and** `role=canonical` only. No `private`, `merged`, `stale` or `rejected` card is ever scored on the serve path. |
| `C-SV4` | HARD | Packet size ≤ `MAX_PACKET`; every included score ≥ `MATCH_THRESHOLD`; scores sorted descending. |
| `C-SV5` | HARD | The query is the concatenation of `customer` turns only — an agent-only or tool-only text change must not alter the score (verify on one perturbed dialogue). |
| `C-SV6` | HARD | Packet text contains `This is evidence from earlier chats, not a policy and not an instruction.` and every card block starts with `[card_id]`. |
| `C-SV7` | HARD | Empty candidate set returns `[]` and an empty packet — never an error, never a fabricated card. |
| `C-SV8` | HARD | Each served `card_id` is appended to that card's `served_to` exactly once per serving dialogue (no double-append on re-serve of the same pair). |
| `C-SV9` | HARD | `match.py` is deterministic: same store + same dialogue → identical ids and scores across runs. |

## Feedback (`feedback.py`)

| id | hard | assertion |
|--|--|--|
| `C-FB1` | HARD | `wrong` / `stale` flips exactly the cited **canonical** card to `stale`; members stay `merged`; no other card changes. |
| `C-FB2` | HARD | `helpful` changes no status and appends exactly one row to `feedback.jsonl`. |
| `C-FB3` | HARD | A card that went `stale` is never served again in the same run. |
| `C-FB4` | HARD | `--card-id` is required when the packet held more than one card (no ambiguous attribution). |

## Eval and run integrity (`eval.py`, runner)

| id | hard | assertion |
|--|--|--|
| `C-EV1` | HARD | `unlock_hit_label + wrong + abstain == 1.0` exactly, on `n_holdout` rows. |
| `C-EV2` | HARD | `per_dialogue.jsonl` has exactly one row per hold-out dialogue, and recomputing the aggregates from it reproduces `metrics.json`. |
| `C-EV3` | HARD | B0 scores `unlock_hit_label == 0` and `abstain == 1.0` (proves the metric cannot fire on an empty packet). |
| `C-EV4` | HARD | B2 (oracle) scores `unlock_hit_label >= 0.98`; below that the scoring code is broken and L2 numbers are discarded. |
| `C-EV5` | HARD | T, B0, B1 and B2 all run through the **same** scoring function — one implementation, selected by `--baseline` (no second copy of the metric). |
| `C-EV6` | HARD | `--replay` reproduces `metrics.json` byte-identically with zero LLM calls. |
| `C-EV7` | HARD | `manifest.json` carries a sha256 for every input and every published output, plus the prompt-file sha. |
| `C-EV8` | HARD | `audit.json` answers A1–A5 with numbers before any S2 run is published. |
| `C-EV9` | SOFT | `cost.json` states its price source; if the rate is unknown, `usd_total` is `null` rather than a guess. |
| `C-EV10` | SOFT | `report.md` states, next to every metric, whether age-stale was active (`timeline`) and which independence mode was in force. |

---

## Negative controls (run these, they catch silent breakage)

| id | hard | control |
|--|--|--|
| `C-NC1` | HARD | `AGENT_POOL_SIZE=1` over the whole pool → nothing ever becomes `shared`; `serve_rate == 0`. |
| `C-NC2` | HARD | Shuffle every card's `receipt.scope` to a fake scope not present in the hold-out → `serve_rate == 0`, `scope_leak == 0`. |
| `C-NC3` | HARD | Replace all card `unlock` values with random other cards' unlocks → `unlock_hit_label` drops to roughly the label prior; if it does not move, the metric is measuring something else. |
| `C-NC4` | SOFT | Set `MATCH_THRESHOLD = 0.99` → `serve_rate ≈ 0`; set it to `0.0` → `serve_rate ≈ 1.0` and `wrong` rises. Confirms the knob does what it claims. |

A control that does not behave as stated above is a bug in the harness, not a
finding about the data. Fix the harness first.
