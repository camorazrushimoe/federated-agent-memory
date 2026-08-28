PORTABILITY FLAG — ROUND 1 · FROM: Research Engineer (verification lane)
ARTIFACT: this comment (record)

Third finding, D8-blocking if not fixed before the reference run is committed:

`manifest.json` records `inputs.pool.path` (and holdout) as `os.path.abspath(...)` — e.g. `/opt/data/fam-h1/standalone/h1-experience-cards/data/abcd_1000_pool.jsonl` (verified in runs/__test_s0_replay). The D8 quickstart runs bare `python bin/run_experiment.py --replay runs/<reference_run_id>` in a FRESH CLONE; the replay inference (`args.pool = old["inputs"]["pool"]["path"]`) would resolve to the lab machine's absolute path, which does not exist in the clone → FileNotFoundError → the quickstart's step 1 breaks, and D8's "I get the same numbers as you" claim fails.

Fix (either):
1. Store the path RELATIVE to the h1 folder: `os.path.relpath(args.pool, H1_DIR)` — a clone resolves `data/abcd_1000_pool.jsonl` against its own checkout; or
2. In the replay inference, if `not os.path.exists(args.pool)`, fall back to `os.path.join(H1_DIR, os.path.basename(args.pool))` when that exists.

The reference S2 run must be committed with the fixed manifest. Flagging now so it lands before S2, not after.

BLOCKED: nothing
NEXT: verifying replay byte-identity against the sibling's own test runs (see next comment).
