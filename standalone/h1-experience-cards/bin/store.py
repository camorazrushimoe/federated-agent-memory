"""JSONL store helpers — one writer, atomic writes, upsert by id.

SPEC §2: JSONL files only, assume a single writer, scripts MUST NOT run
concurrently against the same JSONL. Writes go to a temp file + rename so a
crash cannot leave a half-written store.

Strip rewiring (§3c): read/write IO is re-exported from canonical `jsonio`
(ONE implementation). `upsert_rows`/`upsert_cards` are the additive helpers,
plus `load_labels` (dialogue_id -> unlock_guideline, from an ORIGINAL
un-stripped pack file) used by audit.py and checks.py.
"""

from __future__ import annotations

from jsonio import read_jsonl, write_jsonl  # noqa: F401  (re-export)

__all__ = ["read_jsonl", "write_jsonl", "upsert_rows", "upsert_cards",
           "load_labels"]


def load_labels(path) -> dict[str, str]:
    """dialogue_id -> unlock_guideline, from an ORIGINAL (un-stripped) file.

    Keys follow the ingest mapping (RUN-PROTOCOL §2.1): a pack row's
    `chat_id` becomes `d-<chat_id>`; spec-shaped rows keep their own
    dialogue_id. Labels exist ONLY in the original pack files (C-L2).
    """
    out: dict[str, str] = {}
    for r in read_jsonl(path):
        g = r.get("unlock_guideline")
        if not g:
            continue
        did = r.get("dialogue_id") or f"d-{r.get('chat_id')}"
        out[str(did)] = g
    return out


def upsert_rows(rows: list[dict], new_rows: list[dict], key: str) -> list[dict]:
    """Merge new_rows into rows by `key`, preserving existing order.

    Existing rows keep their relative order; new keys are appended in input
    order. Deterministic, idempotent (re-running on the same input produces the
    same output — C-IN6).
    """
    idx = {r[key]: i for i, r in enumerate(rows)}
    out = list(rows)
    for r in new_rows:
        i = idx.get(r[key])
        if i is None:
            idx[r[key]] = len(out)
            out.append(r)
        else:
            out[i] = r
    return out


def upsert_cards(cards: list[dict], new_cards: list[dict]) -> list[dict]:
    """Upsert by card_id with the SPEC §6.2 re-extract rules applied by caller."""
    return upsert_rows(cards, new_cards, "card_id")
