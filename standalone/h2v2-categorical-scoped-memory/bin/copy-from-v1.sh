#!/usr/bin/env bash
# Materialize reusable v1 files into this folder (byte copy, no edits).
# Safe to re-run. Does NOT overwrite v2-owned files listed in KEEP.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
src="$here/../h2-federated-scoped-memory"

copy_list=(
  bin/adapt_h1_corpus.py
  bin/audit.py
  bin/build_phase_c_inputs.py
  bin/checks.py
  bin/common.py
  bin/eval.py
  bin/ingest.py
  bin/label_gold_useful.py
  bin/llm.py
  bin/mix.py
  bin/outcome.py
  bin/package_d0_run.py
  bin/rank.py
  bin/replay.py
  bin/run_slice.py
  bin/update.py
  bin/write_d0_slice.py
  CHECKS.md
  D0-GOLD.md
  DATA-AUDIT.md
  ENGINEERING-LAYER.md
  RUN-PROTOCOL.md
  SIMPLIFICATIONS.md
  data/gold_useful.jsonl
  data/gold_useful.manifest.json
  data/d0_slice.jsonl
  fixtures/dialogues.jsonl
  fixtures/gold_useful.jsonl
  fixtures/queries/d-007.json
)

for rel in "${copy_list[@]}"; do
  mkdir -p "$here/$(dirname "$rel")"
  cp -f "$src/$rel" "$here/$rel"
  echo "copied $rel"
done

echo "done. v2-owned files left intact: README CATEGORIES WHY-NOT-V1 SPEC PROMPTS"
echo "config.py prompts.py tag.py retrieve.py gold_tags.jsonl"
