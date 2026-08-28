# Run 2026-08-28_S2_B1

## 1. Identity

- stage: S2; extract model: deepseek-v4-flash; timeline: compressed; agent_pool_size: 4
- git_commit: {'sha': '6359d569dd8d45d418340813775b063f989de684', 'dirty': True}
- replay_of: None
- cluster_passes_fired: 0
- config: {"K_INDEPENDENT": 2, "MAX_PACKET": 3, "STALE_AFTER_DAYS": 30, "MATCH_THRESHOLD": 0.18, "CLUSTER_THRESHOLD": 0.35, "CLUSTER_EVERY_N_CHATS": 100, "AGENT_POOL_SIZE": 4, "T0": "2026-08-28T00:00:00Z", "MAX_WORDS_FIELD": 12, "MAX_WORKED": 8}

## 2. Checks

_checks.json is a D2 deliverable; counts pending._

## 3. Audit (A1-A5)

_audit.json is a D3 deliverable; placeholder._

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

_judge pass is D6; placeholder._

## 7. Cost

```json
{
  "deterministic_half_wall_clock_s": 3.215,
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
    "thinking mode disabled on extract calls ({\"thinking\": {\"type\": \"disabled\"}}, lead decision 2026-08-28)",
    "pricing: cache-miss rates (no cache-control sent)",
    "peak window used: False (provider peak hours Mon-Fri 01:00-04:00 & 06:00-10:00 UTC)",
    "extract.calls counts pool + fixture-track raw records (fixture track active: stage=S2)"
  ],
  "price_source": "https://api-docs.deepseek.com/quick_start/pricing/ (retrieved 2026-08-28)",
  "serve": {
    "ms_p50": null,
    "ms_p95": null
  }
}
```

## 8. Fitness verdict

_pending D2-D7._

## 9. What would change the verdict

_pending._

## 11. Access log

- {"opened": "/opt/data/fam/standalone/h1-experience-cards/data/abcd_1000_pool.jsonl", "stage": "S2", "at": "2026-08-28T22:30:00Z", "purpose": "pool slice"}
- {"opened": "/opt/data/fam/standalone/h1-experience-cards/data/abcd_200_holdout.jsonl", "stage": "S2", "at": "2026-08-28T22:30:00Z", "purpose": "holdout ingest (opened exactly once)"}

## 12. Replay byte-identity (C-EV6): None
