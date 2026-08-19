# Federated Agent Memory — PRD & High-Level Technical Design

**Version:** 0.1 · **Status:** Draft  
**Hackathon:** Gemini Enterprise Hackathon · Track 2 — Custom Agent Challenge (MCP)  
**Team:** Sergey Ryabushko (Lead, Architecture, DSPy), Azam Turgunboev  
**Codebase:** [graphiti-memory-system](https://github.com/camorazrushimoe/flat-white)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Case: Enterprise AI at Scale](#2-business-case-enterprise-ai-at-scale)
3. [Core Innovation: Federated Agent Memory](#3-core-innovation-federated-agent-memory)
4. [Architecture Overview](#4-architecture-overview)
5. [Layer-by-Layer Breakdown](#5-layer-by-layer-breakdown)
   - [Layer 0 — Enterprise Tenant & Isolation](#layer-0--enterprise-tenant--isolation)
   - [Layer 1 — Agent Hook (MCP Server)](#layer-1--agent-hook-mcp-server)
   - [Layer 2 — Raw Archive](#layer-2--raw-archive)
   - [Layer 3 — Memory Compiler](#layer-3--memory-compiler)
   - [Layer 4 — Federated Graph Core](#layer-4--federated-graph-core)
   - [Layer 5 — Vector Index](#layer-5--vector-index)
   - [Layer 6 — Metadata Store](#layer-6--metadata-store)
   - [Layer 7 — Federated Retrieval Service](#layer-7--federated-retrieval-service)
   - [Layer 8 — Cross-Agent Enrichment Engine](#layer-8--cross-agent-enrichment-engine)
   - [Layer 9 — Agent Injection](#layer-9--agent-injection)
   - [Layer 10 — Dashboard & Observability](#layer-10--dashboard--observability)
6. [Technology Stack Summary](#6-technology-stack-summary)
7. [Hackathon MVP Scope](#7-hackathon-mvp-scope)

---

## 1. Executive Summary

**Federated Agent Memory** is an MCP server that gives AI agents long-term memory — and makes that memory *collaborative across agents*.

Every AI agent today suffers from the same disease: **amnesia**. Each session starts blank. Claude doesn't remember what Pi figured out yesterday. The support agent doesn't know what the sales agent promised last week. This isn't just annoying — at enterprise scale, it's a **liability**.

We solve this with a **self-learning, multi-agent knowledge fabric**:

- **Ingest** — conversations from any agent (Claude, Gemini, Pi, custom) stream into a unified pipeline in real time
- **Compile** — a DSPy-powered compiler extracts decisions, facts, tasks, entities, and preferences from raw dialogue
- **Store** — everything lands in a temporal knowledge graph (Neo4j) with vector embeddings (Qdrant) for semantic search
- **Federate** — each memory event is automatically classified as **private** (one agent), **shared** (team/department), or **global** (org-wide)
- **Retrieve** — before every new session, the agent receives a compact `memory_packet` drawn from its own memory + shared team knowledge + global org knowledge
- **Enrich** — the **Cross-Agent Enrichment Engine** lets Agent A benefit from Agent B's experience, even when they work in different departments

**What makes this different:** Existing memory systems (Mem0, Letta, basic Graphiti) are *single-agent*. They treat memory as a private notebook. We treat it as a **shared organizational asset** — like a corporate wiki that writes itself, optimized for AI consumption.

**Why this wins the hackathon:**
- Not a napkin idea — **working code exists** (5 Docker containers, 33 tests, real DSPy pipeline)
- Solves a **real, painful problem** that every enterprise adopting AI agents will hit within weeks
- **Self-improving** via DSPy optimization — the compiler gets better as you use it
- **MCP-native** — plug-and-play for any Gemini Enterprise agent, zero code changes

---

## 2. Business Case: Enterprise AI at Scale

### 2.1 The Setting

Imagine **AcmeCorp**, a mid-size enterprise (~2,000 employees) that has embraced AI agents across the organization. They deploy four specialized agents:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ACMECORP AI AGENTS                           │
├───────────────┬──────────────┬────────────────┬─────────────────────┤
│  CUSTOMER     │   INTERNAL   │     SALES      │    ENGINEERING      │
│  SUPPORT      │     HR       │   ASSISTANT    │    ASSISTANT        │
│  AGENT        │   AGENT      │    AGENT       │     AGENT           │
├───────────────┼──────────────┼────────────────┼─────────────────────┤
│ • Handles     │ • Answers    │ • Product info │ • Code review       │
│   tickets     │   benefits   │ • Pricing      │ • Architecture      │
│ • Troubleshoot│   questions  │ • Competitive  │   decisions         │
│ • SLA tracking│ • Onboarding │   intel        │ • Incident          │
│ • Escalations │ • Time-off   │ • Deal support │   response          │
├───────────────┼──────────────┼────────────────┼─────────────────────┤
│ Talks to:     │ Talks to:    │ Talks to:      │ Talks to:           │
│ Customers     │ Employees    │ Sales team     │ Developers          │
└───────────────┴──────────────┴────────────────┴─────────────────────┘
```

### 2.2 The Problem: Memory Silos

Each agent exists in a **vacuum**. Here's what goes wrong:

| Scenario | What Happens | What Should Happen |
|----------|-------------|-------------------|
| **Customer X calls Support** about a login bug | Support Agent troubleshoots from scratch, files a ticket | Support Agent instantly knows: Engineering Agent discussed this exact bug 3 days ago, fix is in progress |
| **Sales Agent pitches** Customer X a premium feature | Sales Agent is unaware Customer X has 3 open support tickets | Sales Agent knows Customer X is frustrated, adjusts the pitch accordingly |
| **New engineer asks** Engineering Agent about auth system | Engineering Agent explains from scratch | Engineering Agent recalls that HR Agent recently onboarded 5 backend engineers who asked the same questions |
| **HR Agent handles** a benefits question | HR Agent answers generically | HR Agent remembers that Sales Agent previously discussed this employee's promotion — benefits package is changing |
| **Support Agent solves** a tricky edge case | Knowledge stays with Support Agent only | Engineering Agent learns the edge case and adds it to the test suite automatically |

The **root cause**: agents have no shared memory. Each one is a brilliant specialist with total amnesia about what every other agent knows.

### 2.3 The Solution: Federated Memory

```
┌─────────────────────────────────────────────────────────────────────┐
│                   FEDERATED AGENT MEMORY LAYER                        │
│                                                                       │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│   │ SUPPORT  │   │   HR     │   │  SALES   │   │   ENG    │        │
│   │  AGENT   │   │  AGENT   │   │  AGENT   │   │  AGENT   │        │
│   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘        │
│        │              │              │              │               │
│        ▼              ▼              ▼              ▼               │
│   ┌─────────────────────────────────────────────────────────┐      │
│   │              MCP SERVER (Ingest + Retrieve)              │      │
│   └──────────────────────────┬──────────────────────────────┘      │
│                              │                                      │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│        ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│        │ PRIVATE  │   │  SHARED  │   │  GLOBAL  │                  │
│        │  MEMORY  │   │  MEMORY  │   │  MEMORY  │                  │
│        │ (per     │   │ (per     │   │ (org-    │                  │
│        │  agent)  │   │  group)  │   │  wide)   │                  │
│        └──────────┘   └──────────┘   └──────────┘                  │
│                              │                                      │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│        ┌─────────────────────────────────────────────┐             │
│        │        CROSS-AGENT ENRICHMENT ENGINE         │             │
│        │  "Agent A learns from Agent B's experience"  │             │
│        └─────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

**The key insight:** memory is not just a private notebook — it's a **shared organizational asset**. When the Support Agent solves a tricky bug, that knowledge doesn't die in a Slack thread. It becomes part of the Engineering Agent's available context the next time someone asks about that subsystem.

### 2.4 Business Value

| Metric | Before Federated Memory | After Federated Memory |
|--------|------------------------|------------------------|
| **Avg. support resolution time** | 45 min | 12 min (agent recalls past solutions) |
| **Sales deal context accuracy** | 60% | 95% (sales agent knows support history) |
| **Onboarding question repetition** | 8x per new hire | 1x (HR agent recalls previous answers) |
| **Cross-team knowledge transfer** | Manual (Slack, wiki) | Automatic (enrichment engine) |
| **New agent ramp-up time** | 2 weeks | 2 days (inherits shared memory) |

---

## 3. Core Innovation: Federated Agent Memory

This section explains the **novel mechanism** that extends the base Graphiti memory system into a federated, multi-agent platform.

### 3.1 Memory Scope Model

Every memory event is tagged with a **visibility scope** at ingest time:

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMORY SCOPE HIERARCHY                         │
│                                                                   │
│   ┌───────────────────────────────────────────────────────────┐  │
│   │                     GLOBAL (org-wide)                       │  │
│   │   • Company policies, public product info, org structure   │  │
│   │   • Readable by: ALL agents                                │  │
│   │   • Example: "AcmeCorp SLA is 4 hours for enterprise tier" │  │
│   └───────────────────────┬───────────────────────────────────┘  │
│                           │                                       │
│   ┌───────────────────────▼───────────────────────────────────┐  │
│   │                  SHARED (department/group)                  │  │
│   │   • Team workflows, domain knowledge, internal processes   │  │
│   │   • Readable by: agents in same group                      │  │
│   │   • Example: "Login bug fixed in v2.4, root cause: NPE"   │  │
│   └───────────────────────┬───────────────────────────────────┘  │
│                           │                                       │
│   ┌───────────────────────▼───────────────────────────────────┐  │
│   │                   PRIVATE (per agent)                       │  │
│   │   • Agent-specific preferences, personal workflow nuances  │  │
│   │   • Readable by: ONLY this agent                           │  │
│   │   • Example: "Customer X prefers email, not phone calls"   │  │
│   └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Visibility Classifier (DSPy Module)

A DSPy-powered classifier runs at the end of the compiler pipeline (after Memory Selector). It decides the scope of each memory event:

```python
class ClassifyVisibility(dspy.Signature):
    """Determine the appropriate visibility scope for a memory event.
    
    Rules:
    - PRIVATE: agent-specific workflow preferences, personal notes, 
               single-interaction details with no cross-agent value
    - SHARED: team-relevant knowledge, domain-specific solutions, 
              processes that benefit colleagues in the same group
    - GLOBAL: org-wide facts, policies, entity information useful 
              across departments
    """
    memory_event_text: str = dspy.InputField()
    event_type: str = dspy.InputField()         # decision, fact, task, preference, etc.
    source_agent_role: str = dspy.InputField()  # "support", "sales", "hr", "engineering"
    entities_involved: list[str] = dspy.InputField()
    
    visibility: Literal["private", "shared", "global"] = dspy.OutputField()
    target_groups: list[str] = dspy.OutputField()  # e.g., ["support", "engineering"]
    reasoning: str = dspy.OutputField()             # why this scope was chosen
```

**Example classifications:**

| Memory Event | Type | Source Agent | → Visibility | Target Groups |
|-------------|------|-------------|-------------|---------------|
| "Customer X prefers email over phone" | preference | support | **private** | — |
| "Login bug root cause: stale JWT cache" | fact | support | **shared** | [support, engineering] |
| "Enterprise SLA: 4-hour response for tier-1" | fact | sales | **global** | — |
| "Our auth microservice uses RS256, not HS256" | decision | engineering | **shared** | [engineering, support] |
| "Q3 company offsite: Sept 15-17" | fact | hr | **global** | — |

### 3.3 Federated Retrieval Model

When an agent starts a new session, the retrieval service runs **three parallel queries** and merges results:

```
    Agent Query: "Customer X is having login issues"
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ PRIVATE  │   │  SHARED  │   │  GLOBAL  │
   │  SCOPE   │   │  SCOPE   │   │  SCOPE   │
   │          │   │          │   │          │
   │ Agent's  │   │ Support  │   │ All org  │
   │ own      │   │ group    │   │ memory   │
   │ memory   │   │ memory   │   │          │
   └────┬─────┘   └────┬─────┘   └────┬─────┘
        │              │              │
        ▼              ▼              ▼
   ┌─────────────────────────────────────────┐
   │         RESULT FUSION & RANKING          │
   │  • Deduplicate across scopes             │
   │  • Rank by: relevance + recency + scope  │
   │  • Private > Shared > Global for ties    │
   │  • Truncate to token budget              │
   └────────────────────┬────────────────────┘
                        │
                        ▼
                 memory_packet
```

**Recency weighting:**

| Age | Weight | Rationale |
|-----|--------|-----------|
| 0–7 days | 1.0× | Fresh knowledge, highest relevance |
| 8–30 days | 0.8× | Still relevant, slight decay |
| 31–90 days | 0.5× | Background context |
| 90+ days | 0.3× | Historical reference only |

### 3.4 Cross-Agent Enrichment Engine

This is the **flagship innovation** — the mechanism that lets agents learn from each other's experiences.

#### How it works

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                CROSS-AGENT ENRICHMENT ENGINE                      │
 │                                                                   │
 │  Agent A (Support) queries: "Customer X login bug"               │
 │                                                                   │
 │  ┌─────────────────────────────────────────────────────────────┐ │
 │  │ STEP 1: IDENTIFY KEY ENTITIES & TOPICS IN QUERY             │ │
 │  │   Entities: [Customer X], [login], [bug]                     │ │
 │  │   Embed query → semantic vector                              │ │
 │  └──────────────────────────┬──────────────────────────────────┘ │
 │                             │                                     │
 │  ┌──────────────────────────▼──────────────────────────────────┐ │
 │  │ STEP 2: SEMANTIC SEARCH ACROSS ALL SHARED + GLOBAL MEMORIES │ │
 │  │   (including those from OTHER agents)                        │ │
 │  │                                                              │ │
 │  │   Qdrant: cosine similarity(query_vector, all_facts)         │ │
 │  │   Filter: source_agent != "support" (look for OTHER agents) │ │
 │  │   Filter: visibility IN ["shared", "global"]                 │ │
 │  │   Filter: status = "active"                                   │ │
 │  └──────────────────────────┬──────────────────────────────────┘ │
 │                             │                                     │
 │  ┌──────────────────────────▼──────────────────────────────────┐ │
 │  │ STEP 3: GRAPH TRAVERSAL FROM MATCHED ENTITIES               │ │
 │  │                                                              │ │
 │  │   Neo4j: MATCH (e:Entity {name: "auth-service"})            │ │
 │  │          -[:RELATES_TO]->(f:Fact)                            │ │
 │  │          WHERE f.source_agent != "support"                    │ │
 │  │                                                              │ │
 │  │   Finds: Engineering Agent discussed "auth microservice      │ │
 │  │   bottleneck" 2 days ago — semantically related to           │ │
 │  │   "login bug"                                                │ │
 │  └──────────────────────────┬──────────────────────────────────┘ │
 │                             │                                     │
 │  ┌──────────────────────────▼──────────────────────────────────┐ │
 │  │ STEP 4: RELEVANCE SCORING & RANKING                         │ │
 │  │                                                              │ │
 │  │   enrichment_score =                                          │ │
 │  │     (semantic_similarity × 0.5)                               │ │
 │  │     + (graph_proximity × 0.3)    ← how connected in graph    │ │
 │  │     + (recency_boost × 0.2)      ← fresher = more relevant   │ │
 │  │                                                              │ │
 │  │   Threshold: enrichment_score >= 0.75 → include in packet    │ │
 │  └──────────────────────────┬──────────────────────────────────┘ │
 │                             │                                     │
 │  ┌──────────────────────────▼──────────────────────────────────┐ │
 │  │ STEP 5: MERGE INTO memory_packet                             │ │
 │  │                                                              │ │
 │  │   Enriched items are labeled with source context:            │ │
 │  │                                                              │ │
 │  │   ```json                                                    │ │
 │  │   {                                                          │ │
 │  │     "text": "Auth microservice experiencing bottleneck       │ │
 │  │              under peak load (RS256 token validation)",       │ │
 │  │     "type": "fact",                                          │ │
 │  │     "source_agent": "engineering_agent",                     │ │
 │  │     "source_group": "engineering",                           │ │
 │  │     "enrichment": true,                                      │ │
 │  │     "enrichment_score": 0.87,                                │ │
 │  │     "why_relevant": "Semantically matches 'login bug' —     │ │
 │  │                      auth service is upstream dependency"   │ │
 │  │   }                                                          │ │
 │  │   ```                                                        │ │
 │  └─────────────────────────────────────────────────────────────┘ │
 └─────────────────────────────────────────────────────────────────┘
```

#### Enrichment in the memory_packet

Enriched items appear in a dedicated section, clearly distinguished from the agent's own memory:

```
<memory>
As of 2026-08-12, here is what I know from previous sessions:

YOUR MEMORY (Support Agent):
DECISIONS:
- Customer X prefers email communication (2026-08-10)

FACTS:
- Customer X is on enterprise tier, SLA 4h (2026-08-09)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ENRICHED CONTEXT (from other agents):
The following items come from other agents' experiences and may be
relevant to your current situation:

FROM ENGINEERING AGENT (2 days ago):
- Auth microservice experiencing bottleneck under peak load
  (RS256 token validation). Fix in progress — ETA Aug 14.
  Relevance: "login bug" → auth service is upstream dependency

FROM SALES AGENT (5 days ago):
- Customer X renewed enterprise contract with early termination
  clause. Relationship status: "needs attention"
  Relevance: shared entity "Customer X"
</memory>
```

#### Why this matters

Without enrichment, the Support Agent would troubleshoot the login bug from scratch, unaware that Engineering already diagnosed a bottleneck in the auth service. With enrichment, the Support Agent immediately knows: "This is likely caused by the auth bottleneck — I can tell the customer the fix is coming Aug 14, and escalate only if the symptoms don't match."

**The agent doesn't just remember — it inherits institutional knowledge automatically.**

---

## 4. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     FEDERATED AGENT MEMORY — ARCHITECTURE                  │
│                                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │ SUPPORT  │  │    HR    │  │  SALES   │  │   ENG    │   AGENT LAYER   │
│  │  AGENT   │  │  AGENT   │  │  AGENT   │  │  AGENT   │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                 │
│       │             │             │             │                         │
│       │  POST /ingest/turn       │  POST /retrieve                       │
│       │  (real-time streaming)   │  (start of session)                   │
│       │             │             │             │                         │
│       └─────────────┼─────────────┼─────────────┘                        │
│                     │             │                                       │
│                     ▼             ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                    LAYER 1: MCP SERVER                            │     │
│  │                    (FastAPI + MCP protocol)                       │     │
│  │  • /ingest/turn — real-time turn ingestion                       │     │
│  │  • /ingest/close — session flush                                 │     │
│  │  • /retrieve — memory_packet generation                          │     │
│  │  • /dashboard — ops visibility                                   │     │
│  │  • Tenant isolation via API key                                  │     │
│  └──────────────────────────┬───────────────────────────────────────┘     │
│                             │                                              │
│              ┌──────────────┼──────────────┐                               │
│              ▼              ▼              ▼                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  LAYER 2     │  │  LAYER 7     │  │  LAYER 8     │                     │
│  │  RAW ARCHIVE │  │  FEDERATED   │  │  CROSS-AGENT │                     │
│  │  (filesystem)│  │  RETRIEVAL   │  │  ENRICHMENT  │                     │
│  └──────┬───────┘  │  SERVICE     │  │  ENGINE      │                     │
│         │          └──────┬───────┘  └──────┬───────┘                     │
│         ▼                 │                 │                               │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │                    LAYER 3: MEMORY COMPILER                       │     │
│  │                    (DSPy Pipeline + Gemma)                        │     │
│  │                                                                   │     │
│  │  Normalizer → Splitter → Classifier → Extractor →                │     │
│  │  Entity Resolver → Contradiction Checker →                       │     │
│  │  Memory Selector → Visibility Classifier (NEW)                   │     │
│  └──────────────────────────┬───────────────────────────────────────┘     │
│                             │                                              │
│          ┌──────────────────┼──────────────────┐                          │
│          ▼                  ▼                  ▼                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  LAYER 4     │  │  LAYER 5     │  │  LAYER 6     │                     │
│  │  FEDERATED   │  │  VECTOR      │  │  METADATA    │                     │
│  │  GRAPH CORE  │  │  INDEX       │  │  STORE       │                     │
│  │  Neo4j +     │  │  Qdrant      │  │  PostgreSQL  │                     │
│  │  Graphiti    │  │              │  │              │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │                    LAYER 0: TENANT & ISOLATION                    │     │
│  │  • Multi-tenant PostgreSQL schemas                                │     │
│  │  • Per-tenant Neo4j databases (or subgraph labels)               │     │
│  │  • Qdrant collection namespacing                                  │     │
│  │  • API key → tenant resolution                                    │     │
│  └──────────────────────────────────────────────────────────────────┘     │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │                    LAYER 10: DASHBOARD & OBSERVABILITY            │     │
│  │  • Service health (Neo4j, Qdrant, Postgres, LLM)                  │     │
│  │  • Memory growth & throughput stats                               │     │
│  │  • Compiler queue depth & quality signals                         │     │
│  │  • Per-tenant stats (for SaaS deployment)                         │     │
│  └──────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Layer-by-Layer Breakdown

---

### Layer 0 — Enterprise Tenant & Isolation

**What it does:**  
In a real enterprise deployment, AcmeCorp's memory must be completely isolated from OtherCorp's memory. This layer handles multi-tenancy: API key resolution, data isolation, and per-tenant configuration.

**Why it's needed for the enterprise use case:**  
The MCP server will serve multiple tenants — either different companies (SaaS) or different departments within one large org. Without isolation, a Support Agent at AcmeCorp could accidentally read Global Corp's memory about a similarly-named client.

**Implementation:**

```
POST /ingest/turn
Authorization: Bearer <API-KEY>
X-Tenant-ID: acme-corp

→ Server resolves tenant from API key
→ All data operations scoped to tenant
→ Memory scopes (private/shared/global) are relative to tenant
```

**Isolation strategy:**

| Component | Isolation Approach |
|-----------|-------------------|
| **PostgreSQL** | Per-tenant schema (`acme_corp.sessions`, `acme_corp.facts`, …) |
| **Neo4j** | Per-tenant database (`acme-corp-memory`) or subgraph labels |
| **Qdrant** | Collection prefix (`acme-corp_entities`, `acme-corp_facts`, …) |
| **Raw Archive** | Per-tenant filesystem directory (`data/raw/acme-corp/…`) |

**For hackathon MVP:** single-tenant only (tenant = `default`). Multi-tenancy is documented in the design but implemented post-hackathon.

**Technology:** FastAPI middleware, PostgreSQL schemas, Neo4j multi-database

---

### Layer 1 — Agent Hook (MCP Server)

**What it does:**  
The single entry point for all agent interactions. Implements the MCP (Model Context Protocol) specification so any MCP-compatible agent can plug in with zero code changes.

**MCP Tools exposed:**

| Tool | Description |
|------|-------------|
| `memory_ingest_turn` | Submit a single conversation turn for processing |
| `memory_ingest_close` | Signal end of session — flush remaining compiler buffer |
| `memory_retrieve` | Get a `memory_packet` for the current session context |
| `memory_search` | Free-text search across agent memory (agent-side exploration) |
| `memory_status` | Get memory system health and stats |

**Real-time streaming API (REST fallback for non-MCP agents):**

```
POST /ingest/turn
{
  "session_id": "sess_20260812_001",
  "source_agent": "support_agent",       // globally unique agent ID
  "agent_group": "customer_support",     // for shared memory scoping
  "model": "gemini-2.5-pro",
  "tenant_id": "acme-corp",
  "turn": {
    "role": "assistant",
    "content": "I've identified the issue — it's a stale JWT cache...",
    "timestamp": "2026-08-12T10:00:05Z",
    "message_id": "a3",
    "tool_calls": []
  }
}
```

**Agent registration:**

Agents are registered with metadata that determines their shared memory group and default retrieval behavior:

```json
{
  "agent_id": "support_agent",
  "agent_group": "customer_support",
  "agent_role": "support",
  "shared_groups": ["customer_support", "engineering"],  // which groups' shared memory to include
  "token_budget": 2000
}
```

**Key design decisions:**
- **MCP-native** — implements the standard protocol, not a custom API
- **REST fallback** — non-MCP agents (Pi, Claude CLI) use direct HTTP endpoints
- **Agent identity is explicit** — `source_agent` and `agent_group` are required in every request
- **Non-blocking ingest** — turns are acknowledged immediately; compilation is async

**Technology:** FastAPI, MCP Python SDK, Pydantic v2

---

### Layer 2 — Raw Archive

**What it does:**  
Immutable store of every raw session. Never modified after write. Source of truth for re-processing and audit.

**Why immutable:**  
If the compiler's prompts are updated or the extractor logic changes, all past sessions can be re-processed from raw JSON. This is critical for a self-learning system — you can't improve the compiler if you've thrown away the training data.

**Storage structure:**

```
data/raw/
  acme-corp/                     ← tenant namespace
    2026/
      08/
        12/
          sess_20260812_001.json
          sess_20260812_002.json
```

**Per-session JSON schema:**

```json
{
  "session_id": "sess_20260812_001",
  "tenant_id": "acme-corp",
  "source_agent": "support_agent",
  "agent_group": "customer_support",
  "model": "gemini-2.5-pro",
  "started_at": "2026-08-12T09:45:00Z",
  "closed_at": "2026-08-12T10:15:00Z",
  "turns": [ ... ],
  "metadata": {
    "user_id": "agent_smith",
    "endpoint_type": "customer_facing"
  }
}
```

**Technology:** Filesystem (Docker volume), Python `pathlib`, atomic writes (`.tmp` → rename)

---

### Layer 3 — Memory Compiler

**What it does:**  
The brain of the system. Transforms raw conversation turns into structured `MemoryEvent` objects through a 7-step DSPy pipeline.

**What's new vs. base Graphiti:** Two additional steps for federation.

```
                    RAW TURNS
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  Step 1: NORMALIZER                   │
     │  • Python + spaCy                     │
     │  • Flatten turns, tag named entities  │
     │  • Output: NormalizedSession          │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  Step 2: EPISODE SPLITTER (DSPy)     │
     │  • Gemma 4B                          │
     │  • Group turns into semantic episodes │
     │  • Split on topic change, decisions   │
     │  • Output: list[Episode]              │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  Step 3: EPISODE CLASSIFIER (DSPy)   │
     │  • Gemma 4B                          │
     │  • Classify: fact/decision/task/...  │
     │  • Output: EpisodeType + confidence  │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  Step 4: MEMORY EXTRACTOR (DSPy)     │
     │  • Gemma 4B + Instructor             │
     │  • Extract entities, relations,       │
     │    claims, tasks, open questions      │
     │  • Output: list[MemoryItem]           │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  Step 5: ENTITY RESOLVER (hybrid)    │
     │  • sentence-transformers + rapidfuzz │
     │  • Resolve "Claude" → canonical ID   │
     │  • New entities → registry           │
     │  • Output: canonical_entity_id map   │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  Step 6: CONTRADICTION CHECKER       │
     │  • Rules + Gemma 4B                  │
     │  • New fact vs. existing facts       │
     │  • Status: active → outdated          │
     │  • Creates supersedes links          │
     │  • Output: ContradictionResult       │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  Step 7: MEMORY SELECTOR (DSPy)      │
     │  • Gemma 4B                          │
     │  • Quality gate — discard low-value   │
     │  • Confidence >= 0.6 required         │
     │  • Output: final MemoryEvent list    │
     └──────────────────┬───────────────────┘
                        │
                        ▼
     ┌──────────────────────────────────────┐
     │  ★ Step 8: VISIBILITY CLASSIFIER     │
     │     (DSPy) — NEW FOR FEDERATION      │
     │  • Gemma 4B                          │
     │  • Classify: private/shared/global   │
     │  • Assign target_groups for shared    │
     │  • Output: MemoryEvent + visibility  │
     └──────────────────┬───────────────────┘
                        │
                        ▼
               STRUCTURED MEMORY EVENTS
              (ready for Graph + Vector write)
```

**Real-time processing model:**

Events are processed in a **sliding window** (4–6 turns). When the buffer fills or a topic shift is detected, the window is flushed through the pipeline. The agent session is never blocked — graph writes happen asynchronously.

**Latency:** ~10–30s per window (Gemma 4B inference is the bottleneck). Acceptable — memory processing is background, not real-time.

**Technology:** DSPy, Instructor (structured output), Gemma 4B via LM Studio, spaCy, sentence-transformers, rapidfuzz

**Compiler configuration (per tenant):**

```yaml
compiler:
  window_size: 6            # turns per processing window
  min_confidence: 0.6       # discard below this
  max_retries: 3            # failed episode retries
  llm_timeout: 30           # seconds per Gemma call
  dspy_optimizer: enabled   # self-improvement loop
```

---

### Layer 4 — Federated Graph Core

**What it does:**  
Stores all memory as a temporal knowledge graph. Entities become nodes, facts/decisions/tasks become connected subgraphs, and time is a first-class dimension.

**What's new vs. base Graphiti:** Nodes and edges carry scope metadata (`visibility`, `source_agent`, `agent_group`, `tenant_id`).

**Graph model:**

```cypher
// Entity nodes — canonical representation of people, products, systems, etc.
(:Entity {
  canonical_id: "ent_cust_x",
  name: "Customer X",
  type: "client",
  tenant_id: "acme-corp",
  created_at: datetime(),
  last_seen: datetime()
})

// Fact nodes — atomic pieces of knowledge
(:Fact {
  fact_id: "fact_login_bug_001",
  text: "Login bug root cause: stale JWT cache after token rotation",
  type: "fact",
  status: "active",
  confidence: 0.91,
  visibility: "shared",       // ★ NEW: federation scope
  source_agent: "support_agent",  // ★ NEW: which agent created this
  agent_group: "customer_support", // ★ NEW: which group
  target_groups: ["customer_support", "engineering"], // ★ NEW: who can read
  tenant_id: "acme-corp",     // ★ NEW: tenant isolation
  session_id: "sess_20260812_001",
  created_at: datetime()
})

// Relations
(:Entity)-[:INVOLVED_IN {
  role: "subject",
  confidence: 0.91,
  timestamp: datetime()
}]->(:Fact)

(:Fact)-[:SUPERSEDES {
  reason: "New root cause identified",
  timestamp: datetime()
}]->(:Fact)

// Episode — groups related turns
(:Episode {
  episode_id: "ep_001",
  summary: "Customer X login troubleshooting",
  visibility: "shared",
  source_agent: "support_agent"
})-[:CONTAINS]->(:Fact)
```

**Temporal model (bi-temporal):**

Every fact has two time dimensions:
- **valid_time** — when the fact was true in the real world
- **recorded_time** — when the system learned about it

This means: "On August 12, the system knew that the login bug was caused by NPE (recorded Aug 10). On August 14, this was superseded: root cause is actually stale JWT cache."

Both versions are preserved. The graph can answer: "What did we believe on August 12?" and "What do we believe now?"

**Technology:** Neo4j 5 (Community Edition), Graphiti (Python library by Zep AI), Cypher query language

---

### Layer 5 — Vector Index

**What it does:**  
Stores embeddings for every entity, fact, and episode summary. Enables semantic similarity search — find conceptually related memories even without explicit graph connections.

**What's new vs. base Graphiti:** Collections are scoped per tenant and visibility. Cross-agent queries can target "all shared + global facts from other agents."

**Collections:**

| Collection | Content | Dimensions | Distance | Scope |
|------------|---------|-----------|----------|-------|
| `{tenant}_entities` | one vector per canonical entity | 384 | Cosine | all |
| `{tenant}_episodes` | one vector per episode summary | 384 | Cosine | private + shared + global |
| `{tenant}_facts_private` | private facts only | 384 | Cosine | agent-filtered |
| `{tenant}_facts_shared` | shared + global facts | 384 | Cosine | group-filtered |

**Why split facts into private vs. shared collections:**  
At query time, the retrieval service knows exactly which collections to search based on the requesting agent's identity. No need for runtime payload filtering — the data is physically separated.

**Cross-agent enrichment query:**

```python
# "Show me shared/global facts from OTHER agents that are
#  semantically similar to my current situation"

qdrant.search(
    collection_name=f"{tenant}_facts_shared",
    query_vector=embed(current_situation),
    query_filter=models.Filter(
        must_not=[
            models.FieldCondition(
                key="source_agent",
                match=models.MatchValue(value="support_agent")  # NOT my own
            )
        ],
        must=[
            models.FieldCondition(
                key="status",
                match=models.MatchValue(value="active")
            )
        ]
    ),
    limit=10,
    score_threshold=0.75
)
```

**Technology:** Qdrant (Docker), `text-embedding-nomic-embed-text-v1.5` (LM Studio), 384-dimensional embeddings

---

### Layer 6 — Metadata Store

**What it does:**  
Relational bookkeeping. Tracks what's been ingested, what's compiling, entity registry, and fact lifecycle.

**What's new vs. base Graphiti:** Agent registry, group definitions, visibility audit log, tenant configuration.

**Key tables:**

```sql
-- Agent registry (NEW)
CREATE TABLE agents (
    agent_id        TEXT PRIMARY KEY,
    agent_group     TEXT NOT NULL,
    agent_role      TEXT,
    shared_groups   TEXT[],     -- which groups' shared memory this agent can read
    token_budget    INT DEFAULT 2000,
    registered_at   TIMESTAMPTZ,
    tenant_id       TEXT NOT NULL
);

-- Session tracking
CREATE TABLE sessions (
    session_id      TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    source_agent    TEXT NOT NULL,
    agent_group     TEXT NOT NULL,
    ingested_at     TIMESTAMPTZ,
    status          TEXT,       -- pending | processing | done | error
    episode_count   INT
);

-- Canonical entity registry
CREATE TABLE entities (
    canonical_id    TEXT PRIMARY KEY,
    canonical_name  TEXT,
    type            TEXT,
    aliases         TEXT[],
    tenant_id       TEXT NOT NULL,
    first_seen      TIMESTAMPTZ,
    last_seen       TIMESTAMPTZ
);

-- Fact lifecycle with visibility (EXTENDED)
CREATE TABLE facts (
    fact_id         TEXT PRIMARY KEY,
    entity_ids      TEXT[],
    type            TEXT,
    status          TEXT,       -- active | outdated | discarded
    visibility      TEXT,       -- private | shared | global      ★ NEW
    source_agent    TEXT,                                          ★ NEW
    agent_group     TEXT,                                          ★ NEW
    target_groups   TEXT[],                                        ★ NEW
    confidence      FLOAT,
    session_id      TEXT,
    tenant_id       TEXT NOT NULL,                                 ★ NEW
    created_at      TIMESTAMPTZ,
    superseded_by   TEXT
);

-- Visibility change log (NEW — for audit)
CREATE TABLE visibility_log (
    log_id          SERIAL PRIMARY KEY,
    fact_id         TEXT,
    old_visibility  TEXT,
    new_visibility  TEXT,
    changed_by      TEXT,       -- "classifier" or "manual"
    changed_at      TIMESTAMPTZ,
    reason          TEXT
);

-- Compiler job queue
CREATE TABLE compiler_jobs (
    job_id          SERIAL PRIMARY KEY,
    session_id      TEXT,
    status          TEXT,
    attempts        INT DEFAULT 0,
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ
);
```

**Technology:** PostgreSQL 16

---

### Layer 7 — Federated Retrieval Service

**What it does:**  
Answers: *"Given this agent, this query, and this context — what memory is relevant?"*

Runs before every agent session and returns a compact `memory_packet`.

**What's new vs. base Graphiti:** Multi-scope retrieval that merges private + shared + global memory, with awareness of agent identity and group membership.

**Retrieval API:**

```
POST /retrieve
Authorization: Bearer <API-KEY>
Content-Type: application/json

{
  "query": "Customer X is having login issues",
  "source_agent": "support_agent",
  "agent_group": "customer_support",
  "top_k": 10,
  "recency_days": 30,
  "include_enrichment": true,    // ★ NEW: cross-agent enrichment
  "token_budget": 2000
}
```

**Retrieval strategy (4 parallel queries):**

```
QUERY: "Customer X is having login issues"
SOURCE: support_agent (group: customer_support)

┌────────────────────────────────────────────────────────────────┐
│ QUERY 1: SEMANTIC — Private Memory                             │
│   Qdrant: {tenant}_facts_private                               │
│   Filter: source_agent = "support_agent"                       │
│   Filter: status = "active"                                    │
│   Returns: top-K direct matches from agent's own history       │
├────────────────────────────────────────────────────────────────┤
│ QUERY 2: SEMANTIC — Shared + Global Memory                     │
│   Qdrant: {tenant}_facts_shared                                │
│   Filter: visibility IN ["shared", "global"]                    │
│   Filter: (visibility = "shared" AND agent_group IN             │
│            ["customer_support"]) OR (visibility = "global")    │
│   Returns: top-K matches from team and org-wide memory         │
├────────────────────────────────────────────────────────────────┤
│ QUERY 3: GRAPH — Entity Neighborhood                           │
│   Neo4j: MATCH (e:Entity {name: "Customer X"})                │
│          -[:INVOLVED_IN]-(f:Fact)                              │
│   Filter by agent's access scope                               │
│   Returns: all facts connected to key entities, with           │
│            graph-distance scoring                              │
├────────────────────────────────────────────────────────────────┤
│ QUERY 4: ENRICHMENT — Cross-Agent (if include_enrichment=true) │
│   Qdrant: {tenant}_facts_shared                                │
│   Filter: source_agent != "support_agent"                      │
│   Filter: visibility IN ["shared", "global"]                    │
│   Score: semantic similarity to query                          │
│   Returns: top-K facts from OTHER agents' experience           │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ FUSION & RANKING                                                │
│                                                                 │
│ 1. Deduplicate across queries (by fact_id)                      │
│ 2. Compute combined score:                                      │
│    score = (semantic_similarity × 0.4)                          │
│          + (graph_proximity × 0.2)                              │
│          + (recency_weight × 0.2)                               │
│          + (scope_boost × 0.2)                                  │
│                                                                 │
│    scope_boost:                                                 │
│      private = 1.0   (own memory is most trusted)               │
│      shared  = 0.85  (team memory is reliable)                  │
│      global  = 0.7   (org memory is context)                   │
│      enrichment = 0.6 (cross-agent is suggestive)              │
│                                                                 │
│ 3. Sort by combined score descending                            │
│ 4. Truncate to token budget                                     │
│ 5. Format as memory_packet                                      │
└────────────────────────────────────────────────────────────────┘
```

**Technology:** FastAPI, Qdrant Python client, Neo4j Python driver, `asyncio.gather` for parallel queries

---

### Layer 8 — Cross-Agent Enrichment Engine

**What it does:**  
The mechanism that makes Federated Agent Memory truly unique. When Agent A queries for memory, the enrichment engine finds experiences from Agent B (and C, and D) that are relevant to A's current situation — even if A has never encountered this context before.

**This is the layer that answers: "What do OTHER agents know that might help THIS agent right now?"**

**Detailed mechanism:**

```
INPUT: query_text, source_agent, agent_group, tenant_id

STEP 0: IDENTIFY CURRENT CONTEXT
─────────────────────────────────
• Extract entities from query (spaCy + entity registry)
• Embed query → vector (nomic-embed-text-v1.5)
• Identify topic clusters from query

STEP 1: SEMANTIC MATCHING (Qdrant)
─────────────────────────────────
• Search {tenant}_facts_shared collection
• Filter: source_agent != current_agent
• Filter: status = "active"
• Score: cosine similarity(query_vector, fact_vector)
• Threshold: similarity >= 0.75
• → candidate_enrichments (up to 20)

STEP 2: GRAPH CONTEXTUALIZATION (Neo4j)
─────────────────────────────────
• For each candidate enrichment from Step 1:
  - Find graph distance between candidate entities and query entities
  - Shortest path in Neo4j between entities
  - Example: candidate mentions "auth-service", query mentions "login"
    → 1-hop connection: (:User)-[:LOGS_IN_VIA]->(:AuthService)
    → high relevance

• For entities NOT directly connected but semantically similar:
  - Check shared properties, shared neighbors
  - Example: "auth-service" and "payment-gateway" are not directly
    linked, but both are connected to "Customer X" →
    contextual relevance

STEP 3: RELEVANCE SCORING
─────────────────────────────────
enrichment_score = 
    (semantic_similarity × 0.40)      ← "How similar is this to my query?"
  + (graph_proximity × 0.25)          ← "How connected are the entities?"
  + (recency_weight × 0.15)           ← "How recent is this experience?"
  + (source_reputation × 0.10)        ← "How reliable is this agent?"
  + (cross_reference × 0.10)          ← "How many other agents reference this?"

Where:
  - semantic_similarity: direct cosine similarity from Qdrant
  - graph_proximity: 1 / (1 + shortest_path_length), normalized
  - recency_weight: 1.0 for last 3 days, 0.8 for last week, 0.5 for month
  - source_reputation: based on agent's fact accuracy history
  - cross_reference: ratio of other agents that have similar facts

STEP 4: GENERATE "WHY RELEVANT" EXPLANATION
─────────────────────────────────
• Use the connection path to generate a human-readable explanation
• Example:
  "Relevance: 'login bug' → auth-service is upstream dependency.
   Engineering Agent discussed auth bottleneck 2 days ago."
• This explanation is included in the memory_packet so the agent
  understands WHY this cross-agent memory is being suggested

STEP 5: THRESHOLD & TRUNCATE
─────────────────────────────────
• Keep only enrichments with score >= 0.70
• Sort by score descending
• Cap at 5 enrichment items (to preserve token budget)
• Merge into memory_packet under "ENRICHED CONTEXT" section
```

**Enrichment quality signals:**

| Signal | How it's measured | Why it matters |
|--------|------------------|----------------|
| **Fact accuracy** | % of agent's facts NOT superseded within 30 days | High-accuracy agents' enrichments are trusted more |
| **Engagement** | Did the agent actually use this enrichment? (heuristic: mentioned in next turns) | Feeds back into relevance scoring |
| **Cross-references** | How many other agents have semantically similar facts | Consensus = higher confidence |
| **Recency decay** | Older facts get lower enrichment scores | Stale knowledge is less useful |

**Self-improvement loop:**

```
Enrichment suggested → Agent uses it? → Feedback signal
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                      "Used and           "Ignored or
                      helpful"            irrelevant"
                          │                   │
                          ▼                   ▼
                Boost source agent    Reduce source agent
                reputation score      reputation for
                                      this topic
```

**Technology:** Qdrant (semantic search), Neo4j (graph traversal), spaCy (entity extraction)

---

### Layer 9 — Agent Injection

**What the agent receives:**

The `memory_packet` is injected into the system prompt before the conversation starts. It's structured to be machine-readable yet compact enough to fit within token budgets.

```

<memory>
As of 2026-08-12T10:00:00Z, here is relevant context from
AcmeCorp's federated memory:

━━━ YOUR MEMORY (support_agent / customer_support) ━━━

DECISIONS:
- Customer X prefers email over phone for technical issues
  (2026-08-10, confidence: 0.95)

FACTS:
- Customer X is on enterprise tier, SLA: 4-hour response
  (2026-08-09, confidence: 0.98)
- Customer X uses Chrome 126 on macOS 14.5
  (2026-08-11, confidence: 0.89)

OPEN TASKS:
- Follow up with Customer X on login resolution
  (created: 2026-08-12)

━ SHARED TEAM MEMORY (customer_support) ━

RECENT SOLUTIONS:
- Login bug v2.3: clear JWT cache, force re-auth
  (from: support_agent_2, 2026-08-11)
- Password reset flow broken on Safari — known issue,
  workaround: use Chrome (from: support_agent_3, 2026-08-10)

━━━ ENRICHED CONTEXT (from other agents) ━━━

FROM engineering_agent (engineering, 2 days ago):
- Auth microservice experiencing bottleneck under peak load
  (RS256 token validation). Fix in progress — ETA Aug 14.
  Relevance: 0.87 — auth service is upstream dependency for login

FROM sales_agent (sales, 5 days ago):
- Customer X renewed enterprise contract with early termination
  clause. Relationship status: "needs attention"
  Relevance: 0.82 — shared entity "Customer X"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ENTITIES KNOWN:
- Customer X (client) · auth-service (system) · JWT (technology)

Use this context to inform your responses. Enriched context comes
from other agents' experiences — it may be indirectly relevant.
Always verify critical facts before acting on them.
</memory>
```

**Token budget:** 2000 tokens default, configurable per agent. The retrieval service handles truncation based on ranking — most relevant items first.

**Technology:** Jinja2 templating, token counting via `tiktoken`

---

### Layer 10 — Dashboard & Observability

**What it does:**  
Live snapshot of system health — is every store up, is the compiler running, how much memory has been accumulated, any quality signals that need human attention.

**Dashboard sections:**

```
┌─────────────────────────────────────────────────────────────────┐
│  FEDERATED AGENT MEMORY — DASHBOARD                              │
│  Tenant: acme-corp | Last refresh: 2s ago                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ SERVICES ────────────────────────────────────────────────┐  │
│  │  Neo4j    ● UP      Postgres  ● UP      Qdrant   ● UP    │  │
│  │  LLM      ● UP      Compiler  ● RUNNING (2 jobs queued)  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ MEMORY GROWTH ───────────────────────────────────────────┐  │
│  │  Total facts: 12,847   Entities: 3,421   Sessions: 892    │  │
│  │  This week: +342 facts, +89 entities, +23 sessions        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ MEMORY SCOPES ───────────────────────────────────────────┐  │
│  │  Private: 4,201   Shared: 6,893   Global: 1,753           │  │
│  │  ████████░░░░░░░░░░░░░░░░  Private (33%)                   │  │
│  │  ██████████████░░░░░░░░░░  Shared  (54%)                   │  │
│  │  ████░░░░░░░░░░░░░░░░░░░░  Global  (13%)                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ AGENT ACTIVITY ──────────────────────────────────────────┐  │
│  │  support_agent      ▲ 142 facts this week                  │  │
│  │  hr_agent           ▲ 67 facts this week                   │  │
│  │  sales_agent        ▲ 89 facts this week                   │  │
│  │  engineering_agent  ▲ 203 facts this week   ★ most active  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ QUALITY SIGNALS ─────────────────────────────────────────┐  │
│  │  Contradictions detected: 12 (3 auto-resolved, 9 pending) │  │
│  │  Low-confidence facts: 47 (<0.6, flagged for review)       │  │
│  │  Cross-agent enrichments served: 1,203 this week           │  │
│  │  Enrichment usefulness rate: 68% (used by agents)          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:** `GET /metrics` (JSON) + `GET /dashboard` (static HTML with 5s polling), `asyncio.gather` for concurrent health checks.

**Technology:** FastAPI, vanilla HTML/CSS/JS

---

## 6. Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Ingest** | FastAPI + MCP SDK | Agent communication protocol |
| **Compiler** | DSPy + Instructor + Gemma 4B | LLM-driven memory extraction |
| **Graph** | Neo4j 5 + Graphiti | Temporal knowledge graph |
| **Vector** | Qdrant + nomic-embed-text | Semantic search |
| **Metadata** | PostgreSQL 16 | Relational bookkeeping |
| **NLP** | spaCy + rapidfuzz | Entity recognition, fuzzy matching |
| **Embeddings** | sentence-transformers | Semantic similarity |
| **Infrastructure** | Docker Compose | Container orchestration |
| **Observability** | Static HTML + FastAPI metrics | Dashboard |
| **Token counting** | tiktoken | Token budget management |

**Why Gemma 4B (not a cloud model):**
- Fully local — zero latency, zero cost per inference
- Good enough for structured extraction (the DSPy pipeline constrains output to JSON schemas via Instructor)
- Swappable: replace `LLM_URL` env var to use Gemini, Claude, or any OpenAI-compatible API for production

**Why DSPy (not raw prompts):**
- The compiler is a pipeline of programmatic steps, not a single mega-prompt
- DSPy optimizes each step against labeled data — the compiler gets better as you use it
- Declarative: you define *what* to extract, DSPy figures out *how* to prompt for it

---

## 7. Hackathon MVP Scope

### What we'll demo

| Component | Status | Notes |
|-----------|--------|-------|
| **MCP Server** | 🔨 Build | Wrap existing ingest/retrieve endpoints as MCP tools |
| **Ingest endpoint** | ✅ Working | Real-time turn streaming |
| **Memory Compiler** | ✅ Working | Full 7-step DSPy pipeline |
| **Neo4j + Graphiti** | ✅ Working | Temporal knowledge graph |
| **Qdrant** | ✅ Working | Semantic search |
| **PostgreSQL** | ✅ Working | Metadata + job queue |
| **Retrieval Service** | ✅ Working | Returns memory_packet |
| **Dashboard** | ✅ Working | Health + throughput stats |
| **Visibility Classifier** | 🔨 Build | DSPy module #8 in compiler pipeline |
| **Federated Retrieval** | 🔨 Build | Multi-scope query merging |
| **Cross-Agent Enrichment** | 🔨 MVP | Semantic search across agents, basic scoring |
| **Multi-tenancy** | 📋 Post-MVP | Single-tenant for hackathon |
| **DSPy Optimizer** | 📋 Stretch | Self-improvement loop demo |

### Demo scenario

**Two agents, one memory:**

1. **Agent A (Engineering)** discusses an auth service bottleneck with a developer. The compiler extracts: `"Auth microservice bottleneck: RS256 validation under peak load"`, classifies it as `shared` (target: `[engineering, support]`).

2. **Agent B (Support)** receives a customer complaint about login failures. It queries: `"Customer X login issues"`.

3. The **Federated Retrieval Service** runs parallel queries:
   - Private memory: finds Customer X's preferences
   - Shared memory: finds recent support team solutions
   - **Enrichment Engine**: finds Engineering's auth bottleneck — semantically similar, graph-connected via `auth-service` entity

4. Agent B's `memory_packet` includes: *"Enriched context: Auth microservice bottleneck — fix ETA Aug 14. Relevance: 0.87 — auth service is upstream dependency for login."*

5. Agent B immediately knows: this is likely the auth bottleneck, not a new bug. It tells the customer the fix is coming and doesn't escalate to engineering — saving hours of duplicate investigation.

### Post-hackathon roadmap

| Phase | Features |
|-------|----------|
| **Phase 1** (1 month post-hackathon) | Multi-tenancy, DSPy optimizer, enrichment feedback loop |
| **Phase 2** (3 months) | Gemini Enterprise ADK integration, GCP Cloud Run deployment |
| **Phase 3** (6 months) | Cross-tenant anonymized learning, enterprise SSO, SLA guarantees |

---

## Appendix A: Agent Group Configuration Example

```yaml
# acme-corp agent configuration
tenant:
  id: "acme-corp"
  name: "Acme Corporation"

agent_groups:
  - id: "customer_support"
    name: "Customer Support"
    shared_memory_groups: ["customer_support"]  # can read shared memory from these groups
    agents:
      - id: "support_agent_1"
        role: "tier1_support"
        token_budget: 2000
      - id: "support_agent_2"
        role: "tier2_support"
        token_budget: 2500

  - id: "engineering"
    name: "Engineering"
    shared_memory_groups: ["engineering", "customer_support"]  # eng can read support shared
    agents:
      - id: "engineering_agent"
        role: "backend"
        token_budget: 3000

  - id: "sales"
    name: "Sales"
    shared_memory_groups: ["sales"]
    agents:
      - id: "sales_agent"
        role: "enterprise_sales"
        token_budget: 1500

  - id: "hr"
    name: "Human Resources"
    shared_memory_groups: ["hr"]
    agents:
      - id: "hr_agent"
        role: "generalist"
        token_budget: 1500

cross_agent_enrichment:
  enabled: true
  max_enrichment_items: 5
  min_similarity_threshold: 0.75
```

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **Memory Event** | A single unit of extracted memory: a fact, decision, task, preference, etc. |
| **Visibility Scope** | Who can read a memory event: `private` (one agent), `shared` (group), or `global` (all) |
| **Agent Group** | A logical grouping of agents (e.g., "customer_support", "engineering") that share memory |
| **Enrichment** | Cross-agent memory surfaced to an agent based on semantic relevance, not direct ownership |
| **memory_packet** | The structured context injected into an agent's system prompt before a session |
| **Federation** | The mechanism that manages private vs. shared vs. global memory across multiple agents |
| **DSPy** | Declarative Self-improving Python — a framework for programming LLM pipelines with optimizable prompts |
| **Instructor** | A library that enforces structured JSON output from LLMs using Pydantic schemas |
| **Bi-temporal graph** | A graph that tracks both when a fact was true (valid time) and when it was recorded (transaction time) |
