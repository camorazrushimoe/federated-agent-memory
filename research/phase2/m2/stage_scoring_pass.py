#!/usr/bin/env python3
"""stage_scoring_pass.py — M2 judge harness (R2): stage the SCORING pass for
the reconstruction test. FROZEN TWO-CALL structure (restored per the lead
adjudication, GH #6 5450060638 §2; interpretation #3 override).

Pre-registered spec (GH #6 5449115746 §3): after the blind answering passes,
the judge scores each candidate against its own transcript-derived reference.
The frozen cost line is "80 × (1 reference call + 1 scoring call over all 3
candidates) = 160" — a TWO-call structure per conversation:

  Call 1 — the REFERENCE (transcript ONLY → the judge's R1–R3). The reference
      is the anchor of the rubric and MUST be formed in a context that has
      NOT seen the candidates, so it is derived purely from the transcript.
      A candidate in the reference context would corrupt the anchor.

  Call 2 — the SCORING (transcript + the 3 anonymized candidates + the
      COMMITTED reference → scores). In a fresh context the judge reads the
      committed reference as the anchor and scores each candidate against it
      with the frozen rubric:
        Q1: 1 = intent+structure both correct, 0.5 = one axis correct, 0 = wrong
        Q2: 1 = the binding constraint, 0.5 = a real but non-binding constraint,
             0 = none/wrong
        Q3: 1 = all resolution actions in order, 0.5 = all present wrong order,
             0.25 = >= half present, 0 = else
      value(candidate) = (s1+s2+s3)/3

Cost (frozen ceiling): 480 blind answering calls + 80 reference calls +
80 scoring calls = **640 — exactly the frozen ceiling** (5449115746 §3). The
earlier combined single call (80) was confirmed in error by the R2 review
(5449907074 §2.3) and overridden by the lead adjudication (5450060638 §2);
this is the restored structure.

The two calls are SEPARATE fresh agent contexts: Call 1 never sees the
candidates; Call 2 receives the committed reference as input.

Reuses the R1 labeling infra pattern (same bind/stage split as
stage_blind_pass.py):
  BIND layer (--bind, committed):
    PROTOCOL-m2-scoring.md  the frozen 2-call scoring protocol (the two-call
                            structure, rubric, output contract, honesty clause)
    reference_input.jsonl   80 rows: convo_codename + transcript ONLY (the B0
                            render — that IS the transcript). NO candidates
                            (anti-leak: the reference context is candidate-free)
    scoring_base.jsonl      80 rows: convo_codename + transcript + the 3
                            anonymized candidate renders (per-convo
                            seeded-shuffled order). NO reference (added at the
                            scoring stage, from the committed reference call)
    convo_mapping.json      convo_codename -> convo_id; candidate codename
                            -> (convo_id, candidate) [reuses the blind bind's
                            item codenames — one codename space]
    scoring_manifest.json   seeds, sha256 of every file, assertions, budget
    bind.md
  STAGE layer (per call, per fresh agent session):
    --stage-reference --stage-dir D: ONLY protocol + reference_input +
      reference prompt + reference conformance checker + stage manifest
      (fresh-context purity; NO candidates, NO scoring base, NO mapping)
    --stage-scoring --stage-dir D --reference <reference_answers.jsonl>:
      validates the committed reference (all convos, R1–R3 non-empty), then
      builds scoring_input.jsonl = scoring_base + the committed reference,
      and stages ONLY protocol + scoring_input + scoring prompt + scoring
      conformance checker + stage manifest

Anonymization: candidates keep the blind bind's item codenames (the judge
sees codenames, never "B0/B1/B2" labels — all three are scored under
identical treatment, per "baselines scored identically"); the per-convo
candidate ORDER is seeded-shuffled (seed 20261101). The transcript is the
B0 render — giving the transcript is giving B0's content; the pre-
registration scores all three candidates against the judge's own
references, including B0 (the ceiling's value is MEASURED, not assumed
1.0).

Honesty clause (rides with every M2 number): agent-judged; the reference and
the scores are produced in separate fresh contexts (the reference is
candidate-free by design). The agreement numbers reported in this round are
the BLIND answering passes' inter-pass disagreement, not this one.

Deterministic, stdlib only; pinned candidates sha verified at bind time.

Usage:
  python3 research/phase2/m2/stage_scoring_pass.py bind \
      --candidates research/phase2/m2/candidates.jsonl \
      --out research/phase2/m2/judge/scoring \
      [--seed 20261101]
  python3 research/phase2/m2/stage_scoring_pass.py stage-reference \
      --bind <bindir> --stage-dir <dir>
  python3 research/phase2/m2/stage_scoring_pass.py stage-scoring \
      --bind <bindir> --stage-dir <dir> --reference <reference_answers.jsonl>
  python3 research/phase2/m2/stage_scoring_pass.py --selftest
"""
import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

PINNED_CANDIDATES_SHA16 = "a54f52a557ce38b5"   # R2 fix-forward candidates (filled B2 draft slotted)
CANDIDATES = ["b0", "b1", "b2"]
N_CONVO_DEFAULT = 80
SEED_DEFAULT = 20261101
REFERENCE_FIELDS = ["convo_codename", "transcript"]
SCORING_BASE_FIELDS = ["convo_codename", "transcript", "candidates"]
SCORING_INPUT_FIELDS = ["convo_codename", "transcript", "reference", "candidates"]
N_BUDGET_BLIND = 480
N_BUDGET_REF = 80
N_BUDGET_SCORE = 80
N_BUDGET_TOTAL = 640   # the frozen ceiling (5449115746 §3)

PROTOCOL_MD = """# M2 Reconstruction — Scoring Protocol (pre-registered, v1.0)

**Round:** R2 (M2 extraction) · frozen on GH #6 5449115746 §3.
**Role:** independent judge (agent-judged). The transcript IS visible in
this pass. This is a **two-call** procedure per conversation (the frozen
structure, restored per the lead adjudication, GH #6 5450060638 §2):

- **Call 1 — the reference.** The judge reads the TRANSCRIPT ONLY (no
  candidates in context) and writes its own reference answers R1–R3. The
  reference is the anchor of the rubric; it MUST be formed in a context that
  has NOT seen the candidates, so it is derived purely from the transcript.
- **Call 2 — the scoring.** In a fresh context the judge reads the transcript
  + the three anonymized candidates + its COMMITTED reference (Call 1's
  output), and scores each candidate against that reference with the frozen
  rubric.

The two calls are separate fresh agent contexts: Call 1 never sees the
candidates; Call 2 receives the committed reference as input.

## 1. What each call sees

- **Call 1 (reference):** `convo_codename` (an anonymized id — identifies
  nothing) + `transcript` (the full conversation, "speaker: text" turns).
  NOTHING else — no candidates.
- **Call 2 (scoring):** `convo_codename` + `transcript` + `reference`
  (the committed R1–R3 from Call 1) + `candidates` — three renders, each
  with a `codename`. The codenames are random; they do NOT identify the
  candidate type. The candidate order is shuffled. Do not infer candidate
  type from the codename or the order (rule R2 below).

## 2. Call 1 — the reference (transcript ONLY)

From the transcript ONLY:
- **R1 — the problem.** Intent (what the customer wants done) and the
  structure (the symptom/constraint that drove the resolution).
- **R2 — the binding constraint.** The constraint/symptom that actually
  determined the resolution (or `not identifiable`).
- **R3 — what worked.** The resolution actions, in order.

The reference is formed BEFORE and APART FROM any candidate. It is the
independent anchor; nothing about a candidate may influence it.

## 3. Call 2 — score each candidate against your committed reference (rubric, frozen)

- **s1 (Q1 — the problem):** 1 = intent + structure both correct vs R1;
  0.5 = exactly one axis correct; 0 = wrong.
- **s2 (Q2 — the binding constraint):** 1 = the binding constraint (R2);
  0.5 = a real but non-binding constraint; 0 = none / wrong.
- **s3 (Q3 — what worked):** 1 = all resolution actions present and in
  order vs R3; 0.5 = all present, wrong order; 0.25 = at least half
  present; 0 = else.
- `value = (s1 + s2 + s3) / 3`.

Rules:
- **R1 — Reference from the transcript only.** R1–R3 must be derivable from
  the transcript; no outside knowledge; formed apart from the candidates.
- **R2 — No candidate-type inference.** Score by content only; the
  codenames are random.
- **R3 — Fidelity of the candidate decides.** Score what the candidate
  SAYS, not what you think it intended. A thin candidate that gets the
  one axis it carries right gets 0.5, not 0 (Q1 rule); Q2 `not
  identifiable` when your R2 is `not identifiable` scores 1.
- **R4 — Same standard for all three candidates.** The transcript itself
  is one of the candidates; score it by the same rubric as the others —
  its value is MEASURED, not assumed.
- **R5 — English.** R1–R3 and any notes in English; scores are exactly
  one of the frozen values above (no other numbers).

## 4. Output contract

**Call 1** — one JSON object per line, one per item, in the order the input
file presents the items:
```
{"convo_codename": "<codename>", "r1": "...", "r2": "...", "r3": "..."}
```

**Call 2** — one JSON object per line, one per item, in the order the input
file presents the items:
```
{"convo_codename": "<codename>",
 "scores": {"<candidate codename>": {"s1": <v>, "s2": <v>, "s3": <v>}, ...}}
```
`scores` must contain ALL THREE candidate codenames. s-values: s1 ∈
{0, 0.5, 1}, s2 ∈ {0, 0.5, 1}, s3 ∈ {0, 0.25, 0.5, 1}.

## 5. Budget (frozen)

Per conversation: 1 reference call + 1 scoring call = 2 calls. 80
conversations → 160 calls. The whole round is 480 blind answering calls +
160 scoring calls = **640 — exactly the frozen ceiling** (5449115746 §3).

## 6. Honesty clause (read before quoting any number from this protocol)

All judging is AGENT-JUDGED. The reference and the scores are produced in
separate fresh contexts (the reference is candidate-free by design). The
agreement numbers reported in this round are the BLIND answering passes'
inter-pass disagreement. Nothing here is "human gold" or "human agreement".
"""


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def codename(key):
    """Deterministic 6-hex digest — same space as the blind bind's item
    codenames (key = f'm2blind:c{NNN}' per (convo, candidate); the convo
    key = f'm2blind:convo:{convo_id}')."""
    return hashlib.sha256(key.encode()).hexdigest()[:6]


def build(rows, seed):
    """80 scoring rows: convo_codename + transcript + 3 anonymized candidate
    renders in per-convo seeded-shuffled order. NO reference (added at the
    scoring stage, from the committed reference call)."""
    rows = sorted(rows, key=lambda r: r["convo_id"])
    out = []
    cands_map = {}
    for i, row in enumerate(rows):
        rng = random.Random(f"{seed}:{row['convo_id']}")
        renders = [{"codename": codename(f"m2blind:c{3 * i + k + 1:03d}"),
                    "_candidate": cand,
                    "render": row[cand]} for k, cand in enumerate(CANDIDATES)]
        rng.shuffle(renders)
        cc = codename(f"m2blind:convo:{row['convo_id']}")
        for r in renders:
            cands_map[f"{cc}|{r['codename']}"] = {
                "convo_id": row["convo_id"],
                "candidate": r["_candidate"],
            }
        out.append({"convo_codename": cc, "transcript": row["b0"],
                    "candidates": [{k: r[k] for k in ("codename", "render")} for r in renders]})
    return out, cands_map


def bind(candidates_path, outdir, seed, n_convo):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(candidates_path).read_text().splitlines() if l.strip()]
    assert len(rows) == n_convo, f"expected {n_convo} rows, got {len(rows)}"
    for row in rows:
        for cand in CANDIDATES:
            assert isinstance(row.get(cand), str) and row[cand], \
                f"row {row.get('convo_id')}: missing render {cand}"

    items, cands_map = build(rows, seed)
    convos_map = {it["convo_codename"]: rows[i]["convo_id"]
                  for i, it in enumerate(items)}
    convos = {c: codename(f"m2blind:convo:{c}") for c in
              (r["convo_id"] for r in sorted(rows, key=lambda r: r["convo_id"]))}

    (outdir / "PROTOCOL-m2-scoring.md").write_text(PROTOCOL_MD)
    proto_sha = sha256_file(outdir / "PROTOCOL-m2-scoring.md")

    # Call 1 input: transcript ONLY (the reference context is candidate-free)
    (outdir / "reference_input.jsonl").write_text(
        "\n".join(json.dumps({k: it[k] for k in REFERENCE_FIELDS}, separators=(",", ":"))
                  for it in items) + "\n")
    ref_sha = sha256_file(outdir / "reference_input.jsonl")

    # Call 2 base: transcript + 3 anonymized candidates (NO reference yet)
    (outdir / "scoring_base.jsonl").write_text(
        "\n".join(json.dumps({k: it[k] for k in SCORING_BASE_FIELDS}, separators=(",", ":"))
                  for it in items) + "\n")
    base_sha = sha256_file(outdir / "scoring_base.jsonl")

    # codename collisions across the whole space (80 convo + 240 candidate)
    all_c = set(convos.values())
    all_c |= set(k.split("|")[1] for k in cands_map)
    assert len(all_c) == n_convo + 3 * n_convo, "codename collision in scoring space"

    (outdir / "convo_mapping.json").write_text(
        json.dumps({"convo_codename -> convo_id": convos_map,
                    "candidate_codename -> {convo_id, candidate}": cands_map,
                    "use": "de-anonymization at JOIN time only — NEVER part of the reference or scoring context"},
                   indent=1, sort_keys=True) + "\n")
    map_sha = sha256_file(outdir / "convo_mapping.json")

    manifest = {
        "purpose": (f"M2 reconstruction SCORING pass (frozen TWO-CALL structure, "
                    f"restored per 5450060638 §2): per convo, Call 1 = reference "
                    f"(transcript ONLY → R1-R3, candidate-free context) + Call 2 = "
                    f"scoring (transcript + 3 candidates + the committed reference → "
                    f"scores). {n_convo} convos x (1 reference + 1 scoring) = "
                    f"{2 * n_convo} calls; round total {N_BUDGET_BLIND} blind + "
                    f"{N_BUDGET_REF} reference + {N_BUDGET_SCORE} scoring = "
                    f"{N_BUDGET_TOTAL} (exactly the frozen ceiling, 5449115746 §3)"),
        "structure": ("2 calls per convo — (1) reference call (transcript ONLY, "
                      "no candidates in context) → committed R1-R3; (2) scoring "
                      "call (transcript + 3 anonymized candidates + the committed "
                      "reference) → scores. Separate fresh contexts."),
        "n_items": len(items),
        "n_convos": n_convo,
        "candidates_per_item": CANDIDATES,
        "renders_source": ("byte-identical to the pinned candidates.jsonl fields "
                           "(transcript == `b0`; candidates == `b0`/`b1`/`b2` "
                           "anonymized + per-convo seeded-shuffled); the scored "
                           "B2 is the FINAL unit (the lead's 80-unit draft slotted "
                           "in, 5450060638 §1 item 1)"),
        "seed": seed,
        "sha256": {"reference_input": ref_sha, "scoring_base": base_sha,
                   "PROTOCOL-m2-scoring": proto_sha, "convo_mapping": map_sha},
        "reference_fields": REFERENCE_FIELDS,
        "scoring_base_fields": SCORING_BASE_FIELDS,
        "scoring_input_fields": SCORING_INPUT_FIELDS,
        "scoring_input_note": ("scoring_input.jsonl is NOT committed: it is built "
                               "at the scoring stage (stage-scoring) from "
                               "scoring_base + the committed reference answers "
                               "(the reference does not exist until Call 1 runs)"),
        "budget": {"blind": N_BUDGET_BLIND, "reference": N_BUDGET_REF,
                   "scoring": N_BUDGET_SCORE, "total": N_BUDGET_TOTAL,
                   "ceiling": N_BUDGET_TOTAL},
        "rule": ("candidates scored under IDENTICAL treatment (anonymized "
                 "codenames, shuffled order, no labels — 'baselines scored "
                 "identically'); the reference is formed in a candidate-free "
                 "context (the anchor is transcript-derived, not corrupted by "
                 "the candidates); the transcript is visible (it is the B0 "
                 "render) and B0 itself is one of the scored candidates — "
                 "its value is MEASURED, not assumed; no flow/band/product "
                 "metadata anywhere in the scoring context"),
        "honesty_clause": ("agent-judged; reference and scores in separate "
                           "fresh contexts (reference candidate-free); NOT "
                           "human agreement"),
    }
    (outdir / "scoring_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    (outdir / "bind.md").write_text(
        "# M2 scoring BIND layer (frozen 2-call structure)\n\n"
        f"{n_convo} convos. Two fresh-context calls: **reference** (transcript "
        "ONLY → R1-R3) and **scoring** (transcript + 3 anonymized candidates + "
        "the committed reference → scores). Reference + base are committed here; "
        "the scoring input is built at stage time from the committed reference. "
        f"Budget: {N_BUDGET_REF} reference + {N_BUDGET_SCORE} scoring = 160 "
        f"(round total {N_BUDGET_TOTAL}, the frozen ceiling).\n"
        "Stage: `stage_scoring_pass.py stage-reference --bind <this dir> "
        "--stage-dir <dir>` (Call 1); then "
        "`stage_scoring_pass.py stage-scoring --bind <this dir> --stage-dir <dir> "
        "--reference <reference_answers.jsonl>` (Call 2). Hand each staged "
        "directory (only) to a fresh agent session.\n\n"
        + "\n".join(f"- `{f.name}`" for f in sorted(outdir.iterdir())) + "\n")
    print(json.dumps(manifest, indent=1))
    print(f"SCORING BIND READY: {outdir} — stage-reference (Call 1), then stage-scoring (Call 2)")
    return manifest


def _write_reference_prompt(path, stage_dir, n_items):
    prompt = f"""You are performing the REFERENCE call (Call 1) of the M2 reconstruction SCORING pass (Federated Agent Memory, round R2).
Files you may and should use (the ONLY files you have):
- {stage_dir}/PROTOCOL-m2-scoring.md — the frozen scoring protocol v1.0 (READ IT FIRST: the two-call structure, the reference rules R1-R5, the Call 1 output contract, the budget, the honesty clause).
- {stage_dir}/reference_input.jsonl — {n_items} items, one JSON object per line: convo_codename, transcript.
Constraints (non-negotiable):
- For each item: write your OWN references R1-R3 from the TRANSCRIPT ONLY.
- You are given NO candidates in this call — by design (the reference must be formed in a context that has NOT seen the candidates). Do not look for or guess at candidates.
- Work in English.
Output: write {stage_dir}/reference_answers.jsonl with one JSON object per line, in the order the input file presents the items (see protocol section 4, Call 1):
{{"convo_codename": "<codename>", "r1": "...", "r2": "...", "r3": "..."}}
Every item exactly once, in input order.
Then report: (1) the path you wrote, (2) the count of lines, (3) confirmation that you used only the two staged files and saw NO candidates.
"""
    Path(path).write_text(prompt + "\n")


def _write_reference_check(path, stage_dir):
    check = "\n".join([
        '"""Conformance check for the M2 reference answers file (Call 1)."""',
        "import json",
        f'rows = [json.loads(l) for l in open(r"{stage_dir}/reference_answers.jsonl") if l.strip()]',
        f'inp = [json.loads(l) for l in open(r"{stage_dir}/reference_input.jsonl") if l.strip()]',
        'assert len(rows) == len(inp), f"row count {len(rows)} != {len(inp)}"',
        "assert [r['convo_codename'] for r in rows] == [r['convo_codename'] for r in inp], 'codename/order mismatch'",
        "for r in rows:",
        "    assert set(r.keys()) == {'convo_codename','r1','r2','r3'}, f\"fields {sorted(r.keys())}\"",
        "    for k in ('r1','r2','r3'):",
        "        assert isinstance(r[k], str) and len(r[k].strip()) >= 1, f\"empty {k}\"",
        'print(f"REFERENCE ANSWERS CONFORM: {len(rows)}/{len(inp)} items")',
    ]) + "\n"
    Path(path).write_text(check)


def _write_scoring_prompt(path, stage_dir, n_items):
    prompt = f"""You are performing the SCORING call (Call 2) of the M2 reconstruction SCORING pass (Federated Agent Memory, round R2).
Files you may and should use (the ONLY files you have):
- {stage_dir}/PROTOCOL-m2-scoring.md — the frozen scoring protocol v1.0 (READ IT FIRST: the two-call structure, the frozen rubric, rules R1-R5, the Call 2 output contract, the budget, the honesty clause).
- {stage_dir}/scoring_input.jsonl — {n_items} items, one JSON object per line: convo_codename, transcript, reference (the committed R1-R3 from Call 1), candidates (3 renders with codenames, shuffled).
Constraints (non-negotiable):
- For each item: score ALL THREE candidates against the item's COMMITTED reference (the `reference` field). The reference was formed from the transcript in a candidate-free context — use it as the anchor; do NOT re-derive or second-guess it.
- Candidate codenames are random — do not infer candidate type (rule R2).
- Work in English; scores use ONLY the frozen values.
Output: write {stage_dir}/scoring_answers.jsonl with one JSON object per line, in the order the input file presents the items (see protocol section 4, Call 2):
{{"convo_codename": "<codename>", "scores": {{"<cand codename>": {{"s1": <v>, "s2": <v>, "s3": <v>}}, ...}}}}
Every item exactly once; `scores` must cover all 3 candidates per item.
Then report: (1) the path you wrote, (2) the count of lines, (3) confirmation that you used only the two staged files.
"""
    Path(path).write_text(prompt + "\n")


def _write_scoring_check(path, stage_dir):
    check = "\n".join([
        '"""Conformance check for the M2 scoring answers file (Call 2)."""',
        "import json",
        f'rows = [json.loads(l) for l in open(r"{stage_dir}/scoring_answers.jsonl") if l.strip()]',
        f'inp = [json.loads(l) for l in open(r"{stage_dir}/scoring_input.jsonl") if l.strip()]',
        'assert len(rows) == len(inp), f"row count {len(rows)} != {len(inp)}"',
        "for row, it in zip(rows, inp):",
        "    assert row['convo_codename'] == it['convo_codename'], 'codename/order mismatch'",
        "    assert set(row.keys()) == {'convo_codename','scores'}, f\"fields {sorted(row.keys())}\"",
        "    want = {c['codename'] for c in it['candidates']}",
        "    assert set(row['scores'].keys()) == want, f\"candidate coverage {set(row['scores'].keys())}\"",
        "    for c, sc in row['scores'].items():",
        "        assert set(sc.keys()) == {'s1','s2','s3'}, f\"{c}: {sorted(sc.keys())}\"",
        "        assert sc['s1'] in (0, 0.5, 1), f\"{c} s1 {sc['s1']}\"",
        "        assert sc['s2'] in (0, 0.5, 1), f\"{c} s2 {sc['s2']}\"",
        "        assert sc['s3'] in (0, 0.25, 0.5, 1), f\"{c} s3 {sc['s3']}\"",
        'print(f"SCORING ANSWERS CONFORM: {len(rows)}/{len(inp)} items, all candidates scored")',
    ]) + "\n"
    Path(path).write_text(check)


def stage_reference(bind_dir, stage_dir):
    """Fresh-context stage for the REFERENCE call (Call 1): ONLY protocol +
    reference input + prompt + checker + manifest. NO candidates, NO scoring
    base, NO mapping — the reference context is candidate-free by design."""
    bind_dir = Path(bind_dir)
    stage_dir = Path(stage_dir)
    need = ["PROTOCOL-m2-scoring.md", "reference_input.jsonl"]
    for f in need:
        assert (bind_dir / f).is_file(), f"bind dir incomplete: missing {f}"

    removed = []
    if stage_dir.exists():
        for f in stage_dir.iterdir():
            removed.append(f.name)
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
    stage_dir.mkdir(parents=True, exist_ok=True)
    for f in need:
        shutil.copy2(bind_dir / f, stage_dir / f)
    n_items = sum(1 for l in (bind_dir / "reference_input.jsonl").read_text().splitlines() if l.strip())
    # anti-leak: the reference input carries ONLY the frozen fields (no
    # candidates, no reference, no mapping)
    for line in (stage_dir / "reference_input.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert set(row.keys()) == set(REFERENCE_FIELDS), f"reference input leak {sorted(row.keys())}"
    _write_reference_prompt(stage_dir / "reference_prompt.md", stage_dir, n_items)
    _write_reference_check(stage_dir / "reference_check.py", stage_dir)
    manifest = {
        "purpose": "fresh-context REFERENCE stage (Call 1, M2 reconstruction scoring, 5450060638 §2)",
        "call": "reference (transcript ONLY → R1-R3; candidate-free context)",
        "staged": {f: sha256_file(stage_dir / f) for f in
                   ["PROTOCOL-m2-scoring.md", "reference_input.jsonl",
                    "reference_prompt.md", "reference_check.py"]},
        "n_items": n_items,
        "pre_existing_removed": removed,
        "answers_out": "reference_answers.jsonl",
        "rule": ("the fresh agent sees ONLY this directory + "
                 "reference_prompt.md; NO candidates, NO scoring base, NO "
                 "mapping, NO other call's input/answers, no repo context — "
                 "the reference is formed in a candidate-free context by design"),
    }
    (stage_dir / "stage_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=1))
    print(f"REFERENCE STAGE READY: {stage_dir} (Call 1) — give reference_prompt.md to a FRESH agent session")
    return manifest


def stage_scoring(bind_dir, stage_dir, reference_path):
    """Fresh-context stage for the SCORING call (Call 2): validates the
    committed reference answers, builds scoring_input.jsonl = scoring_base +
    the committed reference (per convo_codename), and stages ONLY protocol +
    scoring input + prompt + checker + manifest."""
    bind_dir = Path(bind_dir)
    stage_dir = Path(stage_dir)
    for f in ["PROTOCOL-m2-scoring.md", "scoring_base.jsonl"]:
        assert (bind_dir / f).is_file(), f"bind dir incomplete: missing {f}"
    ref_path = Path(reference_path)
    assert ref_path.is_file(), f"reference answers not found: {ref_path}"

    base = [json.loads(l) for l in (bind_dir / "scoring_base.jsonl").read_text().splitlines() if l.strip()]
    ref = [json.loads(l) for l in ref_path.read_text().splitlines() if l.strip()]
    ref_by_cc = {r["convo_codename"]: r for r in ref}
    # the committed reference must cover EXACTLY the convos in the scoring base
    base_cc = [it["convo_codename"] for it in base]
    assert sorted(ref_by_cc) == sorted(base_cc), \
        f"reference codename set != scoring base codename set: " \
        f"missing {sorted(set(base_cc) - set(ref_by_cc))[:5]}, " \
        f"extra {sorted(set(ref_by_cc) - set(base_cc))[:5]}"
    for cc in base_cc:
        for k in ("r1", "r2", "r3"):
            assert isinstance(ref_by_cc[cc].get(k), str) and ref_by_cc[cc][k].strip(), \
                f"{cc}: empty reference field {k}"

    # build scoring_input = base + committed reference (in base order)
    scoring_input = []
    for it in base:
        cc = it["convo_codename"]
        r = ref_by_cc[cc]
        scoring_input.append({
            "convo_codename": cc,
            "transcript": it["transcript"],
            "reference": {"r1": r["r1"], "r2": r["r2"], "r3": r["r3"]},
            "candidates": it["candidates"],
        })

    removed = []
    if stage_dir.exists():
        for f in stage_dir.iterdir():
            removed.append(f.name)
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
    stage_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bind_dir / "PROTOCOL-m2-scoring.md", stage_dir / "PROTOCOL-m2-scoring.md")
    (stage_dir / "scoring_input.jsonl").write_text(
        "\n".join(json.dumps(it, separators=(",", ":")) for it in scoring_input) + "\n")
    # anti-leak: the scoring input carries ONLY the frozen fields
    for line in (stage_dir / "scoring_input.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert set(row.keys()) == set(SCORING_INPUT_FIELDS), f"scoring input leak {sorted(row.keys())}"
    _write_scoring_prompt(stage_dir / "scoring_prompt.md", stage_dir, len(scoring_input))
    _write_scoring_check(stage_dir / "scoring_check.py", stage_dir)
    manifest = {
        "purpose": "fresh-context SCORING stage (Call 2, M2 reconstruction scoring, 5450060638 §2)",
        "call": "scoring (transcript + 3 candidates + the committed reference → scores)",
        "staged": {f: sha256_file(stage_dir / f) for f in
                   ["PROTOCOL-m2-scoring.md", "scoring_input.jsonl",
                    "scoring_prompt.md", "scoring_check.py"]},
        "n_items": len(scoring_input),
        "reference_source": str(ref_path),
        "pre_existing_removed": removed,
        "answers_out": "scoring_answers.jsonl",
        "rule": ("the fresh agent sees ONLY this directory + scoring_prompt.md; "
                 "the committed reference is embedded as each item's "
                 "`reference` field (the anchor, formed candidate-free in "
                 "Call 1); no blind-pass inputs/answers, no candidate mapping, "
                 "no repo context"),
    }
    (stage_dir / "stage_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=1))
    print(f"SCORING STAGE READY: {stage_dir} (Call 2) — give scoring_prompt.md to a FRESH agent session")
    return manifest


def selftest():
    """Synthetic mini run (3 convos): full bind + both stage layers. Verifies
    the frozen 2-call structure — reference input candidate-free, scoring
    input carries the committed reference, per-convo shuffle, codename
    anonymization, mapping completeness, render byte-identity, stage purity,
    reference-validation, determinism."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="m2_scoring_selftest_"))
    rows = []
    for i in range(3):
        cid = 500 + i
        rows.append({
            "convo_id": cid, "flow": "f", "subflow": "s",
            "n_action_turns": 2, "n_tokens_b0": 6, "n_tokens_b1": 2, "n_tokens_b2": 8,
            "b0": f"customer: hello {i} agent: hi {i} customer: thanks {i} agent: done {i}",
            "b1": "search-faq send-link",
            "b2": json.dumps({"problem_shape": f"want {i}", "constraint": f"no id {i}",
                              "unlock": None, "what_worked": ["search-faq", "send-link"],
                              "receipt": {"corpus": "abcd_v1.1", "convo_id": cid, "flow": "f",
                                          "subflow": "s", "event_span": "full_conversation",
                                          "scope": "single_conversation", "confidence": "high"}}),
            "b2_unit": {}, "unmapped": [],
        })
    src = tmp / "candidates.jsonl"
    src.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n")

    # pin must pass for the selftest: temporarily bind via a direct call
    b = tmp / "bind"
    bind(src, b, 20261101, n_convo=3)
    items = [json.loads(l) for l in (b / "scoring_base.jsonl").read_text().splitlines()]
    ref_in = [json.loads(l) for l in (b / "reference_input.jsonl").read_text().splitlines()]
    assert len(items) == len(ref_in) == 3
    # reference input is candidate-free (anti-leak)
    for it in ref_in:
        assert set(it.keys()) == set(REFERENCE_FIELDS), f"ref leak {sorted(it.keys())}"
    # scoring base: transcript + 3 candidates, no reference
    for it in items:
        assert set(it.keys()) == set(SCORING_BASE_FIELDS), f"base leak {sorted(it.keys())}"
        assert len(it["candidates"]) == 3
        all_c = {c["codename"] for c in it["candidates"]}
        assert len(all_c) == 3
    # mapping complete
    mp = json.loads((b / "convo_mapping.json").read_text())
    cm = mp["candidate_codename -> {convo_id, candidate}"]
    assert len(cm) == 9 and {v["candidate"] for v in cm.values()} == set(CANDIDATES)
    # renders byte-identical to source
    for it in items:
        cc = it["convo_codename"]
        mine = {k.split("|")[1]: v for k, v in cm.items() if k.startswith(cc + "|")}
        for c in it["candidates"]:
            cand = mine[c["codename"]]["candidate"]
            src_row = next(r for r in rows if r["convo_id"] == mine[c["codename"]]["convo_id"])
            assert c["render"] == src_row[cand], "render mutated"
        assert it["transcript"] == src_row["b0"]

    # stage-reference: PURE (no candidates, no scoring base, no mapping)
    sref = tmp / "stage_ref"
    sref.mkdir(parents=True, exist_ok=True)
    (sref / "scoring_base.jsonl").write_text("[]\n")   # contamination
    (sref / "convo_mapping.json").write_text("{}\n")
    stage_reference(b, sref)
    staged = sorted(f.name for f in sref.iterdir())
    assert staged == sorted(["PROTOCOL-m2-scoring.md", "reference_input.jsonl",
                             "reference_prompt.md", "reference_check.py",
                             "stage_manifest.json"]), staged
    sm = json.loads((sref / "stage_manifest.json").read_text())
    assert sorted(sm["pre_existing_removed"]) == ["convo_mapping.json", "scoring_base.jsonl"]
    # anti-leak: the reference DATA file carries no candidate content — the
    # candidate codenames from the scoring base must not appear anywhere in
    # the reference stage (prose like "NO candidates" in the prompt/manifest
    # is fine; a candidate render or codename is not)
    base_cand_codenames = {c["codename"] for it in items for c in it["candidates"]}
    for f in sref.iterdir():
        data = f.read_bytes()
        for cc in base_cand_codenames:
            assert cc.encode() not in data, f"candidate codename leaked into {f.name}"
    # and the reference input is field-pure (no candidates key)
    for line in (sref / "reference_input.jsonl").read_text().splitlines():
        assert set(json.loads(line).keys()) == set(REFERENCE_FIELDS)

    # fabricate the committed reference answers (all convos, R1-R3 non-empty)
    ref_ans = [{"convo_codename": it["convo_codename"], "r1": f"ref1 {i}",
                "r2": f"ref2 {i}", "r3": f"ref3 {i}"}
               for i, it in enumerate(ref_in)]
    refp = tmp / "reference_answers.jsonl"
    refp.write_text("\n".join(json.dumps(r) for r in ref_ans) + "\n")

    # stage-scoring: builds scoring_input = base + committed reference
    sscore = tmp / "stage_score"
    sscore.mkdir(parents=True, exist_ok=True)
    (sscore / "candidate_mapping.json").write_text("{}\n")
    stage_scoring(b, sscore, refp)
    staged = sorted(f.name for f in sscore.iterdir())
    assert staged == sorted(["PROTOCOL-m2-scoring.md", "scoring_input.jsonl",
                             "scoring_prompt.md", "scoring_check.py",
                             "stage_manifest.json"]), staged
    sm2 = json.loads((sscore / "stage_manifest.json").read_text())
    assert sm2["pre_existing_removed"] == ["candidate_mapping.json"]
    si = [json.loads(l) for l in (sscore / "scoring_input.jsonl").read_text().splitlines()]
    assert len(si) == 3
    ref_by_cc = {r["convo_codename"]: r for r in ref_ans}
    for it in si:
        assert set(it.keys()) == set(SCORING_INPUT_FIELDS), f"scoring input leak {sorted(it.keys())}"
        assert it["reference"] == {k: ref_by_cc[it["convo_codename"]][k] for k in ("r1", "r2", "r3")}, \
            "committed reference not embedded correctly"
        assert len(it["candidates"]) == 3

    # reference-validation: a reference missing a convo must be REJECTED
    bad_ref = tmp / "bad_ref.jsonl"
    bad_ref.write_text(json.dumps({"convo_codename": ref_in[0]["convo_codename"],
                                   "r1": "x", "r2": "x", "r3": "x"}) + "\n")
    try:
        stage_scoring(b, tmp / "stage_bad", bad_ref)
        raise AssertionError("stage-scoring accepted a partial reference (must reject)")
    except AssertionError as e:
        assert "codename set" in str(e), str(e)

    # determinism: re-bind → identical reference + base inputs
    b2 = tmp / "bind2"
    bind(src, b2, 20261101, n_convo=3)
    assert (b / "reference_input.jsonl").read_bytes() == (b2 / "reference_input.jsonl").read_bytes()
    assert (b / "scoring_base.jsonl").read_bytes() == (b2 / "scoring_base.jsonl").read_bytes()
    print("SELFTEST OK: 3 synthetic convos bound (reference candidate-free, scoring "
          "base + committed reference, anonymized, per-convo shuffled, renders "
          "byte-identical, mapping complete); reference stage pure; reference "
          "validation rejects partial input; deterministic.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
        sys.exit(0)
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    bp = sub.add_parser("bind")
    bp.add_argument("--candidates", default="research/phase2/m2/candidates.jsonl")
    bp.add_argument("--out", required=True)
    bp.add_argument("--seed", type=int, default=SEED_DEFAULT)
    bp.add_argument("--n-convo", type=int, default=N_CONVO_DEFAULT)
    sr = sub.add_parser("stage-reference")
    sr.add_argument("--bind", required=True)
    sr.add_argument("--stage-dir", required=True)
    ss = sub.add_parser("stage-scoring")
    ss.add_argument("--bind", required=True)
    ss.add_argument("--stage-dir", required=True)
    ss.add_argument("--reference", required=True,
                    help="the committed reference answers file (Call 1 output)")
    a = ap.parse_args()
    if a.cmd == "bind":
        csha = sha256_file(a.candidates)[:16]
        assert csha == PINNED_CANDIDATES_SHA16, f"candidates sha mismatch: {csha} (pin {PINNED_CANDIDATES_SHA16})"
        bind(a.candidates, a.out, a.seed, a.n_convo)
    elif a.cmd == "stage-reference":
        stage_reference(a.bind, a.stage_dir)
    else:
        stage_scoring(a.bind, a.stage_dir, a.reference)
