# Что откуда

H2v2 (поиск FIT, ранкер NOT FIT): `../h2v2-categorical-scoped-memory/`
H2 v1 (заморожен NOT FIT): `../h2-federated-scoped-memory/`
H1 корпус: `../h1-experience-cards/data/`

Эта папка не патч v2. Harness поднимается скриптом, не submodule.

## Что копирует `bin/copy-from-v2.sh`

1. Запускает `../h2v2-categorical-scoped-memory/bin/copy-from-v1.sh`
   (золото, срез, checks, mix, llm, eval, labeler, fixtures).
2. Копирует из v2 в эту папку то, без чего не поднять S2/S3/D4:

| path |
|---|
| CATEGORIES.md |
| MAP.md |
| bin/config.py |
| bin/prompts.py |
| bin/tag.py |
| bin/tag_parallel.py |
| bin/retrieve.py |
| bin/eval_live_d4.py |
| bin/run_oracle_d4.py |
| bin/sync_h1_data.sh (затем патчится dest на эту папку) |

3. Копирует из уже материализованного v2: gold, slice, mix, llm,
   common, build_phase_c_inputs, adapt_h1_corpus.

Файлы этой папки (`README`, `SPEC`, `EVAL-PLAN`, `PROMPTS`,
`bin/build_ffp_packets.py`, `bin/judge_ffp.py`, `bin/eval_ffp.py`,
`bin/prompts_judge.py`) скрипт MUST NOT затирать.

## Своё у v3

- README.md, WHY-THIS-ROUND.md, DATA.md, SPEC.md, EVAL-PLAN.md
- PIPELINE.md, ROUND-0-PLAN.md, PROMPTS.md, HANDOFF.md, SOURCE.md
- LAB-BRIEF.md
- bin/copy-from-v2.sh, bin/sync_h1_data.sh
- bin/build_ffp_packets.py, bin/judge_ffp.py, bin/eval_ffp.py
- bin/prompts_judge.py, bin/split_pool_query.py

## Чего не копируем зачем попало

- `bin/rank.py` / `bin/update.py` / `bin/replay.py` — не часть FFP.
  Они могут оказаться на диске после copy-from-v1 внутри v2; сборщик
  пакетов FFP их не импортирует.
- `runs/` v2 с транскриптами.
- Корпус ABCD.
