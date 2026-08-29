# H2 — протокол прогона

Как запускать и куда писать, чтобы два прогона были сравнимы.
Рядом: [`SPEC.md`](./SPEC.md), [`EVAL-PLAN.md`](./EVAL-PLAN.md), [`CHECKS.md`](./CHECKS.md).

---

## 1. Одна команда, один прогон

```
python bin/replay.py \
    --dialogues data/dialogues.jsonl \
    --gold-tags data/gold_tags.jsonl \
    --gold-useful data/gold_useful.jsonl \
    --model deepseek-v4-flash \
    --stage S0 \
    --out runs/2026-08-28_S0_deepseek-v4-flash
```

- `--stage` ∈ `S0 | S1 | S2 | S3 | S4` (EVAL-PLAN §9).
- `--replay <run_dir>` — тот же конвейер из `raw/tag/`, ноль новых вызовов LLM.
- `--arm T|B0|B1|B2|B3` — какая рука кладёт пакет. Подсчёт классов один.
- `--seed` обязателен для B1, по умолчанию `0`.
- `--until N` — обрезать корпус по времени, для S0/S1.
- Каталог `--out` MUST быть пустым. Дописывать в чужой run dir нельзя.

`replay.py` только вызывает шаги в порядке SPEC §8. Своей логики поиска, ранжирования и промптов в нём нет (`C-RP1`).

Пока runner не написан, шаги гоняются по одному. Контракт шага от этого не меняется.

### 1.1 Харнесс чеков (D2)

Одна команда гоняет весь S0-блок `CHECKS.md` по фикстурам — детерминированно,
без LLM (S2 проигрывает запечённый выход из `fixtures/`):

```
python bin/checks.py \
    --fixtures fixtures \
    --workdir runs/<run_id>_checks
```

Пишет `checks.json` (все id из CHECKS.md, HARD/SOFT) и `report.md` в `--workdir`.
Любой HARD из блока «Что прогонять на S0» не зелёный → exit 1, прогон воид.
`C-REPLAY` / `C-EV*` / `C-NC2..C-NC5` в checks.json помечены `passed=null`
(закрываются runner'ом и eval.py на D4/D5) и S0 не валят.

---

## 2. Данные

### 2.1 S0

Только [`fixtures/dialogues.jsonl`](./fixtures/dialogues.jsonl) плюс золото рядом.
Маппинг не нужен: фикстуры уже в схеме SPEC §3.

### 2.2 Корпус H1, если его берут

Пакет `standalone/h1-experience-cards/data/` — не схема SPEC. На ingest:

| поле пакета | поле диалога | правило |
|---|---|---|
| `chat_id` | `dialogue_id` | `d-{chat_id}` |
| `tenant` | `tenant_id` | как есть; на поиск не влияет |
| `vertical` | `vertical` | как есть |
| `turns[].speaker` | `turns[].role` | `customer` / `agent` |
| `turns[].text` | `turns[].text` | как есть |
| — | `channel` | константа `web` |
| — | `agent_id` | `unknown`, либо детерминированный `agent-` + hex |
| `unlock`, `unlock_guideline`, `split`, `n_turns` | выкинуть | это золото H1, не H2 |

`closed_at`: если в пакете нет, синтезировать по индексу файла, шаг 1 минута от `T0=2026-01-01T00:00:00Z`, чтобы replay имел порядок. `T0` писать в манифест.

Код H1 не импортировать. Файл корпуса копировать в run dir или в локальный `data/`.

### 2.3 Золото H2

`gold_tags` пишут люди. `gold_useful` на корпусе — агентная разметка `deepseek-v4-pro`
по решению основателя 2026-08-28 (**NOT human gold**, контракт:
[`ROUND-0-PLAN.md`](./ROUND-0-PLAN.md)); файл несёт `#`-заголовок с кавером. Скрипты только читают.

- `gold_tags.jsonl` — теги без `channel` / `vertical`.
- `gold_useful.jsonl` — `query_id` + `useful_dialogue_ids` строго из прошлого.

Пока корпуса-золота нет, L2 по пользе не публиковать. Фикстурного золота хватает для S0.

---

## 3. Каталог прогона

```
runs/<run_id>/
  manifest.json
  audit.json
  checks.json
  metrics.json
  cost.json
  report.md
  per_query.jsonl
  data/
    dialogues.jsonl
    sessions.jsonl
    ratings.jsonl
    candidates.jsonl
    ranked.jsonl
    packet.json
    serves.jsonl
    outcomes.jsonl
  raw/tag/<dialogue_id>.json
  packets/<query_id>.txt
```

`run_id` = `<UTC-дата>_<stage>_<model>[_<arm>]`. Один id не переиспользовать.

### 3.1 `manifest.json`

```json
{
  "run_id": "2026-08-28_S0_deepseek-v4-flash",
  "created_at": "2026-08-28T22:00:00Z",
  "stage": "S0",
  "git_commit": "<sha, dirty flag>",
  "tag_model": "deepseek-v4-flash",
  "base_url": "https://api.deepseek.com/v1",
  "temperature": 0,
  "seed": 0,
  "arm": "T",
  "config": {
    "MAX_PACKET": 3,
    "EXPLORE_SLOTS": 1,
    "TAG_FIELDS_MIN": 2,
    "DECAY_EVERY_SHOWS": 5,
    "DECAY_AMOUNT": 0.1,
    "GOOD_DELTA": 1.0,
    "BAD_DELTA": -1.0,
    "UNCLEAR_DELTA": 0.0
  },
  "inputs": {
    "dialogues": {"path": "...", "sha256": "...", "rows": 0},
    "gold_tags": {"path": "...", "sha256": "...", "rows": 0},
    "gold_useful": {
      "path": "...",
      "sha256": "...",
      "rows": 0,
      "agent_labeled": true,
      "human_gold": false,
      "labeler_model": "deepseek-v4-pro"
    },
    "prompts": {"path": "PROMPTS.md", "sha256": "..."}
  },
  "outputs": {
    "sessions.jsonl": "...",
    "metrics.json": "..."
  },
  "replay_of": null
}
```

Нет sha или грязный git без пометки — прогон воид.

---

## 4. Схемы результатов

`metrics.json` — EVAL-PLAN §10.
`cost.json` — EVAL-PLAN §4.6. Способ токенов обязателен. Нет прайса → `usd` = null.

`per_query.jsonl`, одна строка на query из gold_useful:

```json
{
  "query_id": "d-007",
  "tag_key": "...",
  "useful_dialogue_ids": ["d-001", "d-002"],
  "packet_dialogue_ids": ["d-001", "d-011", "d-013"],
  "packet_session_ids": ["s-...", "s-...", "s-..."],
  "n_candidates": 5,
  "explore_session_id": "s-...",
  "class": "hit",
  "outcome": "good"
}
```

`class` ∈ `hit|wrong|abstain`. Сумма по файлу MUST сходиться с `metrics.json` руки.

---

## 5. Отчёт

`report.md` в таком порядке, без воды:

1. Кто: run id, stage, model, sha данных, отличия конфига от SPEC §6.
2. Чеки: HARD passed/failed, каждый SOFT.
3. Аудит A1–A6 (на S0 можно написать «фикстуры, полный аудит на S1»).
4. Таблица рук: T / B0 / B1 / B2 / B3 по `hit` / `wrong` / `abstain`.
5. Разметка: три числа по полям.
6. Ротация: `top1_share`, `top3_share`, `explore_fill`.
7. Цена.
8. Вердикт — одна строка EVAL-PLAN §6.4. На S0 вердикт не ставить: мало n.
9. Что дёшево перевернёт вывод.

---

## 6. Гигиена

- JSONL, один писатель, без базы и сервиса.
- Состояние прогона живёт в run dir. Исходный корпус и `fixtures/` не переписывать.
- Промпт, порог или маппинг посреди прогона не менять. Нужна правка — новый run id.
- `call_llm` берёт модель и ключ из флага и `H2_*`, не из `H1_*`.
