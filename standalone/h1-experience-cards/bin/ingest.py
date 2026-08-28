#!/usr/bin/env python3
"""ingest.py — normalize raw chats into the SPEC §3 dialogue schema.

    python bin/ingest.py --in chats.jsonl --out data/dialogues.jsonl \\
        [--timeline compressed|aged] [--agent-pool-size N] [--set k=v]

- Accepts BOTH the pack schema (chat_id/tenant/vertical/turns[].speaker) and
  the spec schema (dialogue_id/tenant_id/vertical/turns[].role); mapping of
  pack rows is exactly RUN-PROTOCOL §2.1.
- agent_id: synthesized deterministically per RUN-PROTOCOL §2.2 unless the
  record already carries one (fixtures).
- closed_at: kept verbatim if present; otherwise synthesized from the row
  index per RUN-PROTOCOL §2.3 (timeline compressed|aged, origin T0 from
  config).
- Rows with zero customer turns are rejected (SPEC §3) and counted as
  dropped. Nothing else is silently dropped (C-IN1).
- The output file ACCUMULATES: rows whose dialogue_id already exists in the
  output are skipped, so re-running ingest on the same input is byte-identical
  (C-IN6) while tick.py can keep feeding new chats into one store.

Prints {kept, dropped, until_cluster}. MUST NOT run cluster (SPEC §6.1).

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import json
import os
import sys
from datetime import timedelta

import config as cfg
import jsonio as hio
from common import dialogue_agent_id, parse_iso

# pack speaker -> spec role. The pack's "action" turns are system-side
# statements (e.g. "Account has been pulled up for Albert Sanders."); the
# spec allows role ∈ {customer, agent, tool} only, so they map to tool
# (no name). Text is preserved verbatim either way.
_SPEAKER_TO_ROLE = {"agent": "agent", "customer": "customer", "tool": "tool",
                    "action": "tool"}

_SPEC_KEYS = ("dialogue_id", "tenant_id", "vertical", "agent_id", "channel",
              "closed_at", "turns")
_DROP_KEYS = ("unlock", "unlock_guideline", "split", "n_turns")


def _turns_to_spec(turns):
    out = []
    for t in turns:
        if not isinstance(t, dict):
            continue
        role = t.get("role") or _SPEAKER_TO_ROLE.get(t.get("speaker"))
        if role not in ("customer", "agent", "tool"):
            continue
        row = {"role": role, "text": t.get("text", "")}
        if role == "tool" and t.get("name"):
            row["name"] = t["name"]
        out.append(row)
    return out


def map_row(row, index, n_rows, agent_pool_size, timeline):
    """Map one input row to the SPEC §3 record. Returns (record, dropped_reason).

    Pack rows are mapped per RUN-PROTOCOL §2.1; spec-schema rows pass through
    verbatim (fixtures carry agent_id/closed_at and they MUST be kept).
    """
    is_pack = "chat_id" in row and "tenant" in row and "turns" in row
    is_spec = "dialogue_id" in row and "tenant_id" in row and "turns" in row

    if is_spec:
        record = {
            "dialogue_id": row["dialogue_id"],
            "tenant_id": row["tenant_id"],
            "vertical": row.get("vertical", ""),
            "agent_id": row.get("agent_id", "unknown"),
            "channel": row.get("channel", "web"),
            "closed_at": row.get("closed_at"),   # kept verbatim (may be None)
            "turns": _turns_to_spec(row.get("turns", [])),
        }
    elif is_pack:
        record = {
            "dialogue_id": "d-" + str(row["chat_id"]),
            "tenant_id": "abcd-" + str(row["tenant"]),
            "vertical": row.get("vertical", ""),
            "agent_id": None,      # synthesized below unless present
            "channel": "web",
            "closed_at": None,     # synthesized below unless present
            "turns": _turns_to_spec(row.get("turns", [])),
        }
        if row.get("agent_id"):    # pack has none today; keep if ever added
            record["agent_id"] = row["agent_id"]
        if row.get("closed_at"):
            record["closed_at"] = row["closed_at"]
    else:
        return None, "unknown schema"

    # Reject rows with zero customer turns (SPEC §3).
    if not any(t["role"] == "customer" for t in record["turns"]):
        return record, "no customer turn"

    if record["agent_id"] is None:
        record["agent_id"] = dialogue_agent_id(record["dialogue_id"],
                                               agent_pool_size)

    if record["closed_at"] is None:
        t0 = parse_iso(cfg.DEFAULTS["T0"])
        if timeline == "compressed":
            days = index % 20
        elif timeline == "aged":
            days = round(index * 60 / max(1, n_rows - 1))
        else:
            raise ValueError(f"unknown timeline {timeline!r}")
        record["closed_at"] = (t0 + timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

    return record, None


def ingest_file(in_path, out_path, timeline="compressed", agent_pool_size=4,
                overrides=None):
    """Core ingest. Returns {'kept', 'dropped', 'until_cluster', 'out'}."""
    cfg_obj = cfg.Config(overrides)
    existing_rows = []
    existing_ids = set()
    if os.path.exists(out_path):
        existing_rows = hio.read_jsonl(out_path)
        for r in existing_rows:
            existing_ids.add(r.get("dialogue_id"))

    kept = 0
    dropped = 0
    written = list(existing_rows)   # accumulate: keep prior rows in file order
    with open(in_path, "r", encoding="utf-8") as fh:
        raw_rows = [json.loads(line) for line in fh if line.strip()]

    for index, row in enumerate(raw_rows):
        record, reason = map_row(row, index, len(raw_rows), agent_pool_size,
                                 timeline)
        if reason is not None:
            dropped += 1
            continue
        if record["dialogue_id"] in existing_ids:
            kept += 1          # already in the store; counted as kept (C-IN1)
            continue
        existing_ids.add(record["dialogue_id"])
        # SPEC §3 key order
        ordered = {k: record[k] for k in _SPEC_KEYS}
        written.append(ordered)
        kept += 1

    hio.write_jsonl(out_path, written, key_order=_SPEC_KEYS)

    # until_cluster: dialogues still needed before the global cursor fires.
    last = 0
    cursor_path = os.path.join(os.path.dirname(out_path) or ".",
                               "cluster_cursor.json")
    if os.path.exists(cursor_path):
        try:
            last = int(hio.read_json(cursor_path).get("last_dialogue_count", 0))
        except (ValueError, TypeError):
            last = 0
    new_total = len(existing_ids)   # store size after this ingest
    since_last = new_total - last
    until_cluster = max(0, cfg_obj.CLUSTER_EVERY_N_CHATS - since_last)

    return {"kept": kept, "dropped": dropped, "until_cluster": until_cluster,
            "out": out_path, "store_rows": new_total}


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="ingest.py",
        description="Normalize raw chats into the SPEC §3 dialogue schema.")
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--timeline", choices=cfg.TIMELINE_MODES,
                    default="compressed")
    ap.add_argument("--agent-pool-size", type=int, default=None,
                    help="override AGENT_POOL_SIZE (RUN-PROTOCOL §2.2)")
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    overrides = cfg.parse_overrides(args.set)
    if args.agent_pool_size is not None:
        overrides["AGENT_POOL_SIZE"] = args.agent_pool_size

    summary = ingest_file(args.in_path, args.out_path, args.timeline,
                          overrides.get("AGENT_POOL_SIZE", 4), overrides)
    print(hio.dumps({k: summary[k] for k in ("kept", "dropped",
                                             "until_cluster")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
