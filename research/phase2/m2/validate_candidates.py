#!/usr/bin/env python3
"""validate_candidates.py — M2 candidate validator (R2): independent
re-derivation + frozen-invariant checks for candidates.jsonl.

Re-implements the extraction (GH #6 5449115746 §4 item 2) INDEPENDENTLY
(no import of extract.py), re-derives every render from the raw corpus +
pinned sample + pinned ontology, and checks the committed
candidates.jsonl against:

  A. pinned inputs: corpus sha256:16 005d425e890b30a1; sample sha
     f2195e7a6abe2221; ontology sha 2e1c1d763518ba08; the canonical vocab
     re-derived = union of ontology.json['actions'] category keys
     (kb_query ∪ interaction ∪ faq_policy), size 30
  B. schema: exactly the 12 frozen fields per row, in order
  C. N = 80; unique convo_ids; every id in the corpus; flow/subflow
     re-join vs the corpus and vs the sample row
  D. B0: re-rendered from the corpus (all `original` turns as
     "speaker: text", space-joined) byte-identical to the committed b0;
     frozen counter (whitespace-split) == committed n_tokens_b0 == sample
     row's n_tokens_b0
  E. B1: re-derived targets[2] sequence (D11) == committed b1 (names,
     order); every name in the canonical vocab; `unmapped` == [] on every
     row (the flag aggregate must be 0 on this corpus); committed
     n_tokens_b1 == whitespace-split of b1 == sample row's n_action_turns
  F. B2: b2_unit has the frozen schema key order; mechanical prefill
     correct (what_worked == B1 sequence; receipt.corpus/convo_id/flow/
     subflow from the corpus); committed b2 == json.dumps(b2_unit)
     (default separators); committed n_tokens_b2 == whitespace-split of b2.
     The judgment fields are checked MODE-AWARE (the validator detects the
     committed artifact's mode):
       SKELETON (PR #22; --draft omitted): F2 — problem_shape/constraint/
         unlock + receipt.event_span/scope/confidence all null (draft
         pending).
       FILLED (R2 fix-forward, 5450060638 §1 item 1; --draft given):
         F2' — judgment fields NON-NULL where drafted (problem_shape/
         constraint + receipt.event_span/scope/confidence non-null on
         every row; `unlock` null ALLOWED — 53/80 on this draft), AND F6 —
         the committed b2_unit equals the pinned b2_draft.jsonl's (sha
         5063a85c4ab79465) unit for that convo (the join slots, never
         mutates, the lead's unit).
  G. token stats: B0 median/p95/min/max match the sample meta exactly
     (187.0 / 277 / 65 / 417)

Stdlib only. Exit 0 with "VERDICT: PASS" iff every check passes; otherwise
lists failures and exits 1.

Usage:
  python3 research/phase2/m2/validate_candidates.py \
      --corpus data/abcd/abcd_v1.1.json \
      --sample research/phase2/m2/sample.jsonl \
      --ontology data/abcd/ontology.json \
      --candidates research/phase2/m2/candidates.jsonl \
      [--draft research/phase2/m2/b2_draft.jsonl]
      (--draft enables the FILLED-unit F-checks; omit to validate the
      SKELETON artifact)
"""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter

CORPUS_SHA = "005d425e890b30a1"
SAMPLE_SHA = "f2195e7a6abe2221"
ONTOLOGY_SHA = "2e1c1d763518ba08"
DRAFT_SHA = "5063a85c4ab79465"   # b2_draft.jsonl (the lead's 80-unit draft)
CATEGORIES = ["kb_query", "interaction", "faq_policy"]
N_SAMPLE = 80
FROZEN_FIELDS = ["convo_id", "flow", "subflow", "n_action_turns",
                 "n_tokens_b0", "n_tokens_b1", "n_tokens_b2",
                 "b0", "b1", "b2", "b2_unit", "unmapped"]
B2_SCHEMA = ["problem_shape", "constraint", "unlock", "what_worked", "receipt"]
RECEIPT_SCHEMA = ["corpus", "convo_id", "flow", "subflow",
                  "event_span", "scope", "confidence"]


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/abcd/abcd_v1.1.json")
    ap.add_argument("--sample", default="research/phase2/m2/sample.jsonl")
    ap.add_argument("--ontology", default="data/abcd/ontology.json")
    ap.add_argument("--candidates", default="research/phase2/m2/candidates.jsonl")
    ap.add_argument("--draft", default=None,
                    help="b2_draft.jsonl (sha 5063a85c4ab79465): enable the "
                         "FILLED-unit F-checks (F2' non-null-where-drafted + "
                         "F6 unit == draft unit). Omit to validate the SKELETON "
                         "(PR #22) artifact.")
    args = ap.parse_args()

    failures = []
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        if not ok:
            failures.append(f"{name}: {detail}")

    # A. pinned inputs + re-derived canonical vocab
    csha, ssh, osha = sha16(args.corpus), sha16(args.sample), sha16(args.ontology)
    check("A1 corpus pinned sha", csha == CORPUS_SHA, f"got {csha}")
    check("A2 sample pinned sha", ssh == SAMPLE_SHA, f"got {ssh}")
    check("A3 ontology pinned sha", osha == ONTOLOGY_SHA, f"got {osha}")

    corpus = json.load(open(args.corpus))
    convos = corpus["train"] + corpus["dev"] + corpus["test"]
    by_id = {c["convo_id"]: c for c in convos}
    sample = {r["convo_id"]: r for r in
              (json.loads(l) for l in open(args.sample) if l.strip())}
    onto = json.load(open(args.ontology))
    vocab = set()
    for cat in CATEGORIES:
        vocab |= set(onto["actions"][cat].keys())
    check("A4 canonical vocab size 30 (re-derived)", len(vocab) == 30,
          f"got {len(vocab)}")

    # --draft pin (FILLED mode): the lead's 80-unit draft
    draft_units = None
    if args.draft:
        dsha = sha16(args.draft)
        check("A5 draft pinned sha", dsha == DRAFT_SHA, f"got {dsha}")
        draft_units = {json.loads(l)["convo_id"]: json.loads(l)["b2_unit"]
                       for l in open(args.draft) if l.strip()}
        check("A6 draft has 80 units", len(draft_units) == N_SAMPLE,
              f"got {len(draft_units)}")

    rows = [json.loads(l) for l in open(args.candidates) if l.strip()]
    # MODE-AWARE (5450060638 §1 item 1): the validator detects the committed
    # artifact's mode. FILLED iff --draft is given (the pinned draft is the
    # authority on the B2 unit); otherwise SKELETON.
    FILLED = args.draft is not None

    # B. schema
    bad = [(i, list(r.keys())) for i, r in enumerate(rows)
           if list(r.keys()) != FROZEN_FIELDS]
    check("B exact 12-field schema (order)", not bad, f"bad rows: {bad[:3]}")

    # C. N, uniqueness, corpus membership, rejoin
    ids = [r["convo_id"] for r in rows]
    check("C1 N == 80", len(rows) == N_SAMPLE, f"got {len(rows)}")
    check("C2 unique convo_ids", len(set(ids)) == len(ids),
          f"{len(rows) - len(set(ids))} dupes")
    check("C3 all ids in corpus", all(i in by_id for i in ids),
          f"missing: {[i for i in ids if i not in by_id][:5]}")
    check("C4 ids == sample ids (set)", set(ids) == set(sample),
          f"diff: {sorted(set(ids) ^ set(sample))[:5]}")
    mismatch = [r["convo_id"] for r in rows
                if r["flow"] != by_id[r["convo_id"]]["scenario"]["flow"]
                or r["subflow"] != by_id[r["convo_id"]]["scenario"]["subflow"]
                or r["flow"] != sample[r["convo_id"]]["flow"]
                or r["subflow"] != sample[r["convo_id"]]["subflow"]]
    check("C5 flow/subflow rejoin (corpus + sample)", not mismatch,
          f"{mismatch[:5]}")

    # D. B0 re-render
    bad_b0, bad_t0, bad_s0 = [], [], []
    for r in rows:
        c = by_id[r["convo_id"]]
        b0 = " ".join(f"{sp}: {tx}" for sp, tx in c["original"])
        if b0 != r["b0"]:
            bad_b0.append(r["convo_id"])
        if len(b0.split()) != r["n_tokens_b0"]:
            bad_t0.append(r["convo_id"])
        if r["n_tokens_b0"] != sample[r["convo_id"]]["n_tokens_b0"]:
            bad_s0.append(r["convo_id"])
    check("D1 b0 byte-identical to corpus re-render", not bad_b0, f"{bad_b0[:5]}")
    check("D2 n_tokens_b0 == frozen counter of b0", not bad_t0, f"{bad_t0[:5]}")
    check("D3 n_tokens_b0 == sample row", not bad_s0, f"{bad_s0[:5]}")

    # E. B1 re-derivation
    bad_b1, bad_vocab, bad_un, bad_t1, bad_a1 = [], [], [], [], []
    n_action_total = 0
    for r in rows:
        c = by_id[r["convo_id"]]
        raw = [t["targets"][2] for t in c.get("delexed", [])
               if t.get("speaker") == "action"]
        n_action_total += len(raw)
        if " ".join(raw) != r["b1"]:
            bad_b1.append(r["convo_id"])
        if any(n not in vocab for n in raw):
            bad_vocab.append(r["convo_id"])
        if r["unmapped"] != []:
            bad_un.append(r["convo_id"])
        if len(r["b1"].split()) != r["n_tokens_b1"]:
            bad_t1.append(r["convo_id"])
        if r["n_tokens_b1"] != sample[r["convo_id"]]["n_action_turns"]:
            bad_a1.append(r["convo_id"])
    check("E1 b1 == re-derived targets[2] sequence (D11)", not bad_b1,
          f"{bad_b1[:5]}")
    check("E2 every B1 name in canonical vocab", not bad_vocab, f"{bad_vocab[:5]}")
    check("E3 unmapped == [] on every row (flag aggregate 0)", not bad_un,
          f"{bad_un[:5]}")
    check("E4 n_tokens_b1 == frozen counter of b1", not bad_t1, f"{bad_t1[:5]}")
    check("E5 n_tokens_b1 == sample n_action_turns", not bad_a1, f"{bad_a1[:5]}")

    # F. B2 (mode-aware): F1/F3/F4/F5 are mode-independent; F2 checks the
    # judgment fields per the committed mode (SKELETON = null, FILLED =
    # non-null where drafted with `unlock` null allowed); F6 (FILLED only)
    # checks the committed unit == the pinned draft's unit (slot, don't
    # mutate).
    bad_schema, bad_null, bad_prefill, bad_render, bad_t2 = [], [], [], [], []
    bad_nonnull, bad_eq = [], []
    n_unlock_null = 0
    for r in rows:
        c = by_id[r["convo_id"]]
        u = r["b2_unit"]
        if list(u.keys()) != B2_SCHEMA or list(u["receipt"].keys()) != RECEIPT_SCHEMA:
            bad_schema.append(r["convo_id"])
            continue
        if FILLED:
            # F2' — non-null where drafted: problem_shape/constraint +
            # receipt.event_span/scope/confidence non-null on every row;
            # `unlock` null ALLOWED (53/80 on this draft)
            if any(u[k] is None for k in ("problem_shape", "constraint")) \
               or any(u["receipt"][k] is None
                      for k in ("event_span", "scope", "confidence")):
                bad_nonnull.append(r["convo_id"])
            if u["unlock"] is None:
                n_unlock_null += 1
            # F6 — committed unit == the pinned draft's unit for this convo
            if u != draft_units.get(r["convo_id"]):
                bad_eq.append(r["convo_id"])
        else:
            # F2 — SKELETON: all six judgment fields null (draft pending)
            if any(u[k] is not None for k in ("problem_shape", "constraint", "unlock")) \
               or any(u["receipt"][k] is not None
                      for k in ("event_span", "scope", "confidence")):
                bad_null.append(r["convo_id"])
        if u["what_worked"] != r["b1"].split() \
           or u["receipt"]["corpus"] != "abcd_v1.1" \
           or u["receipt"]["convo_id"] != r["convo_id"] \
           or u["receipt"]["flow"] != c["scenario"]["flow"] \
           or u["receipt"]["subflow"] != c["scenario"]["subflow"]:
            bad_prefill.append(r["convo_id"])
        if json.dumps(u) != r["b2"]:
            bad_render.append(r["convo_id"])
        if len(r["b2"].split()) != r["n_tokens_b2"]:
            bad_t2.append(r["convo_id"])
    check("F1 b2_unit frozen schema key order", not bad_schema, f"{bad_schema[:5]}")
    if FILLED:
        check("F2' judgment fields non-null where drafted "
              "(problem_shape/constraint/receipt.event_span/scope/confidence; "
              "unlock null allowed)", not bad_nonnull, f"{bad_nonnull[:5]}")
        check("F6 b2_unit == pinned draft unit (slot, don't mutate)",
              not bad_eq, f"{bad_eq[:5]}")
    else:
        check("F2 judgment fields null (lead draft pending)", not bad_null,
              f"{bad_null[:5]}")
    check("F3 mechanical prefill correct (what_worked + receipt)",
          not bad_prefill, f"{bad_prefill[:5]}")
    check("F4 b2 == json.dumps(b2_unit) (default separators)", not bad_render,
          f"{bad_render[:5]}")
    check("F5 n_tokens_b2 == frozen counter of b2", not bad_t2, f"{bad_t2[:5]}")

    # G. token stats vs the frozen sample-meta numbers
    toks = sorted(r["n_tokens_b0"] for r in rows)
    median = (toks[39] + toks[40]) / 2
    p95 = toks[math.ceil(0.95 * len(toks)) - 1]
    check("G1 tokens_b0 median 187.0", median == 187.0, f"got {median}")
    check("G2 tokens_b0 p95 (nearest-rank) 277", p95 == 277, f"got {p95}")
    check("G3 tokens_b0 min 65 / max 417", toks[0] == 65 and toks[-1] == 417,
          f"got min {toks[0]} max {toks[-1]}")

    # ---- report ----
    print("validate_candidates.py — M2 candidates (R2), independent re-derivation")
    print(f"  mode:          {'FILLED (lead draft slotted — --draft given)' if FILLED else 'SKELETON (judgment fields null)'}")
    print(f"  corpus {args.corpus} sha256:16 {csha}")
    print(f"  sample {args.sample} sha256:16 {ssh}")
    print(f"  ontology {args.ontology} sha256:16 {osha} (vocab {len(vocab)})")
    if FILLED:
        print(f"  draft  {args.draft} sha256:16 {sha16(args.draft)}")
    print(f"  candidates {args.candidates} sha256:16 {sha16(args.candidates)} rows {len(rows)}")
    print("-" * 72)
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}"
              + (f" — {detail}" if detail and not ok else ""))
    print("-" * 72)
    t1s = sorted(r["n_tokens_b1"] for r in rows)
    t2s = sorted(r["n_tokens_b2"] for r in rows)
    per_flow = Counter(r["flow"] for r in rows)
    print(f"  per_flow: " + ", ".join(f"{f}={per_flow.get(f, 0)}"
                                      for f in sorted(per_flow)))
    print(f"  B1 tokens: total {n_action_total} min {t1s[0]} max {t1s[-1]} "
          f"(== per-row n_action_turns)")
    if FILLED:
        print(f"  B2 draft tokens (FINAL): min {t2s[0]} median {(t2s[39]+t2s[40])/2} "
              f"max {t2s[-1]} total {sum(t2s)}  |  unlock null: {n_unlock_null}/80 "
              f"(allowed)")
    else:
        print(f"  B2 skeleton tokens: min {t2s[0]} median {(t2s[39]+t2s[40])/2} "
              f"max {t2s[-1]} (PROVISIONAL until lead's draft)")
    print(f"  unmapped aggregate: {sum(len(r['unmapped']) for r in rows)}")
    print("-" * 72)
    if failures:
        print(f"VERDICT: FAIL ({len(failures)} failed check(s))")
        for f in failures:
            print(f"  FAIL {f}")
        sys.exit(1)
    n_chk = len(checks)
    print(f"VERDICT: PASS — {n_chk}/{n_chk} checks (every render re-derived "
          f"from the raw corpus; mode={'FILLED' if FILLED else 'SKELETON'})")
    sys.exit(0)


if __name__ == "__main__":
    main()
