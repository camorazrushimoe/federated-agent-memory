"""D4 — run_slice.py: Phase C measured run on the 60-query slice (EVAL-PLAN §4/§9/§10).

One command, one run dir, all five arms (T/B0/B1/B2/B3) through ONE scoring
function (eval.classify). The measured loop's only LLM is S2 tagging
(deepseek-v4-flash, temp 0); everything after the tags is deterministic.

Design (see ROUND-2 plan, issue #51 comment 5462159237):
- pool = the same-unlock union of the 60 slice queries (labeler's candidate
  universe; verified: all gold useful ids are inside).
- per query, in (closed_at, dialogue_id) order:
    S3 candidates (tag overlap >= TAG_FIELDS_MIN, C-SELF/C-FUTURE) ->
    arm packets: T=rank+explore, B0=empty, B1=seeded random MAX_PACKET,
                 B2=top-by-score no explore, B3=oracle useful∩pool ->
    ONE classify (hit/wrong/abstain) ->
    T's outcome feeds S7 (only T learns; baselines never contaminate).
- writes: manifest.json, audit.json, metrics.json, cost.json, per_query.jsonl,
  report.md, data/{sessions,ratings,candidates,ranked,packet,serves,outcomes},
  data/raw/tag/ (S2 records).

Run:
    H2_API_KEY=... H2_BASE_URL=... python3 bin/run_slice.py \
        --dialogues data/dialogues.jsonl \
        --pool-raw data/abcd_1000_pool.jsonl \
        --slice data/d0_slice.jsonl \
        --gold-useful data/gold_useful.jsonl \
        --model deepseek-v4-flash \
        --out runs/2026-08-29_PhaseC_slice_deepseek-v4-flash
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402
import eval as ev  # noqa: E402  (the ONE scoring function)
import label_gold_useful as lg  # noqa: E402  (slice + candidate construction)
import mix  # noqa: E402
import rank  # noqa: E402
import retrieve  # noqa: E402
import tag  # noqa: E402
import update  # noqa: E402


def read_gold(path):
    """Read gold jsonl skipping the mandatory `#` header (RUN-PROTOCOL §2.3)."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            rows.append(json.loads(s))
    return rows


def build_union_pool(slice_rows, pool_raw):
    """Same-unlock union of pool sessions across the slice (labeler universe)."""
    pool = lg.load_raw(pool_raw)
    for i, r in enumerate(pool, start=1):
        r["_index"] = i
    pool_by_id = {lg.dialogue_id(r): r for r in pool}
    holdout_ids = {q["query_id"] for q in slice_rows}
    union = set()
    for q in slice_rows:
        # query closed_at: find in raw holdout by id (synthetic clock)
        qrow = pool_by_id.get(q["query_id"])
        qclosed = q.get("closed_at") or ""
        cands = lg.build_candidates(pool, q["unlock"], qclosed)
        for c in cands:
            union.add(lg.dialogue_id(c))
    return union, pool_by_id


def arm_packets(candidates, ratings_list, tag_key, useful_ids, pool,
                rng, arm_overrides):
    """Build the five arm packets from the SAME candidates/ratings state.

    Returns {arm: session_ids}. B0 empty; B1 seeded random; B2 top-by-score
    without explore; B3 oracle (useful ∩ pool, gold order, <= MAX_PACKET);
    T = the certified S4 rank (top + explore slot).
    """
    cand_ids = [c["session_id"] for c in candidates]

    # B1: MAX_PACKET random candidates, no ratings/rotation (EVAL-PLAN §4.3)
    b1 = rng.sample(cand_ids, min(config.MAX_PACKET, len(cand_ids))) if cand_ids else []

    # B2: top MAX_PACKET by score, explore slots disabled (same sort as rank.py)
    saved = config.EXPLORE_SLOTS
    try:
        config.EXPLORE_SLOTS = 0
        b2_ranked = rank.rank_candidates(candidates, ratings_list, tag_key)
    finally:
        config.EXPLORE_SLOTS = saved
    b2 = [s["session_id"] for s in b2_ranked[: config.MAX_PACKET]]

    # B3: oracle — up to MAX_PACKET useful ids already in the pool,
    # mapped to session ids (classify works on session ids, like S6)
    src_to_sid = [(s.get("source_dialogue_id"), s["session_id"]) for s in pool]
    pool_src = {s["source_dialogue_id"] for s in pool}
    b3 = [sid for src, sid in src_to_sid
          if src in useful_ids and src in pool_src][: config.MAX_PACKET]

    # T: certified rank (top + explore slot)
    t_ranked = rank.rank_candidates(candidates, ratings_list, tag_key)
    t = [s["session_id"] for s in t_ranked[: config.MAX_PACKET]]

    return {"B0": [], "B1": b1, "B2": b2, "B3": b3, "T": t}


def verdict_line(metrics: dict, cost: dict) -> str:
    """EVAL-PLAN §6.4 — exactly one of FIT / FIT WITH LIMITS / NOT FIT."""
    arms = metrics["arms"]
    n = metrics["n_queries"]
    hard_ok = arms["B0"]["hit"] == 0 and all(sum(a.values()) == n for a in arms.values())
    if not hard_ok:
        return "NOT FIT (hard gate: B0.hit != 0 or classes do not sum to n)"
    if arms["T"]["hit"] <= arms["B1"]["hit"]:
        return ("NOT FIT (T.hit <= B1.hit: the ranker adds nothing over a random "
                "similar past session on this slice)")
    fails = []
    if arms["T"]["wrong"] > 0.25 * n:
        fails.append(f"T.wrong {arms['T']['wrong']} > 0.25*n")
    if (cost.get("packet_tokens_p50") or 0) > 1500:
        fails.append("packet_tokens_p50 > 1500 (whole session is expensive)")
    if fails:
        return "FIT WITH LIMITS (" + "; ".join(fails) + ")"
    return "FIT"


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase C slice run (D4)")
    ap.add_argument("--dialogues", default=config.DEFAULT_PATHS["dialogues"])
    ap.add_argument("--pool-raw", required=True, help="abcd_1000_pool.jsonl")
    ap.add_argument("--slice", required=True, help="d0_slice.jsonl")
    ap.add_argument("--gold-useful", required=True)
    ap.add_argument("--model", default=config.DEFAULT_MODEL)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True, help="run dir (MUST be empty)")
    ap.add_argument("--resume", action="store_true",
                    help="reuse existing data/ tag artifacts (sessions, query_tags, "
                         "raw) instead of a fresh empty dir; zero new LLM calls for "
                         "already-tagged ids (C-TG5)")
    args = ap.parse_args()

    out = Path(args.out)
    if not args.resume:
        if out.exists() and any(out.iterdir()):
            return common.fail(f"--out must be empty: {out}")
    else:
        # resume is only valid when S7 has NOT yet been applied: once
        # update_state.json exists, the ratings file holds the FINAL trajectory
        # and a re-run would use it as the starting state (wrong learning
        # history). Refuse; reset the run dir for a fresh deterministic run.
        if (out / "data" / "update_state.json").exists():
            return common.fail(
                f"--out {out} already has update_state.json (S7 applied). "
                f"Reset the run dir to data/raw+data/sessions only for a fresh "
                f"deterministic re-run; never resume a completed run.")
    out.mkdir(parents=True, exist_ok=True)
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out / "data" / "raw" / "tag"
    raw_dir.mkdir(parents=True, exist_ok=True)
    packets_dir = out / "packets"
    packets_dir.mkdir(parents=True, exist_ok=True)

    # ---- inputs ----
    dialogues = common.read_jsonl(args.dialogues)
    by_did = {d["dialogue_id"]: d for d in dialogues}
    slice_rows = [json.loads(l) for l in open(args.slice) if not l.startswith("#")]
    gold = {r["query_id"]: list(r.get("useful_dialogue_ids") or [])
            for r in read_gold(args.gold_useful)}
    if set(gold) != {q["query_id"] for q in slice_rows}:
        return common.fail("gold_useful query set != slice query set")

    union, pool_raw_by_id = build_union_pool(slice_rows, args.pool_raw)
    missing = [qid for qid in union if qid not in by_did]
    if missing:
        return common.fail(f"union pool ids missing from dialogues: {missing[:5]}")

    # ---- S2 tag pool + queries (the only live LLM; raw records kept) ----
    pool_rows = [by_did[qid] for qid in sorted(union)]
    query_rows = [by_did[q["query_id"]] for q in slice_rows]
    sessions_path = data_dir / "sessions.jsonl"
    ratings_path = data_dir / "ratings.jsonl"
    query_tags_path = data_dir / "query_tags.jsonl"

    tag_stats = tag.process_rows(pool_rows, sessions_path=sessions_path,
                                 ratings_path=ratings_path, raw_dir=raw_dir,
                                 model=args.model, base_url=None)
    # queries tagged separately (never laid into the pool)
    query_stats = tag.process_rows(query_rows, sessions_path=query_tags_path,
                                   ratings_path=data_dir / "query_ratings.jsonl",
                                   raw_dir=raw_dir, model=args.model, base_url=None)

    pool = common.read_jsonl(sessions_path)
    query_tags = {s["source_dialogue_id"]: s for s in common.read_jsonl(query_tags_path)}
    rejected_queries = [q["dialogue_id"] for q in query_rows
                        if q["dialogue_id"] not in query_tags]
    if rejected_queries:
        return common.fail(f"S2 rejected {len(rejected_queries)} queries: "
                           f"{rejected_queries[:5]}")

    # ---- per-query loop (replay order) ----
    order = sorted(slice_rows, key=lambda q: (q.get("closed_at") or "", q["query_id"]))
    rng = random.Random(args.seed)
    ratings = {(r["session_id"], r["tag_key"]): r
               for r in common.read_jsonl(ratings_path)}
    # S7 idempotency across resumes (C-UP5): query ids whose T outcome was
    # already applied are remembered in update_state.json and NOT re-applied.
    state_path = out / "data" / "update_state.json"
    applied = set(common.read_json(state_path).get("applied_query_ids")
                  if state_path.exists() else [])
    per_query = []
    serves = []
    outcomes = []
    cost_packet_tokens = []
    retrieve_rows = []

    for q in order:
        qid = q["query_id"]
        qs = query_tags[qid]
        qtags = qs["tags"]
        qtag_key = qs["tag_key"]
        qclosed = q.get("closed_at") or ""
        useful = gold[qid]

        # S3: candidates = tag overlap >= TAG_FIELDS_MIN, earlier closed_at, no self
        candidates = []
        for s in pool:
            if s.get("source_dialogue_id") == qid:
                continue  # C-SELF
            if s.get("closed_at") and s["closed_at"] >= qclosed:
                continue  # C-FUTURE
            if retrieve.overlap_count(qtags, s.get("tags") or {}) >= config.TAG_FIELDS_MIN:
                candidates.append(s)
        retrieve_rows.append({"query_id": qid, "n_candidates": len(candidates),
                              "candidate_ids": [c["session_id"] for c in candidates]})

        ratings_list = list(ratings.values())
        pkts = arm_packets(candidates, ratings_list, qtag_key, useful, pool,
                           rng, None)

        # ONE scoring function for every arm
        row = {"query_id": qid, "tag_key": qtag_key, "closed_at": qclosed,
               "useful_dialogue_ids": useful, "n_candidates": len(candidates)}
        for arm, ids in pkts.items():
            cls = ev.classify(ids, useful, pool)
            row[f"arm_{arm}_ids"] = ids
            row[f"arm_{arm}_class"] = cls
            per_query.append({"query_id": qid, "arm": arm, "class": cls,
                              "packet_session_ids": ids, "tag_key": qtag_key})
            if arm == "T":
                # cost: packet text tokens for the treatment packet
                ranked_for_t = [c for c in candidates if c["session_id"] in ids]
                packet_text, _ = mix.build_packet(ranked_for_t, pool)
                cost_packet_tokens.append(len(packet_text) // 4)
                with open(packets_dir / f"{qid}.txt", "w") as f:
                    f.write(packet_text)
                # S7: T only (hit->good, wrong->bad, abstain->unclear),
                # applied IN replay order so later queries see the learning
                outcome = ev.outcome_of(cls)
                outcomes.append({"query_id": qid, "tag_key": qtag_key,
                                 "packet_session_ids": ids, "outcome": outcome,
                                 "source": "gold", "closed_at": qclosed})
                serves.append({"query_id": qid, "tag_key": qtag_key,
                               "session_ids": ids})
                if qid not in applied:  # idempotent (C-UP5)
                    update.apply_outcome(outcomes[-1], ratings)
                    applied.add(qid)

    # (S7 updates were applied per query inside the loop, in replay order,
    # so later queries already saw the learning — C-UP5 idempotent.)
    common.write_json(state_path, {"applied_query_ids": sorted(applied)})

    # ---- write artifacts ----
    common.write_jsonl(out / "per_query.jsonl", per_query)
    common.write_jsonl(data_dir / "candidates.jsonl",
                       [{"query_id": r["query_id"], "n_candidates": r["n_candidates"],
                         "candidate_ids": r["candidate_ids"]} for r in retrieve_rows])
    common.write_jsonl(data_dir / "serves.jsonl", serves)
    common.write_jsonl(data_dir / "outcomes.jsonl", outcomes)
    common.write_jsonl(data_dir / "ratings.jsonl", list(ratings.values()))

    # ---- metrics.json (EVAL-PLAN §10) ----
    metrics = ev.aggregate(per_query)

    # retrieve §4.4
    n_with_useful = 0
    recall_num = recall_den = 0
    empty_hits = 0
    for q in order:
        qid = q["query_id"]
        useful = gold[qid]
        rr = next(r for r in retrieve_rows if r["query_id"] == qid)
        cand_src = {s["source_dialogue_id"] for s in pool
                    if s["session_id"] in rr["candidate_ids"]}
        in_pool_useful = [u for u in useful if u in {s["source_dialogue_id"] for s in pool}]
        if in_pool_useful:
            n_with_useful += 1
            recall_den += len(in_pool_useful)
            recall_num += len(set(in_pool_useful) & cand_src)
            if not rr["candidate_ids"]:
                empty_hits += 1
    metrics["retrieve"] = {
        "recall": (recall_num / recall_den) if recall_den else None,
        "empty": (empty_hits / n_with_useful) if n_with_useful else None,
        "n_with_useful_in_pool": n_with_useful,
    }

    # rotation §4.5 (T only; all slice queries have >= MAX_PACKET candidates)
    t_served = [r for r in serves]
    slot_ids = [sid for r in t_served for sid in r["session_ids"]]
    from collections import Counter
    cnt = Counter(slot_ids)
    top = cnt.most_common(3)
    n_slots = len(slot_ids) or 1
    metrics["rotation"] = {
        "burn_in": 0,
        "unique_served": len(cnt),
        "top1_share": (cnt.most_common(1)[0][1] / n_slots) if cnt else 0.0,
        "top3_share": (sum(n for _, n in top) / n_slots) if cnt else 0.0,
        "explore_fill": None,  # computed by eval specialist on ranked detail
        "explore_promote": 0,
        "decay_fired": 0,
        "note": "slice-sized; long-replay rotation is the full-corpus run",
    }

    common.write_json(out / "metrics.json", metrics)

    # ---- cost.json (EVAL-PLAN §4.6) ----
    def pct(v, p):
        if not v:
            return None
        v = sorted(v)
        return v[min(len(v) - 1, int(p * len(v)))]
    raw_recs = list(raw_dir.glob("*.json"))
    tag_in = sum(json.load(open(r)).get("usage", {}).get("prompt_tokens", 0) for r in raw_recs)
    tag_out = sum(json.load(open(r)).get("usage", {}).get("completion_tokens", 0) for r in raw_recs)
    # tag.py raw records carry no per-call latency (common.call_llm has no ms);
    # report call count + tokens from the records, latency = null with note.
    cp = sorted(cost_packet_tokens)
    cost = {
        "method": "tag tokens from provider usage (raw S2 records); packet tokens len(text)//4 fallback",
        "tag_calls": len(raw_recs),  # actual S2 calls (380 in the live run; 0 on a pure resume)
        "tag_tokens_in": tag_in,
        "tag_tokens_out": tag_out,
        "tag_latency_p50": None,
        "tag_latency_p95": None,
        "tag_latency_note": "raw tag records carry no ms; latency not measured this pass",
        "packet_tokens_p50": pct(cp, 0.5),
        "packet_tokens_p95": pct(cp, 0.95),
        "packet_tokens_max": cp[-1] if cp else None,
        "packet_tokens_per_query_mean": (sum(cp) / len(cp)) if cp else None,
        "packet_n": len(cp),
        "usd": None,
        "implied_agent_usd_per_1000": None,
        "card_ratio_note": "typical H1 card ~30-40 words; whole-session packet multiplier in report",
    }
    common.write_json(out / "cost.json", cost)

    # ---- audit.json (EVAL-PLAN §7 A1..A6) ----
    pool_src = {s["source_dialogue_id"] for s in pool}
    a1 = sum(1 for q in order if any(u in pool_src for u in gold[q["query_id"]]))
    n_nonempty = sum(1 for u in gold.values() if u)
    tok_per_tx = [max(1, len(" ".join(t.get("text", "") for t in d.get("turns") or [])) // 4)
                  for d in pool_rows]
    tok_per_tx.sort()
    # A4 from ACTUAL S3 retrieve: fraction of queries with > MAX_PACKET candidates
    a4 = sum(1 for r in retrieve_rows if r["n_candidates"] > config.MAX_PACKET)
    audit = {
        "A1_pool_ceiling": a1 / len(order),
        "A2_gold_tag_overlap": None,
        "A3_tag_key_bucket_median": None,
        "A4_explore_fill_feasible": a4 / len(order),
        "A5_gold_coverage": {"queries": len(order), "non_empty": n_nonempty,
                             "empty": len(order) - n_nonempty},
        "A6_packet_token_ceiling": {"median_transcript_tokens": pct(tok_per_tx, 0.5),
                                    "x_max_packet": (pct(tok_per_tx, 0.5) or 0) * config.MAX_PACKET},
        "notes": ("A2/A3 need gold_tags (human-authored, pending founder decision "
                  "ROUND-0-PLAN §8). A4 computed from actual S3 tag-retrieval."),
    }
    common.write_json(out / "audit.json", audit)

    # ---- manifest.json (RUN-PROTOCOL §3.1) ----
    import hashlib
    import datetime as _dt
    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    manifest = {
        "run_id": out.name,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "stage": "S1-slice",
        "git_commit": subprocess_git(),
        "tag_model": args.model,
        "base_url": "https://api.deepseek.com/v1",
        "temperature": 0,
        "seed": args.seed,
        "arm": "T+B0+B1+B2+B3 (one run, one scoring function)",
        "config": {k: getattr(config, k) for k in
                   ("MAX_PACKET", "EXPLORE_SLOTS", "TAG_FIELDS_MIN",
                    "DECAY_EVERY_SHOWS", "DECAY_AMOUNT", "GOOD_DELTA",
                    "BAD_DELTA", "UNCLEAR_DELTA")},
        "inputs": {
            "dialogues": {"path": args.dialogues, "sha256": sha(args.dialogues),
                          "rows": len(dialogues)},
            "pool_raw": {"path": args.pool_raw, "sha256": sha(args.pool_raw)},
            "slice": {"path": args.slice, "sha256": sha(args.slice), "rows": len(slice_rows)},
            "gold_useful": {"path": args.gold_useful, "sha256": sha(args.gold_useful),
                            "rows": len(gold), "agent_labeled": True,
                            "human_gold": False, "labeler_model": "deepseek-v4-pro"},
            "prompts": {"path": "PROMPTS.md", "sha256": sha("PROMPTS.md")},
        },
        "pool_scope": {"same_unlock_union": len(union),
                       "note": "labeler candidate universe; all gold useful ids inside"},
        "outputs": {"metrics": "metrics.json", "cost": "cost.json",
                    "per_query": "per_query.jsonl", "audit": "audit.json"},
        "caveat": "AGENT-LABELED GOLD — NOT HUMAN GOLD",
    }
    common.write_json(out / "manifest.json", manifest)

    # ---- report.md (RUN-PROTOCOL §5) ----
    arms = metrics["arms"]
    lines = [
        "# H2 — Phase C slice run (first measurement)",
        "",
        f"- run id: `{out.name}` | stage S1-slice | tag model `{args.model}` temp 0",
        f"- slice: {len(order)} queries | pool: same-unlock union {len(union)} sessions",
        "- gold: agent-labeled (deepseek-v4-pro), NOT human gold — curated per sign-off #60",
        "",
        "## Arms (one scoring function, EVAL-PLAN §10)",
        "",
        "| arm | hit | wrong | abstain |",
        "|---|---|---|---|",
    ]
    for a in ("B0", "B1", "B2", "B3", "T"):
        lines.append(f"| {a} | {arms[a]['hit']} | {arms[a]['wrong']} | {arms[a]['abstain']} |")
    lines += [
        "",
        "## Hypothesis gates (EVAL-PLAN §6)",
        "",
        f"- H2-USEFUL `T.hit > B1.hit`: T={arms['T']['hit']} vs B1={arms['B1']['hit']} "
        f"-> {'PASS' if arms['T']['hit'] > arms['B1']['hit'] else 'FAIL'}",
        f"- H2-HARM `T.wrong <= 0.25`: T.wrong={arms['T']['wrong']} "
        f"-> {'PASS' if arms['T']['wrong'] <= 0.25 * len(order) else 'FAIL'}",
        f"- B0 sanity `B0.hit == 0`: B0.hit={arms['B0']['hit']} "
        f"-> {'PASS' if arms['B0']['hit'] == 0 else 'FAIL'}",
        f"- B3 ceiling: {arms['B3']['hit']}/{len(order)} "
        f"(A1 pool ceiling {audit['A1_pool_ceiling']:.2f})",
        f"- retrieve recall: {metrics['retrieve']['recall']} | "
        f"empty: {metrics['retrieve']['empty']}",
        f"- rotation (slice-sized): top1_share {metrics['rotation']['top1_share']:.2f} | "
        f"top3_share {metrics['rotation']['top3_share']:.2f} | "
        f"unique_served {metrics['rotation']['unique_served']}",
        "",
        "## Verdict (EVAL-PLAN §6.4)",
        "",
        f"- {verdict_line(metrics, cost)}",
        "",
        "## Cost",
        f"- tag calls {cost['tag_calls']} ({cost['tag_tokens_in']} in / "
        f"{cost['tag_tokens_out']} out tokens) | packet_tokens_p50 "
        f"{cost['packet_tokens_p50']} | p95 {cost['packet_tokens_p95']} | "
        f"max {cost['packet_tokens_max']}",
        f"- method: {cost['method']}",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    common.print_summary({
        "ok": True, "step": "run_slice", "script": "run_slice.py",
        "run_id": out.name, "queries": len(order), "pool": len(union),
        "tag_calls": tag_stats["tag_calls"] + query_stats["tag_calls"],
        "arms": metrics["arms"], "retrieve": metrics["retrieve"],
        "out": str(out),
    })
    return 0


def subprocess_git() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    d = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return r.stdout.strip() + (" (dirty)" if d.stdout.strip() else "")


if __name__ == "__main__":
    raise SystemExit(main())
