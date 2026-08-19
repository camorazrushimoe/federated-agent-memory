# Federated Agent Memory

A shared, self-learning memory layer for customer-facing AI agents. Every agent
learns from every conversation — even when the customer is anonymous.

This repository is the **specification store** for the project. It holds the
architecture, the docs, and — most importantly — the OpenSpec specs that define
each component before any code is written.

> **Gemini Enterprise Hackathon · Track 2 (Custom Agent / MCP)**

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

## Component spec backlog

| # | Component | Spec status |
|---|-----------|-------------|
| L1 | MCP Server | 📋 to spec |
| **L2** | **Raw Archive** | ✅ **reference example** |
| L3 | Memory Compiler (DSPy) | 📋 to spec |
| L4 | Graph Core (Neo4j + Graphiti) | 📋 to spec |
| L5 | Vector Index (Qdrant) | 📋 to spec |
| L6 | Metadata Store (PostgreSQL) | 📋 to spec |
| L7 | Retrieval Service | 📋 to spec |
| L8 | Cross-Agent Enrichment | 📋 to spec |
| L9 | Agent Injection | 📋 to spec |
| L10 | Dashboard & Observability | 📋 to spec |

**When you spec a component,** open `openspec/specs/raw-archive/spec.md` and copy
its shape: `## Purpose` → `### Requirement` (with SHALL/MUST) → `#### Scenario`
(with WHEN/THEN/AND).

## Docs

Start with `docs/01-business-idea.md` for the *why*, then `docs/02-architecture.md`
for the *what*, then `docs/03-workflow.md` for the *how*.
