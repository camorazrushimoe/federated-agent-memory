# Delta — Outcome Feedback

## ADDED Requirements

### Requirement: Outcome reporting
The system SHALL accept an outcome report from an agent after it acts on a
`memory_packet`.

#### Scenario: Agent reports outcome
- WHEN an agent reports an outcome for a session
- THEN the report SHALL include one of `resolved`, `escalated`,
  `handed_off_to_human`, or `unresolved`
- AND SHALL reference the fact(s) the agent used

### Requirement: Outcome graph edge
The system SHALL link each outcome to the facts the agent used.

#### Scenario: Outcome linked to facts
- WHEN an outcome is recorded
- THEN an `OUTCOME_OF` edge SHALL be created between the agent and each
  referenced fact
- AND the edge SHALL carry the outcome value and timestamp

### Requirement: Helpfulness tagging
The system SHALL tag source facts based on the outcome.

#### Scenario: Resolved outcome
- WHEN the outcome is `resolved`
- THEN the used facts SHALL be tagged `helpful`

#### Scenario: Unresolved outcome
- WHEN the outcome is `unresolved`
- THEN the used facts SHALL be tagged `not_helpful`

### Requirement: Reputation from outcomes
The system SHALL update source reputation from the outcome success rate.

#### Scenario: Reputation update
- WHEN outcomes accumulate for an agent
- THEN `source_reputation` SHALL equal the ratio of helpful to total outcomes
- AND SHALL default to `0.5` before any outcomes exist

### Requirement: Dashboard outcome metrics
The system SHALL expose resolution and escalation rates on the dashboard.

#### Scenario: Metrics available
- WHEN the dashboard loads
- THEN it SHALL display resolution rate and escalation rate, per agent and overall
