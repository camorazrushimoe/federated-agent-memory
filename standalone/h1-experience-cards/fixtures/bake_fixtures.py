#!/usr/bin/env python3
"""Bake the fixture extract responses (one real LLM call per dialogue, committed).

    export H1_API_KEY=<key> H1_MODEL=<model> H1_BASE_URL=<url>
    python fixtures/bake_fixtures.py

Runs the REAL extract prompt against the pinned extract model for every
fixture dialogue that the suite extracts, and writes
fixtures/raw/extract/<dialogue_id>.json. Those files are what the fixture
suite replays with zero LLM calls (checks.py FixtureSuite).

Re-bake when PROMPTS.md or the fixture dialogues change; the baked files are
committed so the S0 gate never depends on a live key.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE.parent / "bin"

EXTRACTED = [
    "d001.jsonl", "ten_dupes_2agents.jsonl", "gift_card.jsonl",
    "freshness_new_member.jsonl", "freshness_quiet.jsonl", "two_clusters.jsonl",
    # live_d013 is extracted mid-suite by the anti-echo test (F10.4)
    "live_d013.jsonl",
]

if __name__ == "__main__":
    model = os.environ.get("H1_MODEL")
    base_url = os.environ.get("H1_BASE_URL")
    if not model or not base_url or not os.environ.get("H1_API_KEY"):
        raise SystemExit("bake_fixtures.py needs H1_API_KEY, H1_MODEL, H1_BASE_URL")

    raw_dir = HERE / "raw" / "extract"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="h1_bake_") as td:
        tmp = Path(td)
        for fx in EXTRACTED:
            dialogues = tmp / fx  # fx already ends in .jsonl
            cards = tmp / f"{fx}.cards.jsonl"
            subprocess.run([sys.executable, str(BIN / "ingest.py"),
                            "--in", str(HERE / fx), "--out", str(dialogues)],
                           check=True, capture_output=True)
            # --raw-dir points at the committed fixtures/raw/extract so the
            # recorded responses are written in place.
            subprocess.run([sys.executable, str(BIN / "extract.py"),
                            "--in", str(dialogues), "--out", str(cards),
                            "--model", model, "--base-url", base_url,
                            "--raw-dir", str(raw_dir),
                            "--clock-start", "2026-08-28T00:00:00Z"],
                           check=True, capture_output=True)
            print(f"baked {fx}")
    n = len(list(raw_dir.glob("*.json")))
    print(f"total baked responses: {n}")
