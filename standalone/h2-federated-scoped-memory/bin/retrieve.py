"""S3 — retrieve.py: find candidate sessions in the pool by tag fields.

- input:  --query dialogue_or_session.json --pool data/sessions.jsonl
- output: data/candidates.jsonl for this query (+ data/query_meta.json)
- prompt: none. If the query is not tagged yet, S3 delegates to S2 (tag.py)
  with the same PROMPTS.md §2–§3 strings — it has no text of its own (C-RT4)
- a candidate MUST match on >= TAG_FIELDS_MIN of the S3 matching fields
  (C-RT1; S3_MATCH_FIELDS — Round 4: problem_shape|constraint|ending; the
  constant channel/vertical fields are excluded from the overlap count)
- the query MUST NOT appear among its own candidates (C-SELF)
- order is not important here — that is S4's job
- MUST NOT call the LLM itself (delegation to tag.py only)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402


def overlap_count(query_tags: dict, session_tags: dict) -> int:
    """Overlap over config.S3_MATCH_FIELDS only (Round 4).

    channel/vertical are constant across the pool, so counting them made
    TAG_FIELDS_MIN=2 admit the whole pool; the overlap count now uses the
    three variable tag fields (config.S3_MATCH_FIELDS). The tag schema and
    the S4/S7 rating key are untouched.
    """
    return sum(1 for f in config.S3_MATCH_FIELDS
               if str(query_tags.get(f, "")).strip() != ""
               and str(query_tags.get(f, "")).strip()
               == str(session_tags.get(f, "")).strip())


def resolve_query(query: dict, pool: list[dict], *, tag_out, ratings_out,
                  raw_dir, model, base_url, replay_dir=None) -> tuple[str, dict, dict]:
    """Return (query_id, query_tags, query_meta). Delegates to tag.py if needed."""
    if isinstance(query.get("tags"), dict) and query.get("tag_key"):
        query_id = query.get("source_dialogue_id") or query["dialogue_id"]
        return query_id, query["tags"], {
            "query_id": query_id, "tag_key": query["tag_key"],
            "query_closed_at": query.get("closed_at") or ""}
    dialogue_id = query["dialogue_id"]
    # Already tagged in the pool? Use its tags (SPEC §7 S3).
    for s in pool:
        if s["source_dialogue_id"] == dialogue_id:
            return dialogue_id, s["tags"], {
                "query_id": dialogue_id, "tag_key": s["tag_key"],
                "query_closed_at": s.get("closed_at") or ""}
    # Untagged query: delegate to S2 with the same prompts (PROMPTS.md §7).
    import tag
    stats = tag.process_rows([query], sessions_path=tag_out,
                             ratings_path=ratings_out, raw_dir=raw_dir,
                             model=model, base_url=base_url,
                             replay_dir=replay_dir)
    tagged = common.read_jsonl(tag_out)
    session = next((s for s in tagged
                    if s["source_dialogue_id"] == dialogue_id), None)
    if session is None:
        raise RuntimeError(
            f"S3: query {dialogue_id} was rejected by S2 delegation "
            f"(rejected={stats['rejected']}, tag_calls={stats['tag_calls']})")
    return dialogue_id, session["tags"], {
        "query_id": dialogue_id, "tag_key": session["tag_key"],
        "query_closed_at": session.get("closed_at") or ""}


def main() -> int:
    ap = argparse.ArgumentParser(description="S3 retrieve: candidates by tag fields")
    ap.add_argument("--query", required=True)
    ap.add_argument("--pool", default=config.DEFAULT_PATHS["sessions"])
    ap.add_argument("--out", default=config.DEFAULT_PATHS["candidates"])
    ap.add_argument("--meta", default=config.DEFAULT_PATHS["query_meta"])
    ap.add_argument("--tag-out", default=config.DEFAULT_PATHS["sessions"],
                    help="where delegated S2 writes sessions (default: the pool)")
    ap.add_argument("--ratings-out", default=config.DEFAULT_PATHS["ratings"])
    ap.add_argument("--raw-dir", default=config.DEFAULT_PATHS["raw_tag"])
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--replay-dir", default=None,
                    help="C-REPLAY: pass through to delegated S2 (zero LLM)")
    args = ap.parse_args()

    query = common.read_json(args.query)
    pool = common.read_jsonl(args.pool)

    query_id, query_tags, meta = resolve_query(
        query, pool, tag_out=args.tag_out, ratings_out=args.ratings_out,
        raw_dir=args.raw_dir, model=args.model, base_url=args.base_url,
        replay_dir=args.replay_dir)

    self_ids = {common.session_id_of(query_id), query_id}
    candidates = []
    self_excluded = []
    q_problem_shape = str(query_tags.get("problem_shape", "")).strip()
    for s in pool:
        sid = s["session_id"]
        src = s.get("source_dialogue_id")
        if sid in self_ids or src == query_id:
            self_excluded.append(sid)
            continue
        if config.S3_REQUIRE_PROBLEM_SHAPE:
            # R4 step 2: no problem_shape match -> not a candidate.
            if str((s.get("tags") or {}).get("problem_shape", "")).strip() \
                    != q_problem_shape:
                continue
        if overlap_count(query_tags, s.get("tags") or {}) >= config.TAG_FIELDS_MIN:
            candidates.append(s)

    common.write_jsonl(args.out, candidates)
    common.write_json(args.meta, meta)
    common.print_summary({
        "ok": True,
        "step": "S3",
        "script": "retrieve.py",
        "query": args.query,
        "query_id": query_id,
        "query_tag_key": meta["tag_key"],
        "pool_rows": len(pool),
        "candidates": len(candidates),
        "candidate_ids": [c["session_id"] for c in candidates],
        "self_excluded": self_excluded,
        "out": args.out,
        "sha256": common.sha256_of(args.out),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
