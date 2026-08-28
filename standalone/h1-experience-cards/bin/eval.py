#!/usr/bin/env python3
"""eval.py — offline evaluation against ground truth (SPEC §6.8, EVAL-PLAN §4).

Two modes:

Runner mode (what run_experiment.py uses):
    python bin/eval.py --dialogues data/dialogues.jsonl \
        --holdout data/holdout_dialogues.jsonl --cards data/cards.jsonl \
        --pool-labels <original pool> --holdout-labels <original holdout> \
        --packets-dir data/packets --arm T --out metrics.json \
        --per-dialogue per_dialogue.jsonl

Standalone mode (SPEC §6.8; fixtures/tests):
    python bin/eval.py --auto --dialogues <file with >=20 dialogues> \
        --labels <same file, with unlock_guideline> --raw-dir ... \
        --cards-out ... [--replay]

The ONE scoring function (`score_holdout`) serves arms T, B0, B1 and B2
(C-EV5). Outcome classes (EVAL-PLAN §4.2): hit / wrong / abstain, with
hit + wrong + abstain == 1.0 asserted (C-EV1). Ground truth lives only here:
labels are read from the ORIGINAL pool/holdout files, never from the store or
the stripped dialogues (EVAL-PLAN §1).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from store import read_jsonl, write_jsonl
from tfidf import TfidfModel

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- label utils

def load_labels(path: str) -> dict[str, str]:
    """dialogue_id -> unlock_guideline, from an ORIGINAL (un-stripped) file."""
    out: dict[str, str] = {}
    for r in read_jsonl(path):
        g = r.get("unlock_guideline")
        if not g:
            continue
        did = r.get("dialogue_id") or f"d-{r.get('chat_id')}"
        out[str(did)] = g
    return out


def card_label(card: dict, cards_by_id: dict, labels: dict[str, str]) -> str | None:
    """Majority unlock_guideline of the cluster's member dialogues (EVAL-PLAN §4.1).

    Ties broken by the canonical's own dialogue. Labels are attached here only.
    """
    members = [card] + [cards_by_id[m] for m in card.get("members", [])
                        if m in cards_by_id]
    votes: dict[str, int] = {}
    for m in members:
        g = labels.get(m["receipt"]["source_dialogue_id"])
        if g:
            votes[g] = votes.get(g, 0) + 1
    if not votes:
        return None
    mx = max(votes.values())
    cands = [g for g, c in votes.items() if c == mx]
    canon_label = labels.get(card["receipt"]["source_dialogue_id"])
    if canon_label in cands:
        return canon_label
    return sorted(cands)[0]


# ---------------------------------------------------------------- B1 retrieval

def b1_claim(dialogue: dict, pool_dialogues: list[dict],
             pool_labels: dict[str, str], cfg: dict) -> tuple[str | None, float]:
    """Raw-retrieval baseline: TF-IDF over pool customer text, in-scope, 0.18.

    Returns (claimed_guideline, best_score). No cards, no LLM.
    """
    scope = f"{dialogue['tenant_id']}/{dialogue['vertical']}"
    query = " ".join(t.get("text", "") for t in dialogue.get("turns", [])
                     if t.get("role") == "customer").lower()
    cands = [d for d in pool_dialogues
             if f"{d['tenant_id']}/{d['vertical']}" == scope]
    if not cands or not query:
        return None, 0.0
    texts = [" ".join(t.get("text", "") for t in d.get("turns", [])
                      if t.get("role") == "customer") for d in cands]
    model = TfidfModel([query] + texts)
    best = -1.0
    best_i = -1
    for i, t in enumerate(texts):
        s = model.cosine(query, t)
        if s > best:
            best, best_i = s, i
    if best < cfg["MATCH_THRESHOLD"] or best_i < 0:
        return None, 0.0
    return pool_labels.get(cands[best_i]["dialogue_id"]), best


# ---------------------------------------------------------------- the scorer

def score_holdout(*, arm: str, holdout: list[dict], cards: list[dict],
                  pool_dialogues: list[dict], pool_labels: dict[str, str],
                  holdout_labels: dict[str, str], packets_dir: str | None,
                  cfg: dict) -> tuple[list[dict], dict]:
    """ONE scoring implementation for T/B0/B1/B2 (C-EV5).

    Returns (per_dialogue_rows, metrics_dict).
    """
    cards_by_id = {c["card_id"]: c for c in cards}
    rows = []
    n = len(holdout)

    for d in holdout:
        did = d["dialogue_id"]
        true_label = holdout_labels.get(did)
        row = {"dialogue_id": did,
               "true_unlock_guideline": true_label,
               "packet_card_ids": [], "packet_scores": [],
               "card_labels": [], "card_votes": [],
               "outcome": "abstain", "smoke_overlap_words": []}

        if arm == "T":
            ids, scores = _read_packet(packets_dir, did)
            row["packet_card_ids"] = ids
            row["packet_scores"] = scores
            served_cards = [cards_by_id[cid] for cid in ids if cid in cards_by_id]
            row["card_labels"] = [card_label(c, cards_by_id, pool_labels)
                                  for c in served_cards]
            row["card_votes"] = [c.get("votes", 0) for c in served_cards]
            if served_cards:
                row["outcome"] = ("hit" if true_label in row["card_labels"]
                                  else "wrong")
                row["smoke_overlap_words"] = _smoke_overlap(
                    _packet_text(packets_dir, did), true_label)
        elif arm == "B0":
            pass  # packet always empty -> abstain
        elif arm == "B1":
            claim, score = b1_claim(d, pool_dialogues, pool_labels, cfg)
            row["packet_scores"] = [round(score, 6)] if claim else []
            row["card_labels"] = [claim] if claim else []
            if claim is not None:
                row["outcome"] = "hit" if claim == true_label else "wrong"
        elif arm == "B2":
            row["card_labels"] = [true_label]
            row["outcome"] = "hit" if true_label else "abstain"
        rows.append(row)

    # ---- aggregates ---------------------------------------------------------
    hit = sum(1 for r in rows if r["outcome"] == "hit")
    wrong = sum(1 for r in rows if r["outcome"] == "wrong")
    abstain = sum(1 for r in rows if r["outcome"] == "abstain")
    assert hit + wrong + abstain == n, "outcome classes must partition the hold-out"

    def frac(k: int) -> float:
        return round(k / n, 6) if n else 0.0

    hit_f, wrong_f = frac(hit), frac(wrong)
    abstain_f = round(1.0 - hit_f - wrong_f, 6)  # forces exact 1.0 sum (C-EV1)

    # served = the dialogues that got a non-empty packet/claim, per arm
    if arm == "T":
        served = [r for r in rows if r["packet_card_ids"]]
    elif arm == "B1":
        served = [r for r in rows if r["card_labels"]]
    elif arm == "B2":
        served = rows
    else:  # B0
        served = []
    serve_rate = frac(len(served))

    packet_size_hist = {"1": 0, "2": 0, "3": 0}
    if arm == "T":
        for s in (len(r["packet_card_ids"]) for r in served):
            packet_size_hist[str(min(s, 3))] = packet_size_hist.get(str(min(s, 3)), 0) + 1

    smoke_hits = sum(1 for r in rows if r["smoke_overlap_words"])
    unlock_hit_smoke = round(smoke_hits / len(served), 6) if served and arm == "T" else 0.0

    canonicals = [c for c in cards if c.get("role") == "canonical"]
    shared = [c for c in canonicals if c.get("status") == "shared"]
    votes_hist = {"1": 0, "2": 0, "3+": 0}
    for c in canonicals:
        v = c.get("votes", 0)
        key = "3+" if v >= 3 else str(v)
        votes_hist[key] = votes_hist.get(key, 0) + 1

    # cluster purity (EVAL-PLAN §4.4): all member dialogues share one guideline
    pure = 0
    for c in canonicals:
        member_ids = [c["receipt"]["source_dialogue_id"]] + [
            cards_by_id[m]["receipt"]["source_dialogue_id"]
            for m in c.get("members", []) if m in cards_by_id]
        labels_seen = {pool_labels.get(i) for i in member_ids if pool_labels.get(i)}
        if len(labels_seen) <= 1:
            pure += 1
    cluster_purity = round(pure / len(canonicals), 6) if canonicals else 0.0

    # unlock_conflict / duplicate_in_packet / scope_leak
    unlock_conflict = 0
    for c in canonicals:
        unlocks = {c.get("unlock")}
        unlocks.update(cards_by_id[m].get("unlock") for m in c.get("members", [])
                       if m in cards_by_id)
        non_none = {u for u in unlocks if u and u != "none"}
        if len(non_none) > 1:
            unlock_conflict += 1
    duplicate_in_packet = 0
    scope_leak = 0
    for d, r in zip(holdout, rows):
        scope = f"{d['tenant_id']}/{d['vertical']}"
        cids = r["packet_card_ids"]
        clusters = [cards_by_id[cid].get("cluster_id") for cid in cids
                    if cid in cards_by_id]
        if len(clusters) != len(set(clusters)):
            duplicate_in_packet += 1
        for cid in cids:
            c = cards_by_id.get(cid)
            if c and c["receipt"]["scope"] != scope:
                scope_leak += 1

    metrics = {
        "primary": {"unlock_hit_label": hit_f, "wrong": wrong_f,
                    "abstain": abstain_f},
        "secondary": {
            "unlock_hit_smoke": unlock_hit_smoke,
            "serve_rate": serve_rate,
            "cluster_purity": cluster_purity,
            "unlock_conflict": unlock_conflict,
            "duplicate_in_packet": duplicate_in_packet,
            "scope_leak": scope_leak,
            "votes_hist": votes_hist,
            "packet_size_hist": packet_size_hist,
        },
    }
    return rows, metrics


def _read_packet(packets_dir: str | None, dialogue_id: str) -> tuple[list[str], list[float]]:
    if not packets_dir:
        return [], []
    p = Path(packets_dir) / f"{dialogue_id}.json"
    if not p.exists():
        return [], []
    rec = json.loads(p.read_text())
    return rec.get("card_ids", []), rec.get("scores", [])


def _packet_text(packets_dir: str | None, dialogue_id: str) -> str:
    if not packets_dir:
        return ""
    p = Path(packets_dir) / f"{dialogue_id}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _smoke_overlap(packet_text: str, guideline: str | None) -> list[str]:
    """Content words (>=5 chars) shared between packet text and the guideline."""
    if not packet_text or not guideline:
        return []
    import re
    words = lambda s: {w for w in re.findall(r"[a-z0-9']+", s.lower()) if len(w) >= 5}
    return sorted(words(packet_text) & words(guideline))


# ---------------------------------------------------------------- standalone

def run_standalone(args) -> None:
    """SPEC §6.8: hold out the last 20% by file order; extract on the first 80%."""
    raw = read_jsonl(args.dialogues)
    n = len(raw)
    split = int(n * 0.8)
    train_raw, holdout_raw = raw[:split], raw[split:]
    labels = load_labels(args.labels)

    train_path = Path(args.cards_out).parent / "train_raw.jsonl"
    hold_path = Path(args.cards_out).parent / "holdout_raw.jsonl"
    write_jsonl(str(train_path), train_raw)
    write_jsonl(str(hold_path), holdout_raw)

    dial_train = str(Path(args.cards_out).parent / "dialogues.jsonl")
    dial_hold = str(Path(args.cards_out).parent / "holdout_dialogues.jsonl")
    cards_path = args.cards_out
    for rawf, outf in ((str(train_path), dial_train), (str(hold_path), dial_hold)):
        subprocess.run([sys.executable, str(HERE / "ingest.py"), "--in", rawf,
                        "--out", outf], check=True, capture_output=True)
    subprocess.run([sys.executable, str(HERE / "extract.py"), "--in", dial_train,
                    "--out", cards_path,
                    *(["--raw-dir", args.raw_dir] if args.raw_dir else []),
                    *(["--replay"] if args.replay else []),
                    *(["--clock-start", args.clock_start] if args.clock_start else [])],
                   check=True, capture_output=True)
    subprocess.run([sys.executable, str(HERE / "cluster.py"), "--cards", cards_path,
                    "--dialogues", dial_train, "--force",
                    *(["--now", args.clock_start] if args.clock_start else [])],
                   check=True, capture_output=True)
    packets_dir = str(Path(args.cards_out).parent / "packets")
    holdout = read_jsonl(dial_hold)
    for d in holdout:
        p = Path(packets_dir)
        p.mkdir(parents=True, exist_ok=True)
        live = p / f"{d['dialogue_id']}.json"
        live.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        subprocess.run([sys.executable, str(HERE / "serve.py"), "--dialogue", str(live),
                        "--cards", cards_path, "--packets-dir", packets_dir,
                        *(["--clock-start", args.clock_start] if args.clock_start else [])],
                       check=True, capture_output=True)
    pool_dialogues = read_jsonl(dial_train)
    cards = read_jsonl(cards_path)
    rows, metrics = score_holdout(
        arm="T", holdout=holdout, cards=cards, pool_dialogues=pool_dialogues,
        pool_labels=labels, holdout_labels=labels, packets_dir=packets_dir,
        cfg=cfgmod.resolve_config())
    _finish(args, rows, metrics, "T")


def _finish(args, rows, metrics, arm) -> None:
    per = Path(args.per_dialogue)
    per.parent.mkdir(parents=True, exist_ok=True)
    per.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                   encoding="utf-8")
    # C-EV2: aggregates recomputed from per_dialogue must match metrics.json
    recomputed = {
        "unlock_hit_label": round(sum(1 for r in rows if r["outcome"] == "hit") / len(rows), 6),
        "wrong": round(sum(1 for r in rows if r["outcome"] == "wrong") / len(rows), 6),
    }
    recomputed["abstain"] = round(1 - recomputed["unlock_hit_label"] - recomputed["wrong"], 6)
    assert recomputed == metrics["primary"], f"C-EV2 recompute mismatch: {recomputed} != {metrics['primary']}"
    out = {"run_id": getattr(args, "run_id", None), "arm": arm,
           "n_holdout": len(rows), "primary": metrics["primary"],
           "secondary": metrics["secondary"], "judge": None}
    if arm != "T":
        out["secondary"]["unlock_hit_smoke"] = None
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline eval against unlock_guideline (SPEC §6.8).")
    ap.add_argument("--dialogues", default=None, help="stripped pool dialogues (runner mode) or raw file (--auto)")
    ap.add_argument("--holdout", default=None, help="stripped holdout dialogues")
    ap.add_argument("--cards", default=None, help="card store (post-cluster, post-serve)")
    ap.add_argument("--pool-labels", default=None, help="ORIGINAL pool file (with unlock_guideline)")
    ap.add_argument("--holdout-labels", default=None, help="ORIGINAL holdout file")
    ap.add_argument("--packets-dir", default=None)
    ap.add_argument("--arm", choices=("T", "B0", "B1", "B2"), default="T")
    ap.add_argument("--extract-summary", default=None, help="extract.py summary JSON (yield/reject)")
    ap.add_argument("--out", default="metrics.json")
    ap.add_argument("--per-dialogue", default="per_dialogue.jsonl")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--independence", default=None)
    ap.add_argument("--match-threshold", type=float, default=None)
    ap.add_argument("--max-packet", type=int, default=None)
    ap.add_argument("--notes", action="append", default=[])
    # standalone mode
    ap.add_argument("--auto", action="store_true", help="run the 80/20 mini-pipeline (SPEC §6.8)")
    ap.add_argument("--labels", default=None, help="original file with unlock_guideline (--auto)")
    ap.add_argument("--raw-dir", default=None)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--clock-start", default=None)
    ap.add_argument("--cards-out", default=None, help="card store path for --auto")
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "MATCH_THRESHOLD": args.match_threshold if args.match_threshold is not None
            else cfgmod.DEFAULTS["MATCH_THRESHOLD"],
        "MAX_PACKET": args.max_packet if args.max_packet is not None
            else cfgmod.DEFAULTS["MAX_PACKET"],
    })

    if args.auto:
        run_standalone(args)
        return 0

    # ---- runner mode --------------------------------------------------------
    pool_dialogues = read_jsonl(args.dialogues)
    holdout = read_jsonl(args.holdout)
    cards = read_jsonl(args.cards)
    pool_labels = load_labels(args.pool_labels) if args.pool_labels else {}
    holdout_labels = load_labels(args.holdout_labels) if args.holdout_labels else {}
    rows, metrics = score_holdout(
        arm=args.arm, holdout=holdout, cards=cards,
        pool_dialogues=pool_dialogues, pool_labels=pool_labels,
        holdout_labels=holdout_labels, packets_dir=args.packets_dir, cfg=cfg)

    if args.extract_summary:
        summ = json.loads(Path(args.extract_summary).read_text())
        ingested = len(pool_dialogues)
        extracted = summ.get("extracted", 0)
        accepted = summ.get("accepted", 0)
        rejected = summ.get("rejected", 0)
        metrics["secondary"]["extract_yield"] = round(accepted / ingested, 6) if ingested else 0.0
        metrics["secondary"]["reject_rate"] = round(rejected / extracted, 6) if extracted else 0.0
        canonical_after = sum(1 for c in cards if c.get("role") == "canonical")
        metrics["secondary"]["cluster_rate"] = round(canonical_after / accepted, 6) if accepted else 0.0
    canon = [c for c in cards if c.get("role") == "canonical"]
    metrics["secondary"]["shared_rate"] = round(
        sum(1 for c in canon if c.get("status") == "shared") / len(canon), 6) if canon else 0.0
    metrics["secondary"]["independence"] = args.independence or "n/a"

    # C-EV3 / C-EV4 sanity checks on the baseline arms
    if args.arm == "B0":
        assert metrics["primary"]["unlock_hit_label"] == 0.0 and metrics["primary"]["abstain"] == 1.0, \
            "C-EV3: B0 must score 0 hit / 1.0 abstain"
    if args.arm == "B2":
        assert metrics["primary"]["unlock_hit_label"] >= 0.98, \
            f"C-EV4: oracle B2 scored {metrics['primary']['unlock_hit_label']} < 0.98 — metric is broken"

    _finish(args, rows, metrics, args.arm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
