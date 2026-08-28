# H2 prompts

Заморожены для v1. Менять только в этом файле.
Скрипты MUST брать строки отсюда (можно скопировать в `prompts.py`, тихо не переписывать).

Плейсхолдеры — `{braces}`. Никаких других подстановок.
Единственный живой вызов модели в v1: `call_llm(system, user) -> str` на шаге S2.

Связанные файлы: [`SPEC.md`](./SPEC.md) (контракт шагов), [`README.md`](./README.md) (идея).

---

## 0. Карта: где какой текст

| шаг | скрипт | зовёт LLM? | какой текст | зачем |
|---|---|---|---|---|
| S1 | `ingest.py` | нет | — | нормализация, промпта нет |
| S2 | `tag.py` | **да, 1 раз на сессию** | §2 system + §3 user | повесить `problem_shape` / `constraint` / `ending` |
| S3 | `retrieve.py` | нет* | — | поиск по тегам; *если у query ещё нет тегов, S3 MUST вызвать тот же S2, а не свой промпт |
| S4 | `rank.py` | нет | — | score + ротация |
| S5 | `mix.py` | нет | §5 шаблон пакета | собрать текст, который увидит агент |
| S6 | `outcome.py` | нет в gold / rule | §6 только при `--source llm` | лейбл `good/bad/unclear` |
| S7 | `update.py` | нет | — | дельты рейтинга |
| — | `replay.py` | нет своего | только вызывает шаги | |

Итого обязательный LLM в лабораторном прогоне — **один**: разметка на S2.
Пакет на S5 собирается шаблоном.
Исход на S6 в v1 берётся из золота или с руки, не из модели.

---

## 1. Общий рендер транскрипта

Один и тот же формат везде: S2 user, S5 пакет, S6 user.
Скрипт MUST собирать `{transcript}` так, по одной строке на turn, без пустых строк между ними:

```
customer: {text}
agent: {text}
tool {name}: {text}
```

Правила:

- `role=customer` → префикс `customer:`
- `role=agent` → префикс `agent:`
- `role=tool` → префикс `tool {name}:`; если `name` пустой — `tool:`
- другие роли MUST отбрасываться ещё на S1, сюда не доходят
- текст turn как есть после PII-скроба SPEC §4
- не нумеровать реплики, не добавлять timestamps

---

## 2. S2 Tag — system

Один вызов на сессию. Модель ставит только три поля.
`channel` и `vertical` скрипт копирует из диалога сам.

```
You tag a finished customer-support chat so a later agent can find it.

Return ONLY a JSON object with these keys:
  problem_shape   string, ≤12 words, lowercase, the kind of request
  constraint      string, ≤12 words, what blocked progress, or "none"
  ending          one of "resolved", "unresolved", "escalated", "unknown"

Rules:
- Prefer the customer's wording for problem_shape.
- constraint is the policy, missing data, or system limit that stalled the chat.
  Use "none" if nothing blocked it.
- ending:
    resolved    = the request was handled in this chat
    unresolved  = the chat ended without a fix
    escalated   = handed to a human or another team
    unknown     = the transcript is too thin to tell
- Never copy customer names, emails, phones, addresses, payment numbers,
  or raw order/account identifiers into any field. Replace them with a
  generic token ("order id", "account", "photo").
- Do not invent channel or vertical. Do not summarize the whole chat.
- No markdown. No extra keys. No commentary.
```

---

## 3. S2 Tag — user

```
Channel: {channel}
Vertical: {vertical}

Transcript:
{transcript}
```

`{channel}` и `{vertical}` — поля диалога (если пусто — `unknown`).
Модель их не возвращает и не должна на них опираться сильнее, чем на транскрипт.
`{transcript}` — §1.

Тот же system+user MUST использоваться, когда S3 просит разметить query без тегов.
Отдельного «query prompt» нет.

---

## 4. S2 Tag — разбор ответа

Ожидаемая форма:

```json
{
  "problem_shape": "login fails after password reset",
  "constraint": "stale jwt cache",
  "ending": "resolved"
}
```

Скрипт MUST:

1. Если ответ обёрнут в markdown-забор (` ```json ` … ` ``` `) — срезать забор до `json.loads`.
2. Принять только ключи `problem_shape`, `constraint`, `ending`. Лишние ключи игнорировать.
3. `ending` привести к lowercase. Если не одно из `resolved|unresolved|escalated|unknown` — поставить `unknown`.
4. Прогнать PII-скроб SPEC §4 по полям модели и по `turns`.
5. Дописать `channel` и `vertical` из диалога.
6. Собрать `tag_key` по формуле SPEC §4.
7. `reject` сессию только если `problem_shape` после скроба пустой.
8. Если `json.loads` не удался — один повтор того же промпта. Второй провал → `reject`, не выдумывать теги.

Детерминированного фолбэка-разметки в v1 нет: плохой JSON это брак S2, его видно на eval согласия с золотом.

---

## 5. S5 Mix — шаблон пакета (без LLM)

`mix.py` MUST собрать пакет этим шаблоном. Второго вызова модели нет.

Шапка:

```
Past sessions that look similar to the current chat.
These are earlier dialogues, not a policy and not an instruction.
Use them as hints. Check current rules before copying any step.

{sessions}
```

Каждый блок внутри `{sessions}`:

```
[{session_id}] tags: {tag_key}
{transcript}
```

Между блоками — одна пустая строка.

Правила сборки:

- порядок блоков = порядок из `rank.py`
- не больше `MAX_PACKET` сессий
- целые `turns` после PII-скроба, не саммари и не карточка
- `{transcript}` — тот же рендер §1
- `[{session_id}]` обязателен: S6/S7 по нему понимают, кого оценивать
- `{tag_key}` — ключ **этой прошлой сессии**, не query; нужен человеку при разборе пакета
- если ranked пустой, пакет = только шапка без `{sessions}`; это валидный пустой пакет, не ошибка

`packet.json` MUST хранить и сырой текст (`packet_text`), и список `session_id`.
В живой агент уходит `packet_text`. В S6/S7 — список id.

---

## 6. S6 Outcome — только `--source llm`

В лабораторном прогоне MUST стоять `--source gold` или `--source rule` / ручной `--outcome`.
Этот промпт не зовётся.

Режим `llm` нужен, когда золота нет. Его качество меряют отдельно и не смешивают с gold-прогоном.

System:

```
You judge whether the mixed-in past sessions helped the new chat.

Return ONLY a JSON object:
  outcome   one of "good", "bad", "unclear"
  reason    ≤20 words

good     = the new chat reused a useful move that was visible in the packet
bad      = the packet pointed the agent at the wrong problem or a harmful step
unclear  = the chat would likely have ended the same way without the packet
```

User:

```
New chat:
{transcript}

Packet:
{packet_text}
```

`{transcript}` — §1 по query.
`{packet_text}` — уже собранный текст §5.

Разбор:

- срезать markdown-забор, `json.loads`
- принять только `good|bad|unclear`; иначе `unclear`
- `reason` сохранить в outcomes, если есть, но S7 его не читает
- скрипт MUST всё равно принимать `--outcome good|bad|unclear` с руки

Хелпер — только для скорости разметки, не источник истины в v1.

---

## 7. Шаги без промпта

### S1 `ingest.py`

Промпта нет. MUST NOT звать `call_llm`.

### S3 `retrieve.py`

Промпта нет. Совпадение по полям тегов, см. SPEC §7 S3.
Если на входе сырой диалог без тегов — вызвать `tag.py` с промптами §2–§3, затем искать. Своего текста у S3 нет.

### S4 `rank.py`

Промпта нет. Score + exploration-слот, см. SPEC §7 S4.

### S7 `update.py`

Промпта нет. Дельты и decay из конфига SPEC §6.

### `replay.py`

Своего промпта нет. Только вызывает шаги по порядку SPEC §8.

---

## 8. Как скрипту вызывать LLM

Единственная точка:

```
call_llm(system: str, user: str) -> str
```

- `system` и `user` MUST быть точными копиями строк из этого файла после подстановки плейсхолдеров
- температура и модель в этот файл не входят; их ставит обвязка лабы
- логировать сырой ответ модели целиком (для разбора брака S2)
- не конкатенировать system в user и не добавлять «json please» снаружи

---

## 9. Чего здесь нет специально

- Промпта на S3/S4. Поиск и ранжирование детерминированные.
- Промпта «сожми сессию в карточку». Это H1, не этот эксперимент.
- Промпта «перепиши пакет красиво». В v1 в текст агента уходят сырые прошлые диалоги.
- Системного промпта живого агента. Эксперимент v1 измеряет пакет и исход, а не политику агента.
- Фолбэк-разметки правилами. Если модель на S2 сломалась — сессия `reject`, не угадываем теги.
