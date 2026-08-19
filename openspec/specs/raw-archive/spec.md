# Raw Archive Specification

## Purpose

The Raw Archive is the immutable, append-only store of every raw agent session.
It is the source of truth for replay and re-processing: if the compiler's prompts
or extraction logic change, every past session can be re-compiled from here.

It stores raw turns exactly as they arrived — never derived memory.

## Requirements

### Requirement: Immutable append-only storage
The system SHALL write each session exactly once and SHALL NOT modify it after
write.

#### Scenario: Session written once
- WHEN a session is closed
- THEN the full session JSON is written to the archive
- AND the file is never modified afterwards

#### Scenario: Re-processing a historical session
- WHEN the compiler re-processes a past session
- THEN it SHALL read from the archive copy, never from live state
- AND the archive file SHALL remain byte-identical

### Requirement: Tenant-namespaced path layout
The system SHALL store each session under a deterministic path derived from
tenant and date.

#### Scenario: Path derivation
- WHEN a session from tenant `acme-corp` is archived on 2026-08-12
- THEN the file SHALL be written to `data/raw/acme-corp/2026/08/12/{session_id}.json`

#### Scenario: Tenant isolation
- WHEN two tenants archive sessions on the same day
- THEN their files SHALL live under different tenant directories
- AND one tenant's archive SHALL NOT be readable from another tenant's path

### Requirement: Atomic writes
The system SHALL write sessions atomically so a crash mid-write never leaves a
partial or corrupt file.

#### Scenario: Crash during write
- WHEN a write is interrupted before completion
- THEN the archive SHALL contain either no file or a complete file
- AND a temporary (`.tmp`) file SHALL NOT be treated as a valid session

### Requirement: Session record schema
Every archived session SHALL include identity, provenance, and the raw turns.

#### Scenario: Required fields
- WHEN a session is archived
- THEN the record SHALL include `session_id`, `tenant_id`, `source_agent`,
  `agent_group`, `started_at`, `closed_at`, and `turns`

#### Scenario: Provenance fields
- WHEN a session is archived
- THEN `source_agent` SHALL identify the agent that produced it
- AND `agent_group` SHALL identify that agent's group for scoping

### Requirement: Idempotent close
Closing an already-closed session SHALL NOT create duplicate archive files.

#### Scenario: Double close
- WHEN `ingest/close` is called twice for the same `session_id`
- THEN exactly one archive file SHALL exist
- AND the second call SHALL be a no-op or return the existing record
