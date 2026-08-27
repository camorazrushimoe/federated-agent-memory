# Research Brief: Cross-Session Experience Extraction

**Audience:** Lab / data analyst  
**Status:** Hypothesis brief + dataset mapping. Experiments start only after the lab sanity-checks the corpora in [`research-customer-support-dialogue-datasets.md`](./research-customer-support-dialogue-datasets.md).  
**Replay / transfer eval:** [issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5) (not this brief).

Product context: `docs/01-business-idea.md`. Scoring formula in `openspec/specs/cross-agent-enrichment/spec.md` is **provisional / unvalidated** (see §8).

---

## 1. Problem

Agents improve offline today. We want a shared memory of *what was learned* (not who the customer was) so a later agent can reuse another session's experience.

**Open gap:** no evidence-based rule for what to extract from unrelated chats and put into shared memory.

This brief is for attaching evidence to hypotheses. It is not permission to run H1–H4 on Syncora.

---

## 2. Goal of this research pass

After the corpus is approved:

- Find transferable patterns (or falsify them).
- Propose operational definitions: same problem, success, experience card.
- Rank which hypotheses deserve a formal experiment.

Analyst report: verdict per hypothesis using the **decision rules in §5**, with examples.

---

## 3. Corpora (replace Syncora)

Full acquisition, licenses, and file-level measurements: [`research-customer-support-dialogue-datasets.md`](./research-customer-support-dialogue-datasets.md).

**Do not use Syncora / `strova-ai/customer_support_conversations_dataset` as primary.** Renamed from `syncora/…`. HF viewer is broken (`CastError`). Card schema ≠ CSV schema. File header is:

`conv_id, turn_index, role, text, timestamp, industry, product, issue_type, language, channel, customer_name, agent_name, overall_sentiment, overall_urgency, outcome, primary_intent`

There is no `status`, `priority`, `category`, `sub_category`, `intent`, `conversation_id`, `turn_id`, or `message`. Text is ~88% padding; `outcome` is sampled-uniform. Smoke-test the probe script on it if you want; then drop it.

### Who serves which hypothesis

| Hyp | Corpus | Why |
|-----|--------|-----|
| H1 | **TWCS** via `TNE-AI/customer-support-on-twitter-conversation` | Real paraphrase, 103 turn patterns / 500 convos |
| H2 | **ABCD** + `guidelines.json` | Ground-truth action sequences / playbook |
| H3 | **ABCD**, first *k* turns/actions only | Avoid last-turn leakage |
| H4 | TWCS implicit 11/4/85; ABCD action-vs-guidelines (proposed) | No sampled `status` field anywhere honest |
| H5 | ABCD cards scored vs playbook; TWCS for wording | |
| H6 | TWCS brands as weak stand-in | No coherent industry×intent grid in Syncora |
| H7 | TWCS brands only | ABCD has no repeat agent identity |
| H8 | TWCS, weakly | 85% of finals have no signal |
| H9 | **no viable static dataset** | issue #5 |
| H10 | **no dataset** | issue #5 |

Kaggle `thoughtvector/customer-support-on-twitter` is a **fallback** if you need raw tweet ids / timestamps. Preferred path is the TNE-AI assembled conversations (no Kaggle auth).

ABCD comes from GitHub `asappresearch/abcd` (`data/abcd_v1.1.json.gz` + `guidelines.json`), not gated HF.

---

## 4. Core research questions

1. Similarity of underlying problems across wording.
2. Extractable unit (transcript vs card).
3. Outcome signal that is not a generator knob.
4. Transfer to a *later* conversation — **out of scope here** ([issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5)).
5. Noise vs shareable signal.
6. Evidence strength / ranking without a feedback loop (H7).

---

## 5. Hypotheses, baselines, decision rules

Verdicts are **support / reject** against a pre-registered number. “Weak support” is not a legal verdict unless the metric lands in a stated gray band.

Also report: *what would have changed your verdict.*

### H1 — Problem clustering across lexical variation
**Claim:** Same underlying issue forms recoverable clusters from early customer text despite different wording.

**Corpus:** TWCS.  
**Baseline:** cluster purity using BM25 / keyword overlap on the first customer turn, same sample.  
**Decision rule:** support iff embedding clusters reach purity ≥ **0.80** on a 100-conversation human-audited sample **and** beat BM25 by ≥ **0.15** purity. Otherwise reject.  
**Trap:** recovering the brand name or a canned template is not semantic robustness.

### H2 — Successful paths share structure
**Claim:** Within a problem class, good outcomes share a short action/question sequence that is *not* just “easy tickets finish faster”.

**Corpus:** ABCD + `guidelines.json`.  
**Control:** difficulty / subflow frequency (or flow-level grouping if a subflow has too few dialogs — Q7).  
**Baseline:** “length of conversation predicts success”.  
**Decision rule:** support iff, *within* a difficulty band, playbook-aligned action sequences are ≥ **15 pp** more common in successes than failures. If the gap disappears after the difficulty control, reject (tautology).  
**Negative result looks like:** same action prefix in success and fail once difficulty is held fixed.

### H3 — Failures leave early signals
**Claim:** Unsuccessful chats are detectable from the **first k turns only**, with outcome-marker templates stripped.

**Corpus:** ABCD.  
**Baseline:** majority-class predictor.  
**Decision rule:** support iff first-*k* model beats majority class by ≥ **10 pp** accuracy on a held-out set *and* last-turn features are not in the input. Otherwise treat as leakage and reject.

### H4 — Outcome fields as proxies
**Claim (revised):** We do not have a trustworthy sampled `status` column. Test whether (a) TWCS final-turn polarity or (b) ABCD action-completion vs `guidelines.json` agrees with a 50–100 chat human gold set.

**Decision rule:** support a proxy iff precision ≥ **0.70** for the “success” class on that gold set. TWCS keyword polarity alone is expected to **fail** (85% no signal). If it fails, say so; do not invent a `status` column.

### H5 — Card smaller than the transcript
**Claim:** A structured card (problem class, constraints, unlocking questions, action that worked, failure modes, support_count) remains useful when the transcript is dropped.

**Corpus:** ABCD cards scored against `guidelines.json`.  
**Decision rule:** support iff ≥ **8/10** hand-built cards from one subflow recover the playbook's required actions (human rubric). Otherwise the unit is wrong.

### H6 — Transfer stronger within a vertical
**Corpus:** TWCS brands. Syncora cannot test this (intent × industry were crossed at random).  
**Decision rule:** support iff within-brand nearest-neighbor cards are judged relevant ≥ **20 pp** more often than cross-brand cards on a 50-pair audit. Else reject or mark underpowered.

### H7 — More independent evidence → higher rank
**Corpus:** TWCS brands only. **No home in ABCD.**

**Design bug (spec, not just research):** if an injected fact helps a later session and that session is counted as *new* support, `support_count` is a positive feedback loop. **Mitigation (required before any experiment):** tag conversations that received an enrichment with the injected fact IDs; **exclude** those conversations from that fact's support counter. Only independent evidence raises rank.

`source_reputation` attaches to the **agent / brand**, not the customer (anonymity in `01-business-idea.md`).

**Baseline:** unranked / recency-only.  
**Decision rule:** left to the replay harness ([issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5)) — static frequency on TWCS can only show that repeat brands exist.

### H8 — Partial success ≠ success
**Corpus:** TWCS.  
**Decision rule:** if a 50-chat audit finds ≥ **20%** “positive-ish ending, problem not actually solved,” adopt a 3-way label (success / partial / fail) before any automatic write to memory.

### H9 — Staleness and harm
**No viable static dataset.** Shared advice goes stale; reuse can be harmful, not just unhelpful. Spec `recency_weight = 0.15` is untested. Metric lives in [issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5): rate of harmful injections vs helpful.

### H10 — Cost
**No dataset.** Packet tokens + latency at p50/p95 must be beaten by quality gain or the feature is unshippable. [issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5).

---

## 6. Playbook for the lab (after corpus approval)

1. Acquire TWCS (TNE-AI) + ABCD (GitHub gz + guidelines) using the commands in the datasets doc.
2. Run `python research/probe_dataset.py --cite-review` then `--kind` on the files. Confirm counts match §3 of the datasets doc (794,335 TWCS rows / ~10,042 ABCD dialogs). A truncated download is a failed setup.
3. Gold sample: 50–100 TWCS threads + 50 ABCD dialogs in 2–3 subflows.
4. H1 on TWCS with BM25 baseline.
5. H2/H5 on ABCD against `guidelines.json`.
6. H3 first-*k* only.
7. Do not spend further time on Syncora.

---

## 7. What to return

| Section | Content |
|--------|---------|
| Slice | Corpus, N, filters |
| Probe output | pasted JSON from `probe_dataset.py` |
| Gold sample | label definitions |
| Verdicts | support / reject per H1–H8 using §5 rules; H9–H10 = N/A |
| Fragile points | what would flip the verdict |
| Definitions | problem class, success, card schema |
| Next | one experiment worth running, or “blocked on issue #5” |

---

## 8. Spec alignment (provisional)

`README.md` (Architecture v2): Cross-Agent Enrichment (L8) was **folded into the Ranker**; Graph Core (L4) was **removed**. The frozen formula in `openspec/specs/cross-agent-enrichment/spec.md` still uses `graph_proximity × 0.25` and threshold `0.70`. Those numbers were fixed **before** this research and are **unvalidated**. This brief must be allowed to move them; they are not a result.

Dataset scout does not rewrite that spec in this PR. Flag only.

---

## 9. Open product questions (optional)

Same as before: vertical vs cross-vertical memory; resolution vs soft success; how aggressive to store failures; minimum independent N before a fact is published.

---

## 10. Non-goals

- Production real-time pipeline
- Fine-tuning models
- Vendoring raw datasets
- Settling the enrichment weights (they stay provisional)
- Proving transfer on a static dump — that is [issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5)

Methodology items that are *product-spec* (H7 exclusion rule, H9/H10 metrics, graph_proximity removal) are called out here so they are not silent. Implementing them in OpenSpec is a separate change.
