#!/usr/bin/env python3
"""BON-37 step 2: verify that numbered subflow variants genuinely share a
playbook, and inspect the two ambiguous subflows (status_questions,
status_delivery_date) before mapping them.

Evidence collected:
  1. For each single-item / storewide family, the union of action names used
     in its dialogues, plus the per-variant action-name sets (to compare
     within a family).
  2. The guideline action sequence (ordered action buttons) for the relevant
     FAQ / Status subflows.
  3. Three example dialogues each for status_questions and status_delivery_date
     (delexed customer + agent lines, truncated) to read what the questions are.

Output: research/phase0/variant_verification.json
Re-run:  python research/phase0/variant_verification.py
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "data/abcd/guidelines.json"
D = ROOT / "data/abcd/abcd_v1.1.json"

g = json.loads(G.read_text())
d = json.loads(D.read_text())

# --- guideline action sequences (ordered list of action buttons per subflow) ---
def guideline_actions(flow: str, subflow: str) -> list:
    body = (g.get(flow) or {}).get("subflows", {}).get(subflow) or {}
    acts = []
    for a in body.get("actions", []):
        acts.append({"type": a.get("type"), "button": a.get("button")})
    return acts

faq_flows = {
    "Boots FAQ": "Single-Item Query",
    "Shirt FAQ": "Single-Item Query",
    "Jeans FAQ": "Single-Item Query",
    "Jacket FAQ": "Single-Item Query",
    "Pricing FAQ": "Storewide Query",
    "Membership FAQ": "Storewide Query",
    "Timing FAQ": "Storewide Query",
    "Policy FAQ": "Storewide Query",
    "Status Active": "Subscription Inquiry",
    "Status Due Date": "Subscription Inquiry",
    "Status Delivery Time": "Order Issue",
}

print("### Guideline action sequences (buttons only) ###")
guide = {}
for sf, fl in faq_flows.items():
    acts = guideline_actions(fl, sf)
    guide[sf] = [a["button"] for a in acts]
    print(f"{fl} / {sf}: {guide[sf]}")

# --- index dialogues by subflow ---
by_sub: dict[str, list] = {}
for split in ("train", "dev", "test"):
    for c in d[split]:
        sc = c.get("scenario") or {}
        sf = sc.get("subflow")
        if sf:
            by_sub.setdefault(sf, []).append((split, c))

# --- action names used per data subflow ---
def action_names(convo) -> list:
    # action turns: {"speaker": "action", "targets": [subflow, "take_action",
    # "<action-name>", [args], -1], ...}  -> name is targets[2]
    out = []
    for t in (convo.get("delexed") or []):
        if t.get("speaker") != "action":
            continue
        tg = t.get("targets") or []
        name = tg[2] if len(tg) > 2 and tg[1] == "take_action" else None
        out.append(str(name) if name else f"(unknown:{tg[1] if len(tg) > 1 else '?'})")
    return out

per_variant_actions = {}
for sf, convos in by_sub.items():
    per_variant_actions[sf] = Counter(n for _, c in convos for n in action_names(c))

families = {
    "boots": [f"boots_{k}_{i}" for k in ("how", "other") for i in (1, 2, 3, 4)],
    "shirt": [f"shirt_{k}_{i}" for k in ("how", "other") for i in (1, 2, 3, 4)],
    "jeans": [f"jeans_{k}_{i}" for k in ("how", "other") for i in (1, 2, 3, 4)],
    "jacket": [f"jacket_{k}_{i}" for k in ("how", "other") for i in (1, 2, 3, 4)],
    "pricing": [f"pricing_{i}" for i in (1, 2, 3, 4)],
    "membership": [f"membership_{i}" for i in (1, 2, 3, 4)],
    "timing": [f"timing_{i}" for i in (1, 2, 3, 4)],
    "policy": [f"policy_{i}" for i in (1, 2, 3, 4)],
}

print("\n### Per-variant action-name sets (families) ###")
fam_report = {}
for fam, members in families.items():
    sets = {m: sorted(per_variant_actions.get(m, {}).keys()) for m in members}
    union = sorted(set(n for s in sets.values() for n in s))
    same = len({tuple(s) for s in sets.values()}) == 1
    fam_report[fam] = {"variants": {m: dict(per_variant_actions.get(m, {})) for m in members},
                       "union": union, "all_variants_identical": same}
    print(f"{fam}: identical across variants={same}; union={union}")
    for m in members:
        print(f"   {m}: {sets[m]}")

# --- examples for the ambiguous subflows ---
def transcript(convo, max_turns=14) -> list:
    out = []
    for t in (convo.get("delexed") or []):
        sp = t.get("speaker")
        if sp == "action":
            a = t.get("action", {})
            out.append(f"[ACTION] {a.get('action_name')} {a.get('action_args')}")
        elif sp in ("customer", "agent"):
            text = t.get("text", "").replace("\n", " ")
            out.append(f"{sp}: {text[:160]}")
        if len(out) >= max_turns:
            break
    return out

examples = {}
for sf in ("status_questions", "status_delivery_date"):
    convos = by_sub.get(sf, [])
    examples[sf] = {
        "n": len(convos),
        "actions_used": dict(per_variant_actions.get(sf, {})),
        "samples": [
            {"split": split, "scenario": c.get("scenario"), "transcript": transcript(c)}
            for split, c in convos[:3]
        ],
    }
    print(f"\n### {sf}: n={len(convos)}, actions={dict(per_variant_actions.get(sf, {}))}")
    for s in examples[sf]["samples"]:
        print(f"  [{s['split']}] scenario={s['scenario']}")
        for line in s["transcript"][:10]:
            print(f"    {line}")

out = {
    "guideline_action_buttons": guide,
    "families": fam_report,
    "ambiguous": examples,
}
out_path = Path(__file__).resolve().parent / "variant_verification.json"
out_path.write_text(json.dumps(out, indent=2))
print(f"\nsaved -> {out_path}")
