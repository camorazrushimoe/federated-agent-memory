# H2v2 — закрывающий отчёт раунда 0

- run id: `2026-08-29_PhaseC_live_deepseek-v4-flash`
- tag model: `deepseek-v4-flash` · temperature 0 · 380/380 сессий, 0 reject
- slice: 60 query · pool: same-unlock union 320
- gold: agent-labeled (`deepseek-v4-pro`), **не human gold**
- `unlock` на вход тегера не подавался

Артефакты этого прогона: [`runs/2026-08-29_PhaseC_live_deepseek-v4-flash/`](./runs/2026-08-29_PhaseC_live_deepseek-v4-flash/).
Оракул до S2: [`runs/2026-08-29_oracle_D4/`](./runs/2026-08-29_oracle_D4/).

Сырые транскрипты и `raw/tag/*` в git не кладём (PII + `.gitignore`).
Теги без текста: `runs/2026-08-29_PhaseC_live_deepseek-v4-flash/tags_only.json`.

---

## Вердикт

**D4 (словарь / тегер / поиск) — FIT.**  
**T vs B1 (ранкер внутри ячейки) — NOT FIT.**  
**Продуктовая гипотеза целиком — FIT WITH LIMITS.**

Что это значит по слоям:

| слой | вопрос | ответ |
|---|---|---|
| словарь процедур | даёт ли закрытый id среднюю ось поиска, а не корзину на 172? | да |
| живой S2 | восстанавливает ли тегер эту ось по транскрипту, без `unlock`? | да, recall 0.81 при потолке 1.00 |
| целая сессия как подсказка | есть ли в пуле полезные прошлые чаты той же процедуры? | да: B3 = 46/60, 14 пустых золота |
| ранкер T | лучше ли score+explore случайной сессии из той же ячейки? | нет: T.hit = B1.hit = 38 |

Поиск починили относительно v1 (там T=2 / B1=5 на нефильтрованном пуле 320).  
Ранжирование внутри найденной ячейки на этом срезе ничего не добавляет.

Корпус 1000+200 по правилу D4 открывать можно. Этого раунда достаточно, чтобы не возвращаться к 19 тикетным категориям и не чинить S3.

---

## D4 — гейт до T vs B1

| гейт | оракул MAP | живой S2 | норма |
|---|---|---|---|
| живых procedure-id | 30 | 30 | 24–32 |
| доля `other` | 0% | 3.4% (11/320) | <10% |
| top-1 id | `wash_jacket` 3.4% | `product_spec` 9.4% | <20% |
| медиана `n_candidates` | 11 | 10 | 8–20 |
| query с 0 кандидатами | 0% | 0% | <15% |
| retrieve.recall vs `gold_useful` | **1.00** (393/393) | **0.81** (318/393) | ≥0.70 |

Живой S2 хуже оракула ровно там, где FINDINGS предупреждал: часть howto сваливается в `product_spec` / `product_info`. Это не коллапс в 19 типов. Медиана кандидатов остаётся десятком.

---

## Руки (один `classify_packet`: hit / wrong / abstain)

| arm | hit | wrong | abstain | hit share |
|---|---|---|---|---|
| B0 пустой пакет | 0 | 0 | 60 | 0.00 |
| B1 random из кандидатов S3 | 38 | 22 | 0 | 0.63 |
| B2 top-score, без explore | 37 | 23 | 0 | 0.62 |
| B3 оракул useful ∩ pool | 46 | 0 | 14 | 0.77 |
| T rank + 1 explore | 38 | 22 | 0 | 0.63 |

- B0.hit = 0 — хард-гейт живой.
- B3.abstain = 14 — это пустое золото, не дыра пула.
- T.wrong = 22/60 = 0.37 > 0.25 — вредный пакет чаще, чем позволяет H2-HARM. Из них 14 — пустое золото (пакет непустой → wrong по определению), 8 — тегер промахнулся мимо useful.
- T и B1 совпали по классу на 56/60 query. Расхождение 2+2. Ранкер не выбирает другую ячейку — ячейку уже выбрал S3.

Стоимость пакета: p50 ≈ 819 ток · p95 ≈ 1090 · max 1280. Ниже порога 1500.

---

## Почему так

1. **S3 теперь фильтр, не дырка.** В v1 channel+vertical были константой, TAG_FIELDS_MIN=2 пропускал весь пул, recall=1.0 был тривиальным. Здесь S3 = exact `problem_shape`, медиана 10 кандидатов.
2. **Полезность на этом паке = та же FAQ-ячейка.** Золото 393/393 совпадает с `unlock`. Если S2 ставит верный id, случайный кандидат из ячейки почти так же хорош, как «умный» top-3: внутри полки ~10 сессий почти все useful.
3. **Рейтинг на старте ноль у всех.** T без накопленной истории вырождается в стабильный tie-break по `session_id`. B2 ≈ T. Explore-слот на срезе из 60 не успевает научиться.
4. **Ошибки тегера дорогие точечно.** `product_spec` на пуле 30/320 — широкая полка; на query вроде `d-867` (n_useful=10, retrieved=6) T берёт чужой spec и получает wrong, хотя B3 в ячейке hit.

---

## Что не утверждаем

- Что целая сессия полезна человеку. Золото агентное.
- Что словарь покрывает домен. D4 видит только 30 ячеек среза; в полном пуле 1000 уникальных unlock = 96, 680/1000 вне среза.
- Что T станет лучше на полном корпусе. На срезе обучения нет. Это отдельный прогон, не этот вердикт.

---

## Как воспроизвести

Ключ в git не кладём. Нужны `H2_API_KEY` и `H2_BASE_URL` (этот прогон: `https://api.deepseek.com/v1`).

```bash
cd standalone/h2v2-categorical-scoped-memory
bash bin/copy-from-v1.sh
bash bin/sync_h1_data.sh
python3 bin/build_phase_c_inputs.py
python3 -c "
from pathlib import Path
p=Path('data/dialogues_pool.jsonl').read_text().splitlines()
s=Path('data/dialogues_slice.jsonl').read_text().splitlines()
Path('data/dialogues.jsonl').write_text('\n'.join(p+s)+'\n')
"

# оракул D4, ноль LLM
python3 bin/run_oracle_d4.py

# живой S2 (380 вызовов) + руки
H2_API_KEY=... H2_BASE_URL=https://api.deepseek.com/v1 \
  python3 bin/tag_parallel.py \
    --in data/dialogues.jsonl \
    --out runs/2026-08-29_PhaseC_live_deepseek-v4-flash/data/sessions_all.jsonl \
    --ratings-out runs/2026-08-29_PhaseC_live_deepseek-v4-flash/data/ratings_all.jsonl \
    --raw-dir runs/2026-08-29_PhaseC_live_deepseek-v4-flash/data/raw/tag \
    --model deepseek-v4-flash --workers 8
python3 bin/eval_live_d4.py --run-dir runs/2026-08-29_PhaseC_live_deepseek-v4-flash
```

Повтор без LLM: те же `tags_only.json` + `eval_live_d4.py` на уже размеченном пуле.
S0 без LLM после `copy-from-v1.sh`: `python3 bin/bake_s0_fixtures.py && python3 bin/checks.py --fixtures fixtures --workdir runs/<id>_checks`.
`C-GD5` красный, пока в дереве нет `data/raw_gold_useful/` — это трейсы разметчика D0, не S0-фикстуры.

---

## Что менять дальше (дешевле сначала)

1. Не трогать словарь ради recall на этих же 60.
2. Не открывать корпус 1000, чтобы «спасти» ранкер: D4 уже зелёный, T=B1 внутри ячейки.
3. Если продукт — «подмешать любую прошлую сессию той же процедуры», текущий T не нужен: S3 + случайный/свежий слот достаточны.
4. Если продукт — выбрать *лучшую* сессию в ячейке, нужен другой сигнал (исход, новизна текста, не score=0 tie-break). Это уже не этот эксперимент.
