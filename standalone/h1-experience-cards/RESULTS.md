# RESULTS — H1 Experience Cards (deliverable skeleton, D1 layout)

> Status: **no measured numbers yet.** This file is the fixed skeleton; the
> numbers are filled from the committed reference run (D8). Nothing in the
> table is hand-typed — it is regenerated from the run dirs.

## 1. Hypothesis

Experience cards extracted from closed chats, clustered and re-served as
evidence packets, give the next agent a useful head start (higher
`unlock_hit_label`, no more `wrong` than raw retrieval) on the same data where
plain retrieval already works.

**What would falsify it:** `T ≤ B1` on `unlock_hit_label` — cards add nothing
over raw retrieval. That is a finished finding, not a failure.

## 2. Verdict

_(one of the three EVAL-PLAN §6.4 lines once S2/S3/S4 are in: FIT / FIT WITH
LIMITS / NOT FIT, with the numbers that produced it.)_

## 3. Primary table

| arm | unlock_hit_label | wrong | abstain | serve_rate | USD/1k |
|--|--|--|--|--|--|
| B0 no memory | | | | | |
| B1 raw retrieval, no cards | | | | | |
| **T card pipeline** | | | | | |
| B2 oracle | | | | | |

## 4. What the audit found (A1–A5)

_(filled at D3, before S2; any amended threshold with the number that forced
it.)_

## 5. Known limits

From `data/README.md` and the run (honest list): no PII to test the PII gate;
single vertical; single language; `unlock` is a dataset label, not a human
judgement (so `unlock_hit` is an upper-bound proxy); age-stale disabled by
construction under `timeline=compressed`; whether the `K=2` independence gate
actually bound anything (audit A3).

## 6. Judge block

_(judge pass + inter-pass agreement + calibration status, or the word
`uncalibrated`.)_

## 7. What would change the verdict

_(the single cheapest next experiment that could flip it.)_

---

**Package size:** total size of the committed package stated here at D8.
