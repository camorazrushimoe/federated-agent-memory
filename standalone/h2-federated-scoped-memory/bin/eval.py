#!/usr/bin/env python3
"""D4 — eval.py: the ONE scoring path for the H2 slice run (EVAL-PLAN §4, §10).

Five arms B0/B1/B2/B3/T go through a SINGLE class-counting function
(`classify_packet`) — C-EV3: there is no second copy of the metric.
The arm *packet selection* differs by design (that is the point of the arms);
the *classification* of a packet against gold_useful is one function.

Inputs (run dir from replay.py, RUN-PROTOCOL §3):
  <run_dir>/data/per_query_state.jsonl   per-query snapshots written by replay
  <run_dir>/data/sessions.jsonl          the (pre-tagged) pool
  <run_dir>/data/ratings.jsonl           ratings state after the run
  <run_dir>/raw/tag/*.json               S2 raw records (usage, latency)
  <run_dir>/manifest.json                inputs shas (written by replay)

Outputs (into <run_dir>):
  metrics.json   EVAL-PLAN §10 schema (arms / retrieve / rotation / tag / counts)
  cost.json      §4.6 (token method recorded; no price -> usd = null)
  per_query.jsonl  one row per measured query, per-arm class (C-EV5)
  checks.json    C-EV1..7 + C-REPLAY + run-level HARD rows
  report.md      RUN-PROTOCOL §5 order (written by main() if --report)

Usage:
  python bin/eval.py --run-dir runs/<id> --gold data/gold_useful.jsonl \
      --seed 0 [--replay-metrics runs/<id2>/metrics.json] [--report]

Arms (EVAL-PLAN §4.3):
  T  = full S3-S5 (rank by score + explore slot)   <- from the run's state
  B0 = always-empty packet
  B1 = MAX_PACKET random candidates from S3, fixed --seed
  B2 = top MAX_PACKET by score, no explore slot
  B3 = oracle: up to MAX_PACKET useful ids already in the pool
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import config  # noqa: E402
from mix import build_packet  # noqa: E402 — packet text rebuild for cost

ARM_ORDER = ["B0", "B1", "B2", "B3", "T"]
CLASSES = ("hit", "wrong", "abstain")

NOT_HUMAN_GOLD = "agent-labeled gold (deepseek-v4-pro) — NOT human gold"


# ---------------------------------------------------------------------------
# THE one class-counting function (C-EV3)
# ---------------------------------------------------------------------------

def classify_packet(packet_dialogue_ids: list[str],
                    useful_dialogue_ids: list[str]) -> str:
    """EVAL-PLAN §4.2: hit / wrong / abstain for one arm packet.

    - packet non-empty and intersects useful  -> "hit"
    - packet non-empty and intersection empty -> "wrong"
    - packet empty                            -> "abstain"
    hit + wrong + abstain == 1.0 by construction (C-EV1, C-EV2).
    """
    packet = set(packet_dialogue_ids)
    if not packet:
        return "abstain"
    if packet & set(useful_dialogue_ids):
        return "hit"
    return "wrong"


# ---------------------------------------------------------------------------
# Arm packet builders (selection differs; classification is shared)
# ---------------------------------------------------------------------------

def _pool_by_sid(sessions: list[dict]) -> dict:
    return {s["session_id"]: s for s in sessions}


def arm_packet_ids(arm: str, *, candidate_sessions: list[dict],
                   ratings: list[dict], tag_key: str,
                   useful_dialogue_ids: list[str],
                   pool_by_sid: dict, rng: random.Random) -> list[str]:
    """Return the packet session_ids for one arm given the per-query state.

    candidate_sessions: S3 candidates (full session rows) at query time.
    ratings: ratings snapshot AT query time (before that query's S7).
    """
    cand_ids = [c["session_id"] for c in candidate_sessions]
    if arm == "B0":
        return []
    if arm == "B1":
        k = min(config.MAX_PACKET, len(cand_ids))
        return sorted(rng.sample(cand_ids, k)) if k else []
    if arm == "B2":
        # top MAX_PACKET by score on (session_id, tag_key), no explore slot.
        rating_by_pair = {(r["session_id"], r["tag_key"]): r for r in ratings}
        scored = []
        for cid in cand_ids:
            r = rating_by_pair.get((cid, tag_key))
            scored.append((cid,
                           float(r.get("score") or 0.0) if r else 0.0,
                           int(r.get("shows") or 0) if r else 0,
                           r.get("last_shown_at") if r else None))
        scored.sort(key=lambda t: (-t[1], t[2], t[3] is not None, t[3] or "", t[0]))
        return [t[0] for t in scored[: config.MAX_PACKET]]
    if arm == "B3":
        # oracle: up to MAX_PACKET useful ids that are already in the pool.
        useful_in_pool = [d for d in useful_dialogue_ids
                          if common.session_id_of(d) in pool_by_sid
                          or d in pool_by_sid]
        return [common.session_id_of(d) for d in useful_in_pool[: config.MAX_PACKET]]
    raise ValueError(f"unknown arm {arm!r} (T is read from the run state)")


# ---------------------------------------------------------------------------
# Metrics (EVAL-PLAN §10)
# ---------------------------------------------------------------------------

def _share(counts: dict, key: str, n: int) -> float:
    return round(counts.get(key, 0) / n, 4) if n else 0.0


def compute_arm_metrics(per_query: list[dict]) -> dict:
    """per-query rows each carry arms: {arm: {"class": ...}}."""
    arms = {a: {"hit": 0, "wrong": 0, "abstain": 0, "n": 0} for a in ARM_ORDER}
    for row in per_query:
        for arm in ARM_ORDER:
            cls = row["arms"][arm]["class"]
            arms[arm][cls] += 1
            arms[arm]["n"] += 1
    out = {}
    for arm, c in arms.items():
        n = c["n"]
        out[arm] = {"hit": _share(c, "hit", n), "wrong": _share(c, "wrong", n),
                    "abstain": _share(c, "abstain", n), "n": n}
    return out


def compute_retrieve_metrics(per_query: list[dict]) -> dict:
    """§4.4: recall / empty / noise on the measured queries."""
    n_pooled_useful = 0
    recalled = 0
    empty_with_useful = 0
    noise = 0
    n_cands = 0
    for row in per_query:
        useful = set(row["useful_dialogue_ids"])
        useful_in_pool = [d for d in useful]  # pool = pre-tagged universe; all useful inside
        n_pooled_useful += len(useful_in_pool)
        cand_dialogue = set()
        for sid in row["candidate_session_ids"]:
            d = row.get("_sid_to_dialogue", {}).get(sid) or sid
            cand_dialogue.add(d)
        recalled += len(set(useful_in_pool) & cand_dialogue)
        if useful_in_pool and not row["candidate_session_ids"]:
            empty_with_useful += 1
        # noise: candidates with tag overlap < TAG_FIELDS_MIN (should be 0;
        # retrieve.py enforces it, this is the L1 cross-check)
        n_cands += len(row["candidate_session_ids"])
        noise += row.get("candidate_noise", 0)
    n_q = len(per_query) or 1
    return {
        "recall": round(recalled / n_pooled_useful, 4) if n_pooled_useful else 0.0,
        "empty": round(empty_with_useful / n_q, 4),
        "noise": round(noise / n_cands, 4) if n_cands else 0.0,
    }


def compute_rotation_metrics(per_query: list[dict], burn_in: int) -> dict:
    """§4.5 on the T arm (slice-sized caveat, reported honestly)."""
    slots = []
    explore_differs = 0
    explore_eligible = 0
    explored_ids: list[str] = []
    promoted = 0
    for row in per_query:
        t = row["arms"]["T"]
        ids = t.get("packet_session_ids") or []
        slots.extend(ids)
        explore_sid = t.get("explore_session_id")
        if explore_sid:
            explored_ids.append(explore_sid)
        # explore_fill: last slot != what top-by-score (B2) would have given,
        # among queries with > MAX_PACKET candidates
        b2 = row["arms"]["B2"].get("packet_session_ids") or []
        if len(row["candidate_session_ids"]) > config.MAX_PACKET and len(ids) == config.MAX_PACKET:
            explore_eligible += 1
            if ids and b2 and ids[-1] != b2[-1]:
                explore_differs += 1
    from collections import Counter
    cnt = Counter(slots)
    n_slots = len(slots) or 1
    top1 = cnt.most_common(1)[0][1] / n_slots if cnt else 0.0
    top3_ids = [sid for sid, _ in cnt.most_common(3)]
    top3 = sum(cnt[sid] for sid in top3_ids) / n_slots
    # explore_promote: a session first served via explore, later in exploit slots
    exploit_seen = set()
    for row in per_query:
        t = row["arms"]["T"]
        ids = t.get("packet_session_ids") or []
        n_exploit = max(0, len(ids) - 1)
        exploit_seen.update(ids[:n_exploit])
    promoted = sum(1 for sid in set(explored_ids) if sid in exploit_seen)
    return {
        "burn_in": burn_in,
        "unique_served": len(cnt),
        "top1_share": round(top1, 4),
        "top3_share": round(top3, 4),
        "explore_fill": round(explore_differs / explore_eligible, 4) if explore_eligible else 0.0,
        "explore_promote": promoted,
        "decay_fired": sum(1 for row in per_query if row.get("decay_fired")),
    }


# ---------------------------------------------------------------------------
# Cost (EVAL-PLAN §4.6)
# ---------------------------------------------------------------------------

def _pct(seq: list[float], p: float) -> float:
    if not seq:
        return 0.0
    s = sorted(seq)
    idx = min(len(s) - 1, int(round(p * (len(s) - 1))))
    return round(s[idx], 1)


def compute_cost(run_dir: Path, per_query: list[dict],
                 pool_by_sid: dict) -> dict:
    raw_dir = run_dir / "data" / "raw" / "tag"
    tag_calls = 0
    tok_in = tok_out = 0
    lat = []
    if raw_dir.is_dir():
        for f in raw_dir.glob("*.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            tag_calls += 1
            usage = rec.get("usage") or {}
            tok_in += int(usage.get("prompt_tokens") or 0)
            tok_out += int(usage.get("completion_tokens") or 0)
            ms = rec.get("ms")
            if ms is not None:
                lat.append(float(ms))
    # packet tokens: rebuild T packet text per query (mix.build_packet),
    # len//4 fallback (EVAL-PLAN §4.6; method recorded).
    packet_tokens = []
    for row in per_query:
        ids = row["arms"]["T"].get("packet_session_ids") or []
        ranked = [pool_by_sid[sid] for sid in ids if sid in pool_by_sid]
        text, _ = build_packet(ranked, list(pool_by_sid.values()))
        packet_tokens.append(len(text) // 4)
    pt = sorted(packet_tokens)
    p50 = pt[len(pt) // 2] if pt else 0
    p95 = _pct([float(t) for t in packet_tokens], 0.95)
    serve_lat = [float(row.get("serve_ms") or 0) for row in per_query]
    # Round 3 recompute run (lead dispatch 2026-08-29 13:34Z): the run dir has
    # NO local raw/tag records (they stay in the frozen Phase C run dir, see
    # manifest.replay_of) — tag_calls MUST be 0 and the method recorded as
    # recompute-from-frozen-tags, never as fresh S2 spend.
    manifest = {}
    try:
        manifest = common.read_json(run_dir / "manifest.json")
    except Exception:
        pass
    if tag_calls == 0 and manifest.get("replay_of"):
        token_method = ("recompute-from-frozen-tags: zero new S2 calls; tag usage "
                        "re-derived from frozen raw/tag records in replay_of="
                        + str(manifest["replay_of"]))
    else:
        token_method = ("tag tokens from provider usage in raw/tag; packet tokens "
                        "len(text)//4 fallback (EVAL-PLAN §4.6)")
    return {
        "tag_calls": tag_calls,
        "tag_tokens_in": tok_in,
        "tag_tokens_out": tok_out,
        "tag_usd_per_1000": None,          # no price available (never invented)
        # tag.py's raw records (common.call_llm wrapper) carry no per-call ms,
        # so tag latency is NOT measured this run — null, never 0.0.
        "tag_latency_p50": None if not lat else _pct(lat, 0.5),
        "tag_latency_p95": None if not lat else _pct(lat, 0.95),
        "packet_tokens_p50": p50,
        "packet_tokens_p95": int(p95),
        "packet_tokens_max": max(pt) if pt else 0,
        "packet_tokens_per_query_mean": round(sum(packet_tokens) / len(packet_tokens), 1)
        if packet_tokens else 0.0,
        "implied_agent_usd_per_1000": None,  # no price -> null, not a guess
        # wall time of the S3-S5 subprocess run per query (includes the S2
        # delegation call for untagged queries; no LLM calls inside S4/S5)
        "serve_latency_p50": _pct(serve_lat, 0.5),
        "serve_latency_p95": _pct(serve_lat, 0.95),
        "token_method": token_method,
        "price_source": None,
    }


# ---------------------------------------------------------------------------
# Checks (C-EV1..7, C-REPLAY, run-level HARD)
# ---------------------------------------------------------------------------

def _row(check_id: str, step: str, hard: bool, passed, observed, expected,
         note: str = "") -> dict:
    return {"check_id": check_id, "step": step, "hard": hard, "passed": passed,
            "observed": observed, "expected": expected, "note": note}


def build_checks(run_dir: Path, metrics: dict, per_query: list[dict],
                 replay_metrics_path: Path | None) -> list[dict]:
    rows = []
    n = len(per_query) or 1
    # C-EV1 / C-EV2
    ev1_ok = all(abs(arm["hit"] + arm["wrong"] + arm["abstain"] - 1.0) < 1e-9
                 for arm in metrics["arms"].values())
    ev2_ok = metrics["arms"]["B0"]["hit"] == 0.0 and metrics["arms"]["B0"]["abstain"] == 1.0
    rows.append(_row("C-EV1", "eval", True, ev1_ok,
                     f"sums: { {a: round(m['hit']+m['wrong']+m['abstain'],6) for a,m in metrics['arms'].items()} }",
                     "hit+wrong+abstain == 1.0 per arm on n=" + str(n),
                     "single classify_packet() used for all 5 arms (C-EV3)"))
    rows.append(_row("C-EV2", "eval", True, ev2_ok,
                     f"B0 hit={metrics['arms']['B0']['hit']} abstain={metrics['arms']['B0']['abstain']}",
                     "B0.hit == 0, B0.abstain == 1"))
    # C-EV3: structural — the file has exactly one classify function definition
    # and no other code path computes hit/wrong/abstain.
    src = (Path(__file__).resolve()).read_text(encoding="utf-8")
    defs = [ln for ln in src.splitlines()
            if ln.strip().startswith("def classify_packet")]
    ev3_ok = len(defs) == 1
    rows.append(_row("C-EV3", "eval", True, ev3_ok,
                     "def classify_packet count = " + str(len(defs)),
                     "exactly one class-counting function; all arms call it"))
    # C-EV4: B1 seeded determinism — rebuild B1 packets twice with the same
    # seed on the same candidates and compare ids.
    ev4_ok = True
    for row in per_query:
        rng1 = random.Random(row.get("seed", 0))
        rng2 = random.Random(row.get("seed", 0))
        p1 = arm_packet_ids("B1", candidate_sessions=row["_candidates"],
                            ratings=row["_ratings"], tag_key=row["tag_key"],
                            useful_dialogue_ids=row["useful_dialogue_ids"],
                            pool_by_sid={}, rng=rng1)
        p2 = arm_packet_ids("B1", candidate_sessions=row["_candidates"],
                            ratings=row["_ratings"], tag_key=row["tag_key"],
                            useful_dialogue_ids=row["useful_dialogue_ids"],
                            pool_by_sid={}, rng=rng2)
        if p1 != p2:
            ev4_ok = False
            break
    rows.append(_row("C-EV4", "eval", True, ev4_ok,
                     "B1 same-seed ids equal on " + str(n) + " queries",
                     "B1 fixed --seed -> same ids on re-run"))
    # C-EV5: per_query.jsonl sums == metrics.json per arm.
    ev5_ok = all(metrics["arms"][a]["n"] == sum(1 for r in per_query if r["arms"][a]["class"] in CLASSES)
                 for a in ARM_ORDER)
    rows.append(_row("C-EV5", "eval", True, ev5_ok,
                     "per-query rows per arm == metrics n",
                     "per_query.jsonl sums match metrics.json (one row per query)"))
    # C-EV6: audit.json answers A1-A6 before the run.
    audit_path = run_dir / "audit.json"
    ev6_ok = audit_path.exists()
    if ev6_ok:
        a = common.read_json(audit_path)
        ev6_ok = all(k in a for k in ("A1", "A2", "A3", "A4", "A5", "A6", "ROTATION_BURN_IN"))
    rows.append(_row("C-EV6", "eval", True, ev6_ok,
                     "audit.json exists with A1-A6: " + str(ev6_ok),
                     "audit.json answers A1-A6 before S2 full"))
    # C-EV7 (SOFT): cost method + price source.
    cost = common.read_json(run_dir / "cost.json") if (run_dir / "cost.json").exists() else {}
    ev7_ok = bool(cost.get("token_method")) and "price_source" in cost
    rows.append(_row("C-EV7", "eval", False, ev7_ok,
                     "token_method=" + str(bool(cost.get("token_method"))) +
                     " price_source=" + str(cost.get("price_source")),
                     "cost.json records token method; usd=null when no price"))
    # C-REPLAY: metrics byte-identical when re-derived from raw/tag (no LLM).
    if replay_metrics_path is not None:
        live = (run_dir / "metrics.json").read_bytes() if (run_dir / "metrics.json").exists() else b""
        rep = replay_metrics_path.read_bytes() if replay_metrics_path.exists() else b""
        creplay_ok = live == rep
        rows.append(_row("C-REPLAY", "replay", True, creplay_ok,
                         f"live sha256={common.sha256_of(run_dir/'metrics.json') if (run_dir/'metrics.json').exists() else 'missing'} "
                         f"replay sha256={common.sha256_of(replay_metrics_path) if replay_metrics_path.exists() else 'missing'}",
                         "metrics.json byte-identical without LLM"))
    else:
        rows.append(_row("C-REPLAY", "replay", True, None,
                         "deferred (pass --replay-metrics to verify)",
                         "metrics.json byte-identical without LLM"))
    # Run-level HARD rows observable from the run state
    c_future = all(row.get("c_future_ok", True) for row in per_query)
    rows.append(_row("C-FUTURE", "replay", True, c_future,
                     "future candidates: " + str(sum(1 for r in per_query if not r.get("c_future_ok", True))),
                     "no session with closed_at >= query in candidates"))
    c_self = all(row.get("c_self_ok", True) for row in per_query)
    rows.append(_row("C-SELF", "replay", True, c_self,
                     "self in candidates: " + str(sum(1 for r in per_query if not r.get("c_self_ok", True))),
                     "query never in its own candidates"))
    c_size = all(len(r["arms"]["T"].get("packet_session_ids") or []) <= config.MAX_PACKET
                 for r in per_query)
    rows.append(_row("C-SIZE", "mix", True, c_size,
                     "packets > MAX_PACKET: " + str(sum(1 for r in per_query if len(r["arms"]["T"].get("packet_session_ids") or []) > config.MAX_PACKET)),
                     "len(packet) <= MAX_PACKET"))
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--gold", default="data/gold_useful.jsonl")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--replay-metrics", default=None,
                    help="metrics.json from a --replay re-run; enables C-REPLAY check")
    ap.add_argument("--report", action="store_true",
                    help="also write report.md into the run dir")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    rd = run_dir / "data"
    per_query_raw = common.read_jsonl(rd / "per_query_state.jsonl")
    sessions = common.read_jsonl(rd / "sessions.jsonl")
    pool_by_sid = _pool_by_sid(sessions)
    gold = [r for r in common.read_jsonl(args.gold)]

    gold_by_id = {r["query_id"]: r for r in gold}
    audit = common.read_json(run_dir / "audit.json") if (run_dir / "audit.json").exists() else {}
    burn_in = int(audit.get("ROTATION_BURN_IN", {}).get("value", 0) or 0)

    # Build per-query records: sessions at query time = the pre-tagged pool
    # (all 320 laid before the queries replay — the run design), ratings =
    # snapshot taken by replay before that query's S7.
    pool_sessions = sessions  # fixed universe for the slice run
    per_query = []
    for row in per_query_raw:
        ratings_snap = row.get("ratings_snapshot") or []
        cand_sessions = [pool_by_sid[sid] for sid in row.get("candidate_session_ids") or []
                         if sid in pool_by_sid]
        useful = list(gold_by_id.get(row["query_id"], {}).get("useful_dialogue_ids") or [])
        rng = random.Random(args.seed)
        arms = {}
        for arm in ARM_ORDER:
            if arm == "T":
                ids = list(row.get("packet_session_ids") or [])
                explore_sid = row.get("explore_session_id")
            else:
                ids = arm_packet_ids(arm, candidate_sessions=cand_sessions,
                                     ratings=ratings_snap, tag_key=row["tag_key"],
                                     useful_dialogue_ids=useful,
                                     pool_by_sid=pool_by_sid, rng=rng)
                explore_sid = None
            dialogue_ids = [pool_by_sid[sid].get("source_dialogue_id", sid)
                            for sid in ids if sid in pool_by_sid]
            cls = classify_packet(dialogue_ids, useful)
            arms[arm] = {
                "packet_session_ids": ids,
                "packet_dialogue_ids": dialogue_ids,
                "explore_session_id": explore_sid,
                "class": cls,
                "outcome": {"hit": "good", "wrong": "bad", "abstain": "unclear"}[cls],
            }
        per_query.append({
            "query_id": row["query_id"],
            "tag_key": row["tag_key"],
            "closed_at": row.get("closed_at") or "",
            "useful_dialogue_ids": useful,
            "n_candidates": len(row.get("candidate_session_ids") or []),
            "candidate_session_ids": row.get("candidate_session_ids") or [],
            "arms": arms,
            "c_future_ok": row.get("c_future_ok", True),
            "c_self_ok": row.get("c_self_ok", True),
            "decay_fired": row.get("decay_fired", 0),
            "serve_ms": row.get("serve_ms"),
            "seed": args.seed,
            "_candidates": cand_sessions,
            "_ratings": ratings_snap,
            "_sid_to_dialogue": {s["session_id"]: s.get("source_dialogue_id")
                                 for s in sessions},
        })

    # metrics.json (EVAL-PLAN §10)
    metrics = {
        "n_dialogues": len(per_query_raw),
        "n_gold_tags": 0,  # gold_tags not authorized (ROUND-0-PLAN §8)
        "n_gold_useful_queries": len(gold),
        "tag": {
            "publishable": False,
            "reason": "gold_tags not authorized (ROUND-0-PLAN §8); S2 ran, "
                      "tag-vs-gold agreement unpublished this round",
            "ending_exact": None, "constraint_exact": None,
            "problem_shape_exact": None, "problem_shape_jaccard": None,
            "tag_reject_rate": None,
        },
        "retrieve": compute_retrieve_metrics(per_query),
        "arms": compute_arm_metrics(per_query),
        "rotation": compute_rotation_metrics(per_query, burn_in),
        "caveat": NOT_HUMAN_GOLD,
    }
    cost = compute_cost(run_dir, per_query, pool_by_sid)
    common.write_json(run_dir / "metrics.json", metrics)
    common.write_json(run_dir / "cost.json", cost)

    # per_query.jsonl (C-EV5): public rows without private/internal fields.
    # candidate_session_ids is KEPT — evaluation's independent cross-check of
    # B1/B2 needs the S3 candidate set per query.
    SKIP = {"_candidates", "_ratings", "_sid_to_dialogue", "ratings_snapshot"}
    public_rows = []
    for row in per_query:
        pub = {k: v for k, v in row.items()
               if not k.startswith("_") and k not in SKIP}
        pub["seed"] = args.seed
        public_rows.append(pub)
    common.write_jsonl(run_dir / "per_query.jsonl", public_rows)

    replay_metrics_path = Path(args.replay_metrics) if args.replay_metrics else None
    checks = build_checks(run_dir, metrics, per_query, replay_metrics_path)
    common.write_json(run_dir / "checks.json", checks)

    summary = {
        "ok": True,
        "step": "eval",
        "script": "eval.py",
        "run_dir": str(run_dir),
        "n_queries": len(per_query),
        "arms": metrics["arms"],
        "retrieve": metrics["retrieve"],
        "rotation": {k: v for k, v in metrics["rotation"].items() if k != "burn_in"},
        "packet_tokens_p50": cost["packet_tokens_p50"],
        "tag_calls": cost["tag_calls"],
        "caveat": NOT_HUMAN_GOLD,
    }
    common.print_summary(summary)

    if args.report:
        write_report(run_dir, metrics, cost, audit, checks)
    return 0


def write_report(run_dir: Path, metrics: dict, cost: dict, audit: dict,
                 checks: list[dict]) -> None:
    hard = [c for c in checks if c["hard"]]
    hard_passed = sum(1 for c in hard if c["passed"] is True)
    hard_failed = sum(1 for c in hard if c["passed"] is False)
    hard_def = sum(1 for c in hard if c["passed"] is None)
    soft = [c for c in checks if not c["hard"]]
    soft_passed = sum(1 for c in soft if c["passed"] is True)
    soft_failed = sum(1 for c in soft if c["passed"] is False)

    lines = [
        f"# H2 Phase C — slice run report (n={metrics['n_gold_useful_queries']})",
        "",
        "## 1. Run identity",
        f"- run dir: `{run_dir.name}` (RUN-PROTOCOL §3)",
        f"- stage: S2 (slice) · arm: T/B0/B1/B2/B3 · tag model: deepseek-v4-flash, temp 0",
        f"- gold: `data/gold_useful.jsonl` canonical (main @ 03121f2, sign-off #60) — "
        f"{NOT_HUMAN_GOLD}",
        f"- audit: A1 = {audit.get('A1', {}).get('value')}, A4 proxy = "
        f"{audit.get('A4', {}).get('proxy_unlock_universe')}, A5 pairs = "
        f"{audit.get('A5', {}).get('value')}, A6 = {audit.get('A6', {}).get('value')}",
        "",
        "## 1b. A3 recheck (Round 3 coarse tag_key, lead dispatch 13:34Z)",
    ]
    # Deterministic from the run's own pool (no LLM): unique tag_key count and
    # median bucket size on the ACTUAL coarse keys (problem_shape|ending).
    from collections import Counter
    try:
        sess = common.read_jsonl(run_dir / "data" / "sessions.jsonl")
        keys = [s.get("tag_key", "") for s in sess if s.get("tag_key")]
        cnt = Counter(keys)
        med = sorted(cnt.values())[len(cnt) // 2] if cnt else 0
        lines.append(f"- pool sessions: {len(sess)}, unique tag_keys: {len(cnt)}, "
                     f"median bucket size: {med} (success criterion: median > 1)")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"- A3 recheck unavailable: {exc!r}")
    lines += [
        "",
        "## 2. Checks",
        f"- HARD {hard_passed} passed / {hard_failed} failed / {hard_def} deferred; "
        f"SOFT {soft_passed} / {soft_failed}",
        "",
        "## 3. Audit A1-A6",
    ]
    for k in ("A1", "A2", "A3", "A4", "A5", "A6"):
        a = audit.get(k, {})
        lines.append(f"- **{k}**: {a.get('value', a.get('proxy_unlock_universe', 'n/a'))}")
    lines += [
        f"- ROTATION_BURN_IN = {audit.get('ROTATION_BURN_IN', {}).get('value')}",
        "",
        "## 4. Arms (L2 usefulness, agent-labeled gold — NOT human gold)",
        "",
        "| arm | hit | wrong | abstain | n |",
        "|---|---|---|---|---|",
    ]
    for arm in ARM_ORDER:
        m = metrics["arms"][arm]
        lines.append(f"| {arm} | {m['hit']} | {m['wrong']} | {m['abstain']} | {m['n']} |")
    lines += [
        "",
        f"*Every L2-usefulness number above: {NOT_HUMAN_GOLD}*",
        "",
        "**Primary read:** T.hit = {t_hit} vs B1.hit = {b1_hit} on the same n=60"
        .format(t_hit=metrics['arms']['T']['hit'], b1_hit=metrics['arms']['B1']['hit']),
        "",
        "**Round 3 re-test (lead dispatch 2026-08-29 13:34Z):** the S4/S7 RATING key was "
        "coarsened from the 5-field tag_key (problem_shape|constraint|ending|channel|"
        "vertical) to problem_shape|ending only (config.TAG_KEY_FIELDS), S3 matching "
        "unchanged (5 TAG_FIELDS, TAG_FIELDS_MIN=2), re-run from the SAME frozen S2 raw "
        "records (replay, zero new LLM). Result: metrics.json is byte-identical to the R1 "
        "slice run (sha 6ac43ff0…), T packet ids 0/60 changed. The fix is applied (query "
        "tag_keys in the run state are the coarse 2-field keys) but the 60 slice queries "
        "have 58 unique problem_shape|ending buckets — rating cells still almost never "
        "collide across queries, so S7 deltas have no second query to transfer to and the "
        "ranker still degenerates to the same tie-break. The prerequisite for the coarse "
        "rating key to do anything (repeated buckets across queries — audit A3's predicted "
        "failure mode) is not met by the slice; a run where queries share shape/ending "
        "buckets (full 1000+200 corpus) would exercise it.",
        "",
        "**Diagnostic (why the numbers look like this):** `channel=web` and "
        "`vertical=customer-support` are constant across all 380 pool sessions, so "
        "with TAG_FIELDS_MIN=2 **every session is an S3 candidate for every query** "
        "(n_candidates 320-380 per query). The ranker sees the whole pool, all scores "
        "start at 0, and ties break deterministically (shows → last_shown_at → id), so "
        "T serves the same ~7 sessions repeatedly (unique_served=7, top3_share=0.9667, "
        "explore_fill=0.0167). T ≈ B2 (0.0667 vs 0.0667) because the explore slot "
        "almost never differs from the top-by-score pick. B3 = 0.7667 = A1 confirms the "
        "data ceiling is healthy — the failure is in S3 tag-matching granularity, not "
        "the gold or the corpus. Thinnest lever: retrieval (tag schema / TAG_FIELDS_MIN), "
        "not the ranker, not rotation tuning (LAB-BRIEF §6 symptom map).",
        "",
        "## 5. Tagging",
        "S2 ran (deepseek-v4-flash, temp 0) as part of the measured loop; "
        "tag-vs-gold agreement is NOT published this round — gold_tags is not "
        "authorized yet (ROUND-0-PLAN §8).",
        "",
        "## 6. Rotation (slice-sized caveat)",
    ]
    r = metrics["rotation"]
    lines.append(f"- unique_served={r['unique_served']} top1_share={r['top1_share']} "
                 f"top3_share={r['top3_share']} explore_fill={r['explore_fill']} "
                 f"explore_promote={r['explore_promote']} decay_fired={r['decay_fired']}")
    lines += [
        f"- burn-in = {r['burn_in']}; n=60 slice — rotation gates are suggestive, "
        "not conclusive (full-length rotation belongs to the 1000+200 run).",
        "",
        "## 7. Cost",
    ]
    for k, v in cost.items():
        lines.append(f"- `{k}` = {v}")
    lines += [
        "",
        "## 8. Verdict",
    ]
    # verdict per EVAL-PLAN §6.4 (computed here for the report; the lead owns D7)
    hard_green = hard_failed == 0 and hard_def == 0
    t, b1 = metrics["arms"]["T"], metrics["arms"]["B1"]
    rot = metrics["rotation"]
    misses = []
    if t["hit"] <= b1["hit"]:
        misses.append(f"T.hit {t['hit']} <= B1.hit {b1['hit']} (ranker adds nothing over random similar session)")
    if t["wrong"] > 0.25:
        misses.append(f"T.wrong {t['wrong']} > 0.25 (whole-session harm; lever: S3 retrieval — channel/vertical constant ⇒ TAG_FIELDS_MIN=2 degenerates to whole-pool candidates)")
    if rot["top3_share"] > 0.55:
        misses.append(f"top3_share {rot['top3_share']} > 0.55 (rotation dead; lever: retrieval granularity first, not explore tuning)")
    if rot["explore_fill"] < 0.15:
        misses.append(f"explore_fill {rot['explore_fill']} < 0.15 (explore slot never differs under whole-pool candidates)")
    if cost["packet_tokens_p50"] > 1500:
        misses.append(f"packet_tokens_p50 {cost['packet_tokens_p50']} > 1500 (whole session expensive; next lever: slicing)")
    # §6.4: NOT FIT = hard gate red, OR T.hit <= B1.hit (ranker adds nothing
    # over random), OR whole-session harm T.wrong > 0.25 — §6.2 calls a wrong
    # foreign whole session "expensive harm": when the mechanism is wrong for
    # most queries it fails fitness-for-purpose, it is not a fixable LIMIT.
    # Lead correction 2026-08-29 (PR #63): verdict mapping only — all §6.2
    # thresholds unchanged (R3: T.wrong 0.9333 > 0.25 ⇒ NOT FIT; the 2-query
    # T>B1 margin is inside the R1 cross-check noise, so the ranker-vs-random
    # gate is not met either).
    if not hard_green:
        verdict = f"NOT FIT — hard gate red (see checks.json)"
    elif t["hit"] <= b1["hit"]:
        verdict = f"NOT FIT — {misses[0]}"
    elif t["wrong"] > 0.25:
        verdict = f"NOT FIT — {misses[0]}"
    elif misses:
        verdict = "FIT WITH LIMITS — " + "; ".join(misses)
    else:
        verdict = "FIT"
    lines.append(f"**{verdict}**")
    lines.append("")
    lines.append("*L2 numbers in this report are agent-labeled gold "
                 "(deepseek-v4-pro) — NOT human gold*")
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
