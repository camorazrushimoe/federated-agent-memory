#!/usr/bin/env python3
"""cluster.py — same-scope similar cards become one card (SPEC §6.3, §5).

Usage:
  python bin/cluster.py --cards data/cards.jsonl --dialogues data/dialogues.jsonl
  python bin/cluster.py --cards ... --dialogues ... --force

Deterministic. No LLM. Greedy clustering oldest-first within each scope,
card-text cosine >= CLUSTER_THRESHOLD (0.35) against the canonical only.
Applies §5 (votes/status), §5.1 (independence), §5.2 (inheritance),
§5.3 (freshness). Writes cards back (upsert by card_id) and the cursor
{last_dialogue_count, last_run_at} only when it ran.

Print JSON {ran, scopes, clusters_formed, merged, promoted, already_shared,
stale, independence, unlock_conflict}.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402


def cluster_scope(cards, store_by_id, cfg):
    """Run one scope's pass. cards: eligible canonical cards sorted by
    (created_at, card_id). store_by_id: full store map card_id -> card (to
    resolve pre-existing members, which are never re-clustered — C-CL7).

    Stability rule (SPEC §6.3, C-CL9): a canonical that already has members
    (a pre-existing cluster) keeps its cluster — its members stay with it and
    it becomes a join target for new cards, never a joiner itself. Only cards
    with no members are processed greedily: they join the first existing
    cluster (in canonical-age order) whose canonical card-text cosine >=
    threshold, else start a new cluster. This makes a re-run on unchanged
    inputs a byte-identical no-op."""
    texts = [H.card_text(c) for c in cards]
    vecs, _ = H.build_tfidf(texts)
    card_vec = {c["card_id"]: v for c, v in zip(cards, vecs)}
    clusters = []  # {canon, members, canon_vec}
    for c in cards:
        if c.get("members"):
            mbrs = [store_by_id[m] for m in c["members"] if m in store_by_id]
            clusters.append({"canon": c, "members": list(mbrs),
                             "canon_vec": card_vec[c["card_id"]]})
    for card in cards:
        if card.get("members"):
            continue  # pre-existing cluster seed
        joined = None
        for cl in clusters:
            if H.cosine(card_vec[card["card_id"]],
                        cl["canon_vec"]) >= cfg["CLUSTER_THRESHOLD"]:
                joined = cl
                break
        if joined is None:
            clusters.append({"canon": card, "members": [],
                             "canon_vec": card_vec[card["card_id"]]})
        else:
            joined["members"].append(card)
    return clusters


def run_pass(cards, cfg, now, prev_state):
    """One full cluster pass over the whole store.
    prev_state: map card_id -> card as it was before the pass (for the
    clusters_formed/promoted/already_shared/stale transition counts).
    Returns (new_cards, summary)."""
    new_cards = []
    from typing import Any
    summary = {"scopes": 0, "clusters_formed": 0, "merged": 0,
               "promoted": 0, "already_shared": 0, "stale": 0,
               "unlock_conflict": 0}  # type: dict[str, Any]
    modes = set()
    by_scope = {}
    for c in cards:
        if c["status"] in ("private", "shared") and c["role"] == "canonical":
            by_scope.setdefault(c["receipt"]["scope"], []).append(c)
    summary["scopes"] = len(by_scope)
    store_by_id = {c["card_id"]: c for c in cards}
    for scope in sorted(by_scope):
        elig = sorted(by_scope[scope],
                      key=lambda c: (c["created_at"] or "", c["card_id"]))
        clusters = cluster_scope(elig, store_by_id, cfg)
        for cl in clusters:
            canon, members = cl["canon"], cl["members"]
            cid = canon["card_id"]
            before = prev_state.get(cid)
            # capture the PRE-mutation state: prev_state aliases the same
            # dict objects, so reading status after mutation would always
            # see the new value (the stale-count aliasing bug).
            was_status = before.get("status") if before else None
            before_members = len(before.get("members") or []) if before else 0

            # inherit §5.2 — fill holes only; never overwrite a non-none
            # canonical value
            if not (canon.get("problem_shape") or "").strip():
                for m in sorted(members, key=lambda c: (c["created_at"] or "",
                                                        c["card_id"])):
                    if (m.get("problem_shape") or "").strip():
                        canon["problem_shape"] = m["problem_shape"]
                        break
            if (canon.get("constraint") or "none").strip().lower() == "none":
                for m in sorted(members, key=lambda c: (c["created_at"] or "",
                                                        c["card_id"])):
                    if (m.get("constraint") or "none").strip().lower() != "none":
                        canon["constraint"] = m["constraint"]
                        break
            if (canon.get("unlock") or "none").strip().lower() == "none":
                for m in sorted(members, key=lambda c: (c["created_at"] or "",
                                                        c["card_id"])):
                    if (m.get("unlock") or "none").strip().lower() != "none":
                        canon["unlock"] = m["unlock"]
                        break
            ww = []
            for m in [canon] + sorted(members, key=lambda c: (
                    c["created_at"] or "", c["card_id"])):
                for item in m.get("what_worked") or []:
                    if item not in ww:
                        ww.append(item)
            canon["what_worked"] = ww[:8]
            if any(m.get("contains_pii") for m in
                   [canon] + members) or canon.get("contains_pii"):
                canon["contains_pii"] = True

            # votes / last_closed_at / status (§5.1, §5.3)
            votes, mode, _ = H.compute_votes(canon, members)
            modes.add(mode)
            canon["votes"] = votes
            new_last = H.last_closed_at(canon, members)
            if new_last:
                canon["receipt"]["last_closed_at"] = new_last
            canon["members"] = [m["card_id"] for m in members]
            newly_merged = 0
            for m in members:
                m_prev = prev_state.get(m["card_id"])
                if not m_prev or m_prev.get("status") != "merged":
                    newly_merged += 1  # a transition to merged THIS pass
                m["status"] = "merged"
                m["role"] = "member"
                m["cluster_id"] = cid
            status = H.apply_status(canon, members, cfg, now)
            if status == "stale":
                canon["status"] = "stale"
                if was_status != "stale":
                    summary["stale"] += 1
            elif status == "shared":
                canon["status"] = "shared"
                if was_status == "shared":
                    summary["already_shared"] += 1
                else:
                    summary["promoted"] += 1
            else:
                canon["status"] = "private"

            # counts
            if len(members) and before_members == 0:
                summary["clusters_formed"] += 1
            summary["merged"] += newly_merged
            unlocks = {canon["unlock"]} if canon["unlock"] and canon[
                "unlock"].lower() != "none" else set()
            for m in members:
                if m["unlock"] and m["unlock"].lower() != "none":
                    unlocks.add(m["unlock"])
            if len(unlocks) > 1:
                summary["unlock_conflict"] += 1

            new_cards.append(canon)
            new_cards.extend(members)

    # cards not eligible for clustering are carried through untouched
    touched = {c["card_id"] for c in new_cards}
    for c in cards:
        if c["card_id"] not in touched:
            new_cards.append(c)

    # dedupe safety (a card appears exactly once)
    new_cards = H.upsert_by_key(new_cards, "card_id")
    summary["independence"] = ("dialogue-only" if not modes or modes == {
        "dialogue-only"} else "agent+dialogue")
    return new_cards, summary


def main():
    ap = argparse.ArgumentParser(description="Cluster cards (SPEC §6.3)")
    ap.add_argument("--cards", required=True)
    ap.add_argument("--dialogues", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cursor-file", default=None)
    ap.add_argument("--now", default=None,
                    help="ISO 'now' for the age rule (deterministic runs)")
    ap.add_argument("--config", action="append", default=[])
    args = ap.parse_args()

    cfg = H.load_config(args.config)
    if not os.path.exists(args.dialogues):
        raise SystemExit(f"dialogues file missing: {args.dialogues}")
    n = sum(1 for _ in open(args.dialogues, "r", encoding="utf-8")
            if _.strip())
    cursor_file = args.cursor_file or os.path.join(
        os.path.dirname(os.path.abspath(args.cards)), "cluster_cursor.json")
    last = 0
    if os.path.exists(cursor_file):
        last = H.load_json(cursor_file).get("last_dialogue_count", 0)
    if n - last < cfg["CLUSTER_EVERY_N_CHATS"] and not args.force:
        H.print_json({"ran": False,
                      "remaining": cfg["CLUSTER_EVERY_N_CHATS"] - (n - last)})
        return

    cards = H.read_jsonl(args.cards)
    prev_state = {c["card_id"]: c for c in cards}
    now = args.now or H.now_iso(cfg)
    new_cards, summary = run_pass(cards, cfg, now, prev_state)
    H.write_jsonl(args.cards, new_cards, mode="w")
    H.write_json(cursor_file,
                 {"last_dialogue_count": n, "last_run_at": H.now_iso(cfg)})
    summary["ran"] = True
    H.print_json(summary)


if __name__ == "__main__":
    main()
