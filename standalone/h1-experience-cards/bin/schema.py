"""Card schema (SPEC.md §4) — validation, field-limit normalization, ids.

The model returns raw JSON; extract.py normalizes it into a spec card. This
module owns:

- card_id derivation: "c-" + first 12 hex of sha256(dialogue_id)
- field limits: problem_shape <=12 words; constraint/unlock <=12 words or the
  literal "none"; what_worked 1-8 items (deterministic truncation)
- full §4 validation (used by extract at write time and by check C-EX1)
"""

from __future__ import annotations

import json

# card_id_for / card_text live in canonical common.py (ONE implementation,
# strip plan §3c). schema.py re-exports them and keeps the validation that is
# its own.
from common import card_id_for, card_text

STATUSES = ("private", "shared", "merged", "stale", "rejected")
ROLES = ("canonical", "member")
WORD_LIMIT = 12
MAX_WORKED = 8


def word_count(s: str) -> int:
    return len(s.split()) if s.strip() else 0


def truncate_words(s: str, limit: int = WORD_LIMIT) -> str:
    words = s.split()
    if len(words) <= limit:
        return s
    return " ".join(words[:limit])


def normalize_fields(card: dict) -> dict:
    """Deterministic post-processing of the model's raw JSON (SPEC §4 rules).

    - problem_shape: lowercase, <=12 words, non-empty else reject (caller)
    - constraint / unlock: lowercase, <=12 words, or exactly "none"
    - what_worked: non-empty strings only, deduped, first-seen order, cap 8
    """
    def norm(s):
        if not isinstance(s, str):
            return ""
        s = " ".join(s.lower().split())
        return s

    card["problem_shape"] = truncate_words(norm(card.get("problem_shape", "")))
    for f in ("constraint", "unlock"):
        v = norm(card.get(f, ""))
        card[f] = "none" if v in ("", "none") else truncate_words(v)
    ww = []
    seen = set()
    for item in (card.get("what_worked") or []):
        if not isinstance(item, str):
            continue
        item = " ".join(item.lower().split())
        if item and item not in seen:
            seen.add(item)
            ww.append(item)
    card["what_worked"] = ww[:MAX_WORKED]
    card["contains_pii"] = bool(card.get("contains_pii"))
    return card


def is_rejected(card: dict) -> bool:
    """SPEC §4 reject rule, applied AFTER scrub+normalization.

    Rejected only when: problem_shape is empty, OR (constraint == none AND
    unlock == none AND what_worked empty). contains_pii is never a reject
    reason.
    """
    if not card.get("problem_shape"):
        return True
    if (card.get("constraint") == "none" and card.get("unlock") == "none"
            and not card.get("what_worked")):
        return True
    return False


def validate_card(card: dict) -> list[str]:
    """Full §4 schema validation; returns a list of violation strings ([] = ok)."""
    errs = []
    for k in ("card_id", "status", "role", "cluster_id", "problem_shape",
              "constraint", "unlock"):
        if not isinstance(card.get(k), str) or not card[k]:
            errs.append(f"missing/empty string field: {k}")
    if card.get("status") not in STATUSES:
        errs.append(f"status not in {STATUSES}: {card.get('status')!r}")
    if card.get("role") not in ROLES:
        errs.append(f"role not in {ROLES}: {card.get('role')!r}")
    if not isinstance(card.get("votes"), int) or card["votes"] < 0:
        errs.append(f"votes not a non-negative int: {card.get('votes')!r}")
    if not isinstance(card.get("members"), list):
        errs.append("members not a list")
    if not isinstance(card.get("served_to"), list):
        errs.append("served_to not a list")
    for st in card.get("served_to", []):
        if not (isinstance(st, dict) and "dialogue_id" in st and "at" in st):
            errs.append(f"served_to entry malformed: {st!r}")
    rec = card.get("receipt")
    if not isinstance(rec, dict):
        errs.append("receipt missing")
    else:
        for k in ("source_dialogue_id", "tenant_id", "vertical", "agent_id",
                  "closed_at", "last_closed_at", "scope"):
            if not isinstance(rec.get(k), str):
                errs.append(f"receipt.{k} missing/not string")
        if rec.get("scope") != f"{rec.get('tenant_id')}/{rec.get('vertical')}":
            errs.append(f"receipt.scope inconsistent: {rec.get('scope')!r}")
    if word_count(card.get("problem_shape", "")) > WORD_LIMIT:
        errs.append("problem_shape >12 words")
    for f in ("constraint", "unlock"):
        v = card.get(f, "")
        if v != "none" and word_count(v) > WORD_LIMIT:
            errs.append(f"{f} >12 words")
    ww = card.get("what_worked", [])
    if not (1 <= len(ww) <= MAX_WORKED):
        errs.append(f"what_worked has {len(ww)} items (must be 1-8)")
    for item in ww:
        if not isinstance(item, str) or not item.strip():
            errs.append(f"what_worked item not a non-empty string: {item!r}")
    if not isinstance(card.get("contains_pii"), bool):
        errs.append("contains_pii not bool")
    if not isinstance(card.get("created_at"), str) or not isinstance(card.get("updated_at"), str):
        errs.append("created_at/updated_at missing")
    return errs


def card_to_line(card: dict) -> str:
    return json.dumps(card, sort_keys=False, ensure_ascii=False)
