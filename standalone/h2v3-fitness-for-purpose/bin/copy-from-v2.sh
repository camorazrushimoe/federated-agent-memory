#!/usr/bin/env bash
# Materialize v2 + v1 harness into this folder. Safe to re-run.
# Does NOT overwrite v3-owned files listed in KEEP.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
v2="$here/../h2v2-categorical-scoped-memory"
v1="$here/../h2-federated-scoped-memory"

if [[ ! -d "$v2" ]]; then
  echo "missing $v2" >&2
  exit 1
fi

# 1. Give v2 its own v1 copies (gold, mix, llm, checks, slice).
if [[ -x "$v2/bin/copy-from-v1.sh" ]]; then
  bash "$v2/bin/copy-from-v1.sh"
fi

copy_from() {
  local src_root="$1"
  local rel="$2"
  mkdir -p "$here/$(dirname "$rel")"
  if [[ ! -f "$src_root/$rel" ]]; then
    echo "skip missing $src_root/$rel"
    return 0
  fi
  cp -f "$src_root/$rel" "$here/$rel"
  echo "copied $rel"
}

# 2. v2-owned search stack
for rel in \
  CATEGORIES.md \
  MAP.md \
  bin/config.py \
  bin/prompts.py \
  bin/tag.py \
  bin/tag_parallel.py \
  bin/retrieve.py \
  bin/eval_live_d4.py \
  bin/run_oracle_d4.py \
  bin/patch_v1_checks.py
do
  copy_from "$v2" "$rel"
done

# 3. v1 harness that v2 just materialized (prefer v2 tree so patches apply)
for rel in \
  bin/adapt_h1_corpus.py \
  bin/build_phase_c_inputs.py \
  bin/checks.py \
  bin/common.py \
  bin/eval.py \
  bin/ingest.py \
  bin/label_gold_useful.py \
  bin/llm.py \
  bin/mix.py \
  bin/rank.py \
  bin/update.py \
  D0-GOLD.md \
  DATA-AUDIT.md \
  data/d0_slice.jsonl \
  data/gold_useful.jsonl \
  data/gold_useful.manifest.json \
  data/gold_useful.seed.jsonl
do
  if [[ -f "$v2/$rel" ]]; then
    copy_from "$v2" "$rel"
  else
    copy_from "$v1" "$rel"
  fi
done

chmod +x "$here/bin/"*.sh "$here/bin/"*.py 2>/dev/null || true
echo "done. v3-owned files left intact: README SPEC EVAL-PLAN PROMPTS DATA PIPELINE"
echo "WHY-THIS-ROUND ROUND-0-PLAN HANDOFF SOURCE LAB-BRIEF"
echo "bin/copy-from-v2.sh bin/sync_h1_data.sh bin/build_ffp_packets.py"
echo "bin/judge_ffp.py bin/eval_ffp.py bin/prompts_judge.py bin/split_pool_query.py"
