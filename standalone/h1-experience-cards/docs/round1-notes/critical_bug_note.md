CRITICAL BUG — scoring path crashes on any non-empty packet · FROM: Research Engineer (verification lane)
ARTIFACT: sandbox eval test (zero LLM) + this comment

bin/eval.py: `score_outcomes` reads `r["true_label"]` (line 92) but BOTH row builders write `"true_unlock_guideline"` — `make_rows_from_packets` (line 267) and `baseline_rows` (lines 293/298/319). Consequences:
- B0 passes only because its rows are all abstain (the label is never read on the abstain branch).
- **T, B1 and B2 crash with `KeyError: 'true_label'` the moment any packet is non-empty.**
- The sibling's smoke runs (__test_s0_replay2 etc.) all scored {0,0,1} abstain — empty packets — so the crash is hidden at S0 scale. S1/S2 WILL hit it, and the S2 reference run would die mid-eval.

Fix (one line): in score_outcomes, read `r.get("true_unlock_guideline")` (fallback `r.get("true_label")`) — or rename the builders' key. I validated this exact fix on a sandbox copy of eval.py: T/B0/B1/B2 all score without crashing (see below).

VALIDATION (sandbox copy, zero LLM): T arm on 3 hold-out dialogues with real matches → no crash, hit/wrong/abstain computed; B0 abstain=1.0; B2 oracle → hit=1.0; B1 scores normally.

Also still open from earlier flags: (a) eval.py standalone Mode A missing --baseline (AttributeError); (b) cost.json counts replayed raw entries as calls; (c) manifest stores abspaths (fresh-clone quickstart replay would break).

BLOCKED: nothing
NEXT: re-running the full sandbox eval with the patched copy to confirm all four arms; awaiting S0.
