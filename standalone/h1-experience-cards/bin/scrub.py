"""PII scrub — SPEC.md §4 "PII gate (scrub, do not discard)".

Strip rewiring (§3c): the regexes themselves live in canonical `common.py`
(_SCRUB_RULES — the ONE source, C-EX5). This module re-exports the canonical
functions and keeps `scrub_card` as the only additive behaviour (a card-shaped
convenience over `common.scrub_pii`).

The bare word "card" is NOT matched (support chats say "gift card").
"""

from __future__ import annotations

from common import pii_matches, scrub_pii, scrub_text

# Backwards-compatible names for any caller that still imports the constants;
# the C-EX5 scan itself uses common.pii_matches (ONE source of regexes).
import re as _re

EMAIL_RE = _re.compile(r"\S+@\S+")
PHONE_RE = _re.compile(r"\+?\d[\d\-\s]{7,}\d")
DIGITS_RE = _re.compile(r"\d{10,}")
TOKEN_RE = _re.compile(r"\bcvv\b|\biban\b|\bssn\b", _re.IGNORECASE)


def scrub_card(card: dict) -> tuple[dict, bool]:
    """Scrub problem_shape / constraint / unlock / what_worked in place-ish.

    Returns (card, replaced_anything). The caller ORs replaced_anything into
    contains_pii and then applies the field limits / reject rule.
    """
    scrubbed, replaced = scrub_pii(card)
    return scrubbed, replaced
