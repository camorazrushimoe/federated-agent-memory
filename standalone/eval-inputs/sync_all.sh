#!/usr/bin/env bash
# Полная локальная копия входов рядом с экспериментами.
# Оригиналы не удаляет и не двигает.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
h1="$root/standalone/h1-experience-cards/data"
h2="$root/standalone/h2-federated-scoped-memory/data"

copy() {
  local src="$1" name="$2"
  if [[ ! -f "$src" ]]; then
    echo "missing $src" >&2
    exit 1
  fi
  cp -f "$src" "$here/$name"
  echo "copied $name ($(wc -l < "$here/$name") lines)"
}

copy "$h1/abcd_1000_pool.jsonl" "abcd_1000_pool.jsonl"
copy "$h1/abcd_200_holdout.jsonl" "abcd_200_holdout.jsonl"
copy "$h1/preview_10.jsonl" "preview_10.jsonl"
copy "$h2/d0_slice.jsonl" "d0_slice.jsonl"
copy "$h2/gold_useful.jsonl" "gold_useful.jsonl"
copy "$h2/gold_useful.manifest.json" "gold_useful.manifest.json"
copy "$h2/gold_useful.seed.jsonl" "gold_useful.seed.jsonl"

python3 - "$here" <<'PY'
import json, sys
from pathlib import Path
here = Path(sys.argv[1])
holdout = {}
for line in (here / "abcd_200_holdout.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    holdout[f"d-{row['chat_id']}"] = row
out = []
for line in (here / "d0_slice.jsonl").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    s = json.loads(line)
    raw = holdout[s["query_id"]]
    out.append({
        "query_id": s["query_id"],
        "family": s["family"],
        "unlock": s["unlock"],
        "closed_at": s["closed_at"],
        "chat_id": raw["chat_id"],
        "tenant": raw.get("tenant"),
        "vertical": raw.get("vertical"),
        "n_turns": raw.get("n_turns"),
        "turns": raw.get("turns"),
    })
(here / "queries_60.jsonl").write_text(
    "\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n",
    encoding="utf-8",
)
print(f"wrote queries_60.jsonl ({len(out)} queries)")
PY

echo
echo "pack ready in $here"
ls -lh "$here"
