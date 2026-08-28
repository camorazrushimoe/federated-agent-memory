# H1 Experience Cards — Model Matrix

One row per extract model. Built by `bin/compare.py` from `metrics.json` +
`cost.json` in each run dir (D7) — **no hand-typed numbers in this table,
ever** (RUN-PROTOCOL §5, DELIVERABLE-PACKAGE §6).

Columns: `unlock_hit_label`, `wrong`, `abstain`, `serve_rate`,
`cluster_purity`, `reject_rate`, judge `faithful`, USD/1000 dialogues,
p50 latency, verdict.

| model | unlock_hit_label | wrong | abstain | serve_rate | cluster_purity | reject_rate | judge faithful | USD/1k | p50 ms | verdict |
|--|--|--|--|--|--|--|--|--|--|--|
| _pending_ | | | | | | | | | | |

Pass 1 is single-arm: the extract slot is decided (`EVAL-PLAN.md` §8) and no
second model is invented to fill the table. The portability S0 run on a
second model id is evidence that a new arm costs one command, not a row here.

---

## Add an arm in three steps

```
1. python bin/run_experiment.py --stage S2 --model <new-model> --out runs/<date>_S2_<model>
2. python bin/compare.py runs/*/ > MODEL-MATRIX.md
3. read the new row next to B1 — if the new arm is at or below B1, the cards
   add nothing on that model, and that is the finding
```
