#!/usr/bin/env python3
"""eval.py — offline evaluation against ground truth (SPEC §6.8, EVAL-PLAN §4).

    python bin/eval.py --dialogues data/dialogues.jsonl --cards data/cards.jsonl \\
        --labels data/labels.jsonl [--holdout file] [--baseline T|B0|B1|B2] \\
        [--model MODEL] [--raw-dir raw/extract] [--replay-dir dir] \\
        [--now ISO] [--run-id ID] [--timeline compressed|aged] [--set k=v]

- Default split: hold out the LAST 20% of --dialogues (file order); extract on
  the first 80%; ONE forced cluster pass; serve each hold-out dialogue; score.
  With --holdout: that file is the hold-out and extraction runs on ALL of
  --dialogues (the runner uses this for S1's pool-tail slice and S2's real
  hold-out).
- --labels is REQUIRED ({dialogue_id, unlock_guideline} JSONL): the ground
  truth sidecar built by the runner from the ORIGINAL pack. Ground truth keys
  never live in dialogues.jsonl (C-L2).
- Metrics: RUN-PROTOCOL §4.1. primary.unlock_hit_label + wrong + abstain
  == 1.0 — asserted on integer counts (every hold-out lands in exactly one
  class, C-EV1); stored ratios are rounded to 6dp with abstain derived as
  1 - hit - wrong so the printed triple sums to 1.0.
- Baselines (same scoring path, C-EV5 — score_outcome is the ONE scoring
  function): B0 empty packet; B1 top-1 raw-customer-text TF-IDF in scope;
  B2 the true label.
- Card label for scoring = majority unlock_guideline of the dialogues in the
  cluster (canonical + members), ties → the canonical's own dialogue label.
  Labels are attached ONLY here (EVAL-PLAN §4.1).
- unlock_hit_smoke: packet card texts share a content word (≥5 chars,
  lowercased) with the hold-out dialogue's unlock_guideline. SPEC §6.8 says
  "the hold-out card's unlock"; the hold-out dialogue has no card — the
  intended meaning is its unlock_guideline (brief §4, noted here).

Writes metrics.json, per_dialogue.jsonl and packets/<id>.txt (arm T).
Prints a JSON summary including extract counts and serve latency for the
runner's cost.json.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import collections
import json
import os
import subprocess
import sys
import time

import config as cfg
import jsonio as hio
from common import TFIDF, now_iso, parse_iso
from match import live_query, live_scope
from serve import serve_dialogue

BIN_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# The ONE scoring function (C-EV5): used by T, B0, B1 and B2.
# ---------------------------------------------------------------------------

def score_outcome(packet_labels, true_label):
    """Classify one hold-out dialogue: hit | wrong | abstain.

    abstain = empty packet (or unscorable: no true label).
    hit     = packet non-empty and ≥1 card label == true label.
    wrong   = packet non-empty and no match (the harm case).
    """
    if true_label is None:
        return "abstain"
    if not packet_labels:
        return "abstain"
    if true_label in packet_labels:
        return "hit"
    return "wrong"


# ---------------------------------------------------------------------------
# Card labelling (labels attached only here)
# ---------------------------------------------------------------------------

def card_label_for(card, store, labels):
    """Majority unlock_guideline of the dialogues in the card's cluster
    (canonical + members), ties → the canonical's own dialogue label."""
    cluster = [card]
    for mid in card.get("members", []):
        if mid in store:
            cluster.append(store[mid])
    values = []
    for c in cluster:
        src = (c.get("receipt") or {}).get("source_dialogue_id")
        lab = labels.get(src)
        if lab is not None:
            values.append(lab)
    if not values:
        return None
    counts = collections.Counter(values)
    best = counts.most_common(1)[0][0]
    if len(counts) > 1 and counts.most_common(2)[0][1] == counts.most_common(2)[1][1]:
        # tie → canonical's own dialogue label
        own = labels.get((card.get("receipt") or {}).get("source_dialogue_id"))
        return own if own is not None else best
    return best


def _content_words(text):
    """Content words (>=5 chars, lowercased) of a text."""
    import re
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) >= 5}


def smoke_overlap(cards, true_label):
    """Content words shared between the packet cards' text and the hold-out
    dialogue's unlock_guideline."""
    if not cards or not true_label:
        return []
    card_text_all = " ".join(
        " ".join([c.get("problem_shape", ""), c.get("constraint", ""),
                  c.get("unlock", ""), " ".join(c.get("what_worked", []))])
        for c in cards)
    return sorted(_content_words(card_text_all) & _content_words(true_label))


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def baseline_b1_packet(dialogue, pool_rows, labels, cfg_obj):
    """B1: top-1 raw customer text in scope, TF-IDF, threshold MATCH_THRESHOLD.

    Returns (packet_labels, packet_scores)."""
    query = live_query(dialogue)
    scope = live_scope(dialogue)
    pool = [d for d in pool_rows
            if live_scope(d) == scope and labels.get(d["dialogue_id"])]
    if not pool:
        return [], []
    texts = [live_query(d) for d in pool]
    tfidf = TFIDF().fit([query] + texts)
    scored = [(tfidf.score(query, t), d) for t, d in zip(texts, pool)]
    scored.sort(key=lambda x: (-x[0], x[1]["dialogue_id"]))
    best_score, best = scored[0]
    if best_score < cfg_obj.MATCH_THRESHOLD:
        return [], []
    return [labels[best["dialogue_id"]]], [round(best_score, 6)]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def _run_script_capture(name, argv):
    proc = subprocess.run([sys.executable, os.path.join(BIN_DIR, name)] + argv,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed (rc={proc.returncode}):\n"
                           f"{proc.stderr}\n{proc.stdout}")
    out = proc.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out}


def run_eval(args):
    cfg_obj = cfg.Config(cfg.parse_overrides(args.set))
    if args.now is None:
        raise ValueError("eval.py requires --now (pinned determinism)")
    pinned_now = args.now

    dialogues = hio.read_jsonl(args.dialogues_path)
    labels = {}
    if args.labels_path and os.path.exists(args.labels_path):
        for row in hio.read_jsonl(args.labels_path):
            labels[row["dialogue_id"]] = row.get("unlock_guideline")

    # ---- split -------------------------------------------------------------
    if args.holdout:
        holdout_rows = hio.read_jsonl(args.holdout)
        extract_rows = dialogues
        train_path = args.dialogues_path
    else:
        n_holdout = max(1, round(len(dialogues) * 0.2))
        extract_rows = dialogues[:-n_holdout]
        holdout_rows = dialogues[-n_holdout:]
        train_path = args.train_out or os.path.join(
            os.path.dirname(args.cards_path) or ".", "dialogues_train.jsonl")
        hio.write_jsonl(train_path, extract_rows)

    t_start = time.time()

    # ---- extract + one forced cluster pass (arm T, fresh store only) ------
    # If the card store already exists (the runner extracted and clustered
    # it), reuse it as-is: re-extracting would (a) spend LLM calls and (b)
    # report extract_yield=0 because every card would be skipped.
    extract_summary = None
    cluster_summary = None
    store = {}
    if os.path.exists(args.cards_path):
        for c in hio.read_jsonl(args.cards_path):
            store[c["card_id"]] = c
    if args.baseline == "T" and not store:
        extract_summary = _run_script_capture("extract.py", [
            "--in", train_path, "--out", args.cards_path,
            "--model", args.model, "--raw-dir", args.raw_dir,
            "--now", pinned_now] +
            (["--replay-dir", args.replay_dir] if args.replay_dir else []) +
            (["--base-url", args.base_url] if args.base_url else []) +
            (["--api-key", args.api_key] if args.api_key else []) +
            (["--set"] + args.set if args.set else []))
        # deterministic half timer starts AFTER the LLM extract step
        t_start = time.time()
        cursor_out = os.path.join(os.path.dirname(args.cards_path) or ".",
                                  "cluster_cursor.json")
        cluster_summary = _run_script_capture("cluster.py", [
            "--cards", args.cards_path, "--dialogues", train_path,
            "--force", "--cursor", cursor_out, "--now", pinned_now] +
            (["--set"] + args.set if args.set else []))
        # reload the store after the forced cluster pass
        store = {}
        for c in hio.read_jsonl(args.cards_path):
            store[c["card_id"]] = c

    per_dialogue = []
    hits = wrongs = abstains = 0
    served = 0
    smoke_hits = 0
    dup_packets = 0
    scope_leak_packets = 0
    packet_size_hist = {"1": 0, "2": 0, "3": 0}
    serve_ms = []

    for d in holdout_rows:
        true_label = labels.get(d["dialogue_id"])
        packet_card_ids, packet_scores, card_labels, card_votes = [], [], [], []
        overlap, packet_cards = [], []
        if args.baseline == "T":
            t0 = time.time()
            served_result = serve_dialogue(
                d, args.cards_path, pinned_now,
                packets_out=args.packets_dir, overrides=cfg.parse_overrides(args.set))
            serve_ms.append(int((time.time() - t0) * 1000))
            # reload the (persisted) store to resolve labels/votes
            store = {}
            for c in hio.read_jsonl(args.cards_path):
                store[c["card_id"]] = c
            packet_cards = [store[cid] for cid in served_result["card_ids"]
                            if cid in store]
            card_labels = [card_label_for(c, store, labels) for c in packet_cards]
            card_votes = [c.get("votes", 0) for c in packet_cards]
            packet_card_ids = served_result["card_ids"]
            packet_scores = served_result["scores"]
            overlap = smoke_overlap(packet_cards, true_label)
        elif args.baseline == "B0":
            packet_card_ids, packet_scores, card_labels, card_votes = [], [], [], []
            overlap = []
            packet_cards = []
        elif args.baseline == "B1":
            b_labels, b_scores = baseline_b1_packet(d, extract_rows, labels, cfg_obj)
            packet_card_ids, packet_scores, card_votes = [], b_scores, []
            card_labels = b_labels
            packet_cards = []
            overlap = (sorted(_content_words(" ".join(b_labels))
                              & _content_words(true_label))
                       if b_labels else [])
        elif args.baseline == "B2":
            packet_card_ids, packet_scores, card_votes = [], [], []
            card_labels = [true_label] if true_label is not None else []
            overlap = sorted(_content_words(true_label))
            packet_cards = []

        outcome = score_outcome(card_labels, true_label)
        if outcome == "hit":
            hits += 1
        elif outcome == "wrong":
            wrongs += 1
        else:
            abstains += 1
        if packet_card_ids or card_labels:
            served += 1
        if overlap:
            smoke_hits += 1

        # packet-level hard invariants (C-SV1/C-SV2 style, computed here)
        if len(packet_card_ids) >= 2:
            cluster_ids = []
            for cid in packet_card_ids:
                c = store.get(cid)
                cluster_ids.append((c or {}).get("cluster_id", cid))
            if len(set(cluster_ids)) < len(cluster_ids):
                dup_packets += 1
        for cid in packet_card_ids:
            c = store.get(cid)
            if c and (c.get("receipt") or {}).get("scope") != live_scope(d):
                scope_leak_packets += 1
        if 1 <= len(packet_card_ids) <= 3:
            packet_size_hist[str(len(packet_card_ids))] += 1

        per_dialogue.append({
            "dialogue_id": d["dialogue_id"],
            "true_unlock_guideline": true_label,
            "packet_card_ids": packet_card_ids,
            "packet_scores": packet_scores,
            "card_labels": card_labels,
            "card_votes": card_votes,
            "outcome": outcome,
            "smoke_overlap_words": overlap,
        })

    deterministic_wall_clock_s = round(time.time() - t_start, 3)

    # ---- aggregates ---------------------------------------------------------
    n = len(holdout_rows)
    # C-EV1: every hold-out lands in exactly one class (assert on counts)
    assert hits + wrongs + abstains == n, \
        f"hits+wrongs+abstains {hits}+{wrongs}+{abstains} != n_holdout {n}"
    hit_r = round(hits / n, 6) if n else 0.0
    wrong_r = round(wrongs / n, 6) if n else 0.0
    abstain_r = round(1.0 - hit_r - wrong_r, 6)   # printed triple sums to 1.0
    assert abs((hit_r + wrong_r + abstain_r) - 1.0) < 1e-6

    # secondary (card-pipeline metrics; null for baseline arms that have none)
    canonicals = [c for c in store.values()
                  if c.get("role") == "canonical"
                  and c.get("status") != "rejected"]
    shared = [c for c in canonicals if c.get("status") == "shared"]

    def _null_for_baseline(value):
        return value if args.baseline == "T" else None

    votes_hist = {"1": 0, "2": 0, "3+": 0}
    for c in canonicals:
        v = c.get("votes", 0)
        key = "3+" if v >= 3 else str(v)
        votes_hist[key] += 1

    multi_member = []
    for c in canonicals:
        if c.get("members"):
            multi_member.append(c)
    pure = 0
    conflicts = 0
    for c in multi_member:
        cluster = [c] + [store[mid] for mid in c.get("members", [])
                         if mid in store]
        vals = []
        for m in cluster:
            lab = labels.get((m.get("receipt") or {}).get("source_dialogue_id"))
            if lab:
                vals.append(lab)
        distinct = set(vals)
        if len(distinct) <= 1:
            pure += 1
        if len(distinct) >= 2:
            conflicts += 1

    # extract counts: from the extract step when this eval ran it, else from
    # the store (runner-extracted path — rejected cards are kept in the store
    # with status=rejected, unparseable dialogues leave no card at all).
    if extract_summary is not None:
        accepted = int(extract_summary.get("extracted", 0) or 0)
        rejected = int(extract_summary.get("rejected", 0) or 0)
    elif args.baseline == "T":
        rejected = sum(1 for c in store.values()
                       if c.get("status") == "rejected")
        accepted = len(store) - rejected
    else:
        accepted = rejected = 0
    n_extract_set = len(extract_rows)

    independence = args.independence
    if independence is None:
        independence = (cluster_summary or {}).get("independence")
    if independence is None:
        independence = "agent+dialogue"

    secondary = {
        "unlock_hit_smoke": round(smoke_hits / n, 6) if n else 0.0,
        "serve_rate": round(served / n, 6) if n else 0.0,
        "extract_yield": _null_for_baseline(
            round(accepted / n_extract_set, 6) if n_extract_set else None),
        "reject_rate": _null_for_baseline(
            round(rejected / (accepted + rejected), 6)
            if (accepted + rejected) else None),
        "cluster_rate": _null_for_baseline(
            round(len(canonicals) / accepted, 6) if accepted else None),
        "shared_rate": _null_for_baseline(
            round(len(shared) / len(canonicals), 6) if canonicals else None),
        "cluster_purity": _null_for_baseline(
            round(pure / len(multi_member), 6) if multi_member else None),
        "unlock_conflict": _null_for_baseline(conflicts),
        "duplicate_in_packet": dup_packets,
        "scope_leak": scope_leak_packets,
        "independence": independence,
        "votes_hist": votes_hist,
        "packet_size_hist": packet_size_hist,
    }

    notes = []
    if args.timeline == "compressed":
        notes.append("age-stale disabled by construction: timeline=compressed")
    else:
        notes.append(f"timeline={args.timeline}: age-stale active")
    notes.append(f"independence={independence}")
    if args.baseline == "T":
        notes.append("unlock_hit_smoke computed against the hold-out "
                     "dialogue's unlock_guideline (SPEC §6.8 wording 'the "
                     "hold-out card's unlock' resolved per brief §4)")

    metrics = {
        "run_id": args.run_id,
        "arm": args.baseline,
        "n_holdout": n,
        "primary": {"unlock_hit_label": hit_r, "wrong": wrong_r,
                    "abstain": abstain_r},
        "secondary": secondary,
        "judge": None,
        "notes": notes,
    }

    if args.metrics_out:
        hio.write_json(args.metrics_out, metrics, sort_keys=True)
    if args.per_dialogue_out:
        hio.write_jsonl(args.per_dialogue_out, per_dialogue)

    summary = {
        "run_id": args.run_id,
        "arm": args.baseline,
        "n_holdout": n,
        "primary": metrics["primary"],
        "secondary": metrics["secondary"],
        "judge": None,
        "notes": notes,
        "extract": extract_summary,
        "cluster": cluster_summary,
        "serve_ms": serve_ms,
        "deterministic_wall_clock_s": deterministic_wall_clock_s,
        "outcome_counts": {"hit": hits, "wrong": wrongs, "abstain": abstains},
    }
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="eval.py",
        description="Offline evaluation against ground truth (SPEC §6.8).")
    ap.add_argument("--dialogues", dest="dialogues_path", required=True)
    ap.add_argument("--cards", dest="cards_path", required=True)
    ap.add_argument("--labels", dest="labels_path", required=True,
                    help="JSONL {dialogue_id, unlock_guideline} sidecar "
                         "(required; ground truth never lives in dialogues)")
    ap.add_argument("--holdout", default=None,
                    help="hold-out dialogues file (else last 20 percent of "
                         "--dialogues)")
    ap.add_argument("--baseline", choices=("T", "B0", "B1", "B2"),
                    default="T")
    ap.add_argument("--model", default=None,
                    help="extract model id, REQUIRED for arm T; NO default "
                         "(D8: a model swap is a flag, never an edit)")
    ap.add_argument("--raw-dir", dest="raw_dir", default="raw/extract")
    ap.add_argument("--replay-dir", dest="replay_dir", default=None)
    ap.add_argument("--now", default=None,
                    help="pinned ISO timestamp (required; brief §6)")
    ap.add_argument("--run-id", dest="run_id", default=None)
    ap.add_argument("--timeline", choices=cfg.TIMELINE_MODES,
                    default="compressed")
    ap.add_argument("--independence", default=None,
                    help="independence mode observed by the runner's cluster "
                         "passes (agent+dialogue|dialogue-only); eval computes "
                         "it itself when it runs the cluster pass")
    ap.add_argument("--train-out", dest="train_out", default=None)
    ap.add_argument("--metrics-out", dest="metrics_out", default="metrics.json")
    ap.add_argument("--per-dialogue-out", dest="per_dialogue_out",
                    default="per_dialogue.jsonl")
    ap.add_argument("--packets-dir", dest="packets_dir", default="packets")
    ap.add_argument("--base-url", default=None,
                    help="LLM base URL (default: env H1_BASE_URL; never "
                         "hard-coded)")
    ap.add_argument("--api-key", default=None,
                    help="LLM API key (default: env H1_API_KEY; never "
                         "printed, never stored)")
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    if args.baseline == "T" and not args.model:
        ap.error("--model is required for arm T (no default; D8 rule)")

    summary = run_eval(args)
    print(hio.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
