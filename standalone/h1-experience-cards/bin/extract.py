#!/usr/bin/env python3
"""extract.py — one experience card per dialogue (the only LLM step).

    python bin/extract.py --in data/dialogues.jsonl --out data/cards.jsonl \\
        --model <extract model> --raw-dir raw/extract \\
        [--replay-dir <run>/raw/extract] [--now ISO] [--set k=v]

- Renders the transcript from PROMPTS.md §2 and calls call_llm (system from
  PROMPTS.md §1). Markdown fences are stripped before json.loads.
- Runs the SPEC §4 PII scrub on every string field and every what_worked
  item; contains_pii=true if the model said so OR the scrub replaced anything.
- Rejects ONLY per the post-scrub rule (SPEC §4): problem_shape empty, or
  (constraint=="none" AND unlock=="none" AND what_worked==[]). Rejected cards
  are written with status=rejected and kept (C-EX8).
- Upserts by card_id. A card that already belongs to a cluster (any state
  other than the fresh-extract shape) is SKIPPED, never overwritten
  (SPEC §6.2, C-EX9) — this is what keeps --replay byte-identical and the
  anti-echo invariant intact.
- Live mode writes raw/<dialogue_id>.json via call_llm's raw_path; replay
  mode reads them (zero network) and copies the record into the new raw dir.
- The model id comes from --model (NO default), the base URL from
  --base-url / env H1_BASE_URL, the key from --api-key / env H1_API_KEY.
  No model/endpoint/key literal lives in this file (D8 rule).
- Unparseable model JSON is a RECORDED RATE (C-EX11): counted in the summary,
  the raw response kept on disk, processing continues with the next dialogue.
  No crash, no silent retry.

Prints {extracted, rejected, skipped, unparseable, pii_flagged}.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import json
import os
import re
import sys

import config as cfg
import jsonio as hio
import llm
from common import (card_id_for, prompts_for, scrub_pii, now_iso)

_CARD_KEYS = ("card_id", "status", "role", "cluster_id", "votes", "members",
              "problem_shape", "constraint", "unlock", "what_worked",
              "contains_pii", "receipt", "served_to", "created_at",
              "updated_at")
_RECEIPT_KEYS = ("source_dialogue_id", "tenant_id", "vertical", "agent_id",
                 "closed_at", "last_closed_at", "scope")

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*$", re.MULTILINE)


def strip_fences(text):
    """Remove ```json / ``` markdown fences around a model response."""
    if "```" not in text:
        return text.strip()
    parts = _FENCE_RE.split(text)
    # parts alternate: outside, fence, inside, fence, outside...
    for part in parts:
        part = part.strip()
        if part:
            return part
    return text.strip()


def _norm_none(value):
    """Normalize the literal 'none' (any case/padding) to lowercase 'none'."""
    if isinstance(value, str) and value.strip().lower() == "none":
        return "none"
    return value


def _words(value):
    return len(str(value).split())


def parse_model_output(raw_text):
    """Strip fences and parse the model's JSON object.

    Returns (obj, error). obj has exactly the 5 extract keys, with
    constraint/unlock normalized to the literal 'none' when applicable.
    """
    text = strip_fences(raw_text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"json parse error: {exc}"
    if not isinstance(obj, dict):
        return None, "not a JSON object"
    required = ("problem_shape", "constraint", "unlock", "what_worked",
                "contains_pii")
    for key in required:
        if key not in obj:
            return None, f"missing key {key!r}"
    if not isinstance(obj["problem_shape"], str) or \
       not isinstance(obj["constraint"], str) or \
       not isinstance(obj["unlock"], str):
        return None, "problem_shape/constraint/unlock must be strings"
    if not isinstance(obj["what_worked"], list) or \
       not all(isinstance(x, str) for x in obj["what_worked"]):
        return None, "what_worked must be a list of strings"
    if not isinstance(obj["contains_pii"], bool):
        return None, "contains_pii must be a boolean"
    # Backstop the spec'd field limits (SPEC §4, C-EX3): the model was told
    # ≤12 words / 1-8 steps; truncation keeps the store schema-valid.
    obj["problem_shape"] = " ".join(obj["problem_shape"].split()[:cfg.DEFAULTS["MAX_WORDS_FIELD"]])
    obj["constraint"] = " ".join(obj["constraint"].split()[:cfg.DEFAULTS["MAX_WORDS_FIELD"]])
    obj["unlock"] = " ".join(obj["unlock"].split()[:cfg.DEFAULTS["MAX_WORDS_FIELD"]])
    obj["what_worked"] = obj["what_worked"][:cfg.DEFAULTS["MAX_WORKED"]]
    obj["constraint"] = _norm_none(obj["constraint"])
    obj["unlock"] = _norm_none(obj["unlock"])
    return obj, None


def render_transcript(dialogue):
    """Render turns as the PROMPTS.md §2 transcript block."""
    lines = []
    for turn in dialogue.get("turns", []):
        role = turn.get("role")
        text = turn.get("text", "")
        if role == "tool":
            name = turn.get("name")
            lines.append(f"tool {name}: {text}" if name else f"tool: {text}")
        else:
            lines.append(f"{role}: {text}")
    return "\n".join(lines)


def _is_fresh_extract_shape(card):
    """True iff the stored card is still the freshly-extracted shape.

    Anything else (merged member, clustered canonical, shared/stale canonical,
    served, voted) must not be overwritten by a re-extract (SPEC §6.2, C-EX9).
    """
    return (card.get("status") == "private"
            and card.get("role") == "canonical"
            and card.get("cluster_id") == card.get("card_id")
            and card.get("votes") == 1
            and not card.get("members")
            and not card.get("served_to"))


def extract_dialogue(dialogue, prompts, model, base_url, api_key,
                     raw_dir, replay_dir, pinned_now, cfg_obj, raw_path=None):
    """Extract one dialogue → card dict or None (unparseable/rejected/skipped).

    Returns (card_or_None, outcome) where outcome ∈
    {extracted, rejected, skipped, unparseable}.
    """
    dlg_id = dialogue["dialogue_id"]
    if raw_path is None:
        raw_path = os.path.join(raw_dir, f"{dlg_id}.json")
    system = prompts["extract_system"]
    user = prompts["extract_user"].format(
        tenant_id=dialogue["tenant_id"],
        vertical=dialogue["vertical"],
        channel=dialogue.get("channel", "web"),
        transcript=render_transcript(dialogue),
    )
    if replay_dir is not None:
        # read the stored record; copy it into this run's raw dir
        response = llm.copy_replay_record(replay_dir, raw_path)
    else:
        response = llm.call_llm(system, user, model=model,
                                base_url=base_url, api_key=api_key,
                                raw_path=raw_path)

    obj, err = parse_model_output(response)
    if err is not None:
        return None, "unparseable"

    card_id = card_id_for(dlg_id)

    scrubbed, replaced = scrub_pii(obj)
    contains_pii = bool(scrubbed.get("contains_pii")) or replaced

    problem_shape = scrubbed["problem_shape"].strip()
    constraint = scrubbed["constraint"]
    unlock = scrubbed["unlock"]
    what_worked = scrubbed["what_worked"]

    rejected = (not problem_shape) or (
        constraint == "none" and unlock == "none" and not what_worked)

    receipt = {
        "source_dialogue_id": dlg_id,
        "tenant_id": dialogue["tenant_id"],
        "vertical": dialogue["vertical"],
        "agent_id": dialogue.get("agent_id", "unknown"),
        # closed_at may be absent (SPEC §3); keys are always present so the
        # card schema is stable (null when missing; cluster skips nulls).
        "closed_at": dialogue.get("closed_at"),
        "last_closed_at": dialogue.get("closed_at"),
        "scope": f"{dialogue['tenant_id']}/{dialogue['vertical']}",
    }

    card = {
        "card_id": card_id,
        "status": "rejected" if rejected else "private",
        "role": "canonical",
        "cluster_id": card_id,
        "votes": 1,
        "members": [],
        "problem_shape": problem_shape,
        "constraint": constraint,
        "unlock": unlock,
        "what_worked": what_worked,
        "contains_pii": contains_pii,
        "receipt": receipt,
        "served_to": [],
        "created_at": pinned_now,
        "updated_at": pinned_now,
    }
    return card, ("rejected" if rejected else "extracted")


def run_extract(in_path, out_path, model, raw_dir, replay_dir=None,
                pinned_now=None, base_url=None, api_key=None,
                overrides=None, cards_path=None):
    """Core extract. Returns the {extracted, rejected, skipped, unparseable,
    pii_flagged} summary."""
    cfg_obj = cfg.Config(overrides)
    if pinned_now is None:
        pinned_now = now_iso()
    prompts = prompts_for(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "PROMPTS.md"))

    # In live mode, resolve the model/base-url/key ONCE (D8: flags/env only,
    # no literals). In replay mode no network happens and none are required.
    if replay_dir is None:
        model, base_url, api_key = llm.resolve_llm_params(model, base_url,
                                                          api_key)

    dialogues = hio.read_jsonl(in_path)

    # existing store (upsert by card_id)
    store = {}
    if cards_path is None:
        cards_path = out_path
    if os.path.exists(cards_path):
        for card in hio.read_jsonl(cards_path):
            store[card["card_id"]] = card

    extracted = rejected = skipped = unparseable = pii_flagged = 0
    for dialogue in dialogues:
        dlg_id = dialogue["dialogue_id"]
        raw_path = os.path.join(raw_dir, f"{dlg_id}.json")
        card_id = card_id_for(dlg_id)

        if card_id in store and not _is_fresh_extract_shape(store[card_id]):
            skipped += 1
            continue

        card, outcome = extract_dialogue(
            dialogue, prompts, model, base_url, api_key, raw_dir, replay_dir,
            pinned_now, cfg_obj, raw_path=raw_path)
        if outcome == "unparseable":
            unparseable += 1
            continue
        store[card_id] = card
        if outcome == "rejected":
            rejected += 1
        else:
            extracted += 1
        if card["contains_pii"]:
            pii_flagged += 1

    # write the whole store, deterministic order
    ordered = [store[k] for k in sorted(store)]
    hio.write_jsonl(cards_path, ordered, key_order=_CARD_KEYS)

    return {"extracted": extracted, "rejected": rejected, "skipped": skipped,
            "unparseable": unparseable, "pii_flagged": pii_flagged}


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="extract.py",
        description="Extract one experience card per dialogue (SPEC §4/§6.2).")
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--raw-dir", dest="raw_dir", required=True)
    ap.add_argument("--replay-dir", dest="replay_dir", default=None,
                    help="read stored raw records instead of calling the LLM")
    ap.add_argument("--now", default=None, help="pinned ISO timestamp")
    ap.add_argument("--base-url", default=None,
                    help="LLM base URL (default: env H1_BASE_URL; never "
                         "hard-coded)")
    ap.add_argument("--api-key", default=None,
                    help="LLM API key (default: env H1_API_KEY; never "
                         "printed, never stored)")
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    summary = run_extract(args.in_path, args.out_path, args.model,
                          args.raw_dir, args.replay_dir, args.now,
                          args.base_url, args.api_key,
                          cfg.parse_overrides(args.set))
    print(hio.dumps({k: summary[k] for k in
                     ("extracted", "rejected", "skipped", "unparseable",
                      "pii_flagged")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
