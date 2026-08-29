# H2 Phase C — slice run report (n=60)

## 1. Run identity
- run dir: `2026-08-29_PhaseC2_tagkey_shape-ending` (RUN-PROTOCOL §3)
- stage: S2 (slice) · arm: T/B0/B1/B2/B3 · tag model: deepseek-v4-flash, temp 0
- gold: `data/gold_useful.jsonl` canonical (main @ 03121f2, sign-off #60) — agent-labeled gold (deepseek-v4-pro) — NOT human gold
- audit: A1 = 0.7667, A4 proxy = 1.0, A5 pairs = 60 rows / 46 non-empty / 393 pairs, A6 = 720

## 1b. A3 recheck (Round 3 coarse tag_key, lead dispatch 13:34Z)
- pool sessions: 380, unique tag_keys: 340, median bucket size: 1 (success criterion: median > 1)

## 2. Checks
- HARD 10 passed / 0 failed / 0 deferred; SOFT 1 / 0

## 3. Audit A1-A6
- **A1**: 0.7667
- **A2**: N/A (gold_tags not authorized — ROUND-0-PLAN §8)
- **A3**: N/A (gold_tags not authorized)
- **A4**: N/A (gold_tags not authorized); proxy below on the unlock-universe
- **A5**: 60 rows / 46 non-empty / 393 pairs
- **A6**: 720
- ROTATION_BURN_IN = 0

## 4. Arms (L2 usefulness, agent-labeled gold — NOT human gold)

| arm | hit | wrong | abstain | n |
|---|---|---|---|---|
| B0 | 0.0 | 0.0 | 1.0 | 60 |
| B1 | 0.0333 | 0.9667 | 0.0 | 60 |
| B2 | 0.0667 | 0.9333 | 0.0 | 60 |
| B3 | 0.7667 | 0.0 | 0.2333 | 60 |
| T | 0.0667 | 0.9333 | 0.0 | 60 |

*Every L2-usefulness number above: agent-labeled gold (deepseek-v4-pro) — NOT human gold*

**Primary read:** T.hit = 0.0667 vs B1.hit = 0.0333 on the same n=60

**Round 3 re-test (lead dispatch 2026-08-29 13:34Z):** the S4/S7 RATING key was coarsened from the 5-field tag_key (problem_shape|constraint|ending|channel|vertical) to problem_shape|ending only (config.TAG_KEY_FIELDS), S3 matching unchanged (5 TAG_FIELDS, TAG_FIELDS_MIN=2), re-run from the SAME frozen S2 raw records (replay, zero new LLM). Result: metrics.json is byte-identical to the R1 slice run (sha 6ac43ff0…), T packet ids 0/60 changed. The fix is applied (query tag_keys in the run state are the coarse 2-field keys) but the 60 slice queries have 58 unique problem_shape|ending buckets — rating cells still almost never collide across queries, so S7 deltas have no second query to transfer to and the ranker still degenerates to the same tie-break. The prerequisite for the coarse rating key to do anything (repeated buckets across queries — audit A3's predicted failure mode) is not met by the slice; a run where queries share shape/ending buckets (full 1000+200 corpus) would exercise it.

**Diagnostic (why the numbers look like this):** `channel=web` and `vertical=customer-support` are constant across all 380 pool sessions, so with TAG_FIELDS_MIN=2 **every session is an S3 candidate for every query** (n_candidates 320-380 per query). The ranker sees the whole pool, all scores start at 0, and ties break deterministically (shows → last_shown_at → id), so T serves the same ~7 sessions repeatedly (unique_served=7, top3_share=0.9667, explore_fill=0.0167). T ≈ B2 (0.0667 vs 0.0667) because the explore slot almost never differs from the top-by-score pick. B3 = 0.7667 = A1 confirms the data ceiling is healthy — the failure is in S3 tag-matching granularity, not the gold or the corpus. Thinnest lever: retrieval (tag schema / TAG_FIELDS_MIN), not the ranker, not rotation tuning (LAB-BRIEF §6 symptom map).

## 5. Tagging
S2 ran (deepseek-v4-flash, temp 0) as part of the measured loop; tag-vs-gold agreement is NOT published this round — gold_tags is not authorized yet (ROUND-0-PLAN §8).

## 6. Rotation (slice-sized caveat)
- unique_served=7 top1_share=0.3222 top3_share=0.9667 explore_fill=0.0167 explore_promote=0 decay_fired=0
- burn-in = 0; n=60 slice — rotation gates are suggestive, not conclusive (full-length rotation belongs to the 1000+200 run).

## 7. Cost
- `tag_calls` = 0
- `tag_tokens_in` = 0
- `tag_tokens_out` = 0
- `tag_usd_per_1000` = None
- `tag_latency_p50` = None
- `tag_latency_p95` = None
- `packet_tokens_p50` = 1069
- `packet_tokens_p95` = 1069
- `packet_tokens_max` = 1069
- `packet_tokens_per_query_mean` = 1063.7
- `implied_agent_usd_per_1000` = None
- `serve_latency_p50` = 156.0
- `serve_latency_p95` = 167.0
- `token_method` = recompute-from-frozen-tags: zero new S2 calls; tag usage re-derived from frozen raw/tag records in replay_of=runs/2026-08-29_PhaseC_slice_deepseek-v4-flash
- `price_source` = None

## 8. Verdict
**FIT WITH LIMITS — T.wrong 0.9333 > 0.25 (whole-session harm; lever: S3 retrieval — channel/vertical constant ⇒ TAG_FIELDS_MIN=2 degenerates to whole-pool candidates); top3_share 0.9667 > 0.55 (rotation dead; lever: retrieval granularity first, not explore tuning); explore_fill 0.0167 < 0.15 (explore slot never differs under whole-pool candidates)**

*L2 numbers in this report are agent-labeled gold (deepseek-v4-pro) — NOT human gold*
