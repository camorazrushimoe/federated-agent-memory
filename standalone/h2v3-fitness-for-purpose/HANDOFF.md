# Лаба — с чего начать

```
cd standalone/h2v3-fitness-for-purpose
bash bin/copy-from-v2.sh
bash bin/sync_h1_data.sh
```

Читать в этом порядке:

`WHY-THIS-ROUND.md` → `DATA.md` → `SPEC.md` → `EVAL-PLAN.md` →
`PIPELINE.md` → `ROUND-0-PLAN.md` → `PROMPTS.md`.

- Ранкера нет. `rank.py` / `update.py` после copy лежат как часть
  harness v2 и нужны только precondition-скрипту D4. Сборщик пакетов
  FFP их не вызывает.
- `gold_useful` — agent-labeled, не human gold, не переразмечать.
- `unlock` на вход тегера и судьи нельзя.
- Словарь процедур заморожен в v2. Здесь его не расширять.
- Пороги FFP в `EVAL-PLAN.md` §6 заморожены до первого живого S8.

Предыдущий закрытый раунд: [`../h2v2-categorical-scoped-memory/REPORT.md`](../h2v2-categorical-scoped-memory/REPORT.md).
