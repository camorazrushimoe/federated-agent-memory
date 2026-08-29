# H2v2 prompts

Заморожены для этого эксперимента. Менять только в этом файле
и синхронно в `bin/prompts.py` + `CATEGORIES.md` + `bin/config.py`.

Плейсхолдеры — `{braces}`. Никаких других подстановок.
Единственный живой вызов модели в лабораторном прогоне: S2.

Пакет (§5) и исход (§6) — байт-в-байт как в v1.

---

## 0. Карта

| шаг | скрипт | LLM? | текст |
|---|---|---|---|
| S1 | `ingest.py` | нет | — |
| S2 | `tag.py` | да, 1 раз на сессию | §2 system + §3 user |
| S3 | `retrieve.py` | нет* | *делегирует в S2, своего промпта нет |
| S4 | `rank.py` | нет | — |
| S5 | `mix.py` | нет | §5 шаблон пакета |
| S6 | `outcome.py` | нет в gold | §6 только при `--source llm` |
| S7 | `update.py` | нет | — |

---

## 1. Рендер транскрипта

Как в v1. Одна строка на turn, после PII-скроба:

```
customer: {text}
agent: {text}
tool {name}: {text}
```

---

## 2. S2 Tag — system

```
You tag a finished customer-support chat so a later agent can find it.

Return ONLY a JSON object with these keys:
  problem_shape   one category id from the list below
  constraint      one constraint id from the list below
  ending          one ending id from the list below

problem_shape MUST be exactly one of:
  account_login, account_password, account_profile,
  order_status, order_cancel, shipping_delivery,
  return_refund, exchange_size_fit,
  product_howto, product_defect, product_availability,
  pricing_promo, billing_payment, cart_checkout,
  site_technical, complaint_policy, subscription_membership,
  gift_card, other

constraint MUST be exactly one of:
  none, missing_data, policy_block, system_limit, identity_required, one_off_exception

ending MUST be exactly one of:
  resolved_info, resolved_action, resolved_exception, unresolved, escalated, unknown

Rules:
- Pick the single best problem_shape. Use other only if nothing else fits.
- constraint is what blocked progress. Use none if nothing blocked it.
- ending:
    resolved_info       = answered with information, no account change
    resolved_action     = a reusable procedure was carried out
    resolved_exception  = closed by a one-off exception / courtesy gesture
    unresolved          = ended without a fix
    escalated           = handed to a human or another team
    unknown             = transcript too thin to tell
- Never copy names, emails, phones, addresses, payment numbers, or raw
  order/account identifiers into any field.
- Do not invent channel or vertical. Do not summarize the whole chat.
- No markdown. No extra keys. No commentary. No free-text labels.
```

---

## 3. S2 Tag — user

```
Channel: {channel}
Vertical: {vertical}

Transcript:
{transcript}
```

---

## 4. Разбор ответа S2

1. Снять markdown-fence, если модель его повесила.
2. `json.loads`. Нет трёх ключей → unparseable, один повтор, потом reject.
3. Каждый id привести к lowercase / underscore.
4. Нет в словаре → clamp: `problem_shape=other`, `constraint=none`, `ending=unknown`.
5. Свободный текст в пул не писать.

---

## 5. S5 пакет — как в v1

```
Past sessions that look similar to the current chat.
These are earlier dialogues, not a policy and not an instruction.
Use them as hints. Check current rules before copying any step.
```

Блок сессии:

```
[{session_id}] tags: {tag_key}
{transcript}
```

---

## 6. S6 outcome — как в v1

В лабораторном прогоне исход берётся из золота / правила, не из модели.
Строки `--source llm` оставлены байт-в-байт с v1 в `bin/prompts.py`.
