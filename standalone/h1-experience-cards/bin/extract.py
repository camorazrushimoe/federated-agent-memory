#!/usr/bin/env python3
"""extract.py — the only LLM step. One dialogue -> one card (SPEC §6.2).

    python bin/extract.py --in data/dialogues.jsonl --out data/cards.jsonl \
        [--raw-dir runs/.../raw/extract] [--replay]

Per dialogue:
1. render turns as customer:/agent:/tool {name}:/tool: lines (PROMPTS.md §2)
2. call_llm with the frozen extract prompts (PROMPTS.md §1/§2)
3. parse the JSON object (markdown fences stripped)
4. normalize fields + PII scrub (SPEC §4) — scrub replaces, never discards
5. reject ONLY per the post-scrub rule; otherwise write status=private,
   role=canonical, votes=1, members=[], cluster_id=card_id,
   receipt.last_closed_at = receipt.closed_at

Determinism / replay:
- card_id = "c-" + sha256(dialogue_id)[:12]
- with --replay, responses are read from raw/extract/<dialogue_id>.json and
  zero LLM calls are made (L0)
- upsert by card_id; rows already in a cluster (cluster_id != card_id, or
  status=merged) are skipped, not overwritten (C-EX9)
- created_at / updated_at come from the pinned run clock (byte-identical
  replay); each dialogue gets a +1s offset in ingestion order
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from clock import RunClock
from llm import call_llm, LLMError
from prompts import Prompts
from schema import (card_id_for, is_rejected, normalize_fields,
                    validate_card)
from scrub import scrub_card
from store import read_jsonl, write_jsonl

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*$", re.MULTILINE)


def parse_model_json(text: str) -> dict:
    """Strip markdown fences, then json.loads. Raises ValueError on failure."""
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    return json.loads(cleaned)


def render_transcript(dialogue: dict) -> str:
    lines = []
    for t in dialogue.get("turns", []):
        role = t.get("role")
        text = t.get("text", "")
        if role == "customer":
            lines.append(f"customer: {text}")
        elif role == "agent":
            lines.append(f"agent: {text}")
        else:  # tool
            name = t.get("name")
            if name:
                lines.append(f"tool {name}: {text}")
            else:
                lines.append(f"tool: {text}")
    return "\n".join(lines)


def build_card(dialogue: dict, model_json: dict, index: int,
               clock: RunClock, cfg: dict) -> dict | None:
    """Normalize + scrub + reject; returns a spec card or None if rejected."""
    # --- coercion of the model's JSON (documented normalization) ------------
    problem_shape = model_json.get("problem_shape")
    if not isinstance(problem_shape, str) or not problem_shape.strip():
        return None  # rejected: empty problem_shape
    card = {
        "problem_shape": problem_shape,
        "constraint": model_json.get("constraint") or "none",
        "unlock": model_json.get("unlock") or "none",
        "what_worked": model_json.get("what_worked") or [],
        "contains_pii": bool(model_json.get("contains_pii")),
    }
    card = normalize_fields(card)
    card, scrubbed = scrub_card(card)
    card["contains_pii"] = card["contains_pii"] or scrubbed
    if is_rejected(card):
        return None

    dialogue_id = dialogue["dialogue_id"]
    scope = f"{dialogue['tenant_id']}/{dialogue['vertical']}"
    now = clock.at(index)  # deterministic created_at/updated_at
    card_id = card_id_for(dialogue_id)
    return {
        "card_id": card_id,
        "status": "private",
        "role": "canonical",
        "cluster_id": card_id,
        "votes": 1,
        "members": [],
        "problem_shape": card["problem_shape"],
        "constraint": card["constraint"],
        "unlock": card["unlock"],
        "what_worked": card["what_worked"],
        "contains_pii": card["contains_pii"],
        "receipt": {
            "source_dialogue_id": dialogue_id,
            "tenant_id": dialogue["tenant_id"],
            "vertical": dialogue["vertical"],
            "agent_id": dialogue["agent_id"],
            "closed_at": dialogue["closed_at"],
            "last_closed_at": dialogue["closed_at"],
            "scope": scope,
        },
        "served_to": [],
        "created_at": now,
        "updated_at": now,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extract one card per dialogue (SPEC §6.2).")
    ap.add_argument("--in", dest="inp", required=True, help="dialogues.jsonl")
    ap.add_argument("--out", required=True, help="cards.jsonl (upsert by card_id)")
    ap.add_argument("--raw-dir", default=None, help="raw/extract directory for request/response records")
    ap.add_argument("--replay", action="store_true", help="read recorded responses instead of calling the LLM")
    ap.add_argument("--model", required=True, help="extract model id (no default: DELIVERABLE-PACKAGE §6)")
    ap.add_argument("--base-url", required=True, help="OpenAI-compatible base URL (no default)")
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--clock-start", default=None, help="pinned run clock ISO (default: now)")
    ap.add_argument("--start-index", type=int, default=0,
                    help="absolute index offset for created_at (chunked runs)")
    ap.add_argument("--force-extract", action="store_true",
                    help="re-extract existing standalone cards (default: only new dialogue ids)")
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "MAX_TOKENS": args.max_tokens or cfgmod.DEFAULTS["MAX_TOKENS"],
    })
    clock = RunClock(args.clock_start) if args.clock_start else RunClock(cfgmod.utcnow_iso())
    prompts = Prompts()
    dialogues = read_jsonl(args.inp)
    existing = read_jsonl(args.out)
    existing_by_id = {c["card_id"]: c for c in existing}

    accepted, rejected, unparseable, skipped = [], [], [], []
    extract_calls = 0
    t0 = time.time()
    for pos_in_file, d in enumerate(dialogues):
        index = args.start_index + pos_in_file
        card_id = card_id_for(d["dialogue_id"])
        prev = existing_by_id.get(card_id)
        if prev is not None:
            # Incremental semantics: a dialogue already extracted is skipped
            # (upsert by card_id, never append duplicates — SPEC §6.2).
            # Rows already in a cluster are NEVER re-extracted even with
            # --force-extract (re-extract must not wipe cluster membership).
            if (prev.get("cluster_id") != card_id
                    or prev.get("status") == "merged" or prev.get("members")):
                skipped.append(d["dialogue_id"])
                continue
            if not args.force_extract:
                skipped.append(d["dialogue_id"])
                continue
        transcript = render_transcript(d)
        user = prompts.extract_user_text(
            tenant_id=d["tenant_id"], vertical=d["vertical"],
            channel=d.get("channel", "web"), transcript=transcript)
        content, meta = call_llm(
            prompts.extract_system, user,
            model=args.model, base_url=args.base_url,
            temperature=cfg["TEMPERATURE"], max_tokens=cfg["MAX_TOKENS"],
            raw_dir=args.raw_dir, dialogue_id=d["dialogue_id"],
            replay=args.replay)
        extract_calls += 1
        try:
            model_json = parse_model_json(content)
            if not isinstance(model_json, dict):
                raise ValueError("model returned non-object JSON")
        except (ValueError, json.JSONDecodeError) as e:
            unparseable.append(d["dialogue_id"])
            print(f"WARN unparseable JSON for {d['dialogue_id']}: {e}", file=sys.stderr)
            continue
        card = build_card(d, model_json, index, clock, cfg)
        if card is None:
            rejected.append(d["dialogue_id"])
        else:
            errs = validate_card(card)
            if errs:
                raise RuntimeError(f"internal: produced invalid card for {d['dialogue_id']}: {errs}")
            accepted.append(card)

    out_cards = list(existing)
    pos = {c["card_id"]: i for i, c in enumerate(out_cards)}
    for card in accepted:
        i = pos.get(card["card_id"])
        if i is None:
            pos[card["card_id"]] = len(out_cards)
            out_cards.append(card)
        else:
            # preserve served_to (evidence history) and created_at on refresh
            old = out_cards[i]
            card["served_to"] = old.get("served_to", [])
            card["created_at"] = old.get("created_at", card["created_at"])
            out_cards[i] = card
    write_jsonl(args.out, out_cards)

    wall = time.time() - t0
    print(json.dumps({
        "extracted": extract_calls,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "unparseable": len(unparseable),
        "skipped_existing": len(skipped),
        "cards_total": len(out_cards),
        "wall_clock_s": round(wall, 3),
        "replay": args.replay,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
