#!/usr/bin/env python3
"""score_agreement.py — M1 two-pass gold set + agreement report.

Usage:
  python3 score_agreement.py --pairs candidate_pairs.jsonl \
      --pass1 pass1_labels.jsonl --pass2 pass2_labels.jsonl \
      --outdir <dir> [--escalation 0.15] [--seed 20260827]
  python3 score_agreement.py --selftest   (synthetic labels, verifies pipeline)

Pass label files: one JSON line per item: {"pair_id", "pass", "label", "rationale"}
label ∈ {same-problem, related-but-different, unrelated}

Outputs (all committed; per-item, regenerable — lab-workflow §8):
  gold_m1_pairs_agentlabeled.jsonl  — per-item: pair snapshot + both passes +
                                      agreed + canonical_label + flag + PROVENANCE
  agreement.json / agreement_report.md — disagreement rate (set + per band),
                                      direction breakdown, >15% escalation flag
  escalation_sample.md               — ONLY if escalation fires (20-item sample)

Canonical rule (PROTOCOL §4): agree → that label; disagreement with an
`unrelated` side → `unrelated` (disagreed-upgraded); same↔related
disagreement → `related-but-different` (disagreed-downgraded).

Provenance (non-negotiable, founder 2026-08-27): provenance = "agent-labeled".
This script refuses to write any other provenance string.
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

LABELS = ["same-problem", "related-but-different", "unrelated"]
PROVENANCE = "agent-labeled"
THRESHOLD_DEFAULT = 0.15
ESCALATION_SAMPLE_N = 20
SEED_DEFAULT = 20260827


def load_jsonl(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def load_labels(path: Path, pass_name: str):
    out = {}
    for row in load_jsonl(path):
        pid = row["pair_id"]
        if pid in out:
            raise SystemExit(f"{pass_name}: duplicate pair_id {pid}")
        lab = row["label"]
        if lab not in LABELS:
            raise SystemExit(f"{pass_name} {pid}: invalid label {lab!r} (want one of {LABELS})")
        out[pid] = {"label": lab, "rationale": row.get("rationale", "")}
    return out


def canonical(l1: str, l2: str):
    if l1 == l2:
        return l1, None
    if "unrelated" in (l1, l2):
        return "unrelated", "disagreed-upgraded"
    return "related-but-different", "disagreed-downgraded"


def direction(l1: str, l2: str):
    if l1 == l2:
        return None
    if "unrelated" in (l1, l2):
        return "cross-unrelated"
    return "adjacent"


def score(pairs, p1, p2, outdir: Path, threshold: float, seed: int):
    outdir.mkdir(parents=True, exist_ok=True)
    ids = [p["pair_id"] for p in pairs]
    missing = [i for i in ids if i not in p1] + [i for i in ids if i not in p2]
    if missing:
        raise SystemExit(f"missing labels for: {sorted(set(missing))[:10]} (…)")

    gold, dis = [], []
    dis_by_band = {b: Counter() for b in {p["band"] for p in pairs}}
    for p in pairs:
        i = p["pair_id"]
        l1, l2 = p1[i]["label"], p2[i]["label"]
        lab, flag = canonical(l1, l2)
        d = direction(l1, l2)
        if d:
            dis.append({"pair_id": i, "band": p["band"], "pass1": l1, "pass2": l2,
                        "direction": d,
                        "rationale1": p1[i]["rationale"], "rationale2": p2[i]["rationale"]})
            dis_by_band[p["band"]][d] += 1
        gold.append({
            **p,  # engineer's pair snapshot (frozen at label time)
            "pass1_label": l1, "pass1_rationale": p1[i]["rationale"],
            "pass2_label": l2, "pass2_rationale": p2[i]["rationale"],
            "agreed": l1 == l2,
            "canonical_label": lab,
            "flag": flag,
            "provenance": PROVENANCE,
            "protocol": "PROTOCOL-m1-pairs.md v1.0",
        })

    n = len(gold)
    ndis = len(dis)
    rate = ndis / n if n else 0.0
    band_rows = []
    for b in sorted(dis_by_band):
        total_b = sum(1 for p in pairs if p["band"] == b)
        dis_b = sum(dis_by_band[b].values())
        band_rows.append({"band": b, "total": total_b, "disagreements": dis_b,
                          "rate": round(dis_b / total_b, 4) if total_b else 0.0,
                          "adjacent": dis_by_band[b]["adjacent"],
                          "cross-unrelated": dis_by_band[b]["cross-unrelated"]})
    fire = rate > threshold

    gold_path = outdir / "gold_m1_pairs_agentlabeled.jsonl"
    gold_path.write_text("\n".join(json.dumps(g) for g in gold) + "\n")

    summary = {
        "set": "M1 pair set",
        "provenance": PROVENANCE,
        "n_pairs": n,
        "disagreements": ndis,
        "inter_pass_disagreement_rate": round(rate, 4),
        "escalation_threshold": threshold,
        "escalation_fired": fire,
        "direction": {"adjacent": sum(1 for d in dis if d["direction"] == "adjacent"),
                      "cross-unrelated": sum(1 for d in dis if d["direction"] == "cross-unrelated")},
        "per_band": band_rows,
        "canonical_counts": dict(Counter(g["canonical_label"] for g in gold)),
        "flags": dict(Counter(g["flag"] for g in gold if g["flag"])),
    }
    (outdir / "agreement.json").write_text(json.dumps(summary, indent=2) + "\n")

    lines = [
        "# M1 Pair Set — Agreement Report",
        "",
        f"**Provenance: agent-labeled** (two independent passes by lab-1-evaluation; "
        "this is agent self-consistency under frozen rules, NOT human–human agreement — "
        "see PROTOCOL §3 honesty clause).",
        "",
        f"- pairs: **{n}**",
        f"- inter-pass disagreement rate: **{rate:.3f} ({ndis}/{n})**",
        f"- direction: {summary['direction']['adjacent']} adjacent · {summary['direction']['cross-unrelated']} cross-unrelated",
        f"- canonical counts: " + ", ".join(f"{k}={v}" for k, v in sorted(summary["canonical_counts"].items())),
        f"- escalation threshold: {threshold:.0%} → **{'FIRED — 20-item sample escalated' if fire else 'not fired'}**",
        "",
        "| band | total | disagreements | rate | adjacent | cross-unrelated |",
        "|---|---|---|---|---|---|",
    ]
    for r in band_rows:
        lines.append(f"| {r['band']} | {r['total']} | {r['disagreements']} | {r['rate']:.3f} | "
                     f"{r['adjacent']} | {r['cross-unrelated']} |")
    lines.append("")
    (outdir / "agreement_report.md").write_text("\n".join(lines))

    if fire:
        write_escalation(dis, gold, outdir, seed)
        lines.append(f"> ESCALATION FIRED: see `escalation_sample.md` (20-item sample for founder review).")
        (outdir / "agreement_report.md").write_text("\n".join(lines))
    print(json.dumps(summary, indent=2))
    return summary


def write_escalation(dis, gold, outdir: Path, seed: int):
    """Deterministic 20-item sample: all disagreements (band-stratified, up to 20),
    padded with seeded agreement items. Side-by-side passes + rationales."""
    by_id = {g["pair_id"]: g for g in gold}
    bands = sorted({d["band"] for d in dis})
    picked = []
    pool = {b: [d for d in dis if d["band"] == b] for b in bands}
    for b in bands:  # round-robin across bands so every band appears
        while pool[b] and len(picked) < ESCALATION_SAMPLE_N:
            picked.append(pool[b].pop(0))
    r = random.Random(seed)
    agreements = [g for g in gold if g["agreed"]]
    r.shuffle(agreements)
    for g in agreements:
        if len(picked) >= ESCALATION_SAMPLE_N:
            break
        picked.append({"pair_id": g["pair_id"], "band": g["band"], "note": "agreement (padding)"})
    picked = picked[:ESCALATION_SAMPLE_N]
    lines = ["# M1 — Escalation Sample for Founder Review (20 items)",
             "", "Why: inter-pass disagreement exceeded the pre-registered 15% threshold "
             "(PROTOCOL §5). Disagreement items first (band-stratified), padded with "
             "seeded agreement items. Both passes side by side; canonical rule noted.", ""]
    for k, item in enumerate(picked, 1):
        g = by_id[item["pair_id"]]
        lines += [f"## {k:02d}. `{g['pair_id']}` — band: {g['band']} "
                  f"({'DISAGREEMENT' if not g['agreed'] else item.get('note', 'agreement')},"
                  f" canonical: {g['canonical_label']})",
                  f"- pass 1: **{g['pass1_label']}** — {g['pass1_rationale']}",
                  f"- pass 2: **{g['pass2_label']}** — {g['pass2_rationale']}",
                  "", "Display:", "```", g["display"], "```", ""]
    (outdir / "escalation_sample.md").write_text("\n".join(lines))


def selftest():
    tmp = Path("/tmp/m1_score_selftest")
    tmp.mkdir(parents=True, exist_ok=True)
    bands = ["should-match"] * 4 + ["ambiguous"] * 2 + ["should-not-match"] * 2
    pairs = [{"pair_id": f"p{i:03d}", "band": bands[i], "conv_a": "a", "conv_b": "b",
              "flow_a": "f1", "flow_b": "f1", "subflow_a": "s", "subflow_b": "s",
              "product_a": "P", "product_b": "P", "display": "A ... | B ..."} for i in range(8)]
    (tmp / "pairs.jsonl").write_text("\n".join(json.dumps(p) for p in pairs) + "\n")
    # 2 disagreements: 1 cross-unrelated, 1 adjacent
    labs1 = ["same-problem"] * 8
    labs2 = ["same-problem"] * 8
    labs2[0] = "unrelated"        # cross-unrelated on p000 (should-match)
    labs2[3] = "related-but-different"  # adjacent on p003
    p1f = tmp / "p1.jsonl"
    p2f = tmp / "p2.jsonl"
    p1f.write_text("\n".join(json.dumps({"pair_id": f"p{i:03d}", "pass": 1,
                                         "label": labs1[i], "rationale": "r1"}) for i in range(8)) + "\n")
    p2f.write_text("\n".join(json.dumps({"pair_id": f"p{i:03d}", "pass": 2,
                                         "label": labs2[i], "rationale": "r2"}) for i in range(8)) + "\n")
    s = score(load_jsonl(tmp / "pairs.jsonl"), load_labels(p1f, "pass1"), load_labels(p2f, "pass2"),
              tmp / "out", THRESHOLD_DEFAULT, SEED_DEFAULT)
    # 2/8 = 0.25 > 0.15 -> escalation MUST fire, sample must be written
    assert s["n_pairs"] == 8 and s["disagreements"] == 2 and s["escalation_fired"] is True
    assert s["inter_pass_disagreement_rate"] == 0.25
    assert s["canonical_counts"]["unrelated"] == 1 and s["canonical_counts"]["related-but-different"] == 1
    assert s["canonical_counts"]["same-problem"] == 6
    assert s["direction"] == {"adjacent": 1, "cross-unrelated": 1}
    bmap = {r["band"]: r for r in s["per_band"]}
    assert bmap["should-match"]["disagreements"] == 2
    assert bmap["ambiguous"]["disagreements"] == 0 and bmap["should-not-match"]["disagreements"] == 0
    gold = load_jsonl(tmp / "out" / "gold_m1_pairs_agentlabeled.jsonl")
    assert all(g["provenance"] == PROVENANCE for g in gold)
    esc = (tmp / "out" / "escalation_sample.md").read_text()
    assert "Founder Review" in esc and "p000" in esc and "p003" in esc
    print("SELFTEST OK: canonical rule, direction counts, band math, escalation sample, "
          f"provenance all correct. rate={s['inter_pass_disagreement_rate']} fired={s['escalation_fired']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs")
    ap.add_argument("--pass1")
    ap.add_argument("--pass2")
    ap.add_argument("--outdir")
    ap.add_argument("--escalation", type=float, default=THRESHOLD_DEFAULT)
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif not (a.pairs and a.pass1 and a.pass2 and a.outdir):
        ap.error("--pairs --pass1 --pass2 --outdir required (or --selftest)")
    else:
        score(load_jsonl(Path(a.pairs)), load_labels(Path(a.pass1), "pass1"),
              load_labels(Path(a.pass2), "pass2"), Path(a.outdir), a.escalation, a.seed)
