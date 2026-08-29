# S0 fixtures

Короткий набор, на котором закрывается проводка. Не корпус и не измерение пользы.

Как гонять — [`LAB-BRIEF.md`](../LAB-BRIEF.md) §5 и [`CHECKS.md`](../CHECKS.md) «Что прогонять на S0».

| файл | зачем |
|---|---|
| `dialogues.jsonl` | 10 чатов в схеме SPEC §3 |
| `gold_tags.jsonl` | человеческие теги для тех же id |
| `gold_useful.jsonl` | какие прошлые чаты были бы подсказкой |
| `queries/d-007.json` | готовый query для одиночного S3 |
| `tagged_sessions.jsonl` | **запечённый выход S2** — результат одного реального прогона `tag.py` (deepseek-v4-flash, temperature 0) по `dialogues.jsonl` |
| `raw/tag/*.json` | сырые request/response того же прогона S2 (по файлу на диалог) |
| `tag_summary.json` | статистика того же прогона: `tag_calls`, `unparseable`, `rejected`, `pii_sessions` |

Харнесс чеков (`bin/checks.py`) проигрывает S2 по `tagged_sessions.jsonl` в
replay-режиме — ноль LLM-вызовов, детерминированный прогон. `raw/tag/` и
`tag_summary.json` нужны для `C-TG10` / `C-TG12`. Перепекать фикстуры только
вместе с новым реальным прогоном S2; в PR класть и session-строки, и raw, и
summary.

`d-006` специально без customer-turn: ingest MUST его отбросить. В золоте его нет.

## Сценарии

| id | что проверяет |
|---|---|
| `d-001`, `d-002`, `d-011`, `d-012`, `d-013` | одна корзина тегов (login + stale jwt + resolved). К моменту `d-007` кандидатов больше `MAX_PACKET` — живёт ротация |
| `d-003` | другой problem_shape (refund). Не должен попадать в пакет login-query, если общих полей < 2 |
| `d-004` | тот же login, другой ending. С `TAG_FIELDS_MIN=2` ещё кандидат; полезным для `d-007` не помечен |
| `d-005` | PII: email, телефон, длинный номер. Сессия жива, идентификаторы вычищены |
| `d-006` | нет customer-turn → drop на S1 |
| `d-007` | поздний query той же корзины. Gold useful = `d-001`, `d-002` |
| `d-014` | тот же login/jwt/resolved, другой `tenant_id`. Должен находиться так же, как `d-001` (`C-ISO4`) |

Порядок `closed_at` уже расставлен. Replay кладёт сессию в пул только после S3–S7 текущего диалога, поэтому `d-007` не видит сам себя.
