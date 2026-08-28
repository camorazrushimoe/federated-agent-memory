#!/usr/bin/env python3
"""audit.py — the floor/ceiling audit A1..A5 (EVAL-PLAN §7).

    python bin/audit.py --pool data/abcd_1000_pool.jsonl \
        --holdout data/abcd_200_holdout.jsonl --dialogues <stripped pool> \
        --cards <store> --pool-labels <orig pool> --holdout-labels <orig holdout> \
        --out audit.json [--fixture-results <fixtures.json>]

Runs BEFORE any S2 measurement. Cheap, deterministic, no LLM. If an item shows
a threshold is unreachable by construction, the contingency in EVAL-PLAN §7
fires and the threshold is amended in EVAL-PLAN.md BEFORE measuring — never
after seeing a result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfgmod
from cluster import compute_votes
from eval import load_labels, score_holdout
from schema import card_text
from store import read_jsonl
from tfidf import TfidfModel


def _customer_text(dialogue: dict) -> str:
    return " ".join(t.get("text", "") for t in dialogue.get("turns", [])
                    if t.get("role") == "customer").lower()


def a1_serve_ceiling(pool: list[dict], holdout: list[dict],
                     threshold: float) -> dict:
    """Fraction of hold-out dialogues with any in-scope pool dialogue at
    customer-text cosine >= MATCH_THRESHOLD — the ceiling on serve_rate."""
    pool_by_scope: dict[str, list[dict]] = {}
    for d in pool:
        pool_by_scope.setdefault(f"{d['tenant_id']}/{d['vertical']}", []).append(d)
    n_above = 0
    n_total = 0
    for h in holdout:
        scope = f"{h['tenant_id']}/{h['vertical']}"
        cands = pool_by_scope.get(scope, [])
        if not cands:
            continue
        n_total += 1
        query = _customer_text(h)
        if not query:
            continue
        texts = [_customer_text(d) for d in cands]
        model = TfidfModel([query] + texts)
        best = max(model.cosine(query, t) for t in texts)
        if best >= threshold:
            n_above += 1
    frac = round(n_above / n_total, 6) if n_total else 0.0
    return {
        "value": frac,
        "n_holdout_with_pool": n_total,
        "n_above_threshold": n_above,
        "question": "fraction of hold-out dialogues with any in-scope pool dialogue at cosine >= 0.18",
        "gate": "serve_rate >= 0.30",
        "reachable": frac >= 0.30,
        "contingency": ("serve_rate gate unreachable by construction" if frac < 0.30
                        else "no contingency"),
    }


def a2_oracle(pool: list[dict], holdout: list[dict], pool_labels: dict,
              holdout_labels: dict, cfg: dict) -> dict:
    """B2 oracle through the scoring code as written: must be >= 0.98."""
    _, met = score_holdout(arm="B2", holdout=holdout, cards=[],
                           pool_dialogues=pool, pool_labels=pool_labels,
                           holdout_labels=holdout_labels, packets_dir=None, cfg=cfg)
    hit = met["primary"]["unlock_hit_label"]
    return {
        "value": hit,
        "question": "does the oracle B2 score 1.0 with the scoring code as written?",
        "reachable": hit >= 0.98,
        "contingency": ("metric is broken; fix before measuring" if hit < 0.98
                        else "no contingency"),
    }


def a3_gate_binds(cards: list[dict], cfg: dict) -> dict:
    """Fraction of clusters blocked by K_INDEPENDENT under agent+dialogue votes."""
    cards_by_id = {c["card_id"]: c for c in cards}
    total_ge2 = 0
    blocked = 0
    detail = []
    for c in cards:
        if c.get("role") != "canonical":
            continue
        members = [cards_by_id[m] for m in c.get("members", []) if m in cards_by_id]
        served = {s["dialogue_id"] for s in c.get("served_to", [])}
        raw = {c["receipt"]["source_dialogue_id"]} | {
            m["receipt"]["source_dialogue_id"] for m in members}
        raw -= served
        if len(raw) >= 2:
            total_ge2 += 1
            votes, _mode = compute_votes(c, members)
            if votes < cfg["K_INDEPENDENT"]:
                blocked += 1
                detail.append(c["card_id"])
    frac = round(blocked / total_ge2, 6) if total_ge2 else 0.0
    return {
        "value": frac,
        "question": "does K_INDEPENDENT=2 ever bind under the deterministic agent synthesis?",
        "clusters_with_2plus_dialogues": total_ge2,
        "clusters_blocked_by_gate": blocked,
        "detail": detail[:10],
        "independence": "agent+dialogue",
        "contingency": "if the gate blocks nothing, say so — an untested gate is not a passed gate",
    }


def a4_card_cosines(cards: list[dict], pool_labels: dict) -> dict:
    """Within-label vs across-label card-text cosine distribution (~50+ cards).

    Asks: is the within-label median >= CLUSTER_THRESHOLD (0.35)? If not,
    clustering will essentially never fire and the promote path is dead on this
    data — report the finding and re-derive the threshold from the distribution.
    """
    labels: dict[str, str | None] = {}
    for c in cards:
        g = pool_labels.get(c["receipt"]["source_dialogue_id"])
        if g:
            labels[c["card_id"]] = g
    canon = [c for c in cards if c.get("role") == "canonical"]
    keyed = [(c["card_id"], card_text(c), labels.get(c["card_id"]))
             for c in canon if labels.get(c["card_id"])]
    within: list[float] = []
    across: list[float] = []
    model = TfidfModel([t for _, t, _ in keyed])
    for i in range(len(keyed)):
        for j in range(i + 1, len(keyed)):
            s = model.cosine(keyed[i][1], keyed[j][1])
            if keyed[i][2] == keyed[j][2]:
                within.append(s)
            else:
                across.append(s)

    def median(xs: list[float]) -> float:
        if not xs:
            return 0.0
        xs = sorted(xs)
        n = len(xs)
        return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

    w_med = round(median(within), 6)
    return {
        "value": w_med,
        "question": "within-label median card-text cosine vs CLUSTER_THRESHOLD=0.35",
        "within_median": w_med,
        "across_median": round(median(across), 6),
        "n_within_pairs": len(within),
        "n_across_pairs": len(across),
        "n_cards_labeled": len(keyed),
        "gate": "CLUSTER_THRESHOLD = 0.35",
        "reachable": w_med >= 0.35,
        "contingency": ("clustering will rarely fire; re-derive the threshold from this "
                        "distribution, documented once in EVAL-PLAN.md, before measuring"
                        if w_med < 0.35 else "no contingency"),
    }


def a5_staleness(fixture_results: dict | None) -> dict:
    """Can the age-stale rule fire at all? Compressed timeline says no by
    construction; the aged fixture verifies the rule itself fires."""
    new_member_ok = quiet_ok = None
    if fixture_results:
        for c in fixture_results.get("freshness_new_member", []):
            if c.get("role") == "canonical":
                new_member_ok = c.get("status") != "stale"
        for c in fixture_results.get("freshness_quiet", []):
            if c.get("role") == "canonical":
                quiet_ok = c.get("status") == "stale"
    return {
        "value": f"compressed: off by construction (max age 19d < {30}d); "
                 f"aged fixture: new-member-not-stale={new_member_ok}, quiet>30d-stale={quiet_ok}",
        "question": "can the staleness rule fire at all?",
        "rule_verified": bool(new_member_ok and quiet_ok),
        "contingency": "compressed timeline for measured runs (stated next to every metric); aged only for C-CL5/C-CL6",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Floor/ceiling audit A1..A5 (EVAL-PLAN §7).")
    ap.add_argument("--pool", required=True, help="original pool file (with labels)")
    ap.add_argument("--holdout", required=True, help="original holdout file")
    ap.add_argument("--dialogues", required=True, help="stripped pool dialogues")
    ap.add_argument("--cards", required=True, help="card store (post-cluster)")
    ap.add_argument("--fixture-results", default=None, help="fixture suite JSON (A5)")
    ap.add_argument("--out", default="audit.json")
    ap.add_argument("--match-threshold", type=float, default=None)
    ap.add_argument("--cluster-threshold", type=float, default=None)
    args = ap.parse_args(argv)

    cfg = cfgmod.resolve_config({
        "MATCH_THRESHOLD": args.match_threshold if args.match_threshold is not None
            else cfgmod.DEFAULTS["MATCH_THRESHOLD"],
        "CLUSTER_THRESHOLD": args.cluster_threshold if args.cluster_threshold is not None
            else cfgmod.DEFAULTS["CLUSTER_THRESHOLD"],
    })
    pool_raw = read_jsonl(args.pool)
    holdout_raw = read_jsonl(args.holdout)
    pool = read_jsonl(args.dialogues)
    cards = read_jsonl(args.cards)
    pool_labels = load_labels(args.pool)
    holdout_labels = load_labels(args.holdout)

    # note: A1's pool here is the customer-text pool of the STRIPPED dialogues
    # (raw text, no labels); holdout dialogues are the stripped eval slice.
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="h1_audit_"))
    hold_stripped = tmp / "holdout_stripped.jsonl"
    hold_stripped.write_text("\n".join(
        json.dumps({k: v for k, v in r.items() if k not in
                    ("unlock", "unlock_guideline", "split", "n_turns")})
        for r in holdout_raw) + "\n", encoding="utf-8")
    holdout = read_jsonl(str(hold_stripped))

    fixtures = None
    if args.fixture_results:
        fixtures = json.loads(Path(args.fixture_results).read_text())

    audit = {
        "A1": a1_serve_ceiling(pool, holdout, cfg["MATCH_THRESHOLD"]),
        "A2": a2_oracle(pool, holdout, pool_labels, holdout_labels, cfg),
        "A3": a3_gate_binds(cards, cfg),
        "A4": a4_card_cosines(cards, pool_labels),
        "A5": a5_staleness(fixtures),
    }
    out = {"audited_at": cfgmod.utcnow_iso(), "stage_gate": "S2",
           "items": audit,
           "note": "if any threshold is unreachable by construction, amend EVAL-PLAN.md "
                   "with the arithmetic BEFORE measuring"}
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
