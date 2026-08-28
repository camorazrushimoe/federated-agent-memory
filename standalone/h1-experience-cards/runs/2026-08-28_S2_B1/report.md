# Run 2026-08-28_S2_B1

## 1. Identity

- arm: **B1** (baseline, LLM-free; round 4/4 — founder's final-round brief)
- stage: S2 (real 200-dialogue hold-out, opened once for baseline scoring)
- created_at (pinned --now): 2026-08-28T22:30:00Z
- git_commit: {"sha": "c5e8d20e35ef3b431a427c4501ab449ff43c9915", "dirty": true}
- inputs: pool sha256 28b77a32e58932bbf1502d73975972285ec071d03f30c6ac2b5d23cd90a5abbb (1000 rows), holdout sha256 e8f453e17c6c3aa115fb2bd1498a833da383cecdcc650667ac349f903343fe3c (200 rows)
- config: MATCH_THRESHOLD=0.18 (B1), timeline=compressed, agent_pool_size=4 (defaults; no overrides)

## 2. Checks

- C-EV1 HARD: `unlock_hit_label + wrong + abstain == 1.0` -> passed (hit 0.735 + wrong 0.26 + abstain 0.005 = 1.0)
- C-EV2 HARD: per_dialogue.jsonl has one row per hold-out dialogue and recomputes metrics.json -> passed (n=200, verified by round4_baselines.py)
- C-EV5 HARD: same scoring function as T (score_outcome in bin/eval.py, selected by --baseline) -> passed by construction; no second copy of the metric exists
- C-EV9 SOFT: price source stated in cost.json -> passed
- C-EV10 SOFT: timeline + independence stated -> passed (timeline=compressed, independence=agent+dialogue)

## 3. Audit

- A2 (oracle B2 == 1.0 with the scoring code as written) is now measured on the REAL hold-out, not a slice: see the B2 run dir.

## 4. Primary table

| arm | unlock_hit_label | wrong | abstain | serve_rate |
|--|--|--|--|--|
| B1 | 0.735 | 0.26 | 0.005 | 0.995 |

## 5. Secondary metrics

```json
{
  "cluster_purity": null,
  "cluster_rate": null,
  "duplicate_in_packet": 0,
  "extract_yield": null,
  "independence": "agent+dialogue",
  "packet_size_hist": {
    "1": 0,
    "2": 0,
    "3": 0
  },
  "reject_rate": null,
  "scope_leak": 0,
  "serve_rate": 0.995,
  "shared_rate": null,
  "unlock_conflict": null,
  "unlock_hit_smoke": 0.81,
  "votes_hist": {
    "1": 0,
    "2": 0,
    "3+": 0
  }
}
```

## 6. Judge (L3)

_Not applicable: baseline arms score against ground truth; no cards exist to judge._

## 7. Cost

```json
{
  "deterministic_half_wall_clock_s": 1.609,
  "extract": {
    "calls": 0,
    "completion_tokens": 0,
    "ms_p50": 0,
    "ms_p95": 0,
    "prompt_tokens": 0,
    "usd_per_1000_dialogues": 0.0,
    "usd_total": 0.0
  },
  "notes": [
    "baseline arm: ZERO LLM calls by construction (calls=0, usd=0.0); cost recorded for completeness per RUN-PROTOCOL \u00a74.3",
    "serve latency null: baseline arms have no packet serve path (B1 scoring is in-memory TF-IDF inside eval.py)"
  ],
  "price_source": "https://api-docs.deepseek.com/quick_start/pricing/ (retrieved 2026-08-28)",
  "serve": {
    "ms_p50": null,
    "ms_p95": null
  }
}
```

## 8. Fitness verdict

_Baseline measurement only; the treatment verdict lives in RESULTS.md (D3 gate: T not run). This number is the comparison the hypothesis is judged against._

## 9. What would change the verdict

_See RESULTS.md: the 'T <= B1' line is resolved by measurement in this round._

## 10. Access log

- {"opened": "/opt/data/federated-agent-memory/standalone/h1-experience-cards/data/abcd_1000_pool.jsonl", "stage": "S2", "at": "2026-08-28T22:30:00Z", "purpose": "pool slice (baseline B1 retrieval pool)"}
- {"opened": "/opt/data/federated-agent-memory/standalone/h1-experience-cards/data/abcd_200_holdout.jsonl", "stage": "S2", "at": "2026-08-28T22:30:00Z", "purpose": "holdout ingest (opened exactly once, baseline scoring)"}

## 11. Honesty note: per_dialogue.jsonl is the per-hold-out record; metrics.json aggregates are recomputed from it (C-EV2) and asserted by this script

