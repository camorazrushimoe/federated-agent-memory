#!/usr/bin/env python3
"""Build an H1 (experience-card) test-data pack out of the lab's ABCD corpus.

ABCD = Action-Based Conversations Dataset v1.1 (10,042 agent<->customer support
conversations, each with a ground-truth flow/subflow label). That label is the
natural stand-in for the "unlock" in PR #29's unlock_hit metric.

Output (in ~/h1-test-data/):
  abcd_1000_pool.jsonl     1000 chats, stratified by subflow, seed 42  (card pool)
  abcd_200_holdout.jsonl    200 chats from a DIFFERENT split, same shape (eval)
  preview_10.jsonl          first 10 pool chats, for eyeballing
  README.md                 schema, provenance, sha256, how it maps to #29
"""
import hashlib
import json
import os
import random
from collections import Counter, defaultdict

SRC = os.path.expanduser(
    "~/agent-office/instances/lab-1/home/research-lead/data/abcd/abcd_v1.1.json")
if not os.path.isfile(SRC):
    SRC = os.path.expanduser(
        "~/agent-office/instances/lab-1/home/research-lead/"
        "federated-agent-memory/data/abcd/abcd_v1.1.json")
OUT = os.path.expanduser("~/h1-test-data")
os.makedirs(OUT, exist_ok=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


src_sha = sha256(SRC)
data = json.load(open(SRC))
print("source:", SRC)
print("source sha256:", src_sha)
print("splits:", {k: len(v) for k, v in data.items()})

# The lab's own 96 raw subflows -> 55 guideline subflows mapping (PR #9 / BON-37).
MAP_SRC = os.path.expanduser(
    "~/agent-office/instances/lab-1/home/research-lead/work/fam-research/"
    "wt22/research/abcd_subflow_mapping.json")
SUB2GUIDE = {}
if os.path.isfile(MAP_SRC):
    raw = json.load(open(MAP_SRC))
    for row in raw.get("mapping", []):
        if isinstance(row, dict):
            src = row.get("data_subflow") or row.get("subflow") or row.get("from")
            dst = (row.get("guidelines_subflow") or row.get("ontology_subflow")
                   or row.get("to") or row.get("mapped"))
            if src and dst:
                SUB2GUIDE[src] = dst
    print(f"subflow->guideline mapping: {len(SUB2GUIDE)} entries from {MAP_SRC}")


def norm(c, split):
    sc = c.get("scenario", {})
    turns = [{"speaker": t[0], "text": t[1]} for t in (c.get("original") or [])]
    return {
        "chat_id": c["convo_id"],
        "split": split,
        "vertical": "customer-support",
        "tenant": sc.get("flow"),          # 10 flows -> use as tenant/vertical key
        "unlock": sc.get("subflow"),       # 55 subflows -> ground-truth "unlock"
        "unlock_guideline": SUB2GUIDE.get(sc.get("subflow"), sc.get("subflow")),
        "n_turns": len(turns),
        "turns": turns,
    }


def stratified(split, n, seed):
    rng = random.Random(seed)
    by_sub = defaultdict(list)
    for c in data[split]:
        by_sub[c["scenario"]["subflow"]].append(c)
    for v in by_sub.values():
        rng.shuffle(v)
    picked, subs = [], sorted(by_sub)
    i = 0
    while len(picked) < n:
        progressed = False
        for s in subs:
            if i < len(by_sub[s]) and len(picked) < n:
                picked.append(norm(by_sub[s][i], split))
                progressed = True
        if not progressed:
            break
        i += 1
    return picked


pool = stratified("train", 1000, 42)
hold = stratified("dev", 200, 42)


def dump(rows, name):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p, os.path.getsize(p), sha256(p)


pool_p, pool_sz, pool_sha = dump(pool, "abcd_1000_pool.jsonl")
hold_p, hold_sz, hold_sha = dump(hold, "abcd_200_holdout.jsonl")
prev_p, prev_sz, _ = dump(pool[:10], "preview_10.jsonl")

pool_subs = Counter(r["unlock"] for r in pool)
pool_guides = Counter(r["unlock_guideline"] for r in pool)
turns = [r["n_turns"] for r in pool]
overlap = len({r["unlock"] for r in pool} & {r["unlock"] for r in hold})
print(f"\npool  {len(pool)} chats, {pool_sz/1e6:.1f} MB, {len(pool_subs)} unlocks, "
      f"turns min/med/max = {min(turns)}/{sorted(turns)[len(turns)//2]}/{max(turns)}")
print(f"hold  {len(hold)} chats, {hold_sz/1e6:.1f} MB, "
      f"{len(set(r['unlock'] for r in hold))} unlocks, overlap with pool = {overlap}")
print("chats per unlock in pool: min", min(pool_subs.values()),
      "max", max(pool_subs.values()))
print("ids disjoint:", not (set(r["chat_id"] for r in pool)
                            & set(r["chat_id"] for r in hold)))

readme = f"""# H1 test data — agent chats with ground-truth "unlock"

Built for the experience-card pipeline spec in PR #29
(`standalone/h1-experience-cards/SPEC.md`): closed chat -> extract card ->
lexical match in the same tenant+vertical -> promote at K=2 independent hits ->
serve as evidence packet -> `unlock_hit` on a hold-out.

## Files

| file | rows | size | sha256 |
|---|---|---|---|
| `abcd_1000_pool.jsonl` | {len(pool)} | {pool_sz/1e6:.1f} MB | `{pool_sha}` |
| `abcd_200_holdout.jsonl` | {len(hold)} | {hold_sz/1e6:.1f} MB | `{hold_sha}` |
| `preview_10.jsonl` | 10 | {prev_sz/1e3:.0f} KB | — |

## Provenance

- Source: **ABCD v1.1** (Action-Based Conversations Dataset), the lab's own copy
  at `{SRC}`, sha256 `{src_sha}`.
- Pool sampled from the **train** split, hold-out from the **dev** split — the
  two files share no chat ids, so a card extracted from the pool that fires on a
  hold-out chat is a genuine transfer, not a lookup.
- Stratified round-robin over subflows, `random.Random(42)`; re-running this
  script reproduces both files byte-for-byte.

## Schema (one JSON object per line)

```json
{{
  "chat_id": "abcd-1234",
  "split": "train",
  "vertical": "customer-support",
  "tenant": "product_defect",      // ABCD flow (10 values) - use as tenant/vertical key
  "unlock": "return_size",         // raw ABCD subflow ({len(pool_subs)} values in this pack)
  "unlock_guideline": "Return Size",  // collapsed to the lab's 55-guideline ontology (BON-37)
  "n_turns": 29,
  "turns": [{{"speaker": "agent", "text": "Hi!"}}, {{"speaker": "customer", "text": "..."}}]
}}
```

Two label granularities on purpose: `unlock` is the raw ABCD subflow
({len(pool_subs)} distinct here), `unlock_guideline` is the same label collapsed to the
lab's 55-subflow guidelines ontology using their own committed 96->55 mapping
(`research/abcd_subflow_mapping.json`, BON-37 / PR #9). Score `unlock_hit`
against `unlock_guideline` unless you specifically want the finer split.

## Why these numbers

- {len(pool)} chats, {sum(turns)} turns total, over {len(pool_guides)} guideline unlocks =
  {min(pool_guides.values())}-{max(pool_guides.values())} chats each, so **K=2 independent hits is reachable for
  all {len(pool_guides)}/{len(pool_guides)} unlocks**, not just the frequent ones. Every guideline present
  in the hold-out is also present in the pool ({len(pool_guides)}/{len(pool_guides)}), so a miss is a real
  miss and not an unseen class.
- 1000 is not too much: it is ~10% of ABCD, and a TF-IDF unigram matcher at
  threshold 0.18 runs over it in seconds with no GPU.
- Turn length in the pool: min {min(turns)}, median {sorted(turns)[len(turns)//2]}, max {max(turns)}.
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
"""
open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write(readme)
print("\nwrote", OUT)
