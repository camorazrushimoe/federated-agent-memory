#!/usr/bin/env python3
"""D0 gold-useful labeler for H2 (founder decision, issue #51).

Produces data/gold_useful.jsonl on the DATA-AUDIT slice, AGENT-LABELED with
deepseek-v4-pro — NOT human gold. Every artifact and report line carries:

    agent-labeled (deepseek-v4-pro), not human gold

Task (per founder decision #51):
  For each query dialogue on the audit slice, read the transcripts of the
  candidate past sessions and judge whether a candidate carries a
  TRANSFERABLE MOVE (procedure, workaround, step sequence) that the query's
  short label does not contain. Never derive the useful list from
  unlock / unlock_guideline (that would re-measure H1 and void the H2
  finding). An empty useful list is a valid answer (dispute/refund/promo
  transcripts are mostly identifiers + one-time exceptions; the rule, not
  the dialogue, is what transfers).

Candidate scope (retrieval hypothesis, DATA-AUDIT §6):
  pool sessions with the same raw unlock as the query and closed_at strictly
  earlier than the query's (C-FUTURE). unlock / unlock_guideline are used
  ONLY to build this candidate scope; they are never passed to the model and
  never appear in the prompt, the output rows, or the notes. The judgment is
  transcript-only.

Slice (DATA-AUDIT §6): hold-out FAQ how-to + site-troubleshoot + 20
negative dispute/promo.
  - how-to:   hold-out unlock containing "_how_"            (34 dialogues)
  - site:     hold-out unlock in {slow_speed, shopping_cart,
               search_results}                               (6 dialogues)
  - negative: exactly 20 = all core dispute/promo (bad_price_competitor,
               bad_price_yesterday, refund_initiate, promo_code_invalid,
               promo_code_out_of_date) + 8 manage_* (first 8 by dialogue_id).
               The audit text says "20 отрицательных"; the exact manage_*
               subset is a deterministic choice documented in the manifest —
               flag to the lead for sign-off at Phase B.

Output format: seed format (data/gold_useful.seed.jsonl) plus a "labeler"
field on every row (founder decision #51 requires every artifact to carry
the provenance marker).

LLM access: via bin/llm.py call_llm (reused from H1 per founder decision
#51), model pinned to --model deepseek-v4-pro (founder decision; still a
flag so a swap is not an edit), temperature 0, thinking disabled. Key /
base_url are resolved from flags -> H2_* env -> factory config.yaml (H1_*
env is NOT read, per the H2 brief) — same key / base_url, no new secret.

Usage:
  python bin/label_gold_useful.py \
      --pool data/abcd_1000_pool.jsonl \
      --holdout data/abcd_200_holdout.jsonl \
      --out data/gold_useful.jsonl \
      --manifest data/gold_useful.manifest.json \
      --raw-dir data/raw_gold_useful \
      --model deepseek-v4-pro \
      --dry-run          # build slice + candidates only, no LLM
      --limit N          # label only the first N slice queries (dev)
      --self-test        # synthetic raw-schema pack, never the hold-out
      --replay-dir DIR   # read raw records instead of calling the LLM
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The factory call_llm wrapper lives next to this script (bin/llm.py),
# reused per founder decision #51. Plain import: script dir is on sys.path.
try:
    from llm import LLMError, USAGE, call_llm
except ImportError:  # pragma: no cover - invoked as a module from repo root
    from bin.llm import LLMError, USAGE, call_llm  # type: ignore

LABELER = "agent-labeled (deepseek-v4-pro), not human gold"
MODEL_DEFAULT = "deepseek-v4-pro"  # founder decision #51; overridable via --model
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)  # same synthetic clock as adapt_h1_corpus.py

ROLE = {"customer": "customer", "agent": "agent", "action": "tool"}
SITE_UNLOCKS = {"slow_speed", "shopping_cart", "search_results"}
NEG_CORE_UNLOCKS = {
    "bad_price_competitor", "bad_price_yesterday", "refund_initiate",
    "promo_code_invalid", "promo_code_out_of_date",
}
NEG_TOTAL = 20  # DATA-AUDIT §6: "20 отрицательных dispute/promo"
# core dialogue count on the hold-out: bad_price_competitor 3 + bad_price_yesterday 3
# + refund_initiate 2 + promo_code_invalid 2 + promo_code_out_of_date 2 = 12
NEG_CORE_DIALOGUES = 12
NEG_MANAGE_FILL = NEG_TOTAL - NEG_CORE_DIALOGUES  # 8 manage_* to reach 20

# --------------------------------------------------------------------------
# D0 gold-useful labeling prompt (frozen here; sha256 recorded in manifest).
# This is NOT the S2 tag prompt (PROMPTS.md §2–§3 are pipeline-frozen); this
# is the D0 measurement prompt commissioned by founder decision #51.
# --------------------------------------------------------------------------
SYSTEM_PROMPT = """You are labeling which PAST customer-support chats would be a useful hint for a NEW chat.

Context: an experiment gives an agent the WHOLE transcript of similar past chats as hints. A past chat is a USEFUL hint only when it contains a concrete TRANSFERABLE MOVE — a procedure, workaround, or step sequence — that the new chat could reuse, and that the new chat's short problem label does not already contain. The label names the problem; it does not contain the how-to.

For the given new chat (QUERY) and the list of PAST chats (CANDIDATES), decide for EACH candidate whether it is useful.

What counts as a transferable move (positive examples):
- A multi-step cleaning procedure for "paint stain on boots" (brush -> flake -> soapy water -> scrape -> nail polish remover): the move is the steps, not the topic name.
- "Close extra tabs, log out and back in, report the slowness" for a "site is slow" query: the move is the step sequence.
- "Refresh the cart, then log out and log back in" for a "cart not updating" query: the move is the sequence, not the fact that both chats are about carts.

What does NOT count (negative examples):
- A candidate that shares the topic or guideline name but shows a DIFFERENT procedure (e.g., a boot-width chat for a paint-stain query, or an ISP-diagnosis chat for a site-slowness query): wrong hint.
- A candidate whose only content is identifiers (names, account/order ids, card numbers), one-time promo codes, and one-off exceptions: the rule transfers, not the chat. Do NOT include these.
- A candidate that only restates the problem or refuses with policy, with no reusable step sequence.

Rules:
- Useful = the candidate transcript shows a specific, reusable step sequence that fits the query's problem and is not visible in the query itself. Short but concrete sequences count.
- Do NOT mark a candidate useful just because it looks similar or because its label matches.
- Empty list is valid and often correct (especially for chats whose content is identifiers and one-time exceptions).

Return ONLY a JSON object, no markdown, no commentary:
{"useful_dialogue_ids": ["d-xxx", ...], "notes": "<=40 words: the transferable move(s), or why the list is empty"}"""

USER_PROMPT_TEMPLATE = """QUERY {query_id}:
{query_transcript}

CANDIDATES (past chats):
{candidates}

Return ONLY the JSON object with useful_dialogue_ids (subset of the candidate ids above, or []) and notes (<=40 words)."""


# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------

def load_raw(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def dialogue_id(row):
    return f"d-{row['chat_id']}"


def synthetic_closed_at(index):
    """Same clock as bin/adapt_h1_corpus.py: T0 + index minutes."""
    return (T0 + timedelta(minutes=index)).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_transcript(row):
    """PROMPTS.md §1 render: one line per turn, customer:/agent:/tool {name}:."""
    lines = []
    for t in row.get("turns") or []:
        sp = t.get("speaker")
        if sp not in ROLE:
            continue
        text = (t.get("text") or "").strip()
        if sp == "action":
            lines.append(f"tool action: {text}")
        else:
            lines.append(f"{sp}: {text}")
    return "\n".join(lines)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Slice + candidates
# --------------------------------------------------------------------------

def slice_family(row):
    unlock = row.get("unlock", "")
    if "_how_" in unlock:
        return "howto"
    if unlock in SITE_UNLOCKS:
        return "site"
    if unlock in NEG_CORE_UNLOCKS:
        return "negative"
    if unlock.startswith("manage_"):
        return "negative_manage"
    return None


def build_slice(holdout_rows):
    """Deterministic slice per DATA-AUDIT §6. Returns list of
    (dialogue_id, family, unlock) sorted by dialogue_id within family."""
    howto, site, neg, neg_manage = [], [], [], []
    for row in holdout_rows:
        fam = slice_family(row)
        did = dialogue_id(row)
        if fam == "howto":
            howto.append((did, fam, row["unlock"]))
        elif fam == "site":
            site.append((did, fam, row["unlock"]))
        elif fam == "negative":
            neg.append((did, fam, row["unlock"]))
        elif fam == "negative_manage":
            neg_manage.append((did, fam, row["unlock"]))
    howto.sort(); site.sort(); neg.sort(); neg_manage.sort()
    # exactly NEG_TOTAL negatives: all core + first NEG_MANAGE_FILL manage_*
    negatives = neg + neg_manage[:NEG_MANAGE_FILL]
    return howto + site + negatives  # family blocks, deterministic order


def build_candidates(pool_rows, query_unlock, query_closed_at):
    """Pool sessions with the same raw unlock, strictly earlier (C-FUTURE)."""
    out = []
    for row in pool_rows:
        if row.get("unlock") != query_unlock:
            continue
        # pool rows are always earlier than hold-out queries on the synthetic
        # clock (pool file first); still enforce C-FUTURE explicitly.
        if synthetic_closed_at(row["_index"]) >= query_closed_at:
            continue
        out.append(row)
    out.sort(key=lambda r: dialogue_id(r))
    return out


# --------------------------------------------------------------------------
# Labeling
# --------------------------------------------------------------------------

def parse_label(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    obj = json.loads(text)
    ids = obj.get("useful_dialogue_ids") or []
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError("useful_dialogue_ids must be a list of strings")
    notes = str(obj.get("notes") or "")
    return {"useful_dialogue_ids": ids, "notes": notes}


def validate_ids(ids, candidate_ids, query_id):
    """Drop ids outside the candidate scope; C-FUTURE already enforced at
    candidate build. Returns (kept, dropped)."""
    kept, dropped = [], []
    for did in ids:
        if did in candidate_ids:
            if did not in kept:
                kept.append(did)
        else:
            dropped.append(did)
    return kept, dropped


def label_one(query_row, candidates, args):
    """One LLM call (or replay read) for one slice query. Returns row dict."""
    candidate_ids = [dialogue_id(c) for c in candidates]
    user = USER_PROMPT_TEMPLATE.format(
        query_id=dialogue_id(query_row),
        query_transcript=render_transcript(query_row),
        candidates="\n\n".join(
            f"[{dialogue_id(c)}]\n{render_transcript(c)}" for c in candidates
        ),
    )
    raw_name = f"{dialogue_id(query_row)}.json"
    raw_path = str(Path(args.raw_dir) / raw_name)
    try:
        response = call_llm(
            SYSTEM_PROMPT, user,
            model=args.model,
            base_url=args.base_url, api_key=args.api_key,
            raw_path=raw_path,
            replay_dir=args.replay_dir,
            temperature=0.0,
        )
    except LLMError as exc:
        return {"status": "llm_error", "error": str(exc)}

    parsed = None
    for attempt in (1, 2):
        try:
            parsed = parse_label(response)
            break
        except (ValueError, json.JSONDecodeError):
            if attempt == 1:
                # one retry with the same prompt (mirrors PROMPTS.md §4)
                try:
                    response = call_llm(
                        SYSTEM_PROMPT, user,
                        model=args.model,
                        base_url=args.base_url, api_key=args.api_key,
                        raw_path=raw_path,
                        replay_dir=args.replay_dir,
                        temperature=0.0,
                    )
                except LLMError as exc:
                    return {"status": "llm_error", "error": str(exc)}
            else:
                return {"status": "rejected", "response": response[:300]}

    if parsed is None:  # unreachable; defensive
        return {"status": "rejected", "response": response[:300]}

    kept, dropped = validate_ids(parsed["useful_dialogue_ids"], set(candidate_ids),
                                 dialogue_id(query_row))
    return {
        "status": "labeled",
        "useful_dialogue_ids": kept,
        "dropped_ids": dropped,
        "notes": parsed["notes"][:500],
    }


# --------------------------------------------------------------------------
# Self-test (never touches the hold-out)
# --------------------------------------------------------------------------

def make_self_test_files(tmpdir):
    """Synthetic raw-schema pack: how-to + site + negative families."""
    tmp = Path(tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)

    def chat(cid, unlock, turns):
        return {"chat_id": cid, "split": "train", "vertical": "customer-support",
                "tenant": "x", "unlock": unlock, "unlock_guideline": "g",
                "n_turns": len(turns), "turns": [
                    {"speaker": s, "text": t} for s, t in turns]}

    pool = [
        chat(101, "boots_how_1", [
            ("customer", "paint stain on my boots"),
            ("agent", "Brush off dry paint, flake it, then wash with soapy water. "
                      "If it stays, scrape gently and use nail polish remover."),
            ("customer", "worked, thanks")]),
        chat(102, "boots_how_1", [
            ("customer", "ink stain on boots"),
            ("agent", "Brush, flake, soapy water, scrape, then nail polish remover."),
            ("customer", "ok")]),
        chat(103, "boots_how_2", [
            ("customer", "is the boot width regular or wide"),
            ("agent", "The width is an extra 1/6 inch over regular."),
            ("customer", "thanks")]),
        chat(104, "slow_speed", [
            ("customer", "site is slow"),
            ("agent", "Close extra tabs and log out then back in. Report to the team."),
            ("customer", "ok")]),
        chat(105, "bad_price_competitor", [
            ("customer", "cheaper elsewhere"),
            ("agent", "Give me your name and account id."),
            ("customer", "Jane Doe, ACCT-12345"),
            ("agent", "Order id?"),
            ("customer", "ORD-999"),
            ("action", "A reason of competitor has been recorded."),
            ("agent", "I'll make a one time exception and provide a promo code: JP0FA"),
            ("customer", "thanks")]),
    ]
    holdout = [
        chat(201, "boots_how_1", [
            ("customer", "paint stain on new boots, how do I clean it"),
            ("agent", "Let me check."),
            ("customer", "please")]),
        chat(202, "bad_price_competitor", [
            ("customer", "why is your price higher than the competitor"),
            ("agent", "Give me your account id."),
            ("customer", "Bob Smith, ACCT-777"),
            ("agent", "Prices change dynamically; I cannot alter this."),
            ("customer", "ok")]),
        chat(203, "slow_speed", [
            ("customer", "the website is really slow today"),
            ("agent", "Let me look into it."),
            ("customer", "please")]),
    ]
    (tmp / "pool.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in pool) + "\n", encoding="utf-8")
    (tmp / "holdout.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in holdout) + "\n", encoding="utf-8")
    return tmp


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def run(args):
    pool_rows = load_raw(args.pool)
    holdout_rows = load_raw(args.holdout)
    # synthetic clock: pool file first (indices 1..N), hold-out after
    for i, row in enumerate(pool_rows, start=1):
        row["_index"] = i
    for i, row in enumerate(holdout_rows, start=len(pool_rows) + 1):
        row["_index"] = i

    slice_ = build_slice(holdout_rows)

    if args.limit:
        slice_ = slice_[: args.limit]

    by_id = {dialogue_id(r): r for r in holdout_rows}
    queries = []
    for did, family, unlock in slice_:
        qrow = by_id[did]
        qclosed = synthetic_closed_at(qrow["_index"])
        candidates = build_candidates(pool_rows, unlock, qclosed)
        queries.append({"query_id": did, "family": family, "unlock": unlock,
                        "n_candidates": len(candidates),
                        "candidates": candidates, "row": qrow})

    out_rows, statuses, usage = [], [], {}
    for q in queries:
        if args.dry_run:
            statuses.append({"query_id": q["query_id"], "family": q["family"],
                             "n_candidates": q["n_candidates"], "status": "dry_run"})
            continue
        if q["n_candidates"] == 0:
            statuses.append({"query_id": q["query_id"], "family": q["family"],
                             "status": "no_candidates",
                             "useful_dialogue_ids": [], "notes": "no candidate sessions in pool"})
            out_rows.append({"query_id": q["query_id"], "useful_dialogue_ids": [],
                             "notes": "no candidate sessions in pool", "labeler": LABELER})
            continue
        res = label_one(q["row"], q["candidates"], args)
        if res["status"] == "labeled":
            statuses.append({"query_id": q["query_id"], "family": q["family"],
                             "status": "labeled",
                             "useful_dialogue_ids": res["useful_dialogue_ids"],
                             "dropped_ids": res["dropped_ids"]})
            out_rows.append({"query_id": q["query_id"],
                             "useful_dialogue_ids": res["useful_dialogue_ids"],
                             "notes": res["notes"], "labeler": LABELER})
        elif res["status"] == "no_candidates":
            pass  # handled above
        else:
            statuses.append({"query_id": q["query_id"], "family": q["family"],
                             "status": res["status"],
                             "detail": res.get("error") or res.get("response")})
        usage = USAGE.snapshot()

    if not args.dry_run:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            for r in out_rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "artifact": str(args.out),
        "labeler": LABELER,
        "model": args.model,
        "temperature": 0,
        "prompt_sha256": hashlib.sha256(
            (SYSTEM_PROMPT + "\n---\n" + USER_PROMPT_TEMPLATE).encode("utf-8")).hexdigest(),
        "inputs": {
            "pool": {"path": str(args.pool), "sha256": sha256_file(args.pool),
                     "rows": len(pool_rows)},
            "holdout": {"path": str(args.holdout), "sha256": sha256_file(args.holdout),
                        "rows": len(holdout_rows)},
        },
        "slice": {
            "rule": ("hold-out FAQ how-to + site-troubleshoot + %d negative "
                     "dispute/promo (all core + first %d manage_* by dialogue_id)"
                     % (NEG_TOTAL, NEG_MANAGE_FILL)),
            "n": len(slice_),
            "families": {},
            "queries": [{"query_id": q["query_id"], "family": q["family"],
                         "unlock": q["unlock"], "n_candidates": q["n_candidates"]}
                        for q in queries],
        },
        "statuses": statuses,
        "usage": usage,
    }
    for fam in ("howto", "site", "negative", "negative_manage"):
        manifest["slice"]["families"][fam] = sum(
            1 for q in queries if q["family"] == fam)
    if not args.dry_run:
        with open(args.manifest, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        sys.stdout.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pool", default="data/abcd_1000_pool.jsonl")
    p.add_argument("--holdout", default="data/abcd_200_holdout.jsonl")
    p.add_argument("--out", default="data/gold_useful.jsonl")
    p.add_argument("--manifest", default="data/gold_useful.manifest.json")
    p.add_argument("--raw-dir", default="data/raw_gold_useful")
    p.add_argument("--model", default=MODEL_DEFAULT,
                   help="model for labeling (default %s, founder decision #51)" % MODEL_DEFAULT)
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="build slice + candidates only; no LLM, no output file")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--replay-dir", default=None)
    p.add_argument("--self-test", default=None, metavar="TMPDIR",
                   help="run against a synthetic raw-schema pack in TMPDIR "
                        "(never the hold-out); writes no gold file")
    args = p.parse_args()

    if args.self_test:
        # force out/manifest into the tmp dir, never into data/
        tmp = make_self_test_files(args.self_test)
        args.out = str(tmp / "gold_useful.jsonl")
        args.manifest = str(tmp / "gold_useful.manifest.json")
        args.raw_dir = str(tmp / "raw")
        args.pool = str(tmp / "pool.jsonl")
        args.holdout = str(tmp / "holdout.jsonl")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
