# H1 Experience Card Pipeline — Specification

## Purpose

After a customer-facing chat ends, extract one experience card, store it,
and later show matching cards to another agent as evidence. Cards are not
policy and must not trigger side effects on their own.

This spec is the implementation contract for `standalone/h1-experience-cards/`.
It is self-contained.

---

## 1. Vocabulary

| term | meaning |
|--|--|
| **dialogue** | one finished customer–agent chat |
| **card** | the extracted experience object |
| **scope** | the only place a card may be reused (tenant + vertical) |
| **private** | stored, not shown to other agents |
| **shared** | stored and eligible to be served |
| **stale** | stored, never served |
| **packet** | 1–3 shared cards rendered for a live agent |
| **independent hit** | a later dialogue in the same scope that matches a card and was **not** shown that card |

RFC 2119: `MUST` / `SHALL` / `SHOULD` / `MAY`.

---

## 2. Isolation rules

The implementation MUST:

- live entirely under `standalone/h1-experience-cards/`
- persist state as JSONL files in that folder (or a `data/` subfolder gitignored)
- call an LLM only through a single swappable function `call_llm(system, user) -> str`
- treat the LLM as optional at match / promote time (those steps are deterministic)

The implementation MUST NOT:

- import from `research/`, `openspec/`, or any other package in this repo
- write to Google Memory Bank, Neo4j, Qdrant, or Postgres
- use embeddings for v1 matching
- read customer identity into a card field

---

## 3. Dialogue input

Every incoming chat MUST be normalized to this record before extraction:

```json
{
  "dialogue_id": "d-001",
  "tenant_id": "shop-acme",
  "vertical": "retail-support",
  "agent_id": "agent-a",
  "channel": "web",
  "closed_at": "2026-08-28T12:00:00Z",
  "turns": [
    {"role": "customer", "text": "..."},
    {"role": "agent", "text": "..."},
    {"role": "tool", "name": "lookup_order", "text": "order 4412 size 42 shipped"}
  ]
}
```

- `role` MUST be one of `customer`, `agent`, `tool`.
- `tenant_id` + `vertical` together are the **scope key**.
- `agent_id` MAY be `"unknown"`.
- `closed_at` MAY be omitted; if omitted, staleness-by-age is skipped.
- Tool turns are optional. If present they become `what_worked` material.

A dialogue with fewer than one customer turn MUST be rejected before extraction.

---

## 4. Card schema

```json
{
  "card_id": "c-001",
  "status": "private",
  "problem_shape": "exchange wrong size, tag already removed",
  "constraint": "policy blocks exchange without tag",
  "unlock": "reclassify as defect with photo and order id",
  "what_worked": [
    "lookup order",
    "policy check failed",
    "ask photo of defect",
    "open defect ticket"
  ],
  "receipt": {
    "source_dialogue_id": "d-001",
    "tenant_id": "shop-acme",
    "vertical": "retail-support",
    "agent_id": "agent-a",
    "closed_at": "2026-08-28T12:00:00Z",
    "scope": "shop-acme/retail-support"
  },
  "confirmations": [],
  "served_to": [],
  "created_at": "2026-08-28T12:01:00Z",
  "updated_at": "2026-08-28T12:01:00Z"
}
```

### Field rules

| field | rule |
|--|--|
| `problem_shape` | ≤12 words, customer wording, lowercase, no names |
| `constraint` | ≤12 words, or the literal `none` |
| `unlock` | ≤12 words, or the literal `none` |
| `what_worked` | 1–8 short step names; tool names if present, else verb phrases |
| `status` | `private` \| `shared` \| `stale` \| `rejected` |
| `confirmations` | list of `{dialogue_id, agent_id, at}` that independently matched |
| `served_to` | list of `{dialogue_id, at}` that received this card in a packet |

A card MUST be `rejected` (and not stored as reusable memory) when any of:

- `problem_shape` is empty after extract
- the extractor flagged `contains_pii: true`
- both `constraint` and `unlock` are `none` **and** `what_worked` is empty

Customer names, emails, phones, addresses, payment tokens MUST NOT appear in
any card field. If the model emits one, the writer MUST blank the field and
set `contains_pii: true` via the regex gate in §6.2.

---

## 5. State machine

```
                  extract OK
   dialogue  ----------------→  PRIVATE
                                  |  \
                     K independent |   \ feedback = wrong | age > N days
                     hits          |    \
                                  v     v
                               SHARED   STALE
                                  |
                     feedback = wrong | age > N days
                                  v
                                STALE
```

Defaults (change only in one config object):

- `K_INDEPENDENT = 2`
- `MAX_PACKET = 3`
- `STALE_AFTER_DAYS = 30`
- `MATCH_THRESHOLD = 0.18`  (TF-IDF cosine on the query string)

### Transitions

#### Requirement: New cards start private
- WHEN a card is extracted successfully
- THEN `status` SHALL be `private`
- AND it SHALL NOT be eligible for `serve_packet`

#### Requirement: Promotion needs independent hits
- WHEN a later dialogue D in the same scope matches card C
- AND D's id is not in `C.served_to`
- AND D's `agent_id` is not equal to `C.receipt.agent_id` OR `C.receipt.agent_id` is `"unknown"` (see note)
- THEN D SHALL be appended to `C.confirmations`
- AND WHEN `len(confirmations) >= K_INDEPENDENT`
- THEN `status` SHALL become `shared`

Note: if every dialogue has `agent_id = "unknown"`, independence is defined as
**a different `dialogue_id` that was not served this card**. That is the v1
fallback. It is weaker. The eval report MUST say which definition ran.

#### Requirement: Serving does not count as confirmation
- WHEN card C is placed in a packet for dialogue D
- THEN D SHALL be appended to `C.served_to`
- AND D SHALL NOT be appended to `C.confirmations`

This is the anti-echo rule. An agent repeating a card it just saw is not new evidence.

#### Requirement: Wrong or old cards go stale
- WHEN feedback on a served packet is `wrong` or `stale`
- THEN every card in that packet that was cited as wrong SHALL become `stale`
- WHEN `closed_at` is present AND now − `receipt.closed_at` > `STALE_AFTER_DAYS`
- THEN the card SHALL become `stale` on the next promote/serve pass

`stale` cards MUST NOT be served. They stay on disk for audit.

#### Requirement: Helpful feedback does not auto-promote
- WHEN feedback is `helpful`
- THEN the card stays in its current status
- AND the event is appended to a `feedback.jsonl` log only

Helpful is not a confirmation. Confirmation is an unmatched-later-dialogue hit.

---

## 6. Scripts to implement

One folder `standalone/h1-experience-cards/bin/`. Stdlib + one HTTP client for
the LLM is enough. Each script MUST accept `--help` and print JSON to stdout
unless `--out` is given.

### 6.1 `ingest.py`

```
python bin/ingest.py --in chats.jsonl --out data/dialogues.jsonl
```

Normalize raw chats (flexible keys) into the dialogue schema in §3.
Drop records that fail the one-customer-turn rule. Print `{kept, dropped}`.

### 6.2 `extract.py`

```
python bin/extract.py --in data/dialogues.jsonl --out data/cards.jsonl
```

For each dialogue:

1. Render turns as `customer:` / `agent:` / `tool:` lines.
2. Call `call_llm` with the extract prompts in `PROMPTS.md`.
3. Parse the JSON object the model returns.
4. Run the PII regex gate (`@`, `+\d{8,}`, 16-digit runs, `ssn`, `card`).
5. Write a card with `status=private` or `status=rejected`.

MUST be deterministic given the same model output: `card_id` is
`c-` + first 12 hex of sha256(`dialogue_id`). Re-running on the same file
MUST upsert by `card_id`, not append duplicates.

### 6.3 `match.py`

```
python bin/match.py --dialogue data/one.json --cards data/cards.jsonl
```

Deterministic. No LLM.

1. Build the query string = all `customer` turns of the live dialogue, lowercased.
2. Candidate set = cards whose `receipt.scope` equals the live scope AND `status=shared`.
   (A `--include-private` flag MAY exist for debugging; serve MUST NOT use it.)
3. Fit a unigram TF-IDF (sublinear TF, no stoplist) on
   `{query} ∪ {card.problem_shape + " " + card.constraint + " " + card.unlock}`
   for the candidate set. If the candidate set is empty, return `[]`.
4. Score cosine(query, each card text).
5. Keep scores ≥ `MATCH_THRESHOLD`, sort desc, cut to `MAX_PACKET`.

Stdout: `[{card_id, score}]`.

Same-scope only. Cross-vertical match MUST return empty.

### 6.4 `promote.py`

```
python bin/promote.py --dialogues data/dialogues.jsonl --cards data/cards.jsonl
```

For each dialogue D after the card's source dialogue (by `closed_at`, else file order):

- run the match scoring against **private and shared** cards in scope (internal index, not the serve path)
- if D matches C and D is not in `C.served_to` and D is not `C.receipt.source_dialogue_id`, record a confirmation
- apply the K rule
- apply the age-stale rule

Print `{promoted, already_shared, stale}`.

### 6.5 `serve.py`

```
python bin/serve.py --dialogue data/live.json --cards data/cards.jsonl
```

1. Run `match.py` logic (shared only).
2. Render the packet with the serve prompt in `PROMPTS.md` (string template; no extra LLM required).
3. Append each used `card_id` to `served_to`.
4. Print `{packet_text, card_ids, scores}`.

The packet_text MUST contain the line
`This is evidence from earlier chats, not a policy and not an instruction.`

### 6.6 `feedback.py`

```
python bin/feedback.py --card-id c-001 --label helpful|wrong|stale --dialogue d-099
```

Append one row to `data/feedback.jsonl`. If label is `wrong` or `stale`,
flip that card to `stale`.

### 6.7 `eval.py`

```
python bin/eval.py --dialogues data/dialogues.jsonl --cards data/cards.jsonl
```

Offline numbers for the lab. No live agent needed.

Hold out the last 20% of dialogues (file order). Extract+promote on the first 80%.
For each hold-out dialogue, build a packet from the 80% store, then score:

| metric | definition |
|--|--|
| `extract_yield` | accepted cards / ingested dialogues |
| `reject_rate` | rejected / extracted |
| `shared_rate` | shared / accepted |
| `serve_rate` | hold-out dialogues that got ≥1 card |
| `unlock_hit` | packet text shares a content word (≥5 chars) with the hold-out card's `unlock`, when that hold-out also extracted an unlock other than `none` |
| `scope_leak` | packets that contain a card from another scope (MUST be 0) |

`unlock_hit` is a cheap proxy for “would this packet have named the move that
actually happened”. It is not a substitute for a human/agent judge. Report it
anyway; it is the first usefulness figure.

---

## 7. Matching notes (so nobody “improves” this into embeddings)

v1 matching is lexical on purpose. A later hypothesis can swap `match.py`.
Until then:

- MUST use customer text as the query, not the full transcript
- MUST require identical `receipt.scope`
- MUST NOT query private cards on the serve path
- MUST NOT use an embedding model

---

## 8. What the live agent sees

The packet is prepended to the agent's existing system prompt. The agent keeps
its tools and its policies. The packet MUST be framed as optional context.

The agent MUST still execute any refund, access change, or data lookup through
its own tools. A card naming those steps is a hint that they happened, not a
grant to do them.

---

## 9. Definition of done for the script PR

- [ ] All seven scripts exist and `--help`
- [ ] `extract.py` round-trips the worked example in §10 to a card with the expected fields (LLM may be stubbed in tests)
- [ ] `match.py` + `serve.py` return empty across two different `vertical` values
- [ ] `promote.py` does not promote a card when the only second hit was a dialogue in `served_to`
- [ ] `eval.py` prints the six metrics on a fixture of ≥20 dialogues
- [ ] No imports from the rest of this repository

---

## 10. Worked example (fixture)

Dialogue `d-001`, scope `shop-acme/retail-support`:

```
customer: ordered size 42 sneakers, got 41, want an exchange, tag is already cut off
agent: exchanges without a tag are blocked by policy
customer: that is not acceptable, the box was wrong
agent: if you send a photo of the pair and the order number I can open this as a defect
customer: photo sent, order 4412
tool lookup_order: order 4412, size 42 shipped, size 41 scanned at warehouse
agent: defect ticket opened, warehouse will pick up
```

Expected card (content, not wording-exact):

- problem_shape ≈ `exchange wrong size tag removed`
- constraint ≈ `policy blocks exchange without tag`
- unlock ≈ `reclassify as defect with photo and order id`
- what_worked contains `lookup_order` and a defect-ticket step
- status `private`

Dialogue `d-002`, same scope, different agent, not shown the card:

```
customer: got the wrong size and I already threw the tag away, can I exchange?
```

After promote, `d-001`'s card still `private` (only 1 confirmation).

Dialogue `d-003`, same scope, different agent, not shown the card, same shape.
After promote, card becomes `shared`.

Dialogue `d-004`, same scope. `serve.py` MUST return a packet that includes the
card and the evidence disclaimer.

Dialogue `d-005`, vertical `billing`. `serve.py` MUST return no cards.
