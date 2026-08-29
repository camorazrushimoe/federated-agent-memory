"""S5 — mix.py: assemble the packet that goes to the agent.

- input:  --ranked data/ranked.jsonl --pool data/sessions.jsonl
- output: data/packet.json (packet_text + ids, C-MX5) + append to
          data/serves.jsonl (query_id/tag_key/ids, C-MX4)
- prompt: none. Packet text is the PROMPTS.md §5 template (C-MX2, C-PROMPT).
- whole turns only, no cards/summaries (C-MX1); blocks in rank order, each
  starting with [session_id]; <= MAX_PACKET sessions (C-SIZE)
- empty ranked -> a valid header-only packet (SPEC §7 S5)
- query_id/tag_key default to data/query_meta.json (lab plumbing written by
  retrieve.py), overridable via flags
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402
import prompts  # noqa: E402


def build_packet(ranked: list[dict], pool: list[dict]) -> tuple[str, list[str]]:
    pool_by_id = {s["session_id"]: s for s in pool}
    blocks = []
    ids = []
    for row in ranked:
        session = pool_by_id.get(row["session_id"], row)
        transcript = common.render_transcript(session.get("turns") or [])
        blocks.append(prompts.PACKET_SESSION_BLOCK.format(
            session_id=session["session_id"],
            tag_key=session.get("tag_key") or common.make_tag_key(session.get("tags") or {}),
            transcript=transcript))
        ids.append(session["session_id"])
    text = prompts.PACKET_HEADER
    if blocks:
        text = text + "\n\n" + "\n\n".join(blocks)
    return text, ids


def main() -> int:
    ap = argparse.ArgumentParser(description="S5 mix: build the hint packet (PROMPTS §5)")
    ap.add_argument("--ranked", default=config.DEFAULT_PATHS["ranked"])
    ap.add_argument("--pool", default=config.DEFAULT_PATHS["sessions"])
    ap.add_argument("--out", default=config.DEFAULT_PATHS["packet"])
    ap.add_argument("--serves", default=config.DEFAULT_PATHS["serves"])
    ap.add_argument("--meta", default=config.DEFAULT_PATHS["query_meta"])
    ap.add_argument("--query-id", default=None)
    ap.add_argument("--tag-key", default=None)
    args = ap.parse_args()

    ranked = common.read_jsonl(args.ranked)
    pool = common.read_jsonl(args.pool)

    query_id, tag_key = args.query_id, args.tag_key
    if not query_id or not tag_key:
        meta = common.read_json(args.meta)
        query_id = query_id or meta["query_id"]
        tag_key = tag_key or meta["tag_key"]

    if len(ranked) > config.MAX_PACKET:  # C-SIZE
        return common.fail(
            f"ranked has {len(ranked)} sessions, MAX_PACKET={config.MAX_PACKET}")

    packet_text, ids = build_packet(ranked, pool)
    packet = {
        "query_id": query_id,
        "tag_key": tag_key,
        "packet_session_ids": ids,
        "packet_text": packet_text,
    }
    common.write_json(args.out, packet)
    common.append_jsonl(args.serves, {
        "query_id": query_id,
        "tag_key": tag_key,
        "session_ids": ids,
    })
    common.print_summary({
        "ok": True,
        "step": "S5",
        "script": "mix.py",
        "query_id": query_id,
        "tag_key": tag_key,
        "ranked": len(ranked),
        "packet_session_ids": ids,
        "n_sessions": len(ids),
        "empty_packet": len(ids) == 0,
        "packet_chars": len(packet_text),
        "out": args.out,
        "serves": args.serves,
        "packet_sha256": common.sha256_of(args.out),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
