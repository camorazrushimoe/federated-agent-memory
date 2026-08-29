# Лаба — с чего начать

```
cd standalone/h2v2-categorical-scoped-memory
bash bin/copy-from-v1.sh    # копирует v1 harness и патчит checks.py
bash bin/sync_h1_data.sh    # ABCD 1000+200
```

Читать в этом порядке: `FINDINGS.md` → `MAP.md` → `CATEGORIES.md` → `SPEC.md` → `ROUND-0-PLAN.md` → `REPORT.md`.

- `unlock` на вход тегера нельзя. `MAP.md` — только разбор и оракул.
- Словарь заморожен. После S2 не добавлять id, чтобы спасти recall на тех же 60.
- Гейт D4: 24–32 живых id; other<10%; top-1<20%; медиана 8–20; пустых query<15%; recall≥0.70.
- Красный D4 → корпус 1000 не открывать.
- `gold_useful` — agent-labeled, не human gold, не переразмечать.
- Фикстуры S0 — синтетические логины (`login_session`), не ABCD.

## Раунд 0 закрыт (2026-08-29)

См. [`REPORT.md`](./REPORT.md).

- D4 на живом S2 (`deepseek-v4-flash`): **FIT** (recall 0.81, медиана 10).
- T vs B1: **NOT FIT** (38 = 38).
- Вердикт продукта: **FIT WITH LIMITS**.
