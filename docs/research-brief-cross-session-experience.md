# Research Brief: Cross-Session Experience Extraction for Federated Agent Memory

**Audience:** Research / data analyst  
**Status:** Draft for hypothesis exploration (not a full experiment protocol yet)  
**Primary dataset:** Syncora Customer Support Conversations (synthetic, multi-turn, labeled)  
**Related list:** `docs/research-customer-support-dialogue-datasets.md`  
**Product context:** `docs/01-business-idea.md`, `openspec/specs/cross-agent-enrichment/spec.md`

---

## 1. Problem we are trying to solve

Customer-facing agents today mostly improve **offline** (retrain / refresh RAG on historical data).  
We want agents to get smarter from **live conversation streams** by:

1. Capturing conversations across agents and users (anonymous — we remember *what was learned*, not *who*).
2. Extracting reusable experience: problem shape, clarifying questions that helped, actions that worked or failed.
3. Sharing that experience so a later agent can reuse it when a similar problem appears (possibly with different wording).

Canonical product story (from business idea):

- Day 1: user asks for a laptop for video editing under $1500 → hesitation about weight → no sale.
- Day 2: different user describes overheating when rendering 4K → cooling-focused recommendation → sale.
- Day 3: same class of question as Day 1 → agent already knows cooling + weight matter → better first recommendation.

**The open gap:** we do not yet have a clear, evidence-based logic for *how* to analyze **unrelated** chats and decide what is worth putting into shared memory.

This brief asks the analyst to dig into real (synthetic but realistic) multi-turn support data and **confirm, refine, or kill** hypotheses about that logic.

---

## 2. Goal of this research pass

Not to build the production pipeline yet.  
Instead:

- Find **concrete patterns** in the data that look like transferable experience.
- Propose **operational definitions** (what counts as “same problem”, “success”, “useful move”).
- Surface **counter-examples** that break naive assumptions.
- Rank which hypotheses are worth a formal experiment next.

Deliverable from analyst: short report with examples (conversation IDs / excerpts), metrics where possible, and a recommendation: *pursue / modify / drop* each hypothesis.

---

## 3. Primary dataset to start with

### Syncora Customer Support Conversations

- **HF:** https://huggingface.co/datasets/syncora/customer_support_conversations_dataset  
- **Kaggle:** https://www.kaggle.com/datasets/syncoraai/customer-support-conversations  
- **Format:** CSV, one row ≈ one turn; group by `conversation_id`, order by `turn_id`
- **Useful fields for us:**
  - `role` (customer / agent)
  - `message`
  - `industry`
  - `category` / `sub_category`
  - `intent`
  - `sentiment`
  - `status` / `priority` (resolution-oriented signals)
  - `channel`, `locale`

**Why Syncora first:** multi-turn + industry + intent + outcome-ish labels in one place; fully synthetic → safe to share and quote in internal docs.

Secondary (if time): Lakshan2003 (long multi-turn banking), Bitext (clean intents), CallCenterEN (more “real” transcripts).

**Do not vendor raw data into this repo.** Work from HF/Kaggle downloads locally; cite conversation structure in the report.

---

## 4. Core research questions

1. **Similarity:** How can two chats be recognized as “about the same underlying problem” despite different wording, users, and agents?
2. **Extractable unit:** What is the smallest useful piece of experience to store (full transcript? summary? intent + successful path? question template? failure mode)?
3. **Outcome signal:** How reliably can we label success vs failure from available fields and dialogue text?
4. **Transfer:** Which extracted pieces actually help a *later* conversation (not just describe the past one)?
5. **Noise vs signal:** What looks similar but should *not* be shared (session-specific noise, wrong industry, partial failures)?
6. **Evidence strength:** Does repeating the same successful pattern across many chats justify ranking it higher (the “more facts → stronger idea” effect)?

---

## 5. Hypotheses to test

Each hypothesis is written so it can be **supported or falsified** with dataset work (clustering, manual review, simple metrics). Analyst should pick a subset if bandwidth is limited; H1–H4 are priority.

### H1 — Problem clustering across lexical variation
**Claim:** Conversations with different surface wording but the same underlying issue form recoverable clusters using intent + category + semantic similarity of early customer turns (not full transcript).

**Why it matters:** Without reliable “same problem” detection, we cannot route experience across sessions.

**Suggested checks:**
- Cluster by `intent` / `category` / embedding of first 1–2 customer messages.
- Manual audit: are cluster members truly the same problem class?
- False friends: same intent label but different real goals.

**Example of evidence we want:** 5–10 pairs/groups of chats that a human agrees are the same problem despite different phrasing.

---

### H2 — Successful paths share structure
**Claim:** Among conversations labeled resolved / positive outcome, agent behavior converges on a short sequence of moves (e.g. clarify constraint → propose option → confirm), and those sequences are more stable *within* a problem cluster than across clusters.

**Why it matters:** Shared memory should store *paths*, not only facts.

**Suggested checks:**
- Within a problem cluster, compare turn sequences of “good” vs “bad” outcomes.
- Extract recurring clarifying questions that appear before resolution.
- Measure whether successful chats ask fewer/more questions before resolution.

---

### H3 — Failures leave detectable early signals
**Claim:** Unresolved / negative-sentiment chats show early patterns (premature recommendation, ignored constraint, topic shift without confirmation) that could be stored as “avoid” experience.

**Why it matters:** Federated memory should strengthen what works *and* weaken what fails.

**Suggested checks:**
- Compare early turns of resolved vs unresolved within the same intent/category.
- Annotate a sample of failure modes (wrong intent, missing info, policy dead-end, user abandon).

---

### H4 — Outcome fields are usable proxies (with caveats)
**Claim:** Dataset fields such as `status`, `sentiment`, and conversation-end patterns correlate with human judgment of “agent was helpful,” enough to bootstrap success/failure labels — but not perfectly.

**Why it matters:** Real-time systems need an automated outcome signal; we need to know how noisy Syncora’s labels are.

**Suggested checks:**
- Sample 50–100 chats; human label success/partial/fail; compare to `status` / `sentiment`.
- Report precision/recall of naive “status=resolved ⇒ success” rule.

---

### H5 — Reusable unit is smaller than the full chat
**Claim:** The transferable memory item is closer to a structured card than a raw transcript, e.g.:

```text
problem_class: …
constraints_that_mattered: …
questions_that_unlocked: …
action_or_answer_that_worked: …
failure_modes_seen: …
support_count: N   # how many chats reinforced this
```

**Why it matters:** Cross-agent enrichment must stay inside token budgets (see enrichment cap in product specs).

**Suggested checks:**
- For 10–20 successful chats in one cluster, try writing such cards by hand.
- Note what is lost vs what remains useful when the card replaces the transcript.

---

### H6 — Cross-industry transfer is limited; within-industry is stronger
**Claim:** Experience transfers more reliably inside the same `industry` (or closely related categories) than across distant industries, even when intent labels look similar (e.g. “refund” in retail vs SaaS).

**Why it matters:** Visibility / scope of shared memory (global vs domain-scoped).

**Suggested checks:**
- Same intent across industries: do successful agent moves still look valid?
- Flag cases where cross-industry reuse would be harmful.

---

### H7 — Evidence accumulation should change rank
**Claim:** When the same structured experience appears in many independent successful chats, it should rank higher for injection into later sessions (more facts → stronger recommendation), analogous to the enrichment scoring intuition in the product (similarity, reputation, cross-reference).

**Why it matters:** Connects dataset patterns to the cross-agent enrichment design.

**Suggested checks:**
- Frequency of near-duplicate successful patterns within a cluster.
- Sketch a simple frequency-weighted score and show example rankings.

---

### H8 — Partial success is common and must not be treated as full success
**Claim:** Many chats end with mixed signals (user still uncertain, issue only partly addressed). Treating them as full “success” pollutes shared memory.

**Suggested checks:**
- Find conversations where `status` looks positive but final customer turns still express doubt.
- Propose a 3-way label: success / partial / fail.

---

## 6. How to work the dataset (practical playbook)

1. **Load & reshape** — pivot turns into conversation objects (`conversation_id` → ordered list of messages + metadata).
2. **Filter** — start with 1–2 industries and 3–5 high-frequency intents/categories to keep analysis tractable.
3. **Label a gold sample** — 50–100 conversations with human success/partial/fail + free-text “what was the real problem?”
4. **Cluster** — embed early customer text; compare clusters to `intent`/`category` labels.
5. **Path mining** — within clusters, summarize agent moves that precede good vs bad endings.
6. **Write example cards** — 10–20 structured experience cards from real rows.
7. **Falsify** — actively hunt cases that break H1–H4.

Tools are up to the analyst (pandas/polars, embeddings, light clustering, spreadsheet for gold labels).

---

## 7. What we want back from the analyst

A short written report (can be a doc or PR comment thread) containing:

| Section | Content |
|--------|---------|
| Dataset slice used | Industries, intents, N conversations, any filters |
| Gold sample | How labels were defined; agreement notes if more than one rater |
| Hypothesis verdicts | For each of H1–H4 (and others if touched): **support / weak support / reject**, with 2–5 concrete examples |
| Proposed definitions | Working definitions of *problem class*, *success*, *experience card* |
| Risks / traps | Where naive automation would learn the wrong thing |
| Recommendation | Top 1–2 hypotheses worth a formal offline experiment next |

Please quote short message excerpts and conversation structure; no need to dump full long chats.

---

## 8. Alignment with product (for context only)

Product already assumes:

- Anonymous users; remember *what was learned*, not identity (`docs/01-business-idea.md`).
- Cross-agent enrichment with a fixed scoring formula and top-K cap (`openspec/specs/cross-agent-enrichment/spec.md`).

This research pass is meant to ground those assumptions in observable dialogue patterns: **what** to extract, **when** two sessions are related, and **how** success/failure should update shared rank.

---

## 9. Open questions for product / founders (optional answers later)

These are not blockers for the analyst, but answers will sharpen the next experiment:

1. Is shared memory primarily **within one business vertical** (e.g. only home-improvement agents) or intentionally cross-vertical?
2. Should “success” be defined only as task resolution, or also include soft outcomes (user satisfaction, reduced time-to-answer)?
3. How aggressive should we be about storing **negative** experience (what failed) vs only positive playbooks?
4. Minimum evidence: is one successful chat enough to publish a shared fact, or do we need recurrence (N≥k)?

---

## 10. Non-goals for this pass

- Building production real-time pipelines
- Training or fine-tuning models
- Committing raw dataset files into git
- Finalizing the enrichment scoring formula

---

*This brief is intentionally hypothesis-heavy and evidence-light. The analyst’s job is to attach evidence from Syncora (and optionally related datasets) so the team can decide whether the federated “learn from other agents’ chats” idea has a workable extraction logic.*
