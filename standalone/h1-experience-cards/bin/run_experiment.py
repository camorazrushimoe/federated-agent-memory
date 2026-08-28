#!/usr/bin/env python3
"""run_experiment.py — one command, one run dir, one manifest (RUN-PROTOCOL §1).

Usage:
  python bin/run_experiment.py --pool data/abcd_1000_pool.jsonl \
      --holdout data/abcd_200_holdout.jsonl --model <model> \
      --stage S2 --out runs/<run_id>
  python bin/run_experiment.py --replay <run_id> --out runs/<run_id>__replay
  python bin/run_experiment.py ... --baseline B0|B1|B2

Everything the runner does is tick.py -> cluster (natural 100-chat cursor) ->
per-hold-out serve.py -> eval.py. No new pipeline logic lives here.

Stage slices (EVAL-PLAN §9):
  S0: store = first 16 pool rows, scoring = last 4 pool rows (20 total)
  S1: store = first 200 pool rows, scoring = pool rows 200..239 (pool tail)
  S2: store = all 1000 pool rows, scoring = the frozen 200 hold-out
The hold-out file is NEVER opened in S0/S1 (C-L5, proven by access.log).

Model, base URL and API key come from --model / --base-url / --api-key or the
H1_BASE_URL / H1_API_KEY environment variables — no literals in bin/ (D8).
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1lib as H  # noqa: E402

BIN = os.path.dirname(os.path.abspath(__file__))
# bin/ -> standalone/h1-experience-cards -> repo root
REPO_ROOT = os.path.dirname(os.path.dirname(BIN))

STAGE_STORE = {"S0": 16, "S1": 200, "S2": 1000}
STAGE_SCORE = {"S0": 4, "S1": 40, "S2": 200}
CHUNK = 100  # CLUSTER_EVERY_N_CHATS cadence for natural cluster passes


def log_access(run_dir, line):
    with open(os.path.join(run_dir, "access.log"), "a",
              encoding="utf-8") as f:
        f.write(line + "\n")


def git_commit_info():
    try:
        head = subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        status = subprocess.run(["git", "-C", REPO_ROOT, "status",
                                 "--porcelain"], capture_output=True,
                                text=True).stdout
        dirty_lines = [l for l in status.splitlines()
                       if not l.startswith("?? runs/")]
        dirty = bool(dirty_lines)
        return {"git_commit": head, "dirty": dirty,
                "dirty_reason": "; ".join(dirty_lines[:5]) or None}
    except Exception as e:  # noqa: BLE001
        return {"git_commit": None, "dirty": None, "dirty_reason": str(e)}


def run_script(script, args, cwd=None):
    r = subprocess.run([sys.executable, os.path.join(BIN, script)] + args,
                       capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        sys.stderr.write(f"--- {script} stderr ---\n{r.stderr}")
        raise SystemExit(f"run_experiment: {script} failed rc="
                         f"{r.returncode}")
    return r.stdout.strip()


def run_checks_phase(run_dir, phase, stage, model, base_url, api_key):
    """Call the Layer-1 harness for a phase; HARD failures abort the run."""
    cmd = ["--run-dir", run_dir, "--phase", phase, "--stage", stage,
           "--model", model]
    if base_url:
        cmd += ["--base-url", base_url]
    if api_key:
        cmd += ["--api-key", api_key]
    r = subprocess.run([sys.executable, os.path.join(BIN, "run_checks.py")]
                       + cmd, capture_output=True, text=True)
    sys.stderr.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(
            f"run_experiment: HARD check failure at phase {phase} — the run "
            f"publishes no L2/L3 numbers (see checks.json)")


def checks_enabled(args):
    return not args.no_checks


def main():
    ap = argparse.ArgumentParser(description="Run the H1 experiment (RUN-PROTOCOL)")
    ap.add_argument("--pool", default=None)
    ap.add_argument("--holdout", default=None)
    ap.add_argument("--model", default=None,
                    help="extract model id — required (no default in bin/), "
                         "unless --replay supplies it from the original "
                         "manifest (D8 quickstart)")
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--stage", default=None, choices=["S0", "S1", "S2"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--replay", default=None,
                    help="run_id to replay (recorded extract responses, zero "
                         "LLM calls)")
    ap.add_argument("--baseline", choices=["B0", "B1", "B2"], default=None)
    ap.add_argument("--timeline", choices=["compressed", "aged"],
                    default="compressed")
    ap.add_argument("--agent-pool-size", type=int, default=4)
    ap.add_argument("--force-cluster", action="store_true")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--config", action="append", default=[])
    ap.add_argument("--at", default=None)
    ap.add_argument("--now", default=None)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--no-checks", action="store_true",
                    help="skip the run_checks harness (used by C-EV6's "
                         "mini-replay, never for a published run)")
    ap.add_argument("--package-baselines", action="store_true",
                    help="after the T arm, run B0/B1/B2 through the same "
                         "scoring path and write metrics_B0/B1/B2.json + "
                         "per_dialogue_B0/B1/B2.jsonl into the run dir "
                         "(DELIVERABLE-PACKAGE.md §4 reference-run layout)")
    args = ap.parse_args()

    run_id = os.path.basename(os.path.normpath(args.out))
    if not run_id:
        raise SystemExit("--out must name the run dir (run_id = basename)")
    if os.path.exists(args.out) and os.listdir(args.out):
        raise SystemExit(
            f"refusing to start: output dir exists and is non-empty "
            f"({args.out}) — the runner never reuses a run dir")

    cfg = H.load_config(args.config)
    os.makedirs(args.out, exist_ok=True)
    data_dir = os.path.join(args.out, "data")
    os.makedirs(data_dir, exist_ok=True)
    replay_of = args.replay
    metrics_run_id = None  # set when replaying; carries the root run id
    base_url = args.base_url or os.environ.get("H1_BASE_URL")
    api_key = args.api_key or os.environ.get("H1_API_KEY")

    if args.replay:
        src = os.path.join("runs", args.replay)
        if not os.path.isdir(src):
            # also try the given path verbatim
            src = args.replay if os.path.isdir(args.replay) else None
        if not src:
            raise SystemExit(f"--replay: cannot find run dir for {args.replay}")
        old = H.load_json(os.path.join(src, "manifest.json"))
        # infer inputs/stage/model from the original run (D8 quickstart:
        # `run_experiment.py --replay <run_id>` must work with no other args)
        def resolve_input(p):
            if not p:
                return None
            if os.path.exists(p):
                return p
            # manifest stores paths relative to the h1 folder (fresh-clone
            # replay): resolve against the checkout, then against CWD
            cand = os.path.join(H.H1_DIR, p)
            if os.path.exists(cand):
                return cand
            return p
        if not args.pool and old.get("inputs", {}).get("pool", {}).get(
                "path"):
            args.pool = resolve_input(old["inputs"]["pool"]["path"])
        if not args.holdout and old.get("inputs", {}).get("holdout"):
            args.holdout = resolve_input(old["inputs"]["holdout"]["path"])
        if not args.stage and old.get("stage"):
            args.stage = old["stage"]
        if not args.model and old.get("extract_model"):
            args.model = old["extract_model"]
        # carry the original run's determinism parameters
        for k in ("timeline", "agent_pool_size", "temperature", "max_tokens"):
            if k in old:
                setattr(args, k, old[k])
        cfg["t0"] = old.get("config", {}).get("t0", cfg["t0"])
        cfg["now_override"] = old.get("config", {}).get("now_override",
                                                        cfg["now_override"])
        if not args.at:
            args.at = old.get("at")
        if not args.now:
            args.now = old.get("now")
        t0 = cfg["t0"]
        replay_dir = os.path.join(src, "raw", "extract")
        if not os.path.isdir(replay_dir):
            raise SystemExit(f"--replay: no raw/extract in {src}")
        # metrics.json must be byte-identical on replay, including run_id.
        # Walk the replay chain to the ORIGINAL run id (a replay of a replay
        # must still carry the root id — C-EV6).
        try:
            src_metrics = H.load_json(os.path.join(src, "metrics.json"))
            metrics_run_id = src_metrics.get("run_id")
        except Exception:  # noqa: BLE001
            metrics_run_id = None
        if not metrics_run_id:
            metrics_run_id = old.get("run_id")
    else:
        t0 = cfg["t0"]
        replay_dir = None
    if not args.stage:
        raise SystemExit("--stage required (S0|S1|S2)")
    if not args.model:
        raise SystemExit("--model required (no default model in bin/ — D8)")
    if not args.pool or not os.path.exists(args.pool):
        raise SystemExit("--pool required (or a replay run that records it)")
    assert args.pool is not None  # guaranteed by the guard above
    now = args.now or cfg.get("now_override") or t0
    at = args.at or now

    # ------------------------------------------------------------------
    # Stage slicing (hold-out opened only at S2 — C-L5)
    # ------------------------------------------------------------------
    n_store = STAGE_STORE[args.stage]
    n_score = STAGE_SCORE[args.stage]

    log_access(args.out, f"opened {os.path.abspath(args.pool)}")
    pool_rows = []
    with open(args.pool, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pool_rows.append(json.loads(line))
    if len(pool_rows) < n_store + n_score:
        raise SystemExit(f"pool has {len(pool_rows)} rows, need "
                         f"{n_store + n_score}")

    store_raw = pool_rows[:n_store]
    if args.stage == "S2":
        log_access(args.out,
                   f"opened {os.path.abspath(args.holdout)}  (once, at S2)")
        score_raw = []
        with open(args.holdout, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    score_raw.append(json.loads(line))
        if len(score_raw) < n_score:
            raise SystemExit(f"holdout has {len(score_raw)} rows, need "
                             f"{n_score}")
        score_raw = score_raw[:n_score]
    else:
        score_raw = pool_rows[n_store:n_store + n_score]

    pool_slice = os.path.join(data_dir, "pool_slice_raw.jsonl")
    score_slice = os.path.join(data_dir, "scoring_slice_raw.jsonl")
    H.write_jsonl(pool_slice, store_raw, mode="w")
    H.write_jsonl(score_slice, score_raw, mode="w")

    # ground truth lives only inside the run dir and only reaches eval.py
    gt_rows = []
    for r in store_raw:
        gt_rows.append({"dialogue_id": f"d-{r['chat_id']}",
                        "unlock_guideline": r["unlock_guideline"]})
    for r in score_raw:
        gt_rows.append({"dialogue_id": f"d-{r['chat_id']}",
                        "unlock_guideline": r["unlock_guideline"]})
    H.write_jsonl(os.path.join(data_dir, "ground_truth_labels.jsonl"),
                  gt_rows, mode="w")

    # ------------------------------------------------------------------
    # Ingest + extract + cluster (chunked at the 100-chat cadence)
    # ------------------------------------------------------------------
    dialogues_path = os.path.join(data_dir, "dialogues.jsonl")
    cards_path = os.path.join(data_dir, "cards.jsonl")
    cluster_passes_fired = 0
    det_t0 = time.monotonic()
    if args.baseline is None:
        chunk_files = []
        for i in range(0, len(store_raw), CHUNK):
            chunk = store_raw[i:i + CHUNK]
            cf = os.path.join(data_dir, f"chunk_{i // CHUNK:03d}_raw.jsonl")
            H.write_jsonl(cf, chunk, mode="w")
            chunk_files.append(cf)
        for i, cf in enumerate(chunk_files):
            delta = os.path.join(data_dir, f"delta_{i:03d}.jsonl")
            cmd = ["--in", cf, "--out", args.out, "--dialogues",
                   dialogues_path, "--cards", cards_path, "--delta-out",
                   delta, "--model", args.model, "--agent-pool-size",
                   str(args.agent_pool_size), "--timeline", args.timeline,
                   "--t0", t0, "--at", at, "--now", now]
            if args.stage == "S0" or args.force_cluster:
                cmd.append("--force-cluster")
            if replay_dir:
                cmd += ["--replay-dir", replay_dir]
            if base_url:
                cmd += ["--base-url", base_url]
            if api_key:
                cmd += ["--api-key", api_key]
            for kv in args.config:
                cmd += ["--config", kv]
            out = run_script("tick.py", cmd)
            for line in out.splitlines():
                s = json.loads(line)
                if s.get("step") == "cluster" and s.get("ran"):
                    cluster_passes_fired += 1

    # ingest the scoring slice (never extracted, never clustered)
    run_script("ingest.py", ["--in", score_slice,
                             "--out", os.path.join(data_dir,
                                                   "holdout_dialogues.jsonl"),
                             "--agent-pool-size", str(args.agent_pool_size),
                             "--timeline", args.timeline, "--t0", t0])

    if checks_enabled(args):
        run_checks_phase(args.out, "ingest", args.stage, args.model,
                         base_url, api_key)
        if args.baseline is None:
            run_checks_phase(args.out, "extract", args.stage, args.model,
                             base_url, api_key)
            run_checks_phase(args.out, "cluster", args.stage, args.model,
                             base_url, api_key)

    # ------------------------------------------------------------------
    # Serve (T arm only)
    # ------------------------------------------------------------------
    serve_ms = []
    packets_dir = os.path.join(args.out, "packets")
    os.makedirs(packets_dir, exist_ok=True)
    served_records = []
    if args.baseline is None:
        holdout_dialogues = H.read_jsonl(os.path.join(
            data_dir, "holdout_dialogues.jsonl"))
        for d in holdout_dialogues:
            one = os.path.join(data_dir, "one.json")
            H.write_json(one, d)
            t0s = time.monotonic()
            out = run_script("serve.py", ["--dialogue", one, "--cards",
                                          cards_path, "--at", at,
                                          "--config", "MAX_PACKET=3"])
            serve_ms.append(int((time.monotonic() - t0s) * 1000))
            res = json.loads(out)
            served_records.append({
                "dialogue_id": d["dialogue_id"],
                "card_ids": res["card_ids"],
                "scores": res["scores"],
                "packet_text": res["packet_text"],
            })
            with open(os.path.join(packets_dir,
                                   f"{d['dialogue_id']}.txt"), "w",
                      encoding="utf-8") as f:
                f.write(res["packet_text"])
        H.write_jsonl(os.path.join(packets_dir, "_served.jsonl"),
                      served_records, mode="w")

    # ------------------------------------------------------------------
    # Eval (the same scoring path for T and every baseline — C-EV5)
    # ------------------------------------------------------------------
    arm = args.baseline or "T"
    eval_out = os.path.join(args.out, "metrics.json")
    cmd = ["score", "--pool-dialogues", dialogues_path, "--cards",
           cards_path, "--labels", os.path.join(data_dir,
                                                "ground_truth_labels.jsonl"),
           "--holdout-dialogues", os.path.join(data_dir,
                                               "holdout_dialogues.jsonl"),
           "--packets-dir", packets_dir, "--baseline", arm,
           "--run-id", (metrics_run_id if args.replay else run_id),
           "--out", args.out]
    for kv in args.config:
        cmd += ["--config", kv]
    run_script("eval.py", cmd)

    if checks_enabled(args):
        run_checks_phase(args.out, "serve", args.stage, args.model,
                         base_url, api_key)
        run_checks_phase(args.out, "eval", args.stage, args.model,
                         base_url, api_key)

    # D8 reference-run layout: one metrics file per baseline arm, through the
    # SAME scoring path (eval.py --baseline), zero extra LLM calls
    if args.package_baselines and arm == "T":
        import shutil
        for barm in ("B0", "B1", "B2"):
            tmp = os.path.join(args.out, "baselines", barm)
            os.makedirs(tmp, exist_ok=True)
            cmd = ["score", "--pool-dialogues", dialogues_path, "--cards",
                   cards_path, "--labels", os.path.join(
                       data_dir, "ground_truth_labels.jsonl"),
                   "--holdout-dialogues", os.path.join(
                       data_dir, "holdout_dialogues.jsonl"),
                   "--packets-dir", packets_dir, "--baseline", barm,
                   "--run-id", run_id, "--out", tmp]
            for kv in args.config:
                cmd += ["--config", kv]
            run_script("eval.py", cmd)
            shutil.copy(os.path.join(tmp, "metrics.json"),
                        os.path.join(args.out, f"metrics_{barm}.json"))
            shutil.copy(os.path.join(tmp, "per_dialogue.jsonl"),
                        os.path.join(args.out, f"per_dialogue_{barm}.jsonl"))

    det_wall = time.monotonic() - det_t0

    # ------------------------------------------------------------------
    # cost.json
    # ------------------------------------------------------------------
    cost = build_cost(args.out, raw_dir=os.path.join(args.out, "raw",
                                                     "extract"),
                      serve_ms=serve_ms, det_wall=det_wall,
                      replayed=bool(replay_dir), base_url=base_url)
    H.write_json(os.path.join(args.out, "cost.json"), cost)

    # ------------------------------------------------------------------
    # manifest.json
    # ------------------------------------------------------------------
    prompts_path = os.path.join(H.H1_DIR, "PROMPTS.md")
    # inputs are stored RELATIVE to the h1 folder so a fresh clone can
    # resolve them for --replay (DELIVERABLE-PACKAGE.md §3/§6 — abspaths
    # would break the bare quickstart replay)
    def rel(p):
        return os.path.relpath(p, H.H1_DIR) if p else None
    manifest = {
        "run_id": run_id,
        "created_at": H.now_iso(),
        "stage": args.stage,
        "git_commit": git_commit_info(),
        "extract_model": args.model,
        "judge_model": args.judge_model,
        "base_url": base_url,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "timeline": args.timeline,
        "agent_pool_size": args.agent_pool_size,
        "config": cfg,
        "at": at,
        "now": now,
        "cluster_passes_fired": cluster_passes_fired,
        "inputs": {
            "pool": {"path": rel(args.pool),
                     "sha256": H.sha256_file(args.pool), "rows": len(pool_rows),
                     "used_rows": len(store_raw)},
            "holdout": None if args.stage != "S2" else {
                "path": rel(args.holdout),
                "sha256": H.sha256_file(args.holdout), "rows": n_score},
            "scoring_slice": {"path": rel(score_slice),
                              "sha256": H.sha256_file(score_slice),
                              "rows": len(score_raw)},
            "prompts": {"path": rel(prompts_path),
                        "sha256": H.sha256_file(prompts_path)},
        },
        "outputs": {
            "cards.jsonl": H.sha256_file(cards_path) if os.path.exists(
                cards_path) else None,
            "metrics.json": H.sha256_file(eval_out),
            "per_dialogue.jsonl": H.sha256_file(os.path.join(
                args.out, "per_dialogue.jsonl")),
            **{f"metrics_{b}.json": H.sha256_file(os.path.join(
                args.out, f"metrics_{b}.json"))
               for b in ("B0", "B1", "B2")
               if os.path.exists(os.path.join(args.out, f"metrics_{b}.json"))},
            **{f"per_dialogue_{b}.jsonl": H.sha256_file(os.path.join(
                args.out, f"per_dialogue_{b}.jsonl"))
               for b in ("B0", "B1", "B2")
               if os.path.exists(os.path.join(
                   args.out, f"per_dialogue_{b}.jsonl"))},
        },
        "replay_of": replay_of,
    }
    H.write_json(os.path.join(args.out, "manifest.json"), manifest)

    # ------------------------------------------------------------------
    # report skeleton (numbers; the verdict is the Lead's at S4)
    # ------------------------------------------------------------------
    write_report(args.out, manifest, arm)

    print(json.dumps({
        "run_id": run_id, "stage": args.stage, "arm": arm,
        "cluster_passes_fired": cluster_passes_fired,
        "extract_calls": cost["extract"]["calls"],
        "metrics": H.load_json(eval_out)["primary"],
        "holdout_opened": args.stage == "S2",
    }, ensure_ascii=False, indent=2))


def build_cost(run_dir, raw_dir, serve_ms, det_wall, replayed, base_url):
    calls = prompt_tokens = completion_tokens = 0
    ms_all = []
    if os.path.isdir(raw_dir):
        for fn in sorted(os.listdir(raw_dir)):
            if not fn.endswith(".json"):
                continue
            rec = H.load_json(os.path.join(raw_dir, fn))
            if rec.get("error") and not rec.get("usage"):
                continue
            calls += 1
            u = rec.get("usage") or {}
            prompt_tokens += u.get("prompt_tokens", 0)
            completion_tokens += u.get("completion_tokens", 0)
            ms_all.append(rec.get("ms", 0))
    def pct(xs, p):
        if not xs:
            return 0
        s = sorted(xs)
        return s[min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))]
    return {
        "extract": {
            "calls": calls,
            "live_llm_calls": 0 if replayed else calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "usd_total": None,
            "usd_per_1000_dialogues": None,
            "ms_p50": pct(ms_all, 50),
            "ms_p95": pct(ms_all, 95),
        },
        "serve": {"ms_p50": pct(serve_ms, 50), "ms_p95": pct(serve_ms, 95)},
        "deterministic_half_wall_clock_s": round(det_wall, 3),
        "price_source": ("no published rate for the run's extract model at "
                         "run time; usd_total=null per RUN-PROTOCOL §4.3 "
                         "(C-EV9)"),
        "replayed": replayed,
        "base_url": base_url,
    }


def write_report(run_dir, manifest, arm):
    m = H.load_json(os.path.join(run_dir, "metrics.json"))
    checks_path = os.path.join(run_dir, "checks.json")
    checks_txt = "no checks.json yet"
    if os.path.exists(checks_path):
        checks = H.load_json(checks_path)
        hard = [c for c in checks if c["hard"]]
        failed = [c for c in hard if not c["passed"]]
        checks_txt = (f"HARD {len(hard) - len(failed)}/{len(hard)} passed, "
                      f"soft warnings: "
                      f"{sum(1 for c in checks if not c['hard'] and not c['passed'])}")
    audit_txt = "audit.json not present (D3)"
    if os.path.exists(os.path.join(run_dir, "audit.json")):
        audit_txt = "audit.json present (A1-A5)"
    cost = H.load_json(os.path.join(run_dir, "cost.json"))
    lines = [
        f"# Run {manifest['run_id']}",
        "",
        f"- stage: {manifest['stage']}, arm: {arm}, model: "
        f"{manifest['extract_model']}, timeline: {manifest['timeline']}, "
        f"agent_pool_size: {manifest['agent_pool_size']}",
        f"- git: {manifest['git_commit']['git_commit']} "
        f"(dirty={manifest['git_commit']['dirty']})",
        f"- replay_of: {manifest['replay_of']}",
        "",
        "## Checks",
        checks_txt,
        "",
        "## Audit",
        audit_txt,
        "",
        "## Primary",
        f"- unlock_hit_label: {m['primary']['unlock_hit_label']}",
        f"- wrong: {m['primary']['wrong']} (weighted above misses)",
        f"- abstain: {m['primary']['abstain']}",
        f"- n_holdout: {m['n_holdout']}",
        "- baselines: B0/B1/B2 measured in their own run dirs (D4); T alone "
        "is not a result",
        "",
        "## Secondary",
        f"- serve_rate: {m['secondary']['serve_rate']}",
        f"- extract_yield: {m['secondary']['extract_yield']}",
        f"- reject_rate: {m['secondary']['reject_rate']}",
        f"- cluster_rate: {m['secondary']['cluster_rate']}",
        f"- shared_rate: {m['secondary']['shared_rate']}",
        f"- cluster_purity: {m['secondary']['cluster_purity']}",
        f"- unlock_conflict: {m['secondary']['unlock_conflict']}",
        f"- duplicate_in_packet: {m['secondary']['duplicate_in_packet']}",
        f"- scope_leak: {m['secondary']['scope_leak']}",
        f"- independence: {m['secondary']['independence']}",
        f"- votes_hist: {m['secondary']['votes_hist']}",
        f"- packet_size_hist: {m['secondary']['packet_size_hist']}",
        "",
        "## Cost",
        f"- extract calls: {cost['extract']['calls']}, prompt tokens: "
        f"{cost['extract']['prompt_tokens']}, completion tokens: "
        f"{cost['extract']['completion_tokens']}",
        f"- usd_total: {cost['extract']['usd_total']} "
        f"(price_source: {cost['price_source']})",
        f"- extract ms p50/p95: {cost['extract']['ms_p50']}/"
        f"{cost['extract']['ms_p95']}",
        f"- deterministic half wall clock: "
        f"{cost['deterministic_half_wall_clock_s']}s",
        "",
        "## Verdict",
        "Verdict is the Lead's at S4 (EVAL-PLAN §6.4). This run publishes "
        "numbers only if checks.json is green.",
        "",
        "## Honesty clause",
        "age-stale is off by construction under timeline=compressed "
        "(stated next to every metric); independence mode as reported above.",
    ]
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
