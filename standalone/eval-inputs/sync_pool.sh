#!/usr/bin/env bash
# abcd_1000_pool.jsonl уже есть в репо (1.7MB) — дублировать через Contents API
# нельзя (лимит ~1MB). Эта копия кладёт его рядом с остальным паком.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
src="$here/../h1-experience-cards/data/abcd_1000_pool.jsonl"
dst="$here/abcd_1000_pool.jsonl"
if [[ ! -f "$src" ]]; then
  echo "missing $src — clone the full repo first" >&2
  exit 1
fi
cp -f "$src" "$dst"
echo "copied $src -> $dst"
wc -l "$dst"
