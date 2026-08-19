# Visibility Classifier Specification

## Purpose

The Visibility Classifier is the final step (step 8) of the Memory Compiler (L3).
It assigns a visibility scope — `private`, `shared`, or `global` — to every
compiled memory event, and decides which groups may read `shared` events.

It exists to federate memory *safely*: the right knowledge reaches the right
agents, and nothing leaks beyond its intended audience.

## Requirements

### Requirement: Scope classification
The system SHALL classify every memory event into exactly one of `private`,
`shared`, or `global`.

#### Scenario: Classifying an event
- WHEN a memory event is compiled
- THEN the classifier SHALL assign exactly one scope
- AND record a confidence score with it

#### Scenario: Shared target groups
- WHEN an event is classified `shared`
- THEN the classifier SHALL assign one or more `target_groups`
- AND agents outside those groups SHALL NOT read it

### Requirement: Default to private on uncertainty
The system SHALL default to `private` whenever it is not confident enough to
share safely.

#### Scenario: Low confidence
- WHEN the classifier's confidence for `shared` or `global` is below threshold
- THEN the event SHALL be classified `private`
- AND it SHALL NOT be exposed to other agents

#### Scenario: Ambiguous scope
- WHEN the classifier cannot decide between scopes
- THEN `private` SHALL win by default

### Requirement: Global classification audit
The system SHALL emit an audit record whenever an event is classified `global`.

#### Scenario: Global event recorded
- WHEN an event is classified `global`
- THEN an audit entry SHALL be recorded (event, source agent, reasoning, time)
- AND it SHALL be visible in the audit log / dashboard

### Requirement: Sensitive-topic blocklist
The system SHALL NOT auto-share events that touch sensitive topics.

#### Scenario: Blocked topic
- WHEN a memory event matches a blocklisted topic (salary, medical, legal, PII)
- THEN the event SHALL be classified `private` regardless of content
- AND the blocklist match SHALL be recorded in the audit log

### Requirement: Fail closed
The system SHALL fail closed — never open — when the classifier itself fails.

#### Scenario: Classifier unavailable
- WHEN the classifier errors or times out
- THEN the event SHALL be classified `private`
- AND compilation of other events SHALL NOT be blocked
