# Closed procedure dictionary

Frozen for this eval. Change only with a new run id and a matching edit here,
in the tagger prompt, and in `MAP.md`.

This is not a call-center ticket taxonomy. Gold on the ABCD slice cuts by
**procedure / FAQ cell**, not by “request type”. See `MAP.md` for the 1:1
unlock → procedure map.

`unlock` / `unlock_guideline` MUST NOT be passed to the tagger.
The tagger sees the transcript only.

`login_session` exists for S0 login/jwt fixtures. It is unused on the 320
Phase C pool — that is expected.

## problem_shape — procedure (33 ids, including `other`)

### Stains and care

| id | use when |
|---|---|
| `stain_paint` | paint on shoes / item, solvent, brush |
| `stain_gum` | gum on a sole (peanut butter, etc.) |
| `stain_wine` | wine / liquid on a jacket |
| `stain_grass` | grass on jeans, vinegar |
| `stain_food` | food on a shirt, cold water + soap |
| `wash_low_heat` | machine-wash a jacket, dry on low |
| `wash_color_guard` | wash a shirt, color-guard detergent, permanent press |
| `wash_frequency` | how often to wash jeans / keep the color |
| `wash_jacket` | how often to wash a jacket (do not mix with jeans) |
| `break_in` | breaking in boots, oil, hours of wear |

### Fit, material, product fact

| id | use when |
|---|---|
| `fit_width` | last width / “wider than standard” |
| `fit_sleeve` | sleeve length by size |
| `fit_inseam` | inseam / outseam |
| `fit_collar` | collar width |
| `tailoring` | hem / tailor price |
| `product_spec` | hood detaches, hidden zipper, what it is made of |
| `product_info` | stock, color, warmth, shipping as a SKU fact |
| `login_session` | cannot log in after a password reset, stale jwt / session cache (S0) |

### Site

| id | use when |
|---|---|
| `cart_not_updating` | item does not land in the cart |
| `site_slow` | slowness, close tabs, log out |
| `search_broken` | search spins / empty results |

### Price and promo

| id | use when |
|---|---|
| `price_competitor` | “cheaper elsewhere” |
| `price_changed` | price was different yesterday |
| `promo_expired` | promo code expired |
| `promo_invalid` | promo code rejected |
| `refund_process` | issue a refund (step sequence) |

### Account and order

| id | use when |
|---|---|
| `change_phone` | change phone number |
| `change_address` | change address |
| `change_name` | change name |
| `cancel_order` | cancel an order |
| `dispute_bill` | billing dispute |
| `subscription_change` | downgrade / change subscription |
| `other` | none of the above; keep rare (<10% after tagging the 320 pool) |

## constraint (audit only, not used in retrieve)

`none` · `missing_data` · `policy_block` · `system_limit` · `identity_required` · `one_off_exception`

Not part of search or the rating key.

## ending (audit only)

`resolved_info` · `resolved_action` · `resolved_exception` · `unresolved` · `escalated` · `unknown`

Gold on this slice does not use ending. After tagging, record the distribution.
If one bucket is >80%, the axis is dead — do not “fix” it with a threshold and
do not add it back into retrieve.
