# H2v3 — спецификация пайплайна

Контракт для `standalone/h2v3-fitness-for-purpose/`.
Замер: [`EVAL-PLAN.md`](./EVAL-PLAN.md). Данные: [`DATA.md`](./DATA.md).
Строки модели: [`PROMPTS.md`](./PROMPTS.md).

RFC 2119: `MUST` / `SHOULD` / `MAY`.

## 0. Что переиспользуем и что выкидываем

Переиспользуем из H2v2 без изменения смысла:

```
S1 ingest
S2 tag          [LLM: v2 PROMPTS §2–§3, словарь процедур]
S3 retrieve     [exact problem_shape, TAG_FIELDS_MIN=1]
S5 mix          [шаблон пакета v2 PROMPTS §5, но FFP_MAX_PACKET=1]
```

В этом эксперименте MUST NOT вызываться:

```
S4 rank
S7 update
replay.py как ученик рейтинга
```

Новый шаг:

```
S8 judge        [LLM: этот PROMPTS.md §J, другая модель чем S2]
S9 eval_ffp     [ноль LLM, рубрика EVAL-PLAN §6]
```

## 1. Конфиг, только этот файл цифр плюс `bin/config.py` после copy

H2v2 значения для поиска остаются:

```
S3_MATCH_FIELDS        = [problem_shape]
TAG_KEY_FIELDS         = [problem_shape]
TAG_FIELDS_MIN         = 1
```

FFP-только:

```
FFP_MAX_PACKET         = 1
FFP_SEED               = 0
FFP_SWAP_AUDIT_N       = 10
```

`MAX_PACKET` из v2 (=3) на сборку FFP-пакета MUST NOT влиять.
Пакет FFP — ровно 0 или 1 сессия.

## 2. Четыре руки, один query

На каждом query среза строятся четыре пакета. Выбор сессии
детерминированный. Никакого score.

| id | содержимое | зачем |
|---|---|---|
| **B0** | только шапка `PROMPTS` §5, ноль сессий | пол: пакет не «помогает из воздуха» |
| **B_tag** | 1 кандидат S3 (exact `problem_shape`), C-SELF, C-FUTURE; порядок `(closed_at, session_id)`, берём первого | treatment: то, что продукт умеет без ранкера |
| **B_raw** | 1 сессия из пула 320 с более ранним `closed_at`, без фильтра тегов; индекс = `sha256(query_id | raw | seed) mod n` | контроль «любая память», цена тегов |
| **B_gold** | 1 id из `useful_dialogue_ids` в порядке списка, если он уже в пуле и раньше query; иначе пусто | потолок агентного золота, не ось вердикта |

Правила выбора:

- query MUST NOT попасть в свой пакет (`session_id` / `source_dialogue_id`).
- сессия с `closed_at >= query.closed_at` MUST NOT попасть в пакет.
- если кандидатов 0 — пакет этой руки пустой (шапка без блока). Это не ошибка.
- если B_tag и B_raw выбрали одну и ту же сессию — пакеты идентичны,
  парное сравнение этой пары MUST записаться как `tie` без вызова судьи,
  в строке query флаг `tag_raw_identical=true`.
- `unlock` MUST NOT участвовать в выборе ни одной руки.

## 3. Судья — S8

Вход: транскрипт query + два пакета (A, B).
Выход: одна JSON-строка на пару.

Пары на query:

1. `tag_vs_b0` — всегда
2. `tag_vs_raw` — всегда (или авто-tie при идентичных пакетах)
3. `tag_vs_gold` — только если B_gold непустой

Порядок A/B на каждую пару MUST быть случайным от
`sha256(query_id | pair_id | seed)`: младший бит = swap.
В артефакте хранится `swapped: bool` и сырой ответ судьи в метках A/B.
`eval_ffp.py` переводит A/B обратно в имена рук.

Модель судьи MUST:

- задаваться флагом `--judge-model`, без тихого дефолта в коде;
- отличаться от тегера S2 (`deepseek-v4-flash` в раунде 0 v2);
- по возможности отличаться от разметчика золота (`deepseek-v4-pro`).
  Если доступен только DeepSeek — это ограничение, писать в манифест,
  пару `tag_vs_gold` не использовать как hard-gate.

Temperature MUST быть 0. Сырой request/response MUST писаться в
`raw/judge/<query_id>__<pair_id>.json`. `--replay-dir` MUST
прогонять S8 без сети.

## 4. Изоляция

Реализация MUST жить только в этой папке (плюс байт-копии, которые
кладёт `copy-from-v2.sh`).
MUST NOT импортировать H1, `research/`, код ранкера в S8/S9.
Ключ, endpoint, model id в файлы не зашивать.

## 5. Артефакты прогона

| файл | кто пишет |
|---|---|
| `runs/<id>/packets.jsonl` | `build_ffp_packets.py` |
| `runs/<id>/judgments.jsonl` | `judge_ffp.py` |
| `runs/<id>/metrics.json` | `eval_ffp.py` |
| `runs/<id>/per_query.jsonl` | `eval_ffp.py` |
| `runs/<id>/manifest.json` | каждый шаг дописывает |
| `runs/<id>/data/raw/judge/` | S8, gitignore |
| `runs/<id>/REPORT.md` | человек после S9 |

`packets.jsonl` держит `packet_session_ids` и `packet_sha256`.
Полный `packet_text` MAY жить рядом в gitignored `data/packets/`.
В git после прогона — id, классы, метрики, не транскрипты.
