# H2 — Phase C slice run (first measurement)

- run id: `2026-08-29_PhaseC_slice_deepseek-v4-flash` | stage S1-slice | tag model `deepseek-v4-flash` temp 0
- slice: 60 queries | pool: same-unlock union 320 sessions
- gold: agent-labeled (deepseek-v4-pro), NOT human gold — curated per sign-off #60

## Arms (one scoring function, EVAL-PLAN §10)

| arm | hit | wrong | abstain |
|---|---|---|---|
| B0 | 0 | 0 | 60 |
| B1 | 5 | 55 | 0 |
| B2 | 2 | 58 | 0 |
| B3 | 46 | 0 | 14 |
| T | 2 | 58 | 0 |

## Hypothesis gates (EVAL-PLAN §6)

- H2-USEFUL `T.hit > B1.hit`: T=2 vs B1=5 -> FAIL
- H2-HARM `T.wrong <= 0.25`: T.wrong=58 -> FAIL
- B0 sanity `B0.hit == 0`: B0.hit=0 -> PASS
- B3 ceiling: 46/60 (A1 pool ceiling 0.77)
- retrieve recall: 1.0 | empty: 0.0
- rotation (slice-sized): top1_share 0.33 | top3_share 1.00 | unique_served 3

## Verdict (EVAL-PLAN §6.4)

- NOT FIT (T.hit <= B1.hit: the ranker adds nothing over a random similar past session on this slice)

## Cost
- tag calls 380 (221591 in / 96492 out tokens) | packet_tokens_p50 1101 | p95 1101 | max 1101
- method: tag tokens from provider usage (raw S2 records); packet tokens len(text)//4 fallback

## Mechanism (why T lost) — verified on the run data

- **S7 learning does not transfer**: ratings are keyed `(session_id, query tag_key)`;
  60/60 query tag_keys are unique (median bucket 1) -> no query ever re-reads a
  rating written by another query. The ranker degenerates to deterministic
  tie-break (session_id asc): the same 3 smallest ids served for all 60 queries
  (unique_served=3, top3_share=1.0). This is EVAL-PLAN A3's predicted failure
  ("если почти все ключи уникальны — рейтинг «под tag_key» не накопится").
- **S3 retrieval is a non-filter this pass**: channel+vertical are constant across
  the pool -> every session passes TAG_FIELDS_MIN=2 -> 320/320 candidates per
  query; retrieve_recall=1.0 is trivial. The ranker faces the whole pool.
- **So T = arbitrary tie-break picking, B1 = random picking; random won
  (5 vs 2).** The useful sessions exist in the pool (B3 oracle 46/60 = A1), and
  S3 finds all of them — the loss is entirely in the S4 ranking / S7 schema axis.

## Next lever (cheapest first)

The slice does NOT kill whole-session hints; it kills the current ranking axis.
Cheapest first test: tag_key = problem_shape|ending only (drop constraint,
channel, vertical) OR per-vertical tag_key buckets — re-run the SAME slice with
the SAME frozen tags (zero new LLM) before any new data spend.
