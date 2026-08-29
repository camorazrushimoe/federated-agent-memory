# Research Report: H2 — whole past session as a hint (Phase C slice measurement)

## 1. Original brief
H2 asks: can a federated scoped-memory system push a WHOLE past customer-support
session as a hint to help a new session, and does it beat a random similar past
session? D0 defined the measurement target (agent-labeled gold, deepseek-v4-pro,
founder decision 2026-08-28). Phase A/B built the pipeline (D1/D2) and the gold
(60-query slice). **Phase C = the first actual measurement.**

## 2. Hypotheses tested
| ID | Statement | Status | Confidence |
|----|-----------|--------|------------|
| H2-D0 | Agent-labeled usefulness gold is a valid H2 target (not H1-collinear) | supported | medium |
| H2-TAG | S2 flash tags match gold tags on the slice | NOT PUBLISHED (gold_tags decision open) | — |
| H2-USEFUL | T.hit > B1.hit on the slice (ranker beats random similar past session) | **rejected (on slice)** | low (n=60) |
| H2-HARM | T.wrong ≤ 0.25 on the slice | **rejected (on slice)** | low |
| H2-ROTATION | top3_share ≤ 0.55 / explore_fill ≥ 0.15 | not measured (slice too short) | — |
| H2-COST | packet_tokens_p50 recorded; >1500 ⇒ FIT WITH LIMITS | supported (1101 ≤ 1500) | medium |

## 3. What we did
1. **Lead sign-off on the gold** (item 1): C-GD6 resolved on the canonical gold —
   d-5711 and d-4815 overridden to empty (labeler's promo/refund moves teach the
   opposite policy or repeat the query's own sequence; PII-heavy), d-3219 accepted
   empty (seed misread the query: zipper-material allergy, not width), d-1789/d-5551
   curation accepted (query already contains the answer). Re-ran checks: HARD 65/0,
   SOFT 6/0, C-GD1..8 all PASS. PR #60 merged `03121f2`.
2. **Phase C opened** (round plan comment 5462159237, bus dispatches to engineer+eval).
3. **D4 build**: `bin/eval.py` (ONE scoring function per EVAL-PLAN §10) +
   `bin/run_slice.py` (runner: S2 tag → T/B0/B1/B2/B3 → classify → S7 for T only →
   metrics/cost/audit/manifest/report; `--resume` reuses frozen tags, refuses
   completed runs to prevent S7 double-apply).
4. **Run** `runs/2026-08-29_PhaseC_slice_deepseek-v4-flash`: 60 queries, pool = 320
   same-unlock union sessions, S2 tag deepseek-v4-flash temp 0, 380 live calls,
   221,591 in / 96,492 out tokens. Fresh run + zero-LLM resume **byte-identical**;
   independent eval cross-check PASS.

## 4. Key findings
- **T 2/58/0 · B0 0/0/60 · B1 5/55/0 · B2 2/58/0 · B3 46/0/14** (hit/wrong/abstain, n=60).
- **H2-USEFUL FAIL: T.hit (2) ≤ B1.hit (5).** Per EVAL-PLAN §4.3 the ranker adds
  nothing over a random similar past session → **verdict NOT FIT** (§6.4).
- **H2-HARM FAIL: T.wrong = 58/60 = 0.97** (in the degenerate state; see mechanism).
- **B3 oracle 46/60 = 0.77 = A1 ceiling**: the pool contained the useful sessions and
  S3 found all of them (retrieve recall 1.0). The failure is NOT the data or retrieval.
- **Mechanism (verified on run data):** S7 ratings are keyed `(session_id, query
  tag_key)`, and **60/60 query tag_keys are unique** (median bucket 1) → learned
  ratings never transfer between queries → the ranker degenerates to deterministic
  tie-break and served the **same 3 session ids for all 60 queries**
  (unique_served=3, top3_share=1.0). S3 is also a non-filter (channel+vertical are
  constant → 320/320 candidates per query). This is exactly audit **A3**'s predicted
  failure ("рейтинг «под tag_key» не накопится").
- **Cost:** packet_tokens_p50 = 1101 (≤ 1500, no cost flag; ~28× a 40-word H1 card).

## 5. Limitations & risks
- n=60 slice: rotation metrics (H2-ROTATION) and tag agreement (H2-TAG) are not
  measurable here; both need the full run / a gold_tags decision.
- Gold is agent-labeled, NOT human gold (caveat rides every L2 number).
- Pool restricted to the same-unlock union (labeler universe) — full-pool noise is a
  later question.
- The NOT FIT verdict is for the CURRENT ranking axis (tag_key schema), not a proof
  that whole-session hints cannot work: B3 oracle shows the material is retrievable.

## 6. Recommendations
- **Ready for handoff?** Partially — the measurement instrument (D4) is merged and
  reproducible; the idea itself is NOT FIT as currently ranked.
- **What should be built next (cheapest first, zero new LLM spend):**
  1. Change `tag_key` to `problem_shape|ending` (drop constraint/channel/vertical) and
     re-run the SAME slice on the SAME frozen tags → does the rating axis start to
     transfer? If T > B1, pursue; if not, the ranking mechanism is the problem.
  2. Make S3 selective (channel/vertical should not be counted as matching fields) so
     the candidate set is meaningful before ranking.
- **What should NOT be built yet:** the full 1000+200 run (gated on the slice result,
   ROUND-0-PLAN §8) and any live-agent A/B.
- **Open questions:** gold_tags decision (blocks H2-TAG metrics); rotation behavior on
  a longer replay; whether session-slicing (SIMPLIFICATIONS) changes usefulness.
