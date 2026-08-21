# Delta — Memory Service (replaces Layer 1)

## ADDED Requirements

### Requirement: Extends ADK BaseMemoryService
The system SHALL be delivered as a Memory Service that inherits from ADK
`BaseMemoryService`, not as a standalone MCP server.

#### Scenario: Drop-in memory implementation
- WHEN an agent is configured to use this service
- THEN it SHALL present the same Memory Service interface as any other ADK
  memory implementation
- AND the agent SHALL NOT depend on any custom network protocol

### Requirement: Compiler-owned memory creation
The system SHALL route all memory creation through a DSPy-driven Compiler.

#### Scenario: Turn compiled into memory
- WHEN raw conversation turns are received
- THEN the Compiler SHALL transform them into structured memory entries
- AND the Compiler SHALL be a DSPy pipeline (not a single prompt)

### Requirement: Ranker-owned memory retrieval
The system SHALL route all memory retrieval through a Ranker that reranks
results for the requesting agent and query.

#### Scenario: Results reranked per query
- WHEN an agent requests memory
- THEN the Ranker SHALL score and order candidate memories for that agent + query
- AND SHALL return the highest-ranked entries within the token budget

### Requirement: Storage delegated to Google Memory Bank
The system SHALL NOT implement its own storage, vector index, or graph database.

#### Scenario: Storage handled by Google
- WHEN a memory entry is persisted
- THEN it SHALL be written to Google Memory Bank
- AND no self-managed Neo4j, Qdrant, or PostgreSQL SHALL be required

### Requirement: Session scoping delegated to Gemini Enterprise
The system SHALL rely on Gemini Enterprise session scoping for access control.

#### Scenario: Scope via session
- WHEN memory is scoped as private, shared, or global
- THEN the scope SHALL be enforced through Gemini Enterprise session scoping
- AND the Compiler SHALL map each entry to the appropriate scope

### Requirement: Novelty signal for real-time RAG
The system SHALL detect fresh, rising signals so agents surface new knowledge
before static indexes are rebuilt.

#### Scenario: Rising topic detected
- WHEN a topic or entity shows a spike in recent memory activity
- THEN the Ranker SHALL boost entries related to that rising topic
- AND the agent SHALL receive the fresh signal in its memory results
