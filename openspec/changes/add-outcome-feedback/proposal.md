# Add Outcome & Escalation Feedback (Layer 11)

## Why

Today, when an agent acts on a `memory_packet`, nothing captures whether the
memory actually helped. Layer 9 injects the packet and the story ends — we never
learn if the suggested fact was useful, if the task was resolved, or if the agent
got stuck and escalated to a human. Failures disappear instead of becoming memory.

This closes the loop: outcomes feed back into the compiler and the graph, so the
system learns what worked and what didn't.

## What Changes

1. Add a new **outcome** event type to the compiler (L3): after acting, an agent
   reports `resolved`, `escalated`, `handed_off_to_human`, or `unresolved`.
2. Add a new graph edge (L4): `(:Agent)-[:OUTCOME_OF]->(:Fact)` linking an
   outcome to the fact(s) the agent used.
3. Tag the source fact as `helpful` / `not_helpful` based on the outcome.
4. Update `source_reputation` in the enrichment engine (L8) using outcome
   success rate — rank facts by whether they *worked*, not just whether they
   were used.
5. Add resolution / escalation metrics to the dashboard (L10).

## Non-goals

- No automatic re-training of the compiler in this change.
- No cross-tenant aggregation.
