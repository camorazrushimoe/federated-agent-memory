"""S1 — ingest.py: normalize raw chats into SPEC §3 dialogues.

- input:  --in raw.jsonl (fixtures/dialogues.jsonl or any SPEC-schema JSONL)
- output: data/dialogues.jsonl
- MUST drop chats without a customer turn (fixture d-006)
- MUST NOT call the LLM and MUST NOT set tags (C-IN6)
- idempotent: re-running on the same input rewrites the same bytes (C-IN5)

H1-pack raw files are NOT SPEC schema; run them through
bin/adapt_h1_corpus.py first (that is its job, not S1's).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

VALID_ROLES = {"customer", "agent", "tool"}


def normalize_dialogue(row: dict) -> dict | None:
    """Return a SPEC §3 dialogue, or None if it must be dropped.

    Unknown roles are dropped at S1 (PROMPTS.md §1); a chat left without a
    customer turn is dropped entirely (SPEC §3).
    """
    turns = []
    for turn in row.get("turns") or []:
        role = turn.get("role")
        if role not in VALID_ROLES:
            continue
        item = {"role": role, "text": turn.get("text") or ""}
        if role == "tool":
            item["name"] = turn.get("name") or ""
        turns.append(item)
    if not any(t["role"] == "customer" for t in turns):
        return None
    out = {
        "dialogue_id": str(row["dialogue_id"]),
        "vertical": str(row.get("vertical") or ""),
        "agent_id": str(row.get("agent_id") or "unknown"),
        "channel": str(row.get("channel") or ""),
        "closed_at": str(row.get("closed_at") or ""),
        "turns": turns,
    }
    if row.get("tenant_id") is not None:  # MAY stay as an H1-schema field
        out = {"dialogue_id": out["dialogue_id"],
               "tenant_id": str(row["tenant_id"]), **out}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="S1 ingest: normalize dialogues (SPEC §3)")
    ap.add_argument("--in", dest="inp", required=True, help="raw dialogues JSONL")
    ap.add_argument("--out", default="data/dialogues.jsonl")
    args = ap.parse_args()

    lines = Path(args.inp).read_text(encoding="utf-8").splitlines()
    lines = [ln for ln in lines if ln.strip()]
    kept, dropped = [], 0
    for ln in lines:
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            return common.fail(f"malformed JSON line in {args.inp}: {ln[:80]!r}")
        if not isinstance(row, dict) or "dialogue_id" not in row or "turns" not in row:
            return common.fail(f"row is not a SPEC §3 dialogue: {ln[:80]!r}")
        norm = normalize_dialogue(row)
        if norm is None:
            dropped += 1
            continue
        kept.append(norm)

    ids = [k["dialogue_id"] for k in kept]
    if len(set(ids)) != len(ids):  # C-IN4
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        return common.fail(f"duplicate dialogue_id in input: {dupes}")

    common.write_jsonl(args.out, kept)
    common.print_summary({
        "ok": True,
        "step": "S1",
        "script": "ingest.py",
        "input": args.inp,
        "input_rows": len(lines),
        "kept": len(kept),
        "dropped": dropped,
        "dropped_no_customer": dropped,
        "out": args.out,
        "out_rows": len(kept),
        "sha256": common.sha256_of(args.out),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
