# Shared eval inputs (не эксперимент)

Копии входных данных для H2 / H2v2. Лежат в `standalone/eval-inputs/`,
рядом с экспериментами, не внутри них. Оригиналы не трогали.

- сырые сессии: `standalone/h1-experience-cards/data/`
- срез и gold: `standalone/h2-federated-scoped-memory/data/`

`abcd_1000_pool.jsonl` (1.7MB) уже лежит в H1. GitHub Contents API не
принимает файл >1MB, поэтому тысяча копируется локально:

```
bash standalone/eval-inputs/sync_all.sh
```

## Сколько диалогов реально ест эксперимент

Не тысячу и не двести целиком.

| слой | сколько | файл | роль |
|---|---:|---|---|
| полный train ABCD | 1000 | `abcd_1000_pool.jsonl` | сырьё, из него режется рабочий пул |
| полный hold-out ABCD | 200 | `abcd_200_holdout.jsonl` | сырьё, из него режутся 60 вопросов |
| рабочий пул памяти Phase C / D4 | **320** | `build_phase_c_inputs.py` из 1000 | эти сессии скармливают тегеру как прошлые чаты |
| вопросы eval | **60** | `d0_slice.jsonl` + `queries_60.jsonl` | по одному query смотрят retrieve |
| gold пользы (оракул B3) | 60 строк | `gold_useful.jsonl` | какие прошлые id были бы полезны |

320 = сессии из 1000 с тем же `unlock`, что у 60 query, и строго раньше query.

Живой прогон D4: разметить **320 + 60**, потом 60 раз retrieve, сравнить с gold.

Полные 1000 в раунде 0 не открывали.

## Файлы здесь

- `abcd_200_holdout.jsonl` — сырой hold-out (200), появляется после `sync_all.sh`
- `abcd_1000_pool.jsonl` — сырой train (1000), тоже после `sync_all.sh`
- `preview_10.jsonl` — первые 10 из pool
- `d0_slice.jsonl` — 60 query без текста (`query_id`, `family`, `unlock`, `closed_at`)
- `queries_60.jsonl` — те же 60 уже с транскриптами (это «вопросы»)
- `gold_useful.jsonl` — gold пользы, agent-labeled `deepseek-v4-pro`, не human gold
- `gold_useful.manifest.json` — манифест разметки
- `gold_useful.seed.jsonl` — 6 seed-строк, не полный gold
- `sync_all.sh` — скопировать всё сюда и склеить `queries_60.jsonl`

`dialogue_id` = `d-{chat_id}`. `unlock` в сырье есть, в теги H2v2 не класть.
