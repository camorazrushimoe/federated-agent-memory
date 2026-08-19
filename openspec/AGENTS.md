# OpenSpec Workflow

This project uses [OpenSpec](https://github.com/Fission-AI/openspec). Specs are
the source of truth; changes are proposals.

## The two directories

- **`openspec/specs/`** — how each component currently behaves. Organized by
  component: `specs/raw-archive/`, `specs/compiler/`, etc. One `spec.md` each.
- **`openspec/changes/`** — proposed modifications. One folder per change,
  containing `proposal.md`, a delta `specs/`, `design.md`, and `tasks.md`.
  When a change is done, its deltas merge into `specs/` and the folder moves to
  `changes/archive/`.

## Spec format

```markdown
# <Component> Specification

## Purpose
One or two lines: what this component does, why it exists.

## Requirements

### Requirement: <Name>
The system SHALL <behavior>.

#### Scenario: <Name>
- WHEN <condition>
- THEN <expected result>
- AND <additional result>
```

- One `## Purpose` per spec.
- Requirements use RFC 2119 keywords (`SHALL` / `MUST` / `SHOULD` / `MAY`).
- Scenarios use `WHEN` / `THEN` / `AND` (optionally `GIVEN` first).
- Keep requirements testable — if you can't imagine a failing scenario, it's
  too vague.

## Delta specs (inside a change)

A change's `specs/<component>/spec.md` uses delta sections:

```markdown
## ADDED Requirements
### Requirement: ...
The system SHALL ...

## MODIFIED Requirements
### Requirement: ...
The system SHALL ... (Previously: ...)

## REMOVED Requirements
### Requirement: ... (Deprecated)
```

On archive: ADDED → appended to the spec, MODIFIED → replaced, REMOVED → deleted.

## Workflow

1. **Propose** — create `changes/<name>/` with `proposal.md` + delta spec(s).
2. **Review** — the team reviews requirements before code is written.
3. **Implement** — follow `tasks.md`.
4. **Archive** — merge deltas into `specs/`, move the folder to `changes/archive/`.

## Rules

- Never edit `openspec/specs/` directly when changing existing behavior — use a
  change. (A brand-new component's *initial* spec may be committed directly.)
- One change = one coherent piece of work. If two components change for two
  reasons, that's two changes.
- `openspec/specs/raw-archive/spec.md` is the reference example — match its
  style and granularity.
