#!/usr/bin/env python3
"""extract.py — M2 candidate extraction (R2): per sample convo, the B0 render,
the B1 action trace, the B2 structured-record SKELETON, and the frozen token
counts.

Pre-registered spec: GH #6 comment 5449115746 §4 item 2 (on the frozen sample,
PR #21 → main @4d68187; D22 accepted as documented, GH #6 5449438507).

Render definitions (frozen; the frozen token counter is whitespace-split of
the rendered candidate):
  B0 = all `original` turns as "speaker: text", space-joined. This is the
       exact render whose token count is sample.jsonl's `n_tokens_b0`
       (checked per row: recompute MUST equal the sample row).
  B1 = the ordered action names from targets[2] of every speaker=="action"
       delexed turn (D11), space-joined. Normalized to the canonical ontology
       vocabulary = union of the category keys of ontology.json["actions"]
       (kb_query ∪ interaction ∪ faq_policy) — exactly the 30 names observed
       in the corpus. An out-of-vocab name is FLAGGED and NEVER DROPPED: it
       stays in the trace, is recorded per row in `unmapped` and aggregated
       in candidates.jsonl.meta.json. Measured on this corpus: 0 unmapped
       (sample and corpus-wide) — the flag path is a guard, not an expected
       count (precision note: the R1-era "10 unmapped" gap was vs
       guidelines.json Title-Case button names, NOT vs this vocab).
  B2 = the pre-registered unit (method doc §M2; `what_failed` stays OUT
       pending §4/R3), as a SKELETON:
       { problem_shape, constraint, unlock, what_worked,
         receipt: {corpus, convo_id, flow, subflow, event_span,
                   scope, confidence} }
       Judgment fields (problem_shape, constraint, unlock,
       receipt.event_span/scope/confidence) are null until the lead's 80-unit
       draft lands (lead is drafting in parallel; nothing blocks on this PR).
       Mechanical fields are pre-filled here: receipt.corpus/convo_id/flow/
       subflow from the corpus, and what_worked = the ordered targets[2]
       sequence (D11) — the pre-registration defines what_worked as "the
       resolution action sequence from targets[2]". The lead's draft is
       authoritative at join time; the pre-fill exists so the join can
       cross-check it.

Token counts in this artifact:
  n_tokens_b0             — final (== sample row, asserted).
  n_tokens_b1             — final (whitespace-split of the B1 render; equals
                            n_action_turns because vocab names carry no
                            whitespace — asserted per row).
  n_tokens_b2             — PROVISIONAL skeleton cost: frozen counter on the
                            skeleton's render. The FINAL B2 token count is
                            computed on the lead's unit at join time (5449115746
                            §4 item 4); the skeleton number is the schema's
                            cost floor and a sanity reference only.
  B2 render = JSON of the unit in schema key order (insertion order = schema
       order, NOT sorted), receipt included, default JSON separators
       (", ", ": "). RENDERING NOTE (flagged for lead confirmation before the
       final join): the pre-registered "canonical JSON (schema key order)"
       does not fix the separators, and the frozen counter is whitespace-
       split. With compact (JCS-style) separators the render contains NO
       whitespace, so every B2 unit would tokenize to exactly 1 token and
       the pre-registered token bar (tokens(B2) <= tokens(B0)/10) would
       pass trivially — self-defeating for the M2 question. Default
       separators are the only reading under which the frozen counter
       measures the unit's actual cost; they are used here.

Deterministic, stdlib only: byte-identical output on re-run (no timestamps
beyond the fixed date string, no unsorted dict iteration). Pinned input shas
are verified before any work.

Usage:
  python3 research/phase2/m2/extract.py \
      --corpus data/abcd/abcd_v1.1.json \
      --sample research/phase2/m2/sample.jsonl \
      --ontology data/abcd/ontology.json \
      --out research/phase2/m2/candidates.jsonl
  python3 research/phase2/m2/extract.py --selftest
      (synthetic out-of-vocab / non-str names: the flag path must fire)
"""
import argparse
import hashlib
import json
import math
from collections import Counter

PINNED_CORPUS_SHA16 = "005d425e890b30a1"
PINNED_SAMPLE_SHA16 = "f2195e7a6abe2221"
PINNED_ONTOLOGY_SHA16 = "2e1c1d763518ba08"
ONTOLOGY_CATEGORIES = ["kb_query", "interaction", "faq_policy"]
CORPUS_NAME = "abcd_v1.1"
B2_SCHEMA = ["problem_shape", "constraint", "unlock", "what_worked", "receipt"]
RECEIPT_SCHEMA = ["corpus", "convo_id", "flow", "subflow",
                  "event_span", "scope", "confidence"]


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def n_tokens(s):
    """Frozen token counter: whitespace-split."""
    return len(s.split())


def render_b0(convo):
    """All original turns as 'speaker: text', space-joined (frozen render)."""
    return " ".join(f"{sp}: {tx}" for sp, tx in convo["original"])


def b1_raw_names(convo):
    """Ordered targets[2] of every speaker=='action' delexed turn (D11)."""
    return [t["targets"][2] for t in convo.get("delexed", [])
            if t.get("speaker") == "action"]


def normalize_trace(raw, vocab):
    """Normalization of the raw targets[2] sequence to the canonical vocab.

    On this corpus it is the identity map (every name is in-vocab).
    Out-of-vocab (or non-str) names are FLAGGED — position + raw value — and
    NEVER DROPPED: the trace keeps them (stringified if non-str).
    Returns (names, unmapped_list).
    """
    names = []
    unmapped = []
    for i, name in enumerate(raw):
        if isinstance(name, str) and name in vocab:
            names.append(name)
            continue
        key = name if isinstance(name, str) else f"<non-str:{type(name).__name__}>"
        names.append(key)  # keep in the trace — never dropped
        unmapped.append({"position": i, "raw": key})
    return names, unmapped


def render_b1(names):
    return " ".join(names)


def b2_skeleton(convo, names):
    """Frozen unit schema, key order fixed; judgment fields null (lead draft
    pending); mechanical fields pre-filled (what_worked = D11 sequence)."""
    return {
        "problem_shape": None,
        "constraint": None,
        "unlock": None,
        "what_worked": list(names),
        "receipt": {
            "corpus": CORPUS_NAME,
            "convo_id": convo["convo_id"],
            "flow": convo["scenario"]["flow"],
            "subflow": convo["scenario"]["subflow"],
            "event_span": None,
            "scope": None,
            "confidence": None,
        },
    }


def render_b2(unit):
    """JSON in schema key order (insertion order = schema order), receipt
    included, default separators (see the RENDERING NOTE in the docstring —
    flagged for lead confirmation)."""
    return json.dumps(unit)


def quantiles(toks):
    """Same convention as sample.py: median (mean of middle two), p95
    nearest-rank."""
    n = len(toks)
    return {
        "median": (toks[n // 2 - 1] + toks[n // 2]) / 2,
        "p95_nearest_rank": toks[math.ceil(0.95 * n) - 1],
        "min": toks[0],
        "max": toks[-1],
        "total": sum(toks),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/abcd/abcd_v1.1.json")
    ap.add_argument("--sample", default="research/phase2/m2/sample.jsonl")
    ap.add_argument("--ontology", default="data/abcd/ontology.json")
    ap.add_argument("--out", default="research/phase2/m2/candidates.jsonl")
    args = ap.parse_args()

    # ---- pinned-input integrity (verified BEFORE any work) ----
    corpus_sha = sha16(args.corpus)
    sample_sha = sha16(args.sample)
    ontology_sha = sha16(args.ontology)
    assert corpus_sha == PINNED_CORPUS_SHA16, f"corpus sha mismatch: {corpus_sha}"
    assert sample_sha == PINNED_SAMPLE_SHA16, f"sample sha mismatch: {sample_sha}"
    assert ontology_sha == PINNED_ONTOLOGY_SHA16, f"ontology sha mismatch: {ontology_sha}"

    corpus = json.load(open(args.corpus))
    convos = corpus["train"] + corpus["dev"] + corpus["test"]
    by_id = {c["convo_id"]: c for c in convos}
    sample = [json.loads(l) for l in open(args.sample) if l.strip()]
    onto = json.load(open(args.ontology))

    # canonical vocab = union of the category keys (frozen definition)
    vocab = set()
    per_category = {}
    for cat in ONTOLOGY_CATEGORIES:
        names = set(onto["actions"][cat].keys())
        per_category[cat] = sorted(names)
        vocab |= names
    assert len(vocab) == 30, f"canonical vocab size {len(vocab)} != 30"

    # ---- per sample convo (convo_id-sorted, fixed row order) ----
    rows = []
    unmapped = Counter()          # name -> count (the flag aggregate)
    unmapped_rows = []            # (convo_id, position, raw name)
    for r in sorted(sample, key=lambda r: r["convo_id"]):
        c = by_id[r["convo_id"]]
        # rejoin vs corpus (validator-style J1 check)
        assert c["scenario"]["flow"] == r["flow"], f"convo {r['convo_id']}: flow mismatch"
        assert c["scenario"]["subflow"] == r["subflow"], f"convo {r['convo_id']}: subflow mismatch"

        b0 = render_b0(c)
        t0 = n_tokens(b0)
        assert t0 == r["n_tokens_b0"], \
            f"convo {r['convo_id']}: frozen B0 counter {t0} != sample row {r['n_tokens_b0']}"

        raw = b1_raw_names(c)
        assert len(raw) == r["n_action_turns"], \
            f"convo {r['convo_id']}: action turns {len(raw)} != sample row {r['n_action_turns']}"

        # normalization to the canonical vocab (identity on this corpus);
        # out-of-vocab names are FLAGGED, never dropped
        names, unmapped_here = normalize_trace(raw, vocab)
        for entry in unmapped_here:
            unmapped[entry["raw"]] += 1
            unmapped_rows.append((r["convo_id"], entry["position"], entry["raw"]))
        b1 = render_b1(names)
        t1 = n_tokens(b1)
        if not unmapped_here:
            # all 30 canonical names are single whitespace-free tokens, so a
            # fully in-vocab trace tokenizes 1:1 with its action turns
            assert t1 == len(raw), \
                f"convo {r['convo_id']}: B1 tokens {t1} != n_action_turns {len(raw)}"
        # else: a flagged name may carry whitespace — t1 != n_action_turns is
        # a CONSEQUENCE to report (meta unmapped block), not a silent rewrite

        b2 = b2_skeleton(c, names)
        b2s = render_b2(b2)
        t2 = n_tokens(b2s)

        rows.append({
            "convo_id": r["convo_id"],
            "flow": r["flow"],
            "subflow": r["subflow"],
            "n_action_turns": len(raw),
            "n_tokens_b0": t0,
            "n_tokens_b1": t1,
            "n_tokens_b2": t2,
            "b0": b0,
            "b1": b1,
            "b2": b2s,
            "b2_unit": b2,
            "unmapped": unmapped_here,
        })

    assert len(rows) == 80 and len({r["convo_id"] for r in rows}) == 80

    with open(args.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    candidates_sha = sha16(args.out)

    # ---- meta (deterministic; fixed date string, no runtime timestamps) ----
    t0s = sorted(r["n_tokens_b0"] for r in rows)
    t1s = sorted(r["n_tokens_b1"] for r in rows)
    t2s = sorted(r["n_tokens_b2"] for r in rows)
    n_unmapped = sum(unmapped.values())
    meta = {
        "artifact": "research/phase2/m2/candidates.jsonl",
        "round": ("R2 (M2 extraction) — candidates per GH #6 5449115746 §4 item 2; "
                  "sample frozen PR #21 (main @4d68187), D22 accepted as documented"),
        "created": "2026-08-28",
        "inputs": {
            "corpus": args.corpus,
            "corpus_sha256_16": corpus_sha,
            "n_universe": len(convos),
            "sample": args.sample,
            "sample_sha256_16": sample_sha,
            "ontology": args.ontology,
            "ontology_sha256_16": ontology_sha,
        },
        "canonical_vocab": {
            "definition": ("union of the category keys of ontology.json['actions']: "
                           "kb_query ∪ interaction ∪ faq_policy"),
            "by_category": {cat: per_category[cat] for cat in ONTOLOGY_CATEGORIES},
            "total": len(vocab),
        },
        "renders": {
            "b0": "all `original` turns as 'speaker: text', space-joined",
            "b1": "ordered targets[2] action names (D11), space-joined",
            "b2": "JSON of the unit, schema key order, receipt included, default separators (', ', ': ') — see the RENDERING NOTE flagged for lead confirmation",
            "token_counter": "whitespace-split of the rendered candidate (frozen)",
        },
        "b2_skeleton": {
            "schema": B2_SCHEMA,
            "receipt_schema": RECEIPT_SCHEMA,
            "judgment_fields_null_until_lead_draft":
                ["problem_shape", "constraint", "unlock",
                 "receipt.event_span", "receipt.scope", "receipt.confidence"],
            "mechanical_prefill":
                ["what_worked (ordered targets[2] sequence, D11 — pre-registration: "
                 "'the resolution action sequence from targets[2]'; the lead's 80-unit "
                 "draft is authoritative at join time)",
                 "receipt.corpus / receipt.convo_id / receipt.flow / receipt.subflow"],
            "note": ("n_tokens_b2 (the `b2` field's token count) is PROVISIONAL — "
                     "the final B2 token count is computed on the lead's unit at "
                     "join time (5449115746 §4 item 4); `b2_unit` carries the "
                     "skeleton structure, `b2` its render"),
            "what_failed": "OUT of the R2 unit (pending §4/R3; collapse rule pre-registered)",
        },
        "token_stats": {
            "b0": quantiles(t0s),
            "b1": quantiles(t1s),
            "b2_skeleton_provisional": quantiles(t2s),
        },
        "unmapped": {
            "definition": ("targets[2] value outside the canonical 30-name vocab "
                           "(FLAGGED, never dropped — stays in the b1 trace and per-row "
                           "`unmapped` list)"),
            "n_sample": n_unmapped,
            "n_sample_action_turns": sum(r["n_action_turns"] for r in rows),
            "names": dict(sorted(unmapped.items())),
            "corpus_wide_check": ("measured at sample-construction time (NOTES.md §5): all "
                                  "36,482 corpus action turns use exactly the 30 ontology "
                                  "names — 0 unmapped"),
            "precision_note": ("the R1-era '10 unmapped' gap was vs guidelines.json "
                               "Title-Case button names, NOT vs the canonical vocab; "
                               "vs the canonical vocab the measured value is 0/30 unmapped. "
                               "0 is the number; the guard is the guard."),
        },
        "honesty_clause": ("agent-judged from the first judge call; inter-pass "
                           "disagreement is a self-consistency floor, NOT human "
                           "inter-rater agreement (rides with every M2 number)"),
        "determinism": ("byte-identical on re-run: pinned input shas verified, "
                        "convo_id-sorted rows, fixed key order, fixed date string"),
        "candidates_sha256_16": candidates_sha,
    }
    meta_path = args.out + ".meta.json"
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, indent=1, sort_keys=False)
        fh.write("\n")

    # ---- summary ----
    q0, q1s_, q2s_ = meta["token_stats"]["b0"], meta["token_stats"]["b1"], meta["token_stats"]["b2_skeleton_provisional"]
    print(f"candidates:    {args.out}  (sha256:16 {candidates_sha})")
    print(f"meta:          {meta_path}")
    print(f"n=80  b0 tokens: median {q0['median']} p95 {q0['p95_nearest_rank']} "
          f"min {q0['min']} max {q0['max']} (must match sample meta)")
    print(f"b1 tokens:     total {q1s_['total']} (== sample action turns 286 expected) "
          f"min {q1s_['min']} max {q1s_['max']}")
    print(f"b2 skeleton:   min {q2s_['min']} max {q2s_['max']} median {q2s_['median']} "
          f"(PROVISIONAL until lead's draft)")
    print(f"unmapped:      {n_unmapped} (flag path {'FIRED' if n_unmapped else 'not fired — guard intact'})")
    if unmapped_rows:
        for cid, pos, key in unmapped_rows:
            print(f"  FLAG convo {cid} position {pos}: {key}")


def selftest():
    """Exercise the flag path that cannot fire on this corpus: synthetic
    out-of-vocab and non-str targets[2] values must be FLAGGED (position +
    raw value) and KEPT in the trace — never silently dropped."""
    vocab = {"pull-up-account", "validate-purchase"}
    # in-vocab, out-of-vocab string, non-str
    raw = ["pull-up-account", "Pull Up Account", 42, "validate-purchase"]
    names, unmapped = normalize_trace(raw, vocab)
    assert names == ["pull-up-account", "Pull Up Account", "<non-str:int>",
                     "validate-purchase"], names
    assert [u["position"] for u in unmapped] == [1, 2], unmapped
    assert [u["raw"] for u in unmapped] == ["Pull Up Account", "<non-str:int>"], unmapped
    # the flagged names stay in the render (never dropped)
    assert "Pull Up Account" in render_b1(names)
    # a flagged whitespace-bearing name changes the token count — reported,
    # not rewritten: 'pull-up-account Pull Up Account <non-str:int>
    # validate-purchase' whitespace-splits to 6 tokens (4 names, +2 from the
    # flagged name's internal spaces)
    assert n_tokens(render_b1(names)) == 6
    # B2 skeleton: schema key order + receipt key order + null judgment fields
    convo = {"convo_id": 1, "scenario": {"flow": "f", "subflow": "s"}}
    unit = b2_skeleton(convo, ["validate-purchase"])
    assert list(unit.keys()) == B2_SCHEMA, list(unit.keys())
    assert list(unit["receipt"].keys()) == RECEIPT_SCHEMA
    assert unit["problem_shape"] is None and unit["constraint"] is None and unit["unlock"] is None
    assert unit["receipt"]["event_span"] is None and unit["receipt"]["scope"] is None \
        and unit["receipt"]["confidence"] is None
    assert unit["what_worked"] == ["validate-purchase"]
    assert unit["receipt"]["corpus"] == CORPUS_NAME
    # render: schema key order preserved in the JSON text
    s = render_b2(unit)
    assert s.index("problem_shape") < s.index("constraint") < s.index("unlock") \
        < s.index("what_worked") < s.index("receipt")
    # and it is valid JSON round-tripping to the same unit
    assert json.loads(s) == unit
    # frozen counter sanity
    assert n_tokens("speaker: hello world") == 3 and n_tokens("") == 0
    print("SELFTEST OK: flag path fires (out-of-vocab + non-str FLAGGED, kept in "
          "trace, never dropped); B2 schema key order + null judgment fields verified.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        main()
