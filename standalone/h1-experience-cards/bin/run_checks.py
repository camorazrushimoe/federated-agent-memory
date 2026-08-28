#!/usr/bin/env python3
"""run_checks.py — the Layer-1 contract harness (CHECKS.md).

Every id in CHECKS.md is implemented as a boolean check on run-dir files.
HARD failures abort the run: the harness exits non-zero listing them, and
run_experiment.py refuses to publish numbers from a failed run.

Usage (called by run_experiment.py after each phase):
  python bin/run_checks.py --run-dir runs/<id> --phase ingest|extract|cluster|serve|eval|all
      [--stage S0|S1|S2] [--fixtures fixtures] [--model M] [--base-url U] [--api-key K]

checks.json row: {check_id, step, hard, passed, observed, expected, note}.
Every id MUST appear in the final checks.json — a missing id is a failure.

Some checks need dedicated mini-runs (fixtures, controls). They run in
<run-dir>/checks_work/ using the SAME bin/ scripts (replay mode for the
fixtures) — no second copy of pipeline logic. C-EX6 (the §10.1 worked
example) is the only check that makes a live LLM call.
"""

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402

H1_DIR = H.H1_DIR
BIN = os.path.dirname(os.path.abspath(__file__))
README_SHA = {
    "abcd_1000_pool.jsonl": "28b77a32e58932bbf1502d73975972285ec071d03f30c6ac2b5d23cd90a5abbb",
    "abcd_200_holdout.jsonl": "e8f453e17c6c3aa115fb2bd1498a833da383cecdcc650667ac349f903343fe3c",
}

PII_RX = [re.compile(r"\S+@\S+"), re.compile(r"\+?\d[\d\-\s]{7,}\d"),
          re.compile(r"\d{10,}"), re.compile(r"\bcvv\b", re.I),
          re.compile(r"\biban\b", re.I), re.compile(r"\bssn\b", re.I)]


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------


class Ctx:
    def __init__(self, run_dir, stage, fixtures, model, base_url, api_key):
        self.run_dir = run_dir
        self.stage = stage
        self.fixtures = fixtures
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.data = os.path.join(run_dir, "data")
        self.work = os.path.join(run_dir, "checks_work")
        self.manifest = H.load_json(os.path.join(run_dir, "manifest.json")) \
            if os.path.exists(os.path.join(run_dir, "manifest.json")) else {}
        self.cfg = self.manifest.get("config", H.DEFAULTS)
        self.pool_path = (self.manifest.get("inputs", {}).get("pool", {}) or
                          {}).get("path")
        self.holdout_path = (self.manifest.get("inputs", {}).get("holdout")
                             or {}).get("path")
        self.timeline = self.manifest.get("timeline", "compressed")
        self.aps = self.manifest.get("agent_pool_size", 4)
        self.at = self.manifest.get("at")
        self.now = self.manifest.get("now")
        os.makedirs(self.work, exist_ok=True)

    def script(self, name, args, check=True):
        r = subprocess.run([sys.executable, os.path.join(BIN, name)] + args,
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise SystemExit(f"run_checks: {name} failed: {r.stderr[-800:]}")
        return r.stdout.strip(), r.returncode

    def env_args(self):
        out = []
        if self.model:
            out += ["--model", self.model]
        if self.base_url:
            out += ["--base-url", self.base_url]
        if self.api_key:
            out += ["--api-key", self.api_key]
        return out

    def cards(self):
        return H.read_jsonl(os.path.join(self.data, "cards.jsonl"))

    def dialogues(self):
        return H.read_jsonl(os.path.join(self.data, "dialogues.jsonl"))

    def holdout_dialogues(self):
        return H.read_jsonl(os.path.join(self.data, "holdout_dialogues.jsonl"))

    def packets(self):
        p = os.path.join(self.data, "..", "packets", "_served.jsonl")
        return H.read_jsonl(p)


# --------------------------------------------------------------------------
# Check registry
# --------------------------------------------------------------------------

RESULTS = []  # {check_id, step, hard, passed, observed, expected, note}


def record(check_id, step, hard, passed, observed, expected, note=""):
    RESULTS.append({"check_id": check_id, "step": step, "hard": hard,
                    "passed": bool(passed), "observed": observed,
                    "expected": expected, "note": note})


def r_pass(cid, step, hard, observed, expected="", note=""):
    record(cid, step, hard, True, observed, expected, note)


def r_fail(cid, step, hard, observed, expected="", note=""):
    record(cid, step, hard, False, observed, expected, note)


def fixture_check(ctx, fn):
    """Run fn(ctx) which calls r_pass/r_fail; returns nothing."""
    return fn(ctx)


# --------------------------------------------------------------------------
# Static / leakage checks (any phase)
# --------------------------------------------------------------------------


def chk_l3(ctx):
    bad = []
    for fn in sorted(os.listdir(BIN)):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(BIN, fn), encoding="utf-8").read()
        for m in re.finditer(r"^\s*(?:import|from)\s+([\w\.]+)", src, re.M):
            mod = m.group(1).split(".")[0]
            if mod in ("research", "openspec", "federated", "google"):
                bad.append(f"{fn}:{mod}")
    if bad:
        r_fail("C-L3", "leakage", True, bad, "no imports from research/, "
               "openspec/, or any repo package")
    else:
        r_pass("C-L3", "leakage", True, "all imports stdlib or bin/")


def chk_l4(ctx):
    bad = []
    for fn in sorted(os.listdir(BIN)):
        if not fn.endswith(".py"):
            continue
        if fn == "run_checks.py":
            continue  # the harness itself lists the forbidden tokens as
            # check patterns; it is meta-tooling, not pipeline code
        src = open(os.path.join(BIN, fn), encoding="utf-8").read()
        low = src.lower()
        for tok in ("embed", "qdrant", "neo4j", "psycopg", "chromadb",
                    "pinecone", "weaviate", "faiss"):
            if tok in low and f"def {tok}" not in low:
                bad.append(f"{fn}:{tok}")
        if fn != "h1lib.py" and "urllib" in low:
            bad.append(f"{fn}:urllib outside call_llm")
    if bad:
        r_fail("C-L4", "leakage", True, bad, "no embedding/vector/DB/network "
               "except call_llm in h1lib.py")
    else:
        r_pass("C-L4", "leakage", True, "clean", "no forbidden deps")


def chk_l1(ctx):
    data_dir = os.path.join(H1_DIR, "data")
    obs = {}
    ok = True
    for name, want in README_SHA.items():
        p = os.path.join(data_dir, name)
        if not os.path.exists(p):
            ok = False
            obs[name] = "missing"
            continue
        got = H.sha256_file(p)
        obs[name] = got[:16]
        if got != want:
            ok = False
    if ok:
        r_pass("C-L1", "leakage", True, obs, "sha256 matches data/README.md")
    else:
        r_fail("C-L1", "leakage", True, obs,
               "sha256 matches data/README.md table")


def _keys_present(obj, names):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in names:
                found.append(k)
            found += _keys_present(v, names)
    elif isinstance(obj, list):
        for it in obj:
            found += _keys_present(it, names)
    return found


def chk_l2(ctx):
    names = ("unlock", "unlock_guideline", "split")
    bad = []
    for f in ("dialogues.jsonl", "holdout_dialogues.jsonl"):
        p = os.path.join(ctx.data, f)
        if os.path.exists(p):
            for i, row in enumerate(H.read_jsonl(p)):
                hits = _keys_present(row, names)
                if hits:
                    bad.append(f"{f}:{i}:{hits}")
    raw = os.path.join(ctx.run_dir, "raw", "extract")
    if os.path.isdir(raw):
        for fn in sorted(os.listdir(raw)):
            if not fn.endswith(".json"):
                continue
            rec = H.load_json(os.path.join(raw, fn))
            hits = _keys_present(rec.get("request", {}), names)
            if hits:
                bad.append(f"raw/{fn}:{hits}")
    if bad:
        r_fail("C-L2", "leakage", True, bad[:5], "no unlock/unlock_guideline/"
               "split keys reach extract input")
    else:
        r_pass("C-L2", "leakage", True, "clean",
               "ground truth never reaches the model")


def chk_l5(ctx):
    log = os.path.join(ctx.run_dir, "access.log")
    if not os.path.exists(log):
        r_fail("C-L5", "leakage", True, "no access.log",
               "runner access log present")
        return
    lines = open(log, encoding="utf-8").read()
    if ctx.stage == "S2":
        if not ctx.holdout_path:
            r_fail("C-L5", "leakage", True, "holdout_path missing from "
                   "manifest inputs", "S2 run records the holdout path")
            return
        n = lines.count(ctx.holdout_path)
        if n == 1:
            r_pass("C-L5", "leakage", True, f"holdout opened {n}x at S2",
                   "exactly once at S2")
        else:
            r_fail("C-L5", "leakage", True, f"holdout path appears {n}x",
                   "exactly once at S2")
    else:
        n = lines.count(ctx.holdout_path) if ctx.holdout_path else 0
        if n == 0:
            r_pass("C-L5", "leakage", True,
                   f"holdout never opened at {ctx.stage}", "never in S0/S1")
        else:
            r_fail("C-L5", "leakage", True, f"holdout path appears {n}x",
                   "never opened in S0/S1")


# --------------------------------------------------------------------------
# Ingest checks
# --------------------------------------------------------------------------


def chk_in(ctx):
    pool_slice = os.path.join(ctx.data, "pool_slice_raw.jsonl")
    dialogues = ctx.dialogues()
    if not os.path.exists(pool_slice):
        r_fail("C-IN1", "ingest", True, "pool_slice_raw.jsonl missing", "")
        return
    raw_rows = H.read_jsonl(pool_slice)
    # C-IN1: kept + dropped == input rows (dropped re-derived)
    dropped = sum(1 for r in raw_rows
                  if not any(t.get("speaker") == "customer"
                             for t in r.get("turns", [])))
    if len(dialogues) + dropped == len(raw_rows):
        r_pass("C-IN1", "ingest", True,
               f"kept={len(dialogues)} dropped={dropped} rows={len(raw_rows)}",
               "kept + dropped == input rows")
    else:
        r_fail("C-IN1", "ingest", True,
               f"kept={len(dialogues)} dropped={dropped} rows={len(raw_rows)}",
               "kept + dropped == input rows")

    bad_turns = [d["dialogue_id"] for d in dialogues
                 if not any(t["role"] == "customer" for t in d["turns"])]
    if not bad_turns and dropped == sum(
            1 for r in raw_rows if not any(
                t.get("speaker") == "customer" for t in r.get("turns", []))):
        r_pass("C-IN2", "ingest", True, f"kept all have >=1 customer turn, "
               f"{dropped} dropped with 0", "one-customer-turn rule")
    else:
        r_fail("C-IN2", "ingest", True, f"violations: {bad_turns[:3]}",
               "every kept >=1 customer turn; every dropped 0")

    bad = [d["dialogue_id"] for d in dialogues if H.dialogue_ok(d)]
    if not bad:
        r_pass("C-IN3", "ingest", True, "all records pass §3 schema",
               "dialogue_id/tenant_id/vertical/agent_id/channel/closed_at/"
               "turns roles in {customer,agent,tool}")
    else:
        r_fail("C-IN3", "ingest", True, bad[:3], "§3 schema")

    ids = [d["dialogue_id"] for d in dialogues]
    if len(ids) == len(set(ids)):
        r_pass("C-IN4", "ingest", True, f"{len(ids)} unique ids", "unique")
    else:
        r_fail("C-IN4", "ingest", True, f"{len(ids) - len(set(ids))} dups",
               "unique dialogue_id")

    # C-IN5: turn text byte-identical on min(20, n) random dialogues
    random.seed(7)
    sample = random.sample(dialogues, min(20, len(dialogues)))
    raw_by_id = {f"d-{r['chat_id']}": r for r in raw_rows}
    mism = []
    for d in sample:
        raw = raw_by_id.get(d["dialogue_id"])
        if not raw:
            mism.append(f"{d['dialogue_id']}:no raw row")
            continue
        raw_texts = [t["text"] for t in raw["turns"]]
        got_texts = [t["text"] for t in d["turns"]]
        if raw_texts != got_texts:
            mism.append(f"{d['dialogue_id']}:text differs")
    if not mism:
        r_pass("C-IN5", "ingest", True, f"{len(sample)} dialogues "
               "byte-identical", "turn text verbatim, no normalisation")
    else:
        r_fail("C-IN5", "ingest", True, mism[:3], "turn text byte-identical")

    # C-IN6: re-running ingest is byte-identical
    try:
        tmp = os.path.join(ctx.work, "reingest_dialogues.jsonl")
        args = ["--in", pool_slice, "--out", tmp, "--agent-pool-size",
                str(ctx.aps), "--timeline", ctx.timeline,
                "--t0", ctx.cfg.get("t0") or "2026-08-28T00:00:00Z"]
        ctx.script("ingest.py", args)
        if H.sha256_file(tmp) == H.sha256_file(
                os.path.join(ctx.data, "dialogues.jsonl")):
            r_pass("C-IN6", "ingest", True, "byte-identical re-ingest", "")
        else:
            r_fail("C-IN6", "ingest", True, "re-ingest differs",
                   "byte-identical dialogues.jsonl")
    except SystemExit as e:
        r_fail("C-IN6", "ingest", True, str(e), "re-ingest runs")

    # C-IN7 (SOFT): agent distribution within ±20% of uniform
    from collections import Counter
    cnt = Counter(d["agent_id"] for d in dialogues)
    if ctx.aps and cnt:
        per = len(dialogues) / ctx.aps
        off = [f"{a}:{c}" for a, c in sorted(cnt.items())
               if abs(c - per) > 0.2 * per]
        if not off:
            r_pass("C-IN7", "ingest", False,
                   f"agents {dict(cnt)} uniform ±20% of {per:.1f}", "")
        else:
            r_fail("C-IN7", "ingest", False, off,
                   "within ±20% of uniform")
    else:
        r_pass("C-IN7", "ingest", False, "n/a", "no agents")


# --------------------------------------------------------------------------
# Extract checks
# --------------------------------------------------------------------------


def chk_ex(ctx):
    cards = ctx.cards()
    by_id = {c["card_id"]: c for c in cards}
    dialogues = {d["dialogue_id"]: d for d in ctx.dialogues()}
    viol = []
    fresh_viol = []
    for c in cards:
        e = H.validate_card(c)
        if e:
            viol.append(f"{c['card_id']}:{e[:2]}")
        if c["status"] in ("private", "rejected") and c.get(
                "cluster_id") == c.get("card_id"):
            e = H.validate_card(c, fresh=True)
            if e:
                fresh_viol.append(f"{c['card_id']}:{e[:2]}")
    if not viol and not fresh_viol:
        r_pass("C-EX1", "extract", True, f"{len(cards)} cards valid",
               "SPEC §4 schema; fresh state for never-clustered cards")
    else:
        r_fail("C-EX1", "extract", True,
               {"schema": viol[:3], "fresh": fresh_viol[:3]}, "no violations")

    bad = [c["card_id"] for c in cards
           if c["card_id"] != H.card_id_of(
               c["receipt"]["source_dialogue_id"])]
    if not bad:
        r_pass("C-EX2", "extract", True, "all card_ids = c- + sha256[:12]",
               "deterministic card id")
    else:
        r_fail("C-EX2", "extract", True, bad[:3], "card_id == c-+sha256[:12]")

    fld = {"problem_shape_long": 0, "problem_shape_empty": 0,
           "constraint_bad": 0, "unlock_bad": 0, "ww_bad": 0}
    for c in cards:
        if c["status"] == "rejected":
            continue
        w = H.word_count(c["problem_shape"])
        if w == 0:
            fld["problem_shape_empty"] += 1
        if w > 12:
            fld["problem_shape_long"] += 1
        for f in ("constraint", "unlock"):
            v = (c.get(f) or "").strip().lower()
            if v != "none" and H.word_count(v) > 12:
                fld[f + "_bad"] += 1
        ww = c.get("what_worked") or []
        if not (1 <= len(ww) <= 8):
            fld["ww_bad"] += 1
    if sum(fld.values()) == 0:
        r_pass("C-EX3", "extract", True, "all field limits hold",
               "≤12 words / none / 1-8 what_worked")
    else:
        r_fail("C-EX3", "extract", True, fld, "field limits hold")

    grounding = {"problem_shape": 0, "constraint": 0, "unlock": 0}
    g_bad = []
    for c in cards:
        if c["status"] == "rejected":
            continue
        d = dialogues.get(c["receipt"]["source_dialogue_id"])
        if not d:
            g_bad.append(f"{c['card_id']}:no dialogue")
            continue
        text = " ".join(t["text"] for t in d["turns"])
        tw = H.content_words(text)
        for f in ("problem_shape", "constraint", "unlock"):
            v = (c.get(f) or "").strip().lower()
            if v == "none" or not v:
                continue
            if not (H.content_words(v) & tw):
                grounding[f] += 1
                g_bad.append(f"{c['card_id']}:{f} ungrounded")
    if not g_bad:
        r_pass("C-EX4", "extract", True, "every non-none field grounded",
               "≥1 content word (≥5 chars) in source transcript")
    else:
        r_fail("C-EX4", "extract", True,
               {"violations": grounding, "examples": g_bad[:5]},
               "grounding holds")

    pii_bad = []
    for c in cards:
        for f in ("problem_shape", "constraint", "unlock"):
            for rx in PII_RX:
                if rx.search(c.get(f) or ""):
                    pii_bad.append(f"{c['card_id']}:{f}")
        for item in c.get("what_worked") or []:
            for rx in PII_RX:
                if rx.search(item):
                    pii_bad.append(f"{c['card_id']}:ww")
    if not pii_bad:
        r_pass("C-EX5", "extract", True, f"full store scan clean "
               f"({len(cards)} cards)", "no PII patterns in any card field")
    else:
        r_fail("C-EX5", "extract", True, pii_bad[:5], "no PII in card fields")


def chk_ex6(ctx):
    """§10.1 worked example against the LIVE model (the only live check)."""
    try:
        d001 = [x for x in H.read_jsonl(os.path.join(
            ctx.fixtures, "spec10_dialogues.jsonl"))
            if x["dialogue_id"] == "d-001"][0]
        one = os.path.join(ctx.work, "d001.jsonl")
        H.write_jsonl(one, [d001], mode="w")
        cards_p = os.path.join(ctx.work, "d001_cards.jsonl")
        out, rc = ctx.script("extract.py", ["--in", one, "--out", cards_p]
                             + ctx.env_args())
        cards = H.read_jsonl(cards_p)
        if not cards:
            r_fail("C-EX6", "extract", True, "no card produced",
                   "§10.1 card survives extraction")
            return
        c = cards[0]
        allf = " ".join([c.get("problem_shape", ""), c.get("constraint", ""),
                         c.get("unlock", "")] + (c.get("what_worked") or []))
        if "4412" in allf:
            r_fail("C-EX6", "extract", True, "4412 present in a field",
                   "no raw order id in fields (C-EX6)")
        elif c["status"] == "rejected":
            r_fail("C-EX6", "extract", True, "card rejected",
                   "not rejected merely because contains_pii=true")
        else:
            r_pass("C-EX6", "extract", True,
                   {"status": c["status"], "contains_pii": c["contains_pii"],
                    "fields_clean_4412": True},
                   "card survives, 4412 absent, pii alone not a reject")
    except Exception as e:  # noqa: BLE001
        r_fail("C-EX6", "extract", True, str(e), "live extract runs")


def _replay_fixture_extract(ctx, dialogues, name):
    src = os.path.join(ctx.fixtures, dialogues)
    out = os.path.join(ctx.work, f"{name}_cards.jsonl")
    ctx.script("extract.py", ["--in", src, "--out", out, "--replay-dir",
                              os.path.join(ctx.fixtures, "raw_extract"),
                              "--at", ctx.at or "2026-08-28T12:00:00Z"]
               + ctx.env_args())
    return H.read_jsonl(out)


def chk_ex7(ctx):
    cards = _replay_fixture_extract(ctx, "spec10_dialogues.jsonl", "ex7")
    g = [c for c in cards
         if c["receipt"]["source_dialogue_id"] == "d-gift"]
    if g and g[0]["contains_pii"] is False:
        r_pass("C-EX7", "extract", True, "gift card chat: contains_pii=false",
               "bare word 'card' must not set contains_pii")
    else:
        r_fail("C-EX7", "extract", True,
               [c.get("contains_pii") for c in g],
               "contains_pii stays false on 'gift card' transcript")


def chk_ex8(ctx):
    cards = _replay_fixture_extract(ctx, "spec10_dialogues.jsonl", "ex8")
    rej = [c for c in cards if c["status"] == "rejected"]
    rej_ids = {c["receipt"]["source_dialogue_id"] for c in rej}
    bad = []
    for c in rej:
        if not H.card_is_rejected(c):
            bad.append(f"{c['card_id']} rejected outside the rule")
    if rej_ids != {"d-rej1", "d-rej2"}:
        bad.append(f"unexpected rejected set {rej_ids}")
    pii = [c for c in cards if c["receipt"]["source_dialogue_id"] == "d-pii"]
    if pii and pii[0]["status"] == "rejected":
        bad.append("d-pii (contains_pii=true) must NOT be rejected")
    if not bad:
        r_pass("C-EX8", "extract", True,
               f"rejected={sorted(rej_ids)}; d-pii accepted",
               "rejection only per the post-scrub rule")
    else:
        r_fail("C-EX8", "extract", True, bad, "rejection rule")


def chk_ex9(ctx):
    cards = _replay_fixture_extract(ctx, "spec10_dialogues.jsonl", "ex9a")
    ids = [c["card_id"] for c in cards]
    if len(ids) != len(set(ids)):
        r_fail("C-EX9", "extract", True, "duplicate card_ids",
               "upsert by card_id")
        return
    # cluster, then re-extract: merged card must be skipped, not overwritten
    dlg = os.path.join(ctx.fixtures, "spec10_dialogues.jsonl")
    cards_p = os.path.join(ctx.work, "ex9a_cards.jsonl")
    ctx.script("cluster.py", ["--cards", cards_p, "--dialogues", dlg,
                              "--force", "--now",
                              ctx.now or "2026-08-28T00:00:00Z"])
    before = H.read_jsonl(cards_p)
    merged = [c for c in before if c["status"] == "merged"][0]
    merged_snapshot = json.dumps(merged, sort_keys=True)
    ctx.script("extract.py", ["--in", dlg, "--out", cards_p,
                              "--replay-dir", os.path.join(
                                  ctx.fixtures, "raw_extract"),
                              "--at", ctx.at or "2026-08-28T12:00:00Z"]
               + ctx.env_args())
    after = {c["card_id"]: c for c in H.read_jsonl(cards_p)}
    merged_after = json.dumps(after[merged["card_id"]], sort_keys=True)
    ids2 = list(after.keys())
    if len(ids2) != len(set(ids2)):
        r_fail("C-EX9", "extract", True, "duplicate card_ids after re-extract",
               "no duplicates")
    elif merged_snapshot != merged_after:
        r_fail("C-EX9", "extract", True, "merged card was overwritten",
               "merged/clustered cards skipped on re-extract")
    else:
        r_pass("C-EX9", "extract", True,
               f"{len(ids)} cards, no dups, merged card untouched",
               "upsert by card_id; clustered cards skipped")


def chk_ex10(ctx):
    raw = os.path.join(ctx.run_dir, "raw", "extract")
    dialogues = ctx.dialogues()
    if not os.path.isdir(raw):
        r_fail("C-EX10", "extract", True, "no raw/extract dir",
               "raw per dialogue")
        return
    files = {fn[:-5] for fn in os.listdir(raw) if fn.endswith(".json")}
    missing = [d["dialogue_id"] for d in dialogues
               if d["dialogue_id"] not in files]
    bad_shape = []
    for fn in sorted(os.listdir(raw)):
        rec = H.load_json(os.path.join(raw, fn))
        if not (rec.get("request") and rec.get("response_text") is not None
                and rec.get("model") and rec.get("usage") is not None):
            bad_shape.append(fn)
    cost = H.load_json(os.path.join(ctx.run_dir, "cost.json"))
    n_cost = cost.get("extract", {}).get("calls", 0)
    if not missing and not bad_shape and n_cost == len(files):
        r_pass("C-EX10", "extract", True,
               f"{len(files)} raw files, calls={n_cost}",
               "raw per dialogue with request/response/model/usage")
    else:
        r_fail("C-EX10", "extract", True,
               {"missing": missing[:3], "bad_shape": bad_shape[:3],
                "cost_calls": n_cost, "raw_files": len(files)},
               "raw completeness == extract calls")


def chk_ex11(ctx):
    raw = os.path.join(ctx.run_dir, "raw", "extract")
    n = parsed = 0
    if os.path.isdir(raw):
        for fn in os.listdir(raw):
            if not fn.endswith(".json"):
                continue
            n += 1
            rec = H.load_json(os.path.join(raw, fn))
            if rec.get("parsed") is not False and not rec.get("error"):
                parsed += 1
    rate = round((n - parsed) / n, 4) if n else 0.0
    r_pass("C-EX11", "extract", False, f"unparseable rate {rate} "
           f"({n - parsed}/{n})", "reported", "SOFT: rate only")


def chk_ex12(ctx):
    cards = ctx.cards()
    dialogues = {d["dialogue_id"]: d for d in ctx.dialogues()}
    hits = []
    for c in cards:
        d = dialogues.get(c["receipt"]["source_dialogue_id"])
        if not d:
            continue
        text = " ".join(t["text"] for t in d["turns"])
        # heuristic names: title-case words appearing >=2x in the transcript
        from collections import Counter
        words = re.findall(r"[A-Z][a-z]{2,}", text)
        names = {w for w, n in Counter(words).items() if n >= 2}
        allf = " ".join([c.get("problem_shape", ""), c.get("constraint", ""),
                         c.get("unlock", "")] + (c.get("what_worked") or []))
        for nm in names:
            if re.search(rf"\b{re.escape(nm)}\b", allf):
                hits.append(f"{c['card_id']}:{nm}")
    if not hits:
        r_pass("C-EX12", "extract", False, "no name-like tokens in fields",
               "no identity leak beyond regex gate", "SOFT")
    else:
        r_fail("C-EX12", "extract", False, hits[:5],
               "no customer name in card fields", "SOFT")


# --------------------------------------------------------------------------
# Cluster checks
# --------------------------------------------------------------------------


def chk_cl1(ctx):
    try:
        cards_p = os.path.join(ctx.work, "cl1_cards.jsonl")
        dlg = os.path.join(ctx.work, "cl1_dialogues.jsonl")
        H.write_jsonl(cards_p, [], mode="w")
        H.write_jsonl(dlg, [], mode="w")  # 0 dialogues -> remaining=100
        out, rc = ctx.script("cluster.py", ["--cards", cards_p,
                                            "--dialogues", dlg,
                                            "--cursor-file", os.path.join(
                                                ctx.work, "cl1_cursor.json")])
        s = json.loads(out)
        if s.get("ran") is False and s.get("remaining") == 100:
            r_pass("C-CL1", "cluster", True, out,
                   "{ran:false, remaining:100} under threshold")
        else:
            r_fail("C-CL1", "cluster", True, out,
                   "no-op when <100 new chats and no --force")
    except Exception as e:  # noqa: BLE001
        r_fail("C-CL1", "cluster", True, str(e), "no-op path runs")


def chk_cl(ctx):
    cards = ctx.cards()
    by_id = {c["card_id"]: c for c in cards}
    # C-CL2: no cluster spans scopes
    bad_scope = []
    for c in cards:
        if c["role"] == "canonical" and c["status"] != "rejected":
            for m in c.get("members") or []:
                if m in by_id and by_id[m]["receipt"]["scope"] != c[
                        "receipt"]["scope"]:
                    bad_scope.append((c["card_id"], m))
    if bad_scope:
        r_fail("C-CL2", "cluster", True, bad_scope[:3],
               "cluster confined to one receipt.scope")
    else:
        r_pass("C-CL2", "cluster", True, "no cross-scope clusters", "")

    # C-CL3: exactly one canonical per cluster_id; oldest; members consistent
    bad = []
    canon_by_cluster = {}
    for c in cards:
        cid = c["cluster_id"]
        if c["role"] == "canonical" and c["status"] != "rejected":
            canon_by_cluster.setdefault(cid, []).append(c["card_id"])
    for cid, canon_ids in canon_by_cluster.items():
        if len(canon_ids) != 1:
            bad.append(f"cluster {cid}: {len(canon_ids)} canonicals")
            continue
        c = by_id[canon_ids[0]]
        mem = c.get("members") or []
        for m in mem:
            mc = by_id.get(m)
            if not mc or mc["role"] != "member" or mc["status"] != "merged" \
                    or mc["cluster_id"] != cid:
                bad.append(f"{m} not a merged member of {cid}")
        oldest = min(canon_ids + mem, key=lambda x: (
            by_id[x]["created_at"] or "", by_id[x]["card_id"]))
        if oldest != c["card_id"]:
            bad.append(f"{cid}: canonical {c['card_id']} not oldest "
                       f"({oldest})")
    if not bad:
        r_pass("C-CL3", "cluster", True,
               f"{len(canon_by_cluster)} clusters, one canonical each, "
               "oldest, members consistent", "")
    else:
        r_fail("C-CL3", "cluster", True, bad[:5], "cluster structure")

    # C-CL4: votes recomputed == stored
    bad_v = []
    for c in cards:
        if c["role"] != "canonical" or c["status"] == "rejected":
            continue
        members = [by_id[m] for m in (c.get("members") or []) if m in by_id]
        v, _m, _d = H.compute_votes(c, members)
        if v != c.get("votes"):
            bad_v.append(f"{c['card_id']}: stored {c['votes']} != "
                         f"recomputed {v}")
    if not bad_v:
        r_pass("C-CL4", "cluster", True, "votes == recomputed for all "
               "canonicals", "incl. served_to subtraction + independence")
    else:
        r_fail("C-CL4", "cluster", True, bad_v[:5],
               "stored votes == recomputed")

    # C-CL5: shared iff votes >= K (and not stale)
    bad_s = []
    for c in cards:
        if c["role"] != "canonical" or c["status"] == "rejected":
            continue
        if c["status"] in ("private", "shared"):
            members = [by_id[m] for m in (c.get("members") or []) if m in by_id]
            stale = H.is_stale(c, members, ctx.cfg,
                               now=ctx.now or "2026-08-28T00:00:00Z")
            want_shared = (c.get("votes", 0) >= ctx.cfg["K_INDEPENDENT"]
                           and not stale)
            if (c["status"] == "shared") != want_shared:
                bad_s.append(f"{c['card_id']}: status={c['status']} "
                             f"votes={c['votes']} stale={stale}")
    if not bad_s:
        r_pass("C-CL5", "cluster", True, "shared iff votes >= K, not stale",
               "C-CL5 iff")
    else:
        r_fail("C-CL5", "cluster", True, bad_s[:5], "shared iff votes >= K")

    # C-CL6: last_closed_at == max(closed_at)
    bad_l = []
    for c in cards:
        if c["role"] != "canonical" or c["status"] == "rejected":
            continue
        members = [by_id[m] for m in (c.get("members") or []) if m in by_id]
        want = H.last_closed_at(c, members)
        if want and c["receipt"].get("last_closed_at") != want:
            bad_l.append(f"{c['card_id']}: {c['receipt'].get('last_closed_at')}"
                         f" != {want}")
    if not bad_l:
        r_pass("C-CL6", "cluster", True, "last_closed_at == max over "
               "canonical+members", "freshness rule")
    else:
        r_fail("C-CL6", "cluster", True, bad_l[:5], "last_closed_at rule")

    # C-CL7: merged never a seed; never served
    bad_m = [c["card_id"] for c in cards
             if c["role"] == "member" and c["cluster_id"] == c["card_id"]]
    served = set()
    for rec in ctx.packets():
        served.update(rec.get("card_ids") or [])
    bad_sv = [cid for cid in served
              if cid in by_id and by_id[cid]["status"] == "merged"]
    if not bad_m and not bad_sv:
        r_pass("C-CL7", "cluster", True, "merged cards never seeds/served", "")
    else:
        r_fail("C-CL7", "cluster", True,
               {"seed_like": bad_m[:3], "served": bad_sv[:3]},
               "merged excluded from seeds and serve path")

    # C-CL8: inheritance (§5.2) — verified on the fixture pair d-x1/d-x2
    # (canonical unlock=none must inherit the member's real unlock), plus the
    # what_worked cap on the run store.
    try:
        pair = [x for x in H.read_jsonl(os.path.join(
            ctx.fixtures, "spec10_dialogues.jsonl"))
            if x["dialogue_id"] in ("d-x1", "d-x2")]
        pairf = os.path.join(ctx.work, "cl8_pair.jsonl")
        H.write_jsonl(pairf, pair, mode="w")
        cards_p = os.path.join(ctx.work, "cl8_cards.jsonl")
        ctx.script("extract.py", ["--in", pairf, "--out", cards_p,
                                  "--replay-dir", os.path.join(
                                      ctx.fixtures, "raw_extract"),
                                  "--at", ctx.at or "2026-08-28T12:00:00Z"]
                   + ctx.env_args())
        ctx.script("cluster.py", ["--cards", cards_p, "--dialogues", pairf,
                                  "--force", "--now",
                                  ctx.now or "2026-08-28T00:00:00Z"])
        pair_cards = {c["receipt"]["source_dialogue_id"]: c
                      for c in H.read_jsonl(cards_p)}
        x1 = pair_cards.get("d-x1")
        inherit_ok = bool(x1) and x1.get("unlock") == (
            "reset password with security questions")
    except Exception as e:  # noqa: BLE001
        inherit_ok = False
        r_fail("C-CL8", "cluster", True, str(e), "inheritance pair runs")
    ww_bad = [c["card_id"] for c in cards
              if c["role"] == "canonical"
              and len(c.get("what_worked") or []) > 8]
    if inherit_ok and not ww_bad:
        r_pass("C-CL8", "cluster", True,
               "d-x1 inherited member unlock; what_worked capped", "")
    else:
        r_fail("C-CL8", "cluster", True,
               {"inherited": inherit_ok, "ww_over_8": ww_bad[:3]},
               "§5.2 inheritance holds")

    # C-CL9: re-run is a no-op
    try:
        cards_p = os.path.join(ctx.data, "cards.jsonl")
        dlg = os.path.join(ctx.data, "dialogues.jsonl")
        sha1 = H.sha256_file(cards_p)
        out1 = json.loads(ctx.script("cluster.py", ["--cards", cards_p,
                                                    "--dialogues", dlg,
                                                    "--force", "--now",
                                                    ctx.now or
                                                    "2026-08-28T00:00:00Z"])[0])
        sha2 = H.sha256_file(cards_p)
        out2 = json.loads(ctx.script("cluster.py", ["--cards", cards_p,
                                                    "--dialogues", dlg,
                                                    "--force", "--now",
                                                    ctx.now or
                                                    "2026-08-28T00:00:00Z"])[0])
        if sha1 == sha2 and out2.get("clusters_formed") == 0 and out2.get(
                "merged") == 0:
            r_pass("C-CL9", "cluster", True,
                   f"byte-identical cards; clusters_formed=0 merged=0 "
                   f"(first pass: formed={out1.get('clusters_formed')})", "")
        else:
            r_fail("C-CL9", "cluster", True,
                   {"bytes_same": sha1 == sha2, "formed": out2.get(
                       "clusters_formed"), "merged": out2.get("merged")},
                   "re-run is a no-op")
    except Exception as e:  # noqa: BLE001
        r_fail("C-CL9", "cluster", True, str(e), "re-run is a no-op")

    # C-CL11 (SOFT): unlock_conflict reported
    conflicts = 0
    for c in cards:
        if c["role"] != "canonical" or c["status"] == "rejected":
            continue
        unlocks = {c["unlock"]} if c.get("unlock", "").lower() != "none" \
            else set()
        for m in (c.get("members") or []):
            mc = by_id.get(m)
            if mc and mc.get("unlock", "").lower() != "none":
                unlocks.add(mc["unlock"])
        if len(unlocks) > 1:
            conflicts += 1
    r_pass("C-CL11", "cluster", False, f"unlock_conflict={conflicts}",
           "reported", "SOFT")


def chk_cl10(ctx):
    """§10.2 + §10.3: ten near-duplicates, two agents vs one agent."""
    ten_ids = [f"d-{i:03d}" for i in range(1, 11)]
    for variant, agent_file, want_votes, want_status in (
            (2, "spec10_dialogues.jsonl", 6, "shared"),
            (1, "spec10_dialogues_a1.jsonl", 1, "private")):
        src = os.path.join(ctx.fixtures, agent_file)
        d10 = [x for x in H.read_jsonl(src) if x["dialogue_id"] in ten_ids]
        d10f = os.path.join(ctx.work, f"cl10_{variant}.jsonl")
        H.write_jsonl(d10f, d10, mode="w")
        cards_p = os.path.join(ctx.work, f"cl10_{variant}_cards.jsonl")
        ctx.script("extract.py", ["--in", d10f, "--out", cards_p,
                                  "--replay-dir", os.path.join(
                                      ctx.fixtures, "raw_extract"),
                                  "--at", ctx.at or "2026-08-28T12:00:00Z"]
                   + ctx.env_args())
        ctx.script("cluster.py", ["--cards", cards_p, "--dialogues", d10f,
                                  "--force", "--now",
                                  ctx.now or "2026-08-28T00:00:00Z"])
        cards = H.read_jsonl(cards_p)
        canon = [c for c in cards if c["role"] == "canonical"
                 and c["status"] != "rejected"]
        if variant == 2:
            ok = (len(canon) == 1 and len(canon[0]["members"]) == 9
                  and canon[0]["votes"] >= 2
                  and canon[0]["status"] == "shared")
            if not ok:
                r_fail("C-CL10", "cluster", True,
                       {"canon": len(canon),
                        "members": len(canon[0]["members"]) if canon else None,
                        "votes": canon[0]["votes"] if canon else None,
                        "status": canon[0]["status"] if canon else None},
                       "10.2: 1 canonical, 9 merged, votes>=2, shared")
        else:
            ok = (len(canon) == 1 and canon[0]["votes"] == 1
                  and canon[0]["status"] == "private"
                  and not any(c["status"] == "shared" for c in cards))
            if not ok:
                r_fail("C-CL10", "cluster", True,
                       {"canon": len(canon),
                        "votes": canon[0]["votes"] if canon else None,
                        "status": canon[0]["status"] if canon else None},
                       "10.3: votes=1, private, nothing shared")
    # if both passed we record one pass row
    passed = all(x["check_id"] != "C-CL10" for x in RESULTS)
    if passed:
        r_pass("C-CL10", "cluster", True,
               "two-agent -> shared; one-agent -> private", "§10.2/§10.3")


def chk_cl6_freshness(ctx):
    """§10.5 aged-timeline contract: yesterday member keeps cluster alive;
    a cluster quiet >30 days goes stale."""
    ids = ["d-10x", "d-10y", "d-10z", "d-10w"]
    src = os.path.join(ctx.fixtures, "spec10_dialogues.jsonl")
    d = [x for x in H.read_jsonl(src) if x["dialogue_id"] in ids]
    df = os.path.join(ctx.work, "fresh.jsonl")
    H.write_jsonl(df, d, mode="w")
    cards_p = os.path.join(ctx.work, "fresh_cards.jsonl")
    ctx.script("extract.py", ["--in", df, "--out", cards_p,
                              "--replay-dir", os.path.join(
                                  ctx.fixtures, "raw_extract"),
                              "--at", ctx.at or "2026-08-28T12:00:00Z"]
               + ctx.env_args())
    ctx.script("cluster.py", ["--cards", cards_p, "--dialogues", df,
                              "--force", "--now", "2026-08-28T00:00:00Z"])
    cards = {c["receipt"]["source_dialogue_id"]: c
             for c in H.read_jsonl(cards_p)}
    x = cards.get("d-10x")
    z = cards.get("d-10z")
    if x and z and x["status"] != "stale" and x["receipt"][
            "last_closed_at"] == "2026-08-27T10:00:00Z" and z["status"] == \
            "stale":
        r_pass("C-CL6", "cluster", True,
               "d-10x alive (member yesterday), d-10z stale (quiet 68d)",
               "aged timeline contract")
    else:
        r_fail("C-CL6", "cluster", True,
               {"d-10x": x and x["status"], "d-10z": z and z["status"]},
               "freshness contract (aged timeline)")


# --------------------------------------------------------------------------
# Promote / anti-echo checks
# --------------------------------------------------------------------------


def chk_pr(ctx):
    cards = ctx.cards()
    by_id = {c["card_id"]: c for c in cards}
    # C-PR2: no shared card with votes < K
    bad = [c["card_id"] for c in cards
           if c["status"] == "shared" and c.get("votes", 0) < ctx.cfg[
               "K_INDEPENDENT"]]
    if bad:
        r_fail("C-PR2", "promote", True, bad, "no shared with votes < K")
    else:
        r_pass("C-PR2", "promote", True, "no shared card below K", "")

    # C-PR1: promote changes only status
    try:
        p = os.path.join(ctx.work, "pr1_cards.jsonl")
        shutil.copy(os.path.join(ctx.data, "cards.jsonl"), p)
        before = H.read_jsonl(p)
        ctx.script("promote.py", ["--cards", p, "--now",
                                  ctx.now or "2026-08-28T00:00:00Z"])
        after = H.read_jsonl(p)
        diffs = []
        for b, a in zip(before, after):
            for k in set(b) | set(a):
                if k == "status":
                    continue
                if b.get(k) != a.get(k):
                    diffs.append(f"{b['card_id']}:{k}")
        if not diffs:
            r_pass("C-PR1", "promote", True, "promote changed only status",
                   "")
        else:
            r_fail("C-PR1", "promote", True, diffs[:5],
                   "promote changes only status")
    except Exception as e:  # noqa: BLE001
        r_fail("C-PR1", "promote", True, str(e), "promote runs")

    # C-PR4: stale canonical never returns to shared; members stay merged
    try:
        p = os.path.join(ctx.work, "pr4_cards.jsonl")
        shutil.copy(os.path.join(ctx.data, "cards.jsonl"), p)
        cards4 = H.read_jsonl(p)
        canon = next((c for c in cards4
                      if c["role"] == "canonical" and c["status"] == "shared"
                      and c.get("members")), None)
        if canon:
            fb = os.path.join(ctx.work, "pr4_feedback.jsonl")
            ctx.script("feedback.py", ["--card-id", canon["card_id"],
                                       "--label", "wrong", "--dialogue",
                                       "d-999", "--cards", p,
                                       "--feedback-file", fb])
            ctx.script("promote.py", ["--cards", p, "--now",
                                      ctx.now or "2026-08-28T00:00:00Z"])
            cards4 = {c["card_id"]: c for c in H.read_jsonl(p)}
            c = cards4[canon["card_id"]]
            members = [cards4[m] for m in (c.get("members") or [])
                       if m in cards4]
            if c["status"] == "stale" and all(
                    m["status"] == "merged" for m in members):
                r_pass("C-PR4", "promote", True,
                       "feedback-stale canonical stays stale; members merged",
                       "")
            else:
                r_fail("C-PR4", "promote", True,
                       {"canon": c["status"],
                        "members": [m["status"] for m in members]},
                       "stale absorbing; members stay merged")
        else:
            r_fail("C-PR4", "promote", True, "no shared canonical with "
                   "members to test", "needs a shared cluster")
    except Exception as e:  # noqa: BLE001
        r_fail("C-PR4", "promote", True, str(e), "feedback+promote path")


def chk_pr3(ctx):
    """Anti-echo (fixture): serve d-013, re-cluster, votes unchanged."""
    try:
        src = os.path.join(ctx.fixtures, "spec10_dialogues.jsonl")
        d10 = [x for x in H.read_jsonl(src)
               if x["dialogue_id"] in [f"d-{i:03d}" for i in range(1, 11)]]
        df = os.path.join(ctx.work, "pr3_d10.jsonl")
        H.write_jsonl(df, d10, mode="w")
        cards_p = os.path.join(ctx.work, "pr3_cards.jsonl")
        ctx.script("extract.py", ["--in", df, "--out", cards_p,
                                  "--replay-dir", os.path.join(
                                      ctx.fixtures, "raw_extract"),
                                  "--at", ctx.at or "2026-08-28T12:00:00Z"]
                   + ctx.env_args())
        ctx.script("cluster.py", ["--cards", cards_p, "--dialogues", df,
                                  "--force", "--now",
                                  ctx.now or "2026-08-28T00:00:00Z"])
        cards = H.read_jsonl(cards_p)
        canon = next(c for c in cards if c["role"] == "canonical"
                     and c["status"] == "shared")
        d013 = next(x for x in H.read_jsonl(src)
                    if x["dialogue_id"] == "d-013")
        one = os.path.join(ctx.work, "pr3_d013.json")
        H.write_json(one, d013)
        # serve 10 times; votes must not move
        for _ in range(10):
            ctx.script("serve.py", ["--dialogue", one, "--cards", cards_p,
                                    "--at", ctx.at or "2026-08-28T12:00:00Z"])
        cards = H.read_jsonl(cards_p)
        canon2 = next(c for c in cards if c["card_id"] == canon["card_id"])
        serves = [s for s in canon2["served_to"]
                  if s["dialogue_id"] == "d-013"]
        votes_before = canon2["votes"]
        ctx.script("cluster.py", ["--cards", cards_p, "--dialogues", df,
                                  "--force", "--now",
                                  ctx.now or "2026-08-28T00:00:00Z"])
        cards = H.read_jsonl(cards_p)
        canon3 = next(c for c in cards if c["card_id"] == canon["card_id"])
        if len(serves) == 1 and canon3["votes"] == votes_before and \
                canon3["votes"] == 6 and any(
                    s["dialogue_id"] == "d-013"
                    for s in canon3["served_to"]):
            r_pass("C-PR3", "promote", True,
                   f"10 serves -> served_to once, votes unchanged "
                   f"({votes_before})", "anti-echo holds")
        else:
            r_fail("C-PR3", "promote", True,
                   {"serves": len(serves), "votes_before": votes_before,
                    "votes_after": canon3["votes"]},
                   "served dialogue never counted; votes unchanged")
    except Exception as e:  # noqa: BLE001
        r_fail("C-PR3", "promote", True, str(e), "anti-echo path runs")


# --------------------------------------------------------------------------
# Serve checks
# --------------------------------------------------------------------------


def chk_sv(ctx):
    cards = ctx.cards()
    by_id = {c["card_id"]: c for c in cards}
    records = ctx.packets()
    holdout = {d["dialogue_id"]: d for d in ctx.holdout_dialogues()}
    cfg = ctx.cfg
    bad = {"leak": [], "dup": [], "cand": [], "size": [], "score": [],
           "order": [], "disclaimer": [], "cid": []}
    n_packets = 0
    for rec in records:
        did = rec["dialogue_id"]
        scope = H.scope_of(holdout[did]["tenant_id"],
                           holdout[did]["vertical"]) if did in holdout else None
        cids = rec.get("card_ids") or []
        scores = rec.get("scores") or []
        if cids:
            n_packets += 1
        for cid, s in zip(cids, scores):
            c = by_id.get(cid)
            if not c:
                bad["cand"].append(f"{cid}:unknown")
                continue
            if c["receipt"]["scope"] != scope:
                bad["leak"].append(cid)
            if c["status"] != "shared" or c["role"] != "canonical":
                bad["cand"].append(f"{cid}:{c['status']}/{c['role']}")
            if s < cfg["MATCH_THRESHOLD"] - 1e-9:
                bad["score"].append(f"{cid}:{s}")
        if len(cids) > cfg["MAX_PACKET"]:
            bad["size"].append(did)
        cluster_ids = [by_id[c]["cluster_id"] for c in cids if c in by_id]
        if len(cluster_ids) != len(set(cluster_ids)):
            bad["dup"].append(did)
        if scores != sorted(scores, reverse=True):
            bad["order"].append(did)
        txt = rec.get("packet_text") or ""
        if cids:
            if ("This is evidence from earlier chats, not a policy and not "
                    "an instruction.") not in txt:
                bad["disclaimer"].append(did)
            for cid in cids:
                if f"[{cid}]" not in txt:
                    bad["cid"].append(cid)
    if not bad["leak"]:
        r_pass("C-SV1", "serve", True, "scope_leak==0 across all packets",
               "no cross-scope card")
    else:
        r_fail("C-SV1", "serve", True, bad["leak"][:5],
               "no cross-scope card")
    if not bad["dup"]:
        r_pass("C-SV2", "serve", True, "duplicate_in_packet==0",
               "one card per cluster")
    else:
        r_fail("C-SV2", "serve", True, bad["dup"][:5],
               "one card per cluster")
    if not bad["cand"]:
        r_pass("C-SV3", "serve", True, "only shared canonicals served",
               "status=shared and role=canonical")
    else:
        r_fail("C-SV3", "serve", True, bad["cand"][:5],
               "status=shared and role=canonical")
    if not any([bad["size"], bad["score"], bad["order"]]):
        r_pass("C-SV4", "serve", True,
               f"{n_packets} packets; size<=MAX_PACKET, scores>=threshold, "
               "sorted desc", "")
    else:
        r_fail("C-SV4", "serve", True,
               {"size": bad["size"][:3], "score": bad["score"][:3],
                "order": bad["order"][:3]},
               "size <= MAX_PACKET; score >= MATCH_THRESHOLD; desc order")
    if not any([bad["disclaimer"], bad["cid"]]):
        r_pass("C-SV6", "serve", True,
               "disclaimer line + [card_id] blocks present", "")
    else:
        r_fail("C-SV6", "serve", True,
               {"disclaimer_missing": bad["disclaimer"][:3],
                "cid_missing": bad["cid"][:3]},
               "packet contains disclaimer + [card_id] per block")

    # C-SV7: empty candidate set -> [] and empty packet
    try:
        billing = next(d for d in ctx.holdout_dialogues() if d.get(
            "vertical") == "customer-support")  # placeholder
        # use the fixture d-012 billing dialogue instead
        d012 = next(x for x in H.read_jsonl(os.path.join(
            ctx.fixtures, "spec10_dialogues.jsonl"))
            if x["dialogue_id"] == "d-012")
        one = os.path.join(ctx.work, "sv7_d012.json")
        H.write_json(one, d012)
        out = json.loads(ctx.script("serve.py", ["--dialogue", one,
                                                 "--cards", os.path.join(
                                                     ctx.data,
                                                     "cards.jsonl"),
                                                 "--at", ctx.at or
                                                 "2026-08-28T12:00:00Z"])[0])
        if out["card_ids"] == [] and "This is evidence" in out[
                "packet_text"]:
            r_pass("C-SV7", "serve", True, "empty candidates -> empty packet",
                   "")
        else:
            r_fail("C-SV7", "serve", True, out, "empty packet for empty set")
    except Exception as e:  # noqa: BLE001
        r_fail("C-SV7", "serve", True, str(e), "empty-set path")

    # C-SV5: query = customer turns only (perturb agent text)
    try:
        d = next(iter(holdout.values()))
        base = os.path.join(ctx.work, "sv5_base.json")
        pert = os.path.join(ctx.work, "sv5_pert.json")
        H.write_json(base, d)
        d2 = json.loads(json.dumps(d))
        for t in d2["turns"]:
            if t["role"] != "customer":
                t["text"] = "zzzz zzzz zzzz zzzz zzzz"
        H.write_json(pert, d2)
        cards_p = os.path.join(ctx.data, "cards.jsonl")
        o1 = ctx.script("match.py", ["--dialogue", base, "--cards",
                                     cards_p])[0]
        o2 = ctx.script("match.py", ["--dialogue", pert, "--cards",
                                     cards_p])[0]
        if o1 == o2:
            r_pass("C-SV5", "serve", True,
                   "agent/tool perturbation did not change scores",
                   "query = customer turns only")
        else:
            r_fail("C-SV5", "serve", True, {"before": o1, "after": o2},
                   "scores unchanged by agent-turn edit")
    except Exception as e:  # noqa: BLE001
        r_fail("C-SV5", "serve", True, str(e), "perturbation path")

    # C-SV8: served_to appended exactly once per (card, dialogue)
    try:
        p = os.path.join(ctx.work, "sv8_cards.jsonl")
        shutil.copy(os.path.join(ctx.data, "cards.jsonl"), p)
        first = next(iter(holdout.values()))
        one = os.path.join(ctx.work, "sv8_one.json")
        H.write_json(one, first)
        for _ in range(2):
            ctx.script("serve.py", ["--dialogue", one, "--cards", p,
                                    "--at", ctx.at or "2026-08-28T12:00:00Z"])
        cards8 = H.read_jsonl(p)
        dbl = []
        for c in cards8:
            cnt = sum(1 for s in c.get("served_to") or []
                      if s["dialogue_id"] == first["dialogue_id"])
            if cnt > 1:
                dbl.append(f"{c['card_id']}:{cnt}")
        if not dbl:
            r_pass("C-SV8", "serve", True, "no double-append on re-serve", "")
        else:
            r_fail("C-SV8", "serve", True, dbl,
                   "exactly one served_to entry per dialogue")
    except Exception as e:  # noqa: BLE001
        r_fail("C-SV8", "serve", True, str(e), "re-serve path")

    # C-SV9: match deterministic
    try:
        one = next(iter(holdout.values()))
        f = os.path.join(ctx.work, "sv9_one.json")
        H.write_json(f, one)
        o1 = ctx.script("match.py", ["--dialogue", f, "--cards",
                                     os.path.join(ctx.data,
                                                  "cards.jsonl")])[0]
        o2 = ctx.script("match.py", ["--dialogue", f, "--cards",
                                     os.path.join(ctx.data,
                                                  "cards.jsonl")])[0]
        if o1 == o2:
            r_pass("C-SV9", "serve", True, "match idempotent", "")
        else:
            r_fail("C-SV9", "serve", True, {"a": o1, "b": o2},
                   "match deterministic")
    except Exception as e:  # noqa: BLE001
        r_fail("C-SV9", "serve", True, str(e), "determinism path")


def chk_fb(ctx):
    """C-FB1..C-FB4 on a scratch store."""
    try:
        cards = ctx.cards()
        canon = next((c for c in cards if c["role"] == "canonical"
                      and c["status"] == "shared" and c.get("members")), None)
        if not canon:
            r_fail("C-FB1", "serve", True, "no shared canonical with members",
                   "feedback needs a shared cluster")
            return
        p = os.path.join(ctx.work, "fb_cards.jsonl")
        shutil.copy(os.path.join(ctx.data, "cards.jsonl"), p)
        fb = os.path.join(ctx.work, "fb_feedback.jsonl")
        # C-FB2 first: helpful changes nothing
        ctx.script("feedback.py", ["--card-id", canon["card_id"],
                                   "--label", "helpful", "--dialogue", "d-1",
                                   "--cards", p, "--feedback-file", fb])
        cards_h = H.read_jsonl(p)
        c_h = next(c for c in cards_h if c["card_id"] == canon["card_id"])
        if c_h["status"] == canon["status"] and len(H.read_jsonl(fb)) == 1:
            r_pass("C-FB2", "serve", True, "helpful: status unchanged, one "
                   "row appended", "")
        else:
            r_fail("C-FB2", "serve", True,
                   {"status": c_h["status"], "rows": len(H.read_jsonl(fb))},
                   "helpful changes nothing")
        # C-FB1: wrong flips the canonical; members stay merged; no other card
        snap_before = {c["card_id"]: json.dumps(c, sort_keys=True)
                       for c in H.read_jsonl(p)}
        ctx.script("feedback.py", ["--card-id", canon["card_id"],
                                   "--label", "wrong", "--dialogue", "d-2",
                                   "--cards", p, "--feedback-file", fb])
        cards_f = H.read_jsonl(p)
        c_f = next(c for c in cards_f if c["card_id"] == canon["card_id"])
        members = [c for c in cards_f
                   if c["card_id"] in (canon.get("members") or [])]
        changed = [cid for cid, snap in snap_before.items()
                   if cid != canon["card_id"]
                   and json.dumps(next(c for c in cards_f
                                       if c["card_id"] == cid),
                                  sort_keys=True) != snap]
        if c_f["status"] == "stale" and all(
                m["status"] == "merged" for m in members) and not changed:
            r_pass("C-FB1", "serve", True,
                   "wrong -> canonical stale, members merged, no other "
                   "card changed", "")
        else:
            r_fail("C-FB1", "serve", True,
                   {"canon": c_f["status"],
                    "members": [m["status"] for m in members],
                    "other_changed": changed[:3]},
                   "exactly the cited canonical flips")
        # C-FB3: stale card never served again
        one = os.path.join(ctx.work, "fb_one.json")
        H.write_json(one, ctx.holdout_dialogues()[0])
        out = json.loads(ctx.script("serve.py", ["--dialogue", one,
                                                 "--cards", p,
                                                 "--at", ctx.at or
                                                 "2026-08-28T12:00:00Z"])[0])
        if canon["card_id"] not in out["card_ids"]:
            r_pass("C-FB3", "serve", True, "stale card not served", "")
        else:
            r_fail("C-FB3", "serve", True, out["card_ids"],
                   "stale never served again")
        # C-FB4: no --card-id with a multi-card packet -> refuse
        r = subprocess.run([sys.executable, os.path.join(BIN, "feedback.py"),
                            "--label", "helpful", "--dialogue", "d-3",
                            "--packet-card-ids", "c-a,c-b",
                            "--feedback-file", os.path.join(
                                ctx.work, "fb4.jsonl")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            r_pass("C-FB4", "serve", True, "refused without --card-id", "")
        else:
            r_fail("C-FB4", "serve", True, "accepted ambiguous feedback",
                   "--card-id required for multi-card packets")
    except Exception as e:  # noqa: BLE001
        r_fail("C-FB1", "serve", True, str(e), "feedback checks run")


# --------------------------------------------------------------------------
# Eval checks
# --------------------------------------------------------------------------


def chk_ev(ctx):
    # C-EV1: hit+wrong+abstain == 1.0 exactly; C-EV2: per_dialogue reproduces
    m = H.load_json(os.path.join(ctx.run_dir, "metrics.json"))
    rows = H.read_jsonl(os.path.join(ctx.run_dir, "per_dialogue.jsonl"))
    n = m.get("n_holdout", len(rows))
    from collections import Counter
    cnt = Counter(r["outcome"] for r in rows)
    h, w, a = cnt.get("hit", 0), cnt.get("wrong", 0), cnt.get("abstain", 0)
    prim = m["primary"]
    if h + w + a == n and abs((prim["unlock_hit_label"] + prim["wrong"] +
                               prim["abstain"]) - 1.0) < 1e-9:
        r_pass("C-EV1", "eval", True,
               f"{h}+{w}+{a}={n}; ratios sum 1.0", "exactly 1.0")
    else:
        r_fail("C-EV1", "eval", True,
               {"counts": [h, w, a], "n": n, "ratios": prim},
               "hit+wrong+abstain == 1.0")
    # C-EV2: one row per hold-out dialogue + aggregates reproduce metrics
    holdout = ctx.holdout_dialogues()
    row_ids = [r["dialogue_id"] for r in rows]
    if len(row_ids) == len(set(row_ids)) == len(holdout):
        ok2 = (abs(prim["unlock_hit_label"] - round(h / n, 6)) < 1e-6
               and abs(prim["wrong"] - round(w / n, 6)) < 1e-6)
        if ok2:
            r_pass("C-EV2", "eval", True,
                   f"{len(rows)} rows == {len(holdout)} hold-out; "
                   "aggregates reproduce", "")
        else:
            r_fail("C-EV2", "eval", True,
                   {"rows": len(rows), "holdout": len(holdout),
                    "metric": prim, "recomputed": [round(h / n, 6),
                                                   round(w / n, 6)]},
                   "per_dialogue reproduces metrics.json")
    else:
        r_fail("C-EV2", "eval", True,
               {"rows": len(row_ids), "unique": len(set(row_ids)),
                "holdout": len(holdout)},
               "one row per hold-out dialogue")

    # C-EV7: manifest shas
    man = ctx.manifest
    missing = []
    for k, v in (man.get("inputs") or {}).items():
        if isinstance(v, dict) and not v.get("sha256"):
            missing.append(f"inputs.{k}")
    for k, v in (man.get("outputs") or {}).items():
        if not v:
            missing.append(f"outputs.{k}")
    if not missing:
        r_pass("C-EV7", "eval", True, "all input/output shas present", "")
    else:
        r_fail("C-EV7", "eval", True, missing, "sha256 for every input and "
               "published output")

    # C-EV8: audit before S2
    audit = os.path.join(ctx.run_dir, "audit.json")
    if ctx.stage == "S2":
        if os.path.exists(audit):
            a5 = H.load_json(audit)
            if all(k in a5 for k in ("A1", "A2", "A3", "A4", "A5")):
                r_pass("C-EV8", "eval", True, "audit.json has A1-A5", "")
            else:
                r_fail("C-EV8", "eval", True, list(a5.keys()),
                       "audit.json answers A1-A5")
        else:
            r_fail("C-EV8", "eval", True, "audit.json missing",
                   "required before S2")
    else:
        r_pass("C-EV8", "eval", True, "deferred (audit due before S2)",
               "audit.json required before S2 runs", "deferred at "
               f"{ctx.stage}")

    # C-EV9 (SOFT) / C-EV10 (SOFT)
    cost = H.load_json(os.path.join(ctx.run_dir, "cost.json"))
    if cost.get("price_source") and (cost["extract"].get("usd_total") is None
                                     or True):
        r_pass("C-EV9", "eval", False,
               f"price_source stated: {cost['price_source'][:60]}...",
               "stated source; usd null if unknown", "SOFT")
    else:
        r_fail("C-EV9", "eval", False, cost.get("price_source"),
               "price source stated", "SOFT")
    report = open(os.path.join(ctx.run_dir, "report.md"),
                  encoding="utf-8").read()
    if "timeline" in report and "independence" in report:
        r_pass("C-EV10", "eval", False, "report states timeline + "
               "independence", "", "SOFT")
    else:
        r_fail("C-EV10", "eval", False, "missing from report.md",
               "timeline + independence stated", "SOFT")


def _eval_baseline(ctx, arm, extra_cfg=None, out_name=None,
                   packets_dir=None):
    """Run eval.py score with a baseline arm on the run's slices."""
    out = os.path.join(ctx.work, out_name or f"eval_{arm}")
    os.makedirs(out, exist_ok=True)
    cmd = ["score", "--pool-dialogues", os.path.join(ctx.data,
                                                     "dialogues.jsonl"),
           "--cards", os.path.join(ctx.data, "cards.jsonl"),
           "--labels", os.path.join(ctx.data, "ground_truth_labels.jsonl"),
           "--holdout-dialogues", os.path.join(ctx.data,
                                               "holdout_dialogues.jsonl"),
           "--packets-dir", packets_dir or os.path.join(ctx.run_dir,
                                                        "packets"),
           "--baseline", arm, "--run-id", ctx.manifest.get("run_id", "x"),
           "--out", out]
    for kv in (extra_cfg or []):
        cmd += ["--config", kv]
    ctx.script("eval.py", cmd)
    return H.load_json(os.path.join(out, "metrics.json"))


def chk_ev34(ctx):
    """C-EV3: B0 -> hit 0, abstain 1.0. C-EV4: B2 -> >= 0.98."""
    try:
        b0 = _eval_baseline(ctx, "B0")
        if b0["primary"]["unlock_hit_label"] == 0.0 and b0["primary"][
                "abstain"] == 1.0:
            r_pass("C-EV3", "eval", True, b0["primary"],
                   "B0: hit=0, abstain=1.0")
        else:
            r_fail("C-EV3", "eval", True, b0["primary"],
                   "B0 hit==0 abstain==1.0")
        b2 = _eval_baseline(ctx, "B2")
        if b2["primary"]["unlock_hit_label"] >= 0.98:
            r_pass("C-EV4", "eval", True, b2["primary"],
                   "B2 oracle >= 0.98 (metric sanity)")
        else:
            r_fail("C-EV4", "eval", True, b2["primary"],
                   "B2 >= 0.98 or the scoring code is broken")
    except Exception as e:  # noqa: BLE001
        r_fail("C-EV3", "eval", True, str(e), "baselines run")


def chk_ev5(ctx):
    src = open(os.path.join(BIN, "eval.py"), encoding="utf-8").read()
    n_defs = len(re.findall(r"def score_outcomes", src))
    if n_defs == 1 and "score_outcomes(rows, n_holdout)" in src:
        r_pass("C-EV5", "eval", True,
               "single score_outcomes; B0/B1/B2 go through eval.py "
               "--baseline", "one scoring function for T and baselines")
    else:
        r_fail("C-EV5", "eval", True, f"score_outcomes defs: {n_defs}",
               "exactly one scoring implementation")


def chk_ev6(ctx):
    """--replay reproduces metrics.json byte-identically, zero LLM calls."""
    try:
        out = os.path.join(ctx.work, "replay_check")
        if os.path.exists(out):
            shutil.rmtree(out)
        cmd = [sys.executable, os.path.join(BIN, "run_experiment.py"),
               "--replay", ctx.manifest.get("run_id", ""), "--out", out,
               "--no-checks", "--stage", ctx.stage, "--model", ctx.model]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           cwd=H1_DIR)
        if r.returncode != 0:
            r_fail("C-EV6", "eval", True, r.stderr[-500:],
                   "replay run completes")
            return
        m1 = open(os.path.join(ctx.run_dir, "metrics.json"), "rb").read()
        m2 = open(os.path.join(out, "metrics.json"), "rb").read()
        cost2 = H.load_json(os.path.join(out, "cost.json"))
        if m1 == m2 and cost2.get("extract", {}).get("live_llm_calls", 1) == 0:
            r_pass("C-EV6", "eval", True,
                   "metrics.json byte-identical; 0 live LLM calls",
                   "replay reproduces the run")
        else:
            r_fail("C-EV6", "eval", True,
                   {"bytes_identical": m1 == m2,
                    "live_llm_calls": cost2.get("extract", {}).get(
                        "live_llm_calls")},
                   "byte-identical metrics + zero LLM calls")
    except Exception as e:  # noqa: BLE001
        r_fail("C-EV6", "eval", True, str(e), "replay path")


def chk_nc(ctx):
    """Negative controls C-NC1..C-NC4."""
    # C-NC1: AGENT_POOL_SIZE=1 -> nothing shared, serve_rate == 0
    try:
        work = os.path.join(ctx.work, "nc1")
        os.makedirs(work, exist_ok=True)
        dlg = os.path.join(work, "dialogues.jsonl")
        ctx.script("ingest.py", ["--in", os.path.join(ctx.data,
                                                      "pool_slice_raw.jsonl"),
                                 "--out", dlg, "--agent-pool-size", "1",
                                 "--timeline", ctx.timeline,
                                 "--t0", ctx.cfg.get("t0") or
                                 "2026-08-28T00:00:00Z"])
        cards_p = os.path.join(work, "cards.jsonl")
        ctx.script("extract.py", ["--in", dlg, "--out", cards_p,
                                  "--replay-dir", os.path.join(ctx.run_dir,
                                                               "raw",
                                                               "extract"),
                                  "--at", ctx.at or "2026-08-28T12:00:00Z"]
                   + ctx.env_args())
        ctx.script("cluster.py", ["--cards", cards_p, "--dialogues", dlg,
                                  "--force", "--now",
                                  ctx.now or "2026-08-28T00:00:00Z"])
        cards = H.read_jsonl(cards_p)
        n_shared = sum(1 for c in cards if c["status"] == "shared")
        if n_shared == 0:
            r_pass("C-NC1", "eval", True, f"A=1: {n_shared} shared cards",
                   "nothing shared with one agent")
        else:
            r_fail("C-NC1", "eval", True, n_shared,
                   "AGENT_POOL_SIZE=1 -> nothing shared")
    except Exception as e:  # noqa: BLE001
        r_fail("C-NC1", "eval", True, str(e), "A=1 control runs")

    # C-NC2: fake scopes -> serve_rate == 0, scope_leak == 0
    try:
        work = os.path.join(ctx.work, "nc2")
        os.makedirs(work, exist_ok=True)
        cards_p = os.path.join(work, "cards.jsonl")
        cards = json.loads(json.dumps(ctx.cards()))
        for c in cards:
            c["receipt"]["scope"] = "fake-scope/fake-vertical"
        H.write_jsonl(cards_p, cards, mode="w")
        served = []
        holdout = ctx.holdout_dialogues()
        for d in holdout:
            one = os.path.join(work, "one.json")
            H.write_json(one, d)
            out = json.loads(ctx.script("serve.py", ["--dialogue", one,
                                                     "--cards", cards_p,
                                                     "--at", ctx.at or
                                                     "2026-08-28T12:00:00Z"])[0])
            served.append(out)
        leak = sum(1 for o in served for c in o["card_ids"])
        rate = round(sum(1 for o in served if o["card_ids"]) / len(served),
                     6) if served else 0
        if rate == 0 and leak == 0:
            r_pass("C-NC2", "eval", True,
                   f"fake scopes: serve_rate={rate}, scope_leak={leak}", "")
        else:
            r_fail("C-NC2", "eval", True, {"serve_rate": rate, "leak": leak},
                   "serve_rate==0 and scope_leak==0")
    except Exception as e:  # noqa: BLE001
        r_fail("C-NC2", "eval", True, str(e), "fake-scope control runs")

    # C-NC3: shuffle unlocks -> unlock_hit_label drops toward label prior
    try:
        work = os.path.join(ctx.work, "nc3")
        os.makedirs(work, exist_ok=True)
        cards = json.loads(json.dumps(ctx.cards()))
        rng = random.Random(42)
        nonrej = [c for c in cards if c["status"] != "rejected"]
        unlocks = [c["unlock"] for c in nonrej]
        rng.shuffle(unlocks)
        for c, u in zip(nonrej, unlocks):
            c["unlock"] = u
        cards_p = os.path.join(work, "cards.jsonl")
        H.write_jsonl(cards_p, cards, mode="w")
        served = []
        for d in ctx.holdout_dialogues():
            one = os.path.join(work, "one.json")
            H.write_json(one, d)
            out = json.loads(ctx.script("serve.py", ["--dialogue", one,
                                                     "--cards", cards_p,
                                                     "--at", ctx.at or
                                                     "2026-08-28T12:00:00Z"])[0])
            served.append({"dialogue_id": d["dialogue_id"],
                           "card_ids": out["card_ids"],
                           "scores": out["scores"],
                           "packet_text": out["packet_text"]})
        pdir = os.path.join(work, "packets")
        os.makedirs(pdir, exist_ok=True)
        H.write_jsonl(os.path.join(pdir, "_served.jsonl"), served, mode="w")
        m = _eval_baseline(ctx, "T", out_name="nc3_eval",
                           packets_dir=pdir)
        t_metrics = H.load_json(os.path.join(ctx.run_dir, "metrics.json"))
        t_hit = t_metrics["primary"]["unlock_hit_label"]
        c_hit = m["primary"]["unlock_hit_label"]
        n_score = len(ctx.holdout_dialogues())
        prior = 1.0 / 55.0
        if c_hit <= t_hit + 1e-9:
            note = "" if n_score >= 20 else \
                "small-n scoring slice; strict prior bound deferred to S2"
            if n_score >= 20 and c_hit > prior + 0.05:
                r_fail("C-NC3", "eval", True,
                       {"T": t_hit, "corrupted": c_hit, "prior": round(
                           prior, 4)},
                       "corrupted hit near label prior")
            else:
                r_pass("C-NC3", "eval", True,
                       {"T": t_hit, "corrupted": c_hit, "prior": round(
                           prior, 4), "n": n_score}, note)
        else:
            r_fail("C-NC3", "eval", True,
                   {"T": t_hit, "corrupted": c_hit},
                   "corrupted hit must not exceed T")
    except Exception as e:  # noqa: BLE001
        r_fail("C-NC3", "eval", True, str(e), "unlock-shuffle control runs")

    # C-NC4 (SOFT): threshold knob — 0.99 -> serve_rate ~0; 0.0 -> ~1.0
    try:
        hi = _eval_baseline(ctx, "B1", extra_cfg=["MATCH_THRESHOLD=0.99"],
                            out_name="nc4_hi")
        lo = _eval_baseline(ctx, "B1", extra_cfg=["MATCH_THRESHOLD=0.0"],
                            out_name="nc4_lo")
        sr_hi = hi["secondary"]["serve_rate"]
        sr_lo = lo["secondary"]["serve_rate"]
        if sr_hi <= 0.05 and sr_lo >= 0.95:
            r_pass("C-NC4", "eval", False,
                   f"threshold 0.99 -> serve_rate {sr_hi}; 0.0 -> {sr_lo}",
                   "knob behaves", "SOFT")
        else:
            r_fail("C-NC4", "eval", False,
                   {"hi": sr_hi, "lo": sr_lo},
                   "0.99 -> ~0, 0.0 -> ~1.0", "SOFT")
    except Exception as e:  # noqa: BLE001
        r_fail("C-NC4", "eval", False, str(e), "threshold knob runs")


# --------------------------------------------------------------------------
# Phase wiring
# --------------------------------------------------------------------------

PHASES = {
    "ingest": [("C-L3", chk_l3), ("C-L4", chk_l4),
               ("C-IN1", chk_in), ("C-IN2", chk_in), ("C-IN3", chk_in),
               ("C-IN4", chk_in), ("C-IN5", chk_in), ("C-IN6", chk_in),
               ("C-IN7", chk_in)],
    "extract": [("C-L2", chk_l2), ("C-EX1", chk_ex), ("C-EX2", chk_ex),
                ("C-EX3", chk_ex), ("C-EX4", chk_ex), ("C-EX5", chk_ex),
                ("C-EX6", chk_ex6), ("C-EX7", chk_ex7), ("C-EX8", chk_ex8),
                ("C-EX9", chk_ex9), ("C-EX11", chk_ex11),
                ("C-EX12", chk_ex12)],
    "cluster": [("C-CL1", chk_cl1), ("C-CL2", chk_cl), ("C-CL3", chk_cl),
                ("C-CL4", chk_cl), ("C-CL5", chk_cl), ("C-CL6", chk_cl),
                ("C-CL6", chk_cl6_freshness), ("C-CL7", chk_cl),
                ("C-CL8", chk_cl), ("C-CL9", chk_cl), ("C-CL10", chk_cl10),
                ("C-CL11", chk_cl), ("C-PR1", chk_pr), ("C-PR2", chk_pr),
                ("C-PR3", chk_pr3), ("C-PR4", chk_pr)],
    "serve": [("C-SV1", chk_sv), ("C-SV2", chk_sv), ("C-SV3", chk_sv),
              ("C-SV4", chk_sv), ("C-SV5", chk_sv), ("C-SV6", chk_sv),
              ("C-SV7", chk_sv), ("C-SV8", chk_sv), ("C-SV9", chk_sv),
              ("C-FB1", chk_fb), ("C-FB2", chk_fb), ("C-FB3", chk_fb),
              ("C-FB4", chk_fb)],
    "eval": [("C-L1", chk_l1), ("C-L5", chk_l5), ("C-EV1", chk_ev),
             ("C-EV2", chk_ev), ("C-EV3", chk_ev34), ("C-EV4", chk_ev34),
             ("C-EV5", chk_ev5), ("C-EV6", chk_ev6), ("C-EV7", chk_ev),
             ("C-EV8", chk_ev), ("C-EV9", chk_ev), ("C-EV10", chk_ev),
             ("C-EX10", chk_ex10),
             ("C-NC1", chk_nc), ("C-NC2", chk_nc), ("C-NC3", chk_nc),
             ("C-NC4", chk_nc)],
}

ALL_IDS = ["C-L1", "C-L2", "C-L3", "C-L4", "C-L5",
           "C-IN1", "C-IN2", "C-IN3", "C-IN4", "C-IN5", "C-IN6", "C-IN7",
           "C-EX1", "C-EX2", "C-EX3", "C-EX4", "C-EX5", "C-EX6", "C-EX7",
           "C-EX8", "C-EX9", "C-EX10", "C-EX11", "C-EX12",
           "C-CL1", "C-CL2", "C-CL3", "C-CL4", "C-CL5", "C-CL6", "C-CL7",
           "C-CL8", "C-CL9", "C-CL10", "C-CL11",
           "C-PR1", "C-PR2", "C-PR3", "C-PR4",
           "C-SV1", "C-SV2", "C-SV3", "C-SV4", "C-SV5", "C-SV6", "C-SV7",
           "C-SV8", "C-SV9",
           "C-FB1", "C-FB2", "C-FB3", "C-FB4",
           "C-EV1", "C-EV2", "C-EV3", "C-EV4", "C-EV5", "C-EV6", "C-EV7",
           "C-EV8", "C-EV9", "C-EV10",
           "C-NC1", "C-NC2", "C-NC3", "C-NC4"]


def main():
    ap = argparse.ArgumentParser(description="Layer-1 contract harness")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--phase", required=True,
                    choices=list(PHASES) + ["all"])
    ap.add_argument("--stage", default=None)
    ap.add_argument("--fixtures", default=os.path.join(H1_DIR, "fixtures"))
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()

    ctx = Ctx(args.run_dir, args.stage, args.fixtures, args.model,
              args.base_url, args.api_key)
    if not ctx.model:
        ctx.model = ctx.manifest.get("extract_model")
    # checks_work is disposable scratch: a fresh harness invocation must not
    # inherit state from a previous one (stale stores break extract/cluster
    # idempotency — a re-extract would wipe a shared canonical's members).
    if os.path.isdir(ctx.work):
        shutil.rmtree(ctx.work)
    os.makedirs(ctx.work, exist_ok=True)

    phases = list(PHASES) if args.phase == "all" else [args.phase]
    for phase in phases:
        seen_fns = set()
        for cid, fn in PHASES[phase]:
            if fn in seen_fns:
                continue  # one fn serves several check ids; run it once
            seen_fns.add(fn)
            try:
                fn(ctx)
            except Exception as e:  # noqa: BLE001
                record(cid, phase, True, False, str(e)[:300],
                       "check runs without error",
                       f"exception in {fn.__name__}")

    # merge into checks.json
    checks_path = os.path.join(args.run_dir, "checks.json")
    existing = H.read_jsonl(checks_path) if os.path.exists(checks_path) else []
    by_id = {c["check_id"]: c for c in existing}
    for r in RESULTS:
        by_id[r["check_id"]] = r
    merged = [by_id[cid] for cid in ALL_IDS if cid in by_id]
    H.write_jsonl(checks_path, merged, mode="w")

    hard_failed = [c for c in merged if c["hard"] and not c["passed"]]
    missing = [cid for cid in ALL_IDS if cid not in by_id]
    if missing and args.phase == "all":
        hard_failed.append({"check_id": f"missing:{missing[:3]}"})
    summary = {
        "phase": args.phase,
        "hard_passed": sum(1 for c in merged if c["hard"] and c["passed"]),
        "hard_failed": len(hard_failed),
        "soft_warnings": sum(1 for c in merged
                             if not c["hard"] and not c["passed"]),
        "total_ids": len(merged),
        "missing_ids": missing,
    }
    print(json.dumps(summary, indent=2))
    if hard_failed:
        print("HARD FAILURES:",
              json.dumps([c["check_id"] for c in hard_failed]))
        sys.exit(1)


if __name__ == "__main__":
    main()
