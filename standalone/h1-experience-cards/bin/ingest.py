#!/usr/bin/env python3
"""ingest.py — normalize raw chats into the SPEC §3 dialogue schema.

SPEC §6.1 / RUN-PROTOCOL §2. Accepts either pack rows (chat_id/turns[].speaker)
or already-normalized dialogue records (dialogue_id/turns[].role). Ground-truth
keys (unlock, unlock_guideline, split) are dropped here — C-L2.

Usage:
  python bin/ingest.py --in chats.jsonl --out data/dialogues.jsonl \\
      [--config k=v ...] [--agent-pool-size N] [--timeline compressed|aged] \\
      [--t0 ISO] [--cursor-dir <dir containing cluster_cursor.json>]

Prints {kept, dropped, until_cluster}. Deterministic (C-IN6).
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib  # noqa: E402


def normalize_row(raw, index, cfg, agent_pool_size, timeline):
    """Pack row or dialogue record -> SPEC §3 dialogue (RUN-PROTOCOL §2)."""
    t0 = h1lib.parse_iso(cfg["t0"])
    if "dialogue_id" in raw:
        # Already-normalized dialogue record (fixtures). Pass through, but
        # strip any ground-truth keys defensively.
        d = {k: v for k, v in raw.items()
             if k not in ("unlock", "unlock_guideline", "split", "n_turns")}
        return d
    # --- pack row mapping ---
    chat_id = raw["chat_id"]
    dialogue_id = f"d-{chat_id}"
    tenant_id = f"abcd-{raw['tenant']}"
    # Timeline (RUN-PROTOCOL §2.3): compressed = t0 + (i mod 20) days,
    # aged = t0 - (i mod 61) days (0..60 days before t0).
    if timeline == "compressed":
        closed_at = h1lib.iso_add(cfg["t0"], days=index % 20)
    elif timeline == "aged":
        closed_at = h1lib.iso_add(cfg["t0"], days=-(index % 61))
    else:
        raise SystemExit(f"bad --timeline {timeline!r} (compressed|aged)")
    # Synthesized agent identity (RUN-PROTOCOL §2.2), deterministic from the
    # dialogue id alone.
    agent_id = "agent-" + chr(ord("a") + int(
        hashlib.sha256(dialogue_id.encode()).hexdigest(), 16) % agent_pool_size)
    turns = []
    for t in raw["turns"]:
        speaker = t.get("speaker")
        if speaker in ("agent", "customer"):
            role = speaker
        elif speaker == "action":
            role = "tool"
        else:
            role = "tool"  # unknown speaker: never lose the text
        turn = {"role": role, "text": t["text"]}
        if role == "tool":
            turn["name"] = "action" if speaker == "action" else "other"
        turns.append(turn)
    return {
        "dialogue_id": dialogue_id,
        "tenant_id": tenant_id,
        "vertical": raw["vertical"],
        "agent_id": agent_id,
        "channel": "web",
        "closed_at": closed_at,
        "turns": turns,
    }


def merge_by_key(existing, new_rows):
    """Stable upsert by dialogue_id: existing order preserved, new appended,
    later duplicates replace earlier in place. Idempotent (C-IN6)."""
    out, pos = [], {}
    for r in existing:
        pos[r["dialogue_id"]] = len(out)
        out.append(r)
    for r in new_rows:
        k = r["dialogue_id"]
        if k in pos:
            out[pos[k]] = r
        else:
            pos[k] = len(out)
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser(description="Normalize raw chats to the "
                                             "SPEC §3 dialogue schema")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--append", action="store_true",
                    help="merge into existing output by dialogue_id instead "
                         "of replacing (idempotent; chunked run support)")
    ap.add_argument("--delta-out", default=None,
                    help="write ONLY this run's kept dialogues here (the "
                         "extract input for incremental/chunked runs)")
    ap.add_argument("--config", action="append", default=[])
    ap.add_argument("--agent-pool-size", type=int, default=4)
    ap.add_argument("--timeline", default="compressed",
                    choices=["compressed", "aged"])
    ap.add_argument("--t0", default=None,
                    help="run timeline origin (overrides config t0)")
    ap.add_argument("--cursor-dir", default=None,
                    help="dir holding cluster_cursor.json (default: --out dir)")
    ap.add_argument("--cursor-file", default=None,
                    help="explicit cluster_cursor.json path (overrides "
                         "--cursor-dir)")
    args = ap.parse_args()

    cfg = h1lib.load_config(args.config)
    if args.t0:
        cfg["t0"] = args.t0

    rows = h1lib.read_jsonl(args.inp)
    # closed_at uses the GLOBAL dialogue position (RUN-PROTOCOL §2.3:
    # "ordering within the pool follows file order"), so chunked ingest
    # (--append) must continue the index, not restart it per chunk.
    start_idx = (len(h1lib.read_jsonl(args.out))
                 if args.append and os.path.exists(args.out) else 0)
    kept, dropped = [], 0
    for i, raw in enumerate(rows):
        try:
            d = normalize_row(raw, start_idx + i, cfg, args.agent_pool_size,
                              args.timeline)
        except KeyError as e:
            dropped += 1
            continue
        errs = h1lib.dialogue_ok(d)
        if errs:
            dropped += 1
            continue
        kept.append(d)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if args.append:
        existing = h1lib.read_jsonl(args.out) if os.path.exists(args.out) \
            else []
        merged = merge_by_key(existing, kept)
        h1lib.write_jsonl(args.out, merged)
        n_total = len(merged)
    else:
        h1lib.write_jsonl(args.out, kept)
        n_total = len(kept)
    if args.delta_out:
        h1lib.write_jsonl(args.delta_out, kept)

    # Cluster cursor (SPEC §6.1: print until_cluster)
    cursor_file = args.cursor_file or os.path.join(
        args.cursor_dir or out_dir, "cluster_cursor.json")
    last = 0
    if os.path.exists(cursor_file):
        try:
            last = json.load(open(cursor_file)).get("last_dialogue_count", 0)
        except Exception:
            last = 0
    n = n_total
    until_cluster = max(0, cfg["CLUSTER_EVERY_N_CHATS"] - (n - last))

    summary = {"kept": len(kept), "dropped": dropped, "until_cluster":
               until_cluster, "rows_in": len(rows)}
    h1lib.print_json(summary)


if __name__ == "__main__":
    main()
