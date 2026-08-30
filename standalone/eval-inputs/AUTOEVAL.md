# Auto-evaluation spec

Build a **cold-start auto-eval** for scoped session memory.
No ranker. Ranking was measured in H2v2 and added nothing (T = B1). Do not rebuild it.

What we measure: after tagging past sessions, does search return a **useful past session** for a new question?
Useful = listed in `gold_useful.jsonl` for that question. That is the ground label.
This is **packet hit**, not end-to-end answer quality.

Reference numbers from the H2v2 close-out (same pack, live tagger `deepseek-v4-flash`): retrieval recall **0.81**, packet hit **38/60 = 63%**, oracle ceiling **46/60 = 77%**.

---

## Inputs

Produce them with `python3 standalone/eval-inputs/build_ready_pack.py`.

- `dialogues_pool_320.jsonl` — 320 closed sessions (memory).
- `dialogues_slice_60.jsonl` — 60 hold-out questions.
- `gold_useful.jsonl` — per question, `useful_dialogue_ids` (may be empty).
- Closed procedure dictionary: `standalone/h2v2-categorical-scoped-memory/bin/config.py` (`PROBLEM_SHAPES`).
- Tagger prompts: that experiment's `PROMPTS.md` / `bin/tag.py`.

Do not pass `unlock` into the tagger.

---

## Pipeline (cold start)

```
1. Tag pool          320 transcripts → procedure id each
2. Tag questions     60 transcripts  → procedure id each
3. Retrieve          question id → all pool sessions with the same id
4. Pack              take up to 3 from that cell (sort by dialogue_id)
5. Score             compare pack / cell to gold_useful
```

Step 1–2 are the only LLM calls. Same tagger, temperature 0.
Persist tagged sessions as JSONL (id, tags, transcript optional).

Retrieve = exact match on `problem_shape`. Nothing else.
If the question tags as `other` or the cell is empty → empty pack → abstain.

Oracle path (ceiling, no LLM): map gold `unlock` → procedure via `MAP.md`, retrieve that cell. Used only as a reference number, not as the system under test.

---

## Labels per question

Let `G` = `useful_dialogue_ids` for the question.
Let `C` = retrieved cell (same procedure).
Let `P` = packet (≤3 ids from `C`).

| label | when |
|---|---|
| **hit** | `P ∩ G` is non-empty |
| **wrong** | pack is non-empty and `P ∩ G` is empty |
| **abstain** | pack is empty |

Also store `cell_hit` = `C ∩ G` non-empty. That isolates the tagger from packet size.

If `G` is empty, a hit is impossible. Those 14 questions are the oracle abstains. Still run them; they count in the denominator of the headline rate.

---

## Output (required)

Write a run dir, e.g. `standalone/eval-inputs/runs/<id>/`.

**Headline number** — this is the result the framework must print:

> **Packet hit rate = hits / 60**
> Example from the lab: **38/60 = 63%** of questions received at least one gold-useful session in the packet.

Print next to it, same block:

- **Oracle ceiling** = questions with `G` non-empty / 60 → lab **46/60 = 77%**. Material that exists.
- **Share of ceiling** = hits / questions-with-`G` → lab **38/46 ≈ 83%**. Of questions where value exists, how often we surface it.
- **Retrieval recall** = gold ids that landed in `C` / all gold ids across the 60. Lab **0.81**.
- counts: hit / wrong / abstain
- median `|C|`

`metrics.json` shape:

```json
{
  "n_questions": 60,
  "n_pool": 320,
  "hit": 38,
  "wrong": 22,
  "abstain": 0,
  "packet_hit_rate": 0.633,
  "oracle_ceiling": 0.767,
  "share_of_ceiling": 0.826,
  "retrieval_recall": 0.81,
  "median_cell_size": 10
}
```

Also write `per_query.jsonl`: `query_id`, tag, `|C|`, packet ids, `G`, label.

One stdout line is enough for a human:

```
packet hit 38/60 (63%) | ceiling 46/60 (77%) | 83% of available value | recall 0.81
```

---

## Out of scope

- Ranker / ratings / explore slot / outcome updates.
- Judging the agent's final reply.
- Relabeling gold.
- Growing the procedure dictionary mid-run to chase recall.

Reuse H2v2 `tag.py` + retrieve-by-`problem_shape`. Do not import the rank/update steps.
