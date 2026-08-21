# Federated Agent Memory

A shared, self-learning memory layer for customer-facing AI agents. Every agent
learns from every conversation — even when the customer is anonymous.

This repository is the **specification store** for the project. It holds the
architecture, the docs, and — most importantly — the OpenSpec specs that define
each component before any code is written.

> **Gemini Enterprise Hackathon · Track 2 (Custom Agent / MCP)**
>
> **Architecture v2 (2026-08-21):** we now build a *smarter memory service* on
> top of Google Memory Bank instead of a self-built storage stack. See
> [`docs/02-architecture.md`](docs/02-architecture.md) and the
> [`adopt-google-memory-bank`](openspec/changes/adopt-google-memory-bank/) change.

---

## What's inside

```
├── docs/                    # Architecture & design documentation
│   ├── 01-business-idea.md  #   one-page business pitch
│   ├── 02-architecture.md   #   component diagram (Mermaid) + L1–L10
│   ├── 03-workflow.md       #   save / retrieve / share lifecycle
│   └── prd-technical-design.md  # full PRD & technical design
├── openspec/                # Specs (source of truth) + changes (proposals)
│   ├── project.md           #   project context for AI agents
│   ├── AGENTS.md            #   OpenSpec workflow instructions
│   ├── specs/               #   current behavior, one folder per component
│   │   └── raw-archive/     #   ← the reference spec (read this first)
│   └── changes/             #   in-flight proposals (empty for now)
└── AGENTS.md                # quick start for AI agents
```

## How we work (OpenSpec)

We use [OpenSpec](https://github.com/Fission-AI/openspec) — specs before code.

- **`openspec/specs/`** — the source of truth: how each component *currently*
  behaves, written as requirements + scenarios.
- **`openspec/changes/`** — proposals: when we change a component, we create a
  change folder (`proposal.md` + delta spec + `design.md` + `tasks.md`), and on
  archive its deltas merge back into `specs/`.

> 👉 **New here?** Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full
> Spec-Driven Development workflow.

## Component spec backlog (v2)

| Component | Owner | Spec status |
|-----------|-------|-------------|
| Memory Service (ADK `BaseMemoryService` extension) | OURS | 🔄 change proposal (`adopt-google-memory-bank`) |
| Compiler (DSPy) | OURS | 🔄 change proposal |
| Ranker (rerank + novelty) | OURS | 🔄 change proposal |
| Google Memory Bank | GOOGLE | not ours to spec |
| Gemini Enterprise session scoping | GOOGLE | not ours to spec |

**Removed from v1 (replaced by Google Memory Bank):** MCP Server (L1), Raw
Archive (L2), Graph Core (L4), Vector Index (L5), Metadata Store (L6),
Retrieval Service (L7), Cross-Agent Enrichment (L8, folded into Ranker),
Agent Injection (L9), Dashboard (L10).

> **Reference example** for spec shape: `openspec/specs/raw-archive/spec.md`
> (kept as a template even though the component itself is superseded).

**When you spec a component,** open `openspec/specs/raw-archive/spec.md` and copy
its shape: `## Purpose` → `### Requirement` (with SHALL/MUST) → `#### Scenario`
(with WHEN/THEN/AND).

## Docs

Start with `docs/01-business-idea.md` for the *why*, then `docs/02-architecture.md`
for the *what*, then `docs/03-workflow.md` for the *how*.
