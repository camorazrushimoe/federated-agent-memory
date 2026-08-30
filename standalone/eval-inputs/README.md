# Auto-eval pack

Shared inputs and spec for the auto-evaluation framework. All docs in this folder are in English.

| file | what |
|---|---|
| `AUTOEVAL.md` | what to build and how to score |
| `CATEGORIES.md` | closed procedure dictionary |
| `MAP.md` | unlock → procedure (oracle / audit only; hide from the tagger) |
| `d0_slice.jsonl` | 60 question ids |
| `gold_useful.seed.jsonl` | 6-row example only, not the gold |
| `build_ready_pack.py` | builds `dialogues_pool_320.jsonl`, `dialogues_slice_60.jsonl`, full `gold_useful.jsonl` |

Full session jsonl files are produced by:

```bash
python3 standalone/eval-inputs/build_ready_pack.py
```

Do not give `unlock` to the tagger.
Headline metric: packet hit rate = hits / 60.
