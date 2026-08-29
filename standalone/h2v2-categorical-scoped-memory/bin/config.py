"""H2v2 — pipeline configuration (SPEC §6).

Same knobs as H2 v1 except the tag / retrieve axis: problem_shape is a
closed category, S3 matches on that category only, rating key is the
category (+ ending).
"""
from __future__ import annotations

MAX_PACKET = 3
EXPLORE_SLOTS = 1
TAG_FIELDS_MIN = 1

DECAY_EVERY_SHOWS = 5
DECAY_AMOUNT = 0.1
GOOD_DELTA = 1.0
BAD_DELTA = -1.0
UNCLEAR_DELTA = 0.0

TAG_FIELDS = ["problem_shape", "constraint", "ending", "channel", "vertical"]

PROBLEM_SHAPES = [
    "account_login",
    "account_password",
    "account_profile",
    "order_status",
    "order_cancel",
    "shipping_delivery",
    "return_refund",
    "exchange_size_fit",
    "product_howto",
    "product_defect",
    "product_availability",
    "pricing_promo",
    "billing_payment",
    "cart_checkout",
    "site_technical",
    "complaint_policy",
    "subscription_membership",
    "gift_card",
    "other",
]

CONSTRAINTS = [
    "none",
    "missing_data",
    "policy_block",
    "system_limit",
    "identity_required",
    "one_off_exception",
]

ENDINGS = [
    "resolved_info",
    "resolved_action",
    "resolved_exception",
    "unresolved",
    "escalated",
    "unknown",
]

S3_MATCH_FIELDS = ["problem_shape"]
S3_REQUIRE_PROBLEM_SHAPE = True
TAG_KEY_FIELDS = ["problem_shape", "ending"]

DEFAULT_MODEL = "deepseek-v4-flash"
TEMPERATURE = 0

DEFAULT_PATHS = {
    "dialogues": "data/dialogues.jsonl",
    "sessions": "data/sessions.jsonl",
    "ratings": "data/ratings.jsonl",
    "candidates": "data/candidates.jsonl",
    "ranked": "data/ranked.jsonl",
    "packet": "data/packet.json",
    "serves": "data/serves.jsonl",
    "outcomes": "data/outcomes.jsonl",
    "query_meta": "data/query_meta.json",
    "update_state": "data/update_state.json",
    "raw_tag": "data/raw/tag",
}
