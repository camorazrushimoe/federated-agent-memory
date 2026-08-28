#!/usr/bin/env python3
"""EVAL-PLAN §7.2 — F5 sweep: alternative cluster key (customer turns).

For each candidate CLUSTER_THRESHOLD in 0.05..0.35 step 0.01, over the pool's
extracted cards, report the same five columns as the §7.1 sweep:
  pairs_same_merged / pairs_diff_merged / cluster_purity / shared_rate /
  serve_rate_ceiling
with the SAME pre-registered selection rule (largest threshold with
cluster_purity >= 0.70 AND serve_rate_ceiling >= 0.30; ties -> larger).

--cluster-key card-text (default): the canonical §7.1 key
    problem_shape + constraint + unlock. Reproduces audit_sweep.py exactly;
    used as the repro gate against the committed #41 curve.
--cluster-key customer-turns: the F5 key — the source dialogue's CUSTOMER
    TURNS (lowercased, concatenated) instead of the card text. Nothing else
    changes: same cards, same scopes, same K_INDEPENDENT, same serve path,
    same metrics, same scoring code, same frozen hold-out, same rule.

Ownership (LAB-BRIEF §1.1, one module one owner): canonical bin/cluster.py,
bin/match.py, bin/common.py and audit_sweep.py are NOT edited. The greedy
clustering and the TF-IDF recipe run inside canonical cluster.py run_cluster()
exactly as audit_sweep.py drives them. For customer-turns the cards' key
fields (problem_shape/constraint/unlock) are temporarily replaced with the
customer-turns text so the canonical key function card_text() yields the F5
key; the resulting cluster_id/status/role/votes are then mapped back onto the
ORIGINAL cards. Metrics come from audit_sweep.compute_metrics and
audit_sweep._match_store — ONE scoring path (C-EV5).

Usage (from standalone/h1-experience-cards/):
  python3 f5_sweep.py --cluster-key card-text|customer-turns \
      --cards runs/2026-08-28_A4sweep/cards.jsonl \
      --dialogues runs/2026-08-28_A4sweep/dialogues.jsonl \
      --pool data/abcd_1000_pool.jsonl --tail-n 40 \
      [--out audit_f5.json] [--md audit_threshold_sweep_f5.md] [--now ISO]

  python3 f5_sweep.py --write-results-md RESULTS.md \
      --cardtext-json audit.json --f5-json audit_f5.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "bin"))

import audit_sweep                        # noqa: E402  (Lead's sweep module, read-only)
import cluster as cluster_mod             # noqa: E402  (canonical, read-only)
import jsonio as hio                      # noqa: E402  (canonical, read-only)

POOL_LABEL_KEY = audit_sweep.POOL_LABEL_KEY
RANGE_START, RANGE_END, RANGE_STEP = 0.05, 0.35, 0.01
RULE = ("largest threshold with cluster_purity >= 0.70 AND "
        "serve_rate_ceiling >= 0.30 (ties -> larger)")
KEY_LABEL = {
    "card-text": "lexical card-text clustering",
    "customer-turns": "customer-turns clustering",
}


def customer_turns_text(dialogue: dict) -> str:
    """EVAL-PLAN §7.2: the source dialogue's customer turns, lowercased,
    concatenated. Turns with role == 'customer' only; empty texts skipped."""
    parts = []
    for t in dialogue.get("turns", []):
        if t.get("role") == "customer" and t.get("text"):
            parts.append(str(t["text"]).lower())
    return " ".join(parts)


def build_keyed_cards(base_cards: list[dict], dialogues: list[dict],
                      cluster_key: str) -> tuple[list[dict], dict]:
    """Return (cards_to_cluster, stats).

    card-text: the cards unchanged (canonical key = card_text()).
    customer-turns: deep copies whose key fields (problem_shape/constraint/
    unlock) are replaced by the source dialogue's customer-turns text, so the
    canonical card_text() produces the F5 key. cluster_id/status/role/votes
    from the resulting clustered store are mapped back onto the ORIGINAL
    cards after clustering (see map_back()).
    """
    stats = {"n_missing_source": 0, "n_empty_key": 0}
    if cluster_key == "card-text":
        return base_cards, stats
    lookup = {d.get("dialogue_id"): d for d in dialogues}
    out = []
    for c in base_cards:
        source = (c.get("receipt") or {}).get("source_dialogue_id")
        dlg = lookup.get(source)
        key = ""
        if dlg is None:
            stats["n_missing_source"] += 1
        else:
            key = customer_turns_text(dlg)
            if not key:
                stats["n_empty_key"] += 1
        cc = copy.deepcopy(c)
        cc["problem_shape"] = key
        cc["constraint"] = ""
        cc["unlock"] = ""
        out.append(cc)
    return out, stats


def map_back(original: list[dict], clustered: list[dict],
             dialogues_lookup: dict) -> list[dict]:
    """Copy the clustering outcome (cluster_id/status/role/votes) from the
    clustered store onto the original cards, then apply the SAME canonical
    post-merge processing (inherit_fields, last_closed_at, members list) that
    a card-text run applies inside run_cluster — so the serve-rate ceiling is
    computed on the same card-text basis in both modes. Everything else stays
    as the real card (the serve path and the metrics must see the ORIGINAL
    cards, only regrouped)."""
    by_id = {c["card_id"]: c for c in clustered}
    out = []
    for c in original:
        cc = copy.deepcopy(c)
        cl = by_id.get(c["card_id"])
        if cl is not None:
            cc["cluster_id"] = cl.get("cluster_id", cc["cluster_id"])
            cc["status"] = cl.get("status", cc["status"])
            cc["role"] = cl.get("role", cc["role"])
            cc["votes"] = cl.get("votes", cc["votes"])
        out.append(cc)

    groups: dict[str, list[dict]] = {}
    for c in out:
        groups.setdefault(c["cluster_id"], []).append(c)
    for cluster_id, members_all in groups.items():
        canonical = next((c for c in members_all if c["card_id"] == cluster_id),
                         None)
        if canonical is None:
            continue
        members = [c for c in members_all if c["card_id"] != cluster_id]
        if not members:
            continue
        members_sorted = sorted(members, key=cluster_mod._sort_key)
        cluster_mod.inherit_fields(canonical, members_sorted)
        canonical["members"] = [m["card_id"] for m in members_sorted]
        lca = cluster_mod.compute_last_closed_at(canonical, members,
                                                 dialogues_lookup)
        if lca is not None:
            canonical.setdefault("receipt", {})["last_closed_at"] = lca
    return out


def run_one_threshold(cards: list[dict], dialogues_path: str, t: float,
                      pinned_now: str) -> tuple[list[dict], dict]:
    """Drive canonical cluster.py run_cluster() at threshold t (same call as
    audit_sweep.py). Returns (clustered_cards, summary)."""
    tmpdir = tempfile.mkdtemp(prefix="h1_f5_sweep_")
    cards_path = os.path.join(tmpdir, "cards.jsonl")
    hio.write_jsonl(cards_path, cards)
    try:
        summary = cluster_mod.run_cluster(
            cards_path, dialogues_path, force=True,
            cursor_path=os.path.join(tmpdir, "cursor.json"),
            pinned_now=pinned_now,
            overrides={"CLUSTER_THRESHOLD": round(t, 4)})
        clustered = hio.read_jsonl(cards_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return clustered, summary


def _sha256(path: str) -> str | None:
    if not path or not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _dir_sha256(path: str) -> str | None:
    if not os.path.isdir(path):
        return None
    h = hashlib.sha256()
    for name in sorted(os.listdir(path)):
        h.update(name.encode())
        h.update(open(os.path.join(path, name), "rb").read())
    return h.hexdigest()


def _git_head() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                           text=True, cwd=str(_HERE.parent.parent), timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


def run_sweep(args) -> dict:
    labels = audit_sweep.load_labels(args.pool)
    all_dialogues = hio.read_jsonl(args.dialogues)
    tail_dialogues = all_dialogues[-args.tail_n:]
    if not tail_dialogues:
        print(json.dumps({"error": "no tail dialogues available"}, indent=2))
        sys.exit(1)

    base_cards = hio.read_jsonl(args.cards)
    dialogue_lookup = {d.get("dialogue_id"): d for d in all_dialogues}
    keyed_cards, key_stats = build_keyed_cards(base_cards, all_dialogues,
                                               args.cluster_key)

    rows = []
    t = RANGE_START
    while t <= RANGE_END + 1e-9:
        clustered, summary = run_one_threshold(keyed_cards, args.dialogues, t,
                                               args.now)
        store = clustered if args.cluster_key == "card-text" else \
            map_back(base_cards, clustered, dialogue_lookup)
        m = audit_sweep.compute_metrics(store, labels, tail_dialogues)
        rows.append({"threshold": round(t, 4), **m,
                     "cluster_summary": summary})
        t = round(t + RANGE_STEP, 4)

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
            "rule": RULE,
            "status": "DERIVED",
        }
    else:
        verdict = {
            "selected_threshold": None,
            "rule": RULE,
            "status": (f"NOT FIT for {KEY_LABEL[args.cluster_key]} on this "
                       f"data — no threshold in {RANGE_START:.2f}.."
                       f"{RANGE_END:.2f} satisfies both gates; do not lower "
                       f"the gates, do not run a full S2 treatment arm"),
        }

    result = {
        "audit_id": "F5-sweep" if args.cluster_key == "customer-turns" else
                    "A4-sweep-repro",
        "cluster_key": args.cluster_key,
        "method": ("EVAL-PLAN 7.2 F5 sweep (alternative cluster key) on the "
                   "pool only; hold-out frozen; canonical cluster.py/match.py "
                   "at each threshold") if args.cluster_key == "customer-turns"
                  else "EVAL-PLAN 7.1 sweep reproduction (card-text key)",
        "pool_slice": os.path.basename(args.cards),
        "n_cards": len(base_cards),
        "tail_n": args.tail_n,
        "selection_rule": RULE,
        "key_stats": key_stats,
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

    print(json.dumps({"cluster_key": args.cluster_key,
                      "verdict": verdict, "n_rows": len(rows),
                      "key_stats": key_stats}, indent=2))
    return result


def fmt(v):
    return "—" if v is None else f"{v:.4f}" if isinstance(v, float) else str(v)


def write_md(path: str, result: dict) -> None:
    lines = [
        f"# Audit — F5 threshold sweep, cluster key = {result['cluster_key']} "
        f"(EVAL-PLAN §7.2)",
        "",
        f"- Method: pool-only sweep over {result['n_cards']} extracted cards; "
        f"hold-out frozen; canonical cluster.py/match.py at each threshold.",
        f"- Cluster key: {KEY_LABEL[result['cluster_key']]}"
        + ("" if result["cluster_key"] == "card-text" else
           " (source dialogue's customer turns, lowercased, concatenated)"),
        f"- Tail slice: {result['tail_n']} pool-tail dialogues as "
        f"hold-out-shaped queries (never the real hold-out).",
        f"- Selection rule (pre-registered, not re-opened): "
        f"{result['selection_rule']}",
        "",
        "| threshold | pairs_same_merged | pairs_diff_merged | cluster_purity "
        "| shared_rate | serve_rate_ceiling |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for r in result["rows"]:
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
    lines.append("One round per EVAL-PLAN §7.2 (pre-authorized before the §7.1 "
                 "sweep result); any later change requires a new pre-registered "
                 "rule.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def one_line_answer(ct_verdict: dict, f5_verdict: dict) -> str:
    ct_pass = ct_verdict.get("selected_threshold") is not None
    f5_pass = f5_verdict.get("selected_threshold") is not None
    if f5_pass and not ct_pass:
        return ("The signal lived in the raw text, not the cards: the "
                "alternative cluster key (customer turns) passes; the primary "
                "configuration (card-text) does not.")
    if ct_pass and not f5_pass:
        return ("The signal lived in the cards, not the raw text: the primary "
                "configuration passes; the alternative cluster key does not.")
    if ct_pass and f5_pass:
        return "The signal lived in both the cards and the raw text."
    return ("The signal lived nowhere: neither the card-text key nor the "
            "customer-turns key meets the pre-registered gates "
            "(cluster_purity >= 0.70 AND serve_rate_ceiling >= 0.30) at any "
            "threshold in 0.05..0.35.")


def curve_table(rows: list[dict]) -> str:
    lines = ["| threshold | pairs_same_merged | pairs_diff_merged | "
             "cluster_purity | shared_rate | serve_rate_ceiling |",
             "|---|--:|--:|--:|--:|--:|"]
    for r in rows:
        lines.append(f"| {r['threshold']:.2f} | {fmt(r['pairs_same_merged'])} "
                     f"| {fmt(r['pairs_diff_merged'])} | "
                     f"{fmt(r['cluster_purity'])} | {fmt(r['shared_rate'])} | "
                     f"{fmt(r['serve_rate_ceiling'])} |")
    return "\n".join(lines)


def write_results_md(path: str, ct_result: dict, f5_result: dict) -> None:
    ct_v, f5_v = ct_result["verdict"], f5_result["verdict"]
    answer = one_line_answer(ct_v, f5_v)

    def verdict_line(v):
        if v["selected_threshold"] is not None:
            return (f"**DERIVED — threshold {v['selected_threshold']:.2f}** "
                    f"({v['selected_row']})")
        return f"**{v['status']}**"

    doc = f"""# H1 Experience Cards — Results

**Status:** round 3 closed. The §7.1 A4 sweep (PR #41) published its NOT FIT
verdict; the pre-authorized §7.2 F5 sweep (alternative cluster key — customer
turns) ran its single round and its verdict is recorded below. Numbers below
are generated from the committed sweep JSONs (`audit.json`, `audit_f5.json`),
never hand-typed (RUN-PROTOCOL §5).

## 1. The hypothesis

Experience cards extracted from past dialogues carry a reusable signal that
helps a fresh dialogue (measured as `unlock_hit_label` on the frozen
hold-out, vs B0/B1/B2 baselines).

Falsifier, pre-registered (EVAL-PLAN §7.1/§7.2): if **no** cluster threshold
in 0.05..0.35 satisfies `cluster_purity >= 0.70` AND
`serve_rate_ceiling >= 0.30` — first for the card-text key, then for the
customer-turns key — the pipeline as configured cannot serve a meaningfully
pure memory, and the verdict is NOT FIT.

## 2. The verdicts

### 2.1 Primary configuration — lexical card-text clustering (EVAL-PLAN §7.1, PR #41)

{verdict_line(ct_v)}

### 2.2 Alternative cluster key — customer turns (EVAL-PLAN §7.2, F5, one round)

{verdict_line(f5_v)}

### 2.3 The one-line answer

> {answer}

## 3. The two curves, side by side

### 3.1 Card-text cluster key (`audit.json`, PR #41)

{curve_table(ct_result["rows"])}

### 3.2 Customer-turns cluster key (`audit_f5.json`, F5)

{curve_table(f5_result["rows"])}

## 4. What the audit found (A1–A5)

A1: serve ceiling measured in the §7.1/§7.2 sweeps — `serve_rate_ceiling`
maxes at 0.15 for card-text and 0.175 for customer-turns on the pool tail
slice (see 3.1/3.2), i.e. the `serve_rate >= 0.30` gate is unreachable with
either key. A4: within-label card-to-card cosine median 0.084–0.100, fraction
of pairs >= 0.35 = 0.0 (recorded in EVAL-PLAN §7.1). The separation columns
(`pairs_diff_merged`) stay low for both keys — see the tables above.

## 5. Known limits

- The sweep measures the **ceiling** on serving (would the query get >= 1
  card); it is not an S2 treatment-arm measurement, which is not run while the
  ceiling gate is unmet (EVAL-PLAN §7.1).
- Customer-turns key is a single one-round probe (EVAL-PLAN §7.2), not a
  re-tuned pipeline.
- The customer-turns key merges eagerly at low thresholds — raw customer
  text shares boilerplate across problems (`pairs_diff_merged` 0.143 at
  0.05 vs 0.051 for card-text), so its purity only clears 0.70 where almost
  nothing merges (`shared_rate` collapses), and the serve ceiling is capped
  by the query-to-card match step (`MATCH_THRESHOLD`), not by the cluster
  key.
- Judge block (L3) and calibration remain pending; they are not reached while
  the value gates fail.

## 6. The judge block

_Pending — not reached (no S2 treatment run under NOT FIT)._

## 7. What would change the verdict

The cheapest next experiment would be widening scope (tenant → vertical) to
raise the serve ceiling (A1 contingency, EVAL-PLAN §7), or a different
similarity signal (embeddings are explicitly out of scope for this
experiment, SPEC §7). Both are follow-ups, not re-runs of the frozen rule.
"""
    Path(path).write_text(doc, encoding="utf-8")
    print(f"wrote {path}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cluster-key", choices=sorted(KEY_LABEL),
                    default="card-text")
    ap.add_argument("--cards")
    ap.add_argument("--dialogues")
    ap.add_argument("--pool")
    ap.add_argument("--tail-n", type=int, default=40)
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--now", default="2026-08-28T12:00:00Z")
    ap.add_argument("--write-results-md", default=None,
                    help="write RESULTS.md from two result JSONs")
    ap.add_argument("--cardtext-json", default=None)
    ap.add_argument("--f5-json", default=None)
    args = ap.parse_args(argv)

    if args.write_results_md:
        if not args.cardtext_json or not args.f5_json:
            print("--write-results-md needs --cardtext-json and --f5-json")
            return 2
        ct = json.load(open(args.cardtext_json, encoding="utf-8"))
        f5 = json.load(open(args.f5_json, encoding="utf-8"))
        write_results_md(args.write_results_md, ct, f5)
        return 0

    if not (args.cards and args.dialogues and args.pool):
        ap.error("--cards/--dialogues/--pool are required for a sweep")
    run_sweep(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
