# M1 Pair-Construction Capacity (computed from the corpus, not assumed)

- conversations: **10042** (8034/1004/1004) · flows **10** · subflows **96**
- products (distinct `scenario.product` values): `{"amounts": [], "names": []}`=2585, `{"amounts": [54], "names": ["calvin_klei`=50, `{"amounts": [94], "names": ["tommy_hilfi`=49, `{"amounts": [54], "names": ["calvin_klei`=49, `{"amounts": [84], "names": ["calvin_klei`=48, `{"amounts": [59], "names": ["guess jacke`=48, `{"amounts": [94], "names": ["calvin_klei`=47, `{"amounts": [89], "names": ["guess jeans`=47, `{"amounts": [59], "names": ["michael_kor`=47, `{"amounts": [69], "names": ["guess shirt`=46 (+1304 more)
- subflows with <5 conversations: **1** (of 96); <2 (cannot form any same-subflow pair): **0**
- flows with a single subflow (no ambiguous-band pairs inside): []
- **FINDING — empty `scenario.product`: 2585 conversations (25.7%) have `product = {amounts: [], names: []}`. A cross-*product* sub-band can only be constructed from the 7457 conversations that carry a non-empty product. Pre-registered rule for evaluation: a pair whose either side has an empty product is judged on problem shape only (rule R3) and is NOT auto-assigned to the cross-product sub-band.

## Pair ceilings (theoretical max, no conversation reuse)

| band | ceiling |
|---|---|
| should-match (same subflow) | 848,766 |
| ambiguous (diff subflow, same flow) | 4,246,706 |
| should-not-match (cross-flow, incl. cross-product) | 45,320,389 |

## Flows

| flow | conversations | subflows |
|---|---|---|
| storewide_query | 1094 | 16 |
| purchase_dispute | 1076 | 8 |
| product_defect | 1070 | 6 |
| account_access | 1048 | 3 |
| single_item_query | 1045 | 32 |
| order_issue | 1040 | 9 |
| troubleshoot_site | 1026 | 4 |
| shipping_issue | 1020 | 4 |
| subscription_inquiry | 910 | 6 |
| manage_account | 713 | 8 |

## Subflows (sorted by size)

| subflow | flow | conversations | max same-subflow pairs |
|---|---|---|---|
| recover_username | account_access | 361 | 64980 |
| reset_2fa | account_access | 351 | 61425 |
| recover_password | account_access | 336 | 56280 |
| status | shipping_issue | 268 | 35778 |
| credit_card | troubleshoot_site | 266 | 35245 |
| missing | shipping_issue | 261 | 33930 |
| search_results | troubleshoot_site | 259 | 33411 |
| shopping_cart | troubleshoot_site | 251 | 31375 |
| slow_speed | troubleshoot_site | 250 | 31125 |
| manage | shipping_issue | 248 | 30628 |
| cost | shipping_issue | 243 | 29403 |
| return_size | product_defect | 191 | 18145 |
| manage_dispute_bill | subscription_inquiry | 190 | 17955 |
| status_due_amount | subscription_inquiry | 185 | 17020 |
| return_color | product_defect | 180 | 16110 |
| refund_status | product_defect | 179 | 15931 |
| status_due_date | subscription_inquiry | 178 | 15753 |
| refund_update | product_defect | 177 | 15576 |
| refund_initiate | product_defect | 176 | 15400 |
| return_stain | product_defect | 167 | 13861 |
| manage_extension | subscription_inquiry | 165 | 13530 |
| manage_pay_bill | subscription_inquiry | 162 | 13041 |
| status_service_removed | manage_account | 153 | 11628 |
| bad_price_competitor | purchase_dispute | 149 | 11026 |
| out_of_stock_general | purchase_dispute | 140 | 9730 |
| mistimed_billing_never_bought | purchase_dispute | 139 | 9591 |
| status_delivery_time | order_issue | 139 | 9591 |
| bad_price_yesterday | purchase_dispute | 139 | 9591 |
| mistimed_billing_already_returned | purchase_dispute | 137 | 9316 |
| status_quantity | order_issue | 135 | 9045 |
| status_payment_method | order_issue | 134 | 8911 |
| manage_create | order_issue | 134 | 8911 |
| promo_code_invalid | purchase_dispute | 133 | 8778 |
| status_shipping_question | manage_account | 131 | 8515 |
| status_mystery_fee | order_issue | 130 | 8385 |
| status_service_added | manage_account | 129 | 8256 |
| out_of_stock_one_item | purchase_dispute | 127 | 8001 |
| manage_cancel | order_issue | 125 | 7750 |
| manage_downgrade | order_issue | 123 | 7503 |
| manage_upgrade | order_issue | 117 | 6786 |
| status_credit_missing | manage_account | 114 | 6441 |
| promo_code_out_of_date | purchase_dispute | 112 | 6216 |
| pricing_3 | storewide_query | 81 | 3240 |
| pricing_2 | storewide_query | 76 | 2850 |
| membership_1 | storewide_query | 76 | 2850 |
| timing_1 | storewide_query | 76 | 2850 |
| membership_3 | storewide_query | 71 | 2485 |
| policy_2 | storewide_query | 70 | 2415 |
| policy_1 | storewide_query | 69 | 2346 |
| membership_4 | storewide_query | 69 | 2346 |
| policy_4 | storewide_query | 69 | 2346 |
| timing_4 | storewide_query | 65 | 2080 |
| membership_2 | storewide_query | 65 | 2080 |
| pricing_4 | storewide_query | 65 | 2080 |
| policy_3 | storewide_query | 64 | 2016 |
| timing_2 | storewide_query | 63 | 1953 |
| timing_3 | storewide_query | 60 | 1770 |
| pricing_1 | storewide_query | 55 | 1485 |
| manage_change_name | manage_account | 51 | 1275 |
| manage_change_address | manage_account | 51 | 1275 |
| manage_change_phone | manage_account | 48 | 1128 |
| jacket_other_4 | single_item_query | 45 | 990 |
| boots_how_2 | single_item_query | 43 | 903 |
| boots_other_1 | single_item_query | 42 | 861 |
| jeans_other_3 | single_item_query | 40 | 780 |
| jacket_how_2 | single_item_query | 39 | 741 |
| boots_other_4 | single_item_query | 37 | 666 |
| jacket_how_4 | single_item_query | 36 | 630 |
| boots_other_2 | single_item_query | 36 | 630 |
| manage_payment_method | manage_account | 36 | 630 |
| shirt_other_2 | single_item_query | 34 | 561 |
| jeans_how_2 | single_item_query | 34 | 561 |
| shirt_how_1 | single_item_query | 34 | 561 |
| boots_other_3 | single_item_query | 34 | 561 |
| jeans_other_1 | single_item_query | 33 | 528 |
| shirt_how_4 | single_item_query | 33 | 528 |
| shirt_other_1 | single_item_query | 33 | 528 |
| jeans_other_2 | single_item_query | 32 | 496 |
| jeans_other_4 | single_item_query | 32 | 496 |
| boots_how_3 | single_item_query | 32 | 496 |
| jeans_how_1 | single_item_query | 31 | 465 |
| shirt_how_2 | single_item_query | 31 | 465 |
| status_questions | subscription_inquiry | 30 | 435 |
| shirt_how_3 | single_item_query | 30 | 435 |
| jacket_other_2 | single_item_query | 30 | 435 |
| boots_how_4 | single_item_query | 30 | 435 |
| jacket_how_1 | single_item_query | 29 | 406 |
| jacket_other_1 | single_item_query | 29 | 406 |
| jeans_how_3 | single_item_query | 28 | 378 |
| jacket_how_3 | single_item_query | 28 | 378 |
| jacket_other_3 | single_item_query | 27 | 351 |
| boots_how_1 | single_item_query | 27 | 351 |
| shirt_other_4 | single_item_query | 27 | 351 |
| shirt_other_3 | single_item_query | 27 | 351 |
| jeans_how_4 | single_item_query | 22 | 231 |
| status_delivery_date | order_issue | 3 | 3 |

_Computed by `pair_capacity.py` (deterministic; re-run to reproduce). Purpose: the engineer's stratification must fit under these ceilings; evaluation checks the delivered `candidate_pairs.jsonl` against them._
