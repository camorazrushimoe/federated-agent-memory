#!/usr/bin/env python3
"""Patch copied v1 checks.py so S0 does not enforce the old tag schema.

v1 C-TG4: ending in {resolved, unresolved, escalated, unknown}
v1 C-TG3 message: 5-field tag_key
v2: ending has resolved_* split; tag_key is problem_shape only.
Safe to re-run.
"""
from __future__ import annotations

from pathlib import Path

p = Path(__file__).resolve().parent / "checks.py"
if not p.exists():
    raise SystemExit("bin/checks.py missing — run bin/copy-from-v1.sh first")
text = p.read_text()
old_enum = '{"resolved", "unresolved", "escalated", "unknown"}'
new_enum = '{"resolved_info", "resolved_action", "resolved_exception", "unresolved", "escalated", "unknown"}'
if old_enum not in text and new_enum in text:
    print("already patched", p)
    raise SystemExit(0)
if old_enum not in text:
    raise SystemExit(f"pattern not found in {p}: {old_enum}")
text = text.replace(old_enum, new_enum, 1)
text = text.replace(
    "tag_key == problem_shape|constraint|ending|channel|vertical, no edge spaces",
    "tag_key == problem_shape (H2v2), no edge spaces",
)
text = text.replace(
    "ending in enum; constraint <=12 words or 'none'; problem_shape <=12 words",
    "ending in v2 enum; constraint is a vocab id; problem_shape is a vocab id",
)
p.write_text(text)
print("patched", p)
