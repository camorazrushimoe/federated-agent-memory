#!/usr/bin/env python3
"""ingest.py — normalize raw chats into the SPEC §3 dialogue schema.

    python bin/ingest.py --in chats.jsonl --out data/dialogues.jsonl

Mapping (RUN-PROTOCOL §2): pack records (chat_id/tenant/vertical/turns) become
spec records (dialogue_id/tenant_id/vertical/agent_id/channel/closed_at/turns).
Ground truth keys (unlock, unlock_guideline, split, n_turns) are DROPPED here
and never reach extract.py (C-L2, EVAL-PLAN §1).

Two gaps in the pack are handled deterministically:
- agent_id  : synthesized  agent-<a..> from sha256(dialogue_id) % AGENT_POOL_SIZE
              (RUN-PROTOCOL §2.2). Explicit agent_id in a spec-format record is
              kept verbatim (fixtures use this).
- closed_at : synthesized from the `--timeline` (compressed|aged) over file
              order (RUN-PROTOCOL §2.3). Explicit closed_at is kept verbatim.
- action turns: the pack's `action` speaker turns are system/tool events;
              mapped to role=tool so no turn text is lost (C-IN5). Disclosed in
              the report; the protocol's §2.1 table omits them.

Records with fewer than one customer turn are dropped (SPEC §3).

Output is an UPSERT by dialogue_id against the existing out file, so feeding
the pool in 100-chat chunks (the runner) never duplicates rows and re-running
on the same input is byte-identical (C-IN6). Prints {kept, dropped,
until_cluster} to stdout.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from clock import RunClock
from store import read_jsonl, upsert_rows, write_jsonl

VALID_ROLES = ("customer", "agent", "tool")


def synthesize_agent(dialogue_id: str, pool_size: int) -> str:
    h = int(hashlib.sha256(dialogue_id.encode("utf-8")).hexdigest(), 16)
    return "agent-" + chr(ord("a") + h % pool_size)


def closed_at_for(timeline: str, t0_iso: str, index: int) -> str:
    from config import parse_iso, iso
    t0 = parse_iso(t0_iso)
    if timeline == "compressed":
        days = index % 20
    elif timeline == "aged":
        days = index % 61  # 0..60 days
    else:
        raise ValueError(f"unknown timeline: {timeline}")
    return iso(t0 + datetime.timedelta(days=days))


def normalize_record(rec: dict, index: int, cfg: dict) -> dict | None:
    """One raw record -> one spec dialogue, or None if it must be dropped."""
    turns = rec.get("turns") or []
    n_customer = sum(1 for t in turns if t.get("speaker") == "customer"
                     or t.get("role") == "customer")
    if n_customer < 1:
        return None  # SPEC §3: fewer than one customer turn -> reject before extraction

    if "chat_id" in rec:
        # pack format (data/README.md)
        dialogue_id = f"d-{rec['chat_id']}"
        tenant_id = f"abcd-{rec['tenant']}"
        vertical = rec["vertical"]
        channel = "web"
    else:
        dialogue_id = rec["dialogue_id"]
        tenant_id = rec["tenant_id"]
        vertical = rec["vertical"]
        channel = rec.get("channel", "web")

    agent_id = rec.get("agent_id")
    if not agent_id:
        agent_id = synthesize_agent(dialogue_id, cfg["AGENT_POOL_SIZE"])

    closed_at = rec.get("closed_at")
    if not closed_at:
        closed_at = closed_at_for(cfg["TIMELINE"], cfg["T0"], index)

    out_turns = []
    for t in turns:
        speaker = t.get("speaker") or t.get("role")
        text = t.get("text", "")
        if speaker == "action":
            # pack system/tool event -> SPEC tool turn (disclosed mapping)
            role = "tool"
            name = None
        elif speaker in ("customer", "agent"):
            role = speaker
            name = None
        elif speaker == "tool":
            role = "tool"
            name = t.get("name")
        else:
            # unknown speaker role: keep as tool (never customer/agent unless named)
            role = "tool"
            name = t.get("name")
        entry = {"role": role, "text": text}
        if name:
            entry["name"] = name
        out_turns.append(entry)

    return {
        "dialogue_id": dialogue_id,
        "tenant_id": tenant_id,
        "vertical": vertical,
        "agent_id": agent_id,
        "channel": channel,
        "closed_at": closed_at,
        "turns": out_turns,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Normalize raw chats into SPEC §3 dialogues.")
    ap.add_argument("--in", dest="inp", required=True, help="input chats.jsonl (pack or spec format)")
    ap.add_argument("--out", required=True, help="output dialogues.jsonl")
    ap.add_argument("--agent-pool-size", type=int, default=None, help="AGENT_POOL_SIZE (default from config)")
    ap.add_argument("--timeline", choices=("compressed", "aged"), default=None)
    ap.add_argument("--t0", default=None, help="ISO T0 for closed_at synthesis")
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "AGENT_POOL_SIZE": args.agent_pool_size or cfgmod.DEFAULTS["AGENT_POOL_SIZE"],
        "TIMELINE": args.timeline or cfgmod.DEFAULTS["TIMELINE"],
        "T0": args.t0 or cfgmod.DEFAULTS["T0"],
    })

    raw = read_jsonl(args.inp)
    normalized = []
    dropped = 0
    for i, rec in enumerate(raw):
        d = normalize_record(rec, i, cfg)
        if d is None:
            dropped += 1
        else:
            normalized.append(d)

    existing = read_jsonl(args.out)
    merged = upsert_rows(existing, normalized, "dialogue_id")
    write_jsonl(args.out, merged)

    # until_cluster: dialogues remaining until the next cluster pass
    cursor_path = Path(args.out).parent / "cluster_cursor.json"
    last = 0
    if cursor_path.exists():
        last = json.loads(cursor_path.read_text()).get("last_dialogue_count", 0)
    new_since = len(merged) - last
    remaining = max(0, cfg["CLUSTER_EVERY_N_CHATS"] - new_since)

    print(json.dumps({"kept": len(normalized), "dropped": dropped,
                      "until_cluster": remaining}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
