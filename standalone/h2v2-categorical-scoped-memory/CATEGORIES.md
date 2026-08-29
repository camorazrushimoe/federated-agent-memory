# H2v2 — закрытый словарь тегов

Заморожен до первого S2. Менять только новым run id и правкой этого файла
плюс `bin/config.py` плюс `PROMPTS.md` §2.

Ориентир зерна — 55 `unlock_guideline` из H1. Список короче и **свой**.
`unlock` / `unlock_guideline` на вход тегеру MUST NOT подаваться.

## problem_shape (19)

| id | когда |
|---|---|
| `account_login` | не пускает в аккаунт, сессия, cookie |
| `account_password` | сброс / смена пароля |
| `account_profile` | имя, адрес, контакты профиля |
| `order_status` | где заказ, трекинг как факт |
| `order_cancel` | отмена заказа |
| `shipping_delivery` | доставка, служба, задержка |
| `return_refund` | возврат денег / товара |
| `exchange_size_fit` | обмен, размер, посадка |
| `product_howto` | как пользоваться / ухаживать |
| `product_defect` | брак, повреждение |
| `product_availability` | нет в наличии, когда будет |
| `pricing_promo` | цена, промокод, скидка |
| `billing_payment` | оплата, карта, списание |
| `cart_checkout` | корзина, оформление |
| `site_technical` | сайт тормозит, поиск, вёрстка |
| `complaint_policy` | жалоба на правило / тон |
| `subscription_membership` | подписка, членство |
| `gift_card` | подарочная карта |
| `other` | ничего из списка; держать редким |

## constraint (6)

`none` · `missing_data` · `policy_block` · `system_limit` · `identity_required` · `one_off_exception`

`none` в пересечение S3 не входит: S3 смотрит только `problem_shape`.

## ending (6)

| id | смысл |
|---|---|
| `resolved_info` | ответили информацией |
| `resolved_action` | сделали переносимую процедуру |
| `resolved_exception` | закрыли разовым исключением |
| `unresolved` | не закрыли |
| `escalated` | отдали человеку / другой команде |
| `unknown` | по транскрипту не видно |

v1 `resolved` у 93% был мёртвой осью. Три resolved-* должны это развить.
Если после первого S2 снова одна корзина >80% — словарь ending не сработал,
это пишется в report и не лечится порогом.
