#!/usr/bin/env python3
"""cluster.py — deterministic same-scope clustering (NO LLM, C-L4).

    python bin/cluster.py --cards data/cards.jsonl --dialogues data/dialogues.jsonl \\
        [--force] [--cursor data/cluster_cursor.json] [--now ISO] [--set k=v]

- Reads the global cursor (last_dialogue_count, default 0). If
  n_dialogues - last < CLUSTER_EVERY_N_CHATS and no --force: prints
  {"ran": false, "remaining": N} and exits 0 (C-CL1).
- Per scope: candidates = cards with status ∈ {private, shared} AND
  role=canonical, oldest first (created_at, tie: card_id). Greedy: each card
  joins the FIRST existing cluster whose canonical card-text cosine ≥
  CLUSTER_THRESHOLD (TF-IDF fitted on THIS scope's candidate card-texts),
  else starts a new cluster. Oldest stays canonical.
- Applies §5.1 votes (rebuilt from scratch; served_to subtracted;
  independence rule), §5.2 inheritance (holes filled from the oldest member,
  what_worked dedup union capped at 8, contains_pii OR), §5.3 freshness
  (last_closed_at = max closed_at).
- status=shared iff votes >= K_INDEPENDENT and not stale; age-stale fires
  when now - last_closed_at > STALE_AFTER_DAYS (canonical stays canonical,
  members stay merged). now is pinned --now; datetime.now() is NEVER called
  here.
- Merged cards are never re-seeded, never re-merged, never un-merged:
  re-running on unchanged inputs is a no-op with byte-identical cards
  (C-CL7/C-CL9).
- unlock_conflict requires ground-truth labels, which are NOT available to
  this deterministic step (they are stripped at ingest, C-L2). cluster.py
  prints unlock_conflict: 0 with this note; eval.py computes the real number
  from labels + cluster membership into metrics.json (brief §5).

Prints {ran, scopes, clusters_formed, merged, promoted, already_shared,
stale, independence, unlock_conflict, note}.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import os
import sys

import config as cfg
import jsonio as hio
from common import TFIDF, card_text, days_since, now_iso


def load_store(cards_path):
    store = {}
    if os.path.exists(cards_path):
        for card in hio.read_jsonl(cards_path):
            store[card["card_id"]] = card
    return store


def _dialogue_lookup(dialogues_path):
    lookup = {}
    if os.path.exists(dialogues_path):
        for d in hio.read_jsonl(dialogues_path):
            lookup[d.get("dialogue_id")] = d
    return lookup


def _agent_of(card, dialogues):
    """receipt.agent_id, falling back to the dialogues file (brief §4)."""
    aid = (card.get("receipt") or {}).get("agent_id")
    if aid:
        return aid
    d = dialogues.get((card.get("receipt") or {}).get("source_dialogue_id"))
    if d:
        return d.get("agent_id", "unknown")
    return "unknown"


def _closed_at_of(card, dialogues):
    """receipt.closed_at, falling back to the dialogues file."""
    ca = (card.get("receipt") or {}).get("closed_at")
    if ca:
        return ca
    d = dialogues.get((card.get("receipt") or {}).get("source_dialogue_id"))
    if d:
        return d.get("closed_at")
    return None


def _sort_key(card):
    return (card.get("created_at") or "", card.get("card_id") or "")


def compute_votes(canonical, members, dialogues):
    """SPEC §5.1 — returns (votes, independence_mode)."""
    candidates = {canonical["receipt"]["source_dialogue_id"]}
    for m in members:
        candidates.add(m["receipt"]["source_dialogue_id"])
    served = {entry.get("dialogue_id")
              for entry in canonical.get("served_to", [])}
    candidates -= served

    canonical_agent = _agent_of(canonical, dialogues)
    agents = {_agent_of(c, dialogues) for c in [canonical] + members
              if c["receipt"]["source_dialogue_id"] in candidates}
    all_unknown = not agents or all(
        a in (None, "", "unknown") for a in agents)

    if all_unknown:
        return len(candidates), "dialogue-only"
    kept = 0
    for c in [canonical] + members:
        cid = c["receipt"]["source_dialogue_id"]
        if cid not in candidates:
            continue
        if cid == canonical["receipt"]["source_dialogue_id"]:
            kept += 1                      # the first card always counts
        elif _agent_of(c, dialogues) != canonical_agent:
            kept += 1
    return kept, "agent+dialogue"


def compute_last_closed_at(canonical, members, dialogues):
    values = [_closed_at_of(canonical, dialogues)]
    for m in members:
        values.append(_closed_at_of(m, dialogues))
    values = [v for v in values if v]
    if not values:
        return None
    return max(values)


def inherit_fields(canonical, members):
    """SPEC §5.2 — fill canonical holes from the OLDEST member that has a
    value; what_worked = dedup union in first-seen order, capped at 8."""
    ordered_members = sorted(members, key=_sort_key)  # oldest first
    canon_ps = (canonical.get("problem_shape") or "").strip()
    if not canon_ps:
        for m in ordered_members:
            v = (m.get("problem_shape") or "").strip()
            if v:
                canonical["problem_shape"] = v
                break
    if canonical.get("constraint") == "none":
        for m in ordered_members:
            v = m.get("constraint")
            if v and v != "none":
                canonical["constraint"] = v
                break
    if canonical.get("unlock") == "none":
        for m in ordered_members:
            v = m.get("unlock")
            if v and v != "none":
                canonical["unlock"] = v
                break
    union = []
    seen = set()
    for c in [canonical] + ordered_members:
        for item in c.get("what_worked", []):
            if item not in seen:
                seen.add(item)
                union.append(item)
    canonical["what_worked"] = union[:cfg.DEFAULTS["MAX_WORKED"]]
    canonical["contains_pii"] = bool(canonical.get("contains_pii")) or any(
        m.get("contains_pii") for m in ordered_members)
    return canonical


def run_cluster(cards_path, dialogues_path, force=False, cursor_path=None,
                pinned_now=None, overrides=None):
    """Core cluster. Returns the summary dict (also printed by main())."""
    cfg_obj = cfg.Config(overrides)
    if pinned_now is None:
        raise ValueError("cluster.py requires --now (pinned determinism, "
                         "brief §6)")

    if cursor_path is None:
        cursor_path = os.path.join(
            os.path.dirname(cards_path) or ".", "cluster_cursor.json")
    last = 0
    if os.path.exists(cursor_path):
        last = int(hio.read_json(cursor_path).get("last_dialogue_count", 0) or 0)

    n_dialogues = hio.row_count(dialogues_path) if os.path.exists(
        dialogues_path) else 0
    if n_dialogues - last < cfg_obj.CLUSTER_EVERY_N_CHATS and not force:
        remaining = max(0, cfg_obj.CLUSTER_EVERY_N_CHATS -
                        (n_dialogues - last))
        return {"ran": False, "remaining": remaining}

    store = load_store(cards_path)
    dialogues = _dialogue_lookup(dialogues_path)

    # pre-existing cluster structure (C-CL7/C-CL9): already-merged members
    # stay on their canonical card across runs. They are never candidates, so
    # the greedy below must re-attach them to their stored canonical instead
    # of leaving the canonical to re-form as a singleton.
    pre_members = {}
    for card in store.values():
        if card.get("status") == "merged" and card.get("role") == "member":
            pre_members.setdefault(card.get("cluster_id"), []).append(card)

    # group candidates per scope
    scopes = {}
    for card in store.values():
        if card.get("status") in ("private", "shared") and \
           card.get("role") == "canonical":
            scopes.setdefault(card["receipt"]["scope"], []).append(card)

    prev_status = {cid: store[cid].get("status") for cid in store}

    clusters_formed = 0
    merged = 0
    promoted = 0
    already_shared = 0
    stale = 0
    independence = "agent+dialogue"
    used_dialogue_only = False

    for scope in sorted(scopes):
        candidates = sorted(scopes[scope], key=_sort_key)
        if not candidates:
            continue
        texts = [card_text(c) for c in candidates]
        tfidf = TFIDF().fit(texts)
        clusters = []  # list of [canonical, [members]]
        for i, card in enumerate(candidates):
            # members this canonical already absorbed in an earlier run
            carried = list(pre_members.get(card["card_id"], []))
            joined = None
            for cl in clusters:
                if tfidf.score(card_text(card), card_text(cl[0])) >= \
                        cfg_obj.CLUSTER_THRESHOLD:
                    joined = cl
                    break
            if joined is None:
                clusters.append([card, carried])
            else:
                joined[1].append(card)
                joined[1].extend(carried)
        for canonical, members in clusters:
            if members:
                members_sorted = sorted(members, key=_sort_key)
                newly_merged = [m for m in members_sorted
                                if m.get("status") != "merged"]
                if newly_merged:
                    clusters_formed += 1
                    merged += len(newly_merged)
                for m in members_sorted:
                    m["status"] = "merged"
                    m["role"] = "member"
                    m["cluster_id"] = canonical["card_id"]
                canonical["members"] = [m["card_id"] for m in members_sorted]
                inherit_fields(canonical, members_sorted)
            # freshness §5.3
            lca = compute_last_closed_at(canonical, members, dialogues)
            receipt = canonical["receipt"]
            if lca is not None:
                receipt["last_closed_at"] = lca
            # votes §5.1
            votes, mode = compute_votes(canonical, members, dialogues)
            if mode == "dialogue-only":
                used_dialogue_only = True
            canonical["votes"] = votes
            # status
            stale_now = False
            if lca is not None:
                d = days_since(pinned_now, lca)
                if d is not None and d > cfg_obj.STALE_AFTER_DAYS:
                    stale_now = True
            if stale_now:
                canonical["status"] = "stale"
                if prev_status.get(canonical["card_id"]) != "stale":
                    stale += 1
            elif votes >= cfg_obj.K_INDEPENDENT:
                if prev_status.get(canonical["card_id"]) == "shared":
                    already_shared += 1
                else:
                    promoted += 1
                canonical["status"] = "shared"
            else:
                canonical["status"] = "private"
            canonical["updated_at"] = pinned_now

    if used_dialogue_only:
        independence = "dialogue-only"

    # write whole store, deterministic order
    ordered = [store[k] for k in sorted(store)]
    hio.write_jsonl(cards_path, ordered)

    hio.write_json(cursor_path,
                   {"last_dialogue_count": n_dialogues,
                    "last_run_at": pinned_now})

    return {
        "ran": True,
        "scopes": len(scopes),
        "clusters_formed": clusters_formed,
        "merged": merged,
        "promoted": promoted,
        "already_shared": already_shared,
        "stale": stale,
        "independence": independence,
        "unlock_conflict": 0,
        "note": ("unlock_conflict requires ground-truth labels, which are "
                 "stripped at ingest (C-L2); eval.py computes the real value "
                 "from labels + cluster membership into metrics.json"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cluster.py",
        description="Deterministic same-scope clustering (SPEC §5/§6.3).")
    ap.add_argument("--cards", dest="cards_path", required=True)
    ap.add_argument("--dialogues", dest="dialogues_path", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--cursor", dest="cursor_path", default=None)
    ap.add_argument("--now", default=None,
                    help="pinned ISO timestamp (required; brief §6)")
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    summary = run_cluster(args.cards_path, args.dialogues_path, args.force,
                          args.cursor_path, args.now,
                          cfg.parse_overrides(args.set))
    print(hio.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
