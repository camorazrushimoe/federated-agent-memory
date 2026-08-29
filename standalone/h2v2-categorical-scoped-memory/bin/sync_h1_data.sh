#!/usr/bin/env bash
# Copy the H1 ABCD pack into this experiment's data/.
# Does not delete the H1 original. No H1 code is imported.
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
src="$root/standalone/h1-experience-cards/data"
dst="$root/standalone/h2v2-categorical-scoped-memory/data"
mkdir -p "$dst"
for f in abcd_1000_pool.jsonl abcd_200_holdout.jsonl preview_10.jsonl; do
  cp -f "$src/$f" "$dst/$f"
done
echo "synced into $dst"
ls -l "$dst"/*.jsonl
