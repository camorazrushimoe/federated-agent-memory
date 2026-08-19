# Contributing

We use **Spec-Driven Development (SDD)** via [OpenSpec](https://github.com/Fission-AI/openspec).

The core rule is simple: **specs before code.** We agree on *what* a component
does and *why* before anyone writes it. The spec is the contract — code follows.

---

## Why

AI agents are powerful but unpredictable when requirements live only in chat
history. A spec layer means we align on behavior before implementation, and every
engineer (and every coding agent) reads the same source of truth.

## The two directories

```
openspec/
├── specs/      # SOURCE OF TRUTH — how the system currently behaves
│   └── <component>/spec.md        # one spec per component
└── changes/    # PROPOSALS — proposed modifications, not yet merged
    └── <change-name>/
        ├── proposal.md            # why + what
        ├── design.md              # how (technical approach)
        ├── tasks.md               # implementation checklist
        └── specs/<component>/spec.md   # delta: ADDED/MODIFIED/REMOVED
```

- **`specs/`** is read-only in day-to-day work. You don't edit it to change
  behavior — you write a *change* and merge it in.
- **`changes/`** is where work happens. One folder per coherent piece of work.

## The loop

```
propose ──► review ──► implement ──► archive
```

1. **Propose** — create `changes/<name>/` with `proposal.md` + a delta spec.
2. **Review** — the team reviews the *requirements* before code is written.
3. **Implement** — follow `tasks.md`. (Code may live in this repo or another.)
4. **Archive** — merge the delta into `specs/`, move the folder to
   `changes/archive/YYYY-MM-DD-<name>/`.

The archive **is** the changelog — every archived change is a dated record of
what changed and why.

## How to write a spec

A spec has a `## Purpose`, then requirements, then scenarios:

```markdown
# <Component> Specification

## Purpose
What this component does, in one or two lines.

## Requirements

### Requirement: <Name>
The system SHALL <behavior>.

#### Scenario: <Name>
- WHEN <condition>
- THEN <expected result>
- AND <additional result>
```

- One `## Purpose` per spec.
- Requirements use RFC 2119 keywords: `SHALL` / `MUST` / `SHOULD` / `MAY`.
- Scenarios use `WHEN` / `THEN` / `AND` (optionally `GIVEN` first).
- Keep requirements **testable** — if you can't imagine a failing scenario,
  it's too vague.

**Reference template:** [`openspec/specs/raw-archive/spec.md`](openspec/specs/raw-archive/spec.md)
— copy its shape and granularity.

## How to create a change

Copy the structure of the worked example:
[`openspec/changes/add-outcome-feedback/`](openspec/changes/add-outcome-feedback/)
(`proposal.md` + `design.md` + `tasks.md` + delta spec).

The delta spec uses one of three sections:

```markdown
## ADDED Requirements
### Requirement: ...      # new behavior

## MODIFIED Requirements
### Requirement: ...      # (Previously: ...)

## REMOVED Requirements
### Requirement: ...      # (deprecated, why)
```

On archive: `ADDED` → appended to the spec, `MODIFIED` → replaced, `REMOVED` →
deleted.

## Rules of thumb

- **Never edit `openspec/specs/` directly** to change existing behavior — use a
  change. (A brand-new component's *initial* spec may be committed directly.)
- **One change = one coherent piece of work.** Two components changed for two
  reasons = two changes.
- **Decisions before specs.** If a design choice is unresolved, it's a GitHub
  issue, not a spec — see below.

## Open decisions

These are being discussed with the architect and must be resolved **before**
their specs are written:

- [#1 — switch compiler LLM from Gemma 4B to Gemini?](https://github.com/camorazrushimoe/federated-agent-memory/issues/1)
- [#2 — cross-agent contradiction resolution policy](https://github.com/camorazrushimoe/federated-agent-memory/issues/2)

## For AI coding assistants

If you're an AI agent working in this repo, read
[`AGENTS.md`](AGENTS.md) and [`openspec/AGENTS.md`](openspec/AGENTS.md) for the
machine-readable workflow.
