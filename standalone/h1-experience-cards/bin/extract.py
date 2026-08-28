#!/usr/bin/env python3
"""extract.py — extract one experience card per dialogue (SPEC §6.2).

Usage:
  python bin/extract.py --in data/dialogues.jsonl --out data/cards.jsonl \
      --raw-dir raw/extract [--model <model>] [--at ISO]
  python bin/extract.py ... --replay-dir raw/extract   # zero LLM calls

Deterministic given the same model output: card_id = c- + sha256(dialogue_id)
[:12]; re-extract upserts by card_id; cards already merged/joined to a
cluster are skipped, never overwritten (C-EX9).

Print JSON {extracted, skipped, rejected, unparseable, calls, cards}.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402


def record_raw(raw_dir, dialogue_id, rec):
    os.makedirs(raw_dir, exist_ok=True)
    with open(os.path.join(raw_dir, f"{dialogue_id}.json"), "w",
              encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description="Extract cards (SPEC §6.2)")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", required=True,
                    help="model id — REQUIRED, there is no default in bin/ "
                         "(DELIVERABLE-PACKAGE.md §6)")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--at", default=None, help="deterministic run timestamp")
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("--replay-dir", default=None,
                    help="replay recorded raw/extract responses, no LLM")
    ap.add_argument("--prompts", default=H.PROMPTS_PATH)
    ap.add_argument("--config", action="append", default=[])
    ap.add_argument("--re-extract-all", action="store_true",
                    help="re-extract existing non-clustered cards too "
                         "(default: same — existing clustered cards are "
                         "always skipped)")
    args = ap.parse_args()

    cfg = H.load_config(args.config)
    prompts = H.load_prompts(args.prompts)
    at = args.at or H.now_iso(cfg)

    dialogues = H.read_jsonl(args.inp)
    existing = {c["card_id"]: c for c in H.read_jsonl(args.out)}
    raw_dir = args.raw_dir or (os.path.join(os.path.dirname(
        os.path.abspath(args.out)), "raw", "extract"))

    replay = {}
    if args.replay_dir:
        if not os.path.isdir(args.replay_dir):
            raise SystemExit(f"replay dir missing: {args.replay_dir}")
        for fn in sorted(os.listdir(args.replay_dir)):
            if fn.endswith(".json"):
                replay[fn[:-5]] = H.load_json(os.path.join(args.replay_dir,
                                                           fn))

    extracted = skipped = rejected = unparseable = calls = 0
    cards_out = []
    for d in dialogues:
        did = d["dialogue_id"]
        cid = H.card_id_of(did)
        prev = existing.get(cid)
        # C-EX9: a card that already belongs to a cluster is never overwritten
        if prev and (prev.get("status") == "merged"
                     or prev.get("cluster_id") != cid):
            skipped += 1
            cards_out.append(prev)
            continue
        # build the fresh card scaffold; content fields come from the model
        card = H.fresh_card(d, at)
        transcript = H.render_transcript(d)
        user_prompt = prompts["extract_user"].format(
            tenant_id=d["tenant_id"], vertical=d["vertical"],
            channel=d["channel"], transcript=transcript)
        system_prompt = prompts["extract_system"]
        assert user_prompt is not None and system_prompt is not None

        if did in replay:
            rec = replay[did]
            content = rec.get("response_text", "")
            usage = rec.get("usage") or {}
            ms = rec.get("ms", 0)
            finish = rec.get("finish_reason")
            error = rec.get("error")
        else:
            calls += 1
            try:
                t0 = time.monotonic()
                content, usage, ms, finish = H.call_llm(
                    system_prompt, user_prompt, model=args.model,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens, base_url=args.base_url,
                    api_key=args.api_key)
                ms = int((time.monotonic() - t0) * 1000)
                error = None
            except H.LlmFatal:
                raise
            except H.LlmError as e:
                # unparseable-call row: recorded, card not written
                unparseable += 1
                rec = {"dialogue_id": did, "model": args.model,
                       "request": {"system": system_prompt,
                                   "user": user_prompt,
                                   "temperature": args.temperature,
                                   "max_tokens": args.max_tokens},
                       "response_text": "", "parsed": False, "usage": {},
                       "ms": 0, "finish_reason": None, "error": str(e)}
                if raw_dir:
                    record_raw(raw_dir, did, rec)
                continue

        obj, perr = H.parse_model_json(content)
        rec = {"dialogue_id": did, "model": args.model,
               "request": {"system": system_prompt, "user": user_prompt,
                           "temperature": args.temperature,
                           "max_tokens": args.max_tokens},
               "response_text": content, "parsed": perr is None,
               "usage": usage, "ms": ms, "finish_reason": finish,
               "error": perr}
        if raw_dir:
            record_raw(raw_dir, did, rec)

        if obj is None:
            unparseable += 1
            continue
        if not isinstance(obj, dict):
            unparseable += 1
            continue

        card["problem_shape"] = str(obj.get("problem_shape", "")).strip()
        card["constraint"] = str(obj.get("constraint", "none")).strip()
        card["unlock"] = str(obj.get("unlock", "none")).strip()
        ww = obj.get("what_worked") or []
        card["what_worked"] = [str(x).strip() for x in ww]
        card["contains_pii"] = bool(obj.get("contains_pii", False))
        H.scrub_card_fields(card)
        if H.card_is_rejected(card):
            card["status"] = "rejected"
            rejected += 1
        else:
            extracted += 1
        errs = H.validate_card(card, fresh=card["status"] != "rejected")
        if errs:
            raise SystemExit(
                f"extract: internal card build failed for {did}: {errs}")
        cards_out.append(card)

    H.write_jsonl(args.out, cards_out, mode="w")
    H.print_json({"extracted": extracted, "skipped": skipped,
                  "rejected": rejected, "unparseable": unparseable,
                  "calls": calls, "cards": len(cards_out)})


if __name__ == "__main__":
    main()
