# Unlock → problem_shape (заморожено)

Это **не** вход тегера. Тегер `unlock` не видит.
Карта нужна, чтобы оракул и разбор S2 были проверяемыми, а не устными.

Срез содержит 30 unlock. Каждый — своя FAQ-ячейка ABCD.
Имена id звучат как процедура; золото меряет ячейку. Поэтому
`wash_frequency` (джинсы) и `wash_jacket` (куртка) разделены:
общее «как часто стирать» на оракуле даёт бакет 22 и precision 0.50
на этих query, а золото 393/393 требует тот же unlock.

| unlock | problem_shape |
|---|---|
| boots_how_1 | stain_paint |
| boots_how_2 | fit_width |
| boots_how_3 | stain_gum |
| boots_how_4 | break_in |
| jacket_how_1 | stain_wine |
| jacket_how_2 | wash_low_heat |
| jacket_how_3 | wash_jacket |
| jacket_how_4 | product_spec |
| jeans_how_1 | stain_grass |
| jeans_how_2 | wash_frequency |
| jeans_how_3 | fit_inseam |
| jeans_how_4 | tailoring |
| shirt_how_1 | stain_food |
| shirt_how_2 | wash_color_guard |
| shirt_how_3 | fit_sleeve |
| shirt_how_4 | fit_collar |
| shopping_cart | cart_not_updating |
| slow_speed | site_slow |
| search_results | search_broken |
| bad_price_competitor | price_competitor |
| bad_price_yesterday | price_changed |
| promo_code_out_of_date | promo_expired |
| promo_code_invalid | promo_invalid |
| refund_initiate | refund_process |
| manage_change_phone | change_phone |
| manage_change_address | change_address |
| manage_change_name | change_name |
| manage_cancel | cancel_order |
| manage_dispute_bill | dispute_bill |
| manage_downgrade | subscription_change |

Не из среза:

| источник | problem_shape |
|---|---|
| S0 фикстуры login/jwt | login_session |
| ничего из списка | other |
| запас под SKU-факт без процедуры | product_info |

`product_info` на идеальном оракуле среза может быть пустым.
Это не провал. Провал — если живой S2 сваливает в него howto-ячейки.
