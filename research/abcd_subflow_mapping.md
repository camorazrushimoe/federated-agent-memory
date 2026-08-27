# ABCD subflow → guidelines mapping (96 → 55)

Companion to [`abcd_subflow_mapping.json`](./abcd_subflow_mapping.json) (canonical)
and [`abcd_subflow_mapping.csv`](./abcd_subflow_mapping.csv) (human-readable mirror).
Builds: **BON-37** / GitHub issue #7.

## What this is

`guidelines.json` documents 55 subflows in Title Case (`Initiate Refund`,
`Boots FAQ`, …); the data's `scenario.subflow` field uses 96 distinct snake_case
values (`refund_initiate`, `boots_how_1`, …). This table maps **every one of the
96 data values** to one of the 55 guideline subflows (or `null` with a reason —
none are unmapped).

## Coverage

| | conversations | subflows |
|--|--|--|
| Naive name join (probe `guidelines` block) | 4,582 (0.456) | 32 of 96 |
| **This mapping** (probe `mapping` block) | **10,042 (1.0)** | **96 of 96** |

Reproduce:

```bash
python research/probe_dataset.py --kind abcd \
    --path data/abcd/abcd_v1.1.json \
    --guidelines data/abcd/guidelines.json \
    --mapping research/abcd_subflow_mapping.json
# -> guidelines.conversation_coverage: 0.456   (naive join, kept for comparison)
# -> mapping.conversation_coverage:      1.0
```

## How it was derived

Three methods, recorded per row in the JSON/CSV (`method` field):

### 1. DIRECT (46 rows) — name match

The data value is (or tokenizes to) the same subflow as in `ontology.json`,
whose entries join 1:1 to `guidelines.json`. Examples:
`refund_initiate → Initiate Refund`, `credit_card → Invalid Credit Card`,
`status → Shipping Status`, `missing → Missing Item`.

Note two near-misses the naive probe *does* get: `status` and `cost` join via
normalised name collision, but only because `ontology.json` ships bare names
for the shipping flow; they are unambiguous within their flow.

### 2. VARIANT (48 rows) — numbered variants → the single documented FAQ

The 8 products/categories with numbered variants are documented **once each**
in the guidelines:

| data variants | guideline subflow |
|--|--|
| `boots_how_1..4`, `boots_other_1..4` | Boots FAQ |
| `shirt_how_1..4`, `shirt_other_1..4` | Shirt FAQ |
| `jeans_how_1..4`, `jeans_other_1..4` | Jeans FAQ |
| `jacket_how_1..4`, `jacket_other_1..4` | Jacket FAQ |
| `pricing_1..4` | Pricing FAQ |
| `membership_1..4` | Membership FAQ |
| `timing_1..4` | Timing FAQ |
| `policy_1..4` | Policy FAQ |

**Verified, not assumed** (`research/phase0/variant_verification.py`):
every guideline FAQ playbook is the same 4-step sequence
`Search FAQ → <product> → Select Answer → N/A`, and the data dialogues in each
family use exactly the matching `search-faq` + `search-<product>` +
`select-faq` actions (plus off-playbook digressions that vary per dialogue).
So all `how_N`/`other_N`/`N` variants of a product share that product's
playbook. Per-variant action inventories are in
`research/phase0/variant_verification.json`.

### 3. INFERRED (2 rows) — generic names, mapped from dialogues + action traces

| data subflow (n) | guideline subflow | confidence | evidence |
|--|--|--|--|
| `status_questions` (30) | Status Active | medium | transcripts ask "is my subscription active?"; action trace `pull-up-account → verify-identity → subscription-status → send-link` matches the Status Active playbook. |
| `status_delivery_date` (3) | Status Delivery Time | high | transcript "the delivery date of my order seems to be wrong"; uses `ask-the-oracle` + `update-order`, distinctive to that playbook. |

Sample transcripts and action counters are in
`research/phase0/variant_verification.json` (`ambiguous` key).

### The 9 ontology subflows that never appear in the data

Recorded in the JSON under `unused_ontology_subflows`:

`boots, jacket, jeans, membership, policy, pricing, shirt, timing` (8 bare
base names — they appear in the data only via their numbered variants, which
the VARIANT rule covers), plus `status_active` (its 30 dialogues carry the
generic label `status_questions` instead).

## Known limitations

- `status_questions → Status Active` is a **medium-confidence** inference
  (n=30, generic label). If it is wrong, the affected conversations' playbook
  scores are wrong — flag it when scoring M3 evidence.
- Mapping a numbered variant to a single FAQ means the variant-level
  differences (which product attribute the customer asked about) are lost in
  playbook scoring. Keep `scenario.subflow` for finer-grained analysis.
- Coverage 1.0 is a **join** claim, not a quality claim: it says every data
  conversation can be compared to *some* documented playbook, which was the
  goal of #7.
