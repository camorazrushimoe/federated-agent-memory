# Research Commission: Shareable Experience for Federated Agent Memory

**For:** Lab Lead · Research Analyst
**From:** Product / founders
**Status:** Open commission. **The method and the success criteria are yours to propose** — see §3.
**Data:** Certified and ready to download — [`research-customer-support-dialogue-datasets.md`](./research-customer-support-dialogue-datasets.md)
**Out of scope here:** proving that injected memory helps a later conversation → [issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5)

> **Founder decisions (answers to §8, recorded):** we have deliberately chosen the
> *widest* options available, because we would rather learn the answers than
> constrain the work into confirming our guesses. Concretely: **sharing scope is
> an open empirical question, not a given (§8.1)**, and **you may explore on any
> accepted corpus without a licence constraint on the research itself (§8.5)**.

---

## 1. What we are building

A memory layer behind customer-facing AI agents. Today every agent has amnesia: whatever it works out in a conversation dies when the chat closes, and the next agent solves the same problem from scratch. We want the experience to survive and to move between agents — while the customer stays anonymous. We remember *what was learned*, never *who asked*.

The canonical story (`docs/01-business-idea.md`):

- **Day 1** — a shopper wants a laptop for video editing under $1500. The agent recommends one; the shopper hesitates about weight. No sale.
- **Day 2** — a different shopper says their laptop shuts down when rendering 4K. The agent finds overheating, recommends better cooling. Sale.
- **Day 3** — a third shopper asks the Day-1 question. The agent already knows that for editing laptops, cooling and weight are what matter. Right recommendation first try.

Three strangers, three conversations, one piece of experience moved automatically between agents.

---

## 2. What we do not know — this is the commission

We can build storage and retrieval. **What we cannot yet specify is the mechanism in the middle:** given a pile of unrelated conversations from different agents and different users, how do you decide what is worth remembering, and how do you make it findable later?

That splits into four linked unknowns. We are commissioning work on **M1–M3**. M4 is context so you know what the output feeds into.

### M1 — Comparison: when are two conversations "about the same thing"?

Two customers describe the same underlying problem in completely different words, to different agents, possibly about different products. Something has to recognise that these belong together, otherwise experience can never be routed from one to the other.

*A useful answer looks like:* an operational definition of "same problem" that a human reviewer agrees with, plus evidence about where it breaks — cases that look similar but must **not** be pooled.

*We are not asking:* which embedding model is best. We care about the definition and its failure modes, not the vendor.

### M2 — Extraction: what is the unit worth keeping?

A full transcript is too big to inject into a later conversation and mostly irrelevant. Something smaller has to carry the value. Our guess is a structured record — problem shape, the constraint that actually mattered, the question that unlocked it, what worked, what failed — but that is a guess and we would rather you falsify it than inherit it.

*A useful answer looks like:* a proposed unit, drafted by hand from real conversations, plus an honest account of what is lost when the transcript is thrown away.

### M3 — Valuation: what makes a unit worth publishing, and when is it strong enough?

Not everything learned is worth broadcasting. Some of it is session-specific noise, some is wrong, some is only half-true. And a single successful conversation is weak evidence — we suspect a pattern should have to recur before it earns rank.

*A useful answer looks like:* candidate signals of value that are actually present in the data, plus the traps — what would a naive rule wrongly promote?

**One thing we already know is a trap, and we want it respected in whatever you design:** if a shared piece of experience gets injected into a later conversation, and that conversation's success is then counted as fresh evidence *for* it, the counter feeds on itself. Popular advice becomes unfalsifiable and early mistakes calcify. Whatever counts as evidence has to distinguish independent confirmation from its own echo.

### M4 — Adoption (context only, not commissioned)

Eventually a later agent has to notice the relevant experience and act on it. Whether that actually improves outcomes cannot be measured on a static corpus — it needs a replay setup where the same conversation runs with and without memory. That is [issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5), separate work. **Do not try to prove transfer from a dump.**

---

## 3. What we are deliberately not prescribing

An earlier version of this document carried pre-registered numeric thresholds written by us — cluster purity ≥ 0.80, beat the baseline by ≥ 0.15, and so on. **We have removed them on purpose.** Designing the analysis is your job, not ours, and our numbers were guesses dressed as requirements.

What we do ask for is the *discipline*, not our version of it:

- **Pick your own criteria, and write them down before you look at the results.** Whatever "this hypothesis held up" means, we want to know what it meant *before* the answer was known.
- **Say what would have changed your mind.** A verdict with no fragility statement is not usable.
- **Baselines beat intuitions.** If a method looks good, we want to know what it beat — including the dumb version of itself.
- **"This is not answerable with this data" is a valid and valuable result.** We would rather pay for a clean negative than a hedged maybe. See §5 for limits we already found.

We are also fine with you reformulating M1–M3 if the data suggests better questions. Tell us why.

---

## 4. The data you have (certified against the files)

Full acquisition commands, licences and measurements: [`research-customer-support-dialogue-datasets.md`](./research-customer-support-dialogue-datasets.md). Every number there is reproducible with `research/probe_dataset.py`.

Two corpora passed acceptance. Everything else we screened failed — including the dataset this PR originally recommended.

| | **ABCD** | **TWCS** |
|--|--|--|
| Source | GitHub `asappresearch/abcd`, one `curl`, no auth | HF `TNE-AI/customer-support-on-twitter-conversation`, no auth |
| Size | 10,042 human–human dialogues | 794,335 assembled threads |
| Text | natural language | natural language, real brands |
| Structure | 10 flows, ~1,000 dialogues each | median 3 turns, 103 distinct turn patterns per 500 |
| Ground truth | **36,482 action turns; 100% of dialogues have ≥1 recorded action.** Plus `guidelines.json`, the playbook human agents were required to follow | none — outcome must be inferred |
| Outcome signal | derivable from actions vs playbook (unproven, see §5) | organic but sparse: **11% positive / 4% negative / 85% no signal** |
| Repeat sources | no persistent agent identity | **yes** — 109 brands, e.g. AmazonHelp ×52 in a 500 sample |
| Licence | **MIT — commercially clean** | source is CC BY-NC-SA; the mirror states no licence → **research only** |

Practically: **ABCD is where the ground truth is** — it is the only corpus where "what the agent actually did" is recorded rather than guessed, and the only one we could ship against. **TWCS is where the messy reality is** — real people, real paraphrase, real unresolved cases, and the only place where the same source recurs.

> **Licence: explore freely.** Licences restrict redistributing the *data* and
> shipping artefacts trained on it — they do not restrict what you may learn from
> reading it. So: use either corpus, whichever suits the question. Three practical
> limits, none of which should shape your method: don't commit raw data to this
> repo; don't train a production artefact on TWCS; and if a finding turns out to
> hold *only* on TWCS, flag it early so we can decide whether to license the data
> or re-derive it. Legal signs off before anything ships, not before you start.

---

## 5. Limits we already verified — please don't rediscover these

This is the part we did so you don't have to. All of it is reproducible via the probe script.

**The dataset this PR originally proposed is unusable.** `strova-ai/customer_support_conversations_dataset` (formerly `syncora/…`): median 68 words per message of which **8 are real** — ~88% random padding; the entire recurring vocabulary is **149 tokens**; `outcome` is near-uniform across 5 values (704/694/689/686/658 per conversation) so it was sampled rather than derived; every label is constant within a conversation; intent × issue_type fills **210 of 210** cells, i.e. crossed at random; no source ever repeats. Its HF viewer is broken and its card contradicts its own CSV. Use it only to sanity-check that the probe flags garbage.

**ABCD's subflow level is underpowered.** The data carries **96 distinct subflows**, not the 55 in `ontology.json` (50 are absent from the ontology, 9 ontology entries never appear). Distribution: min 3, **median 69.5**, max 361 — **54 of 96 subflows have under 100 dialogues, 36 have under 50.** Splitting a 70-dialogue subflow by outcome and then controlling for anything leaves cells of ~15. Flow level is healthy (10 flows, 713–1,094 each); we suggest starting there, but the choice is yours.

**ABCD's playbook does not join to the data out of the box.** `guidelines.json` documents 55 subflows in Title Case (`Initiate Refund`, `Boots FAQ`); the data uses snake_case (`return_color`, `boots_how_1`). Naive name matching joins **32 names = 45.6% of conversations**. A manual 96→55 mapping table is required before playbook comparison can cover the corpus. **This is unbuilt work — budget for it or scope around it.** (If you build it, commit it; we want it reusable.)

**Outcome labels are the weak point everywhere.** No corpus we accepted has a trustworthy outcome column. TWCS gives an organic signal on only 15% of threads. ABCD's is derivable from actions but that derivation is unproven. Treat "how do we even know it went well" as a first-class problem, not a preprocessing step.

**Reputation and evidence-accumulation have no clean home.** They need the same source to recur. ABCD has no persistent agent identity; TWCS has brands, which is a loose stand-in at best. If M3 depends on source history, say so and we will treat it as blocked rather than pretend it was tested.

---

## 6. How we would like to run this

Short phases, with a checkpoint after each, so we can redirect before effort is sunk.

**Phase 0 — Data sanity (a few days).** Download both corpora, run `probe_dataset.py`, confirm the numbers in §5 reproduce on your machine. If they don't, stop and tell us — that is a finding about us, not about you. Confirm the corpora are workable, or reject them.

**Phase 1 — Method proposal (short doc, no results yet).** How you intend to attack M1–M3, what you will measure, your pre-registered criteria, what you expect to be hard. We review and confirm before the main pass. This is where we would rather argue than after.

**Phase 2 — Closeout report.** Contents in §7.

We are not putting a deadline in this document because we don't know what the work costs. **Tell us what Phase 2 needs and we will scope it.** If something in §5 makes a phase pointless, say that instead of absorbing it.

---

## 7. Closeout report — what we actually want back

Please write for a reader who has not touched the data. Short excerpts and conversation IDs, not full transcripts. Raw data stays out of this repo.

We want **found things**, not a methodology essay. Concretely:

1. **What is actually in this data.** The conversation taxonomy you found — by flow, industry, brand — with counts. Which problem types recur often enough to be worth sharing at all, and which are one-offs. We currently have almost no picture of this and it is the thing we most want.
2. **How you compared conversations (M1).** Your working definition of "same problem", how well it held, and concrete examples of pairs a human agrees on. Equally important: the false friends — pairs the method matched that must never be pooled.
3. **What you would keep (M2).** A proposed unit of shareable experience, with **real worked examples** drawn from real conversations. What survives the transcript being dropped, and what is lost.
4. **What made something valuable (M3).** The signals of value you found in the data, the rule you would use to promote a unit into shared memory, and how you would keep the evidence counter honest. Include what a naive rule would wrongly promote.
5. **What you checked and killed.** Explicitly. Which ideas did not survive contact with the data, and why. This is as valuable to us as the positive results — it stops us rebuilding them later.
6. **What this data cannot answer.** Add to §5.
7. **Verdict and the single next experiment.** Is the mechanism viable on real data? If yes, what is the *one* experiment you would run next and what would it settle? If no, what data would we need to acquire?

A short structured summary we can drop into a decision meeting is worth more than length.

---

## 8. Questions we owed you — answered

Where we had a choice between constraining the work and leaving it open, we chose open. If any of these openness turns out to be unhelpful — if you'd rather we just picked — say so and we will.

**1. Scope of sharing — ANSWERED: treat it as an open empirical question.**
We are not pre-deciding whether shared memory works within one vertical or across verticals. Both are on the table, and which one holds up is more valuable to us than either assumption. Report which way the data points and at what cost — if cross-vertical reuse turns out to be actively harmful, that is a first-class finding, not a failure.

**2. Definition of success — ANSWERED: yours to propose, and we expect more than one.**
Do not force everything into "resolved / not resolved". If the data supports a softer notion — fewer turns to an answer, no escalation, no repeat contact, explicit customer confirmation — propose the set you can actually measure and say which is most trustworthy. We would rather have two honest partial signals than one forced binary. Note §5: no accepted corpus hands you a reliable outcome column, so this is part of the research, not setup.

**3. Negative experience — ANSWERED: in scope, and we want it.**
Store what failed, not only what worked. Our instinct is that advice-to-avoid is the highest-value content we could hold, and also the most dangerous to get wrong. Treat "what should this agent *not* do" as a legitimate unit of shareable experience under M2, and tell us if the data can support it.

**4. Minimum evidence to publish — ANSWERED: no number from us.**
We deliberately will not set N. Recommend one from what you observe, or tell us the data cannot support a defensible threshold. If your answer is "it depends on the type of claim", that is a better answer than a constant — see the echo trap in §2/M3.

**5. Commercial constraint — ANSWERED: relaxed, explore freely.**
See the callout in §4. Use whichever accepted corpus fits the question. The three limits are operational, not methodological: no raw data committed to this repo, no production artefact trained on TWCS, and an early flag if a finding holds *only* on non-commercial data. Do not narrow your method to stay inside a licence.

**Still genuinely undecided (we will answer when it matters):** whether a shared fact is scoped per tenant, per vertical, or globally. That is a product decision downstream of your findings on M1, so it would be backwards to fix it now.

## 9. Questions we would like back from you

1. Does the ABCD action trace plus `guidelines.json` actually support a defensible outcome signal, once the mapping table exists?
2. Given §5, is any of M1–M3 simply not answerable with what we have? Name it early.
3. What would you want that we don't have — and is it buyable, or does it have to come from our own agent traffic?

**Standing permissions**, so you don't have to ask:

- **Propose more data.** If the two accepted corpora are not enough, name what you want and we will try to get it. The acceptance checklist in the datasets doc is the bar; anything that clears it is worth proposing.
- **Reformulate the questions.** M1–M3 are our decomposition of the problem, not a specification. If the data suggests a better cut, take it and tell us why.
- **Restructure the phases.** §6 is a suggestion. If a different shape gets to a real answer faster, propose it.
- **Return a negative result.** "This is not answerable with this data, and here is what would be" is a complete deliverable, not a failure to deliver.

---

## 10. Working agreements

- **No raw datasets in this repo.** Download locally; cite IDs and short excerpts.
- Numbers in a report should be reproducible — extend `research/probe_dataset.py` rather than working in a scratch notebook that dies with the session.
- Commit the 96→55 mapping table if you build it.
- The scoring formula in `openspec/specs/cross-agent-enrichment/spec.md` (weights, threshold `0.70`, and a `graph_proximity` term whose component was removed in Architecture v2) is **provisional and unvalidated**. It was written before this research. It is not a constraint on your findings — if your work contradicts it, the spec is what changes.

---

*This commission exists because the honest state of the product is: we have a clear story about agents sharing experience, and no evidence-based rule for what that experience is or how to recognise it. That rule is what we are asking for.*
