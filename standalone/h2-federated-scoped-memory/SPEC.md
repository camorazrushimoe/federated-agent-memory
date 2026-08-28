# H2 — спецификация пайплайна

Контракт для `standalone/h2-federated-scoped-memory/`.
Идея и упрощения: [`README.md`](./README.md), [`SIMPLIFICATIONS.md`](./SIMPLIFICATIONS.md).
Все строки, которые уходят в модель или в пакет агента: [`PROMPTS.md`](./PROMPTS.md).

После закрытого диалога система размечает **сессию целиком**, кладёт её в общий пул, в новый диалог подмешивает похожие прошлые сессии и по исходу двигает их рейтинг.

Лаба пишет скрипты и evaluation. Этот файл фиксирует шаги, данные и что должно быть измеримо после каждого шага.
Планы `EVAL-PLAN.md` / `CHECKS.md` сюда не входят — они отдельные артефакты.

RFC 2119: `MUST` / `SHALL` / `SHOULD` / `MAY`.

---

## 0. Зачем шаги отдельные

Каждый шаг — один скрипт, один вход, один выход, одна проверка.
Нельзя склеивать tag + retrieve + rank в один вызов: иначе не понять, где сломалось.

Порядок строго такой:

```
S1 ingest   →  нормальные диалоги
S2 tag      →  сессии с метаданными     [LLM: PROMPTS.md §2–§3]
S3 retrieve →  кандидаты по тегам
S4 rank     →  порядок + слот ротации
S5 mix      →  пакет, который уйдёт в промпт   [шаблон: PROMPTS.md §5]
S6 outcome  →  исход новой сессии       [LLM только --source llm: PROMPTS.md §6]
S7 update   →  новый рейтинг подмешанных сессий
```

`replay.py` гоняет этот конвейер по корпусу по времени. Он MUST только вызывать шаги по порядку, без своей логики.

---

## 1. Словарь

| термин | смысл |
|---|---|
| **dialogue** | сырой закрытый чат |
| **session** | тот же чат после разметки; единица памяти |
| **tags** | метаданные сессии, только чтобы её найти |
| **tag_key** | каноническая строка из тегов, под которую живёт рейтинг |
| **pool** | все размеченные сессии одного тенанта |
| **query** | новый диалог, для которого ищем подсказки |
| **candidates** | сессии из пула, прошедшие поиск |
| **packet** | 1–N целых сессий, которые подмешивают в query |
| **outcome** | `good` / `bad` / `unclear` — чем закончился query после подмешивания |
| **rating** | счёт пользы сессии **для конкретного tag_key** |

Одного глобального рейтинга у сессии нет. Одна сессия MAY быть полезной для одних тегов и вредной для других.

---

## 2. Изоляция

Реализация MUST:

- жить только в `standalone/h2-federated-scoped-memory/`
- хранить состояние JSONL (или `data/`, который можно gitignore)
- ходить в LLM только через `call_llm(system: str, user: str) -> str`
- брать system/user **только** из [`PROMPTS.md`](./PROMPTS.md)
- считать писателя одним: скрипты MUST NOT крутиться параллельно по одним и тем же JSONL

Реализация MUST NOT:

- импортировать `research/`, `openspec/`, H1-код, POC из GitLab
- писать в Memory Bank, Neo4j, Qdrant, Postgres
- использовать эмбеддинги в v1
- вводить тенанты, группы агентов, `private/shared/global`
- резать сессию на мелкие события
- склеивать несколько сессий в одну каноническую историю
- читать личность клиента в теги
- добавлять свой system/user текст «чтобы модель лучше слушалась»

`tenant_id` в сыром диалоге MAY остаться как поле H1-схемы. На поиск и рейтинг он MUST NOT влиять.

---

## 3. Вход: диалог

Нормализация та же, что в H1, чтобы можно было взять тот же корпус.

```json
{
  "dialogue_id": "d-001",
  "tenant_id": "shop-acme",
  "vertical": "retail-support",
  "agent_id": "agent-a",
  "channel": "web",
  "closed_at": "2026-08-28T12:00:00Z",
  "turns": [
    {"role": "customer", "text": "..."},
    {"role": "agent", "text": "..."},
    {"role": "tool", "name": "lookup_order", "text": "order 4412 size 42 shipped"}
  ]
}
```

- `role` MUST быть `customer` | `agent` | `tool`
- диалог без одного customer-turn MUST отбрасываться на S1
- `agent_id` MAY быть `"unknown"`
- корпус для прогона: JSONL таких записей (100–1000 диалогов). Пока можно брать H1 `data/`, отдельный H2-пак появится позже

---

## 4. Сессия после разметки

```json
{
  "session_id": "s-001",
  "source_dialogue_id": "d-001",
  "closed_at": "2026-08-28T12:00:00Z",
  "channel": "web",
  "vertical": "retail-support",
  "agent_id": "agent-a",
  "turns": [],
  "tags": {
    "problem_shape": "login fails after password reset",
    "constraint": "stale jwt cache",
    "ending": "resolved",
    "channel": "web",
    "vertical": "retail-support"
  },
  "tag_key": "login fails after password reset|stale jwt cache|resolved|web|retail-support",
  "contains_pii": false,
  "created_at": "2026-08-28T12:01:00Z"
}
```

Правила тегов:

| поле | правило |
|---|---|
| `problem_shape` | ≤12 слов, формулировка клиента, lowercase, без идентификаторов |
| `constraint` | ≤12 слов или литерал `none` |
| `ending` | `resolved` \| `unresolved` \| `escalated` \| `unknown` |
| `channel` | из диалога, иначе `unknown` |
| `vertical` | из диалога, иначе `unknown` |

`tag_key` MUST собираться так:

```
{problem_shape}|{constraint}|{ending}|{channel}|{vertical}
```

без лишних пробелов по краям. Это ключ рейтинга.

`session_id` MUST быть детерминированным: `s-` + первые 12 hex от SHA-256(`source_dialogue_id`).

PII-скроб MUST пройтись по тегам и по `turns` перед записью в пул (email, телефон, ≥10 цифр подряд, cvv/iban/ssn). Попадание заменяется заглушкой, `contains_pii=true`. Сессию из-за PII не отбрасывать.

Сессию MUST `reject` только если после скроба `problem_shape` пустой.

Рендер `turns` в текст для модели и пакета — [`PROMPTS.md` §1](./PROMPTS.md).

---

## 5. Рейтинг

Файл `data/ratings.jsonl`, одна строка на пару `(session_id, tag_key)`:

```json
{
  "session_id": "s-001",
  "tag_key": "login fails after password reset|stale jwt cache|resolved|web|retail-support",
  "score": 0.0,
  "shows": 0,
  "good": 0,
  "bad": 0,
  "unclear": 0,
  "last_shown_at": null
}
```

Стартовый `score` MUST быть `0.0`.
Новая сессия MUST получить строку рейтинга под свой собственный `tag_key` в момент записи в пул.

---

## 6. Конфиг

Один объект. Менять цифры только там.

```
MAX_PACKET            = 3
EXPLORE_SLOTS         = 1
TAG_FIELDS_MIN        = 2
DECAY_EVERY_SHOWS     = 5
DECAY_AMOUNT          = 0.1
GOOD_DELTA            = +1.0
BAD_DELTA             = -1.0
UNCLEAR_DELTA         =  0.0
```

`MAX_PACKET` включает слот ротации.
Если кандидатов меньше — пакет короче, пустые слоты не выдумывать.

---

## 7. Шаги

Каждый скрипт печатает один JSON-summary в stdout и пишет свой артефакт.
Повторный прогон MUST быть идемпотентным: upsert по id, не плодить строки.

У каждого шага строка **Промпт** — куда смотреть. Если «нет», `call_llm` звать запрещено.

### S1 — `ingest.py`

Нормализует сырые чаты в схему §3.

- вход: `--in raw.jsonl`
- выход: `data/dialogues.jsonl`
- Промпт: нет
- MUST отбросить чат без customer-turn
- MUST NOT звать LLM и MUST NOT ставить теги

Eval после шага: `kept`, `dropped`, доля отброшенных. Дальше не пускать мусор.

### S2 — `tag.py`

Компилятор. Вешает теги на целую сессию.

- вход: `--in data/dialogues.jsonl`
- выход: `data/sessions.jsonl` + стартовые строки в `data/ratings.jsonl`
- Промпт: [`PROMPTS.md` §2 system + §3 user](./PROMPTS.md), разбор §4
- MUST звать LLM только через `call_llm` и только этими строками
- MUST рендерить транскрипт по [`PROMPTS.md` §1](./PROMPTS.md)
- MUST прогнать PII-скроб
- MUST собрать `tag_key` по формуле §4
- `channel` и `vertical` MUST копировать из диалога, модель их не выдумывает
- повторный прогон той же `dialogue_id` MUST обновить ту же `session_id`, не создать вторую
- второй подряд неразборный ответ модели MUST дать `reject`, не выдумывать теги

Eval после шага: согласие тегов с золотой разметкой на замороженном куске.
Считать `problem_shape`, `constraint`, `ending` отдельно.
Плохая разметка = ранкер ещё ни при чём.

### S3 — `retrieve.py`

Ищет кандидатов в пуле по тегам query.

- вход: `--query dialogue_or_session.json` `--pool data/sessions.jsonl`
- выход: `data/candidates.jsonl` для этого query
- Промпт: нет. Если query ещё не размечен — вызвать S2 с теми же промптами §2–§3, своего текста не писать
- query MUST быть размечен тем же `tag.py` (или принять уже готовую session)
- кандидат MUST совпасть хотя бы по `TAG_FIELDS_MIN` полям из `{problem_shape, constraint, ending, channel, vertical}`
- query MUST NOT попасть в свои кандидаты (`session_id` / `source_dialogue_id` совпали)
- порядок на этом шаге не важен — это работа S4
- MUST NOT звать LLM сам, кроме делегирования в S2

Eval после шага: среди кандидатов есть сессии, которые человек пометил как «похожие»; нет сессий с нулевым пересечением тегов.
Если поиск пустой на заведомо похожей паре — ломается S3, не ранкер.

### S4 — `rank.py`

Ставит порядок и слот ротации.

- вход: `--candidates data/candidates.jsonl` `--ratings data/ratings.jsonl` `--tag-key ...`
- выход: `data/ranked.jsonl`
- Промпт: нет
- рейтинг брать по паре `(session_id, tag_key query)`. Нет строки — считать `score=0`, `shows=0`
- первые `MAX_PACKET - EXPLORE_SLOTS` мест MUST занять самые высокие `score`
- последний слот MUST быть exploration, если есть кому:
  меньше всего `shows`, при равенстве — давно не показывали (`last_shown_at`), при равенстве — меньший `session_id`
- exploration MUST NOT дублировать уже выбранную сессию
- MUST NOT звать LLM

Eval после шага:

- полезная по золоту сессия не уезжает под шум, если рейтинг уже накоплен
- в выдаче на длинном прогоне не одни и те же 1–2 id
- exploration-слот иногда содержит сессию с малым `shows`

### S5 — `mix.py`

Собирает пакет, который уйдёт агенту.

- вход: `--ranked data/ranked.jsonl` `--pool data/sessions.jsonl`
- выход: `data/packet.json` + append в `data/serves.jsonl`
- Промпт: нет LLM. Текст пакета MUST быть шаблоном [`PROMPTS.md` §5](./PROMPTS.md)
- пакет MUST содержать целые `turns` выбранных сессий, не карточки и не саммари
- в пакете MUST быть заголовок, что это прошлые диалоги-подсказки, не правило
- каждая сессия в пакете MUST начинаться с `[session_id]`
- размер MUST быть ≤ `MAX_PACKET`
- MUST записать, какие `session_id` ушли в какой `query_id` и с каким `tag_key`
- `packet.json` MUST держать и `packet_text`, и список id

Eval после шага: пакет не пустой при непустом ranked; нет self-mix; нет сессии вне ranked; в промпт не уехал весь пул.
Пустой ranked → валидный пакет из одной шапки, без выдуманных сессий.

### S6 — `outcome.py`

Ставит исход query после подмешивания.

- вход: `--query ...` `--packet data/packet.json`
- выход: одна строка в `data/outcomes.jsonl`
- Промпт: нет при `--source gold|rule` и при ручном `--outcome`. LLM-хелпер только при `--source llm`: [`PROMPTS.md` §6](./PROMPTS.md)

```json
{
  "query_id": "d-900",
  "packet_session_ids": ["s-001", "s-014"],
  "tag_key": "...",
  "outcome": "good",
  "source": "gold|rule|llm",
  "closed_at": "2026-08-28T13:00:00Z"
}
```

`outcome` MUST быть `good` | `bad` | `unclear`.

В v1 лабораторный прогон MUST уметь читать золотой исход из разметки корпуса (`source=gold`), чтобы шаг был проверяемым без живого агента.
LLM-лейбл — отдельный режим, его качество меряют отдельно и не смешивают с gold-прогоном.

Eval после шага: на золотом наборе лейбл совпадает с человеком. Если нет — S7 учить не на чем.

### S7 — `update.py`

Двигает рейтинг тех сессий, которые реально ушли в пакет.

- вход: `--outcome data/outcomes.jsonl` `--ratings data/ratings.jsonl`
- выход: обновлённый `data/ratings.jsonl`
- Промпт: нет
- для каждой сессии пакета, по `tag_key` query:
  - `shows += 1`
  - `last_shown_at = outcome.closed_at`
  - `good|bad|unclear += 1` по исходу
  - `score += GOOD_DELTA` / `BAD_DELTA` / `UNCLEAR_DELTA`
- если `shows` стал кратен `DECAY_EVERY_SHOWS`, MUST сделать `score -= DECAY_AMOUNT` (после дельты исхода)
- чужие пары `(session_id, tag_key)` MUST NOT трогать
- сессии, которых не было в пакете, MUST NOT получать ни дельту, ни decay
- MUST NOT звать LLM

Eval после шага: good поднимает score, bad опускает, decay срабатывает на частом топе, чужие ключи стоят.

---

## 8. Прогон по корпусу — `replay.py`

Единственная точка входа оператора.

```
replay.py --dialogues data/dialogues.jsonl [--until N] [--gold data/gold.jsonl]
```

Порядок на каждом диалоге `d` по `closed_at`, затем `dialogue_id`:

1. S3–S5 относительно уже лежащего пула (для первых диалогов пакет пустой — это нормально)
2. S6 — исход `d`
3. S7 — обновить рейтинг пакета, если пакет был
4. S2 — разметить `d` и положить в пул

Так сессия не подмешивает саму себя и не учится на будущем.

`replay.py` MUST NOT содержать своих промптов.

Eval всего прогона (это уже не шаг, а сводка):

- польза: исходы с пакетом от ранкера vs без пакета vs пакет из случайной похожей сессии
- ротация: доля уникальных `session_id` в пакетах, не залипли ли топ-3
- разметку сюда не смешивать — она закрыта на S2

---

## 9. Файлы состояния

| файл | кто пишет | что внутри |
|---|---|---|
| `data/dialogues.jsonl` | S1 | нормализованные чаты |
| `data/sessions.jsonl` | S2 | пул размеченных сессий |
| `data/ratings.jsonl` | S2, S7 | рейтинг по `(session_id, tag_key)` |
| `data/candidates.jsonl` | S3 | кандидаты одного query |
| `data/ranked.jsonl` | S4 | упорядоченные кандидаты |
| `data/packet.json` | S5 | текущий пакет (`packet_text` + id) |
| `data/serves.jsonl` | S5 | лог всех пакетов |
| `data/outcomes.jsonl` | S6 | исходы |
| `data/gold.jsonl` | разметка, не скрипты | золотые теги и/или исходы |

---

## 10. Что этот контур ещё не делает

Это не дыры реализации, это вне версии:

- нарезка сессии на события (отложено, экономия токенов)
- порог отсечения по score — в пакет идут выбранные слоты, даже с `score=0`
- явный лайк от агента; сигнал только `good/bad/unclear` по сессии
- удаление сессии из пула
- эмбеддинги и LLM на retrieve/rank
- системный промпт живого агента (пакет — вход, политика агента — не этот эксперимент)

---

## 11. Порядок работы для лабы

1. Прочитать README + этот SPEC + [`PROMPTS.md`](./PROMPTS.md). Поля и строки модели не выдумывать.
2. Написать скрипты S1–S7 и `replay.py`.
3. На маленьком fixture-наборе (10–20 диалогов) закрыть контракт каждого шага.
4. Потом отдельно — evaluation и золотая разметка. Спека eval здесь не подменяется.

Пока нет золота, шаги S1, S3, S4, S5, S7 всё равно MUST быть проверяемы правилами этого файла: идемпотентность, self-mix запрещён, дельты рейтинга, слот ротации.
