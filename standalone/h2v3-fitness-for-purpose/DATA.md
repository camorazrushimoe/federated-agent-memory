# Данные

Никакого нового корпуса. Тот же ABCD-срез и то же агентное золото, что
в H2 / H2v2. Новые файлы — только пакеты рук и суждения FFP.

## Откуда что берётся

| что | где лежит канонически | как попадает сюда |
|---|---|---|
| пул 1000 + hold-out 200 | `standalone/h1-experience-cards/data/abcd_*.jsonl` | `bash bin/sync_h1_data.sh` |
| срез 60 query | `standalone/h2-federated-scoped-memory/data/d0_slice.jsonl` | `copy-from-v2.sh` |
| gold_useful 60 строк | тот же каталог, `data/gold_useful.jsonl` | `copy-from-v2.sh` |
| манифест разметчика | `data/gold_useful.manifest.json` | `copy-from-v2.sh` |
| seed-рубрика | `data/gold_useful.seed.jsonl` | лежит в v2, копируется |
| словарь процедур | `../h2v2-categorical-scoped-memory/CATEGORIES.md` | копируется |
| живые теги 320+60 | v2 `runs/2026-08-29_PhaseC_live_deepseek-v4-flash/tags_only.json` (если есть локально) или новый S2 | см. PIPELINE шаг C |

Корпус 1000+200 в git не кладём. Срез и золото — да, это уже на main.

## Что такое срез 60

Контракт: [`../h2-federated-scoped-memory/D0-GOLD.md`](../h2-federated-scoped-memory/D0-GOLD.md),
[`../h2-federated-scoped-memory/DATA-AUDIT.md`](../h2-federated-scoped-memory/DATA-AUDIT.md) §6.

| семья | правило | n |
|---|---|---|
| how-to | hold-out unlock содержит `_how_` | 34 |
| site | `slow_speed` / `shopping_cart` / `search_results` | 6 |
| negative | споры/промо + первые 8 `manage_*` по id | 20 |

Пул Phase C для этих 60 — **same-unlock union 320**, не весь 1000.
Его собирает `bin/build_phase_c_inputs.py` (копия из v1/v2).

`unlock` / `unlock_guideline` в тегер, в пакет и в промпт судьи
MUST NOT попадать. Это метка H1.

## Что такое gold_useful

- 60 строк, по одной на query среза.
- Поле `useful_dialogue_ids`: прошлые сессии, в которых разметчик
  увидел **переносимый ход**, которого нет в самом query.
- Разметчик: `deepseek-v4-pro`, temperature 0.
- Статус: **agent-labeled, NOT human gold.**
- Пустой список валиден (14 query на каноническом файле).
- Только сессии с `closed_at` строго раньше query (C-FUTURE).
- Lead-curation: две перезаписи списка в `[]` (d-1789, d-5551) плюс
  правки notes. Сырой выход разметчика — в v1
  `runs/2026-08-29_D0_gold_useful/`.

В FFP золото — **рука B_gold и калибровка**, не ось вердикта.
Вердикт строится по судье. Любая цифра, где золото участвует как
пересечение id, MUST нести пометку
`agent-labeled (deepseek-v4-pro), not human gold`.

## Что тегер видит

Только `channel`, `vertical` и транскрипт. Словарь — закрытые id из
[`CATEGORIES.md`](../h2v2-categorical-scoped-memory/CATEGORIES.md)
(копия после bootstrap). `unlock` на вход S2 запрещён.

## Что судья видит

- транскрипт query (без unlock, без gold-списка, без id процедуры);
- два пакета, подписанные «Packet A» / «Packet B»;
- шаблон из [`PROMPTS.md`](./PROMPTS.md) §J.

Судья MUST NOT видеть: имя руки (B_tag / B0 / …), `problem_shape`,
`useful_dialogue_ids`, какой пакет «должен» победить.

## Чего в git нет и не будет

- сырые транскрипты пула (`data/abcd_*.jsonl`, `data/dialogues*.jsonl`)
- `raw/tag/*`, `raw/judge/*`
- ключи API
- `runs/*/data/` с полными сессиями

В git после прогона кладём: `metrics.json`, `per_query.jsonl`,
`judgments.jsonl` без текстов транскриптов, `REPORT.md`.
