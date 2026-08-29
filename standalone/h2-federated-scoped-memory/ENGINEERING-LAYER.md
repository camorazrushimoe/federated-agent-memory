# H2 engineering layer

Work-split for four engineers while the lab run is still in flight.
This file is the *how we cut the work*. Logic, schemas, prompts, and checks stay in the existing specs — do not restate them here.

Read first: [`README.md`](./README.md) → [`SPEC.md`](./SPEC.md) → [`PROMPTS.md`](./PROMPTS.md) → [`CHECKS.md`](./CHECKS.md). Acceptance is a fixture rerun, not a diff review.

---

## Plan

Do not start four components on day one. Freeze a thin skeleton, then split.

### Day 0 — skeleton (one owner, half a day)

One person lands the shared floor everyone else imports:

- schemas: Dialogue, Session, Rating, Candidate, Ranked, Packet, Outcome, Serve
- config from SPEC §6 (`MAX_PACKET`, `EXPLORE_SLOTS`, deltas, decay)
- `call_llm(system, user) -> str` (env only: `H2_API_KEY`, `H2_BASE_URL`, `--model`)
- transcript render (`PROMPTS.md` §1) and PII scrub (SPEC §4)
- `tag_key` and deterministic `session_id`
- JSONL IO with upsert by id
- prompts copied from `PROMPTS.md`, not rewritten

Until this exists, nobody writes a script. After it exists, the four tracks below run in parallel against [`fixtures/`](./fixtures/).

### Then — four tracks

| Track | Component | Scripts | Can start from |
|---|---|---|---|
| A | Compiler / Tagger | `tag.py` | skeleton + fixtures |
| B | Retriever + Ranker | `retrieve.py`, `rank.py` | skeleton + `tagged_sessions.jsonl` |
| C | Mixer + Feedback | `mix.py`, `outcome.py`, `update.py` | skeleton + ranked/gold fixtures |
| D | Runtime | `ingest.py`, pool JSONL, `replay.py`, eval harness | skeleton + the other CLIs as they land |

One component, one owner. The author does not accept their own track. No second `bin/`.

### Done when

Each track is done when its CHECKS ids are green on fixtures. The slice is done when `replay.py` walks S3–S5 → S6 → S7 → S2 on fixtures without inventing logic of its own.

---

## Components

Four coarse pieces. Scripts inside a component stay separate (one input, one output, one check) — do not fold `tag + retrieve + rank` into one call.

### Compiler / Tagger

Turns a closed dialogue into a memory unit: the **whole session plus tags**.

- Input: Dialogue. Output: Session + seed Rating row (`score=0`).
- Only required LLM call in v1. Prompts: `PROMPTS.md` §2–§3. Parse: §4.
- Copies `channel` / `vertical` from the dialogue. Model does not invent them.
- Scrubs PII. Rejects only if `problem_shape` is empty after scrub.
- Writes `raw/tag/<dialogue_id>.json`.

If tags are bad, the ranker is not at fault.

### Retriever + Ranker

Finds similar sessions, then decides what to show.

**Retriever** (`retrieve.py`)

- Match ≥ `TAG_FIELDS_MIN` tag fields. No embeddings, no LLM (delegate untagged queries to Compiler).
- Drop self-matches. Ignore `tenant_id`. Order does not matter here.

**Ranker** (`rank.py`)

- Reads rating for `(session_id, query tag_key)`. Missing row = `score=0`.
- First `MAX_PACKET - EXPLORE_SLOTS` slots = highest score.
- Last slot = explore (fewest `shows`, then oldest `last_shown_at`, then smaller `session_id`).
- No score cutoff. No LLM. Formula may change later; slot contract should not.

### Mixer + Feedback

Serves the packet and closes the learning loop.

**Mixer** (`mix.py`)

- Builds the agent packet from ranked ids. Unit is a **whole past session**, not a card.
- Text is the `PROMPTS.md` §5 template only. Empty rank → header-only packet.
- Logs `serves.jsonl`.

**Outcome** (`outcome.py`)

- Labels the query `good | bad | unclear`.
- Lab default: `--source gold` (intersection with `useful_dialogue_ids`). LLM helper is a separate mode and must not mix into experiment numbers.

**Updater** (`update.py`)

- Moves score only for sessions that were actually in the packet, only under the query `tag_key`.
- Applies good/bad/unclear deltas, then decay every `DECAY_EVERY_SHOWS`.

### Runtime

Glue and storage. No ranking brain.

- **Ingest** — normalize raw chats to SPEC §3, drop chats with no customer turn, strip H1-only gold fields.
- **Pool** — `sessions.jsonl` + `ratings.jsonl`. One writer. Rating key is `(session_id, tag_key)`, not a global session score.
- **Replay** — time-order the corpus; on each dialogue call S3–S5 → S6 → S7 → S2. Must not add prompts or extra rules.
- **Eval** — HARD checks from `CHECKS.md`, plus the four scores in `EVAL-PLAN.md` (tag quality, packet utility vs B0–B3, rotation, token cost).

Replay order matters: a session must not mix into itself or train on the future. Empty packets on the first dialogues are expected.

---

## Contracts

Schemas and file names live in SPEC §3–§9. Do not invent parallel types.

Stitch points:

```
Ingest        → Dialogue
Compiler      → Session + Rating seed
Retriever     → Candidates
Ranker        → Ranked (≤ MAX_PACKET)
Mixer         → Packet { packet_text, session_ids } + Serve
Outcome       → Outcome { good|bad|unclear, source }
Updater       → Ratings'
```

Invariants to fail a track on, even before a full run: `C-SELF`, `C-FUTURE`, `C-PII`, `C-SIZE`, `C-DELTA`, `C-PROMPT`, `C-ISO4`.

---

## Out of scope for this slice

Tenants, agent groups, private/shared/global, embeddings, session chunking, story merge, Memory Bank / Qdrant / Neo4j, H1 or GitLab-POC imports, extra system/user text on top of `PROMPTS.md`.

Those wait until the lab answers whether a whole similar session as a hint is worth the tokens.
