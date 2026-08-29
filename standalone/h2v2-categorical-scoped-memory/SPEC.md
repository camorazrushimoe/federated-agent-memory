# H2v2 — спецификация пайплайна

Контракт для `standalone/h2v2-categorical-scoped-memory/`.
Шаги S1–S7 те же, что в v1. Здесь только отличия.
Замер: [`FINDINGS.md`](./FINDINGS.md). Словарь: [`CATEGORIES.md`](./CATEGORIES.md).

`tags.problem_shape` MUST быть ровно одним id из словаря. Clamp неизвестного → `other`.
`constraint` и `ending` — аудит, не S3 и не `tag_key`.
`tag_key` MUST = `problem_shape`.
`unlock` на вход тегера MUST NOT.

```
S3_MATCH_FIELDS = [problem_shape]
TAG_KEY_FIELDS  = [problem_shape]
TAG_FIELDS_MIN  = 1
```

Гейт после S2 на 60+320, до T vs B1: id 12–28; other<10%; top-1<20%;
медиана кандидатов 8–20; пустых query<15%; recall≥0.70.
Красный = NOT FIT. Корпус не открывать. Словарь не расширять после D3.
После copy-from-v1.sh поправить checks.py (в v1 ending-enum и 5-польный tag_key).
