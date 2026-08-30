# Unlock → problem_shape (frozen)

This is **not** tagger input. The tagger must not see `unlock`.
The map exists so the oracle and tagger review are checkable.

The slice has 30 unlock values. Each is its own ABCD FAQ cell.
Gold measures the cell, so `wash_frequency` (jeans) and `wash_jacket`
(jacket) stay separate. A shared “how often to wash” bucket collapses
them and drops precision.

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

Not in the slice:

| source | problem_shape |
|---|---|
| S0 login/jwt fixtures | login_session |
| nothing in the list | other |
| SKU fact with no procedure | product_info |

`product_info` may be empty on a perfect oracle of this slice. That is fine.
Failure is a live tagger dumping how-to cells into `product_info`.
