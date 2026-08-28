#!/usr/bin/env python3
"""Map the copied H1 ABCD pack into SPEC §3 dialogues.

Not an H1 import. Reads JSONL, writes JSONL. No LLM.

  python bin/adapt_h1_corpus.py \
      --in data/abcd_1000_pool.jsonl data/abcd_200_holdout.jsonl \
      --out data/dialogues.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
ROLE = {"customer": "customer", "agent": "agent", "action": "tool"}


def adapt_row(raw: dict, index: int) -> dict:
    turns = []
    for t in raw.get("turns") or []:
        sp = t.get("speaker")
        role = ROLE.get(sp)
        if role is None:
            continue
        item = {"role": role, "text": t.get("text") or ""}
        if role == "tool":
            item["name"] = "action"
        turns.append(item)
    chat_id = raw.get("chat_id")
    return {
        "dialogue_id": f"d-{chat_id}",
        "tenant_id": raw.get("tenant") or "unknown",
        "vertical": raw.get("vertical") or "customer-support",
        "agent_id": "unknown",
        "channel": "web",
        "closed_at": (T0 + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "turns": turns,
        "source_chat_id": chat_id,
        "source_split": raw.get("split"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inputs", nargs="+", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = kept = dropped = 0
    with out.open("w") as w:
        for path in args.inputs:
            for line in Path(path).read_text().splitlines():
                if not line.strip():
                    continue
                n += 1
                row = adapt_row(json.loads(line), index=n)
                if not any(t["role"] == "customer" for t in row["turns"]):
                    dropped += 1
                    continue
                w.write(json.dumps(row, ensure_ascii=False) + "\n")
                kept += 1
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    summary = {
        "ok": True,
        "input_rows": n,
        "kept": kept,
        "dropped_no_customer": dropped,
        "out": str(out),
        "sha256": digest,
        "t0": T0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "closed_at_step_minutes": 1,
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
