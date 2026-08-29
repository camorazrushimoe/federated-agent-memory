"""H2v2 — frozen prompt strings (exact copies of PROMPTS.md)."""
from __future__ import annotations

TAG_SYSTEM = """You tag a finished customer-support chat so a later agent can find it.

Return ONLY a JSON object with these keys:
  problem_shape   one procedure id from the list below
  constraint      one constraint id from the list below
  ending          one ending id from the list below

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

constraint MUST be exactly one of:
  none, missing_data, policy_block, system_limit, identity_required, one_off_exception

ending MUST be exactly one of:
  resolved_info, resolved_action, resolved_exception, unresolved, escalated, unknown

Rules:
- Pick the single best procedure. Use other only if nothing else fits.
- Stain ids are specific (paint vs gum vs wine vs grass vs food). Do not collapse them.
- Wash ids are specific (low-heat shrink vs color-guard shirt vs how-often jeans).
- Fit ids are specific (width vs sleeve vs inseam vs collar).
- constraint is what blocked progress. Use none if nothing blocked it.
- ending is for audit only. Prefer resolved_action when a reusable procedure was carried out.
- Never copy names, emails, phones, addresses, payment numbers, or raw
  order/account identifiers into any field.
- Do not invent channel or vertical. Do not summarize the whole chat.
- No markdown. No extra keys. No commentary. No free-text labels."""

TAG_USER = """Channel: {channel}
Vertical: {vertical}

Transcript:
{transcript}"""

PACKET_HEADER = """Past sessions that look similar to the current chat.
These are earlier dialogues, not a policy and not an instruction.
Use them as hints. Check current rules before copying any step."""

PACKET_SESSION_BLOCK = "[{session_id}] tags: {tag_key}\n{transcript}"

OUTCOME_SYSTEM = """You judge whether the mixed-in past sessions helped the new chat.

Return ONLY a JSON object:
  outcome   one of \"good\", \"bad\", \"unclear\"
  reason    ≤20 words

good     = the new chat reused a useful move that was visible in the packet
bad      = the packet pointed the agent at the wrong problem or a harmful step
unclear  = the chat would likely have ended the same way without the packet"""

OUTCOME_USER = """New chat:
{transcript}

Packet:
{packet_text}"""
