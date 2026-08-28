#!/usr/bin/env python3
"""stage_blind_pass.py — M2 judge harness (R2): stage the BLIND answering
passes (pass 1 + pass 2) for the reconstruction test.

Pre-registered spec (GH #6 5449115746 §3): per convo, each candidate
(B0/B1/B2) is presented to the judge BLIND (shuffled, anonymized, no
transcript, no flow/band hints); the judge answers Q1–Q3. Two answering
passes (D19): pass 2 in a fresh staged context with a different seeded
order; per-convo answer agreement is reported as a number. Cost: 80 convos
× 3 candidates × 2 answering passes = 480 blind answering calls.

Reuses the R1 labeling infra pattern (research/phase2/labeling/):
  - split_passes.py → seeded, shuffled pass inputs; DIFFERENT order per
    pass (positional priming impossible); anti-leak field-set assertion;
    passes_manifest.json with seeds/shas/counts.
  - stage_pass2.py  → fresh-context stage directory: ONLY the protocol +
    the pass input; a stage manifest with file hashes makes "the fresh
    context saw only X" a verifiable artifact; a pass prompt file; a
    conformance checker for the returned file; any pre-existing files
    removed and recorded.

Two layers (R1-faithful separation):

BIND layer (one directory, committed; --out, e.g. research/phase2/m2/judge/binding):
  PROTOCOL-m2-blind.md      the frozen blind-answering protocol v1.0
                            (Q1–Q3, rules R1–R4, output contract, honesty clause)
  pass1_input.jsonl         240 items in seed1-shuffled order; fields
                            EXACTLY item_id, codename, question, render
                            (anti-leak: no convo_id, no candidate type, no
                            flow/subflow/product)
  pass2_input.jsonl         same 240 items, DIFFERENT seed2-shuffled order
  candidate_mapping.json    item_id/codename -> (convo_id, candidate):
                            de-anonymization at JOIN time only
  passes_manifest.json      seeds, counts, sha256 of every file,
                            order-difference + anti-leak assertions
  bind.md                   (human summary of the layer + file inventory)

STAGE layer (per pass, per fresh agent session; --stage-pass N --stage-dir D):
  D/PROTOCOL-m2-blind.md    copied verbatim from the bind layer
  D/passN_input.jsonl       copied verbatim
  D/passN_prompt.md         the exact prompt for the fresh agent
  D/passN_check.py          conformance checker for the returned answers
  D/stage_manifest.json     sha256 of each staged file + any pre-existing
                            files removed (and recorded) — "the fresh
                            context saw ONLY this directory" becomes
                            verifiable. NOTHING else may be in D (the
                            mapping file in particular never reaches it).

The candidate renders are byte-identical to candidates.jsonl (B0 the full
transcript render, B1 the action trace, B2 the structured record as
rendered there — see candidates.jsonl.meta.json). Anonymization =
deterministic 6-hex codename (sha256 of the item id — no structural
relation to convo/candidate) + per-pass seeded shuffle; the judge never
sees which candidate is which, which convo it came from, or any
flow/band/product metadata. The transcript is NOT given to the answering
judge (that is the point of the reconstruction test); it appears only in
the SCORING pass (fresh context, separately staged — scoring plumbing is
built after the lead's B2 draft lands, since the scored B2 is the final
unit, not the skeleton).

Honesty clause (rides with every M2 number): agent-judged; inter-pass
disagreement is a self-consistency floor, NOT human inter-rater agreement.

Deterministic, stdlib only; pinned input sha verified at bind time.

Usage:
  python3 research/phase2/m2/stage_blind_pass.py bind \
      --candidates research/phase2/m2/candidates.jsonl \
      --out research/phase2/m2/judge/binding \
      [--seed1 20260901] [--seed2 20261001]
  python3 research/phase2/m2/stage_blind_pass.py stage --bind <bindir> --pass 1 --stage-dir <dir>
  python3 research/phase2/m2/stage_blind_pass.py stage --bind <binddir> --pass 2 --stage-dir <dir>
  python3 research/phase2/m2/stage_blind_pass.py --selftest
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
SEED1_DEFAULT, SEED2_DEFAULT = 20260901, 20261001
PASS_INPUT_FIELDS = ["item_id", "codename", "question", "render"]
ANSWER_FIELDS = ["item_id", "pass", "q1", "q2", "q3"]

PROTOCOL_MD = """# M2 Blind Reconstruction — Answering Protocol (pre-registered, v1.0)

**Round:** R2 (M2 extraction) · frozen on GH #6 5449115746 §3.
**Role:** independent judge (agent-judged). You answer per item, exactly
once per pass, from the item's `render` ONLY.

## 1. What you see

Each item carries: `item_id`, a `codename` (an anonymized identity — it
does NOT identify the conversation or the candidate type), `question`,
and `render` (the item's full text).

You are told NOTHING else: no conversation id, no candidate type, no
flow/subflow, no product, no transcript. Different passes present the
same items in different orders. You have no access to any other pass's
answers — that is by design (pass independence).

> **Scope note (interpretation, flagged for lead confirmation):** "no
> flow/band hints" means no hints attached to the PRESENTATION — the judge
> never receives item metadata (convo id, candidate type, construction
> band) alongside a render. A render that contains flow/subflow fields as
> part of its own content (the B2 unit's receipt, a frozen unit field) is
> the candidate being tested and is answered AS-IS; any value carried by
> those in-unit fields is part of the unit's measured value, not a
> presentation leak.

## 2. The three questions (answer each item on all three)

- **Q1 — the problem.** State the customer's problem: the intent (what the
  customer wants done) and the structure (the symptom/constraint that
  drove the resolution). One or two sentences.
- **Q2 — the binding constraint.** State the constraint/symptom that
  actually determined the resolution. If it cannot be identified from the
  render, answer exactly: `not identifiable`.
- **Q3 — what worked.** State the resolution actions, IN ORDER, as listed
  or described in the render. If none are present, answer exactly: `none`.

## 3. Rules

- **R1 — Answer from the render only.** No outside knowledge of the
  corpus, the product, or the item's provenance.
- **R2 — Do not infer from codename or order.** They are random.
- **R3 — Fidelity over plausibility.** If the render is thin (e.g. a bare
  action list), answer only what it supports; `not identifiable` is a
  legitimate Q2 answer and is NOT a failure.
- **R4 — English, concise.** Q1 ≤ 40 words, Q2 ≤ 25 words, Q3 ≤ 40 words.

## 4. Output contract

Write one JSON object per line, in the order the input file presents the
items:
`{"item_id": "<id>", "pass": <1|2>, "q1": "...", "q2": "...", "q3": "..."}`
One line per item, every item exactly once, in input order.

## 5. Honesty clause (read before quoting any number from this protocol)

All answering is AGENT-JUDGED. The inter-pass disagreement rate measures
the judge's OWN consistency under frozen rules — a self-consistency floor,
NOT human inter-rater agreement. It is never cited as "human agreement".
"""


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def codename(item_id):
    """Deterministic 6-hex anonymized codename (no structural relation to
    the item's convo or candidate type). Unique per item."""
    return hashlib.sha256(f"m2blind:{item_id}".encode()).hexdigest()[:6]


def build_items(rows):
    """One item per (convo, candidate): 3 × n rows. item_id = cNNN, globally
    unique, in (convo_id-order, b0/b1/b2-order). `_convo_id`/`_candidate`
    are internal — stripped from every pass input (anti-leak)."""
    items = []
    n = 0
    for row in sorted(rows, key=lambda r: r["convo_id"]):
        for cand in CANDIDATES:
            n += 1
            item_id = f"c{n:03d}"
            items.append({
                "item_id": item_id,
                "codename": codename(item_id),
                "question": "Answer Q1, Q2, Q3 from the render only (protocol section 2).",
                "render": row[cand],
                "_convo_id": row["convo_id"],
                "_candidate": cand,
            })
    return items


def _write_pass_input(path, rows):
    path.write_text("\n".join(
        json.dumps({k: r[k] for k in PASS_INPUT_FIELDS}, separators=(",", ":"))
        for r in rows) + "\n")
    return sha256_file(path)


def _write_prompt(path, stage_dir, passn, n_items):
    prompt = f"""You are performing PASS {passn} of the M2 blind reconstruction test (Federated Agent Memory, round R2).
Files you may and should use (the ONLY files you have):
- {stage_dir}/PROTOCOL-m2-blind.md — the frozen protocol v1.0 (READ IT FIRST: Q1–Q3, rules R1–R4, output contract, honesty clause).
- {stage_dir}/pass{passn}_input.jsonl — {n_items} items, one JSON object per line, fields: item_id, codename, question, render.
Constraints (non-negotiable):
- Answer every item on Q1, Q2, Q3 from the render ONLY (protocol sections 2–3).
- You are not told which conversation or which candidate type any item is — do not try to work it out; it is irrelevant to the task.
- No access to any other pass's answers — by design (pass independence).
- Work in English.
Output: write {stage_dir}/pass{passn}_answers.jsonl with one JSON object per line, in the order the input file presents the items:
{{"item_id": "<id>", "pass": {passn}, "q1": "...", "q2": "...", "q3": "..."}}
Every item exactly once, in input order.
Then report: (1) the path you wrote, (2) the count of lines, (3) confirmation that you used only the two staged files.
"""
    Path(path).write_text(prompt + "\n")


def _write_check(path, stage_dir, passn):
    check = "\n".join([
        f'"""Conformance check for the M2 blind pass-{passn} answers file."""',
        "import json, sys",
        f'rows = [json.loads(l) for l in open(r"{stage_dir}/pass{passn}_answers.jsonl") if l.strip()]',
        f'inp = [json.loads(l) for l in open(r"{stage_dir}/pass{passn}_input.jsonl") if l.strip()]',
        'assert len(rows) == len(inp), f"row count {len(rows)} != {len(inp)}"',
        "assert [r['item_id'] for r in rows] == [r['item_id'] for r in inp], 'order mismatch'",
        "for r in rows:",
        "    assert set(r.keys()) == {'item_id','pass','q1','q2','q3'}, f\"fields {sorted(r.keys())}\"",
        f"    assert r['pass'] == {passn}",
        "    for k in ('q1','q2','q3'):",
        "        assert isinstance(r[k], str) and len(r[k].strip()) >= 1, f\"empty {k}\"",
        f'print(f"PASS{passn} ANSWERS CONFORM: {{len(rows)}}/{{len(inp)}} items")',
    ]) + "\n"
    Path(path).write_text(check)


def bind(candidates_path, outdir, seed1, seed2, n_convo):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in Path(candidates_path).read_text().splitlines() if l.strip()]
    assert len(rows) == n_convo, f"expected {n_convo} candidate rows, got {len(rows)}"
    for row in rows:
        for cand in CANDIDATES:
            assert cand in row and isinstance(row[cand], str), \
                f"row {row.get('convo_id')}: missing render {cand}"

    items = build_items(rows)
    codenames = [it["codename"] for it in items]
    assert len(codenames) == len(set(codenames)), "codename collision"
    mapping = {f"{it['item_id']}|{it['codename']}":
               {"convo_id": it["_convo_id"], "candidate": it["_candidate"]} for it in items}

    r1, r2 = random.Random(seed1), random.Random(seed2)
    p1 = list(items); r1.shuffle(p1)
    p2 = list(items); r2.shuffle(p2)
    order1 = [x["item_id"] for x in p1]
    order2 = [x["item_id"] for x in p2]
    assert order1 != order2, "FATAL: both pass inputs in identical order (seeds collided?)"

    (outdir / "PROTOCOL-m2-blind.md").write_text(PROTOCOL_MD)
    proto_sha = sha256_file(outdir / "PROTOCOL-m2-blind.md")
    s1 = _write_pass_input(outdir / "pass1_input.jsonl", p1)
    s2 = _write_pass_input(outdir / "pass2_input.jsonl", p2)

    # anti-leak: every pass-input row carries EXACTLY the frozen field set
    for name in ("pass1_input.jsonl", "pass2_input.jsonl"):
        for line in (outdir / name).read_text().splitlines():
            row = json.loads(line)
            assert set(row.keys()) == set(PASS_INPUT_FIELDS), f"{name}: leak {sorted(row.keys())}"

    (outdir / "candidate_mapping.json").write_text(
        json.dumps({"key": "item_id|codename",
                    "use": "de-anonymization at JOIN time only — NEVER part of a pass context",
                    "mapping": mapping}, indent=1, sort_keys=True) + "\n")
    map_sha = sha256_file(outdir / "candidate_mapping.json")

    manifest = {
        "purpose": ("M2 blind answering passes (Q1–Q3): "
                    f"{n_convo} convos x 3 candidates (b0/b1/b2) x 2 passes = {3 * n_convo} items/pass"),
        "n_items_per_pass": len(items),
        "n_convos": n_convo,
        "candidates": CANDIDATES,
        "renders_source": ("byte-identical to the `b0`/`b1`/`b2` fields of the pinned "
                           "candidates.jsonl (see its meta for the render definitions)"),
        "seeds": {"pass1": seed1, "pass2": seed2},
        "sha256": {"pass1_input": s1, "pass2_input": s2,
                   "PROTOCOL-m2-blind": proto_sha, "candidate_mapping": map_sha},
        "orders_differ": order1 != order2,
        "pass_input_fields": PASS_INPUT_FIELDS,
        "rule": ("pass inputs carry ONLY item_id + codename + question + render "
                 "(no convo_id, no candidate type, no flow/subflow/product — "
                 "anti-leak, asserted mechanically); codenames are "
                 "deterministic 6-hex digests with no structural relation to "
                 "convo/candidate; pass2 uses a different seeded order than "
                 "pass1; each pass runs in a FRESH agent context staged by "
                 "stage (below) with no access to the other pass's answers; "
                 "the transcript is NOT given to the answering judge (the "
                 "scoring pass sees it, separately staged)"),
        "honesty_clause": ("agent-judged; inter-pass disagreement = "
                           "self-consistency floor, not human agreement"),
    }
    (outdir / "passes_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")

    # per-pass prompt + conformance checker (referencing the bind dir for
    # convenience; the staged copies reference the stage dir)
    for passn in (1, 2):
        _write_prompt(outdir / f"pass{passn}_prompt.md", outdir, passn, len(items))
        _write_check(outdir / f"pass{passn}_check.py", outdir, passn)

    (outdir / "bind.md").write_text(
        "# M2 blind-answering BIND layer\n\n"
        f"{len(items)} items ({n_convo} convos x 3 candidates) in two seeded, shuffled, "
        "anonymized pass inputs; mapping + manifest for the join. Stage a per-pass "
        "directory with `stage_blind_pass.py stage --bind <this dir> --pass <1|2> "
        "--stage-dir <dir>` and hand THAT directory (only) to a fresh agent session.\n\n"
        + "\n".join(f"- `{f.name}`" for f in sorted(outdir.iterdir())) + "\n")
    print(json.dumps(manifest, indent=1))
    print(f"BIND READY: {outdir} — now stage each pass for its fresh agent session")
    return manifest


def stage(bind_dir, passn, stage_dir):
    """Clean fresh-context stage for pass `passn` (R1 stage_pass2.py pattern):
    ONLY protocol + pass input + prompt + checker + manifest. Any
    pre-existing files (esp. any other pass's answers or the mapping) are
    removed and recorded."""
    bind_dir = Path(bind_dir)
    stage_dir = Path(stage_dir)
    proto = bind_dir / "PROTOCOL-m2-blind.md"
    pinput = bind_dir / f"pass{passn}_input.jsonl"
    assert proto.is_file() and pinput.is_file(), \
        f"bind dir incomplete: {bind_dir} (need PROTOCOL-m2-blind.md + pass{passn}_input.jsonl)"
    assert passn in (1, 2), "pass must be 1 or 2"

    removed = []
    if stage_dir.exists():
        for f in stage_dir.iterdir():
            removed.append(f.name)
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
    stage_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(proto, stage_dir / "PROTOCOL-m2-blind.md")
    shutil.copy2(pinput, stage_dir / f"pass{passn}_input.jsonl")
    n_items = sum(1 for l in pinput.read_text().splitlines() if l.strip())
    _write_prompt(stage_dir / f"pass{passn}_prompt.md", stage_dir, passn, n_items)
    _write_check(stage_dir / f"pass{passn}_check.py", stage_dir, passn)

    manifest = {
        "purpose": f"fresh-context pass-{passn} stage (M2 blind reconstruction, D19)",
        "staged": {
            "PROTOCOL-m2-blind.md": sha256_file(stage_dir / "PROTOCOL-m2-blind.md"),
            f"pass{passn}_input.jsonl": sha256_file(stage_dir / f"pass{passn}_input.jsonl"),
        },
        "n_items": n_items,
        "pre_existing_removed": removed,
        "answers_out": f"pass{passn}_answers.jsonl",
        "rule": ("the fresh agent sees ONLY this directory + pass"
                 f"{passn}_prompt.md; no other pass's input/answers, no "
                 "candidate_mapping.json, no transcript, no repo context"),
    }
    (stage_dir / "stage_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=1))
    print(f"STAGE READY: {stage_dir} (pass {passn}) — give pass{passn}_prompt.md to a FRESH agent session")
    return manifest


def selftest():
    """Synthetic mini run (3 convos x 3 candidates = 9 items): verifies the
    full bind + stage pipeline — anti-leak field set, codename
    anonymization, order difference, mapping completeness, render
    byte-identity, stage-dir purity, determinism."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="m2_blind_selftest_"))
    rows = []
    for i in range(3):
        cid = 100 + i
        rows.append({
            "convo_id": cid, "flow": "f", "subflow": "s",
            "n_action_turns": 1, "n_tokens_b0": 4, "n_tokens_b1": 1,
            "n_tokens_b2_skeleton": 10,
            "b0": f"customer: hello {i} agent: hi {i} customer: thanks {i}",
            "b1": f"search-faq",
            "b2": json.dumps({"problem_shape": None, "constraint": None, "unlock": None,
                              "what_worked": ["search-faq"],
                              "receipt": {"corpus": "abcd_v1.1", "convo_id": cid, "flow": "f",
                                          "subflow": "s", "event_span": None, "scope": None,
                                          "confidence": None}}),
            "unmapped": [],
        })
    src = tmp / "candidates.jsonl"
    src.write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n")

    bind(src, tmp / "bind", 20260901, 20261001, n_convo=3)
    b = tmp / "bind"
    p1 = [json.loads(l) for l in (b / "pass1_input.jsonl").read_text().splitlines()]
    p2 = [json.loads(l) for l in (b / "pass2_input.jsonl").read_text().splitlines()]
    assert len(p1) == len(p2) == 9
    for row in p1 + p2:
        assert set(row.keys()) == set(PASS_INPUT_FIELDS), f"leak: {sorted(row.keys())}"
    assert [r["item_id"] for r in p1] != [r["item_id"] for r in p2], "orders must differ"
    mp = json.loads((b / "candidate_mapping.json").read_text())["mapping"]
    assert len(mp) == 9
    assert {v["candidate"] for v in mp.values()} == set(CANDIDATES)
    # codenames anonymized: 6-hex digests, not a direct reuse of the item id
    for row in p1 + p2:
        assert len(row["codename"]) == 6 and all(ch in "0123456789abcdef" for ch in row["codename"])
        assert row["codename"] != row["item_id"].lstrip("c").lstrip("0")
    # renders byte-identical to source rows
    src_by_id = {}
    for it in build_items(rows):
        src_by_id[it["item_id"]] = it["render"]
    for row in p1 + p2:
        assert row["render"] == src_by_id[row["item_id"]], "render mutated in transit"

    # stage pass 1 into a dir that CONTAMINATES with a stray mapping + a
    # fake pass-2 answers file: staging must remove + record them
    s1dir = tmp / "stage1"
    s1dir.mkdir(parents=True, exist_ok=True)
    (s1dir / "candidate_mapping.json").write_text("{}\n")
    (s1dir / "pass2_answers.jsonl").write_text('{"item_id":"c001","pass":2,"q1":"x","q2":"x","q3":"x"}\n')
    stage(b, 1, s1dir)
    staged = sorted(f.name for f in s1dir.iterdir())
    assert staged == sorted([f"PROTOCOL-m2-blind.md", "pass1_input.jsonl", "pass1_prompt.md",
                             "pass1_check.py", "stage_manifest.json"]), staged
    sm = json.loads((s1dir / "stage_manifest.json").read_text())
    assert sorted(sm["pre_existing_removed"]) == ["candidate_mapping.json", "pass2_answers.jsonl"]
    # no de-anonymization material anywhere in the stage dir. NOTE: the words
    # "convo_id"/"candidate type" legitimately appear inside B2 renders (the
    # receipt is a frozen unit field — the judge sees the unit AS the unit)
    # and in the protocol's rules; the purity check targets the mapping's
    # structure, not corpus or protocol text.
    for f in s1dir.iterdir():
        data = f.read_bytes()
        assert b"de-anonymization" not in data, f.name
        assert b"item_id|codename" not in data, f.name
        if f.suffix == ".json":
            assert not any(k in data for k in (b'"candidate":', b'"convo_id":')), f.name

    # determinism: re-bind → identical pass inputs
    bind(src, tmp / "bind2", 20260901, 20261001, n_convo=3)
    assert (b / "pass1_input.jsonl").read_bytes() == (tmp / "bind2" / "pass1_input.jsonl").read_bytes()
    assert (b / "pass2_input.jsonl").read_bytes() == (tmp / "bind2" / "pass2_input.jsonl").read_bytes()
    print("SELFTEST OK: 9 synthetic items bound (anti-leak, anonymized, orders differ, "
          "renders byte-identical); stage dir pure (contamination removed + recorded); "
          "deterministic on re-run.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
        sys.exit(0)
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    bp = sub.add_parser("bind")
    bp.add_argument("--candidates", default="research/phase2/m2/candidates.jsonl")
    bp.add_argument("--out", required=True)
    bp.add_argument("--seed1", type=int, default=SEED1_DEFAULT)
    bp.add_argument("--seed2", type=int, default=SEED2_DEFAULT)
    bp.add_argument("--n-convo", type=int, default=N_CONVO_DEFAULT)
    sp = sub.add_parser("stage")
    sp.add_argument("--bind", required=True)
    sp.add_argument("--pass", dest="passn", type=int, required=True, choices=[1, 2])
    sp.add_argument("--stage-dir", required=True)
    a = ap.parse_args()
    if a.cmd == "bind":
        csha = sha256_file(a.candidates)[:16]
        assert csha == PINNED_CANDIDATES_SHA16, f"candidates sha mismatch: {csha} (pin {PINNED_CANDIDATES_SHA16})"
        bind(a.candidates, a.out, a.seed1, a.seed2, a.n_convo)
    else:
        stage(a.bind, a.passn, a.stage_dir)
