#!/usr/bin/env python3
"""cluster.py — deterministic clustering + promote + staleness (SPEC §5, §6.3).

    python bin/cluster.py --cards data/cards.jsonl --dialogues data/dialogues.jsonl [--force]

No LLM. Steps:
1. cursor (data/cluster_cursor.json, default 0); n = rows(dialogues.jsonl).
2. if n - last < CLUSTER_EVERY_N_CHATS and no --force: {ran:false, remaining:N}.
3. Per scope: candidates = status in {private, shared} AND role=canonical.
   Greedy oldest-first: a card joins the first existing cluster whose canonical
   card-text (problem_shape + constraint + unlock) cosine >= CLUSTER_THRESHOLD
   (TF-IDF fitted on that scope's card-texts only); otherwise it starts one.
4. Apply §5.1 votes (independence + served_to subtraction), §5.2 inheritance,
   §5.3 freshness (last_closed_at), status = shared iff votes >= K and not
   stale, stale iff age rule fires (pinned `--now` clock).
5. Write cards back (upsert by card_id) + cursor {last_dialogue_count, last_run_at}.

Determinism: TF-IDF vocab iterates sorted; canonical = oldest created_at (tie:
smaller card_id); re-running on an unchanged store is a no-op (C-CL9), detected
via the store sha recorded in the cursor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from clock import RunClock
from schema import card_text, validate_card
from store import read_jsonl, write_jsonl
from tfidf import TfidfModel


def compute_votes(canonical: dict, members: list[dict]) -> tuple[int, str]:
    """SPEC §5.1 — rebuild from scratch. Returns (votes, independence_mode)."""
    served = {s["dialogue_id"] for s in canonical.get("served_to", [])}
    candidates = {canonical["receipt"]["source_dialogue_id"]}
    for m in members:
        candidates.add(m["receipt"]["source_dialogue_id"])
    candidates -= served  # anti-echo: served dialogues never vote

    canon_agent = canonical["receipt"].get("agent_id")
    if not canon_agent:
        canon_agent = "unknown"
    if all((_agent_of(c) in (None, "", "unknown")) for c in [canonical] + members):
        return len(candidates), "dialogue-only"
    keep = set()
    for d in candidates:
        if d == canonical["receipt"]["source_dialogue_id"]:
            keep.add(d)  # the first card always counts
            continue
        agent = _agent_of(member_by_dialogue(canonical, members, d))
        if agent != canon_agent:
            keep.add(d)
    return len(keep), "agent+dialogue"


def _agent_of(card: dict | None) -> str:
    if card is None:
        return "unknown"
    return card["receipt"].get("agent_id") or "unknown"


def member_by_dialogue(canonical: dict, members: list[dict], dialogue_id: str) -> dict | None:
    if canonical["receipt"]["source_dialogue_id"] == dialogue_id:
        return canonical
    for m in members:
        if m["receipt"]["source_dialogue_id"] == dialogue_id:
            return m
    return None


def inherit_fields(canonical: dict, members: list[dict]) -> dict:
    """SPEC §5.2 — fill holes from the oldest member; never overwrite non-none."""
    ordered = sorted(members, key=lambda m: (m.get("created_at", ""), m["card_id"]))
    if not canonical.get("problem_shape"):
        for m in ordered:
            if m.get("problem_shape"):
                canonical["problem_shape"] = m["problem_shape"]
                break
    for f in ("constraint", "unlock"):
        if canonical.get(f) in (None, "", "none"):
            for m in ordered:
                if m.get(f) not in (None, "", "none"):
                    canonical[f] = m[f]
                    break
    seen = set()
    ww = []
    for item in canonical.get("what_worked", []) + [i for m in ordered for i in m.get("what_worked", [])]:
        if item not in seen:
            seen.add(item)
            ww.append(item)
        if len(ww) >= 8:
            break
    canonical["what_worked"] = ww
    canonical["contains_pii"] = bool(canonical.get("contains_pii")) or any(
        m.get("contains_pii") for m in members)
    return canonical


def last_closed_at(canonical: dict, members: list[dict]) -> str | None:
    """SPEC §5.3 — max(closed_at) over canonical + members that have one."""
    times = [c["receipt"]["closed_at"] for c in [canonical] + members
             if c["receipt"].get("closed_at")]
    if not times:
        return None
    return max(times)


def cluster_pass(cards: list[dict], dialogues: list[dict], cfg: dict,
                 clock: RunClock, pass_offset: int = 0) -> dict:
    """Run the greedy per-scope clustering; returns stats.

    Mutates nothing — returns (new_cards, stats) via the caller writing.
    """
    by_scope: dict[str, list[dict]] = {}
    for c in cards:
        if c.get("status") in ("private", "shared") and c.get("role") == "canonical":
            by_scope.setdefault(c["receipt"]["scope"], []).append(c)

    merged_count = promoted_count = already_shared = stale_count = 0
    clusters_formed = 0
    unlock_conflict = 0
    independence_mode = None

    # working copy; untouched cards pass through
    out = {c["card_id"]: dict(c) for c in cards}
    card_index = {c["card_id"]: c for c in cards}

    for scope in sorted(by_scope):
        cands = sorted(by_scope[scope], key=lambda c: (c.get("created_at", ""), c["card_id"]))
        clusters: list[list[dict]] = []  # each cluster holds member cards in order
        canonicals: list[dict] = []
        texts = [card_text(c) for c in cands]
        model = TfidfModel(texts) if texts else None
        for i, c in enumerate(cands):
            if c.get("members"):
                # An established canonical (it already has members from an
                # earlier pass) is a SEED on later passes — it must never be
                # absorbed into another cluster. Its existing members travel
                # with it (inheritance / votes / freshness need them). This is
                # what keeps re-runs stable (SPEC §6.3 "A later run MUST be
                # stable"; C-CL9).
                canonicals.append(dict(c))
                clusters.append([dict(card_index[m]) for m in c["members"]
                                 if m in card_index])
                continue
            best = None
            if model is not None:
                for j, canon in enumerate(canonicals):
                    if model.cosine(texts[i], card_text(canon)) >= cfg["CLUSTER_THRESHOLD"]:
                        best = j
                        break
            if best is None:
                canonicals.append(dict(c))
                clusters.append([])
            else:
                clusters[best].append(dict(c))
        for ci, canon in enumerate(canonicals):
            clusters_formed += 1
            members = clusters[ci]
            # inheritance + freshness + votes + status
            canon = inherit_fields(canon, members)
            lca = last_closed_at(canon, members)
            canon["receipt"]["last_closed_at"] = lca or canon["receipt"].get("closed_at")
            votes, mode = compute_votes(canon, members)
            if independence_mode is None:
                independence_mode = mode
            canon["votes"] = votes
            canon["members"] = [m["card_id"] for m in members]
            newly_merged = 0
            for m in members:
                was_merged_before = (m.get("status") == "merged")
                m["status"] = "merged"
                m["role"] = "member"
                m["cluster_id"] = canon["card_id"]
                if not was_merged_before:
                    newly_merged += 1
            merged_count += newly_merged
            now = clock.now()
            stale = False
            if lca:
                age = clock.age_days(lca)
                if age is not None and age > cfg["STALE_AFTER_DAYS"]:
                    stale = True
            was_shared = canon.get("status") == "shared"
            if votes >= cfg["K_INDEPENDENT"] and not stale:
                if not was_shared:
                    promoted_count += 1
                canon["status"] = "shared"
            else:
                canon["status"] = "stale" if stale else "private"
            if was_shared and canon.get("status") == "shared":
                already_shared += 1
            if stale:
                stale_count += 1
            canon["updated_at"] = clock.at(1000 + ci + pass_offset)
            out[canon["card_id"]] = canon
            for m in members:
                m["updated_at"] = clock.at(1000 + ci + pass_offset)
                out[m["card_id"]] = m
            # unlock_conflict: two different non-none unlocks inside one cluster
            unlocks = {canon.get("unlock")}
            unlocks.update(m.get("unlock") for m in members)
            non_none = {u for u in unlocks if u and u != "none"}
            if len(non_none) > 1:
                unlock_conflict += 1

    new_cards = [out[cid] for cid in (c["card_id"] for c in cards)]
    return {
        "cards": new_cards,
        "scopes": len(by_scope),
        "clusters_formed": clusters_formed,
        "merged": merged_count,
        "promoted": promoted_count,
        "already_shared": already_shared,
        "stale": stale_count,
        "unlock_conflict": unlock_conflict,
        "independence": independence_mode or "n/a",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cluster + promote + stale (SPEC §6.3). Deterministic, no LLM.")
    ap.add_argument("--cards", required=True, help="cards.jsonl")
    ap.add_argument("--dialogues", required=True, help="dialogues.jsonl (row count drives the cursor)")
    ap.add_argument("--force", action="store_true", help="run regardless of the 100-chat cursor")
    ap.add_argument("--now", default=None, help="pinned staleness clock ISO (default: now)")
    ap.add_argument("--cluster-threshold", type=float, default=None)
    ap.add_argument("--k-independent", type=int, default=None)
    ap.add_argument("--stale-after-days", type=int, default=None)
    ap.add_argument("--cluster-every-n", type=int, default=None)
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "CLUSTER_THRESHOLD": args.cluster_threshold if args.cluster_threshold is not None
            else cfgmod.DEFAULTS["CLUSTER_THRESHOLD"],
        "K_INDEPENDENT": args.k_independent if args.k_independent is not None
            else cfgmod.DEFAULTS["K_INDEPENDENT"],
        "STALE_AFTER_DAYS": args.stale_after_days if args.stale_after_days is not None
            else cfgmod.DEFAULTS["STALE_AFTER_DAYS"],
        "CLUSTER_EVERY_N_CHATS": args.cluster_every_n if args.cluster_every_n is not None
            else cfgmod.DEFAULTS["CLUSTER_EVERY_N_CHATS"],
    })

    cards_path = Path(args.cards)
    dialogues_path = Path(args.dialogues)
    cursor_path = cards_path.parent / "cluster_cursor.json"
    cursor: dict = {"last_dialogue_count": 0}
    if cursor_path.exists():
        cursor = json.loads(cursor_path.read_text())

    n = len(read_jsonl(dialogues_path))
    if n - cursor["last_dialogue_count"] < cfg["CLUSTER_EVERY_N_CHATS"] and not args.force:
        remaining = cfg["CLUSTER_EVERY_N_CHATS"] - (n - cursor["last_dialogue_count"])
        print(json.dumps({"ran": False, "remaining": remaining,
                          "clusters_formed": 0, "merged": 0, "promoted": 0,
                          "already_shared": 0, "stale": 0, "scopes": 0,
                          "independence": cursor.get("independence", "n/a"),
                          "unlock_conflict": 0, "reason": "cursor gate"}))
        return 0

    cards = read_jsonl(cards_path)

    # C-CL9 no-op: store unchanged since the last successful pass. Fires with
    # or without --force (--force only bypasses the 100-chat cursor gate; a
    # store that is byte-identical needs no recompute).
    store_sha = hashlib.sha256("".join(
        json.dumps(c, sort_keys=True) + "\n" for c in cards).encode()).hexdigest()
    if cursor.get("last_cards_sha") == store_sha:
        if n != cursor.get("last_dialogue_count", 0):
            # dialogues grew but produced no new cards: advance the cursor
            cursor["last_dialogue_count"] = n
            cursor["last_run_at"] = cfgmod.utcnow_iso()
            cursor_path.write_text(json.dumps(cursor, indent=1), encoding="utf-8")
        print(json.dumps({"ran": False, "remaining": 0, "clusters_formed": 0,
                          "merged": 0, "promoted": 0, "already_shared": 0,
                          "stale": 0, "scopes": 0,
                          "independence": cursor.get("independence", "n/a"),
                          "unlock_conflict": 0, "reason": "store unchanged"}))
        return 0

    clock = RunClock(args.now) if args.now else RunClock(cfgmod.utcnow_iso())
    t0 = time.time()
    result = cluster_pass(cards, read_jsonl(dialogues_path), cfg, clock)
    new_cards = result["cards"]

    for c in new_cards:
        errs = validate_card(c)
        if errs:
            raise RuntimeError(f"cluster produced invalid card {c['card_id']}: {errs}")
    write_jsonl(cards_path, new_cards)
    # record the POST-pass store sha: a re-run on this exact store is a no-op
    post_sha = hashlib.sha256("".join(
        json.dumps(c, sort_keys=True) + "\n" for c in new_cards).encode()).hexdigest()
    cursor["last_dialogue_count"] = n
    cursor["last_run_at"] = clock.now()
    cursor["last_cards_sha"] = post_sha
    cursor["independence"] = result["independence"]
    cursor_path.write_text(json.dumps(cursor, indent=1), encoding="utf-8")

    result["ran"] = True
    result["wall_clock_s"] = round(time.time() - t0, 3)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
