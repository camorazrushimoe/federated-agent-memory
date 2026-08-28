# Reference run

**Reference run id:** _to be named when the S2 run on `deepseek-v4-flash` lands_ (D5/D8).

What makes it the reference (one line, once it exists):

> `<run_id>` — stage S2, extract model `deepseek-v4-flash`, date `YYYY-MM-DD`,
> all HARD checks green, raw extract responses committed in full, `--replay`
> reproduces `metrics.json` byte-identically in a fresh clone with zero LLM
> calls (machine + Python version stated in `RESULTS.md`).

Rules that keep this file honest:

- Exactly one run is the reference. It is the S2 run on the founder-pinned
  extract model (`deepseek-v4-flash`), committed **including** `raw/`,
  `cards.jsonl` and `packets/` — those recorded responses are the replay fuel.
- The S0 portability proof (a second model id completing stage S0) is NOT a
  reference run and NOT a measured arm; it lives as its own run dir and is
  cited in `RESULTS.md` as portability evidence only.
- If the reference run is ever re-done, this file is updated with the new id
  and the reason, and the old run dir stays on disk (history is evidence).
