# Research datasets: Customer–Agent dialogues (vetted acquisition package)

**Role of this doc:** dataset scout package. A stranger should be able to obtain the data and reproduce the cited measurements without asking anyone.

**Related:** [`research-brief-cross-session-experience.md`](./research-brief-cross-session-experience.md) · probe: [`../research/probe_dataset.py`](../research/probe_dataset.py)

> Numbers tagged **(review)** come from the PR #4 file-level probe (not the Hugging Face card). Reproduce the canned block with:
>
> ```bash
> python research/probe_dataset.py --cite-review
> ```
>
> Then re-run the same metrics on the downloaded file with `--kind` / `--path`.

---

## Acceptance checklist (file, not card)

A dataset is eligible as **primary** for a hypothesis only if all of these pass on the *downloaded file*:

- [ ] Schema matches the file header (not the dataset card)
- [ ] Real text: usable median real tokens/turn, no random padding, language filterable
- [ ] Genuinely multi-turn (not one SFT row per exchange)
- [ ] Outcome is **organic** or **action-derived**, not a sampled column with a near-uniform distribution
- [ ] Recurring **problem types** (enough to cluster) — needed for H1
- [ ] Recurring **source entities** (same brand/agent appears more than once) — needed for H7 / `source_reputation`
- [ ] License stated, with a commercial-use verdict

Fail “real text” or “organic/action-derived outcome” → not primary, regardless of file size.

---

## Working set (what the lab should download first)

### 1. TWCS conversations — primary for H1 / H5 / weak H4

| | |
|--|--|
| **Preferred path** | Hugging Face [`TNE-AI/customer-support-on-twitter-conversation`](https://huggingface.co/datasets/TNE-AI/customer-support-on-twitter-conversation) |
| **Why this path** | Threads already assembled (`Customer:` / `Support:` prefixes). No Kaggle API key. Viewer works. |
| **Fallback** | Kaggle [`thoughtvector/customer-support-on-twitter`](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) — raw tweets + `in_response_to_tweet_id`. Use if you need timestamps / tweet ids the mirror may drop. |
| **Auth** | HF: none for public download. Kaggle fallback: Kaggle account + API token. |
| **Expected count** | TNE-AI card/viewer: **794,335** conversations, **109** company values. |
| **License (source TWCS)** | **CC BY-NC-SA 4.0** on Kaggle; commercial use of the full set requires contact `stuart@thoughtvector.io`. |
| **License (TNE-AI mirror)** | **Unknown on the dataset card** (Q2). Treat as **research-only**, same as source, until legal signs off. A mirror does **not** inherit redistribution rights automatically. |
| **Commercial?** | **No** (NC + SA on the source). Research / hackathon only. |
| **Outcome origin** | Organic-implicit. Final customer-turn signal **(review, n=500):** 11% clearly positive / 4% clearly negative / **85% no signal**. Keyword rules will not carry H4; need an LLM judge or a proxy. |
| **Repeat sources** | **Yes.** 93 brands with repeats in the 500-sample (e.g. AmazonHelp ×52, AppleSupport ×36). This is the H7 home, not ABCD. |
| **Text quality (review, n=500)** | median **18** real words/turn; 5,836 distinct tokens; hapax share **0.56** (natural language); median **3** turns (max 48); **103** distinct turn patterns / 500 convos. |

```bash
# Preferred (no auth)
pip install datasets pandas pyarrow
python - <<'PY'
from datasets import load_dataset
ds = load_dataset("TNE-AI/customer-support-on-twitter-conversation", split="train")
print(ds)
print(ds.column_names)
print(len(ds))
ds.to_parquet("twcs_conversations.parquet")
PY
python research/probe_dataset.py --kind twcs --path twcs_conversations.parquet --sample 500
```

**Starting filter (Q6 — share of noise not measured; this is the minimum clean step):**
keep threads with ≥1 `Support:` turn; drop conversations whose only support line is a follow/welcome template; optional language filter on the first customer turn. Exact non-English share: **unknown (Q5)** — measure with langdetect on a 2k sample before claiming “English corpus”.

**Provenance of the mirror (Q2):** not independently re-counted against the Kaggle tweet graph in this PR. Spot-check a handful of threads against Kaggle if you enable the fallback. If the mirror drops turns, stop and say so.

---

### 2. ABCD — primary for H2 / H3 / H5 (playbook-scored cards)

| | |
|--|--|
| **Path** | GitHub **[asappresearch/abcd](https://github.com/asappresearch/abcd)** — **not** the gated HF copy |
| **Files** | `data/abcd_v1.1.json.gz` (~37 MB) · `data/guidelines.json` · `data/ontology.json` |
| **Auth** | none |
| **Expected count** | **10,042** human–human dialogues; **10 flows / 55 subflows** (review + ontology) |
| **License** | **MIT** |
| **Commercial?** | **Yes** |
| **Outcome origin** | **No `outcome` column.** Proposed derivation: compare performed `speaker: "action"` sequence to the ordered `actions` in `guidelines.json` for that subflow (Q8). Treat as action-derived, not sampled — **distribution unknown until probed**. |
| **Repeat agent identity** | **No.** H7 / `source_reputation` has **no home** in ABCD. |
| **Scale (Q7)** | 10,042 / 55 ≈ **183** per subflow *if uniform*. Actual per-subflow histogram: **unknown until** `probe_dataset.py --kind abcd`. If the tail is thin, group subflows by flow before success/fail path comparison. |

`guidelines.json` is a first-class asset: per subflow it records the **exact action sequence and instructions** human agents were required to follow. H2/H5 become measurable — extract a card from a conversation, score it against the documented playbook — instead of unsupervised path mining.

```bash
mkdir -p data/abcd && cd data/abcd
curl -L -o abcd_v1.1.json.gz https://github.com/asappresearch/abcd/raw/master/data/abcd_v1.1.json.gz
curl -L -o guidelines.json https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json
curl -L -o ontology.json https://raw.githubusercontent.com/asappresearch/abcd/master/data/ontology.json
gunzip -k abcd_v1.1.json.gz
# sanity: file should be tens of MB uncompressed; 10k-ish dialogues in train+dev+test
python ../../../research/probe_dataset.py --kind abcd --path abcd_v1.1.json
```

(Adjust the relative path to `research/probe_dataset.py` from wherever you run it.)

---

### 3. MultiWOZ 2.2 — structure only, not a support-outcome corpus

| | |
|--|--|
| **Do not** | `load_dataset("pfb30/multi_woz_v22")` on datasets 3.x — the repo is a **loading script only** (`.gitattributes`, README, `.py`). Script loading was removed. |
| **Do** | parquet on the auto-convert ref |
| **License** | Apache 2.0 |
| **Commercial?** | **Yes** |
| **Outcome** | Task success in the MultiWOZ sense (booking informed/requested), **not** support resolution. |

```bash
python - <<'PY'
from datasets import load_dataset
ds = load_dataset(
    "pfb30/multi_woz_v22",
    split="train",
    revision="refs/convert/parquet",
)
print(ds)
print(len(ds))
PY
```

If that revision fails, fetch `v2.2/train/0000.parquet` from the dataset's convert tree on the Hub.

---

## Demoted / do-not-primary

### Syncora / strova-ai — smoke-test only

Renamed: `syncora/customer_support_conversations_dataset` → [`strova-ai/customer_support_conversations_dataset`](https://huggingface.co/datasets/strova-ai/customer_support_conversations_dataset). HF viewer **broken** (`CastError`); card schema ≠ file schema. **Do not trust the preview.**

Actual header: `conv_id, turn_index, role, text, timestamp, industry, product, issue_type, language, channel, customer_name, agent_name, overall_sentiment, overall_urgency, outcome, primary_intent`.

**(review)** 3,430 complete conversations; median 14 turns (10–18); median 68 words/message of which **8 real** (~88% padding); 1,044,426 distinct tokens, **1,005,883 hapax**, **149** tokens occur >50×; `outcome` counts 704/694/689/686/657 (**sampled**); every label constant within a conversation; `primary_intent` × `issue_type` = 14×15 all 210 cells filled; names unique per conversation → no repeat entities.

Use only to verify that `probe_dataset.py` flags padding + uniform labels. **Not for H1–H7.**

### Lakshan2003

SFT rows: `instruction / conversation_history / history_summary / client_question / agent_answer / refined_agent_answer`. No outcome. Answers are LLM-refined. Cannot ground H2/H3/H4.

### Saif7800, CallCenterEN, DialogStudio

- `Saif7800/customer_qa_dataset` — viewer `TypeError` (`tool_name` struct). Probe files or drop.
- `AIxBlock/92k-real-world-call-center-scripts-english` — Arrow error; payload is **12 ZIP archives**. License **CC BY-NC 4.0** → research/hackathon only, **cannot inform a shipped product**. Realism corpus if someone unpacks ZIPs; not in the minimum lab slice.
- `Salesforce/dialogstudio` — **401 gated**.

### Organic-outcome dumps listed earlier (Ubuntu / StackExchange / GitHub-closed-by-commit)

**Removed as placeholders (Q4).** No links, schemas, licenses, or measured outcome distributions were attached. Do not start a week of work on them from this brief. Re-open only with a verified package (link + schema + license + how outcome is derived + distribution).

---

## Commercial filter (Q1)

| Dataset | License | Shipped product? |
|---------|---------|------------------|
| ABCD | MIT | Yes |
| MultiWOZ 2.2 | Apache 2.0 | Yes |
| TWCS (Kaggle source) | CC BY-NC-SA 4.0 | **No** (contact author for commercial) |
| TNE-AI TWCS mirror | Unknown card; treat as source NC | **No** until legal review |
| CallCenterEN | CC BY-NC 4.0 | **No** |
| Syncora/strova-ai | card claimed open; irrelevant — data unusable | n/a |

Hackathon research may use the NC sets. Anything that ships with Federated Agent Memory should be designed so it can be *validated* on ABCD (and MultiWOZ structure), not *trained* on TWCS, unless a commercial license is obtained.

---

## Does any single corpus pass the full bar? (Q3)

**No.** Working combination:

| Hypothesis | Corpus | Notes |
|------------|--------|-------|
| H1 clustering despite paraphrase | TWCS | |
| H2 successful paths | ABCD + `guidelines.json` | |
| H3 early failure signals | ABCD (first-k actions/turns only) | |
| H4 outcome-proxy noise | TWCS 11/4/85 signal — **weak**; ABCD action-vs-guidelines — **proposed** |
| H5 experience cards | ABCD (score vs playbook) + TWCS (draft cards) | |
| H6 cross-industry transfer | TWCS brands as stand-ins; **weak** |
| H7 evidence accumulation / reputation | TWCS brands only. **No home in ABCD.** |
| H8 partial success | TWCS 85% no-signal makes this messy |
| H9 staleness / harm | **No viable static dataset** — needs replay + dated facts |
| H10 cost | **No dataset** — eval harness ([issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5)) |
| Transfer “does memory help the next chat” | **No static dataset** — [issue #5](https://github.com/camorazrushimoe/federated-agent-memory/issues/5) |
