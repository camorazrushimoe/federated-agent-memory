# H2v2 — спецификация пайплайна

Контракт для `standalone/h2v2-categorical-scoped-memory/`.

Шаги S1–S7 те же, что в v1 (`../h2-federated-scoped-memory/SPEC.md`).
Этот файл фиксирует **только отличия**. Если здесь не сказано иначе — действует v1.

Идея: [`README.md`](./README.md). Почему не патч v1: [`WHY-NOT-V1.md`](./WHY-NOT-V1.md).
Словарь: [`CATEGORIES.md`](./CATEGORIES.md). Строки модели: [`PROMPTS.md`](./PROMPTS.md).

RFC 2119: `MUST` / `SHALL` / `SHOULD` / `MAY`.

---

## 0. Что не меняется

- единица памяти = целая сессия
- один тенант, без private/shared/global
- JSONL на диске, без эмбеддингов, без H1-импорта, без `unlock` на вход тегера
- S1 ingest / S4 rank / S5 mix / S6 outcome / S7 update — как в v1
- eval-руки B0/B1/B2/B3/T и `gold_useful.jsonl` — копия v1, не переразмечать
- `replay.py` MUST только вызывать шаги по порядку

Порядок:

```
S1 ingest   →  нормальные диалоги
S2 tag      →  сессии с категорией          [LLM: PROMPTS.md §2–§3]
S3 retrieve →  кандидаты той же категории
S4 rank     →  порядок + слот ротации
S5 mix      →  пакет                         [шаблон: PROMPTS.md §5]
S6 outcome  →  good / bad / unclear
S7 update   →  рейтинг на полке tag_key
```

---

## 4. Сессия после разметки (отличие)

```json
{
  "session_id": "s-001",
  "source_dialogue_id": "d-001",
  "closed_at": "2026-08-28T12:00:00Z",
  "channel": "web",
  "vertical": "customer-support",
  "agent_id": "agent-a",
  "turns": [],
  "tags": {
    "problem_shape": "account_login",
    "constraint": "system_limit",
    "ending": "resolved_action",
    "channel": "web",
    "vertical": "customer-support"
  },
  "tag_key": "account_login|resolved_action",
  "contains_pii": false,
  "created_at": "2026-08-28T12:00:00Z"
}
```

Правила тегов:

| поле | правило |
|---|---|
| `problem_shape` | ровно один id из `CATEGORIES.md` / `config.PROBLEM_SHAPES` (19 штук) |
| `constraint` | ровно один id из `config.CONSTRAINTS` (6 штук) |
| `ending` | ровно один id из `config.ENDINGS` (6 штук) |
| `channel` | из диалога, иначе `unknown` |
| `vertical` | из диалога, иначе `unknown` |

Свободный текст в этих трёх полях MUST NOT попасть в пул. `tag.py` MUST clamp:

- неизвестный `problem_shape` → `other`
- неизвестный `constraint` → `none`
- неизвестный `ending` → `unknown`

`tag_key` MUST собираться так:

```
{problem_shape}|{ending}
```

без лишних пробелов по краям. Это ключ рейтинга S4/S7 (`config.TAG_KEY_FIELDS`).

`session_id` MUST быть детерминированным: `s-` + первые 12 hex от SHA-256(`source_dialogue_id`) — как в v1 `common.session_id_of`.

PII-скроб — как в v1. Сессию из-за PII не отбрасывать.
Сессию MUST `reject` только если после скроба `problem_shape` пустой.

`unlock` / `unlock_guideline` MUST NOT читаться тегером и MUST NOT попадать в `tags`.

---

## 6. Конфиг (отличие)

Живые цифры только в `bin/config.py`.

```
MAX_PACKET                 = 3
EXPLORE_SLOTS              = 1
TAG_FIELDS_MIN             = 1
S3_MATCH_FIELDS            = [problem_shape]
S3_REQUIRE_PROBLEM_SHAPE   = True
TAG_KEY_FIELDS             = [problem_shape, ending]
DEFAULT_MODEL              = deepseek-v4-flash
TEMPERATURE                = 0
```

Decay и дельты исхода — как в v1. Их MUST NOT крутить, чтобы сдвинуть T.hit.

---

## 7. S3 retrieve (отличие)

Кандидат MUST иметь `tags.problem_shape` в точности равный query.

- `channel` / `vertical` в порог MUST NOT входить
- `constraint` в порог MUST NOT входить
- query MUST NOT попасть в свои кандидаты
- порядок кандидатов не нормируется — это S4
- LLM у S3 нет; неразмеченный query делегируется в тот же S2

После первого S2 на срезе 60 + пуле 320, **до** T vs B1:

- используемых `problem_shape` ≫ 2 и ≪ 60
- медиана размера бакета не 1 и не ~300
- медиана `n_candidates` — десятки, не 0 и не размер пула
- retrieve.recall по `gold_useful` не обвалился в ноль

Красный гейт = NOT FIT на словаре. Корпус 1000+200 не открывать.

---

## Что лаба сдаёт

См. [`ROUND-0-PLAN.md`](./ROUND-0-PLAN.md). Один run id на первый S2. v1 raw/tag replayть нельзя: словарь другой.
