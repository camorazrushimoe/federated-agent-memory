# H2v2 prompts

Заморожены. Менять только здесь и синхронно в `bin/prompts.py` + `CATEGORIES.md` + `bin/config.py`.

## 2. S2 Tag — system

problem_shape MUST be exactly one of:
  stain_paint, stain_gum, stain_wine, stain_grass, stain_food,
  wash_low_heat, wash_color_guard, wash_frequency, break_in,
  fit_width, fit_sleeve, fit_inseam, fit_collar, tailoring,
  product_spec, product_info,
  cart_not_updating, site_slow, search_broken,
  price_competitor, price_changed, promo_expired, promo_invalid,
  refund_process,
  change_phone, change_address, change_name,
  cancel_order, dispute_bill, subscription_change,
  other

Rules: pick one procedure; do not collapse stain/wash/fit ids; no unlock; no free text.

User template unchanged:
Channel: {channel}
Vertical: {vertical}
Transcript: {transcript}
