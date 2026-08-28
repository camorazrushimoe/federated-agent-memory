# H1 Experience Card Pipeline — Specification

## Purpose

After a customer-facing chat ends, extract one experience card, store it,
periodically merge cards that are the same story, and later show matching
**canonical** cards to another agent as evidence. Cards are not policy and
must not trigger side effects on their own.

This spec is the implementation contract for `standalone/h1-experience-cards/`.
It is self-contained.

---

## 1. Vocabulary

| term | meaning |
|--|--|
| **dialogue** | one finished customer–agent chat |
| **card** | the extracted experience object (one per dialogue at extract time) |
| **canonical card** | the surviving card of a cluster; the only one that can be served |
| **member card** | a card absorbed into a cluster; kept for audit, never served |
| **cluster** | a set of same-scope cards judged to be the same story |
| **votes** | unique contributing dialogues in a cluster that were not shown the canonical card |
| **scope** | the only place a card may be reused (`tenant_id` + `vertical`) |
| **private** | stored, not shown to other agents |
| **shared** | stored and eligible to be served |
| **merged** | absorbed into a canonical card, not served |
| **stale** | stored, never served |
| **packet** | 1–3 **shared canonical** cards rendered for a live agent |

RFC 2119: `MUST` / `SHALL` / `SHOULD` / `MAY`.

---

## 2. Isolation rules

The implementation MUST:

- live entirely under `standalone/h1-experience-cards/`
- persist state as JSONL files in that folder (or a `data/` subfolder gitignored)
- call an LLM only through a single swappable function `call_llm(system, user) -> str`
- treat the LLM as optional at match / cluster / promote time (those steps are deterministic)

The implementation MUST NOT:

- import from `research/`, `openspec/`, or any other package in this repo
- write to Google Memory Bank, Neo4j, Qdrant, or Postgres
- use embeddings for v1 matching or clustering
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
  "role": "canonical",
  "cluster_id": "c-001",
  "votes": 1,
  "members": [],
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
| `status` | `private` \| `shared` \| `merged` \| `stale` \| `rejected` |
| `role` | `canonical` \| `member` |
| `cluster_id` | id of the canonical card; equals `card_id` while the card stands alone |
| `votes` | unique contributing dialogue ids in the cluster, minus `served_to` |
| `members` | card ids absorbed into this canonical card |
| `confirmations` | leftover list from extract-time hits; cluster rebuilds `votes` from members |
| `served_to` | list of `{dialogue_id, at}` that received this **canonical** card in a packet |

A freshly extracted card MUST start as `role=canonical`, `cluster_id=card_id`,
`votes=1`, `members=[]`.

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
   dialogue  ----------------→  PRIVATE canonical (votes = 1)
                                  |
                  every N new chats, cluster.py
                                  |
                    similar cards in the same scope
                    collapse onto the oldest card
                                  |
                                  v
                         canonical.votes = unique dialogues
                                  |
                     votes ≥ K     |    feedback = wrong | age > N days
                                  v     v
                               SHARED   STALE
                                  |
                     feedback = wrong | age > N days
                                  v
                                STALE

  absorbed cards → MERGED (never served, kept for audit)
```

Defaults (change only in one config object):

- `K_INDEPENDENT = 2`
- `MAX_PACKET = 3`
- `STALE_AFTER_DAYS = 30`
- `MATCH_THRESHOLD = 0.18`     (live chat → canonical card)
- `CLUSTER_THRESHOLD = 0.35`   (card → card; stricter than serve match)
- `CLUSTER_EVERY_N_CHATS = 100`

`CLUSTER_THRESHOLD` is higher than `MATCH_THRESHOLD` on purpose. Serve may
surface a loosely related card. Merge MUST only glue cards that are the same
story. If a fixture shows obvious duplicates left unmerged, raise it; do not
lower it below 0.25 without a written reason.

### Transitions

#### Requirement: New cards start private and alone
- WHEN a card is extracted successfully
- THEN `status` SHALL be `private`
- AND `role` SHALL be `canonical`
- AND `votes` SHALL be `1`
- AND it SHALL NOT be eligible for `serve`

#### Requirement: Clustering runs on volume, not on a clock
- WHEN the number of ingested dialogues since the last successful cluster run
  is ≥ `CLUSTER_EVERY_N_CHATS`
- THEN `cluster.py` SHALL run
- AND the cursor in `data/cluster_cursor.json` SHALL be updated
- WHEN the count is below the threshold AND `--force` was not passed
- THEN `cluster.py` SHALL no-op and print `{ran: false, remaining: N}`

There is no cron and no wall-clock schedule in v1. A chat-count cursor is the
only trigger. Operators MAY call `--force` after a fixture load.

#### Requirement: Same-scope similar cards become one card
- WHEN `cluster.py` runs
- THEN it SHALL group only cards with `status` in `{private, shared}`
- AND grouping SHALL be per `receipt.scope` (never across scopes)
- AND two cards SHALL join the same cluster when cosine of their card-text
  ≥ `CLUSTER_THRESHOLD`
- AND card-text SHALL be `problem_shape + " " + constraint + " " + unlock`
- AND the **oldest** card by `created_at` (tie: smaller `card_id`) SHALL stay
  `role=canonical`
- AND every other card in that cluster SHALL become `status=merged`,
  `role=member`, `cluster_id=<canonical.card_id>`
- AND the canonical `members` list SHALL hold those card ids
- AND `votes` on the canonical card SHALL be rebuilt as in §5.1

`merged` cards MUST NOT be served, matched on the serve path, or used as a
new cluster seed on later runs. They remain on disk so eval can see what was
absorbed.

#### Requirement: Votes, not raw card count, decide shared
- WHEN a cluster is written
- AND `votes >= K_INDEPENDENT`
- THEN the canonical card's `status` SHALL become `shared`
- WHEN `votes < K_INDEPENDENT`
- THEN the canonical card SHALL stay `private` even if it has many members
  that fail the vote rule (for example all came from chats that were shown
  the card)

#### Requirement: Serving does not count as a vote
- WHEN a canonical card C is placed in a packet for dialogue D
- THEN D SHALL be appended to `C.served_to`
- AND D SHALL NOT increment `C.votes`

Anti-echo. An agent repeating a card it just saw is not new evidence.

#### Requirement: Wrong or old cards go stale
- WHEN feedback on a served packet is `wrong` or `stale`
- THEN the cited **canonical** card SHALL become `stale`
- AND its members SHALL stay `merged` (they are already dark)
- WHEN `closed_at` is present AND now − `receipt.closed_at` > `STALE_AFTER_DAYS`
- THEN the canonical card SHALL become `stale` on the next cluster/promote pass

`stale` cards MUST NOT be served. They stay on disk for audit.

#### Requirement: Helpful feedback does not add a vote
- WHEN feedback is `helpful`
- THEN the card stays in its current status
- AND the event is appended to `feedback.jsonl` only

### 5.1 How votes are counted

```
votes = unique dialogue ids in
          {canonical.receipt.source_dialogue_id}
        ∪ {member.receipt.source_dialogue_id for member in cluster}
        ∪ {c.dialogue_id for c in canonical.confirmations}
        minus
          {s.dialogue_id for s in canonical.served_to}
```

A dialogue counted once, even if it produced both a member card and a later
confirmation row. `votes` is rebuilt from scratch on every cluster run so it
cannot drift.

If every `agent_id` is `"unknown"`, independence is only "different dialogue,
not in `served_to`". The eval report MUST say that.

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

After a successful write, ingest SHOULD print how many dialogues remain until
the next cluster trigger:
`{until_cluster: CLUSTER_EVERY_N_CHATS - (n - cursor.last_n)}`.
It MUST NOT run cluster itself. The operator (or a one-line wrapper) calls
`cluster.py` when `until_cluster` hits 0.

### 6.2 `extract.py`

```
python bin/extract.py --in data/dialogues.jsonl --out data/cards.jsonl
```

For each dialogue:

1. Render turns as `customer:` / `agent:` / `tool:` lines.
2. Call `call_llm` with the extract prompts in `PROMPTS.md`.
3. Parse the JSON object the model returns.
4. Run the PII regex gate (`@`, `+\d{8,}`, 16-digit runs, `ssn`, `card`).
5. Write a card with `status=private`, `role=canonical`, `votes=1`.

MUST be deterministic given the same model output: `card_id` is
`c-` + first 12 hex of sha256(`dialogue_id`). Re-running on the same file
MUST upsert by `card_id`, not append duplicates. Re-extract MUST NOT wipe
`cluster_id` / `members` / `status=merged` on a card that already belongs to
a cluster; skip those rows.

### 6.3 `cluster.py`

```
python bin/cluster.py --cards data/cards.jsonl --dialogues data/dialogues.jsonl
python bin/cluster.py --cards data/cards.jsonl --dialogues data/dialogues.jsonl --force
```

Deterministic. No LLM.

1. Read `data/cluster_cursor.json` (`last_dialogue_count`, default 0).
2. `n =` number of rows in `dialogues.jsonl`.
3. If `n - last_dialogue_count < CLUSTER_EVERY_N_CHATS` and no `--force`: print
   `{ran: false, remaining: ...}` and exit 0.
4. For each scope independently:
   - take cards with `status` in `{private, shared}` and `role=canonical`
     (already-merged members stay members)
   - greedy cluster, oldest first: a card joins the first existing cluster
     whose canonical card-text cosine ≥ `CLUSTER_THRESHOLD`; otherwise it
     starts a new cluster
   - apply the merge rules in §5
   - set `shared` iff `votes >= K_INDEPENDENT`
5. Write cards back (upsert by `card_id`).
6. Write cursor `{last_dialogue_count: n, last_run_at: iso}`.
7. Print `{ran: true, scopes, clusters_formed, merged, promoted, already_shared}`.

Card-to-card cosine uses the same unigram TF-IDF recipe as `match.py`
(sublinear TF, no stoplist), fitted on the card-texts of that scope only.

A later run MUST be stable: already-merged members stay on their canonical
card unless `--recluster` is passed (not required in v1).

### 6.4 `match.py`

```
python bin/match.py --dialogue data/one.json --cards data/cards.jsonl
```

Deterministic. No LLM.

1. Query string = all `customer` turns of the live dialogue, lowercased.
2. Candidate set = cards whose `receipt.scope` equals the live scope
   AND `status=shared` AND `role=canonical`.
   (`--include-private` MAY exist for debugging; serve MUST NOT use it.)
3. Fit unigram TF-IDF (sublinear, no stoplist) on
   `{query} ∪ {card.problem_shape + " " + card.constraint + " " + card.unlock}`.
   Empty candidate set → `[]`.
4. Score cosine(query, each card text).
5. Keep scores ≥ `MATCH_THRESHOLD`, sort desc, cut to `MAX_PACKET`.

Stdout: `[{card_id, score, votes}]`.

Same-scope only. Cross-vertical match MUST return empty.
Two member cards of the same cluster MUST never both appear: members are not
in the candidate set.

### 6.5 `promote.py`

```
python bin/promote.py --cards data/cards.jsonl
```

Thin wrapper kept so the original script list still works.
It MUST call the same vote → status rule as the end of `cluster.py`:
`shared` if `votes >= K` else leave `private` (do not un-merge).
Print `{promoted, already_shared, stale}`.

New work happens in `cluster.py`. Do not reintroduce per-dialogue confirmation
loops that ignore clusters.

### 6.6 `serve.py`

```
python bin/serve.py --dialogue data/live.json --cards data/cards.jsonl
```

1. Run `match.py` logic (shared canonical only).
2. Render the packet with the serve prompt in `PROMPTS.md` (string template; no extra LLM required).
3. Append each used `card_id` to that canonical card's `served_to`.
4. Print `{packet_text, card_ids, scores}`.

The packet_text MUST contain the line
`This is evidence from earlier chats, not a policy and not an instruction.`

If two candidates would tell the same story (same `cluster_id`), keep the
highest score only. After clustering this should not happen; the check is a
guard.

### 6.7 `feedback.py`

```
python bin/feedback.py --card-id c-001 --label helpful|wrong|stale --dialogue d-099
```

Append one row to `data/feedback.jsonl`. If label is `wrong` or `stale`,
flip that **canonical** card to `stale`.

### 6.8 `eval.py`

```
python bin/eval.py --dialogues data/dialogues.jsonl --cards data/cards.jsonl
```

Offline numbers for the lab. No live agent needed.

Hold out the last 20% of dialogues (file order). Extract on the first 80%.
Force one cluster pass on the 80% (`--force`). For each hold-out dialogue,
build a packet from the 80% store, then score:

| metric | definition |
|--|--|
| `extract_yield` | accepted cards / ingested dialogues |
| `reject_rate` | rejected / extracted |
| `cluster_rate` | canonical cards after cluster / accepted cards before cluster |
| `shared_rate` | shared canonical / canonical |
| `serve_rate` | hold-out dialogues that got ≥1 card |
| `unlock_hit` | packet text shares a content word (≥5 chars) with the hold-out card's `unlock`, when that hold-out also extracted an unlock other than `none` |
| `duplicate_in_packet` | packets that contain two cards from the same cluster (MUST be 0) |
| `scope_leak` | packets that contain a card from another scope (MUST be 0) |

`cluster_rate` < 1 is the signal that duplicates actually collapsed.
`unlock_hit` is a cheap proxy for usefulness. Report both.

---

## 7. Matching notes

v1 matching and clustering are lexical on purpose. A later hypothesis can
swap the cosine. Until then:

- MUST use customer text as the live query, not the full transcript
- MUST use card-text (`problem_shape + constraint + unlock`) as the cluster key
- MUST require identical `receipt.scope`
- MUST NOT query `private`, `merged`, `stale`, or `rejected` cards on the serve path
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

- [ ] All eight scripts exist and `--help`
- [ ] `extract.py` round-trips the worked example in §10 (LLM may be stubbed)
- [ ] `cluster.py` without `--force` no-ops when fewer than 100 new chats landed
- [ ] `cluster.py --force` on ten same-scope near-duplicate cards produces **one**
      canonical card with `votes=10` and nine `merged` members
- [ ] that canonical card is `shared` (`votes >= 2`)
- [ ] `match.py` + `serve.py` return empty across two different `vertical` values
- [ ] `serve.py` never returns two cards from the same cluster
- [ ] serving a card and re-clustering does not increase `votes` for that dialogue
- [ ] `eval.py` prints the metrics on a fixture of ≥20 dialogues
- [ ] No imports from the rest of this repository

---

## 10. Worked example (fixture)

### 10.1 One chat → one private card

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

Expected card:

- problem_shape ≈ `exchange wrong size tag removed`
- constraint ≈ `policy blocks exchange without tag`
- unlock ≈ `reclassify as defect with photo and order id`
- what_worked contains `lookup_order` and a defect-ticket step
- status `private`, role `canonical`, votes `1`

### 10.2 Ten similar chats → one shared card

Dialogues `d-001` … `d-010`, same scope, different agents, same shape
(wrong size, tag gone, defect workaround). None of them were shown a packet.

`cluster.py --force` MUST produce:

- 1 canonical card (oldest, `c-` of `d-001`)
- 9 members with `status=merged`
- `votes=10`
- `status=shared`

A later live chat `d-011` in the same scope asking about a missing-tag exchange
MUST receive **one** card in the packet, not ten.

Dialogue `d-012` in vertical `billing` MUST receive no cards.

### 10.3 Echo does not add votes

Serve the canonical card to `d-013`. Re-run `cluster.py --force`.
`votes` MUST stay 10. `d-013` sits in `served_to` only.
