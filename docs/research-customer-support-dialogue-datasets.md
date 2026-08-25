# Research datasets: Customer–Agent / Support Dialogues (English)

Curated list of publicly available **English** multi-turn (or Q/A) customer–agent / customer-support dialogue datasets useful for evaluating and testing federated agent memory, support agents, intent handling, multi-turn context, and related research.

Most public datasets are **synthetic** or heavily processed/anonymized because real production chat logs are rarely released due to privacy. Synthetic data is generally suitable for hackathon prototypes, evaluation harnesses, and offline testing.

> **Note:** This is a research/sources list only. Datasets are not vendored in this repository. Links point to Hugging Face, Kaggle, papers, or official releases. Verify licenses before commercial use.

## Primary recommendations

| Dataset | Type | Volume (approx.) | Focus / Industries | Notes | Link |
|---------|------|------------------|--------------------|-------|------|
| **Syncora Customer Support Conversations** | Fully synthetic, multi-turn | Large (~629 MB CSV; thousands of multi-turn dialogues) | SaaS, Travel, Education, E-commerce (+ banking/telecom variants) | Rich metadata: industry, category, channel, sentiment, intent, priority, status. Privacy-safe. Strong general-purpose starting point. | [Hugging Face](https://huggingface.co/datasets/syncora/customer_support_conversations_dataset) / [Kaggle](https://www.kaggle.com/datasets/syncoraai/customer-support-conversations) |
| **Lakshan2003 Client–Agent Conversations** | Synthetic (banking corpus + LLM refinement) | **183,337** conversations<br>Avg ~10 turns (2–58)<br>~1.84M total turns | Banking / financial support (accounts, cards, transactions, fraud, etc.) | Strong multi-turn context; includes history summaries and refined agent answers. Excellent for long-context / continuity tests. | [Hugging Face](https://huggingface.co/datasets/Lakshan2003/customer-support-client-agent-conversations) |
| **Bitext Customer Support** | Hybrid synthetic (linguist-curated) | **~26.9k** instruction/response pairs<br>27 intents / ~10 categories | General customer support | High linguistic quality (register variation, noise, politeness). Ideal for intent detection and response generation. Easy to expand into multi-turn. | [Hugging Face](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset) |
| **Bitext Retail / eCommerce** | Hybrid synthetic | ~45k examples | Retail & e-commerce (orders, returns, shipping, product inquiries) | Highly relevant for product-recommendation / catalog-style agents. | [Hugging Face](https://huggingface.co/datasets/bitext/Bitext-retail-ecommerce-llm-chatbot-training-dataset) |
| **Saif7800 Customer QA Dataset** | Synthetic | **~500.7k** records (train/val/test) | E-commerce, SaaS, Healthcare, Finance | Feature-rich: multi-turn threads, CSAT, resolution, channel, preference pairs, tool-calling traces. Good for broader evaluation. | [Hugging Face](https://huggingface.co/datasets/Saif7800/customer_qa_dataset) |
| **AIxBlock CallCenterEN** | Real (PII-redacted transcripts) | **91,706** transcripts | Mixed call-center (inbound/outbound support & sales); multiple English accents | Closest public option to real spoken support interactions. Useful for realism stress-tests. | [Hugging Face](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english) |

## Additional useful sources

| Dataset / Resource | Type | Notes | Link |
|--------------------|------|-------|------|
| **NatCS** (Amazon / ACL Findings 2023) | Synthetic spoken-style multi-domain | Designed to be more naturalistic than typical written task-oriented datasets. Multi-domain customer service. | [arXiv](https://arxiv.org/abs/2305.03007) (release via associated GitHub / challenge materials) |
| **Bitext verticals** (Banking, Telco, Travel, etc.) | Hybrid synthetic | Same family as the general Customer Support set; useful for domain-specific evaluation. | Search `bitext` collections on [Hugging Face](https://huggingface.co/bitext) |
| **oopere/RetailBanking-Conversations** | Synthetic | Smaller (~320 conversations, 4–8 turns), advisor-style retail banking. | [Hugging Face](https://huggingface.co/datasets/oopere/RetailBanking-Conversations) |
| **MG-ShopDial / related e-com multi-goal datasets** | Research collections | Multi-goal shopping dialogues (search + recommendation + QA). Smaller but high quality for conversational commerce. | See papers citing MG-ShopDial |

## Suggested usage for this project

- **Evaluation harness**: sample multi-turn threads, feed partial history into the memory layer / ranker, measure retrieval quality and response consistency.
- **Synthetic traffic generation**: use Bitext intents or Syncora categories as seeds to expand into longer federated sessions.
- **Privacy / visibility testing**: real-looking but synthetic data is ideal for testing classifiers that decide what can be shared across agents/tenants.
- **Domain transfer**: start with general support (Bitext / Syncora) then specialize with retail or banking sets.

## License & compliance reminders

- Prefer datasets with explicit open licenses (MIT, CDLA, CC0, Apache, etc.).
- Synthetic / redacted datasets are preferred for any public demos or shared evaluation artifacts.
- Always re-check the dataset card and license on the hosting platform before redistribution or commercial use.

---

*Added for Gemini Enterprise Hackathon research / evaluation support. Feel free to extend this list with additional sources as they are discovered.*
