# H1 Experience Cards — Results

> Status: **no measured run yet** (D1 build in progress). Every line below is
> the committed structure; numbers are filled from the reference run when it
> lands (D8). No number in this file is ever hand-typed — each comes from a
> run dir (`metrics.json` / `cost.json`) or from `compare.py`.

## 1. Hypothesis

Experience cards extracted from finished chats, clustered into shared
canonical stories, and served as evidence packets to a later agent beat raw
retrieval of the past chat (B1) on naming the right `unlock_guideline` for a
hold-out dialogue.

**What would falsify it:** `T ≤ B1` on `unlock_hit_label` — the cards add
nothing over plain retrieval. That is a complete result.

## 2. Verdict

_One of the three EVAL-PLAN §6.4 lines, with the numbers that produced it._
Placeholder until the reference run:

> **NOT YET MEASURED** — pending the S2 run on `deepseek-v4-flash` (reference
> run, D5) and the D3 audit gate.

## 3. Primary table (T next to every baseline)

| arm | unlock_hit_label | wrong | abstain | serve_rate | USD/1k |
|--|--|--|--|--|--|
| B0 no memory | _pending_ | _pending_ | _pending_ | _pending_ | 0 |
| B1 raw retrieval, no cards | _pending_ | _pending_ | _pending_ | _pending_ | 0 |
| **T card pipeline** | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |
| B2 oracle | _pending_ | _pending_ | _pending_ | _pending_ | 0 |

## 4. What the audit found (A1–A5)

_Each item answered with numbers from `audit.json`, before any S2 run (D3 gate).
Any threshold amended here with the arithmetic that forced it._

## 5. Known limits

Copied honestly from `data/README.md` and the run (no PII to test the PII
gate; single vertical; single language; `unlock` is a dataset label, not a
human judgement; age-stale disabled by construction under
`timeline=compressed`; whether the `K=2` independence gate actually bound).

## 6. Judge block

_Inter-pass agreement and calibration status, or the word `uncalibrated`
(EVAL-PLAN §5). Pending D6._

## 7. What would change the verdict

_The single cheapest next experiment that could flip the verdict. Filled at
D8 with the measured deltas (e.g. `T - B1` and the extraction cost)._

---

## Package facts

- Total size of the committed package: _stated at D8_.
- Machine + Python version where `--replay` was proven byte-identical:
  _stated at D8_.
