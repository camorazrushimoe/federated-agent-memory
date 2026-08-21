# Adopt Google Memory Bank (replace the self-built stack)

## Why

The v1 architecture rebuilds the entire memory stack from scratch: Raw Archive
(L2), Neo4j + Graphiti graph (L4), Qdrant vector index (L5), PostgreSQL metadata
store (L6), and a custom Retrieval Service (L7). That is a ten-layer rebuild of
capabilities Google already ships.

On the architecture grooming call (2026-08-20) Petro Vozhdai made the point that
reframes the whole project: Gemini Enterprise / Agent Platform already provides a
managed **Memory Bank** and an **ADK `BaseMemoryService`** extension point — and
Vertex AI already ships a Memory Bank implementation using exactly that pattern.
Building storage and retrieval from scratch is neither the differentiator nor the
smart move for a Gemini Enterprise hackathon.

The part that *is* novel — and defensible — is not *where* memory lives, but *what
we put into it* and *what we surface out of it*. That is the compiler and the
ranker.

## What Changes

1. **Drop the self-built storage + retrieval stack** (L2, L4, L5, L6, L7) in
   favor of **Google Memory Bank** (managed storage + retrieval).
2. **Replace the custom MCP server (L1)** as the integration surface with a
   **Memory Service** that extends ADK `BaseMemoryService` — the same pattern
   Vertex AI Memory Bank uses. We become a *plug-in memory implementation*, not a
   parallel infrastructure service.
3. **Keep and sharpen the two genuinely novel pieces:**
   - **Compiler** (DSPy-driven) — how raw turns are compiled into structured
     memory (what to store, how to structure it).
   - **Ranker** (new) — how retrieved memory is reranked for the requesting
     agent + query, including **novelty / trend detection**.
4. **Replace our visibility-scope model + custom session tracking** with
   **Gemini Enterprise session scoping** (private/shared/global maps to session
   and agent scoping policy).
5. **Reframe the business differentiator as real-time RAG** — closing the gap
   between new conversational signals and when an agent actually gets smarter
   (the "trend novelty" idea from the call).

## Non-goals

- No re-implementation of storage, embeddings, or vector search.
- No full `docs/prd-technical-design.md` rewrite in this change (tracked as a
  follow-up task; the layer-by-layer breakdown is superseded by this proposal).
- No change to the anonymous-customer framing in `docs/01-business-idea.md`.

## Impact

- `openspec/specs/raw-archive` — **REMOVED** (replaced by Google Memory Bank).
- `openspec/specs/cross-agent-enrichment` — **MODIFIED** (folds into the Ranker).
- `openspec/specs/visibility-classifier` — **MODIFIED** (delegated to Gemini
  session scoping; policy moves into the Compiler).
- New: `openspec/specs/memory-service` — the component that replaces L1.
- `docs/02-architecture.md` — rewritten.
- `README.md` — component backlog updated.
