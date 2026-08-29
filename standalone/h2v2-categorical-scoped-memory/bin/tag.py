"""S2 — tag.py: the compiler. Tags a whole session (SPEC §4).

H2v2 change vs v1: problem_shape / constraint / ending are closed-vocab
ids from config.PROBLEM_SHAPES / CONSTRAINTS / ENDINGS. Parse clamps
unknown values (other / none / unknown). Do not accept free-text labels.

Everything else is the v1 contract:
- input:  --in data/dialogues.jsonl
- output: data/sessions.jsonl + starter rows in data/ratings.jsonl
- prompt: PROMPTS.md §2 system + §3 user
- LLM only through common.call_llm, temperature 0
- PII scrub before writing to the pool
- reject ONLY when problem_shape is empty after scrub
- two consecutive unparseable model answers -> reject
- idempotent on dialogue_id
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402
import prompts  # noqa: E402

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*$")


def _strip_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and _FENCE_RE.match(lines[0]):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _token(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower().replace(" ", "_")


def _clamp(value: object, allowed: list[str], fallback: str) -> str:
    token = _token(value)
    return token if token in allowed else fallback


def _parse_tags(content: str) -> dict | None:
    """Closed-vocab parse. Missing keys -> reject. Unknown ids -> clamp."""
    try:
        obj = json.loads(_strip_fence(content))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    for key in ("problem_shape", "constraint", "ending"):
        if key not in obj:
            return None
    return {
        "problem_shape": _clamp(obj["problem_shape"], config.PROBLEM_SHAPES, "other"),
        "constraint": _clamp(obj["constraint"], config.CONSTRAINTS, "none"),
        "ending": _clamp(obj["ending"], config.ENDINGS, "unknown"),
    }


def tag_dialogue(dialogue: dict, *, model: str, base_url: str | None,
                 raw_dir: str | Path, replay_dir: str | Path | None = None,
                 ) -> tuple[dict | None, dict]:
    """Tag one raw dialogue. Returns (session_row|None, call_stats)."""
    dialogue_id = dialogue["dialogue_id"]
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    channel = (dialogue.get("channel") or "").strip() or "unknown"
    vertical = (dialogue.get("vertical") or "").strip() or "unknown"

    turns = copy.deepcopy(dialogue.get("turns") or [])
    turns, pii_turns = common.scrub_turns(turns)
    transcript = common.render_transcript(turns)
    user = prompts.TAG_USER.format(channel=channel, vertical=vertical,
                                   transcript=transcript)

    stats = {"tag_calls": 0, "unparseable": 0, "rejected": False, "pii": pii_turns}
    tags = None
    for attempt in (1, 2):
        if replay_dir is not None:
            rec = common.read_json(Path(replay_dir) / f"{dialogue_id}.json")
            content = rec["response"]["choices"][0]["message"]["content"]
            result = {"content": content, "raw": rec["response"],
                      "usage": rec.get("usage") or {}, "model": model}
            stats["tag_calls"] += 1
        else:
            result = common.call_llm(prompts.TAG_SYSTEM, user, model=model,
                                     base_url=base_url)
            stats["tag_calls"] += 1
            common.write_json(raw_dir / f"{dialogue_id}.json", {
                "request": {"model": model, "system": prompts.TAG_SYSTEM, "user": user},
                "response": result["raw"],
                "model": model,
                "usage": result["usage"],
            })
        tags = _parse_tags(result["content"])
        if tags is not None:
            break
        stats["unparseable"] += 1

    if tags is None:
        stats["rejected"] = True
        return None, stats

    pii_any = pii_turns
    for field in ("problem_shape", "constraint", "ending"):
        tags[field], h = common.scrub_text(tags[field])
        pii_any = pii_any or h
    tags["problem_shape"] = _clamp(tags["problem_shape"], config.PROBLEM_SHAPES, "other")
    tags["constraint"] = _clamp(tags["constraint"], config.CONSTRAINTS, "none")
    tags["ending"] = _clamp(tags["ending"], config.ENDINGS, "unknown")
    tags["channel"] = channel
    tags["vertical"] = vertical

    if not tags["problem_shape"].strip():
        stats["rejected"] = True
        return None, stats

    session = {
        "session_id": common.session_id_of(dialogue_id),
        "source_dialogue_id": dialogue_id,
        "closed_at": dialogue.get("closed_at") or "",
        "channel": channel,
        "vertical": vertical,
        "agent_id": dialogue.get("agent_id") or "unknown",
        "turns": turns,
        "tags": tags,
        "tag_key": common.make_tag_key(tags),
        "contains_pii": bool(pii_any),
        "created_at": dialogue.get("closed_at") or "",
    }
    return session, stats


def _rating_row(session_id: str, tag_key: str) -> dict:
    return {
        "session_id": session_id,
        "tag_key": tag_key,
        "score": 0.0,
        "shows": 0,
        "good": 0,
        "bad": 0,
        "unclear": 0,
        "last_shown_at": None,
    }


def _upsert_sessions(pool: list[dict], new_rows: list[dict]) -> list[dict]:
    index = {s["session_id"]: i for i, s in enumerate(pool)}
    for row in new_rows:
        i = index.get(row["session_id"])
        if i is None:
            index[row["session_id"]] = len(pool)
            pool.append(row)
        else:
            pool[i] = row
    return pool


def _upsert_ratings(ratings: list[dict], wanted: list[tuple[str, str]]) -> list[dict]:
    seen = {(r["session_id"], r["tag_key"]) for r in ratings}
    for sid, key in wanted:
        if (sid, key) not in seen:
            ratings.append(_rating_row(sid, key))
            seen.add((sid, key))
    return ratings


def process_rows(rows: list[dict], *, sessions_path, ratings_path, raw_dir,
                 model, base_url, replay_dir: str | Path | None = None) -> dict:
    pool = common.read_jsonl(sessions_path)
    ratings = common.read_jsonl(ratings_path)
    pool_by_id = {s["source_dialogue_id"]: s for s in pool}

    stats = {"sessions": 0, "reused": 0, "rejected": 0, "tag_calls": 0,
             "unparseable": 0, "pii_sessions": 0}
    new_rows: list[dict] = []
    wanted: list[tuple[str, str]] = []

    for row in rows:
        dialogue_id = row.get("dialogue_id") or row.get("source_dialogue_id")
        if not dialogue_id:
            raise SystemExit(common.fail(f"row has no dialogue_id/source_dialogue_id: {row!r}"))
        if "tags" in row and isinstance(row.get("tags"), dict):
            session = row
            stats["reused"] += 1
            pii = bool(session.get("contains_pii"))
        else:
            existing = pool_by_id.get(dialogue_id)
            if existing is not None:
                session = existing
                stats["reused"] += 1
                pii = bool(session.get("contains_pii"))
            else:
                session, call_stats = tag_dialogue(
                    row, model=model, base_url=base_url, raw_dir=raw_dir,
                    replay_dir=replay_dir)
                stats["tag_calls"] += call_stats["tag_calls"]
                stats["unparseable"] += call_stats["unparseable"]
                if session is None:
                    stats["rejected"] += 1
                    continue
                pii = bool(session.get("contains_pii"))
                stats["sessions"] += 1
        if pii:
            stats["pii_sessions"] += 1
        new_rows.append(session)
        wanted.append((session["session_id"], session["tag_key"]))
        pool_by_id[dialogue_id] = session

    pool = _upsert_sessions(pool, new_rows)
    ratings = _upsert_ratings(ratings, wanted)
    common.write_jsonl(sessions_path, pool)
    common.write_jsonl(ratings_path, ratings)
    stats["pool_rows"] = len(pool)
    stats["rating_rows"] = len(ratings)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="S2 tag: closed-vocab session tags (H2v2 SPEC §4)")
    ap.add_argument("--in", dest="inp", default=config.DEFAULT_PATHS["dialogues"])
    ap.add_argument("--out", default=config.DEFAULT_PATHS["sessions"])
    ap.add_argument("--ratings-out", default=config.DEFAULT_PATHS["ratings"])
    ap.add_argument("--raw-dir", default=config.DEFAULT_PATHS["raw_tag"])
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--base-url", default=None, help="default: H2_BASE_URL env")
    ap.add_argument("--replay-dir", default=None,
                    help="C-REPLAY: read saved raw/tag records instead of the LLM")
    args = ap.parse_args()

    rows = common.read_jsonl(args.inp)
    stats = process_rows(rows, sessions_path=args.out, ratings_path=args.ratings_out,
                         raw_dir=args.raw_dir, model=args.model,
                         base_url=args.base_url, replay_dir=args.replay_dir)
    common.print_summary({
        "ok": True,
        "step": "S2",
        "script": "tag.py",
        "in": args.inp,
        "in_rows": len(rows),
        "sessions": stats["sessions"],
        "reused": stats["reused"],
        "rejected": stats["rejected"],
        "tag_calls": stats["tag_calls"],
        "unparseable": stats["unparseable"],
        "pii_sessions": stats["pii_sessions"],
        "out": args.out,
        "pool_rows": stats["pool_rows"],
        "ratings_out": args.ratings_out,
        "rating_rows": stats["rating_rows"],
        "sha256": common.sha256_of(args.out),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
