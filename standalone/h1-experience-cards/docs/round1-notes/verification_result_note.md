VERIFICATION RESULT — ROUND 1 · FROM: Research Engineer (verification lane)
ARTIFACT: sandbox smoke test (zero LLM calls, canned fixture responses) + this comment

Ran the integrated bin/ through a zero-LLM sandbox test (ingest fixtures → extract from fixtures/raw_extract → cluster --force → serve d-011/d-012/d-013 → feedback wrong → re-serve). Current state:

PASSING (against SPEC §10 + CHECKS):
- §10.2: d-001..d-013 (same scope, two agents) → 1 canonical d-001, 9+2 members merged, votes=7, status=shared. Serve d-011 → exactly 1 card [c-216689894762], score 0.347.
- Cross-vertical: serve d-012 (billing) → 0 cards.
- Freshness: d-10x/d-10y cluster last_closed_at=08-27 → NOT stale (shared); d-10z/d-10w quiet cluster → stale.
- Inheritance: d-x1 unlock=none → inherited 'reset password with security questions' from d-x2.
- Rejection: d-rej1 (empty problem_shape) and d-rej2 (both none + empty what_worked) → rejected.
- PII: d-pii what_worked email scrubbed, contains_pii=true, no example.com in the card; d-gift ('gift card') contains_pii=false; d-001 has no '4412' in any field.
- Feedback: wrong → canonical stale → re-serve returns [].

ONE REAL BUG (bin/eval.py): standalone Mode A crashes — `AttributeError: 'Namespace' object has no attribute 'baseline'` in finalize_mode_b. The `standalone` subparser does not define --baseline but finalize_mode_b reads args.baseline unconditionally. The runner's `score` mode (Mode B) is unaffected. Fix is one line (set_defaults(baseline="T") on the standalone parser, or getattr in finalize). This bites SPEC §6.8 standalone eval and any fixture eval that routes through Mode A.

NOTE (my sandbox script, not the code): I initially asserted votes==6 for the §10.2 cluster; actual is votes=7 because d-011/d-013 (same scope, same canned story, agents a/b) correctly join the cluster. votes>=2 per SPEC §10.2 — code is right, my assertion was wrong.

EARLIER FLAG (from my first audit pass, still open): run_experiment.py --replay requires --pool/--holdout/--model/--stage (argparse required=True). The DELIVERABLE-PACKAGE.md §3 quickstart runs bare `python bin/run_experiment.py --replay runs/<reference_run_id>` — that will fail until replay relaxes the required args (they should come from the original manifest). Please confirm the fix lands before the PR.

BLOCKED: nothing
NEXT: awaiting the sibling's local test / S0; will re-run the sandbox and then the two executed done-criteria (fresh-clone replay byte-identity, deepseek-v4-pro S0) when the branch is pushed.
