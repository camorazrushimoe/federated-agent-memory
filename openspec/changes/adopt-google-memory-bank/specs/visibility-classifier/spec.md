# Delta — Visibility Classifier

## MODIFIED Requirements

### Requirement: Scope classification
**Modified.** Scope classification moves into the Compiler, and enforcement is
delegated to Gemini Enterprise session scoping instead of a custom graph label.

#### Scenario: Classifying an event
- WHEN a memory event is compiled
- THEN the Compiler SHALL assign exactly one scope (`private`, `shared`, `global`)
- AND the scope SHALL be enforced through Gemini Enterprise session scoping

#### Scenario: Shared target groups
- WHEN an event is classified `shared`
- THEN it SHALL be associated with the relevant agent group via session scoping
- AND agents outside that group SHALL NOT read it

### Requirement: Default to private on uncertainty
**Unchanged.** The system still fails closed to `private` on low confidence.

### Requirement: Global classification audit
**Modified.** Audit records are emitted via GCP logging instead of a custom
dashboard.

#### Scenario: Global event recorded
- WHEN an event is classified `global`
- THEN an audit entry SHALL be written to GCP structured logging
  (event, source agent, reasoning, time)

### Requirement: Sensitive-topic blocklist
**Unchanged.** Blocklisted topics still force `private` regardless of content.

### Requirement: Fail closed
**Unchanged.** A classifier failure still defaults the event to `private`.
