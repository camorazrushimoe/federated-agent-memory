# Что откуда

v1 заморожен: `../h2-federated-scoped-memory/` (NOT FIT, PR #63 / #64).

Файлы ниже скопированы байт-в-байт с v1 (`sha256` совпадает). Не править
«заодно»: любое изменение — отдельный коммит и строка в этом файле.

| path | sha256-12 | bytes |
|---|---|---|
| CHECKS.md | af9edec950dd | 16432 |
| D0-GOLD.md | c0bd1a3865ad | 6621 |
| DATA-AUDIT.md | 526fd5fadacf | 9997 |
| ENGINEERING-LAYER.md | 9fe2192febc7 | 5430 |
| EVAL-PLAN.md | 6a8b785a1b73 | 27470 |
| RUN-PROTOCOL.md | 4aba4510e792 | 7726 |
| SIMPLIFICATIONS.md | 20694e4900d6 | 6172 |
| bin/adapt_h1_corpus.py | 1af470f9f8a8 | 2620 |
| bin/audit.py | 55409c7c13fd | 11642 |
| bin/build_phase_c_inputs.py | 09b11249de28 | 5731 |
| bin/checks.py | 06466c61e6c7 | 79273 |
| bin/common.py | 000ce13b25d1 | 8933 |
| bin/eval.py | 7fda82ecd799 | 34197 |
| bin/ingest.py | 953354bb35c8 | 3463 |
| bin/label_gold_useful.py | f598fa5da712 | 23706 |
| bin/llm.py | e29213e9b530 | 10220 |
| bin/mix.py | 64acb162f733 | 3549 |
| bin/outcome.py | 1e2e28baa173 | 4936 |
| bin/package_d0_run.py | c15a2ebe4e59 | 2993 |
| bin/rank.py | e41dfa1e7372 | 4027 |
| bin/replay.py | 5cc8ee5721c5 | 16423 |
| bin/run_slice.py | 5a3a4a95287b | 22844 |
| bin/update.py | 2eef72694bd6 | 4956 |
| bin/write_d0_slice.py | 1c0601f898ed | 1927 |
| data/d0_slice.jsonl | 56b5bfc0432f | 6521 |
| data/gold_useful.jsonl | eeeb2e5c81bf | 23552 |
| data/gold_useful.manifest.json | 414ebbd14278 | 28588 |
| data/gold_useful.seed.jsonl | ba0fcca62b30 | 1443 |
| fixtures/README.md | 15ceb832fad6 | 2923 |
| fixtures/dialogues.jsonl | fd469cc2f0b9 | 4267 |
| fixtures/gold_useful.jsonl | 7a3769db1944 | 1009 |
| fixtures/queries/d-007.json | 1591d881405e | 410 |

Корпус ABCD 1000+200 в git не кладём (gitignore). Локально:

```
bash bin/sync_h1_data.sh
```

## Своё у v2 (не копия)

- README.md, WHY-NOT-V1.md, CATEGORIES.md, ROUND-0-PLAN.md, SPEC.md, PROMPTS.md, SOURCE.md
- bin/config.py, bin/prompts.py, bin/tag.py, bin/retrieve.py
- bin/copy-from-v1.sh, bin/sync_h1_data.sh
- fixtures/gold_tags.jsonl (словарь v2)
- standalone/h2-federated-scoped-memory/H2V2.md (указатель из v1)
