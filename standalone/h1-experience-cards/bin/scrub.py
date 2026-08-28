"""PII scrub — SPEC.md §4 "PII gate (scrub, do not discard)".

Runs on every string field and every what_worked item AFTER the model returns
JSON. Replaces each hit with a generic token and sets contains_pii=true if
anything was replaced. The bare word "card" is NOT matched (support chats say
"gift card").

Note: SPEC §4's regexes are what they are — a 4-digit order id like "4412" is
not caught by `\\d{10,}`; that case is handled by the extract prompt itself,
and C-EX6 verifies it on the fixture.
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\S+@\S+")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{7,}\d")
DIGITS_RE = re.compile(r"\d{10,}")
TOKEN_RE = re.compile(r"\bcvv\b|\biban\b|\bssn\b", re.IGNORECASE)

# regex -> replacement token (SPEC §4: "order id", "account", "email", "phone")
_PATTERNS = [
    (EMAIL_RE, "email"),
    (PHONE_RE, "phone"),
    (DIGITS_RE, "order id"),
    (TOKEN_RE, "account"),
]


def scrub_text(text: str) -> tuple[str, bool]:
    """Return (scrubbed_text, replaced_anything)."""
    out = text
    replaced = False
    for pat, token in _PATTERNS:
        if pat.search(out):
            out = pat.sub(token, out)
            replaced = True
    return out, replaced


def scrub_card(card: dict) -> tuple[dict, bool]:
    """Scrub problem_shape / constraint / unlock / what_worked in place-ish.

    Returns (card, replaced_anything). The caller ORs replaced_anything into
    contains_pii and then applies the field limits / reject rule.
    """
    replaced = False
    for field in ("problem_shape", "constraint", "unlock"):
        if isinstance(card.get(field), str):
            card[field], r = scrub_text(card[field])
            replaced = replaced or r
    ww = card.get("what_worked") or []
    out_ww = []
    for item in ww:
        if isinstance(item, str):
            s, r = scrub_text(item)
            replaced = replaced or r
            out_ww.append(s)
    card["what_worked"] = out_ww
    return card, replaced
