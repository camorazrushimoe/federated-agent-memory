#!/usr/bin/env python3
"""Package the D0 run dir: runs/<date>_D0_gold_useful/manifest.json (§5.5).

Reads the labeler's data/gold_useful.manifest.json + gold + slice and writes
the ROUND-0-PLAN §5.5 manifest (labeler cost lives here, NEVER in the S2
cost.json). The raw transcripts stay in data/raw_gold_useful (gitignored).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
H2 = HERE.parent
DATA = H2 / "data"

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    lm = json.loads((DATA / "gold_useful.manifest.json").read_text(encoding="utf-8"))
    gold_path = DATA / "gold_useful.jsonl"
    slice_path = DATA / "d0_slice.jsonl"
    statuses = lm.get("statuses", [])
    n_err = sum(1 for s in statuses if s.get("status") != "labeled" and s.get("status") != "no_candidates")
    usage = lm.get("usage", {})
    qs = lm.get("slice", {}).get("queries", [])
    max_cands = max((q.get("n_candidates", 0) for q in qs), default=0)
    run_id = "2026-08-29_D0_gold_useful"
    run_dir = H2 / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    # the run dir is the REPLICA RECORD: its gold_useful.jsonl (if present)
    # is the labeler's raw output at run time — never overwrite it with a
    # later-curated data/gold_useful.jsonl.
    record_gold = run_dir / "gold_useful.jsonl"
    gold_src = record_gold if record_gold.exists() else gold_path
    manifest = {
        "run_id": run_id,
        "kind": "gold_useful",
        "human_gold": False,
        "agent_labeled": True,
        "labeler_model": lm.get("model"),
        "base_url": None,  # resolved from H2_BASE_URL at run time; key never stored
        "temperature": lm.get("temperature"),
        "k": max_cands,
        "prompts_sha": lm.get("prompt_sha256"),
        "pool_sha": lm["inputs"]["pool"]["sha256"],
        "holdout_sha": lm["inputs"]["holdout"]["sha256"],
        "slice_sha": sha256_file(slice_path),
        "gold_out_sha": sha256_file(gold_src),
        "gold_out_source": str(gold_src.relative_to(H2)),
        "rows": len(statuses),
        "label_error_rows": n_err,
        "calls": usage.get("calls"),
        "tokens_in": usage.get("prompt_tokens"),
        "tokens_out": usage.get("completion_tokens"),
        "usd": None,  # no price source -> null, never a guess (C-EV7 pattern)
        "caveat": "AGENT-LABELED GOLD — NOT HUMAN GOLD",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = run_dir / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
