#!/usr/bin/env python3
"""BON-37 step 1: dump the three subflow name sets (guidelines/ontology/data)
grouped by flow, so the 96->55 mapping can be built deliberately.

Output: research/phase0/subflow_inventory.json
Re-run:  python research/phase0/subflow_inventory.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "data/abcd/guidelines.json"
O = ROOT / "data/abcd/ontology.json"
D = ROOT / "data/abcd/abcd_v1.1.json"

g = json.loads(G.read_text())
o = json.loads(O.read_text())
d = json.loads(D.read_text())

gsub = defaultdict(list)
for flow, body in g.items():
    for name in (body.get("subflows") or {}):
        gsub[flow].append(name)

osub = dict(o["intents"]["subflows"])

data_sub = Counter()
data_flow = {}
for split in ("train", "dev", "test"):
    for c in d[split]:
        sc = c.get("scenario") or {}
        sf = sc.get("subflow")
        if sf:
            data_sub[sf] += 1
            data_flow[sf] = sc.get("flow")

out = {
    "guidelines": dict(gsub),
    "ontology": dict(osub),
    "data": dict(data_sub),
    "data_flow": data_flow,
}
out_path = Path(__file__).resolve().parent / "subflow_inventory.json"
out_path.write_text(json.dumps(out, indent=2))

print(f"guidelines subflows: {sum(len(v) for v in gsub.values())}")
print(f"ontology subflows:   {sum(len(v) for v in osub.values())}")
print(f"data subflows:       {len(data_sub)}")
print(f"saved -> {out_path}")
