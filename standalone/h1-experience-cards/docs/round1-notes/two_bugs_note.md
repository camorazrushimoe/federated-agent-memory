TWO BUGS CONFIRMED + FIXES VALIDATED ON SANDBOX COPIES — ROUND 1 · FROM: Research Engineer (verification lane)
ARTIFACT: sandbox copies (eval_fixed.py, cluster_fixed.py) + this comment

1) eval.py score_outcomes KeyError (CRITICAL — reported earlier, now confirmed with reproduction):
`score_outcomes` reads `r["true_label"]`; both row builders write `"true_unlock_guideline"`. Any non-empty packet crashes T/B1/B2. My sandbox reproduction: with a ONE-LINE fix (`r.get("true_unlock_guideline", r.get("true_label"))`), all four arms score correctly on the §10 fixtures: T {hit 0.666667, wrong 0.0, abstain 0.333333} (hit+wrong+abstain == 1.0 exactly), B0 abstain 1.0, B1 hit 1.0, B2 hit 1.0. The sibling's smoke runs never caught it because every packet was empty (all-abstain).

2) cluster.py summary `stale` count is always 0 (NEW, confirmed with instrumentation): in run_pass, `before = prev_state.get(cid)` aliases the same dict object as `canon`. `canon["status"] = "stale"` runs BEFORE `before.get("status") != "stale"` is read, so the transition is never counted (observed: store has d-10z stale, summary says stale:0). Card state is correct; only the summary count lies (report/SPEC §6.3 print contract). Fix: capture `was_status` before mutation (validated: summary now reports stale:1).

Both fixes validated on sandbox copies with zero LLM calls; neither changes any metric, only crash-resistance and count truth.

Still open from earlier flags: (a) eval.py standalone Mode A missing --baseline (AttributeError — one line: a.set_defaults(baseline="T")); (b) cost.json counts replayed raw entries as live calls; (c) manifest stores abspaths — fresh-clone quickstart replay breaks. Plus the two fixed by the integrating engineer already (replay required-args, fixture regeneration) — confirmed on disk.

BLOCKED: nothing
NEXT: awaiting the D1 branch push; then fresh-clone verification + pro-model S0.
