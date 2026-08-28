#!/usr/bin/env python3
"""Selftest for join_m2.py — proves the JOIN PIPELINE, not any result.

Runs the join against SYNTHETIC judge outputs (fabricated, structurally
valid, derived from the real frozen binding layer) in two scenarios:

  A. collapse scenario   — B1 (action trace) reaches the 0.8 value bar on
                           >= 64/80 convos  -> outcome branch 'COLLAPSE TRIGGERED'
  B. no-collapse scenario — B2 carries value, B1 does not -> 'NO COLLAPSE'

and verifies:
  1. every frozen input gate passes (shas, key order, what_worked==B1 trace,
     frozen-counter recomputation 80/80);
  2. the join is deterministic (byte-identical results.json on re-run);
  3. the round-verdict / falsification / agreement branches compute as the
     frozen contract says (re-derived independently in this selftest from
     the same judge files — not by importing join_m2's internals);
  4. the gate layer REJECTS tampering (wrong judge file order, non-frozen
     score value) with a non-zero exit;
  5. the report renders the required sections (per-convo table, verdict,
     falsification, loss ledger, agreement, honesty clause, vocab guard,
     re-run contract) and is marked SYNTHETIC.

Nothing here is a result: the outputs live in /tmp and are deleted on
success. The real join runs the same join_m2.py on evaluation's judge files.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

M2 = "research/phase2/m2"
JOIN = f"{M2}/join_m2.py"
TMP = "/tmp/m2_join_selftest"
PY = sys.executable


def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


def load_lines(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def norm(s):
    return " ".join((s or "").lower().split())


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def make_judge_files(tag, collapse):
    """Build structurally valid synthetic judge files for scenario `tag`.

    collapse=True  -> B1 value 1.0 on convos[0:64] (>=64/80), 0.5 elsewhere.
    collapse=False -> B1 value 0.5 everywhere; B2 1.0 on [0:50], 0.5 else.
    B0 is 1.0 everywhere except every 7th convo (0.5) — the ceiling is
    MEASURED, not assumed 1.0 (synthetic realism).
    """
    d = f"{TMP}/{tag}"
    os.makedirs(d, exist_ok=True)
    cands = load_lines(f"{M2}/candidates.jsonl")
    cand_map = json.load(open(f"{M2}/judge/binding/candidate_mapping.json"))["mapping"]
    conv_map_file = json.load(open(f"{M2}/judge/scoring/convo_mapping.json"))
    flat = conv_map_file["candidate_codename -> {convo_id, candidate}"]
    code_to_cid = conv_map_file["convo_codename -> convo_id"]
    pass1_input = load_lines(f"{M2}/judge/binding/pass1_input.jsonl")
    pass2_input = load_lines(f"{M2}/judge/binding/pass2_input.jsonl")
    scoring_input = load_lines(f"{M2}/judge/scoring/scoring_input.jsonl")

    # --- blind pass answers (item_id keyed; order = each pass's input order)
    pass1_rows = []
    for it in pass1_input:
        key = f"{it['item_id']}|{it['codename']}"
        cid = cand_map[key]["convo_id"]
        cand = cand_map[key]["candidate"]
        pass1_rows.append({
            "item_id": it["item_id"], "pass": 1,
            "q1": f"synthetic q1 for convo {cid} candidate {cand} (intent + structure)",
            "q2": f"synthetic binding constraint for convo {cid}",
            "q3": f"synthetic actions in order for convo {cid}",
        })
    p1_by_id = {r["item_id"]: r for r in pass1_rows}
    pass2_rows = []
    disagree = set(it["item_id"] for it in pass1_input[::7])  # ~34 items disagree on q2
    for it in pass2_input:
        r = dict(p1_by_id[it["item_id"]])
        r["pass"] = 2
        if it["item_id"] in disagree:
            r["q2"] = r["q2"] + " (rephrased)"
        pass2_rows.append(r)
    write_jsonl(f"{d}/pass1_answers.jsonl", pass1_rows)
    write_jsonl(f"{d}/pass2_answers.jsonl", pass2_rows)

    # --- scoring answers
    code_of = {}
    for c, v in flat.items():
        code_of[(v["convo_id"], v["candidate"])] = c.split("|", 1)[1]
    scoring_rows = []
    for i, it in enumerate(scoring_input):
        code = it["convo_codename"]
        cid = code_to_cid[code]
        def sc_for(cand):
            if cand == "b0":
                v = 0.5 if i % 7 == 0 else 1.0
            elif cand == "b1":
                v = (1.0 if cid in [c["convo_id"] for c in cands[:64]] else 0.5) if collapse else 0.5
            else:
                v = (1.0 if cid in [c["convo_id"] for c in cands[:50]] else 0.5) if not collapse else 1.0
            return {"s1": v, "s2": v, "s3": v}
        scoring_rows.append({
            "convo_codename": code,
            "r1": "synthetic reference problem",
            "r2": "synthetic reference constraint",
            "r3": "synthetic reference actions",
            "scores": {code_of[(cid, c)]: sc_for(c) for c in ("b0", "b1", "b2")},
        })
    write_jsonl(f"{d}/scoring_answers.jsonl", scoring_rows)
    return d


def run_join(d, out_dir, tag):
    cmd = [PY, JOIN, "--m2", M2,
           "--pass1", f"{d}/pass1_answers.jsonl",
           "--pass2", f"{d}/pass2_answers.jsonl",
           "--scoring", f"{d}/scoring_answers.jsonl",
           "--out-dir", out_dir, "--dry-run",
           "--results", f"m2_results.{tag}.json", "--report", f"m2_report.{tag}.md"]
    return subprocess.run(cmd, capture_output=True, text=True)


def independent_check(d, out_dir, tag, expect_round_pass, expect_collapse):
    """Re-derive the headline numbers from the judge files alone (plain Python)."""
    res = json.load(open(f"{out_dir}/m2_results.{tag}.json"))
    scoring = load_lines(f"{d}/scoring_answers.jsonl")
    conv_map_file = json.load(open(f"{M2}/judge/scoring/convo_mapping.json"))
    flat = conv_map_file["candidate_codename -> {convo_id, candidate}"]
    code_to_cid = conv_map_file["convo_codename -> convo_id"]
    pass1 = {r["item_id"]: r for r in load_lines(f"{d}/pass1_answers.jsonl")}
    pass2 = {r["item_id"]: r for r in load_lines(f"{d}/pass2_answers.jsonl")}
    cands = load_lines(f"{M2}/candidates.jsonl")

    # values + bar
    n_pass = n_v = 0
    sum_b2 = sum_b0 = 0
    code_of = {}
    for c, v in flat.items():
        code_of[(v["convo_id"], v["candidate"])] = c.split("|", 1)[1]
    cid_of = {code: cid for code, cid in code_to_cid.items()}
    for r in cands:
        sr = next(s for s in scoring if cid_of[s["convo_codename"]] == r["convo_id"])
        vals = {c: (sr["scores"][code_of[(r["convo_id"], c)]]["s1"]
                    + sr["scores"][code_of[(r["convo_id"], c)]]["s2"]
                    + sr["scores"][code_of[(r["convo_id"], c)]]["s3"]) / 3
                for c in ("b0", "b1", "b2")}
        t2 = len(json.dumps(next(x for x in load_lines(f"{M2}/b2_draft.jsonl")
                                 if x["convo_id"] == r["convo_id"])["b2_unit"]).split())
        v_ok = vals["b2"] >= 0.8 * vals["b0"]
        t_ok = t2 <= r["n_tokens_b0"] / 10
        n_v += v_ok
        n_pass += v_ok and t_ok
        sum_b2 += t2
        sum_b0 += r["n_tokens_b0"]
    agg = sum_b2 / sum_b0
    got_pass = (n_pass / 80 >= 0.70) and (agg <= 0.1)
    assert res["round_verdict"]["round_pass"] == got_pass == expect_round_pass, \
        f"{tag}: round verdict mismatch (join {res['round_verdict']['round_pass']}, independent {got_pass})"
    assert abs(res["aggregates"]["tokens"]["b2"] - sum_b2) < 1e-9
    assert abs(res["aggregates"]["tokens"]["b0"] - sum_b0) < 1e-9
    assert abs(res["round_verdict"]["aggregate_token_ratio"] - agg) < 1e-6

    # agreement
    pass1_input = load_lines(f"{M2}/judge/binding/pass1_input.jsonl")
    n_agree = n_tot = 0
    for it in pass1_input:
        for q in ("q1", "q2", "q3"):
            n_tot += 1
            if norm(pass1[it["item_id"]][q]) == norm(pass2[it["item_id"]][q]):
                n_agree += 1
    assert res["two_pass_agreement"]["item_questions_agree"] == n_agree, f"{tag}: agreement n"
    assert abs(res["two_pass_agreement"]["agreement_rate"] - n_agree / n_tot) < 1e-6
    assert res["two_pass_agreement"]["disagreement_gt_15pct"] == (n_agree / n_tot < 0.85)

    # falsification branch
    assert res["falsification_b1_vs_b2"]["b1_collapses_unit"] == expect_collapse, f"{tag}: collapse flag"
    if expect_collapse:
        assert res["falsification_b1_vs_b2"]["outcome"].startswith("COLLAPSE TRIGGERED"), f"{tag}"
    else:
        assert res["falsification_b1_vs_b2"]["outcome"].startswith("NO COLLAPSE"), f"{tag}"

    # structural finding
    st = res["structural_token_half"]
    assert st["empty_unit_floor_tokens"] == 23, f"{tag}: floor"
    # independent: floor > B0/10 per convo from the pinned rows
    n_blocked_ind = sum(1 for x in load_lines(f"{M2}/candidates.jsonl") if 23 > x["n_tokens_b0"] / 10)
    assert st["per_convo_floor_blocked_count"] == n_blocked_ind, \
        f"{tag}: floor-blocked count {st['per_convo_floor_blocked_count']} != independent {n_blocked_ind}"
    assert abs(st["aggregate_ratio_floor"] - 23 * 80 / sum_b0) < 1e-6, f"{tag}: floor arithmetic"

    # report sections
    rep = open(f"{out_dir}/m2_report.{tag}.md").read()
    for section in ("## 1. Inputs", "## 2. The frozen bar", "## 3. Per-convo table",
                    "## 4. Round verdict", "## 5. B1-vs-B2 falsification",
                    "## 6. Per-field loss ledger", "## 7. Two-pass agreement",
                    "## 8. Vocab guard", "## 9. Honesty clause", "## 10. Re-run contract",
                    "SYNTHETIC DRY RUN", "0 is the number", "self-consistency floor"):
        assert section in rep, f"{tag}: report missing section {section!r}"
    assert res["dry_run"] is True
    print(f"  [{tag}] independent re-derivation: MATCH (round_pass={got_pass}, collapse={expect_collapse}, "
          f"agreement={n_agree}/{n_tot}, agg_ratio={agg:.4f})")


def tamper_tests():
    d = f"{TMP}/tamper"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(f"{TMP}/A", d)
    # 1) reorder pass1 answers -> order gate must fire
    rows = load_lines(f"{d}/pass1_answers.jsonl")
    rows[0], rows[1] = rows[1], rows[0]
    write_jsonl(f"{d}/pass1_shuffled.jsonl", rows)
    cmd = [PY, JOIN, "--m2", M2, "--pass1", f"{d}/pass1_shuffled.jsonl",
           "--pass2", f"{d}/pass2_answers.jsonl", "--scoring", f"{d}/scoring_answers.jsonl",
           "--out-dir", d, "--dry-run", "--results", "x.json", "--report", "x.md"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 1 and "order != input order" in r.stderr, f"tamper1: {r.returncode} {r.stderr[:200]}"
    print("  [tamper-1] reordered pass1 answers -> JOIN GATE FAILED (order) — correct")
    # 2) non-frozen score value -> score gate must fire
    sc = load_lines(f"{d}/scoring_answers.jsonl")
    sc[0]["scores"][list(sc[0]["scores"])[0]]["s1"] = 0.3
    write_jsonl(f"{d}/scoring_bad.jsonl", sc)
    cmd = [PY, JOIN, "--m2", M2, "--pass1", f"{d}/pass1_answers.jsonl",
           "--pass2", f"{d}/pass2_answers.jsonl", "--scoring", f"{d}/scoring_bad.jsonl",
           "--out-dir", d, "--dry-run", "--results", "x.json", "--report", "x.md"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 1 and "non-frozen score values" in r.stderr, f"tamper2: {r.returncode} {r.stderr[:200]}"
    print("  [tamper-2] non-frozen s1=0.3 -> JOIN GATE FAILED (frozen rubric values) — correct")


def main():
    shutil.rmtree(TMP, ignore_errors=True)
    print("selftest_join_m2 — synthetic pipeline proof (NOT results)")
    for tag, collapse in (("A", True), ("B", False)):
        d = make_judge_files(tag, collapse)
        out = f"{TMP}/out{tag}"
        os.makedirs(out, exist_ok=True)
        r = run_join(d, out, tag)
        assert r.returncode == 0, f"{tag}: join failed:\n{r.stdout}\n{r.stderr}"
        b1 = open(f"{out}/m2_results.{tag}.json", "rb").read()
        rep1 = open(f"{out}/m2_report.{tag}.md", "rb").read()
        # determinism: second run byte-identical
        r2 = run_join(d, out, tag)
        assert r2.returncode == 0 and r.stdout == r2.stdout, f"{tag}: re-run differs"
        b2 = open(f"{out}/m2_results.{tag}.json", "rb").read()
        rep2 = open(f"{out}/m2_report.{tag}.md", "rb").read()
        assert b1 == b2 and rep1 == rep2, f"{tag}: not deterministic"
        print(f"  [{tag}] join OK (rc=0), deterministic (byte-identical results.json + report.md)")
        independent_check(d, out, tag, expect_round_pass=False, expect_collapse=collapse)
    tamper_tests()
    shutil.rmtree(TMP, ignore_errors=True)
    print("SELFTEST PASS — pipeline proven on synthetic data; no real results produced")


if __name__ == "__main__":
    main()
