# Run 2026-08-28_S0_deepseek-v4-flash
- stage: S0 | model: deepseek-v4-flash | timeline: compressed | independence: agent+dialogue (synthesized A=4)
- cluster passes fired: 1 natural (+ final --force: ran)
- age-stale: OFF by construction (compressed)

## Checks
HARD passed: 58/59; soft warnings: 1
- HARD FAIL C-EX4: grounding violations 3 over 37 fields
- SOFT warn C-IN7: agent distribution {'agent-b': 4, 'agent-a': 4, 'agent-c': 5, 'agent-d': 3} (uniform would be ~4)

## Audit (A1-A5)
- not required at this stage (S2 gate)

## Primary table (same scoring path, EVAL-PLAN §4)
| arm | unlock_hit_label | wrong | abstain | serve_rate |
|---|---|---|---|---|
| T | None | None | None | 0.0 |
| B0 | 0.0 | 0.0 | 1.0 | 0.0 |
| B1 | 0.25 | 0.5 | 0.25 | 0.75 |
| B2 | 1.0 | 0.0 | 0.0 | 1.0 |

## Secondary (T)
```json
{
 "unlock_hit_smoke": 0.0,
 "serve_rate": 0.0,
 "cluster_purity": 0.928571,
 "unlock_conflict": 1,
 "duplicate_in_packet": 0,
 "scope_leak": 0,
 "votes_hist": {
  "1": 13,
  "2": 1,
  "3+": 0
 },
 "packet_size_hist": {
  "1": 0,
  "2": 0,
  "3": 0
 },
 "extract_yield": 1.0,
 "reject_rate": 0.0,
 "cluster_rate": 0.875,
 "shared_rate": 0.071429,
 "independence": "agent+dialogue"
}
```

## Judge block
- L3 not run at this stage (S3 gate). Honesty clause applies to any judge number later: *agent-drafted, agent-judged; self-consistency floor, not human inter-rater agreement.*

## Cost
```json
{
 "extract": {
  "calls": 16,
  "prompt_tokens": 9161,
  "completion_tokens": 6446,
  "usd_total": null,
  "usd_per_1000_dialogues": null,
  "ms_p50": 3594,
  "ms_p95": 8546
 },
 "serve": {
  "ms_p50": 0,
  "ms_p95": 0
 },
 "deterministic_half_wall_clock_s": 70.766,
 "price_source": "provider rate unknown at run time; tokens reported, usd_total null (C-EV9)"
}
```

## Fitness verdict: NOT FIT (hard gate failure — run aborted, no L2 published)

## What would change the verdict: see D3 audit + D4 baselines before S2.
