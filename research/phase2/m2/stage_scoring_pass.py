#!/usr/bin/env python3
"""stage_scoring_pass.py — M2 judge harness (R2): stage the SCORING pass for
the reconstruction test (the second half of the frozen 640-call budget).

Pre-registered spec (GH #6 5449115746 §3): after the blind answering
passes, the judge (fresh context, TRANSCRIPT VISIBLE) first writes its OWN
reference answers R1–R3 from the transcript, then scores each candidate
against its reference:
  Q1: 1 = intent+structure both correct, 0.5 = one axis correct, 0 = wrong
  Q2: 1 = the binding constraint, 0.5 = a real but non-binding constraint,
      0 = none/wrong
  Q3: 1 = all resolution actions in order, 0.5 = all present wrong order,
      0.25 = >= half present, 0 = else
value(candidate) = (s1+s2+s3)/3
Cost: 80 convos × (1 reference + 1 scoring call over all 3 candidates)
= 160 scoring calls (one combined call per convo, per the pre-registration).

Reuses the R1 labeling infra pattern (same bind/stage split as
stage_blind_pass.py):
  BIND layer (--bind, committed):
    PROTOCOL-m2-scoring.md  the frozen scoring protocol (rubric, output
                            contract, honesty clause)
    scoring_input.jsonl     80 rows: convo_codename, transcript (the B0
                            render — that IS the transcript), candidates
                            (the 3 candidate renders, anonymized codenames,
                            per-convo seeded-shuffled order)
    convo_mapping.json      convo_codename -> convo_id; candidate codename
                            -> (convo_id, candidate) [reuses the blind
                            bind's item codenames — one codename space]
    scoring_manifest.json   seeds, sha256 of every file, assertions
    bind.md
  STAGE layer (--stage --stage-dir D): ONLY protocol + scoring input +
    prompt + checker + stage manifest (fresh-context purity, same as the
    blind passes).

Anonymization: candidates keep the blind bind's item codenames (the judge
sees codenames, never "B0/B1/B2" labels — all three are scored under
identical treatment, per "baselines scored identically"); the per-convo
candidate ORDER is seeded-shuffled (seed 20261101). The transcript is the
B0 render — giving the transcript is giving B0's content; the pre-
registration scores all three candidates against the judge's own
references, including B0 (the ceiling's value is MEASURED, not assumed
1.0).

Honesty clause (rides with every M2 number): agent-judged; the scoring
pass is a single pass by the judge (references + scores in one fresh
context); inter-pass agreement numbers come from the BLIND answering
passes, not this one.

Deterministic, stdlib only; pinned candidates sha verified.

Usage:
  python3 research/phase2/m2/stage_scoring_pass.py bind \
      --candidates research/phase2/m2/candidates.jsonl \
      --out research/phase2/m2/judge/scoring \
      [--seed 20261101]
  python3 research/phase2/m2/stage_scoring_pass.py stage \
      --bind <bindir> --stage-dir <dir>
  python3 research/phase2/m2/stage_scoring_pass.py --selftest
"""
import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

PINNED_CANDIDATES_SHA16 = "dd1869a2d72c6b2b"
CANDIDATES = ["b0", "b1", "b2"]
N_CONVO_DEFAULT = 80
SEED_DEFAULT = 20261101

PROTOCOL_MD = """# M2 Reconstruction — Scoring Protocol (pre-registered, v1.0)

**Round:** R2 (M2 extraction) · frozen on GH #6 5449115746 §3.
**Role:** independent judge (agent-judged). The transcript IS visible in
this pass. For each item you: (1) write your own reference answers R1–R3
from the transcript, (2) score each of the three candidates against your
reference.

## 1. What you see

Each item carries: `convo_codename` (an anonymized conversation id — it
identifies nothing), `transcript` (the full conversation, "speaker: text"
turns), and `candidates` — three renders, each with a `codename`. The
codenames are random; they do NOT identify the candidate type. The
candidate order is shuffled. Do not infer candidate type from the codename
or the order (R2 below).

## 2. Step 1 — your own references (write these FIRST, before scoring)

From the transcript ONLY:
- **R1 — the problem.** Intent (what the customer wants done) and the
  structure (the symptom/constraint that drove the resolution).
- **R2 — the binding constraint.** The constraint/symptom that actually
  determined the resolution (or `not identifiable`).
- **R3 — what worked.** The resolution actions, in order.

## 3. Step 2 — score each candidate against your reference (rubric, frozen)

- **s1 (Q1 — the problem):** 1 = intent + structure both correct vs R1;
  0.5 = exactly one axis correct; 0 = wrong.
- **s2 (Q2 — the binding constraint):** 1 = the binding constraint (R2);
  0.5 = a real but non-binding constraint; 0 = none / wrong.
- **s3 (Q3 — what worked):** 1 = all resolution actions present and in
  order vs R3; 0.5 = all present, wrong order; 0.25 = at least half
  present; 0 = else.
- `value = (s1 + s2 + s3) / 3`.

Rules:
- **R1 — References from the transcript only.** Your R1–R3 must be
  derivable from the transcript; no outside knowledge.
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

One JSON object per line, one per item, in the order the input file
presents the items:
```
{"convo_codename": "<codename>",
 "r1": "...", "r2": "...", "r3": "...",
 "scores": {"<candidate codename>": {"s1": <v>, "s2": <v>, "s3": <v>}, ...}}
```
`scores` must contain ALL THREE candidate codenames. s-values: s1 ∈
{0, 0.5, 1}, s2 ∈ {0, 0.5, 1}, s3 ∈ {0, 0.25, 0.5, 1}.

## 5. Honesty clause (read before quoting any number from this protocol)

All judging is AGENT-JUDGED (single scoring pass, references + scores in
one fresh context). This pass has no "pass 2" — the agreement numbers
reported in this round are the BLIND answering passes' inter-pass
disagreement. Nothing here is "human gold" or "human agreement".
"""


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def codename(key):
    """Deterministic 6-hex digest — same space as the blind bind's item
    codenames (key = f'm2blind:c{NNN}' per (convo, candidate); the convo
    key = f'm2blind:convo:{convo_id}')."""
    return hashlib.sha256(key.encode()).hexdigest()[:6]


def build(rows, seed):
    """80 scoring rows: convo_codename + transcript + 3 anonymized
    candidate renders in per-convo seeded-shuffled order."""
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
    (outdir / "scoring_input.jsonl").write_text(
        "\n".join(json.dumps(it, separators=(",", ":")) for it in items) + "\n")
    inp_sha = sha256_file(outdir / "scoring_input.jsonl")

    # codename collisions across the whole space (80 convo + 240 candidate)
    all_c = set(convos.values())
    all_c |= set(k.split("|")[1] for k in cands_map)
    assert len(all_c) == n_convo + 3 * n_convo, "codename collision in scoring space"

    (outdir / "convo_mapping.json").write_text(
        json.dumps({"convo_codename -> convo_id": convos_map,
                    "candidate_codename -> {convo_id, candidate}": cands_map,
                    "use": "de-anonymization at JOIN time only — NEVER part of the scoring context"},
                   indent=1, sort_keys=True) + "\n")
    map_sha = sha256_file(outdir / "convo_mapping.json")

    manifest = {
        "purpose": ("M2 reconstruction SCORING pass: 80 convos x (own references "
                    "R1-R3 + rubric scores of all 3 candidates) — one combined "
                    "call per convo, which executes the pre-registered sequence "
                    "(first write your own references, then score each candidate) "
                    "in order. Frozen budget for this half: 160 (80 reference + "
                    "80 scoring calls); the combined call uses 80 — within the "
                    "frozen bound, no extra calls"),
        "n_items": len(items),
        "n_convos": n_convo,
        "candidates_per_item": CANDIDATES,
        "renders_source": ("byte-identical to the pinned candidates.jsonl fields "
                           "(transcript == `b0`; candidates == `b0`/`b1`/`b2` "
                           "anonymized + per-convo seeded-shuffled)"),
        "seed": seed,
        "sha256": {"scoring_input": inp_sha,
                   "PROTOCOL-m2-scoring": proto_sha, "convo_mapping": map_sha},
        "rule": ("candidates scored under IDENTICAL treatment (anonymized "
                 "codenames, shuffled order, no labels — 'baselines scored "
                 "identically'); the transcript is visible (it is the B0 "
                 "render) and B0 itself is one of the scored candidates — "
                 "its value is MEASURED, not assumed; no flow/band/product "
                 "metadata anywhere in the scoring context"),
        "honesty_clause": "agent-judged; single scoring pass; NOT human agreement",
    }
    (outdir / "scoring_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    prompt = f"""You are performing the M2 reconstruction SCORING pass (Federated Agent Memory, round R2).
Files you may and should use (the ONLY files you have):
- {outdir}/PROTOCOL-m2-scoring.md — the frozen scoring protocol v1.0 (READ IT FIRST: references R1-R3, the frozen rubric, rules R1-R5, output contract, honesty clause).
- {outdir}/scoring_input.jsonl — {n_convo} items, one JSON object per line: convo_codename, transcript, candidates (3 renders with codenames, shuffled).
Constraints (non-negotiable):
- For each item: write your OWN references R1-R3 from the transcript FIRST, then score ALL THREE candidates against your reference with the frozen rubric.
- Candidate codenames are random — do not infer candidate type (rule R2).
- Work in English; scores use ONLY the frozen values.
Output: write {outdir}/scoring_answers.jsonl with one JSON object per line, in the order the input file presents the items (see protocol section 4):
{{"convo_codename": "<codename>", "r1": "...", "r2": "...", "r3": "...", "scores": {{"<cand codename>": {{"s1": <v>, "s2": <v>, "s3": <v>}}, ...}}}}
Every item exactly once; `scores` must cover all 3 candidates per item.
Then report: (1) the path you wrote, (2) the count of lines, (3) confirmation that you used only the two staged files.
"""
    (outdir / "scoring_prompt.md").write_text(prompt + "\n")
    check = "\n".join([
        '"""Conformance check for the M2 scoring answers file."""',
        "import json",
        f'rows = [json.loads(l) for l in open(r"{outdir}/scoring_answers.jsonl") if l.strip()]',
        f'inp = [json.loads(l) for l in open(r"{outdir}/scoring_input.jsonl") if l.strip()]',
        'assert len(rows) == len(inp), f"row count {len(rows)} != {len(inp)}"',
        "for row, it in zip(rows, inp):",
        "    assert row['convo_codename'] == it['convo_codename'], 'codename/order mismatch'",
        "    assert set(row.keys()) == {'convo_codename','r1','r2','r3','scores'}, f\"fields {sorted(row.keys())}\"",
        "    for k in ('r1','r2','r3'):",
        "        assert isinstance(row[k], str) and len(row[k].strip()) >= 1, f\"empty {k}\"",
        "    want = {c['codename'] for c in it['candidates']}",
        "    assert set(row['scores'].keys()) == want, f\"candidate coverage {{set(row['scores'].keys())}}\"",
        "    for c, sc in row['scores'].items():",
        "        assert set(sc.keys()) == {'s1','s2','s3'}, f\"{c}: {{sorted(sc.keys())}}\"",
        "        assert sc['s1'] in (0, 0.5, 1), f\"{c} s1 {{sc['s1']}}\"",
        "        assert sc['s2'] in (0, 0.5, 1), f\"{c} s2 {{sc['s2']}}\"",
        "        assert sc['s3'] in (0, 0.25, 0.5, 1), f\"{c} s3 {{sc['s3']}}\"",
        'print(f"SCORING ANSWERS CONFORM: {len(rows)}/{len(inp)} items, all candidates scored")',
    ]) + "\n"
    (outdir / "scoring_check.py").write_text(check)
    (outdir / "bind.md").write_text(
        "# M2 scoring BIND layer\n\n"
        f"{n_convo} scoring items (transcript visible; 3 anonymized candidates "
        "each, per-convo shuffled); mapping + manifest for the join. Stage with "
        "`stage_scoring_pass.py stage --bind <this dir> --stage-dir <dir>` and "
        "hand THAT directory (only) to a fresh agent session.\n\n"
        + "\n".join(f"- `{f.name}`" for f in sorted(outdir.iterdir())) + "\n")
    print(json.dumps(manifest, indent=1))
    print(f"SCORING BIND READY: {outdir} — stage the fresh-context dir, then hand scoring_prompt.md")
    return manifest


def stage(bind_dir, stage_dir):
    bind_dir = Path(bind_dir)
    stage_dir = Path(stage_dir)
    need = ["PROTOCOL-m2-scoring.md", "scoring_input.jsonl", "scoring_prompt.md",
            "scoring_check.py"]
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
    n_items = sum(1 for l in (bind_dir / "scoring_input.jsonl").read_text().splitlines() if l.strip())
    manifest = {
        "purpose": "fresh-context scoring stage (M2 reconstruction, 5449115746 §3)",
        "staged": {f: sha256_file(stage_dir / f) for f in need},
        "n_items": n_items,
        "pre_existing_removed": removed,
        "answers_out": "scoring_answers.jsonl",
        "rule": "the fresh agent sees ONLY this directory + scoring_prompt.md; "
                "no blind-pass inputs/answers, no candidate mapping, no repo context",
    }
    (stage_dir / "stage_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=1))
    print(f"SCORING STAGE READY: {stage_dir} — give scoring_prompt.md to a FRESH agent session")
    return manifest


def selftest():
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
            "b2": json.dumps({"problem_shape": None, "constraint": None, "unlock": None,
                              "what_worked": ["search-faq", "send-link"],
                              "receipt": {"corpus": "abcd_v1.1", "convo_id": cid, "flow": "f",
                                          "subflow": "s", "event_span": None, "scope": None,
                                          "confidence": None}}),
            "b2_unit": {}, "unmapped": [],
        })
    src = tmp / "candidates.jsonl"
    src.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n")
    bind(src, tmp / "bind", 20261101, n_convo=3)
    b = tmp / "bind"
    items = [json.loads(l) for l in (b / "scoring_input.jsonl").read_text().splitlines()]
    assert len(items) == 3
    all_item_c = set()
    for it in items:
        assert set(it.keys()) == {"convo_codename", "transcript", "candidates"}
        assert len(it["candidates"]) == 3
        all_item_c |= {c["codename"] for c in it["candidates"]}
    assert len(all_item_c) == 9
    mp = json.loads((b / "convo_mapping.json").read_text())
    assert len(mp["convo_codename -> convo_id"]) == 3
    cm = mp["candidate_codename -> {convo_id, candidate}"]
    assert len(cm) == 9
    assert {v["candidate"] for v in cm.values()} == set(CANDIDATES)
    # per-convo: the 3 candidate codenames map to that convo's b0/b1/b2
    for it in items:
        cc = it["convo_codename"]
        mine = {k: v for k, v in cm.items() if k.startswith(cc + "|")}
        assert len(mine) == 3
        assert {v["candidate"] for v in mine.values()} == set(CANDIDATES)
        cid = mp["convo_codename -> convo_id"][cc]
        assert all(v["convo_id"] == cid for v in mine.values())
        src_row = next(r for r in rows if r["convo_id"] == cid)
        by_cand = {k.split("|")[1]: v for k, v in mine.items()}  # codename -> {convo_id, candidate}
        for c in it["candidates"]:
            cand = by_cand[c["codename"]]
            assert c["render"] == src_row[cand["candidate"]], "render mutated"
        assert it["transcript"] == src_row["b0"]
    # codename space: 3 convo + 9 candidate codenames, all distinct
    allc = set(mp["convo_codename -> convo_id"]) | {k.split("|")[1] for k in cm}
    assert len(allc) == 12
    # stage purity
    sdir = tmp / "stage"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "candidate_mapping.json").write_text("{}\n")
    stage(b, sdir)
    staged = sorted(f.name for f in sdir.iterdir())
    assert staged == sorted(["PROTOCOL-m2-scoring.md", "scoring_input.jsonl",
                             "scoring_prompt.md", "scoring_check.py", "stage_manifest.json"]), staged
    sm = json.loads((sdir / "stage_manifest.json").read_text())
    assert sm["pre_existing_removed"] == ["candidate_mapping.json"]
    # determinism
    bind(src, tmp / "bind2", 20261101, n_convo=3)
    assert (b / "scoring_input.jsonl").read_bytes() == (tmp / "bind2" / "scoring_input.jsonl").read_bytes()
    print("SELFTEST OK: 3 synthetic convos bound (anonymized, per-convo shuffled, "
          "renders byte-identical, mapping complete); stage dir pure; deterministic.")


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
    sp = sub.add_parser("stage")
    sp.add_argument("--bind", required=True)
    sp.add_argument("--stage-dir", required=True)
    a = ap.parse_args()
    if a.cmd == "bind":
        csha = sha256_file(a.candidates)[:16]
        assert csha == PINNED_CANDIDATES_SHA16, f"candidates sha mismatch: {csha} (pin {PINNED_CANDIDATES_SHA16})"
        bind(a.candidates, a.out, a.seed, a.n_convo)
    else:
        stage(a.bind, a.stage_dir)
