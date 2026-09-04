# H2v3 — Evaluation Plan (Fitness for Purpose)

**Статус:** план заморожен до первого живого S8. Пороги §6 менять
только до прогона судьи, с причиной в этом файле.
**Рядом:** [`SPEC.md`](./SPEC.md), [`DATA.md`](./DATA.md), [`PIPELINE.md`](./PIPELINE.md).

Вопрос плана: **помогает ли одна прошлая сессия той же процедуры
решить текущий запрос, или она нейтральна / вредна.**

Hit по `gold_useful` сюда не входит как вердикт. Это L2-поиск из v2,
уже измерен.

## 0. Слои

| слой | вопрос | имя | этот раунд |
|---|---|---|---|
| L0 | прогон повторяется? | replay сырых S2 и S8 | да |
| L1 | контракт пакетов | C-SELF / C-FUTURE / C-SIZE=1 | да |
| L2 | поиск ещё жив? | D4 на тех же тегах | precondition, не вердикт |
| L3 | пакет помогает? | судья helps / neutral / hurts | **главный слой** |
| L4 | пользоваться? | FIT / FIT WITH LIMITS / NOT FIT | §6 |

1. D4 зелёный не даёт FIT этого эксперимента.
2. Пересечение пакета с `useful_dialogue_ids` не даёт FIT.
3. Судья без контроля swap и без B0 — не результат.

## 1. Популяция

- Query: D0-срез, n=60, `data/d0_slice.jsonl`.
- Пул: Phase C same-unlock union 320.
- Теги: живой S2 v2 (`deepseek-v4-flash`, temp 0) или replay.
- Золото: `data/gold_useful.jsonl`, заморожен. agent-labeled (deepseek-v4-pro), not human gold.

## 2. L1 HARD

C-SELF, C-FUTURE, C-SIZE (0 или 1 сессия), C-UNLOCK, C-BLIND, C-REPLAY, C-PARSE (≥0.95).

## 3. L2 precondition

D4 тем же кодом что v2. Красный D4 → S8 не стартовать.

## 4. L3 судья

Классы после unswap: `helps` / `hurts` / `neutral`.

```
net_vs_B0  = P(helps|tag_vs_b0) - P(hurts|tag_vs_b0)
hurt_vs_B0 = P(hurts|tag_vs_b0)
net_vs_raw = P(helps|tag_vs_raw) - P(hurts|tag_vs_raw)
```

`tag_vs_gold` — отчёт, не gate. Swap-audit n=10, согласие ≥ 0.80.

## 6. Рубрика (заморожена до S8)

Hard: L1 + D4 зелёный + parse ≥ 0.95 + swap ≥ 0.80.
Value: net_vs_B0 ≥ +0.15; hurt_vs_B0 ≤ 0.20; net_vs_raw ≥ +0.10.

- **FIT** — hard + три value + packet_tokens_p50 ≤ 1500.
- **FIT WITH LIMITS** — hard зелёные, value/цена упали; назвать рычаг.
- **NOT FIT** — hard, или net_vs_B0 ≤ 0, или hurt_vs_B0 > 0.20.

Порог после увиденного числа не двигать. Полный текст с обоснованием порогов — в этом файле на ветке; расширенная версия с скелетом metrics.json и DoD раунда 0 совпадает с локальным черновиком эксперимента.
