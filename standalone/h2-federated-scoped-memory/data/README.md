# H2 data

Копия тестового пака H1. Исходник не удаляли:
`standalone/h1-experience-cards/data/`.

Крупные jsonl в git не дублируем. Забрать их сюда:

```
bash bin/sync_h1_data.sh
```

Аудит глазами: [`../DATA-AUDIT.md`](../DATA-AUDIT.md).
Схема сырых файлов — H1, не SPEC. В пайплайн их MUST прогонять через
[`../bin/adapt_h1_corpus.py`](../bin/adapt_h1_corpus.py).

## Files

| file | rows | role |
|---|---|---|
| `abcd_1000_pool.jsonl` | 1000 | pool, train split ABCD |
| `abcd_200_holdout.jsonl` | 200 | hold-out, dev split, chat id не пересекаются с pool |
| `preview_10.jsonl` | 10 | первые 10 pool, смотреть глазами |
| `gold_useful.seed.jsonl` | seed | образец разметки пользы, не L2-золото |

sha256 исходного H1-пака — в `standalone/h1-experience-cards/data/README.md`.

## Что здесь не золото H2

`unlock` и `unlock_guideline` оставлять в сырье можно, адаптер их выкидывает.
Подставлять их в `gold_tags` / `gold_useful` нельзя: это метка H1.

Настоящие `gold_tags.jsonl` и `gold_useful.jsonl` появляются только после D0
(агентная разметка `deepseek-v4-pro` по решению основателя 2026-08-28 —
**NOT human gold**, срез из DATA-AUDIT §6; контракт: `ROUND-0-PLAN.md`).
Пока их нет — L2 по пользе не публиковать.
