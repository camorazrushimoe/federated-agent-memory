# Лаба — с чего начать

```
cd standalone/h2v2-categorical-scoped-memory
bash bin/copy-from-v1.sh    # копирует v1 harness и патчит checks.py
bash bin/sync_h1_data.sh    # ABCD 1000+200
```

Читать в этом порядке: `FINDINGS.md` → `MAP.md` → `CATEGORIES.md` → `SPEC.md` → `ROUND-0-PLAN.md`.

- `unlock` на вход тегера нельзя. `MAP.md` — только разбор и оракул.
- Словарь заморожен. После S2 не добавлять id, чтобы спасти recall на тех же 60.
- Гейт D4: 24–32 живых id; other<10%; top-1<20%; медиана кандидатов 8–20; пустых query<15%; recall≥0.70.
  12–28 было бы красным на идеальном тегере (30 ячеек в пуле 320).
- Красный D4 → корпус 1000 не открывать. D4 не видит 680/1000 чатов вне среза.
- `gold_useful` — agent-labeled, не human gold, не переразмечать.
- Фикстуры S0 — синтетические логины (`login_session`), не ABCD. `gold_tags.jsonl` сверен с текстами.
