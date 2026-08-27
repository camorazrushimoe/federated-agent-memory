#!/usr/bin/env python3
"""BON-37: build the explicit 96 -> 55 ABCD subflow -> guidelines mapping table.

Outputs
-------
research/abcd_subflow_mapping.json   (canonical, machine-readable)
research/abcd_subflow_mapping.csv    (human-readable mirror)

How it is derived (see research/abcd_subflow_mapping.md for the narrative):
  * 46 data subflows literally match an ontology/guidelines name  -> DIRECT
  * 48 numbered variants (boots_how_1..4, pricing_3, ...) map to the single
    guideline FAQ subflow for that product/category -> VARIANT
  * 2 generic data subflows are mapped by reading dialogues + action traces
    -> INFERRED (status_questions, status_delivery_date)

Re-run:  python research/phase0/build_mapping.py
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "data/abcd/guidelines.json"
O = ROOT / "data/abcd/ontology.json"
D = ROOT / "data/abcd/abcd_v1.1.json"

g = json.loads(G.read_text())
o = json.loads(O.read_text())
d = json.loads(D.read_text())

# ---- guidelines: flow -> set of Title Case subflow names ----
guide_by_flow = {f: set((b.get("subflows") or {})) for f, b in g.items()}
guide_all = set().union(*guide_by_flow.values())
assert len(guide_all) == 55, f"expected 55 guideline subflows, got {len(guide_all)}"

# ---- full ontology(snake) -> guideline(Title Case) name map (all 55) ----
ONT2GUIDE = {
    # product_defect
    "refund_initiate": "Initiate Refund",
    "refund_update": "Update Refund",
    "refund_status": "Refund Status",
    "return_stain": "Return Due to Stain",
    "return_color": "Return Due to Color",
    "return_size": "Return Due to Size",
    # order_issue
    "status_mystery_fee": "Status Mystery Fee",
    "status_delivery_time": "Status Delivery Time",
    "status_payment_method": "Status Payment Method",
    "status_quantity": "Status Quantity",
    "manage_upgrade": "Manage Upgrade",
    "manage_downgrade": "Manage Downgrade",
    "manage_create": "Manage Create",
    "manage_cancel": "Manage Cancel",
    # account_access
    "recover_username": "Recover Username",
    "recover_password": "Recover Password",
    "reset_2fa": "Reset Two-Factor Auth",
    # troubleshoot_site
    "credit_card": "Invalid Credit Card",
    "shopping_cart": "Cart Not Updating",
    "search_results": "Search Not Working",
    "slow_speed": "Website Too Slow",
    # manage_account
    "status_service_added": "Status Service Added",
    "status_service_removed": "Status Service Removed",
    "status_shipping_question": "Status Shipping Question",
    "status_credit_missing": "Status Credit Missing",
    "manage_change_address": "Manage Change Address",
    "manage_change_name": "Manage Change Name",
    "manage_change_phone": "Manage Change Phone",
    "manage_payment_method": "Manage Payment Method",
    # purchase_dispute
    "bad_price_competitor": "Bad Price Competitor",
    "bad_price_yesterday": "Bad Price Yesterday",
    "out_of_stock_general": "Out-of-Stock General",
    "out_of_stock_one_item": "Out-of-Stock One Item",
    "promo_code_invalid": "Promo Code Invalid",
    "promo_code_out_of_date": "Promo Code Out of Date",
    "mistimed_billing_already_returned": "Mistimed Billing Already Returned",
    "mistimed_billing_never_bought": "Mistimed Billing Never Bought",
    # shipping_issue
    "status": "Shipping Status",
    "manage": "Manage Shipping",
    "missing": "Missing Item",
    "cost": "Shipping Cost",
    # subscription_inquiry
    "status_active": "Status Active",
    "status_due_amount": "Status Due Amount",
    "status_due_date": "Status Due Date",
    "manage_pay_bill": "Manage Pay Bill",
    "manage_extension": "Manage Extension",
    "manage_dispute_bill": "Manage Dispute Bill",
    # single_item_query (canonical base names)
    "boots": "Boots FAQ",
    "shirt": "Shirt FAQ",
    "jeans": "Jeans FAQ",
    "jacket": "Jacket FAQ",
    # storewide_query (canonical base names)
    "pricing": "Pricing FAQ",
    "membership": "Membership FAQ",
    "timing": "Timing FAQ",
    "policy": "Policy FAQ",
}
# every target must be a real guideline subflow
for k, v in ONT2GUIDE.items():
    assert v in guide_all, f"ONT2GUIDE target not in guidelines: {v!r} (for {k})"

# ---- collect data subflows + flow + count ----
data_sub: Counter = Counter()
data_flow: dict = {}
for split in ("train", "dev", "test"):
    for c in d[split]:
        sc = c.get("scenario") or {}
        sf = sc.get("subflow")
        if sf:
            data_sub[sf] += 1
            data_flow[sf] = sc.get("flow")
assert len(data_sub) == 96, f"expected 96 data subflows, got {len(data_sub)}"

# ---- variant rules ----
SINGLE_ITEM = {"boots": "Boots FAQ", "shirt": "Shirt FAQ",
               "jeans": "Jeans FAQ", "jacket": "Jacket FAQ"}
STOREWIDE = {"pricing": "Pricing FAQ", "membership": "Membership FAQ",
             "timing": "Timing FAQ", "policy": "Policy FAQ"}
re_si = re.compile(r"^(boots|shirt|jeans|jacket)_(how|other)_([1-4])$")
re_sw = re.compile(r"^(pricing|membership|timing|policy)_([1-4])$")

# ---- inferred (evidence in research/phase0/variant_verification.json) ----
INFERRED = {
    "status_questions": {
        "flow": "subscription_inquiry",
        "target": "Status Active",
        "confidence": "medium",
        "reason": ("Transcripts ask 'is my subscription active?'; action trace "
                   "pull-up-account -> verify-identity -> subscription-status -> "
                   "send-link matches the Status Active playbook. Generic name; "
                   "n=30."),
    },
    "status_delivery_date": {
        "flow": "order_issue",
        "target": "Status Delivery Time",
        "confidence": "high",
        "reason": ("Transcript: 'the delivery date of my order seems to be "
                   "wrong'. Uses ask-the-oracle + update-order, distinctive to "
                   "the Status Delivery Time playbook. n=3."),
    },
}

# ---- build the 96-row table ----
rows = []
for sf, cnt in sorted(data_sub.items()):
    fl = data_flow[sf]
    if sf in INFERRED:
        info = INFERRED[sf]
        rows.append({"subflow": sf, "flow": fl, "count": cnt,
                     "guidelines_subflow": info["target"],
                     "method": "INFERRED", "confidence": info["confidence"],
                     "reason": info["reason"]})
        continue
    m = re_si.match(sf)
    if m:
        base = m.group(1)
        rows.append({"subflow": sf, "flow": fl, "count": cnt,
                     "guidelines_subflow": SINGLE_ITEM[base],
                     "method": "VARIANT", "confidence": "high",
                     "reason": (f"Numbered variant of {base}; the guidelines "
                                f"document one '{SINGLE_ITEM[base]}' playbook "
                                f"for all {base} questions (how_N/other_N).")})
        continue
    m = re_sw.match(sf)
    if m:
        base = m.group(1)
        rows.append({"subflow": sf, "flow": fl, "count": cnt,
                     "guidelines_subflow": STOREWIDE[base],
                     "method": "VARIANT", "confidence": "high",
                     "reason": (f"Numbered variant of {base}; the guidelines "
                                f"document one '{STOREWIDE[base]}' playbook "
                                f"for all {base} questions.")})
        continue
    if sf in ONT2GUIDE:
        rows.append({"subflow": sf, "flow": fl, "count": cnt,
                     "guidelines_subflow": ONT2GUIDE[sf],
                     "method": "DIRECT", "confidence": "high",
                     "reason": "Name matches the ontology/guidelines subflow."})
        continue
    # anything left is unmapped
    rows.append({"subflow": sf, "flow": fl, "count": cnt,
                 "guidelines_subflow": None,
                 "method": "UNMAPPED", "confidence": "n/a",
                 "reason": "No confident mapping; needs manual review."})

# ---- sanity: everything maps to a real guideline subflow or is flagged ----
unmapped = [r for r in rows if r["method"] == "UNMAPPED"]
for r in rows:
    if r["guidelines_subflow"] is not None:
        assert r["guidelines_subflow"] in guide_all, r

# ---- coverage (conversation-weighted) ----
total = sum(r["count"] for r in rows)
covered = sum(r["count"] for r in rows if r["guidelines_subflow"] is not None)
coverage = round(covered / total, 3)

# ---- the 9 ontology subflows that never appear in the data ----
ontology_set = set()
for fl, names in o["intents"]["subflows"].items():
    for n in names:
        ontology_set.add(n)
unused_ontology = sorted(ontology_set - set(data_sub))

out = {
    "description": ("Explicit mapping from the 96 ABCD data subflow values to "
                    "the 55 guidelines.json subflows (BON-37)."),
    "counts": {
        "data_subflows": len(rows),
        "direct": sum(1 for r in rows if r["method"] == "DIRECT"),
        "variant": sum(1 for r in rows if r["method"] == "VARIANT"),
        "inferred": sum(1 for r in rows if r["method"] == "INFERRED"),
        "unmapped": len(unmapped),
    },
    "conversation_coverage": coverage,
    "covered_conversations": covered,
    "total_conversations": total,
    "unused_ontology_subflows": unused_ontology,
    "mapping": rows,
}

jp = ROOT / "research/abcd_subflow_mapping.json"
jp.write_text(json.dumps(out, indent=2))

cp = ROOT / "research/abcd_subflow_mapping.csv"
with cp.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subflow", "flow", "count", "guidelines_subflow",
                "method", "confidence", "reason"])
    for r in rows:
        w.writerow([r["subflow"], r["flow"], r["count"],
                    r["guidelines_subflow"], r["method"], r["confidence"],
                    r["reason"]])

print(f"data subflows:        {len(rows)}")
print(f"  DIRECT:             {out['counts']['direct']}")
print(f"  VARIANT:            {out['counts']['variant']}")
print(f"  INFERRED:           {out['counts']['inferred']}")
print(f"  UNMAPPED:           {len(unmapped)} {unmapped}")
print(f"conversation coverage:{coverage}  ({covered}/{total})")
print(f"unused ontology (9):  {unused_ontology}")
print(f"wrote {jp}")
print(f"wrote {cp}")
