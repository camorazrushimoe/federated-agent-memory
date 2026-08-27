#!/usr/bin/env python3
"""stage_pass2.py — build the clean stage directory + prompt for a FRESH-context
pass 2 labeling run (protocol §3 mechanism (c), RUNBOOK S2).

Why a script, not a habit: pass independence is the load-bearing property of
the two-pass design. If staging is mechanical, "the fresh context saw ONLY
protocol + pass2_input.jsonl" becomes a verifiable artifact (stage_manifest
with file hashes), not a recollection.

Usage:
  python3 stage_pass2.py --passes research/phase2/m1/passes --out /tmp/m1_p2_stage
  (optionally --label-out <path the subagent must write>)

Outputs:
  <out>/PROTOCOL-m1-pairs.md   (copied verbatim from this directory)
  <out>/pass2_input.jsonl      (copied verbatim)
  <out>/stage_manifest.json    (source paths + sha256 of each staged file)
  <out>/pass2_prompt.md        (the exact prompt to give the fresh agent)
  <out>/pass2_check.py         (conformance checker for the returned labels)

The stage directory must contain NOTHING else — the script removes any stray
files (including any pass1 labels) and records the deletion in the manifest.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", required=True, help="dir with pass2_input.jsonl")
    ap.add_argument("--out", required=True, help="clean stage dir (created/reset)")
    ap.add_argument("--label-out", default="pass2_labels.jsonl",
                    help="file name the subagent must write (relative to stage dir)")
    a = ap.parse_args()

    passes = Path(a.passes)
    p2 = passes / "pass2_input.jsonl"
    proto = HERE / "PROTOCOL-m1-pairs.md"
    out = Path(a.out)
    if not p2.is_file():
        sys.exit(f"FATAL: {p2} not found — run split_passes.py first")
    if not proto.is_file():
        sys.exit(f"FATAL: protocol not next to this script: {proto}")

    # Reset the stage dir: anything pre-existing (esp. pass1 labels) is a
    # contamination risk; remove and record it.
    removed = []
    if out.exists():
        for f in out.iterdir():
            removed.append(f.name)
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
    out.mkdir(parents=True, exist_ok=True)

    shutil.copy2(proto, out / "PROTOCOL-m1-pairs.md")
    shutil.copy2(p2, out / "pass2_input.jsonl")
    n_pairs = sum(1 for l in p2.read_text().splitlines() if l.strip())

    manifest = {
        "purpose": "fresh-context pass-2 stage (protocol §3(c))",
        "staged": {
            "PROTOCOL-m1-pairs.md": sha256_file(out / "PROTOCOL-m1-pairs.md"),
            "pass2_input.jsonl": sha256_file(out / "pass2_input.jsonl"),
        },
        "n_pairs": n_pairs,
        "pre_existing_removed": removed,
        "label_out": a.label_out,
        "rule": "the fresh agent sees ONLY this directory + this prompt; "
                "no pass-1 file, no pass-1 summary, no prior labeling context",
    }
    (out / "stage_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    prompt = f"""You are performing PASS 2 of a two-pass labeling exercise for a research gold set (M1 pair set) in the Federated Agent Memory project.
Files you may and should use (the ONLY files you have):
- {out}/PROTOCOL-m1-pairs.md — the frozen protocol v1.1 (READ IT FIRST; it defines the 3-class scale, adjudication rules R1-R6, and the honesty clause).
- {out}/pass2_input.jsonl — {n_pairs} pairs, one JSON object per line, fields: pair_id, display. The display is two conversations (CONV A / CONV B) with customer turns.
Constraints (non-negotiable):
- Label each of the {n_pairs} pairs exactly once with one of: same-problem | related-but-different | unrelated, per the protocol's scale and rules R1-R6.
- Do not look at, reference, or assume any other label file. You have no access to any pass-1 output — that is by design (pass independence).
- Give each item a one-line rationale (10-25 words).
- Work in English.
Output: write the file {out}/{a.label_out} with one JSON object per line, in the order the input file presents the pairs:
{{"pair_id": "<id>", "pass": 2, "label": "<label>", "rationale": "<one line>"}}
Then report: (1) the path you wrote, (2) the pair_id -> label results, (3) confirmation that you used only the two staged files.
"""
    (out / "pass2_prompt.md").write_text(prompt + "\n")

    check = f"""""" + "\n".join([
        '"""Conformance check for the fresh-context pass-2 labels file."""',
        "import json, sys",
        f'VALID = {{"same-problem", "related-but-different", "unrelated"}}',
        f'rows = [json.loads(l) for l in open(r"{out}/{a.label_out}") if l.strip()]',
        f'inp = [json.loads(l) for l in open(r"{out}/pass2_input.jsonl") if l.strip()]',
        'assert len(rows) == len(inp), "row count mismatch"',
        "assert [r['pair_id'] for r in rows] == [r['pair_id'] for r in inp], 'order mismatch'",
        "for r in rows:",
        "    assert set(r.keys()) == {'pair_id','pass','label','rationale'}, f\"fields {sorted(r.keys())}\"",
        "    assert r['pass'] == 2",
        "    assert r['label'] in VALID, f\"bad label {r['label']!r}\"",
        "    assert len(r['rationale'].strip()) >= 5, 'rationale too short'",
        'print(f"PASS2 LABELS CONFORM: {len(rows)}/{len(inp)} pairs")',
        "",
    ]) + "\n"
    (out / "pass2_check.py").write_text(check + "\n")

    print(json.dumps(manifest, indent=2))
    print(f"STAGE READY: {out}  (prompt: pass2_prompt.md — give it to a FRESH agent session)")


if __name__ == "__main__":
    main()
