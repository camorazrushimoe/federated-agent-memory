# Certified data package: customer–agent dialogue corpora

**Role of this doc:** dataset acceptance and acquisition. A stranger should be able to obtain the data and reproduce every number here without asking anyone.

**Commission this data serves:** [`research-commission-shareable-experience.md`](./research-commission-shareable-experience.md)
**Probe:** [`../research/probe_dataset.py`](../research/probe_dataset.py)

> This document answers **"is this corpus fit to work on"** — not "what does it contain". Findings are the lab's output, not ours.
>
> Numbers tagged **(probe)** are reproducible. Each cited block records the command that regenerates it:
>
> ```bash
> python research/probe_dataset.py --cite-review   # prints cited constants (no computation)
> ```
>
> Then run the `--kind` command shown next to each corpus and compare. **If they disagree, that is a bug on our side — tell us.**

---

## Verdict

| Corpus | Verdict | Serves |
|--------|---------|--------|
| **ABCD** (`asappresearch/abcd`) | **ACCEPT** — MIT, action ground truth | primary; the only commercially clean corpus |
| **TWCS** (`TNE-AI/…-twitter-conversation`) | **ACCEPT for research** — non-commercial licence | real paraphrase, real brands, recurring sources |
| MultiWOZ 2.2 | accept, narrow | dialogue structure only; not a support-outcome corpus |
| Syncora / `strova-ai` | **REJECT** | padded text, sampled labels — smoke-test only |
| Lakshan2003 · Saif7800 · CallCenterEN · DialogStudio | **REJECT / blocked** | see §5 |

---

## 1. Acceptance checklist (run against the file, never the card)

A corpus is eligible as **primary** only if all of these pass on the *downloaded file*:

- [ ] Schema matches the file header, not the dataset card
- [ ] Real text — recurring vocabulary, no random padding, language filterable
- [ ] Genuinely multi-turn, with turn structure that *varies* between conversations
- [ ] Outcome is **organic** or **action-derived** — not a sampled column with a near-uniform distribution
- [ ] Recurring **problem types**, enough to group
- [ ] Recurring **source entities** — the same brand/agent appears more than once
- [ ] Enough conversations **per group** to compare subsets (statistical power, not just totals)
- [ ] Licence stated, with an explicit commercial-use verdict

Fail "real text" or "organic/action-derived outcome" → not primary, regardless of file size.

**The single most robust discriminator we found is `hapax_share`** — the fraction of tokens occurring exactly once. Natural language reuses its vocabulary; random padding does not.

| Corpus | `hapax_share` | Reading |
|--------|---------------|---------|
| Syncora / strova-ai | **0.963** | padded — reject |
| TWCS (TNE-AI) | **0.56** | natural language |

---

## 2. ABCD — primary

| | |
|--|--|
| **Path** | GitHub **[asappresearch/abcd](https://github.com/asappresearch/abcd)** — **not** the gated HF copy (`Salesforce/dialogstudio` returns 401) |
| **Files** | `data/abcd_v1.1.json.gz` (37 MB) · `data/guidelines.json` · `data/ontology.json` |
| **Auth** | none |
| **Licence** | **MIT** (verified on the repo) |
| **Commercial use** | **Yes** |
| **Counts (probe)** | **10,042** dialogues = train 8,034 / dev 1,004 / test 1,004 |
| **Structure (probe)** | 10 flows, **713–1,094 dialogues per flow** |
| **Action ground truth (probe)** | **36,482 action turns; 100% of dialogues contain ≥1 action** |
| **Outcome origin** | derivable by comparing performed actions to the documented playbook — **proposed, unproven** |
| **Repeat source identity** | **No** — no persistent agent identity |

```bash
mkdir -p data/abcd && cd data/abcd
curl -L -o abcd_v1.1.json.gz https://github.com/asappresearch/abcd/raw/master/data/abcd_v1.1.json.gz
curl -L -O https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json
curl -L -O https://raw.githubusercontent.com/asappresearch/abcd/master/data/ontology.json
gunzip -k abcd_v1.1.json.gz

# expect: n_conversations 10042, action_turns_total 36482
python research/probe_dataset.py --kind abcd \
    --path abcd_v1.1.json --guidelines guidelines.json
```

### Why this corpus matters

Each conversation carries turns with `speaker: "action"` recording **what the agent actually did** — the action name plus arguments (e.g. `pull-up-account`). Alongside it, `guidelines.json` documents, per subflow, the **exact ordered action sequence and instructions the human agents were required to follow**.

This is the only corpus we found where the "correct playbook" is written down next to real conversations. It is what makes evaluating extracted experience possible rather than purely unsupervised.

### Two limits you must plan around

**Subflow level is underpowered (probe).** The data contains **96 distinct subflows**, not the 55 declared in `ontology.json` — 50 appear in the data but not the ontology (`boots_how_1..4`, `jacket_how_1..4`, …), and 9 ontology entries never appear in the data.

| per-subflow | value |
|--|--|
| min | **3** |
| median | **69.5** |
| max | **361** |
| subflows under 100 dialogues | **54 of 96** |
| subflows under 50 dialogues | **36 of 96** |

Splitting a 70-dialogue subflow by outcome and controlling for anything else leaves cells around 15. **Flow level (10 groups, 713–1,094 each) is healthy** and is the safer default.

**The playbook does not join to the data (probe).** `guidelines.json` names subflows in Title Case (`Initiate Refund`, `Boots FAQ`); the data uses snake_case (`return_color`, `boots_how_1`). Naive name normalisation matches **32 names, covering 45.6% of conversations** (4,582 / 10,042).

→ **A manual 96 → 55 mapping table does not exist and has to be built.** Until it does, playbook comparison covers under half the corpus. This is unbudgeted work; scope it explicitly. **If you build it, commit it** — we want it reusable.

---

## 3. TWCS — real-world corpus, research licence only

| | |
|--|--|
| **Preferred path** | HF [`TNE-AI/customer-support-on-twitter-conversation`](https://huggingface.co/datasets/TNE-AI/customer-support-on-twitter-conversation) |
| **Why this path** | threads already assembled with `Customer:` / `Support:` prefixes; parquet; viewer works; **no auth** |
| **Fallback** | Kaggle [`thoughtvector/customer-support-on-twitter`](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) — raw tweets + `in_response_to_tweet_id`, needs a Kaggle API token and thread reconstruction. Use only if you need raw tweet ids / timestamps the mirror may drop. |
| **Counts** | **794,335** conversations, **109** company values |
| **Licence (source)** | CC BY-NC-SA 4.0 on Kaggle; commercial use requires contacting the author |
| **Licence (this mirror)** | **none stated on the card** — verified absent. Treat as at least as restrictive as the source. |
| **Commercial use** | **No** — research / hackathon only, pending legal review |
| **Text (probe, n=500)** | median **18** words/turn · **9** real words/turn (median real words, ≥50-occurrence tokens); 5,836 distinct tokens; `hapax_share` **0.56** |
| **Structure (probe, n=500)** | median **3** turns (max 48); **103 distinct turn patterns** — genuine structural variation |
| **Repeat sources (probe)** | **Yes** — 93 brands recur in a 500 sample (AmazonHelp ×52, AppleSupport ×36) |
| **Outcome signal (probe)** | final customer turn: **11% clearly positive · 4% clearly negative · 85% no signal** |

```bash
pip install datasets pandas pyarrow
python - <<'PY'
from datasets import load_dataset
ds = load_dataset("TNE-AI/customer-support-on-twitter-conversation", split="train")
print(ds, len(ds), ds.column_names)   # expect 794,335 rows
ds.to_parquet("twcs_conversations.parquet")
PY

python research/probe_dataset.py --kind twcs \
    --path twcs_conversations.parquet \
    --offsets 0,5000,120000,400000,700000 --per-offset 100
# NOTE (BON-40): do NOT use `--sample 500` — that reads the FIRST 500 rows,
# a biased head sample that reproduces none of the figures above (it yields
# median 15 words / 8 real words, 7,067 tokens, 5.0 median turns). The cited
# block was measured on the 5-offset sample pinned in probe --cite-review.
```

**Consequence of the 85% figure:** keyword polarity on the closing turn will not carry an outcome label. Plan for an LLM judge, a proxy, or a hand-labelled gold set — and note that the 15% of threads which *do* carry a signal are unlikely to be a random sample of the whole.

**Starting filter (noise share not measured):** keep threads with ≥1 `Support:` turn; drop threads whose only support line is a follow/welcome template. **Non-English share is unmeasured** — run a language detector on a 2k sample before calling this an English corpus.

**Mirror provenance is unverified.** We did not re-derive the thread graph from Kaggle. If you rely on this as source of truth, spot-check a handful of threads against the original; if the mirror silently drops turns, stop and tell us.

---

## 4. MultiWOZ 2.2 — structure only

| | |
|--|--|
| **Do not** | `load_dataset("pfb30/multi_woz_v22")` — the repo contains only `.gitattributes`, `README.md` and `multi_woz_v22.py`. **It is a loading script with no data**, and `datasets` 3.x removed script loading. |
| **Do** | read the auto-converted parquet on `refs/convert/parquet` (`v2.2/train/0000.parquet`) |
| **Licence** | Apache 2.0 (verified on the card) |
| **Commercial use** | Yes |
| **Outcome** | task success in the booking sense — **not** support resolution |

```bash
python - <<'PY'
from datasets import load_dataset
ds = load_dataset("pfb30/multi_woz_v22", split="train", revision="refs/convert/parquet")
print(ds, len(ds))
PY
```

If the revision form fails, download `v2.2/train/0000.parquet` from the convert tree directly and read it with pandas.

---

## 5. Rejected and blocked

### Syncora / strova-ai — REJECT (smoke-test only)

Renamed `syncora/customer_support_conversations_dataset` → [`strova-ai/customer_support_conversations_dataset`](https://huggingface.co/datasets/strova-ai/customer_support_conversations_dataset). **HF viewer broken** (`CastError`) because the card's declared schema contradicts the shipped CSV. **Do not trust the preview.**

Actual header: `conv_id, turn_index, role, text, timestamp, industry, product, issue_type, language, channel, customer_name, agent_name, overall_sentiment, overall_urgency, outcome, primary_intent` — there is no `status`, `priority`, `category`, `sub_category`, `intent`, `conversation_id`, `turn_id` or `message`.

**(probe)** on the first 31 MB / 20,000 messages:

| metric | value |
|--|--|
| median words per message | 68 |
| median **real** words per message | **8** |
| median padding share | **0.884** |
| `hapax_share` | **0.963** |
| recurring vocabulary (tokens seen ≥50×) | **149** |
| `outcome` per conversation | 704 / 694 / 689 / 686 / 658 → **sampled, near-uniform** |
| labels varying within a conversation | **0** |
| `primary_intent` × `issue_type` | 14×15, **210 of 210 cells populated** — crossed at random |
| unique customer / agent names | 3,430 / 3,419 over 3,431 conversation ids → **no repeat sources** |

```bash
# reproduce the rejection
python research/probe_dataset.py --kind syncora \
    --path customer_support_data.csv --sample-messages 20000
```

The 629 MB file size is padding, not content. Use only to confirm the probe flags garbage.

### Others

- **`Lakshan2003/customer-support-client-agent-conversations`** — not a multi-turn corpus. Schema is `conversation_id / instruction / conversation_history / history_summary / client_question / agent_answer / refined_agent_answer`: an SFT dataset, one row per exchange, **no outcome label**, and agent answers are LLM-*refined*, so a "good path" is a model's output rather than a human's.
- **`Saif7800/customer_qa_dataset`** — viewer fails (`TypeError`, inconsistent `tool_name` struct). CSAT/resolution fields advertised on the card are unverified. Probe the files before trusting them.
- **`AIxBlock/92k-real-world-call-center-scripts-english`** — viewer fails (Arrow error); payload is **12 ZIP archives** needing manual unpacking. Licence **CC BY-NC 4.0** → research only, cannot inform a shipped product. Realism corpus if someone invests the unpacking; not in the minimum slice.
- **`Salesforce/dialogstudio`** — **401 gated.** The file tree is browsable but downloads require accepting terms. It bundles ABCD, SGD, MultiWOZ and Taskmaster in one format, so it is worth revisiting *if* someone obtains access — but ABCD is simpler to take from GitHub.
- **Ubuntu Dialogue / StackExchange accepted answers / GitHub issues closed by a linked commit** — previously listed as organic-outcome sources and **removed as placeholders**: no links, schemas, licences or measured distributions were ever attached. Attractive in principle because the outcome is real rather than annotated. Re-list only with a verified package: link, schema, size, licence, how the outcome is derived, and a measured distribution.

---

## 6. Commercial filter

| Corpus | Licence | May inform a shipped product? |
|--------|---------|-------------------------------|
| ABCD | MIT | **Yes** |
| MultiWOZ 2.2 | Apache 2.0 | Yes |
| TWCS (Kaggle source) | CC BY-NC-SA 4.0 | **No** — contact author for commercial terms |
| TWCS (TNE-AI mirror) | none stated | **No** until legal review |
| CallCenterEN | CC BY-NC 4.0 | **No** |
| Syncora / strova-ai | card claims open | moot — data unusable |

**Working rule — explore freely.** A licence restricts redistributing the *data* and shipping artefacts trained on it; it does not restrict what you may learn from reading it. Use whichever corpus fits the question, and do not narrow your method to stay inside a licence.

Three operational limits, none of which should shape the research:

- no raw data committed to this repo
- no production artefact trained on TWCS
- if a finding holds **only** on TWCS, flag it early so we can decide between licensing the data and re-deriving the result on ABCD

Legal signs off before anything ships, not before work starts.

---

## 7. Does any single corpus pass the full bar?

**No.** The gaps are structural, and knowing which is which is more useful than a single ranking:

| Requirement | ABCD | TWCS | Consequence |
|-------------|------|------|-------------|
| Natural text | yes | yes | both usable |
| Turn structure varies | yes | yes | both usable |
| Non-sampled outcome | derivable, unproven | organic on 15% | **the weakest link in both** |
| Recurring problem types | yes (10 flows) | yes (brands, topics) | grouping is possible |
| Recurring **sources** | **no** | brands only | source-reputation work is effectively blocked |
| Power per group | flow yes / subflow no | large | prefer coarse groups |
| Commercially clean | **yes** | no | ship-facing claims must rest on ABCD |

Two consequences worth stating plainly:

1. **Outcome labelling is an open research problem here, not a preprocessing step.** Neither corpus hands it over.
2. **Anything depending on the same source recurring has no clean home.** ABCD has no agent identity; TWCS brands are a loose proxy. Treat it as blocked rather than weakly tested.

---

*Screened and measured in PR #4. Extend this document rather than starting a parallel list, and extend `research/probe_dataset.py` rather than working in a scratch notebook.*
