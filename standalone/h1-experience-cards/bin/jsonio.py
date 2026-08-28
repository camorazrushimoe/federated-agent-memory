#!/usr/bin/env python3
"""Deterministic JSON/JSONL IO for the H1 experience-card pipeline.

Determinism rule (brief §6): fixed key order everywhere. Schema records are
written in the exact key order of the SPEC §3/§4 examples (dict insertion
order is preserved by json.dumps). Free-form artifacts (raw LLM records,
manifests) use sort_keys=True — consistent either way, determinism is what
matters.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import json
import os


def dumps(obj, indent=None):
    """Deterministic compact JSON (no key sorting — caller controls order)."""
    return json.dumps(obj, ensure_ascii=False, indent=indent,
                      separators=(",", ":") if indent is None else None)


def dump_sorted(obj, indent=None):
    """Deterministic JSON with sorted keys (for free-form artifacts)."""
    return json.dumps(obj, ensure_ascii=False, indent=indent, sort_keys=True,
                      separators=(",", ":") if indent is None else None)


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows, key_order=None):
    """Write rows as JSONL. Rows keep their own key order; use key_order to
    enforce a canonical order (e.g. SPEC schema order)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            if key_order is not None:
                ordered = {k: row[k] for k in key_order if k in row}
                # keep any extra keys (should not happen for schema records)
                for k, v in row.items():
                    if k not in ordered:
                        ordered[k] = v
                fh.write(dumps(ordered) + "\n")
            else:
                fh.write(dumps(row) + "\n")


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj, sort_keys=True, indent=2):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(dump_sorted(obj, indent=indent) if sort_keys else dumps(obj, indent=indent))
        fh.write("\n")


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def row_count(path):
    n = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n
