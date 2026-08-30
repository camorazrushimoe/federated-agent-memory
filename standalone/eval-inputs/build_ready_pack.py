#!/usr/bin/env python3
"""Собрать готовый eval-пак: 320 пул + 60 query + gold.

Источники уже в репо, ничего скачивать не надо:
  standalone/h1-experience-cards/data/abcd_1000_pool.jsonl
  standalone/h1-experience-cards/data/abcd_200_holdout.jsonl
  standalone/h2-federated-scoped-memory/data/gold_useful.jsonl

Пишет сюда же, в standalone/eval-inputs/:
  dialogues_pool_320.jsonl
  dialogues_slice_60.jsonl
  gold_useful.jsonl
  queries_60.jsonl
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
H1 = ROOT / "standalone" / "h1-experience-cards" / "data"
H2 = ROOT / "standalone" / "h2-federated-scoped-memory" / "data"

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
SITE_UNLOCKS = {"slow_speed", "shopping_cart", "search_results"}
NEG_CORE = {
    "bad_price_competitor",
    "bad_price_yesterday",
    "refund_initiate",
    "promo_code_invalid",
    "promo_code_out_of_date",
}
NEG_MANAGE_FILL = 8


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n",
        encoding="utf-8",
    )


def dialogue_id(row: dict) -> str:
    return f"d-{row['chat_id']}"


def closed_at(index: int) -> str:
    return (T0 + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%SZ")


def slice_family(row: dict) -> str | None:
    unlock = row.get("unlock", "")
    if "_how_" in unlock:
        return "howto"
    if unlock in SITE_UNLOCKS:
        return "site"
    if unlock in NEG_CORE:
        return "negative"
    if unlock.startswith("manage_"):
        return "negative_manage"
    return None


def adapt(raw: dict, index: int) -> dict:
    turns = []
    for t in raw.get("turns") or []:
        role = {"customer": "customer", "agent": "agent", "action": "tool"}.get(
            t.get("speaker")
        )
        if role is None:
            continue
        item = {"role": role, "text": t.get("text") or ""}
        if role == "tool":
            item["name"] = "action"
        turns.append(item)
    return {
        "dialogue_id": f"d-{raw['chat_id']}",
        "tenant_id": raw.get("tenant") or "unknown",
        "vertical": raw.get("vertical") or "customer-support",
        "agent_id": "unknown",
        "channel": "web",
        "closed_at": closed_at(index),
        "turns": turns,
        "source_chat_id": raw.get("chat_id"),
        "source_split": raw.get("split"),
        "unlock": raw.get("unlock"),
    }


def main() -> int:
    pool_src = H1 / "abcd_1000_pool.jsonl"
    hold_src = H1 / "abcd_200_holdout.jsonl"
    gold_src = H2 / "gold_useful.jsonl"
    for p in (pool_src, hold_src, gold_src):
        if not p.exists():
            raise SystemExit(f"missing {p}")

    pool_rows = read_jsonl(pool_src)
    hold_rows = read_jsonl(hold_src)
    for i, row in enumerate(pool_rows, start=1):
        row["_index"] = i
    for i, row in enumerate(hold_rows, start=len(pool_rows) + 1):
        row["_index"] = i

    buckets = {"howto": [], "site": [], "negative": [], "negative_manage": []}
    for row in hold_rows:
        fam = slice_family(row)
        if fam:
            buckets[fam].append((dialogue_id(row), fam, row["unlock"]))
    for k in buckets:
        buckets[k].sort()
    slice_ = (
        buckets["howto"]
        + buckets["site"]
        + buckets["negative"]
        + buckets["negative_manage"][:NEG_MANAGE_FILL]
    )

    by_id = {dialogue_id(r): r for r in hold_rows}
    pool_ids: set[str] = set()
    for did, _, unlock in slice_:
        qclosed = closed_at(by_id[did]["_index"])
        for row in pool_rows:
            if row.get("unlock") != unlock:
                continue
            if closed_at(row["_index"]) >= qclosed:
                continue
            pool_ids.add(dialogue_id(row))

    pool_out = [
        adapt(row, row["_index"])
        for row in pool_rows
        if dialogue_id(row) in pool_ids
    ]
    pool_out.sort(key=lambda d: d["dialogue_id"])
    slice_out = [adapt(by_id[did], by_id[did]["_index"]) for did, _, _ in slice_]
    slice_out.sort(key=lambda d: (d["closed_at"], d["dialogue_id"]))

    write_jsonl(HERE / "dialogues_pool_320.jsonl", pool_out)
    write_jsonl(HERE / "dialogues_slice_60.jsonl", slice_out)
    shutil.copyfile(gold_src, HERE / "gold_useful.jsonl")
    write_jsonl(HERE / "queries_60.jsonl", slice_out)

    print(
        json.dumps(
            {
                "ok": True,
                "pool": len(pool_out),
                "slice": len(slice_out),
                "gold": "copied",
                "unlocks_in_pool": len({r["unlock"] for r in pool_out}),
                "out": str(HERE),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
