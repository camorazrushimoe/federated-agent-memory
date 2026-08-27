#!/usr/bin/env python3
"""Quick check of the ABCD conversation turn schema (speaker values, action fields)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
d = json.loads((ROOT / "data/abcd/abcd_v1.1.json").read_text())
c = d["train"][0]
print("conversation keys:", list(c.keys()))
print("scenario:", c["scenario"])
for t in c["delexed"][:6]:
    print(json.dumps(t)[:220])
print("speaker values seen:", sorted({str(t.get("speaker")) for t in c["delexed"]}))

# also check an action turn's exact shape
for t in c["delexed"]:
    if t.get("speaker") == "action":
        print("action turn shape:", json.dumps(t)[:300])
        break
