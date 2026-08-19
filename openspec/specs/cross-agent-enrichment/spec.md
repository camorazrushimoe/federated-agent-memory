# Cross-Agent Enrichment Specification

## Purpose

The Cross-Agent Enrichment Engine (L8) finds experiences from *other* agents that
are relevant to the current agent's situation, scores them, and injects the best
ones into the `memory_packet` as "enriched context".

This is how Agent A learns from Agent B without ever having seen the
conversation — the flagship mechanism of federated memory.

## Requirements

### Requirement: Enrichment scoring formula
The system SHALL score candidate enrichments with a single, fixed formula.

#### Scenario: Score computation
- WHEN a candidate enrichment is evaluated
- THEN its score SHALL be computed as
  `semantic_similarity × 0.40 + graph_proximity × 0.25 + recency_weight × 0.15
  + source_reputation × 0.10 + cross_reference × 0.10`
- AND the score SHALL be in the range 0.0–1.0

#### Scenario: Inclusion threshold
- WHEN an enrichment score is below `0.70`
- THEN the candidate SHALL be excluded from the packet

### Requirement: Cross-agent scope
The system SHALL enrich only from other agents' shared or global facts, never the
requesting agent's own memory.

#### Scenario: Exclude own agent
- WHEN searching for enrichments
- THEN facts from the requesting agent SHALL be excluded
- AND only `shared` or `global` facts with status `active` SHALL be considered

### Requirement: Item cap
The system SHALL cap the number of enrichment items to preserve the token budget.

#### Scenario: Too many matches
- WHEN more than 5 candidates pass the threshold
- THEN only the top 5 by score SHALL be included

### Requirement: Cold start — source reputation default
The system SHALL assign a neutral reputation to agents with no history.

#### Scenario: New agent
- WHEN an agent has no accuracy history
- THEN its `source_reputation` SHALL default to `0.5`

### Requirement: Cold start — cross-reference default
The system SHALL NOT penalize facts that have no cross-agent references yet.

#### Scenario: No peers
- WHEN a fact has no semantically similar facts from other agents
- THEN `cross_reference` SHALL be `0.0`
- AND the candidate SHALL remain eligible on its other scores
