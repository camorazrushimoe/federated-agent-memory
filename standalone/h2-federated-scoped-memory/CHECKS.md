# H2 — проверки контракта (Layer 1)

Это не качество. Зелёный чек значит: проводка держит [`SPEC.md`](./SPEC.md).
Пользу, ротацию и цену считает [`EVAL-PLAN.md`](./EVAL-PLAN.md).

- **HARD** — прогон обнуляется, L2 не публикуется.
- **SOFT** — строка в `checks.json` и в `report.md`, прогон жив.

Строка `checks.json`: `{check_id, step, hard, passed, observed, expected, note}`.
Каждый id из этого файла MUST быть в `checks.json` на любом прогоне, даже если он тривиально зелёный. Пропущенный id = провал.

Семь гейтов из EVAL-PLAN §3 и §6.1 здесь те же id: `C-SELF`, `C-FUTURE`, `C-PII`, `C-PROMPT`, `C-SIZE`, `C-DELTA`, `C-REPLAY`.

Фикстуры для S0: [`fixtures/`](./fixtures/).

---

## Изоляция

| id | hard | правило |
|---|---|---|
| `C-ISO1` | HARD | Код живёт только в `standalone/h2-federated-scoped-memory/`. В `bin/` нет импорта из `research/`, `openspec/`, H1, GitLab-POC. |
| `C-ISO2` | HARD | Нет эмбеддингов, векторных баз, драйверов БД и сетевых вызовов кроме `call_llm` (grep: `embed`, `qdrant`, `neo4j`, `psycopg`, `chromadb`, `openai` вне обёртки). |
| `C-ISO3` | HARD | LLM только через `call_llm(system, user)`. Model / base URL / key не зашиты в `bin/`: только `--model`, `H2_BASE_URL` / `--base-url`, `H2_API_KEY`. |
| `C-ISO4` | HARD | `tenant_id` не влияет на S3/S4. Фикстура `fx-tenant`: два диалога с разными tenant и одинаковыми тегами — оба в кандидатах. |
| `C-ISO5` | HARD | Прогон не пишет в исходный корпус и не пишет в папку H1 `data/`. Состояние — в run dir или в локальном `data/`, который можно gitignore. |

---

## S1 — `ingest.py`

| id | hard | правило |
|---|---|---|
| `C-IN1` | HARD | `kept + dropped ==` число строк входа. Тихо ничего не пропадает. |
| `C-IN2` | HARD | Отброшен только чат без customer-turn. У каждого kept есть ≥1 customer. Фикстура `fx-drop`. |
| `C-IN3` | HARD | У kept есть `dialogue_id`, `vertical`, `agent_id`, `channel`, `turns[].role ∈ {customer, agent, tool}`. `tenant_id` MAY быть. |
| `C-IN4` | HARD | `dialogue_id` уникальны. |
| `C-IN5` | HARD | Повторный ingest — байт-идентичный `dialogues.jsonl` (upsert, не append-дубли). |
| `C-IN6` | HARD | Теги на этом шаге не ставятся. LLM не зовётся. |

---

## S2 — `tag.py`

| id | hard | правило |
|---|---|---|
| `C-PROMPT` | HARD | system/user — ровно [`PROMPTS.md`](./PROMPTS.md) §2–§3. Своего текста нет. Транскрипт рендерится по §1. |
| `C-TG1` | HARD | `session_id == "s-" + sha256(source_dialogue_id)[:12]`. |
| `C-TG2` | HARD | `channel` и `vertical` скопированы из диалога, не из ответа модели. |
| `C-TG3` | HARD | `tag_key == problem_shape\|constraint\|ending\|channel\|vertical` без краевых пробелов. |
| `C-TG4` | HARD | `ending ∈ {resolved, unresolved, escalated, unknown}`. `constraint` — строка ≤12 слов или `none`. `problem_shape` ≤12 слов. |
| `C-TG5` | HARD | Повторный tag той же `dialogue_id` обновляет ту же `session_id`, второй строки в пуле нет. |
| `C-TG6` | HARD | Reject только если после скроба `problem_shape` пустой. PII сам по себе не reject. Фикстура `fx-pii`. |
| `C-PII` | HARD | После скроба в тегах и `turns` нет `\\S+@\\S+`, телефона, ≥10 цифр подряд, `cvv` / `iban` / `ssn`. Скан всего пула, не только фикстуры. |
| `C-TG7` | HARD | На `fx-pii`: сессия жива, `contains_pii=true`, сырой email/телефон/длинный номер в тегах и `turns` отсутствуют. |
| `C-TG8` | HARD | Слово `card` в «gift card» само по себе не ставит `contains_pii`. |
| `C-TG9` | HARD | Два подряд неразборных ответа модели → reject, теги не выдумываются. |
| `C-TG10` | HARD | На каждый вызов есть `raw/tag/<dialogue_id>.json` с request, response, model, usage. Число файлов = `tag_calls` в `cost.json`. |
| `C-TG11` | HARD | Новая сессия получает стартовую строку рейтинга под свой `tag_key` со `score=0`, `shows=0`. |
| `C-TG12` | SOFT | Доля неразборного JSON и доля reject записаны. |
| `C-TG13` | SOFT | Grounding: для непустого `problem_shape` и не-`none` `constraint` — есть ли слово ≥5 символов в транскрипте. Считать, не валить прогон. |

---

## S3 — `retrieve.py`

| id | hard | правило |
|---|---|---|
| `C-SELF` | HARD | Query не попадает в кандидаты по `session_id` или `source_dialogue_id`. |
| `C-RT1` | HARD | Кандидат совпал хотя бы по `TAG_FIELDS_MIN` полям из `{problem_shape, constraint, ending, channel, vertical}`. Ноль пересечения — не кандидат. |
| `C-RT2` | HARD | Фикстура `fx-similar`: у `d-007` в кандидатах есть `d-001` и `d-002`. |
| `C-RT3` | HARD | Фикстура `fx-far`: `d-003` (refund) не обязан быть в кандидатах `d-007`, если общих полей < `TAG_FIELDS_MIN`. |
| `C-RT4` | HARD | Шаг сам LLM не зовёт. Если query без тегов — только делегирование в `tag.py` с теми же промптами. |
| `C-RT5` | HARD | Повторный retrieve на том же пуле и query — тот же набор id (порядок не важен). |

---

## S4 — `rank.py`

| id | hard | правило |
|---|---|---|
| `C-RK1` | HARD | Первые `MAX_PACKET - EXPLORE_SLOTS` мест — максимальный `score` по паре `(session_id, tag_key query)`. Нет строки рейтинга → `score=0`, `shows=0`. |
| `C-RK2` | HARD | Последний слот — exploration, если есть лишний кандидат: меньше `shows`, затем старше `last_shown_at` (null считается самым старым), затем меньший `session_id`. |
| `C-RK3` | HARD | Explore не дублирует уже выбранный id. |
| `C-RK4` | HARD | Фикстура `fx-rotate`: при пяти кандидатах с одинаковыми тегами пакет длины 3, и третий id не обязан быть третьим по score. |
| `C-RK5` | HARD | LLM нет. Повторный rank на тех же ratings — байт-идентичный `ranked.jsonl`. |
| `C-RK6` | SOFT | Если кандидатов ≤ `MAX_PACKET`, explore-слот отдельно не выдумывается — пакет = все кандидаты, отсортированные по score. |

---

## S5 — `mix.py`

| id | hard | правило |
|---|---|---|
| `C-SIZE` | HARD | Число сессий в пакете ≤ `MAX_PACKET`. Пустых слотов нет. Пустой ranked → пакет из одной шапки, без выдуманных сессий. |
| `C-MX1` | HARD | В пакет идут целые `turns`, не саммари и не карточки. |
| `C-MX2` | HARD | Текст пакета — шаблон [`PROMPTS.md`](./PROMPTS.md) §5. Шапка на месте. Каждый блок начинается с `[session_id]`. |
| `C-MX3` | HARD | Self-mix запрещён (это же `C-SELF` на выходе mix). Нет id вне ranked. |
| `C-MX4` | HARD | `serves.jsonl` содержит `query_id`, `tag_key`, список `session_id` в порядке пакета. |
| `C-MX5` | HARD | `packet.json` держит и `packet_text`, и список id. |
| `C-MX6` | HARD | Повторный mix на том же ranked — тот же `packet_text`. |

---

## S6 — `outcome.py`

| id | hard | правило |
|---|---|---|
| `C-OC1` | HARD | Лабораторный прогон идёт с `--source gold`. LLM-хелпер в этом режиме не зовётся. |
| `C-OC2` | HARD | Gold-исход: пакет ∩ `useful_dialogue_ids` непустой → `good`; пакет непустой и пересечение пустое → `bad`; пакет пустой → `unclear`. |
| `C-OC3` | HARD | `outcome ∈ {good, bad, unclear}`. Лишних значений нет. |
| `C-OC4` | HARD | Строка в `outcomes.jsonl` содержит `query_id`, `packet_session_ids`, `tag_key`, `outcome`, `source`, `closed_at`. |
| `C-OC5` | HARD | Режим `--source llm` пишет `source=llm` и не попадает в те же агрегаты, что gold. |

---

## S7 — `update.py`

| id | hard | правило |
|---|---|---|
| `C-DELTA` | HARD | Дельта и `shows += 1` только у пар `(session_id из пакета, tag_key query)`. Чужие строки байт-в-байт те же. |
| `C-UP1` | HARD | `good` → `score += GOOD_DELTA`, `bad` → `BAD_DELTA`, `unclear` → `UNCLEAR_DELTA`. Счётчик соответствующего исхода `+= 1`. |
| `C-UP2` | HARD | `last_shown_at = outcome.closed_at`. |
| `C-UP3` | HARD | Если после инкремента `shows % DECAY_EVERY_SHOWS == 0`, `score -= DECAY_AMOUNT` (после дельты исхода). Фикстура `fx-decay`. |
| `C-UP4` | HARD | Сессии не из пакета не получают ни дельту, ни decay. |
| `C-UP5` | HARD | LLM нет. Повторный update той же outcome-строки идемпотентен: вторая прогонка не плюсует score ещё раз (ключ — `query_id` + пакет, не «ещё один проход файла»). |

`C-UP5` проверять так: прогнать S7 дважды на одном и том же `outcomes.jsonl` без новых строк — ratings не должны уехать второй раз. Значит update MUST помнить обработанные `query_id` либо принимать ровно одну новую строку за вызов.

---

## Replay

| id | hard | правило |
|---|---|---|
| `C-FUTURE` | HARD | В кандидатах и пакете нет сессии с `closed_at >= query.closed_at`. Порядок SPEC §8: сначала S3–S5 по уже лежащему пулу, потом S6/S7, потом S2 кладёт текущий диалог. |
| `C-RP1` | HARD | `replay.py` не содержит своих промптов и своей логики поиска/ранжирования. Только вызов шагов. |
| `C-RP2` | HARD | На фикстурах первые диалоги могут получить пустой пакет — это не ошибка. |
| `C-REPLAY` | HARD | `--replay <run_id>` не зовёт LLM и воспроизводит `metrics.json` байт-в-байт. |
| `C-RP3` | HARD | `manifest.json` держит sha256 входов, `PROMPTS.md`, конфига, каждого артефакта. Нет sha — прогон воид. |

---

## Eval

| id | hard | правило |
|---|---|---|
| `C-EV1` | HARD | У каждой руки `hit + wrong + abstain == 1.0` на том же n. |
| `C-EV2` | HARD | B0: `hit == 0`, `abstain == 1`. Иначе сломан подсчёт. |
| `C-EV3` | HARD | T, B0, B1, B2, B3 идут через одну функцию классов. Нет второй копии метрики. |
| `C-EV4` | HARD | B1 фиксирует `--seed`. Два вызова с одним seed — один набор id. |
| `C-EV5` | HARD | `per_query.jsonl` — одна строка на query из gold_useful. Сумма по файлу сходится с `metrics.json`. |
| `C-EV6` | HARD | `audit.json` отвечает A1–A6 числами до публикации S2 full. |
| `C-EV7` | SOFT | `cost.json` указывает способ токенов и источник цены. Нет прайса → `usd` = null, не догадка. |

---

## Негативные контроли

Ломают харнесс, не «находку про данные». Сначала чинить проверку.

| id | hard | контроль |
|---|---|---|
| `C-NC1` | HARD | Пустой пул → все пакеты пустые, ни одного self-mix, B0 и T совпадают. |
| `C-NC2` | HARD | Переставить всем сессиям в пуле `closed_at` в будущее относительно query → пакеты пустые, `C-FUTURE` зелёный. |
| `C-NC3` | HARD | Очистить `gold_useful` до пустых списков → T.`hit` == 0. Если hit жив — метрика смотрит не туда. |
| `C-NC4` | HARD | `TAG_FIELDS_MIN = 5` на фикстуре, где золотые пары делят 2–3 поля → `retrieve_empty` растёт, B3.`hit` падает. |
| `C-NC5` | SOFT | `EXPLORE_SLOTS = 0` → `explore_fill == 0` и выдача совпадает с B2. |

---

## D0 — золото пользы (Phase B, ROUND-0-PLAN §7)

Гоняются на артефактах D0-прогона: `data/gold_useful.jsonl` +
`data/d0_slice.jsonl` + `data/raw_gold_useful/` (лежат локально, PII-guard).
Пока артефактов нет — строки в `checks.json` идут deferred (S0 не валят).

| id | hard | правило |
|---|---|---|
| `C-GD1` | HARD | `gold_useful.jsonl` начинается с `#`-заголовка «AGENT-LABELED GOLD — NOT HUMAN GOLD» (labeler=…, prompt_sha, corpus_sha, slice_sha, created_at). Потребители пропускают `#`-строки. |
| `C-GD2` | HARD | Каждый `useful_dialogue_id` имеет `closed_at` строго раньше query (нет future-leak). |
| `C-GD3` | HARD | В золоте нет PII (`notes`, id): email / телефон / ≥10 цифр подряд / iban / ssn / cvv-паттерн. |
| `C-GD4` | HARD | Строк == строк среза (60); `query_id` уникальны и ⊆ `d0_slice.jsonl`. |
| `C-GD5` | HARD | `data/raw_gold_useful/` — один файл на строку золота; count == rows. |
| `C-GD6` | SOFT | Согласие с seed: на 6 seed-строках направление списков (пустой/непустой) не противоречит seed. Противоречие → разобрать, в отчёт. |
| `C-GD7` | HARD | Анти-H1 коллинеарность (rule 3): useful-множества строго уже корзин `unlock_guideline`. Строк, где useful == все прошлые same-guideline сессии (H1-сигнатура), ≤ 20% непустых строк; каждая how-to строка исключает ≥1 same-guideline сессию, если такая есть. Провал ⇒ labeler переоткрыл H1 ⇒ новый run id. |
| `C-GD8` | HARD | Манифест D0: `labeler_model == deepseek-v4-pro`; модель S2-петли не тронута (`deepseek-v4-flash`). |

---

## Что прогонять на S0

Минимум, без корпуса и без золота корпуса:

`C-ISO*`, `C-IN*`, `C-PROMPT`, `C-TG1`–`C-TG11`, `C-PII`, `C-SELF`, `C-RT1`–`C-RT5`, `C-RK1`–`C-RK5`, `C-SIZE`, `C-MX*`, `C-OC1`–`C-OC4`, `C-DELTA`, `C-UP1`–`C-UP5`, `C-FUTURE`, `C-RP1`–`C-RP2`, `C-NC1`.

`C-REPLAY` и `C-EV*` закрываются, когда появляется runner. `C-GD*` закрываются на D0-прогоне (Phase B). До этого шаги гоняются по одному на [`fixtures/`](./fixtures/).
