# Tasks — Adopt Google Memory Bank

- [ ] 1.1 Pin the target artifact: Agent Platform Memory Bank vs Vertex AI
  Memory Bank, and the exact ADK `BaseMemoryService` entry point
- [ ] 1.2 Spike: `hello-world` Memory Service that extends `BaseMemoryService`
  and writes/reads one entry through Google Memory Bank
- [ ] 2.1 Spec the Compiler (DSPy) interface: raw turns → structured memory
  entries
- [ ] 2.2 Move the visibility policy into the Compiler, mapped onto Gemini
  session scoping
- [ ] 3.1 Spec the Ranker interface: retrieved memories + query → ranked results
- [ ] 3.2 Define the novelty / trend signal for real-time RAG (rolling-window
  topic/entity spike)
- [ ] 4.1 Rewrite `docs/02-architecture.md` (done in this change)
- [ ] 4.2 Update `README.md` component backlog (done in this change)
- [ ] 5.1 Rewrite `docs/prd-technical-design.md` layer breakdown to the new
  architecture (follow-up)
- [ ] 5.2 Deprecate the v1 MCP server + self-built stack docs/notes
- [ ] 6.1 Hackathon demo: two agents sharing memory through the custom Memory
  Service, with the ranker surfacing a fresh signal the first agent didn't have
