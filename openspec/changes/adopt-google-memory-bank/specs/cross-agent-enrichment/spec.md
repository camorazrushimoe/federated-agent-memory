# Delta — Cross-Agent Enrichment

## MODIFIED Requirements

### Requirement: Enrichment scoring formula
**Modified.** Cross-agent enrichment becomes a responsibility of the Ranker.
Scores are computed over memory retrieved from Google Memory Bank, and the
`graph_proximity` term is removed (there is no self-managed graph).

#### Scenario: Score computation
- WHEN a candidate enrichment is evaluated
- THEN its score SHALL be computed as
  `semantic_similarity × 0.50 + recency_weight × 0.25 + source_reputation × 0.15
  + novelty × 0.10`
- AND the score SHALL be in the range 0.0–1.0

#### Scenario: Inclusion threshold
- WHEN an enrichment score is below `0.70`
- THEN the candidate SHALL be excluded from the packet

### Requirement: Cross-agent scope
**Modified.** The requesting agent's own memory is still excluded, but scope is
enforced via Gemini Enterprise session scoping rather than custom graph labels.

#### Scenario: Exclude own agent
- WHEN searching for enrichments
- THEN entries from the requesting agent SHALL be excluded
- AND only `shared` or `global` entries SHALL be considered

### Requirement: Item cap
**Unchanged.** The system still caps enrichment items to preserve the token budget.

### Requirement: Cold start — source reputation default
**Unchanged.** New agents still default to a neutral `source_reputation` of `0.5`.

### Requirement: Cold start — cross-reference default
**Removed.** With no self-managed graph, `cross_reference` no longer applies.
