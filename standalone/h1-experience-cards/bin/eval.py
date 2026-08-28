#!/usr/bin/env python3
"""eval.py — offline evaluation against ground truth (SPEC §6.8, EVAL-PLAN §4).

Two modes:

Mode A — self-contained (SPEC §6.8):
  python bin/eval.py --dialogues data/dialogues.jsonl --cards data/cards.jsonl \
      --labels GT.jsonl --model <model> --out runs/x [--replay-dir raw/extract]
  Holds out the last 20% of dialogues (file order), extracts on the first 80%,
  forces one cluster pass, serves each hold-out dialogue, then scores.

Mode B — scoring-only (run_experiment.py orchestration; T and baselines):
  python bin/eval.py --score --pool-dialogues data/dialogues.jsonl \
      --cards data/cards.jsonl --labels GT.jsonl \
      --holdout-dialogues data/holdout_dialogues.jsonl \
      --packets-dir packets --baseline T|B0|B1|B2 --run-id X --out runs/x

C-EV5: T, B0, B1 and B2 all run through the SAME scoring function
(score_outcomes) — one implementation, selected by --baseline.

Writes metrics.json + per_dialogue.jsonl into --out. Prints JSON to stdout
unless --out is given.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402
from match import match  # noqa: E402
from serve import serve  # noqa: E402
from cluster import run_pass  # noqa: E402


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------


def load_label_map(path):
    out = {}
    if path and os.path.exists(path):
        for r in H.read_jsonl(path):
            if "dialogue_id" in r and "unlock_guideline" in r:
                out[r["dialogue_id"]] = r["unlock_guideline"]
    return out


def attach_card_labels(cards, labels_by_dialogue):
    """canonical card -> label: majority unlock_guideline of the dialogues in
    its cluster (canonical + members), ties broken by the canonical's own
    dialogue (EVAL-PLAN §4.1)."""
    by_id = {c["card_id"]: c for c in cards}
    out = {}
    for c in cards:
        if c["role"] != "canonical" or c["status"] == "rejected":
            continue
        ids = [c["receipt"]["source_dialogue_id"]]
        for m in (c.get("members") or []):
            if m in by_id:
                ids.append(by_id[m]["receipt"]["source_dialogue_id"])
        labs = [labels_by_dialogue[i] for i in ids if i in labels_by_dialogue]
        if not labs:
            continue
        counts = {}
        for l in labs:
            counts[l] = counts.get(l, 0) + 1
        mx = max(counts.values())
        tied = sorted(l for l, v in counts.items() if v == mx)
        canon_lab = labels_by_dialogue.get(c["receipt"]["source_dialogue_id"])
        out[c["card_id"]] = canon_lab if canon_lab in tied else tied[0]
    return out


# --------------------------------------------------------------------------
# The ONE scoring function (C-EV5)
# --------------------------------------------------------------------------


def score_outcomes(rows, n_holdout):
    """rows: list of per-dialogue dicts with
    {dialogue_id, true_label, packet_text, packet_card_ids, card_labels,
     card_votes, packet_scores, smoke_overlap_words}.
    Returns (primary, counts) with primary = {unlock_hit_label, wrong,
    abstain} and counts = {hit, wrong, abstain}."""
    hit = wrong = abstain = 0
    for r in rows:
        if r["packet_card_ids"]:
            if r["true_unlock_guideline"] in r["card_labels"]:
                hit += 1
            else:
                wrong += 1
        else:
            abstain += 1
    assert hit + wrong + abstain == n_holdout, (
        f"hit+wrong+abstain {hit}+{wrong}+{abstain} != n_holdout {n_holdout}")
    if n_holdout == 0:
        return {"unlock_hit_label": 0.0, "wrong": 0.0, "abstain": 0.0}, {
            "hit": 0, "wrong": 0, "abstain": 0}
    h = round(hit / n_holdout, 6)
    w = round(wrong / n_holdout, 6)
    a = round(1.0 - h - w, 6)
    primary = {"unlock_hit_label": h, "wrong": w, "abstain": a}
    counts = {"hit": hit, "wrong": wrong, "abstain": abstain}
    # C-EV1: the three ratios sum to exactly 1.0 by construction
    assert abs((h + w + a) - 1.0) < 1e-12
    return primary, counts


def smoke_overlap(packet_text, true_label):
    pw = H.content_words(packet_text)
    lw = H.content_words(true_label)
    return sorted(pw & lw)


# --------------------------------------------------------------------------
# Secondary metrics from the store (T arm)
# --------------------------------------------------------------------------


def store_metrics(cards, n_pool_dialogues, labels_by_dialogue, rows,
                  independence):
    by_id = {c["card_id"]: c for c in cards}
    accepted = [c for c in cards if c["status"] != "rejected"]
    rejected = [c for c in cards if c["status"] == "rejected"]
    canonicals = [c for c in accepted if c["role"] == "canonical"]
    shared = [c for c in canonicals if c["status"] == "shared"]

    extract_yield = round(len(accepted) / n_pool_dialogues, 6) if (
        n_pool_dialogues) else 0.0
    reject_rate = round(len(rejected) / len(cards), 6) if cards else 0.0
    # cluster_rate: canonical after cluster / accepted before cluster
    # (accepted before cluster == accepted, since every fresh card is
    # canonical; after clustering canonicals are role=canonical)
    cluster_rate = round(len(canonicals) / len(accepted), 6) if accepted else 0.0
    shared_rate = round(len(shared) / len(canonicals), 6) if canonicals else 0.0

    votes_hist = {"1": 0, "2": 0, "3+": 0}
    for c in canonicals:
        v = c.get("votes", 0)
        if v >= 3:
            votes_hist["3+"] += 1
        else:
            votes_hist[str(max(v, 1))] += 1

    packet_size_hist = {"1": 0, "2": 0, "3": 0}
    for r in rows:
        n = len(r["packet_card_ids"])
        if n:
            packet_size_hist[str(min(n, 3))] = packet_size_hist.get(
                str(min(n, 3)), 0) + 1

    # cluster purity + unlock_conflict over clusters (incl. singletons)
    clusters = {}   # cluster_id -> list of cards (canonical + members)
    for c in accepted:
        clusters.setdefault(c["cluster_id"], []).append(c)
    pure = 0
    conflicts = 0
    for cid, members in clusters.items():
        labs = set()
        has_lab = False
        for c in members:
            l = labels_by_dialogue.get(c["receipt"]["source_dialogue_id"])
            if l:
                has_lab = True
                labs.add(l)
        if has_lab and len(labs) == 1:
            pure += 1
        elif not has_lab:
            pure += 1  # no labels available: nothing to be impure about
        unlocks = set()
        for c in members:
            u = (c.get("unlock") or "").strip().lower()
            if u and u != "none":
                unlocks.add(u)
        if len(unlocks) > 1:
            conflicts += 1
    total_clusters = len(clusters)
    cluster_purity = round(pure / total_clusters, 6) if total_clusters else 0.0

    serve_rate = round(sum(1 for r in rows if r["packet_card_ids"]) /
                       len(rows), 6) if rows else 0.0
    unlock_smoke = round(sum(1 for r in rows if r["smoke_overlap_words"]) /
                         len(rows), 6) if rows else 0.0
    dup = sum(1 for r in rows if len(r["packet_card_ids"]) != len(
        {c for c in r["packet_card_ids"]}))
    # duplicate_in_packet = two cards of one cluster in one packet
    dup = 0
    for r in rows:
        cids = r["packet_card_ids"]
        cluster_ids = {by_id[c]["cluster_id"] for c in cids if c in by_id}
        if len(cluster_ids) != len(cids):
            dup += 1
    scope_leak = 0  # serve() filters by scope; checked again in C-SV1
    return {
        "unlock_hit_smoke": unlock_smoke,
        "serve_rate": serve_rate,
        "extract_yield": extract_yield,
        "reject_rate": reject_rate,
        "cluster_rate": cluster_rate,
        "shared_rate": shared_rate,
        "cluster_purity": cluster_purity,
        "unlock_conflict": conflicts,
        "duplicate_in_packet": dup,
        "scope_leak": scope_leak,
        "independence": independence,
        "votes_hist": votes_hist,
        "packet_size_hist": packet_size_hist,
    }


def derive_independence(cards):
    modes = set()
    by_id = {c["card_id"]: c for c in cards}
    for c in cards:
        if c["role"] != "canonical" or c["status"] == "rejected":
            continue
        members = [by_id[m] for m in (c.get("members") or []) if m in by_id]
        _v, mode, _d = H.compute_votes(c, members)
        modes.add(mode)
    if not modes:
        return "agent+dialogue"
    if modes == {"dialogue-only"}:
        return "dialogue-only"
    return "agent+dialogue"


# --------------------------------------------------------------------------
# Metric assembly
# --------------------------------------------------------------------------


def assemble(run_id, arm, n_holdout, rows, primary, counts, secondary, notes):
    return {
        "run_id": run_id,
        "arm": arm,
        "n_holdout": n_holdout,
        "primary": primary,
        "secondary": secondary,
        "judge": None,
        "notes": notes,
    }


def write_per_dialogue(out_dir, rows):
    H.write_jsonl(os.path.join(out_dir, "per_dialogue.jsonl"), rows,
                  mode="w")


def make_rows_from_packets(records, labels_by_dialogue, card_labels, cards):
    """records: [{dialogue_id, card_ids, scores, packet_text}]."""
    by_id = {c["card_id"]: c for c in cards}
    rows = []
    for rec in records:
        did = rec["dialogue_id"]
        true_label = labels_by_dialogue.get(did)
        card_ids = list(rec.get("card_ids") or [])
        scores = list(rec.get("scores") or [])
        packet_text = rec.get("packet_text") or ""
        labs = [card_labels[c] for c in card_ids if c in card_labels]
        votes = [by_id[c].get("votes", 0) for c in card_ids if c in by_id]
        rows.append({
            "dialogue_id": did,
            "true_unlock_guideline": true_label,
            "packet_card_ids": card_ids,
            "packet_scores": [round(s, 6) for s in scores],
            "card_labels": labs,
            "card_votes": votes,
            "outcome": ("hit" if card_ids and true_label in labs else
                        "wrong" if card_ids else "abstain"),
            "smoke_overlap_words": smoke_overlap(packet_text, true_label)
            if true_label else [],
        })
    return rows


# --------------------------------------------------------------------------
# Baselines (same scoring path; different packet source)
# --------------------------------------------------------------------------


def baseline_rows(arm, holdout_dialogues, labels_by_dialogue, pool_dialogues,
                  cfg):
    rows = []
    for d in holdout_dialogues:
        did = d["dialogue_id"]
        true_label = labels_by_dialogue.get(did)
        qtext = H.customer_text(d)
        if arm == "B0":
            rows.append({"dialogue_id": did, "true_unlock_guideline":
                         true_label, "packet_card_ids": [], "packet_scores":
                         [], "card_labels": [], "card_votes": [],
                         "outcome": "abstain", "smoke_overlap_words": []})
        elif arm == "B2":
            rows.append({"dialogue_id": did, "true_unlock_guideline":
                         true_label, "packet_card_ids": ["oracle"],
                         "packet_scores": [1.0], "card_labels": [true_label],
                         "card_votes": [], "outcome": "hit",
                         "smoke_overlap_words": smoke_overlap(
                             true_label or "", true_label)})
        elif arm == "B1":
            scope = H.scope_of(d["tenant_id"], d["vertical"])
            pool_docs = [H.customer_text(p) for p in pool_dialogues
                         if H.scope_of(p["tenant_id"], p["vertical"]) == scope]
            pool_ids = [p["dialogue_id"] for p in pool_dialogues
                        if H.scope_of(p["tenant_id"], p["vertical"]) == scope]
            best = -1.0
            best_idx = -1
            if pool_docs:
                scores = H.score_query_vs_docs(qtext, pool_docs)
                for i, s in enumerate(scores):
                    if s > best:
                        best, best_idx = s, i
            if best >= cfg["MATCH_THRESHOLD"] and best_idx >= 0:
                claimed = labels_by_dialogue.get(pool_ids[best_idx])
                rows.append({"dialogue_id": did, "true_unlock_guideline":
                             true_label, "packet_card_ids": ["b1-"
                             + pool_ids[best_idx]], "packet_scores":
                             [round(best, 6)], "card_labels": [claimed],
                             "card_votes": [], "outcome":
                             "hit" if claimed == true_label else "wrong",
                             "smoke_overlap_words": smoke_overlap(
                                 pool_docs[best_idx], true_label)})
            else:
                rows.append({"dialogue_id": did, "true_unlock_guideline":
                             true_label, "packet_card_ids": [],
                             "packet_scores": [], "card_labels": [],
                             "card_votes": [], "outcome": "abstain",
                             "smoke_overlap_words": []})
        else:
            raise SystemExit(f"unknown baseline arm {arm!r}")
    return rows


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def common_args(ap):
    ap.add_argument("--out", default=None,
                    help="run dir to write metrics.json / per_dialogue.jsonl")
    ap.add_argument("--run-id", default="local")
    ap.add_argument("--config", action="append", default=[])


def mode_a(args):
    cfg = H.load_config(args.config)
    prompts = H.load_prompts(args.prompts)
    at = args.at or H.now_iso(cfg)
    dialogues = H.read_jsonl(args.dialogues)
    n = len(dialogues)
    n_holdout = max(1, int(n * 0.2)) if n > 5 else 0
    if n_holdout == 0:
        raise SystemExit("eval: need >5 dialogues to hold out 20%")
    pool_d = dialogues[:n - n_holdout]
    holdout_d = dialogues[n - n_holdout:]
    labels = load_label_map(args.labels)
    out_dir = args.out
    os.makedirs(os.path.join(out_dir, "packets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)

    cards_path = os.path.join(out_dir, "data", "cards.jsonl")
    cards = H.read_jsonl(cards_path)
    existing = {c["card_id"] for c in cards}
    todo = [d for d in pool_d if H.card_id_of(d["dialogue_id"]) not in existing]
    if todo:
        tmp = os.path.join(out_dir, "data", "eval_pool_delta.jsonl")
        H.write_jsonl(tmp, todo, mode="w")
        # extract the 80% through the SAME extract.py entry point (no second
        # copy of extraction logic)
        import subprocess
        cmd = [sys.executable, os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "extract.py"),
            "--in", tmp, "--out", cards_path, "--model", args.model,
            "--raw-dir", os.path.join(out_dir, "raw", "extract"),
            "--at", at]
        if args.replay_dir:
            cmd += ["--replay-dir", args.replay_dir]
        if args.base_url:
            cmd += ["--base-url", args.base_url]
        if args.api_key:
            cmd += ["--api-key", args.api_key]
        for kv in args.config:
            cmd += ["--config", kv]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            raise SystemExit("eval: extract failed")
    # force one cluster pass on the 80% store
    run_pass_force(cards_path, args.dialogues, cfg, at)
    cards = H.read_jsonl(cards_path)

    # serve each hold-out dialogue
    records = []
    packets_dir = os.path.join(out_dir, "packets")
    for d in holdout_d:
        packet_text, card_ids, scores = serve(d, cards, cfg, prompts, at,
                                              cards_path=cards_path)
        cards = H.read_jsonl(cards_path)  # reload after serve mutation
        records.append({"dialogue_id": d["dialogue_id"],
                        "card_ids": card_ids, "scores": scores,
                        "packet_text": packet_text})
        with open(os.path.join(packets_dir, f"{d['dialogue_id']}.txt"),
                  "w", encoding="utf-8") as f:
            f.write(packet_text)
    H.write_jsonl(os.path.join(packets_dir, "_served.jsonl"), records,
                  mode="w")

    card_labels = attach_card_labels(cards, labels)
    rows = make_rows_from_packets(records, labels, card_labels, cards)
    finalize_mode_b(args, cfg, out_dir, cards, labels, holdout_d, rows,
                    mode_a_pool_count=len(pool_d))


def run_pass_force(cards_path, dialogues_path, cfg, at):
    import cluster as cluster_mod
    cards = H.read_jsonl(cards_path)
    prev = {c["card_id"]: c for c in cards}
    new_cards, _ = run_pass(cards, cfg, at, prev)
    H.write_jsonl(cards_path, new_cards, mode="w")
    H.write_json(os.path.join(os.path.dirname(cards_path),
                              "cluster_cursor.json"),
                 {"last_dialogue_count": sum(1 for _ in open(
                     dialogues_path) if _.strip()),
                  "last_run_at": at})


def mode_b(args):
    cfg = H.load_config(args.config)
    labels = load_label_map(args.labels)
    holdout_d = H.read_jsonl(args.holdout_dialogues)
    cards = H.read_jsonl(args.cards)
    pool_dialogues = H.read_jsonl(args.pool_dialogues) if (
        args.pool_dialogues and os.path.exists(args.pool_dialogues)) else []
    if args.baseline == "T":
        records = H.read_jsonl(os.path.join(args.packets_dir,
                                            "_served.jsonl"))
        card_labels = attach_card_labels(cards, labels)
        rows = make_rows_from_packets(records, labels, card_labels, cards)
    else:
        rows = baseline_rows(args.baseline, holdout_d, labels,
                             pool_dialogues, cfg)
    finalize_mode_b(args, cfg, args.out, cards, labels, holdout_d, rows,
                    mode_a_pool_count=None)


def finalize_mode_b(args, cfg, out_dir, cards, labels, holdout_d, rows,
                    mode_a_pool_count=None):
    n_holdout = len(holdout_d)
    primary, counts = score_outcomes(rows, n_holdout)
    if args.baseline == "T":
        n_pool = mode_a_pool_count if mode_a_pool_count is not None else len(
            H.read_jsonl(args.pool_dialogues)) if (
            args.pool_dialogues and os.path.exists(args.pool_dialogues)) else 0
        independence = derive_independence(cards)
        secondary = store_metrics(cards, n_pool, labels, rows, independence)
        notes = ["T arm: card pipeline"]
    else:
        secondary = {k: (0.0 if k in ("unlock_hit_smoke", "serve_rate",
                                      "extract_yield", "reject_rate",
                                      "cluster_rate", "shared_rate",
                                      "cluster_purity") else
                         (0 if k in ("unlock_conflict",
                                     "duplicate_in_packet", "scope_leak")
                          else ({} if k in ("votes_hist",
                                            "packet_size_hist") else
                                "agent+dialogue")))
                     for k in ("unlock_hit_smoke", "serve_rate",
                               "extract_yield", "reject_rate", "cluster_rate",
                               "shared_rate", "cluster_purity",
                               "unlock_conflict", "duplicate_in_packet",
                               "scope_leak", "independence", "votes_hist",
                               "packet_size_hist")}
        secondary["serve_rate"] = round(
            sum(1 for r in rows if r["packet_card_ids"]) / n_holdout, 6) if (
            n_holdout) else 0.0
        secondary["packet_size_hist"] = {"1": sum(
            1 for r in rows if len(r["packet_card_ids"]) == 1),
            "2": sum(1 for r in rows if len(r["packet_card_ids"]) == 2),
            "3": sum(1 for r in rows if len(r["packet_card_ids"]) >= 3)}
        notes = [f"baseline arm {args.baseline}: no cards extracted, "
                 f"card-derived secondary metrics not applicable"]
    metrics = assemble(args.run_id, args.baseline, n_holdout, rows, primary,
                       counts, secondary, notes)
    if out_dir:
        H.write_json(os.path.join(out_dir, "metrics.json"), metrics)
        write_per_dialogue(out_dir, rows)
    else:
        H.print_json(metrics)


def main():
    ap = argparse.ArgumentParser(
        description="Evaluate cards against ground truth (SPEC §6.8)")
    sub = ap.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("standalone", help="SPEC §6.8 self-contained eval")
    a.add_argument("--dialogues", required=True)
    a.add_argument("--cards", required=True)
    a.add_argument("--labels", default=None)
    a.add_argument("--model", required=True)
    a.add_argument("--base-url", default=None)
    a.add_argument("--api-key", default=None)
    a.add_argument("--replay-dir", default=None)
    a.add_argument("--at", default=None)
    a.add_argument("--prompts", default=H.PROMPTS_PATH)
    common_args(a)
    a.set_defaults(func=mode_a, baseline="T", pool_dialogues=None)
    a.set_defaults(holdout_dialogues=None, packets_dir=None)

    b = sub.add_parser("score", help="scoring-only (runner orchestration)")
    b.add_argument("--pool-dialogues", default=None)
    b.add_argument("--cards", required=True)
    b.add_argument("--labels", required=True)
    b.add_argument("--holdout-dialogues", required=True)
    b.add_argument("--packets-dir", required=True)
    b.add_argument("--baseline", choices=["T", "B0", "B1", "B2"],
                   default="T")
    common_args(b)
    b.set_defaults(func=mode_b)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
