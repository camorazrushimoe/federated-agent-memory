"""JSONL store helpers — one writer, atomic writes, upsert by id.

SPEC §2: JSONL files only, assume a single writer, scripts MUST NOT run
concurrently against the same JSONL. Writes go to a temp file + rename so a
crash cannot leave a half-written store.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


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
