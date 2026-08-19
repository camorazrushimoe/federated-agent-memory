# Agent Instructions

You are working on **Federated Agent Memory** — a shared, self-learning memory
layer for customer-facing AI agents.

## Start here

1. Read `openspec/project.md` for project context and component boundaries.
2. Read `openspec/AGENTS.md` for the OpenSpec workflow you must follow.
3. Read `docs/02-architecture.md` for the component diagram (L1–L10).

## The one rule that matters

**Specs before code.** Every component's behavior is defined in
`openspec/specs/<component>/spec.md` *before* it is implemented.

- The reference template is `openspec/specs/raw-archive/spec.md`.
- New behavior = a change folder in `openspec/changes/`, never a direct edit to
  `openspec/specs/` (unless it's a brand-new component's initial spec).

## Conventions

- Requirements use RFC 2119 keywords: `SHALL`, `MUST`, `SHOULD`, `MAY`.
- Every requirement has at least one scenario (`WHEN` / `THEN` / `AND`).
- Docs are plain Markdown; diagrams are Mermaid (render in GitHub & Obsidian).
