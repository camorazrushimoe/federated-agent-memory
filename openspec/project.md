# Project Context

## What we're building

**Federated Agent Memory** — an MCP server that gives AI agents long-term memory
and makes that memory *collaborative across agents*.

The problem: every AI agent has amnesia — each session starts blank, and what an
agent learns dies when the chat closes. We build a memory layer that collects,
structures, and shares knowledge across agents, so when one agent solves
something, every other agent can reuse it next time.

Three key ideas:

1. **Federate** — every memory event is tagged `private` (one agent), `shared`
   (a group), or `global` (org-wide).
2. **Compile** — a DSPy pipeline turns raw conversation turns into structured
   memory (facts, decisions, tasks, entities, preferences).
3. **Enrich** — cross-agent enrichment surfaces *other* agents' relevant
   experience in every new session.

## Components (L1–L10)

| # | Component | Responsibility |
|---|-----------|----------------|
| L1 | MCP Server | Single entry point: ingest / retrieve / search / status. MCP-native + REST fallback. |
| L2 | Raw Archive | Immutable append-only store of every raw session. |
| L3 | Memory Compiler | 8-step DSPy pipeline: turns → structured memory events. |
| L4 | Graph Core | Temporal knowledge graph (Neo4j + Graphiti): entities, facts, provenance. |
| L5 | Vector Index | Embeddings (Qdrant) for semantic search, split by visibility scope. |
| L6 | Metadata Store | Relational bookkeeping (PostgreSQL): agents, sessions, entities, fact lifecycle. |
| L7 | Retrieval Service | Hybrid query + fusion → compact `memory_packet`. |
| L8 | Cross-Agent Enrichment | Finds other agents' relevant experience, scores and injects it. |
| L9 | Agent Injection | Formats and injects the `memory_packet` into the agent's prompt. |
| L10 | Dashboard | Live ops view: health, growth, scopes, quality signals. |

See `docs/02-architecture.md` for the full diagram.

## Tech stack

- **Ingest**: FastAPI + MCP Python SDK
- **Compiler**: DSPy + Instructor + Gemini (swappable local model)
- **Graph**: Neo4j 5 + Graphiti
- **Vector**: Qdrant
- **Metadata**: PostgreSQL 16
- **NLP/embeddings**: spaCy, sentence-transformers
- **Infra**: Docker Compose

## Conventions

- Specs are the source of truth; one folder per component under `openspec/specs/`.
- Requirements use RFC 2119 keywords; every requirement has WHEN/THEN scenarios.
- `openspec/specs/raw-archive/spec.md` is the reference example — match its
  style and granularity when writing new specs.
- Multi-tenancy (Layer 0) is documented in the PRD but out of scope for the MVP.
