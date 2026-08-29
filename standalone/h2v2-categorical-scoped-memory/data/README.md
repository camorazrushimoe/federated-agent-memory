# H2v2 data

Корпус — как в v1: не дублируем крупные jsonl.

```
bash bin/sync_h1_data.sh
bash bin/copy-from-v1.sh
```

Польза (копия из v1, не переразмечать): `gold_useful.jsonl`, `d0_slice.jsonl`.
`unlock` в теги v2 MUST NOT класть.
