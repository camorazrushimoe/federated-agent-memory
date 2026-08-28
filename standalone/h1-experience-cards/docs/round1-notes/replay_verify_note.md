REPLAY MECHANISM VERIFIED + TWO ACCOUNTING BUGS — ROUND 1 · FROM: Research Engineer (verification lane)
ARTIFACT: sandbox replay runs (zero LLM calls) + this comment

1) REPLAY DETERMINISM: PROVEN. Replayed the sibling's own runs/__test_s0_replay2 into a sandbox dir (0.5s wall, no API key in env, so any live call would have failed loudly):
- per_dialogue.jsonl: sha d5451532... == d5451532... BYTE-IDENTICAL
- metrics.json: identical modulo the run_id field only (run_id = basename of --replay target; chain semantics — my replay-of-a-replay stamps the intermediate id). Replay of the REFERENCE run itself (a real run, not a chain) will carry the reference run's own id → fully byte-identical metrics.json.
- Zero-LLM-call proof: with H1_API_KEY/H1_BASE_URL/LLM_BASE_URL/CUSTOM_API_KEY all unset, the replay completed rc=0 with identical outputs. A live call would have needed a key.

2) BUG (cost.json, replay): build_cost counts raw/extract entries with usage as `calls` — a replayed run re-records its raw files from the source (usage preserved) and therefore reports `extract.calls = 16` although it made ZERO live calls (`replayed: true`). This breaks the zero-call claim in cost.json and will break C-EX10's "count equals calls" reading on replay runs. Fix: when `replayed=true`, count only entries that were LIVE in this run (the runner knows: live calls happen only when replay_dir is None — either skip the count or record a `live_calls` field; tokens may still be reported from recorded usage).

3) BUG (manifest.json, portability — flagged earlier, restating with evidence): inputs.pool.path is stored as abspath (/opt/data/fam-h1/...). A fresh clone cannot resolve it → bare quickstart `--replay runs/<id>` fails with FileNotFoundError. Store relpath from the h1 folder (or fall back to H1_DIR/basename in the replay inference). The committed reference run must have the fixed manifest.

Both are small, deterministic, and land before S2 — they do not change any metric; they change what a clone can re-derive.

BLOCKED: nothing
NEXT: eval.py Mode A --baseline fix (flagged earlier) + the two above; then fresh-clone verification of the real S0 run.
