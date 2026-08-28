#!/usr/bin/env python3
"""R2/M2 join — pre-built 2026-08-28 (research-engineer, lab-1), BON-42.

JOINS the pinned inputs with the judge's numbers and renders:
    m2_results.json + m2_report.md
per the FROZEN contract (GH #6 comment 5449115746 section 4 item 4):

    per-convo table (value B0/B1/B2, tokens B0/B1/B2, per-convo bar),
    round verdict vs the frozen bar, B1-vs-B2 falsification outcome,
    per-field loss ledger, two-pass agreement number, honesty clause,
    README re-run contract (research/phase2/m2/README.md).

Pinned inputs (verified by sha256:16 on every run, gates 1-3):
    candidates.jsonl  dd1869a2d72c6b2b   (PR #22, main @601c310)
    b2_draft.jsonl    5063a85c4ab79465   (PR #23, main @d8a8f33)
Judge inputs (pinned by the join itself via recorded shas, gate 4):
    blind pass1 / pass2 answers (240 items each, PROTOCOL-m2-blind.md)
    scoring answers (80 rows, PROTOCOL-m2-scoring.md)

At join time n_tokens_b2 is RECOMPUTED on the draft unit with the frozen
counter (whitespace-split of json.dumps(unit), default separators) and must
equal b2_draft's n_tokens_b2 on all 80 rows (gate 5); otherwise the join
aborts — the join is a pure function of the judge outputs.

Usage (the one command, once the judge's numbers land):
    python3 research/phase2/m2/join_m2.py \
        --m2 research/phase2/m2 \
        --pass1 <path>/pass1_answers.jsonl \
        --pass2 <path>/pass2_answers.jsonl \
        --scoring <path>/scoring_answers.jsonl
    --out-dir <dir>          (default: the m2 dir)
    --results / --report     (output paths, default m2_results.json / m2_report.md)
    --dry-run                (marks the artifacts SYNTHETIC-DRY-RUN; never commit
                              those as real results — use only with synthetic
                              judge files, e.g. via selftest_join_m2.py)

selftest (pipeline proof, synthetic judge numbers, no real results):
    python3 research/phase2/m2/selftest_join_m2.py

Stdlib only. Deterministic: fixed date string, fixed key order,
convo_id-sorted rows, byte-identical output on re-run (given the same
inputs). The bar is FROZEN — the join never tunes it (D18).
"""
import argparse
import datetime
import hashlib
import json
import statistics
import sys

# ----------------------------- frozen inputs -------------------------------
CANDIDATES_SHA = "dd1869a2d72c6b2b"   # candidates.jsonl  (PR #22, main @601c310)
DRAFT_SHA = "5063a85c4ab79465"        # b2_draft.jsonl    (PR #23, main @d8a8f33)
SAMPLE_SHA = "f2195e7a6abe2221"       # sample.jsonl      (PR #21, main @4d68187)
B2_SCHEMA = ["problem_shape", "constraint", "unlock", "what_worked", "receipt"]
RECEIPT_SCHEMA = ["corpus", "convo_id", "flow", "subflow", "event_span", "scope", "confidence"]

# ------------------------ frozen bar (5449115746 s3) ------------------------
BAR = {
    "source": "GH #6 5449115746 s3 (frozen pre-registration; D18 — never tuned)",
    "per_convo": "value(B2) >= 0.8 * value(B0) AND tokens(B2) <= tokens(B0)/10",
    "value_factor": 0.8,
    "token_ratio_max": 0.1,
    "round_pass": "share of convos meeting the per-convo bar >= 0.70 AND aggregate token ratio sum(tokens(B2))/sum(tokens(B0)) <= 0.1",
    "value_counter": "value(candidate) = (s1+s2+s3)/3, rubric per PROTOCOL-m2-scoring.md (frozen)",
    "token_counter": "whitespace-split tokens of the rendered candidate; B2 = canonical JSON of the unit, schema key order, default separators (', ', ': ')",
    "falsification": "B1 (action trace) scored identically; if B1 alone reconstructs >= 80% of B0's value, the unit collapses to trace + label (pre-registered collapse)",
}
HONESTY = ("All M2 numbers are AGENT-JUDGED (blind answering passes 1+2 + one scoring "
           "pass, frozen protocols). The two-pass agreement is a judge self-consistency "
           "floor under frozen rules, NOT human inter-rater agreement, and is never cited "
           "as 'human agreement'. The B2 units are AGENT-DRAFTED (lead); the falsification "
           "is the independent blind judge.")

DATE = "2026-08-28"


# ------------------------------- utilities ---------------------------------
def sha16(b):
    return hashlib.sha256(b).hexdigest()[:16]


def load_lines(path):
    out = []
    with open(path, "rb") as f:
        for ln in f.read().decode("utf-8").splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    return out


def frac(n, d):
    if d == 0:
        return "0"
    for dec in range(0, 7):
        s = f"{n / d:.{dec}f}" if dec else str(round(n / d, 0)).replace(".0", "")
        if float(s) == n / d:
            return s
    return f"{n / d:.6f}"


def pct(x):
    return f"{100 * x:.1f}%"


def norm(s):
    return " ".join((s or "").lower().split())


# ------------------------------ gate helpers --------------------------------
class Fail(Exception):
    pass


def gate(cond, msg):
    if not cond:
        raise Fail(msg)


# ------------------------------ main pipeline -------------------------------
def run(m2, pass1_path, pass2_path, scoring_path, out_dir,
        results_path, report_path, dry_run):
    # ---------- Gate 1: pinned frozen inputs ----------
    cand_path, draft_path = f"{m2}/candidates.jsonl", f"{m2}/b2_draft.jsonl"
    cand_raw = open(cand_path, "rb").read()
    draft_raw = open(draft_path, "rb").read()
    sha16(cand_raw) == CANDIDATES_SHA or gate(False, f"candidates.jsonl sha {sha16(cand_raw)} != pinned {CANDIDATES_SHA}")
    sha16(draft_raw) == DRAFT_SHA or gate(False, f"b2_draft.jsonl sha {sha16(draft_raw)} != pinned {DRAFT_SHA}")
    cands = [json.loads(l) for l in cand_raw.decode().splitlines() if l.strip()]
    drafts = [json.loads(l) for l in draft_raw.decode().splitlines() if l.strip()]
    gate(len(cands) == 80 and len(drafts) == 80, "expected 80 rows in both files")
    cids_c = [r["convo_id"] for r in cands]
    cids_d = [r["convo_id"] for r in drafts]
    gate(cids_c == sorted(cids_c), "candidates not convo_id-sorted")
    gate(cids_c == cids_d, "candidates/b2_draft convo_id order mismatch")
    draft_by_id = {r["convo_id"]: r for r in drafts}

    # ---------- Gate 2: candidates <-> b2_draft integrity ----------
    for r in cands:
        d = draft_by_id[r["convo_id"]]
        u = d["b2_unit"]
        gate(list(u.keys()) == B2_SCHEMA, f"{r['convo_id']}: draft unit key order {list(u.keys())} != frozen {B2_SCHEMA}")
        gate(list(u["receipt"].keys()) == RECEIPT_SCHEMA, f"{r['convo_id']}: receipt key order {list(u['receipt'].keys())} != frozen")
        gate(isinstance(u["what_worked"], list) and all(isinstance(x, str) for x in u["what_worked"]),
             f"{r['convo_id']}: what_worked not a list of str")
        # what_worked == the B1 trace (machine check, 80/80 expected)
        ww = u["what_worked"]
        b1_trace = r["b1"].split(" ") if r["b1"] else []
        gate(ww == b1_trace, f"{r['convo_id']}: what_worked {ww} != B1 trace {b1_trace}")
        rc = u["receipt"]
        for k in ("convo_id", "flow", "subflow"):
            gate(rc[k] == r[k], f"{r['convo_id']}: receipt.{k} {rc[k]!r} != candidate row {r[k]!r}")
        gate(rc["corpus"] == "abcd_v1.1", f"{r['convo_id']}: receipt.corpus {rc['corpus']!r}")

    # ---------- Gate 5 (early): frozen token counter recomputation ----------
    for d in drafts:
        u = d["b2_unit"]
        recompute = len(json.dumps(u).split())
        gate(recompute == d["n_tokens_b2"],
             f"{d['convo_id']}: frozen-counter recompute {recompute} != draft n_tokens_b2 {d['n_tokens_b2']}")

    # ---------- Gate 3: binding layer (blind passes) ----------
    cand_map = json.load(open(f"{m2}/judge/binding/candidate_mapping.json"))["mapping"]
    pass1_input = load_lines(f"{m2}/judge/binding/pass1_input.jsonl")
    pass2_input = load_lines(f"{m2}/judge/binding/pass2_input.jsonl")
    gate(len(pass1_input) == 240 and len(pass2_input) == 240, "expected 240 items per pass")
    gate([i["item_id"] for i in pass1_input] != [i["item_id"] for i in pass2_input],
         "pass1/pass2 order must differ (frozen protocol)")
    pass1, pass2 = load_lines(pass1_path), load_lines(pass2_path)
    gate([r["item_id"] for r in pass1] == [i["item_id"] for i in pass1_input], "pass1 answers: order != input order")
    gate([r["item_id"] for r in pass2] == [i["item_id"] for i in pass2_input], "pass2 answers: order != input order")
    for pno, rows, inp in ((1, pass1, pass1_input), (2, pass2, pass2_input)):
        seen = set()
        for r, i in zip(rows, inp):
            gate(set(r.keys()) == {"item_id", "pass", "q1", "q2", "q3"}, f"pass{pno}: fields {sorted(r.keys())}")
            gate(r["pass"] == pno, f"pass{pno}: row pass field {r['pass']}")
            for k in ("q1", "q2", "q3"):
                gate(isinstance(r[k], str) and r[k].strip(), f"pass{pno} {r['item_id']}: empty {k}")
            gate(r["item_id"] not in seen, f"pass{pno}: duplicate item_id {r['item_id']}")
            seen.add(r["item_id"])
        gate(seen == {i["item_id"] for i in inp}, f"pass{pno}: item_id coverage mismatch")
    pass1_by_id = {r["item_id"]: r for r in pass1}
    pass2_by_id = {r["item_id"]: r for r in pass2}
    # item_id|codename -> (convo_id, candidate); codenames must match the input files
    for rows, inp in ((pass1, pass1_input), (pass2, pass2_input)):
        for r, i in zip(rows, inp):
            key = f"{r['item_id']}|{i['codename']}"
            gate(key in cand_map, f"unknown blind item {key}")

    # ---------- Gate 4: scoring answers vs scoring layer ----------
    conv_map_file = json.load(open(f"{m2}/judge/scoring/convo_mapping.json"))
    flat = conv_map_file["candidate_codename -> {convo_id, candidate}"]   # 240 slots
    code_to_cid = conv_map_file["convo_codename -> convo_id"]             # 80 codes
    gate(len(flat) == 240 and len(code_to_cid) == 80, "scoring mapping must cover 80 convos x 3")
    # every (convo_id, candidate) exactly once
    pairs = {(v["convo_id"], v["candidate"]) for v in flat.values()}
    gate(len(pairs) == 240, "candidate slots must be unique per (convo, candidate)")
    gate(all(code_to_cid[c.split("|", 1)[0]] == v["convo_id"] for c, v in flat.items()),
         "convo_codename <-> candidate slot mapping inconsistent")
    scoring_input = load_lines(f"{m2}/judge/scoring/scoring_input.jsonl")
    gate(len(scoring_input) == 80, "expected 80 scoring items")
    gate({it["convo_codename"] for it in scoring_input} == set(code_to_cid),
         "scoring input convo_codename set != the committed mapping set")
    for it in scoring_input:
        row_cands = {c["codename"] for c in it["candidates"]}
        map_cands = {c.split("|", 1)[1] for c in flat if c.startswith(it["convo_codename"] + "|")}
        gate(row_cands == map_cands, f"{it['convo_codename']}: input candidate codenames != mapping")
    scoring = load_lines(scoring_path)
    gate([r["convo_codename"] for r in scoring] == [it["convo_codename"] for it in scoring_input],
         "scoring answers: convo_codename order != input order")
    sc_by_code = {}
    for r in scoring:
        gate(set(r.keys()) == {"convo_codename", "r1", "r2", "r3", "scores"}, f"scoring: fields {sorted(r.keys())}")
        for k in ("r1", "r2", "r3"):
            gate(isinstance(r[k], str) and r[k].strip(), f"scoring {r['convo_codename']}: empty {k}")
        row_cands = {c["codename"] for c in next(it for it in scoring_input
                                                 if it["convo_codename"] == r["convo_codename"])["candidates"]}
        gate(set(r["scores"].keys()) == row_cands and len(r["scores"]) == 3,
             f"scoring {r['convo_codename']}: must score exactly the 3 candidate codenames of the row")
        for cname, sc in r["scores"].items():
            gate(set(sc.keys()) == {"s1", "s2", "s3"}, f"scoring {r['convo_codename']} {cname}: {sorted(sc.keys())}")
            gate(sc["s1"] in (0, 0.5, 1) and sc["s2"] in (0, 0.5, 1) and sc["s3"] in (0, 0.25, 0.5, 1),
                 f"scoring {r['convo_codename']} {cname}: non-frozen score values {sc}")
        sc_by_code[r["convo_codename"]] = r

    # sample.jsonl cross-check (cheap, pinned)
    sample_raw = open(f"{m2}/sample.jsonl", "rb").read()
    gate(sha16(sample_raw) == SAMPLE_SHA, f"sample.jsonl sha {sha16(sample_raw)} != pinned {SAMPLE_SHA}")
    sample_by_id = {r["convo_id"]: r for r in load_lines(f"{m2}/sample.jsonl")}
    for r in cands:
        s = sample_by_id[r["convo_id"]]
        gate(r["flow"] == s["flow"] and r["subflow"] == s["subflow"],
             f"{r['convo_id']}: flow/subflow mismatch vs frozen sample")
        gate(r["n_tokens_b0"] == s["n_tokens_b0"], f"{r['convo_id']}: n_tokens_b0 mismatch vs frozen sample")

    # ---------------- assemble per-convo table ----------------
    code_of = {}  # (convo_id, candidate) -> candidate codename
    for c, v in flat.items():
        code_of[(v["convo_id"], v["candidate"])] = c.split("|", 1)[1]

    def val(sc):
        return (sc["s1"] + sc["s2"] + sc["s3"]) / 3

    rows = []
    for r in cands:
        cid = r["convo_id"]
        code = next(cc for cc, ccid in code_to_cid.items() if ccid == cid)
        sr = sc_by_code[code]
        sc = {}
        for cand in ("b0", "b1", "b2"):
            s = sr["scores"][code_of[(cid, cand)]]
            sc[cand] = {"s1": s["s1"], "s2": s["s2"], "s3": s["s3"], "value": round(val(s), 6)}
        toks = {"b0": r["n_tokens_b0"], "b1": r["n_tokens_b1"], "b2": draft_by_id[cid]["n_tokens_b2"]}
        v_ok = sc["b2"]["value"] >= 0.8 * sc["b0"]["value"] - 1e-12
        t_ok = toks["b2"] <= toks["b0"] / 10
        b1_v_ok = sc["b1"]["value"] >= 0.8 * sc["b0"]["value"] - 1e-12
        b1_t_ok = toks["b1"] <= toks["b0"] / 10
        rows.append({
            "convo_id": cid, "flow": r["flow"], "subflow": r["subflow"],
            "n_action_turns": r["n_action_turns"],
            "tokens": toks,
            "value_b0": sc["b0"]["value"], "value_b1": sc["b1"]["value"], "value_b2": sc["b2"]["value"],
            "per_item_scores": {c: {k: sc[c][k] for k in ("s1", "s2", "s3")} for c in ("b0", "b1", "b2")},
            "value_bar": v_ok, "token_bar": t_ok, "per_convo_bar": v_ok and t_ok,
            "b1_value_bar": b1_v_ok, "b1_token_bar": b1_t_ok,
        })

    # ---------------- structural finding (token half, frozen schema) -------
    empty_floor = len(json.dumps(
        {"problem_shape": None, "constraint": None, "unlock": None,
         "what_worked": [], "receipt": {"corpus": "abcd_v1.1", "convo_id": 0,
                                        "flow": "", "subflow": "", "event_span": None,
                                        "scope": None, "confidence": None}}).split())
    gate(empty_floor == 23, f"empty-unit floor {empty_floor} != 23 (frozen schema fact)")
    n_floor_blocked = sum(1 for x in rows if empty_floor > x["tokens"]["b0"] / 10)
    n_floor_reachable = len(rows) - n_floor_blocked
    sum_b0 = sum(x["tokens"]["b0"] for x in rows)
    sum_b1 = sum(x["tokens"]["b1"] for x in rows)
    sum_b2 = sum(x["tokens"]["b2"] for x in rows)
    b0_median = statistics.median(x["tokens"]["b0"] for x in rows)
    b0_max = max(x["tokens"]["b0"] for x in rows)
    n_draft_token_pass = sum(1 for x in rows if x["token_bar"])
    structural = {
        "empty_unit_floor_tokens": empty_floor,
        "per_convo_floor_blocked_count": n_floor_blocked,
        "per_convo_floor_blocked": f"{n_floor_blocked}/{len(rows)} convos structurally impossible: floor {empty_floor} > tokens(B0)/10 (median B0 {b0_median:.0f} -> allowance {b0_median / 10:.1f}; no content-bearing unit fits)",
        "per_convo_floor_reachable_in_principle": (f"{n_floor_reachable}/{len(rows)} convos have an allowance >= {empty_floor} (max B0 {b0_max} -> {b0_max / 10:.1f}), "
                                                    f"but only a unit AT or BELOW the empty floor (judgment fields hollowed) could pass; "
                                                    f"the measured draft passes {n_draft_token_pass}/{len(rows)}"),
        "aggregate_ratio_floor": round(empty_floor * 80 / sum_b0, 6),
        "aggregate_ratio_floor_note": f"23*80/{sum_b0}",
        "verdict": ("the token half of the frozen bar is UNREACHABLE as a pass of the round: "
                    "the aggregate-ratio floor (empty unit on every row) exceeds 0.1, so the round "
                    "criterion 2 fails no matter how the units are drafted; per-convo, "
                    f"{n_floor_blocked}/80 convos are structurally impossible. This is a property "
                    "of the frozen schema + frozen counter + frozen sample, independent of drafting "
                    "effort — a structural finding, reported per D18, never negotiated. The value "
                    "half is the judge's measurement."),
        "doc_correction": ("arithmetic slips corrected at join (measured from the pinned rows; both "
                           "leave the structural finding unchanged): (1) the quoted 'B0 sum 13,396' "
                           "in B2-DRAFT-NOTES.md s2 and lead 5449935167 s3 is off — the measured B0 "
                           f"sum over the 80 pinned rows is {sum_b0} (candidates/sample meta total: "
                           f"{sum_b0}); the aggregate floor is 23*80/{sum_b0} = "
                           f"{round(empty_floor * 80 / sum_b0, 4)}, not 0.137 (which derives from the "
                           "slipped total); (2) 'exceeds tokens(B0)/10 for all 80 convos' is the "
                           f"AGGREGATE floor's property — per-convo the floor exceeds the allowance on "
                           f"{n_floor_blocked}/80 (median B0 187 -> 18.7; max B0 417 -> 41.7, so "
                           f"{n_floor_reachable} convos' allowances reach the floor). Both floors "
                           "exceed 0.1; a pass requires BOTH halves."),
    }

    # ---------------- round verdict (frozen bar) ----------------------------
    n_pass = sum(1 for x in rows if x["per_convo_bar"])
    n_v = sum(1 for x in rows if x["value_bar"])
    n_t = sum(1 for x in rows if x["token_bar"])
    agg_ratio = sum_b2 / sum_b0
    share = n_pass / 80
    v1 = share >= 0.70
    v2 = agg_ratio <= 0.1
    round_verdict = {
        "per_convo_pass": f"{n_pass}/80 = {frac(n_pass, 80)}",
        "per_convo_share": share,
        "aggregate_token_ratio": round(agg_ratio, 6),
        "value_half_pass_convo_count": f"{n_v}/80",
        "token_half_pass_convo_count": f"{n_t}/80",
        "criterion_1_share_ge_0_70": v1,
        "criterion_2_aggregate_le_0_1": v2,
        "round_pass": v1 and v2,
        "verdict_line": (f"ROUND {'PASSES' if (v1 and v2) else 'FAILS'} the frozen bar: "
                         f"per-convo bar {n_pass}/80 = {pct(share)} (criterion: >= 70%); "
                         f"aggregate token ratio {round(agg_ratio, 4)} (criterion: <= 0.1). "
                         f"Value half met by {n_v}/80; token half met by {n_t}/80 "
                         f"(structural finding, see structural_token_half)."),
        "honesty_clause": HONESTY,
    }

    # ---------------- B1-vs-B2 falsification -------------------------------
    n_b1v = sum(1 for x in rows if x["b1_value_bar"])
    n_b1t = sum(1 for x in rows if x["b1_token_bar"])
    fals = {
        "rule": BAR["falsification"],
        "b1_value_half_share": f"{n_b1v}/80 = {frac(n_b1v, 80)}",
        "b1_token_half_share": f"{n_b1t}/80 = {frac(n_b1t, 80)}",
        "mean_value_b0": round(sum(x["value_b0"] for x in rows) / 80, 6),
        "mean_value_b1": round(sum(x["value_b1"] for x in rows) / 80, 6),
        "mean_value_b2": round(sum(x["value_b2"] for x in rows) / 80, 6),
        "b1_collapses_unit": n_b1v >= 56,
        "collapse_rule_operational": "collapse iff B1 meets value(B1) >= 0.8 x value(B0) on >= 70% of the 80 convos (the round's own >=70% convention applied to B1's identical scoring)",
        "outcome": "",
    }
    if n_b1v >= 56:
        fals["outcome"] = (f"COLLAPSE TRIGGERED — B1 (action trace) alone meets the 0.8 value bar on "
                           f"{n_b1v}/80 convos (>= 70%, the round's own convention); the pre-registered "
                           "collapse applies: the unit reduces to trace + label — a finding, not a failure")
    else:
        if fals["mean_value_b2"] >= 0.8 * fals["mean_value_b0"]:
            tail = "B2 carries the value (mean >= 0.8 x B0)"
        else:
            tail = ("NEITHER candidate carries >= 80% of B0's value on the mean — the unit's "
                    "value claim is not met (a finding, D18)")
        fals["outcome"] = (f"NO COLLAPSE — B1 (action trace) meets the 0.8 value bar on only "
                           f"{n_b1v}/80 convos (< 70%); {tail} "
                           "(adjudicated per lead 5449935167 s4 on the measured numbers)")

    # ---------------- per-field loss ledger --------------------------------
    def ledger(a, b):
        L = {}
        for f in ("s1", "s2", "s3"):
            loss = sum(x["per_item_scores"][a][f] - x["per_item_scores"][b][f] for x in rows)
            L[f] = {"n_pos": sum(1 for x in rows if x["per_item_scores"][a][f] - x["per_item_scores"][b][f] > 0),
                    "total_loss": loss, "mean_loss": round(loss / 80, 6),
                    "mean_loss_display": f"{loss}/80 = {frac(loss, 80)}"}
        L["value"] = {"n_pos": sum(1 for x in rows if x[f"value_{a}"] - x[f"value_{b}"] > 0),
                      "total_loss": round(sum(x[f"value_{a}"] - x[f"value_{b}"] for x in rows), 6),
                      "mean_loss": round(sum(x[f"value_{a}"] - x[f"value_{b}"] for x in rows) / 80, 6)}
        return L

    loss_ledger = {
        "definition": "loss(field) = mean over the 80 convos of score(field, B0) - score(field, candidate); 'what is lost per field when the transcript drops' (frozen contract)",
        "b2_vs_b0": ledger("b0", "b2"),
        "b1_vs_b0": ledger("b0", "b1"),
    }

    # ---------------- two-pass agreement (blind passes) ---------------------
    # NOTE: the two passes present the SAME items in DIFFERENT orders (frozen
    # protocol), so pair rows by item_id — never positionally.
    pass2_input_by_id = {i["item_id"]: i for i in pass2_input}
    gate(set(pass2_input_by_id) == {i["item_id"] for i in pass1_input},
         "pass1/pass2 item_id sets must be identical")
    n_iq_agree = n_iq_total = 0
    conv_iq = {cid: [0, 0] for cid in cids_c}
    for it1 in pass1_input:
        a1 = pass1_by_id[it1["item_id"]]
        a2 = pass2_by_id[it1["item_id"]]
        key = f"{it1['item_id']}|{it1['codename']}"
        conv = cand_map[key]["convo_id"]
        gate(pass2_input_by_id[it1["item_id"]]["codename"] == it1["codename"],
             f"{it1['item_id']}: codename differs between passes")
        for q in ("q1", "q2", "q3"):
            n_iq_total += 1
            conv_iq[conv][1] += 1
            if norm(a1[q]) == norm(a2[q]):
                n_iq_agree += 1
                conv_iq[conv][0] += 1
    convs_fully = sum(1 for v in conv_iq.values() if v[0] == v[1])
    n_items = sum(1 for it in pass1_input
                  if all(norm(pass1_by_id[it["item_id"]][q]) == norm(pass2_by_id[it["item_id"]][q])
                         for q in ("q1", "q2", "q3")))
    rate = n_iq_agree / n_iq_total
    agreement = {
        "definition": ("exact string match after lowercasing + whitespace collapse, per "
                       "(item, question), between blind pass 1 and pass 2 (both passes blind, "
                       "fresh staged context, different order — PROTOCOL-m2-blind.md)"),
        "item_questions_total": n_iq_total,
        "item_questions_agree": n_iq_agree,
        "agreement_rate": round(rate, 6),
        "agreement_display": f"{n_iq_agree}/{n_iq_total} = {frac(n_iq_agree, n_iq_total)}",
        "per_convo_all_agree": f"{convs_fully}/80",
        "items_all_questions_agree": f"{n_items}/240",
        "disagreement_gt_15pct": rate < 0.85,
        "flag": ("DISAGREEMENT > 15%: per the frozen protocol, a 20-item sample goes to the "
                 "founder (never the whole set)") if rate < 0.85 else "disagreement <= 15%: no founder-sample trigger",
        "honesty_clause": "self-consistency floor, NOT human inter-rater agreement",
    }

    # ---------------- results JSON ------------------------------------------
    results = {
        "artifact": "research/phase2/m2/m2_results.json",
        "round": "R2 (M2 extraction) — join per GH #6 5449115746 s4 item 4 (frozen contract)",
        "created": DATE,
        "dry_run": dry_run,
        "frozen_inputs": {
            "candidates": {"path": "research/phase2/m2/candidates.jsonl", "sha256_16": CANDIDATES_SHA, "main": "d8a8f33 (via PR #22 @601c310)"},
            "b2_draft": {"path": "research/phase2/m2/b2_draft.jsonl", "sha256_16": DRAFT_SHA, "main": "d8a8f33 (PR #23)"},
            "sample": {"path": "research/phase2/m2/sample.jsonl", "sha256_16": SAMPLE_SHA, "main": "4d68187 (PR #21, D22)"},
        },
        "judge_inputs": {
            "pass1": {"path": pass1_path, "sha256_16": sha16(open(pass1_path, "rb").read()), "items": 240},
            "pass2": {"path": pass2_path, "sha256_16": sha16(open(pass2_path, "rb").read()), "items": 240},
            "scoring": {"path": scoring_path, "sha256_16": sha16(open(scoring_path, "rb").read()), "items": 80},
            "protocols": ["research/phase2/m2/judge/binding/PROTOCOL-m2-blind.md", "research/phase2/m2/judge/scoring/PROTOCOL-m2-scoring.md"],
            "note": "judge files are evaluation's output; pinned here by sha so the join is a pure function of them (re-runnable, auditable)",
        },
        "frozen_bar": BAR,
        "structural_token_half": structural,
        "aggregates": {
            "tokens": {"b0": sum_b0, "b1": sum_b1, "b2": sum_b2,
                       "ratio_b1_b0": round(sum_b1 / sum_b0, 6),
                       "ratio_b2_b0": round(sum_b2 / sum_b0, 6)},
            "value_mean": {"b0": fals["mean_value_b0"], "b1": fals["mean_value_b1"], "b2": fals["mean_value_b2"]},
        },
        "per_convo": rows,
        "round_verdict": round_verdict,
        "falsification_b1_vs_b2": fals,
        "per_field_loss_ledger": loss_ledger,
        "two_pass_agreement": agreement,
        "honesty_clause": HONESTY,
        "re_run_contract": ("README.md (this directory): pinned inputs verified by sha on every run; "
                            "n_tokens_b2 recomputed on the draft unit with the frozen counter; "
                            "deterministic output (byte-identical on re-run for the same inputs)."),
    }

    # ---------------- report markdown ---------------------------------------
    rp = []
    ap = rp.append
    ap("# M2 results (R2) — the join")
    if dry_run:
        ap("")
        ap("> **SYNTHETIC DRY RUN — NOT REAL RESULTS.** These artifacts were produced by the join")
        ap("> selftest on synthetic judge outputs to prove the pipeline. The real join runs the")
        ap("> same command on evaluation's judge files; its output replaces this file. Do not")
        ap("> quote these numbers. Do not commit a dry-run artifact as the round's result.")
    ap("")
    ap(f"**Round:** R2 (M2 extraction) · join per GH #6 `5449115746` s4 item 4 (frozen contract). "
       f"Created {DATE} by `join_m2.py`.")
    ap("")
    ap("**Question:** does the structured experience record (B2) preserve >= 80% of the")
    ap("transcript's rubric value at <= 1/10 of its token count? (frozen D18 bar; collapse rule")
    ap("pre-registered: if B1 (the action trace) alone reaches >= 80%, the unit collapses to")
    ap("trace + label.)")
    ap("")
    ap("## 1. Inputs (pinned, verified by sha256:16 at join time)")
    ap("")
    ap("| input | sha256:16 | state |")
    ap("|---|---|---|")
    ap(f"| `candidates.jsonl` (B0/B1 renders + frozen token counts) | `{CANDIDATES_SHA}` | PR #22, main @601c310 |")
    ap(f"| `b2_draft.jsonl` (the 80 B2 units) | `{DRAFT_SHA}` | PR #23, main @d8a8f33 |")
    ap(f"| `sample.jsonl` (frozen 80-convo sample) | `{SAMPLE_SHA}` | PR #21 (D22) |")
    ap(f"| blind pass1 answers | `{results['judge_inputs']['pass1']['sha256_16']}` | evaluation, 240 items |")
    ap(f"| blind pass2 answers | `{results['judge_inputs']['pass2']['sha256_16']}` | evaluation, 240 items |")
    ap(f"| scoring answers | `{results['judge_inputs']['scoring']['sha256_16']}` | evaluation, 80 rows |")
    ap("")
    ap("`n_tokens_b2` was recomputed on each draft unit with the frozen counter")
    ap("(whitespace-split of `json.dumps(unit)`, default separators) — 80/80 equal to the draft's")
    ap("stored value (gate 5 of the join).")
    ap("")
    ap("## 2. The frozen bar (never tuned — D18)")
    ap("")
    ap(f"- **Per convo:** value(B2) >= 0.8 x value(B0) **AND** tokens(B2) <= tokens(B0)/10.")
    ap(f"- **Round passes iff** >= 70% of the 80 convos meet the per-convo criterion **AND** the")
    ap(f"  aggregate token ratio sum(tokens(B2))/sum(tokens(B0)) <= 0.1.")
    ap(f"- value(candidate) = (s1+s2+s3)/3 under the frozen scoring rubric; B0 is scored under")
    ap(f"  identical treatment — the ceiling's value is MEASURED, not assumed 1.0.")
    ap("")
    ap("### The token half — structural finding (frozen schema, reported not negotiated)")
    ap("")
    ap(f"The empty-unit schema floor is **{empty_floor} tokens** under the frozen counter. Per-convo, the")
    ap(f"floor exceeds `tokens(B0)/10` on **{n_floor_blocked}/80** convos (median B0 {b0_median:.0f} -> allowance")
    ap(f"{b0_median / 10:.1f}; only a unit with its judgment fields hollowed could pass those, and the draft passes")
    ap(f"{n_draft_token_pass}/80). The other {n_floor_reachable}/80 convos' allowances reach the floor (max B0 {b0_max} -> {b0_max / 10:.1f}),")
    ap(f"but the **aggregate-ratio floor** — the empty unit on all 80 rows — is 23x80/{sum_b0} = "
       f"**{round(empty_floor * 80 / sum_b0, 4)} > 0.1**,")
    ap("so round criterion 2 (aggregate ratio <= 0.1) fails **no matter how the units are drafted**. The")
    ap("token half is unreachable as a pass of the round — a property of frozen schema + counter +")
    ap("sample, independent of drafting effort. **The value half is the judge's measurement; the token")
    ap("half reports as this structural finding.** A missed bar is the finding (D18) — the bar")
    ap("was not negotiated after seeing results.")
    ap("")
    ap(f"*Doc corrections (arithmetic slips in B2-DRAFT-NOTES.md s2 / lead 5449935167 s3, measured from the")
    ap(f"pinned rows at join; both leave the structural finding unchanged): (1) the quoted 'B0 sum 13,396' is")
    ap(f"off — the measured B0 sum over the 80 pinned rows is **{sum_b0}** (candidates/sample meta total: {sum_b0});")
    ap(f"the aggregate floor is {round(empty_floor * 80 / sum_b0, 4)} (vs 0.137 from the slipped total). (2) 'exceeds tokens(B0)/10 for")
    ap(f"all 80 convos' is the AGGREGATE floor's property — per-convo the floor exceeds the allowance on")
    ap(f"{n_floor_blocked}/80, not all 80. Both floors exceed 0.1; a pass requires BOTH halves.*")
    ap("")
    ap("## 3. Per-convo table (80 rows; value = (s1+s2+s3)/3; tokens = frozen counter)")
    ap("")
    ap("| convo_id | flow | subflow | tok B0/B1/B2 | value B0/B1/B2 | per-convo bar |")
    ap("|---|---|---|---|---|---|")
    for x in rows:
        t = x["tokens"]
        bar = "PASS" if x["per_convo_bar"] else "FAIL"
        v = f"{x['value_b0']:.3f} / {x['value_b1']:.3f} / {x['value_b2']:.3f}"
        ap(f"| {x['convo_id']} | {x['flow']} | {x['subflow']} | {t['b0']}/{t['b1']}/{t['b2']} | {v} | {bar} (v {'ok' if x['value_bar'] else 'no'}, t {'ok' if x['token_bar'] else 'no'}) |")
    ap("")
    ap(f"- per-convo bar: **{n_pass}/80** (value half {n_v}/80; token half {n_t}/80 — structural).")
    ap(f"- aggregates: tokens B0/B1/B2 = {sum_b0}/{sum_b1}/{sum_b2}; ratio B1/B0 = {round(sum_b1 / sum_b0, 4)}; "
       f"ratio B2/B0 = {round(sum_b2 / sum_b0, 4)}.")
    ap(f"- mean value: B0 {fals['mean_value_b0']:.4f} / B1 {fals['mean_value_b1']:.4f} / B2 {fals['mean_value_b2']:.4f}.")
    ap("")
    ap("## 4. Round verdict (frozen bar)")
    ap("")
    ap(f"**{round_verdict['verdict_line']}**")
    ap("")
    ap("## 5. B1-vs-B2 falsification outcome")
    ap("")
    ap(f"B1 (action trace, scored identically): value-half share **{fals['b1_value_half_share']}**, "
       f"token-half share {fals['b1_token_half_share']}.")
    ap("")
    ap(f"**{fals['outcome']}**")
    ap("")
    ap("## 6. Per-field loss ledger (what is lost per field when the transcript drops)")
    ap("")
    ap("Loss = mean over the 80 convos of score(field, B0) - score(field, candidate).")
    ap("")
    ap("| field | B2 vs B0 (n convos w/ loss, total/80, mean) | B1 vs B0 (n, total/80, mean) |")
    ap("|---|---|---|")
    names = {"s1": "Q1 problem (intent + structure)", "s2": "Q2 binding constraint", "s3": "Q3 what worked (in order)"}
    for f in ("s1", "s2", "s3", "value"):
        l2, l1 = loss_ledger["b2_vs_b0"][f], loss_ledger["b1_vs_b0"][f]
        def cell(l):
            tot = l["total_loss"] if f != "value" else round(l["total_loss"], 4)
            mean = l["mean_loss"] if f != "value" else round(l["mean_loss"], 4)
            return f"{l['n_pos']}, {tot}/80, {mean}"
        ap(f"| {names.get(f, 'value = (s1+s2+s3)/3')} | {cell(l2)} | {cell(l1)} |")
    ap("")
    ap("## 7. Two-pass agreement (blind answering passes)")
    ap("")
    ap(f"**{agreement['agreement_display']}** of item-questions agree across passes "
       f"({agreement['definition']}); per-convo all-questions-agree {agreement['per_convo_all_agree']}; "
       f"items with all 3 questions agreeing {agreement['items_all_questions_agree']}.")
    ap("")
    ap(f"{agreement['flag']}.")
    ap("")
    ap(f"> {agreement['honesty_clause']}.")
    ap("")
    ap("## 8. Vocab guard (note for the report — so the D11 record does not resurface)")
    ap("")
    ap("`what_worked` uses the canonical 30-name ontology vocab. Vs that vocab the measured value")
    ap("on this corpus is **0/30 unmapped** (286/286 sample action turns; guard intact, never")
    ap("fired on this corpus). The R1-era '10 unmapped' was vs guidelines.json Title-Case button")
    ap("names — a different denominator. **0 is the number.**")
    ap("")
    ap("## 9. Honesty clause (rides with every number in this report)")
    ap("")
    ap(f"> {HONESTY}")
    ap("")
    ap("## 10. Re-run contract")
    ap("")
    ap("See `README.md` in this directory: pinned inputs verified by sha on every run; the join")
    ap("is one command, deterministic, and a pure function of the judge files (recorded by sha).")

    out = "\n".join(rp) + "\n"
    with open(results_path, "w") as f:
        f.write(json.dumps(results, indent=1) + "\n")
    with open(report_path, "w") as f:
        f.write(out)

    # ---------------- console summary ---------------------------------------
    print("join_m2 complete" + ("  [DRY RUN — synthetic judge inputs]" if dry_run else ""))
    print(f"  results: {results_path}")
    print(f"  report:  {report_path}")
    print(f"  per-convo bar: {n_pass}/80 | value half {n_v}/80 | token half {n_t}/80 (structural 0/80)")
    print(f"  aggregate token ratio: {agg_ratio:.4f} (criterion <= 0.1)")
    print(f"  round verdict: {'PASS' if round_verdict['round_pass'] else 'FAIL'} — {round_verdict['verdict_line'][:120]}")
    print(f"  falsification: {fals['outcome'][:120]}")
    print(f"  two-pass agreement: {agreement['agreement_display']} (flag: {agreement['disagreement_gt_15pct']})")
    return results


def main():
    ap = argparse.ArgumentParser(
        description="R2/M2 join: pinned candidates+b2_draft x judge numbers -> m2_results.json + m2_report.md")
    ap.add_argument("--m2", default="research/phase2/m2")
    ap.add_argument("--pass1", required=True, help="blind pass-1 answers jsonl")
    ap.add_argument("--pass2", required=True, help="blind pass-2 answers jsonl")
    ap.add_argument("--scoring", required=True, help="scoring answers jsonl")
    ap.add_argument("--out-dir", default=None, help="default: the m2 dir")
    ap.add_argument("--results", default="m2_results.json")
    ap.add_argument("--report", default="m2_report.md")
    ap.add_argument("--dry-run", action="store_true",
                    help="mark artifacts SYNTHETIC-DRY-RUN (selftest only; never commit as real results)")
    a = ap.parse_args()
    out_dir = a.out_dir or a.m2
    try:
        run(a.m2, a.pass1, a.pass2, a.scoring, out_dir,
            f"{out_dir}/{a.results}", f"{out_dir}/{a.report}", a.dry_run)
    except Fail as e:
        print(f"JOIN GATE FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
