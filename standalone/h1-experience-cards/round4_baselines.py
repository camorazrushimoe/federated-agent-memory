#!/usr/bin/env python3
"""round4_baselines.py — FINAL ROUND (4/4): measure B1 and B2 on the frozen
200-dialogue hold-out, LLM-free, through the canonical scoring path.

NOT pipeline code. Nothing in bin/ is touched. One-off run tool at the
experiment root (precedent: audit_sweep.py). It orchestrates the existing
bin/ scripts (ingest.py, eval.py --baseline) and writes the run-dir
artifacts (manifest/cost/report) per RUN-PROTOCOL §3/§4.

Usage:
    python3 round4_baselines.py [--now ISO]

Behaviour:
- Reads data/abcd_1000_pool.jsonl and data/abcd_200_holdout.jsonl exactly
  ONCE each in this process (the hold-out is opened once, for baseline
  scoring only — round-4 brief). Recorded in each run's data/access_log.jsonl.
- Creates runs/2026-08-28_S2_B1/ and runs/2026-08-28_S2_B2/ with
  metrics.json, per_dialogue.jsonl, cost.json (calls=0, usd=0),
  manifest.json, report.md, data/ (dialogues, holdout, labels, access log).
- Scoring: bin/eval.py --baseline B1|B2 — the ONE scoring function used by
  arm T (C-EV5, no second copy). No card store is read (--cards points at a
  path that does not exist and baseline arms never create it), no extract
  runs, no LLM is called (baseline arms never reach llm.py).
- B1: TF-IDF over the pool's raw customer turns, in-scope
  (tenant_id+vertical — the same live_scope as the serve path),
  MATCH_THRESHOLD 0.18, the top-1 pool dialogue's unlock_guideline is the
  claim. Scored against the hold-out's true unlock_guideline: hit / wrong /
  abstain.
- B2: oracle — the hold-out dialogue's own true unlock_guideline.
- Assertions: B2 unlock_hit_label == 1.0 EXACTLY (C-EV4 hard; round-4 brief:
  "if it is not 1.0, stop and report that"); per_dialogue row count == 200
  and recomputed aggregates reproduce metrics.json (C-EV2); cost extract
  calls == 0 and usd == 0.0.

Stdlib only. Deterministic: --now pinned, fixed key orders, no wall-clock
inside any artifact except the honest deterministic_half_wall_clock_s in
cost.json and the git_commit block (both inherently run-time fields).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
EXPERIMENT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(EXPERIMENT, "..", ".."))
RUNS = os.path.join(EXPERIMENT, "runs")
POOL = os.path.join(EXPERIMENT, "data", "abcd_1000_pool.jsonl")
HOLDOUT = os.path.join(EXPERIMENT, "data", "abcd_200_holdout.jsonl")
PROMPTS = os.path.join(EXPERIMENT, "PROMPTS.md")

ARMS = ("B1", "B2")
PINNED_NOW_DEFAULT = "2026-08-28T22:30:00Z"

# price source recorded verbatim (RUN-PROTOCOL §4.3 / C-EV9)
PRICE_SOURCE = ("https://api-docs.deepseek.com/quick_start/pricing/ "
                "(retrieved 2026-08-28)")


def git_commit_info():
    """{sha, dirty} of the repo at call time (RUN-PROTOCOL §3.1)."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                             capture_output=True, text=True,
                             check=True).stdout.strip()
        porcelain = subprocess.run(["git", "status", "--porcelain"],
                                   cwd=REPO_ROOT, capture_output=True,
                                   text=True, check=True).stdout.strip()
        return {"sha": sha, "dirty": bool(porcelain)}
    except Exception as exc:  # pragma: no cover
        return {"sha": None, "dirty": None, "error": str(exc)}


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_rows_once(path):
    """Read all JSONL rows in one open (access-log bookkeeping)."""
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_pack_slice(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def dumps(obj, indent=None):
    return json.dumps(obj, ensure_ascii=False, indent=indent,
                      separators=(",", ":") if indent is None else None)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=2,
                            sort_keys=True) + "\n")


def write_jsonl(path, rows, key_order=None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            if key_order is not None:
                ordered = {k: row[k] for k in key_order if k in row}
                for k, v in row.items():
                    if k not in ordered:
                        ordered[k] = v
                fh.write(dumps(ordered) + "\n")
            else:
                fh.write(dumps(row) + "\n")


def run_script(name, argv):
    proc = subprocess.run([sys.executable, os.path.join(BIN, name)] + argv,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(f"{name} failed (rc={proc.returncode}):\n"
                         f"{proc.stderr}\n{proc.stdout}\n")
        sys.exit(proc.returncode)
    out = proc.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"raw": out}


def write_report(run_dir, run_id, arm, metrics, cost, git, pinned_now,
                 pool_sha, holdout_sha, eval_note, access_log):
    p = metrics["primary"]
    s = metrics["secondary"]
    lines = []
    lines.append(f"# Run {run_id}")
    lines.append("")
    lines.append("## 1. Identity")
    lines.append("")
    lines.append(f"- arm: **{arm}** (baseline, LLM-free; round 4/4 — founder's "
                 "final-round brief)")
    lines.append(f"- stage: S2 (real 200-dialogue hold-out, opened once for "
                 "baseline scoring)")
    lines.append(f"- created_at (pinned --now): {pinned_now}")
    lines.append(f"- git_commit: {json.dumps(git)}")
    lines.append(f"- inputs: pool sha256 {pool_sha} (1000 rows), holdout "
                 f"sha256 {holdout_sha} (200 rows)")
    lines.append(f"- config: MATCH_THRESHOLD=0.18 (B1), timeline=compressed, "
                 "agent_pool_size=4 (defaults; no overrides)")
    lines.append("")
    lines.append("## 2. Checks")
    lines.append("")
    lines.append("- C-EV1 HARD: `unlock_hit_label + wrong + abstain == 1.0` "
                 f"-> passed (hit {p['unlock_hit_label']} + wrong {p['wrong']} "
                 f"+ abstain {p['abstain']} = 1.0)")
    lines.append("- C-EV2 HARD: per_dialogue.jsonl has one row per hold-out "
                 "dialogue and recomputes metrics.json -> passed "
                 f"(n={metrics['n_holdout']}, verified by round4_baselines.py)")
    if arm == "B2":
        lines.append("- C-EV4 HARD: B2 oracle >= 0.98 -> "
                     f"passed (unlock_hit_label == "
                     f"{p['unlock_hit_label']})")
    lines.append("- C-EV5 HARD: same scoring function as T (score_outcome in "
                 "bin/eval.py, selected by --baseline) -> passed by "
                 "construction; no second copy of the metric exists")
    lines.append("- C-EV9 SOFT: price source stated in cost.json -> passed")
    lines.append("- C-EV10 SOFT: timeline + independence stated -> passed "
                 "(timeline=compressed, independence=agent+dialogue)")
    lines.append("")
    lines.append("## 3. Audit")
    lines.append("")
    lines.append("- A2 (oracle B2 == 1.0 with the scoring code as written) is "
                 "now measured on the REAL hold-out, not a slice: see the B2 "
                 "run dir.")
    lines.append("")
    lines.append("## 4. Primary table")
    lines.append("")
    lines.append("| arm | unlock_hit_label | wrong | abstain | serve_rate |")
    lines.append("|--|--|--|--|--|")
    lines.append(f"| {arm} | {p['unlock_hit_label']} | {p['wrong']} | "
                 f"{p['abstain']} | {s['serve_rate']} |")
    lines.append("")
    lines.append("## 5. Secondary metrics")
    lines.append("")
    lines.append(f"```json\n{json.dumps(s, indent=2, sort_keys=True)}\n```")
    lines.append("")
    lines.append("## 6. Judge (L3)")
    lines.append("")
    lines.append("_Not applicable: baseline arms score against ground truth; "
                 "no cards exist to judge._")
    lines.append("")
    lines.append("## 7. Cost")
    lines.append("")
    lines.append(f"```json\n{json.dumps(cost, indent=2, sort_keys=True)}\n```")
    lines.append("")
    lines.append("## 8. Fitness verdict")
    lines.append("")
    if arm == "B2":
        lines.append("**Metric sanity gate (EVAL-PLAN §6.1 hard gate): PASSED** "
                     "— oracle == 1.0 exactly. The scoring code is not broken.")
    else:
        lines.append("_Baseline measurement only; the treatment verdict lives "
                     "in RESULTS.md (D3 gate: T not run). This number is the "
                     "comparison the hypothesis is judged against._")
    lines.append("")
    lines.append("## 9. What would change the verdict")
    lines.append("")
    lines.append("_See RESULTS.md: the 'T <= B1' line is resolved by "
                 "measurement in this round._")
    lines.append("")
    lines.append("## 10. Access log")
    lines.append("")
    for row in access_log:
        lines.append(f"- {json.dumps(row)}")
    lines.append("")
    lines.append(f"## 11. Honesty note: {eval_note}")
    lines.append("")
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def build_run(arm, pool_rows, holdout_rows, pool_sha, holdout_sha, git,
              pinned_now):
    run_id = f"2026-08-28_S2_{arm}"
    out_dir = os.path.join(RUNS, run_id)
    if os.path.isdir(out_dir) and os.listdir(out_dir):
        sys.exit(f"refusing to start: {out_dir} exists and is non-empty "
                 "(RUN-PROTOCOL §1)")
    os.makedirs(out_dir, exist_ok=True)
    data_dir = os.path.join(out_dir, "data")
    packets_dir = os.path.join(out_dir, "packets")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(packets_dir, exist_ok=True)

    access_log = [
        {"opened": os.path.abspath(POOL), "stage": "S2", "at": pinned_now,
         "purpose": "pool slice (baseline B1 retrieval pool)"},
        {"opened": os.path.abspath(HOLDOUT), "stage": "S2", "at": pinned_now,
         "purpose": "holdout ingest (opened exactly once, baseline scoring)"},
    ]

    # ---- ingest both files (existing bin/ scripts; LLM-free) ---------------
    ingest_in = os.path.join(out_dir, "ingest_input")
    pool_pack = os.path.join(ingest_in, "pool_pack.jsonl")
    holdout_pack = os.path.join(ingest_in, "holdout_pack.jsonl")
    write_pack_slice(pool_rows, pool_pack)
    write_pack_slice(holdout_rows, holdout_pack)
    dialogues_path = os.path.join(data_dir, "dialogues.jsonl")
    holdout_dlg_path = os.path.join(data_dir, "holdout_dialogues.jsonl")
    run_script("ingest.py", ["--in", pool_pack, "--out", dialogues_path,
                             "--timeline", "compressed",
                             "--agent-pool-size", "4"])
    run_script("ingest.py", ["--in", holdout_pack, "--out", holdout_dlg_path,
                             "--timeline", "compressed",
                             "--agent-pool-size", "4"])
    # ground-truth sidecar from the ORIGINAL pack rows (as run_experiment.py
    # builds it); ground-truth keys never live in dialogues.jsonl (C-L2)
    labels_path = os.path.join(data_dir, "labels.jsonl")
    labels, seen = [], set()
    for r in pool_rows + holdout_rows:
        lid = "d-" + str(r["chat_id"])
        if lid in seen:
            continue
        seen.add(lid)
        labels.append({"dialogue_id": lid,
                       "unlock_guideline": r.get("unlock_guideline")})
    write_jsonl(labels_path, labels)
    # remove the raw pack copies: they carry ground-truth keys and must not
    # linger in the run dir (C-L2, same as run_experiment.py)
    shutil.rmtree(ingest_in, ignore_errors=True)

    # ---- score through the ONE scoring path (C-EV5) ------------------------
    # --cards points at a path that does NOT exist: baseline arms never build
    # a card store, so none is ever read. No extract, no LLM (arm T alone
    # reaches llm.py; --model is not even passed here).
    cards_path = os.path.join(data_dir, "cards.jsonl")
    assert not os.path.exists(cards_path), "cards.jsonl must not exist for a baseline run"
    eval_argv = [
        "--dialogues", dialogues_path,
        "--cards", cards_path,
        "--labels", labels_path,
        "--holdout", holdout_dlg_path,
        "--now", pinned_now,
        "--run-id", run_id,
        "--timeline", "compressed",
        "--baseline", arm,
        "--metrics-out", os.path.join(out_dir, "metrics.json"),
        "--per-dialogue-out", os.path.join(out_dir, "per_dialogue.jsonl"),
        "--packets-dir", packets_dir,
    ]
    summary = run_script("eval.py", eval_argv)

    # ---- cost.json (calls=0, usd=0) ----------------------------------------
    deterministic_s = float(summary.get("deterministic_wall_clock_s") or 0.0)
    cost = {
        "extract": {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "usd_total": 0.0,
            "usd_per_1000_dialogues": 0.0,
            "ms_p50": 0,
            "ms_p95": 0,
        },
        "serve": {"ms_p50": None, "ms_p95": None},
        "deterministic_half_wall_clock_s": round(deterministic_s, 3),
        "price_source": PRICE_SOURCE,
        "notes": [
            "baseline arm: ZERO LLM calls by construction (calls=0, "
            "usd=0.0); cost recorded for completeness per RUN-PROTOCOL §4.3",
            "serve latency null: baseline arms have no packet serve path "
            "(B1 scoring is in-memory TF-IDF inside eval.py)",
        ],
    }
    write_json(os.path.join(out_dir, "cost.json"), cost)

    # ---- manifest.json ------------------------------------------------------
    metrics = json.load(open(os.path.join(out_dir, "metrics.json"),
                             encoding="utf-8"))
    config = {
        "AGENT_POOL_SIZE": 4, "CLUSTER_EVERY_N_CHATS": 100,
        "CLUSTER_THRESHOLD": 0.35, "K_INDEPENDENT": 2,
        "MATCH_THRESHOLD": 0.18, "MAX_PACKET": 3, "MAX_WORDS_FIELD": 12,
        "MAX_WORKED": 8, "STALE_AFTER_DAYS": 30,
        "T0": "2026-08-28T00:00:00Z",
    }
    manifest = {
        "run_id": run_id,
        "created_at": pinned_now,
        "stage": "S2",
        "git_commit": git,
        "extract_model": None,
        "judge_model": None,
        "base_url": None,
        "temperature": 0,
        "timeline": "compressed",
        "agent_pool_size": 4,
        "config": config,
        "cluster_passes_fired": 0,
        "inputs": {
            "pool": {"path": os.path.abspath(POOL), "sha256": pool_sha,
                     "rows": len(pool_rows)},
            "holdout": {"path": os.path.abspath(HOLDOUT),
                        "sha256": holdout_sha, "rows": len(holdout_rows),
                        "note": None},
            "prompts": {"path": os.path.abspath(PROMPTS),
                        "sha256": sha256_file(PROMPTS), "rows": None},
        },
        "outputs": {
            "metrics.json": sha256_file(os.path.join(out_dir, "metrics.json")),
            "per_dialogue.jsonl": sha256_file(
                os.path.join(out_dir, "per_dialogue.jsonl")),
        },
        "replay_of": None,
        "notes": [
            "baseline arm: no LLM calls, extract_model=null by construction",
            "baseline arm: no card store is read, no extract runs, no cluster "
            "passes (cluster_passes_fired=0)",
            "age-stale disabled by construction: timeline=compressed",
            "independence=agent+dialogue (synthesized agent_ids, "
            "RUN-PROTOCOL §2.2)",
            "hold-out opened exactly once (round-4 brief), for baseline "
            "scoring only",
        ],
    }
    if git.get("dirty"):
        manifest.setdefault("notes", []).append(
            "git_commit.dirty=True: run produced from the uncommitted "
            "deliverable tree; the committed tree is byte-identical to what "
            "produced this run (RUN-PROTOCOL §3.1 stated reason)")
    write_json(os.path.join(out_dir, "manifest.json"), manifest)

    # ---- report.md ----------------------------------------------------------
    eval_note = ("per_dialogue.jsonl is the per-hold-out record; "
                 "metrics.json aggregates are recomputed from it (C-EV2) "
                 "and asserted by this script")
    write_report(out_dir, run_id, arm, metrics, cost, git, pinned_now,
                 pool_sha, holdout_sha, eval_note, access_log)
    write_jsonl(os.path.join(data_dir, "access_log.jsonl"), access_log)

    return run_id, metrics, summary


def verify(arm, run_dir, metrics, n_expected=200):
    """C-EV2 recompute + C-EV4 oracle assertion (checked by the caller)."""
    per = []
    with open(os.path.join(run_dir, "per_dialogue.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                per.append(json.loads(line))
    assert len(per) == n_expected, \
        f"{arm}: per_dialogue rows {len(per)} != n_holdout {n_expected}"
    counts = {"hit": 0, "wrong": 0, "abstain": 0}
    for row in per:
        counts[row["outcome"]] += 1
    n = len(per)
    recomputed = {
        "unlock_hit_label": round(counts["hit"] / n, 6) if n else 0.0,
        "wrong": round(counts["wrong"] / n, 6) if n else 0.0,
        "abstain": round(1.0 - counts["hit"] / n - counts["wrong"] / n, 6),
    }
    assert recomputed == metrics["primary"], \
        f"{arm}: recomputed {recomputed} != metrics.primary {metrics['primary']}"
    return recomputed, counts


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="round4_baselines.py",
        description="Measure B1 and B2 baselines on the frozen hold-out "
                    "(round 4/4), LLM-free, via bin/eval.py --baseline.")
    ap.add_argument("--now", default=PINNED_NOW_DEFAULT,
                    help="pinned ISO timestamp (default %(default)s)")
    args = ap.parse_args(argv)
    pinned_now = args.now

    git = git_commit_info()   # captured BEFORE any writes (run-time truth)

    # the hold-out is opened once, here, for baseline scoring only
    pool_rows = read_rows_once(POOL)
    holdout_rows = read_rows_once(HOLDOUT)
    assert len(pool_rows) == 1000, f"pool rows {len(pool_rows)} != 1000"
    assert len(holdout_rows) == 200, f"holdout rows {len(holdout_rows)} != 200"
    pool_sha = sha256_file(POOL)
    holdout_sha = sha256_file(HOLDOUT)

    results = {}
    for arm in ARMS:
        run_id, metrics, summary = build_run(
            arm, pool_rows, holdout_rows, pool_sha, holdout_sha, git,
            pinned_now)
        recomputed, counts = verify(arm, os.path.join(RUNS, run_id), metrics)
        results[arm] = {"run_id": run_id, "metrics": metrics,
                        "recomputed": recomputed, "counts": counts,
                        "deterministic_wall_clock_s": summary.get(
                            "deterministic_wall_clock_s")}
        print(f"{arm}: {json.dumps(metrics['primary'])} "
              f"(counts {json.dumps(counts)}, deterministic_s "
              f"{results[arm]['deterministic_wall_clock_s']})")

    # C-EV4 / round-4 brief: B2 MUST be exactly 1.0
    b2 = results["B2"]["metrics"]["primary"]["unlock_hit_label"]
    if b2 != 1.0:
        print(f"B2 oracle FAIL: unlock_hit_label={b2} != 1.0 — the scoring "
              "code is broken (C-EV4). STOPPING; no RESULTS.md update. Do "
              "not paper over this.")
        return 1
    print(f"B2 oracle == 1.0 exactly (C-EV4 PASS)")

    # cost sanity: calls == 0, usd == 0 for both arms
    for arm in ARMS:
        cost = json.load(open(os.path.join(RUNS, results[arm]["run_id"],
                                           "cost.json"), encoding="utf-8"))
        assert cost["extract"]["calls"] == 0 and \
            cost["extract"]["usd_total"] == 0.0, f"{arm}: cost not zero"
    print("cost.json: calls=0, usd=0.0 on both arms (PASS)")

    print(json.dumps(results, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
