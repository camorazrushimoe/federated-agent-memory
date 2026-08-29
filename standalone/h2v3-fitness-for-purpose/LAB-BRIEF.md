# Lab brief — H2v3 Fitness for Purpose

Одностраничник для человека, который поднимает стенд с нуля.

## Вопрос

Помогает ли одна прошлая целая сессия той же процедуры (теги v2 + S3,
без ранкера) сильному ризонеру на замороженных 60 query — относительно
тишины и относительно случайной прошлой сессии.

## Не вопрос

Бьёт ли ранкер случай. Это закрыто: нет. Совпадает ли пакет с
`gold_useful`. Это коллинеарно поиску.

## Данные

- Query: `data/d0_slice.jsonl` (60).
- Пул: same-unlock union 320 из ABCD, собирается `build_phase_c_inputs.py`.
- Gold: `data/gold_useful.jsonl`, agent-labeled deepseek-v4-pro,
  NOT human gold. Пустые списки валидны.
- Теги: replay v2 или `tag_parallel.py --model deepseek-v4-flash`.

## Руки

B0 пустой · B_tag первый S3-кандидат по `(closed_at, id)` ·
B_raw детерминированный индекс по sha · B_gold первый useful в пуле.

По одной сессии. Никакого score.

## Судья

Слепое A/B, JSON `winner` ∈ {A,B,tie} + `harm_flag`.
Пары: tag vs B0, tag vs raw, tag vs gold (если gold непустой).
10 query — повтор со swap. Модель — флаг, не flash.

## Гейты вердикта (до прогона)

Hard: контракт пакетов, D4 зелёный, parse ≥ 0.95, swap ≥ 0.80.
Value: net_vs_B0 ≥ +0.15, hurt_vs_B0 ≤ 0.20, net_vs_raw ≥ +0.10.
Иначе FIT WITH LIMITS или NOT FIT. См. EVAL-PLAN §6.

## Команда старта

```
bash bin/copy-from-v2.sh && bash bin/sync_h1_data.sh
```

Дальше PIPELINE.md шаги B–G.
