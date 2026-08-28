# Run 2026-08-28_S2_baseline_B1

## 1. Identity

- stage: S2; arm: B1; timeline: compressed; agent_pool_size: 4; extract_model: none (baseline arm)
- git_commit: {"sha": "c5e8d20e35ef3b431a427c4501ab449ff43c9915", "dirty": false}
- config: {"K_INDEPENDENT": 2, "MAX_PACKET": 3, "STALE_AFTER_DAYS": 30, "MATCH_THRESHOLD": 0.18, "CLUSTER_THRESHOLD": 0.35, "CLUSTER_EVERY_N_CHATS": 100, "AGENT_POOL_SIZE": 4, "T0": "2026-08-28T00:00:00Z", "MAX_WORDS_FIELD": 12, "MAX_WORKED": 8}

## 2. Checks

_Card-store checks (CHECKS.md) are not applicable to a baseline arm: no cards.jsonl exists, nothing was extracted, clustered, served or promoted. Scoring-path check C-EV5 is structural (one score_outcome in eval.py) and is verified by the repo state itself._

## 3. Audit (A1-A5)

_A1-A5 live in the committed audit.json (D3); the only audit item this run measures is A2 — the B2 oracle — verified in the B2 arm run dir._

## 4. Primary table (T vs baselines, same hold-out)

| arm | unlock_hit_label | wrong | abstain | serve_rate |
|---|---|---|---|---|
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

_null — no cards, no judge._

## 7. Cost

```json
{
  "deterministic_half_wall_clock_s": 1.767,
  "extract": {
    "calls": 0,
    "completion_tokens": 0,
    "ms_p50": null,
    "ms_p95": null,
    "prompt_tokens": 0,
    "usd_per_1000_dialogues": 0.0,
    "usd_total": 0.0
  },
  "notes": [
    "baseline arm: no extract, no serve, zero LLM calls by construction; usd_total = 0"
  ],
  "price_source": "https://api-docs.deepseek.com/quick_start/pricing/ (retrieved 2026-08-28)",
  "serve": {
    "ms_p50": null,
    "ms_p95": null
  }
}
```

## 8. Fitness verdict

_Baseline arms carry no verdict; the verdict lives in RESULTS.md §2/§3._

## 9. What would change the verdict

_n/a (baseline)._
