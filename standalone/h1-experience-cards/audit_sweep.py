#!/usr/bin/env python3
"""EVAL-PLAN §7.1 — A4 threshold sweep on the pool (hold-out stays frozen).

For each candidate CLUSTER_THRESHOLD in 0.05..0.35 step 0.01, over the pool's
extracted cards, report:
  pairs_same_merged     fraction of card pairs sharing one unlock_guideline
                        that land in the same cluster
  pairs_diff_merged     fraction of pairs with DIFFERENT unlock_guideline that
                        land in the same cluster  (the decisive column)
  cluster_purity        fraction of clusters whose member dialogues all share
                        one unlock_guideline
  shared_rate           canonical cards reaching `shared`
  serve_rate_ceiling    fraction of hold-out-shaped queries (pool tail slice,
                        never the real hold-out) that would get >= 1 card

Selection rule (pre-registered, fixed BEFORE the curve is read):
  largest threshold with cluster_purity >= 0.70 AND serve_rate_ceiling >= 0.30;
  ties go to the larger threshold. If nothing satisfies both -> NOT FIT for
  lexical card-text clustering on this data; publish the curve and stop.

The sweep drives the CANONICAL cluster.py / match.py implementations at each
threshold — no second copy of the algorithm (C-EV5 spirit). It must run from
the experiment root with bin/ importable (post-#35 tree).

Usage (from standalone/h1-experience-cards/):
  python3 audit_sweep.py --cards runs/<A4sweep>/cards.jsonl \
      --dialogues runs/<A4sweep>/dialogues.jsonl \
      --pool data/abcd_1000_pool.jsonl --tail-n 40 \
      [--out audit.json] [--md audit_threshold_sweep.md] [--now ISO]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "bin"))

import cluster as cluster_mod          # noqa: E402
import match as match_mod              # noqa: E402
import jsonio as hio                   # noqa: E402
from common import card_text           # noqa: E402

POOL_LABEL_KEY = "unlock_guideline"


def dialogue_id_of(chat_id: int) -> str:
    return f"d-{chat_id}"


def load_labels(pool_path: str) -> dict[str, str]:
    """dialogue_id -> unlock_guideline (eval-side only; never into cards)."""
    labels = {}
    for line in open(pool_path, encoding="utf-8"):
        row = json.loads(line)
        labels[dialogue_id_of(row["chat_id"])] = row[POOL_LABEL_KEY]
    return labels


def card_label(card: dict, labels: dict[str, str]) -> str | None:
    return labels.get(card.get("receipt", {}).get("source_dialogue_id"))


def compute_metrics(store: list[dict], labels: dict[str, str],
                    tail_dialogues: list[dict]) -> dict:
    """Compute the five sweep columns from a clustered store."""
    clusters: dict[str, list[dict]] = {}
    for c in store:
        clusters.setdefault(c["cluster_id"], []).append(c)

    # ---- pairs_same_merged / pairs_diff_merged (all card pairs) -----------
    same_total = same_merged = diff_total = diff_merged = 0
    for i in range(len(store)):
        li = card_label(store[i], labels)
        if li is None:
            continue
        for j in range(i + 1, len(store)):
            lj = card_label(store[j], labels)
            if lj is None:
                continue
            merged = store[i]["cluster_id"] == store[j]["cluster_id"]
            if li == lj:
                same_total += 1
                if merged:
                    same_merged += 1
            else:
                diff_total += 1
                if merged:
                    diff_merged += 1

    pairs_same_merged = same_merged / same_total if same_total else None
    pairs_diff_merged = diff_merged / diff_total if diff_total else None

    # ---- cluster_purity (member dialogues all share one label) ------------
    pure = 0
    for members in clusters.values():
        labels_in = {card_label(c, labels) for c in members}
        labels_in.discard(None)
        if len(labels_in) <= 1:
            pure += 1
    cluster_purity = pure / len(clusters) if clusters else None

    # ---- shared_rate (canonical cards reaching shared) --------------------
    canonicals = [c for c in store if c.get("role") == "canonical"]
    shared = [c for c in canonicals if c.get("status") == "shared"]
    shared_rate = len(shared) / len(canonicals) if canonicals else None

    # ---- serve_rate_ceiling (pool tail slice, hold-out frozen) ------------
    served = 0
    for dlg in tail_dialogues:
        scored = _match_store(dlg, store)
        if scored:
            served += 1
    serve_rate_ceiling = served / len(tail_dialogues) if tail_dialogues else None

    return {
        "n_cards": len(store),
        "n_clusters": len(clusters),
        "pairs_same_total": same_total,
        "pairs_same_merged": round(pairs_same_merged, 6) if pairs_same_merged is not None else None,
        "pairs_diff_total": diff_total,
        "pairs_diff_merged": round(pairs_diff_merged, 6) if pairs_diff_merged is not None else None,
        "cluster_purity": round(cluster_purity, 6) if cluster_purity is not None else None,
        "shared_rate": round(shared_rate, 6) if shared_rate is not None else None,
        "serve_rate_ceiling": round(serve_rate_ceiling, 6) if serve_rate_ceiling is not None else None,
    }


def _match_store(dialogue: dict, store: list[dict]) -> list[dict]:
    """Same algorithm as match.match_cards but against an in-memory store."""
    import config as cfg
    cfg_obj = cfg.Config()
    scope = match_mod.live_scope(dialogue)
    query = match_mod.live_query(dialogue)
    candidates = [c for c in store
                  if (c.get("receipt") or {}).get("scope") == scope
                  and c.get("status") == "shared"
                  and c.get("role") == "canonical"]
    if not candidates:
        return []
    from common import TFIDF
    texts = [card_text(c) for c in candidates]
    tfidf = TFIDF().fit([query] + texts)
    scored = []
    for c in candidates:
        s = tfidf.score(query, card_text(c))
        if s >= cfg_obj.MATCH_THRESHOLD:
            scored.append({"card_id": c["card_id"], "score": s,
                           "votes": c.get("votes", 0)})
    scored.sort(key=lambda x: (-x["score"], x["card_id"]))
    return scored[:cfg_obj.MAX_PACKET]


def _sha256(path: str) -> str | None:
    if not path or not os.path.exists(path):
        return None
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _dir_sha256(path: str) -> str | None:
    if not os.path.isdir(path):
        return None
    import hashlib
    h = hashlib.sha256()
    for name in sorted(os.listdir(path)):
        h.update(name.encode())
        h.update(open(os.path.join(path, name), "rb").read())
    return h.hexdigest()


def _git_head() -> str | None:
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, cwd=str(_HERE.parent.parent),
                           timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--dialogues", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--tail-n", type=int, default=40,
                    help="number of pool-tail dialogues used as hold-out-shaped queries")
    ap.add_argument("--out", default=None, help="audit.json path (raw rows)")
    ap.add_argument("--md", default=None, help="audit_threshold_sweep.md path")
    ap.add_argument("--now", default="2026-08-28T12:00:00Z")
    ap.add_argument("--cluster-key", choices=("card-text", "customer-turns"),
                    default="card-text",
                    help="cluster similarity key (F5 = customer-turns, "
                         "EVAL-PLAN §7.2); default card-text reproduces the "
                         "committed A4 sweep")
    args = ap.parse_args(argv)

    labels = load_labels(args.pool)
    all_dialogues = hio.read_jsonl(args.dialogues)
    tail_dialogues = all_dialogues[-args.tail_n:]
    if not tail_dialogues:
        print(json.dumps({"error": "no tail dialogues available"}, indent=2))
        return 1

    base_cards = hio.read_jsonl(args.cards)

    rows = []
    t = 0.05
    while t <= 0.35 + 1e-9:
        store = copy.deepcopy(base_cards)
        tmpdir = tempfile.mkdtemp(prefix="h1_sweep_")
        cards_path = os.path.join(tmpdir, "cards.jsonl")
        hio.write_jsonl(cards_path, store)
        try:
            summary = cluster_mod.run_cluster(
                cards_path, args.dialogues, force=True,
                cursor_path=os.path.join(tmpdir, "cursor.json"),
                pinned_now=args.now,
                overrides={"CLUSTER_THRESHOLD": round(t, 4)},
                cluster_key=args.cluster_key)
            store = hio.read_jsonl(cards_path)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        m = compute_metrics(store, labels, tail_dialogues)
        rows.append({
            "threshold": round(t, 4),
            **m,
            "cluster_summary": summary,
        })
        t = round(t + 0.01, 4)

    # ---- selection rule (fixed before the curve; do not re-open) ----------
    candidates = [r for r in rows
                  if r["cluster_purity"] is not None
                  and r["cluster_purity"] >= 0.70
                  and r["serve_rate_ceiling"] is not None
                  and r["serve_rate_ceiling"] >= 0.30]
    if candidates:
        chosen = max(candidates, key=lambda r: r["threshold"])
        verdict = {
            "selected_threshold": chosen["threshold"],
            "selected_row": {k: chosen[k] for k in
                             ("pairs_same_merged", "pairs_diff_merged",
                              "cluster_purity", "shared_rate",
                              "serve_rate_ceiling")},
            "rule": "largest threshold with cluster_purity >= 0.70 AND "
                    "serve_rate_ceiling >= 0.30 (ties -> larger)",
            "status": "DERIVED",
        }
    else:
        key_label = ("card-text" if args.cluster_key == "card-text"
                     else "customer-turns")
        verdict = {
            "selected_threshold": None,
            "rule": "largest threshold with cluster_purity >= 0.70 AND "
                    "serve_rate_ceiling >= 0.30 (ties -> larger)",
            "status": (f"NOT FIT for lexical {key_label} clustering on this "
                       f"data — no threshold in 0.05..0.35 satisfies both "
                       f"gates; do not lower the gates, do not run a full S2 "
                       f"treatment arm"),
        }

    result = {
        "audit_id": "A4-sweep",
        "method": "EVAL-PLAN 7.1 threshold sweep on the pool only; "
                  "hold-out frozen; canonical cluster.py/match.py at each threshold",
        "cluster_key": args.cluster_key,
        "pool_slice": os.path.basename(args.cards),
        "n_cards": len(base_cards),
        "tail_n": args.tail_n,
        "selection_rule": verdict["rule"],
        "provenance": {
            "extract_model": "deepseek-v4-flash",
            "temperature": 0,
            "prompts_sha256": _sha256(str(_HERE / "PROMPTS.md")),
            "cards_sha256": _sha256(args.cards),
            "dialogues_sha256": _sha256(args.dialogues),
            "raw_dir_sha256": _dir_sha256(
                os.path.join(os.path.dirname(args.cards), "raw")),
            "pinned_now": args.now,
            "git_head": _git_head(),
        },
        "verdict": verdict,
        "rows": rows,
    }

    if args.out:
        hio.write_json(args.out, result)
        print(f"wrote {args.out}")
    if args.md:
        write_md(args.md, result)
        print(f"wrote {args.md}")

    print(json.dumps({"verdict": verdict, "n_rows": len(rows)}, indent=2))
    return 0


def write_md(path: str, result: dict) -> None:
    key_label = result.get("cluster_key", "card-text")
    lines = [
        "# Audit — A4 threshold sweep (EVAL-PLAN §7.1)",
        "",
        f"- Method: pool-only sweep over {result['n_cards']} extracted cards; "
        f"hold-out frozen; canonical cluster.py/match.py at each threshold.",
        f"- Cluster key: **{key_label}** "
        f"({('SPEC §6.3, primary contract' if key_label == 'card-text' else 'F5, EVAL-PLAN §7.2 alternative')}).",
        f"- Tail slice: {result['tail_n']} pool-tail dialogues as hold-out-shaped "
        f"queries (never the real hold-out).",
        f"- Selection rule (pre-registered, not re-opened): {result['selection_rule']}",
        "",
        "| threshold | pairs_same_merged | pairs_diff_merged | cluster_purity | "
        "shared_rate | serve_rate_ceiling |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for r in result["rows"]:
        def fmt(v):
            return "—" if v is None else f"{v:.4f}" if isinstance(v, float) else str(v)
        lines.append(
            f"| {r['threshold']:.2f} | {fmt(r['pairs_same_merged'])} | "
            f"{fmt(r['pairs_diff_merged'])} | {fmt(r['cluster_purity'])} | "
            f"{fmt(r['shared_rate'])} | {fmt(r['serve_rate_ceiling'])} |")
    lines += ["", "## Verdict", ""]
    v = result["verdict"]
    if v["selected_threshold"] is not None:
        lines.append(f"**DERIVED threshold: {v['selected_threshold']:.2f}** "
                     f"(row: {v['selected_row']})")
    else:
        lines.append(f"**{v['status']}**")
    lines.append("")
    lines.append("Derived 2026-08-28 per EVAL-PLAN §7.1; any later change "
                 "requires a new sweep and a new pre-registered rule.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
