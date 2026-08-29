"""H2v2 — frozen prompt strings (exact copies of PROMPTS.md).

S2 system/user differ from H2 v1: closed category vocab. Packet and
outcome strings are reused byte-identical from v1.
"""
from __future__ import annotations

TAG_SYSTEM = """You tag a finished customer-support chat so a later agent can find it.

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
