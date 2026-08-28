# H1 test data — agent chats with ground-truth "unlock"

Built for the experience-card pipeline spec in PR #29
(`standalone/h1-experience-cards/SPEC.md`): closed chat -> extract card ->
lexical match in the same tenant+vertical -> promote at K=2 independent hits ->
serve as evidence packet -> `unlock_hit` on a hold-out.

## Files

| file | rows | size | sha256 |
|---|---|---|---|
| `abcd_1000_pool.jsonl` | 1000 | 1.8 MB | `28b77a32e58932bbf1502d73975972285ec071d03f30c6ac2b5d23cd90a5abbb` |
| `abcd_200_holdout.jsonl` | 200 | 0.4 MB | `e8f453e17c6c3aa115fb2bd1498a833da383cecdcc650667ac349f903343fe3c` |
| `preview_10.jsonl` | 10 | 16 KB | — |

## Provenance

- Source: **ABCD v1.1** (Action-Based Conversations Dataset), the lab's own copy
  at `/home/ronnybonny/agent-office/instances/lab-1/home/research-lead/federated-agent-memory/data/abcd/abcd_v1.1.json`, sha256 `005d425e890b30a1cdaf0d29d83b08bb7abf038d90fc4924a12e82228e587789`.
- Pool sampled from the **train** split, hold-out from the **dev** split — the
  two files share no chat ids, so a card extracted from the pool that fires on a
  hold-out chat is a genuine transfer, not a lookup.
- Stratified round-robin over subflows, `random.Random(42)`; re-running this
  script reproduces both files byte-for-byte.

## Schema (one JSON object per line)

```json
{
  "chat_id": "abcd-1234",
  "split": "train",
  "vertical": "customer-support",
  "tenant": "product_defect",      // ABCD flow (10 values) - use as tenant/vertical key
  "unlock": "return_size",         // raw ABCD subflow (96 values in this pack)
  "unlock_guideline": "Return Size",  // collapsed to the lab's 55-guideline ontology (BON-37)
  "n_turns": 29,
  "turns": [{"speaker": "agent", "text": "Hi!"}, {"speaker": "customer", "text": "..."}]
}
```

Two label granularities on purpose: `unlock` is the raw ABCD subflow
(96 distinct here), `unlock_guideline` is the same label collapsed to the
lab's 55-subflow guidelines ontology using their own committed 96->55 mapping
(`research/abcd_subflow_mapping.json`, BON-37 / PR #9). Score `unlock_hit`
against `unlock_guideline` unless you specifically want the finer split.

## Why these numbers

- 1000 chats, 20110 turns total, over 55 guideline unlocks =
  10-88 chats each, so **K=2 independent hits is reachable for
  all 55/55 unlocks**, not just the frequent ones. Every guideline present
  in the hold-out is also present in the pool (55/55), so a miss is a real
  miss and not an unseen class.
- 1000 is not too much: it is ~10% of ABCD, and a TF-IDF unigram matcher at
  threshold 0.18 runs over it in seconds with no GPU.
- Turn length in the pool: min 7, median 19, max 55.
- If you want a cheaper first cut, take the first 200 lines of the pool - the
  round-robin ordering keeps it subflow-balanced.

## What this data does NOT give you

- No PII to test the PII gate with: ABCD names/addresses are synthetic.
- `unlock` is a dataset label, not a human judgement of "what actually unlocked
  the case", so `unlock_hit` measured against it is an upper-bound proxy.
- Single vertical (retail customer support), single language (English). Nothing
  here tests cross-tenant leakage, because every chat is the same tenant family.

## Also available in the lab (not packed here)

- `twcs_conversations.parquet` (209.5 MB) - Twitter customer support, real
  public conversations, **no** subflow labels, so no ground-truth unlock. Useful
  for noise/scale tests, useless for `unlock_hit`.
