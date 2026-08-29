"""H2v2 — pipeline configuration (SPEC §6).

problem_shape is a closed PROCEDURE id (not a ticket type).
S3 and the rating key use that id only.
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
    "stain_paint",
    "stain_gum",
    "stain_wine",
    "stain_grass",
    "stain_food",
    "wash_low_heat",
    "wash_color_guard",
    "wash_frequency",
    "wash_jacket",
    "break_in",
    "fit_width",
    "fit_sleeve",
    "fit_inseam",
    "fit_collar",
    "tailoring",
    "product_spec",
    "product_info",
    "login_session",
    "cart_not_updating",
    "site_slow",
    "search_broken",
    "price_competitor",
    "price_changed",
    "promo_expired",
    "promo_invalid",
    "refund_process",
    "change_phone",
    "change_address",
    "change_name",
    "cancel_order",
    "dispute_bill",
    "subscription_change",
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
TAG_KEY_FIELDS = ["problem_shape"]

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
