# H2v2 — план первого раунда

Словарь — процедуры, не 19 тикетных категорий. Основание: FINDINGS.md.

| # | что | гейт |
|---|---|---|
| V2-D0 | после copy-from-v1.sh поправить checks.py под 1-польный tag_key и ending-enum v2 | S0 не падает на контракте v1 |
| V2-D1 | словарь заморожен в CATEGORIES + config + PROMPTS §2 | список id совпадает |
| V2-D2 | S0 на фикстурах новым тегером | HARD S0 зелёные |
| V2-D3 | S2 на pool 320 + slice 60 | распределение id в report |
| V2-D4 | гейт бакетов | 12–28 id; other<10%; top-1<20%; медиана 8–20; recall≥0.70 |
| V2-D5 | если D4 зелёный: T/B0–B3 на том же gold_useful | FIT / FIT WITH LIMITS / NOT FIT |

D4 красный → стоп. Запрет: unlock на вход S2; расширять словарь ради recall; возвращать ending в S3.
