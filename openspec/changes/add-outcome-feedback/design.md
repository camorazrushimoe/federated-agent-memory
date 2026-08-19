# Design — Outcome & Escalation Feedback (Layer 11)

## Overview

A thin new layer (L11) that captures the outcome of an agent action and routes
it back into the system as first-class memory. It closes the loop between
retrieval (L7), injection (L9), and the compiler (L3).

## Flow

```
Layer 9 (Agent Injection) → agent responds
        ↓
Layer 11 (Outcome Feedback) → agent reports outcome
        ↓
Layer 3 (Compiler) → new event type "outcome"
        ↓
Layer 4 (Graph) → OUTCOME_OF edge + helpful/not-helpful tag
        ↓
Layer 8 (Enrichment) → reputation updated from outcome success rate
```

## Data model

- **Outcome event** (compiler input):
  `{ session_id, source_agent, outcome, used_facts: [fact_id, ...], note }`
- **`OUTCOME_OF` edge** (Neo4j): agent → fact, carrying `outcome` + `timestamp`.
- **Fact tags**: `helpful` / `not_helpful` counters on the fact node.
- **Reputation**: `source_reputation = helpful / (helpful + not_helpful)`,
  cold-start neutral default `0.5`.

## Open decisions (architect)

- Should `unresolved` auto-mark used facts as `not_helpful`, or leave them
  neutral? (The failure may not be the fact's fault.)
- Does escalation create a human task queue, or just a metric?

## Technology

Reuses the existing compiler queue, Neo4j graph writes, and dashboard metrics
endpoint. No new infrastructure.
