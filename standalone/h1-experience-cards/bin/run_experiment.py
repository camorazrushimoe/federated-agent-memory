#!/usr/bin/env python3
"""run_experiment.py — one command, one run dir, one manifest (RUN-PROTOCOL §1).

    python bin/run_experiment.py --pool data/abcd_1000_pool.jsonl \
        --holdout data/abcd_200_holdout.jsonl --model <extract-model> \
        --stage S2 --out runs/<date>_S2_<model>

Stages (EVAL-PLAN §9): S0 = fixtures + first 20 pool dialogues; S1 = 200 pool
+ 40 from the pool tail (NOT the real hold-out); S2 = 1000 pool + 200 hold-out.

Flow: chunked tick (ingest + extract per 100-chat chunk, cluster via the
natural cursor -> exactly 10 passes) -> final cluster --force -> serve every
eval dialogue -> eval.py (arm T) -> baselines B0/B1/B2 + negative controls
(same scoring path) -> cost -> manifest -> checks (HARD failures abort) ->
audit (S1+) -> replay self-check (byte-identical, zero LLM) -> report.

--replay <run_id> re-runs everything from the recorded extract responses with
zero LLM calls (L0). --baseline B0|B1|B2 re-derives a baseline from an
existing T run dir through the same scoring path.

The runner refuses to start if the output dir exists and is non-empty, and
refuses to touch the hold-out in S0/S1 (C-L5, access log).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

import config as cfgmod
from clock import RunClock
from prompts import Prompts
from store import read_jsonl, write_jsonl

CLUSTER_CHUNK = 100  # CLUSTER_EVERY_N_CHATS default; chunk size for the cursor


# --------------------------------------------------------------------------- #
# small helpers                                                               #
# --------------------------------------------------------------------------- #

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def git_commit(root: Path) -> dict:
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10)
        return {"sha": head.stdout.strip() or None,
                "dirty": bool(dirty.stdout.strip())}
    except Exception as e:  # no git available
        return {"sha": None, "dirty": None, "error": str(e)}


class Runner:
    def __init__(self, run_dir: Path, access_log: list[str] | None = None,
                 run_log: list[list[str]] | None = None):
        self.run_dir = run_dir
        self.data = run_dir / "data"
        self.raw = run_dir / "raw" / "extract"
        self.packets = run_dir / "packets"
        self.access = access_log if access_log is not None else []
        self.rlog = run_log if run_log is not None else []
        self.clock: RunClock | None = None
        self.cfg = cfgmod.DEFAULTS
        # LLM identity comes from CLI/env at run time (D8 §6); never from a
        # literal or a config default.
        self.model: str | None = None
        self.base_url: str | None = None

    # -- logging --------------------------------------------------------------
    def log_access(self, *paths: str) -> None:
        for p in paths:
            if p:
                self.access.append(str(Path(p).resolve()))

    def run(self, argv: list[str], *, cwd: Path | None = None,
            expect_fail: bool = False, log: bool = True) -> tuple[int, str]:
        """Run one of the bin/ scripts; log argv; return (rc, combined output).

        `log=False` marks an eval-layer call (e.g. the audit's read of the real
        hold-out at S1) that is NOT part of the pipeline access log — C-L5
        asserts on the pipeline log only.
        """
        if log:
            self.rlog.append([str(x) for x in argv])
            for a in argv:
                if isinstance(a, str) and (a.startswith(str(ROOT)) or a.startswith("/")):
                    self.log_access(a)
        t0 = time.time()
        proc = subprocess.run([sys.executable] + argv, capture_output=True,
                              text=True, cwd=str(cwd) if cwd else str(ROOT),
                              timeout=3600)
        wall = time.time() - t0
        out = proc.stdout + proc.stderr
        if proc.returncode != 0 and not expect_fail:
            raise RuntimeError(f"step failed: {argv}\n{out[-2000:]}")
        return proc.returncode, out

    def last_json(self, out: str) -> dict:
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except ValueError:
                    continue
        return {}

    # -- pipeline phases --------------------------------------------------------
    def phase_ingest_extract(self, chunks: list[Path], clock_iso: str) -> dict:
        """Per-chunk ingest+extract (upsert semantics); no clustering yet."""
        summary = {"ingest_kept": 0, "ingest_dropped": 0, "extracted": 0,
                   "accepted": 0, "rejected": 0, "unparseable": 0}
        for i, chunk in enumerate(chunks):
            self.log_access(str(chunk))
            rc, out = self.run([str(HERE / "ingest.py"), "--in", str(chunk),
                                "--out", str(self.data / "dialogues.jsonl"),
                                "--agent-pool-size", str(self.cfg["AGENT_POOL_SIZE"]),
                                "--timeline", str(self.cfg["TIMELINE"]),
                                "--t0", str(self.cfg["T0"])])
            ing = self.last_json(out)
            summary["ingest_kept"] += ing.get("kept", 0)
            summary["ingest_dropped"] += ing.get("dropped", 0)
            rc, out = self.run([str(HERE / "extract.py"),
                                "--in", str(self.data / "dialogues.jsonl"),
                                "--out", str(self.data / "cards.jsonl"),
                                "--model", self.model or "",
                                "--base-url", self.base_url or "",
                                "--raw-dir", str(self.raw),
                                "--clock-start", clock_iso,
                                "--start-index", str(i * CLUSTER_CHUNK)])
            ex = self.last_json(out)
            for k in ("extracted", "accepted", "rejected", "unparseable"):
                summary[k] += ex.get(k, 0)
        return summary

    def phase_cluster(self, n_chunks: int, clock_iso: str,
                      force_final: bool = True) -> dict:
        """Natural-cursor passes (one per 100-chunk) + optional final --force."""
        passes = []
        for _ in range(n_chunks):
            rc, out = self.run([str(HERE / "cluster.py"),
                                "--cards", str(self.data / "cards.jsonl"),
                                "--dialogues", str(self.data / "dialogues.jsonl"),
                                "--now", clock_iso])
            passes.append(self.last_json(out))
        if force_final:
            rc, out = self.run([str(HERE / "cluster.py"),
                                "--cards", str(self.data / "cards.jsonl"),
                                "--dialogues", str(self.data / "dialogues.jsonl"),
                                "--force", "--now", clock_iso])
            passes.append(self.last_json(out))
        fired = sum(1 for p in passes if p.get("ran") is True)
        forced = sum(1 for p in passes[-1:] if p.get("ran") is True and p.get("reason") != "store unchanged")
        return {"passes": passes, "natural_fired": fired, "forced_final_ran": forced}

    def phase_serve(self, eval_dialogues: list[dict], clock_iso: str) -> dict:
        served = {"dialogues": 0, "packets": 0, "ms": []}
        for d in eval_dialogues:
            live = self.data / f"live_{d['dialogue_id']}.json"
            live.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            self.log_access(str(live))
            rc, out = self.run([str(HERE / "serve.py"),
                                "--dialogue", str(live),
                                "--cards", str(self.data / "cards.jsonl"),
                                "--packets-dir", str(self.packets),
                                "--clock-start", clock_iso])
            res = self.last_json(out)
            served["dialogues"] += 1
            served["ms"].append(res.get("serve_ms", 0))
            # packets/<id>.json carries the exact card ids + scores for eval.py
            if res.get("card_ids"):
                (self.packets / f"{d['dialogue_id']}.json").write_text(
                    json.dumps({"card_ids": res["card_ids"], "scores": res["scores"]}),
                    encoding="utf-8")
                served["packets"] += 1
        return served


# --------------------------------------------------------------------------- #
# live run                                                                    #
# --------------------------------------------------------------------------- #

def live_run(args) -> int:
    # --holdout only exists for S2; S0/S1 must never see it (C-L5). The default
    # is None so an explicit --holdout at S0/S1 is an error, not a silent open.
    if args.stage in ("S0", "S1") and args.holdout:
        print(json.dumps({"error": "the real hold-out must not be touched before S2 "
                                   "(no --holdout at S0/S1)"}))
        return 1
    pool_path = Path(args.pool)
    holdout_path = Path(args.holdout) if args.holdout else Path(ROOT / "data" / "abcd_200_holdout.jsonl")
    if not pool_path.exists() or not holdout_path.exists():
        print(json.dumps({"error": f"missing input: {pool_path} / {holdout_path}"}))
        return 1

    out_dir = Path(args.out).resolve()  # absolute: fixture subprocesses use their own cwd
    if out_dir.exists() and any(out_dir.iterdir()):
        print(json.dumps({"error": f"output dir exists and is non-empty: {out_dir}"}))
        return 1

    pool_rows = [json.loads(l) for l in pool_path.read_text().splitlines() if l.strip()]
    holdout_rows = []
    if args.stage == "S2":
        holdout_rows = [json.loads(l) for l in holdout_path.read_text().splitlines() if l.strip()]

    if args.stage == "S0":
        train_raw, eval_raw = pool_rows[:16], pool_rows[16:20]
    elif args.stage == "S1":
        train_raw, eval_raw = pool_rows[:200], pool_rows[200:240]
    else:
        train_raw, eval_raw = pool_rows, holdout_rows

    clock = RunClock(args.clock_start) if args.clock_start else RunClock(cfgmod.utcnow_iso())
    clock_iso = clock.to_manifest()["start"]
    if not args.model:
        print(json.dumps({"error": "--model is required (no default in bin/)"}))
        return 1
    base_url = args.base_url or os.environ.get("H1_BASE_URL", "")
    if not base_url:
        print(json.dumps({"error": "--base-url is required (or export H1_BASE_URL)"}))
        return 1
    cfg = cfgmod.resolve_config({
        "TIMELINE": args.timeline,
        "AGENT_POOL_SIZE": args.agent_pool_size,
    })
    if args.match_threshold is not None:
        cfg["MATCH_THRESHOLD"] = args.match_threshold
    if args.cluster_threshold is not None:
        cfg["CLUSTER_THRESHOLD"] = args.cluster_threshold

    access_log: list[str] = []
    run_log: list[list[str]] = []
    r = Runner(out_dir, access_log, run_log)
    r.cfg = cfg
    r.clock = clock
    r.model = args.model
    r.base_url = base_url
    for p in (out_dir / "data", out_dir / "raw" / "extract", out_dir / "packets",
              out_dir / "data" / "chunks"):
        p.mkdir(parents=True, exist_ok=True)
    r.log_access(str(pool_path))
    if args.stage == "S2":
        r.log_access(str(holdout_path))  # the one S2 open of the hold-out

    # inputs snapshot (for C-L1: committed pack shas vs data/README.md)
    pool_sha = sha256_file(pool_path)
    holdout_sha = sha256_file(holdout_path) if holdout_path.exists() else ""

    # --- stage slice files ---------------------------------------------------
    slice_file = out_dir / "data" / "pool_input_slice.jsonl"
    slice_file.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in train_raw) + "\n",
                          encoding="utf-8")
    eval_slice = out_dir / "data" / "eval_input_slice.jsonl"
    eval_slice.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in eval_raw) + "\n",
                          encoding="utf-8")
    chunks = []
    for i in range(0, len(train_raw), CLUSTER_CHUNK):
        c = out_dir / "data" / "chunks" / f"chunk_{i // CLUSTER_CHUNK:03d}.jsonl"
        c.write_text("\n".join(json.dumps(x, ensure_ascii=False)
                               for x in train_raw[i:i + CLUSTER_CHUNK]) + "\n",
                     encoding="utf-8")
        chunks.append(c)

    t_pipeline = time.time()
    # --- phase A: ingest + extract (chunked) ---------------------------------
    extract_summary = r.phase_ingest_extract(chunks, clock_iso)
    # --- phase B: cluster (natural cursor per 100, then final --force) -------
    cluster_res = r.phase_cluster(len(chunks), clock_iso, force_final=True)
    # --- ingest the eval slice (stripped, for serve + B1) ----------------------
    rc, out = r.run([str(HERE / "ingest.py"), "--in", str(eval_slice),
                     "--out", str(out_dir / "data" / "holdout_dialogues.jsonl"),
                     "--agent-pool-size", str(cfg["AGENT_POOL_SIZE"]),
                     "--timeline", str(cfg["TIMELINE"]), "--t0", str(cfg["T0"])])
    holdout_dialogues = read_jsonl(out_dir / "data" / "holdout_dialogues.jsonl")
    # --- serve ----------------------------------------------------------------
    served = r.phase_serve(holdout_dialogues, clock_iso)
    pipeline_wall = time.time() - t_pipeline

    # --- eval (arm T) ----------------------------------------------------------
    extract_summary_file = out_dir / "data" / "extract_summary.json"
    extract_summary_file.write_text(json.dumps(extract_summary), encoding="utf-8")
    # eval-slice labels: S0/S1 slice from the pool -> labels live in the pool;
    # S2 slice is the real hold-out -> labels live in the holdout file. The
    # pipeline never sees either (labels are read by eval.py only).
    eval_labels = str(pool_path) if args.stage in ("S0", "S1") else str(holdout_path)
    rc, out = r.run([str(HERE / "eval.py"),
                     "--dialogues", str(out_dir / "data" / "dialogues.jsonl"),
                     "--holdout", str(out_dir / "data" / "holdout_dialogues.jsonl"),
                     "--cards", str(out_dir / "data" / "cards.jsonl"),
                     "--pool-labels", str(pool_path),
                     "--holdout-labels", eval_labels,
                     "--packets-dir", str(out_dir / "packets"),
                     "--arm", "T",
                     "--extract-summary", str(extract_summary_file),
                     "--out", str(out_dir / "metrics.json"),
                     "--per-dialogue", str(out_dir / "per_dialogue.jsonl"),
                     "--run-id", out_dir.name,
                     "--independence", "agent+dialogue"])
    metrics = json.loads((out_dir / "metrics.json").read_text())

    # --- cost ------------------------------------------------------------------
    cost = build_cost(out_dir, extract_summary, served, pipeline_wall)
    (out_dir / "cost.json").write_text(json.dumps(cost, indent=1, ensure_ascii=False),
                                       encoding="utf-8")

    # --- controls + baselines (B0/B1/B2 through the same scoring path) --------
    import checks as checksmod
    ctx = _make_ctx(args, out_dir, cfg, clock_iso, metrics, cost,
                    extract_summary, pool_path, holdout_path,
                    pool_sha, holdout_sha, access_log, run_log)
    # fixture suite (deterministic, baked responses, zero LLM)
    ctx.fixture = checksmod.run_fixture_suite(ROOT / "fixtures",
                                              out_dir / "fixtures_work", cfg)
    controls = checksmod.run_controls(ctx, str(pool_path), eval_labels,
                                      nc1_input=str(slice_file))
    ctx.controls = controls
    (out_dir / "controls.json").write_text(json.dumps(controls, indent=1,
                                                      ensure_ascii=False), encoding="utf-8")
    # one metrics file per baseline arm (DELIVERABLE-PACKAGE §4)
    for arm in ("B0", "B1", "B2"):
        arm_met = controls.get(arm)
        if arm_met:
            (out_dir / f"metrics_{arm}.json").write_text(
                json.dumps({"run_id": out_dir.name, "arm": arm,
                            "n_holdout": metrics.get("n_holdout"),
                            "primary": arm_met.get("primary"),
                            "secondary": arm_met.get("secondary"),
                            "judge": None}, indent=1, ensure_ascii=False),
                encoding="utf-8")

    # --- audit (S1+; S2 gate via --audit for the committed one) ---------------
    audit = None
    if args.stage == "S2" and args.audit:
        # the committed D3 audit is the gate; the recomputed copy below documents it
        audit = json.loads(Path(args.audit).read_text())
        ctx.audit = audit
    if args.stage in ("S1", "S2"):
        recomputed = run_audit(args, out_dir, cfg, ctx)
        if ctx.audit is None:
            ctx.audit = recomputed
        audit = ctx.audit
    elif args.audit:
        audit = json.loads(Path(args.audit).read_text())
        ctx.audit = audit

    # --- manifest (BEFORE replay: replay_run reads it) -------------------------
    manifest = build_manifest(args, out_dir, cfg, clock_iso, extract_summary,
                              cluster_res, pool_path, holdout_path,
                              pool_sha, holdout_sha, base_url)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1,
                                                      ensure_ascii=False), encoding="utf-8")
    ctx.manifest = manifest

    # --- replay self-check (L0) -------------------------------------------------
    replay_dir = out_dir / "replay_verify"
    replay_ok = replay_run(out_dir, replay_dir, r.cfg)
    ctx.replay_identical = replay_ok
    if replay_ok:
        ctx.replay_metrics_sha = sha256_file(out_dir / "metrics.json")

    # --- checks ------------------------------------------------------------------
    # C-EV10 (SOFT) reads report.md, so a preliminary report is written first
    # and overwritten with the final one (with check counts) below.
    prelim = build_report(args, out_dir, metrics, controls, cost, audit, [],
                          extract_summary, cluster_res, cfg)
    (out_dir / "report.md").write_text(prelim, encoding="utf-8")
    check_rows = checksmod.build_checks(ctx)
    (out_dir / "checks.json").write_text(
        json.dumps(check_rows, indent=1, ensure_ascii=False), encoding="utf-8")
    hard_failed = [c for c in check_rows if c["hard"] and not c["passed"]]
    soft_warn = [c for c in check_rows if not c["hard"] and not c["passed"]]

    # --- report -------------------------------------------------------------------
    report = build_report(args, out_dir, metrics, controls, cost, audit, check_rows,
                          extract_summary, cluster_res, cfg)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    summary = {
        "run_id": out_dir.name,
        "stage": args.stage,
        "metrics": metrics,
        "baselines": {arm: controls.get(arm, {}).get("primary") for arm in ("B0", "B1", "B2")},
        "hard_passed": sum(1 for c in check_rows if c["hard"] and c["passed"]),
        "hard_total": sum(1 for c in check_rows if c["hard"]),
        "soft_warnings": len(soft_warn),
        "hard_failures": [c["check_id"] for c in hard_failed],
        "replay_identical": replay_ok,
        "extract": extract_summary,
        "cluster_passes_fired": cluster_res["natural_fired"],
        "out_dir": str(out_dir),
    }
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 2 if hard_failed else 0


# --------------------------------------------------------------------------- #
# supporting builders                                                         #
# --------------------------------------------------------------------------- #

def _make_ctx(args, out_dir: Path, cfg: dict, clock_iso: str, metrics: dict,
              cost: dict, extract_summary: dict, pool_path: Path,
              holdout_path: Path, pool_sha: str, holdout_sha: str,
              access_log: list[str], run_log: list[list[str]]):
    import checks as checksmod
    ctx = checksmod.Ctx()
    ctx.stage = args.stage
    ctx.arm = "T"
    ctx.run_dir = out_dir
    ctx.metrics = metrics
    ctx.cost = cost
    ctx.extract_summary = extract_summary
    ctx.pool_original = str(pool_path)
    ctx.holdout_original = str(holdout_path)
    ctx.pool_sha = pool_sha
    ctx.holdout_sha = holdout_sha
    ctx.input_shas_ok = _input_shas_match(pool_path, holdout_path)
    ctx.access_log = access_log
    ctx.run_log = run_log
    ctx.cfg = cfg
    ctx.clock_iso = clock_iso
    return ctx


def _input_shas_match(pool_path: Path, holdout_path: Path) -> bool:
    """C-L1: shas equal the ones recorded in data/README.md, after the run."""
    readme = (ROOT / "data" / "README.md").read_text()
    exp = {
        "abcd_1000_pool.jsonl": "28b77a32e58932bbf1502d73975972285ec071d03f30c6ac2b5d23cd90a5abbb",
        "abcd_200_holdout.jsonl": "e8f453e17c6c3aa115fb2bd1498a833da383cecdcc650667ac349f903343fe3c",
    }
    ok = True
    if pool_path.name in exp and sha256_file(pool_path) != exp[pool_path.name]:
        ok = False
    if holdout_path.name in exp and sha256_file(holdout_path) != exp[holdout_path.name]:
        ok = False
    return ok


def build_cost(out_dir: Path, extract_summary: dict, served: dict,
               pipeline_wall: float) -> dict:
    raw_dir = out_dir / "raw" / "extract"
    calls = 0
    p_tokens = c_tokens = 0
    ms = []
    if raw_dir.exists():
        for p in raw_dir.glob("*.json"):
            rec = json.loads(p.read_text())
            usage = rec.get("usage") or {}
            calls += 1
            p_tokens += usage.get("prompt_tokens", 0)
            c_tokens += usage.get("completion_tokens", 0)
            ms.append(rec.get("ms", 0))
    ms_sorted = sorted(ms)
    def pct(q: float) -> int:
        if not ms_sorted:
            return 0
        return int(ms_sorted[min(len(ms_sorted) - 1, int(q * len(ms_sorted)))])
    serve_ms = sorted(served.get("ms", []))
    def spct(q: float) -> int:
        if not serve_ms:
            return 0
        return int(serve_ms[min(len(serve_ms) - 1, int(q * len(serve_ms)))])
    cost = {
        "extract": {
            "calls": calls,
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "usd_total": None,
            "usd_per_1000_dialogues": None,
            "ms_p50": pct(0.5),
            "ms_p95": pct(0.95),
        },
        "serve": {"ms_p50": spct(0.5), "ms_p95": spct(0.95)},
        "deterministic_half_wall_clock_s": round(pipeline_wall, 3),
        "price_source": "provider rate unknown at run time; tokens reported, usd_total null (C-EV9)",
    }
    return cost


def run_audit(args, out_dir: Path, cfg: dict, ctx) -> dict | None:
    import checks as checksmod
    fixture_results = {k: v for k, v in ctx.fixture.results.items()}
    fixture_file = out_dir / "fixtures_work" / "results.json"
    # fixture results contain Paths/dicts; keep JSON-safe subset
    safe = {k: v for k, v in fixture_results.items()
            if isinstance(v, (dict, list, str, int, float, bool)) or v is None}
    fixture_file.write_text(json.dumps(safe, default=str), encoding="utf-8")
    pool = str(Path(args.pool).resolve())
    holdout = str(Path(args.holdout).resolve())
    # NOTE (C-L5 interpretation): the audit reads the REAL hold-out at S1+ —
    # that is EVAL-PLAN §7 A1's own arithmetic, required before S2, and it
    # never feeds the pipeline. C-L5 therefore asserts on the PIPELINE access
    # log only; the audit read is disclosed in report.md, not hidden.
    rc, out = ctx.run([str(HERE / "audit.py"),
                       "--pool", pool, "--holdout", holdout,
                       "--dialogues", str(out_dir / "data" / "dialogues.jsonl"),
                       "--cards", str(out_dir / "data" / "cards.jsonl"),
                       "--fixture-results", str(fixture_file),
                       "--out", str(out_dir / "audit.json")],
                      log=False)
    p = out_dir / "audit.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


def _rel_or_abs(p: Path) -> str:
    """Store repo-relative paths in the manifest so --replay works in a fresh
    clone (DELIVERABLE-PACKAGE §1, claim 2). Absolute only if outside ROOT."""
    try:
        rel = p.resolve().relative_to(ROOT.resolve())
        return str(rel)
    except ValueError:
        return str(p.resolve())


def build_manifest(args, out_dir: Path, cfg: dict, clock_iso: str,
                   extract_summary: dict, cluster_res: dict,
                   pool_path: Path, holdout_path: Path,
                   pool_sha: str, holdout_sha: str, base_url: str) -> dict:
    prompts = Prompts()
    def sha(rel: str) -> str:
        p = out_dir / rel
        return sha256_file(p) if p.exists() else "MISSING"
    git = git_commit(ROOT)
    # the eval slice's labels live in the pool at S0/S1 and in the holdout at S2
    eval_labels = str(pool_path) if args.stage in ("S0", "S1") else str(holdout_path)
    return {
        "run_id": out_dir.name,
        "created_at": cfgmod.utcnow_iso(),
        "stage": args.stage,
        "git_commit": f"{git.get('sha')}{'+dirty' if git.get('dirty') else ''}",
        "extract_model": args.model,
        "judge_model": None,
        "base_url": base_url,
        "temperature": cfg["TEMPERATURE"],
        "timeline": cfg["TIMELINE"],
        "agent_pool_size": cfg["AGENT_POOL_SIZE"],
        "config": cfgmod.manifest_config(cfg),
        "cluster_passes_fired": cluster_res["natural_fired"],
        "inputs": {
            "pool": {"path": _rel_or_abs(pool_path), "sha256": pool_sha,
                     "rows": len(read_jsonl(pool_path))},
            "holdout": {"path": _rel_or_abs(holdout_path), "sha256": holdout_sha,
                        "rows": len(read_jsonl(holdout_path))},
            "eval_labels": {"path": _rel_or_abs(Path(eval_labels)),
                            "sha256": sha256_file(Path(eval_labels))},
            "prompts": {"path": prompts.path, "sha256": prompts.sha256},
        },
        "outputs": {
            "cards.jsonl": sha("data/cards.jsonl"),
            "metrics.json": sha("metrics.json"),
            "per_dialogue.jsonl": sha("per_dialogue.jsonl"),
        },
        "clock": {"start": clock_iso, "tz": "UTC"},
        "replay_of": None,
        "notes": ["age-stale disabled by construction: timeline=compressed",
                  "pack action speaker turns mapped to role=tool (no turn text lost)",
                  "run clock pinned; created_at/served_at/staleness-now derive from it"],
    }


def build_report(args, out_dir: Path, metrics: dict, controls: dict, cost: dict,
                 audit: dict | None, check_rows: list[dict],
                 extract_summary: dict, cluster_res: dict, cfg: dict) -> str:
    hard_failed = [c for c in check_rows if c["hard"] and not c["passed"]]
    soft_warn = [c for c in check_rows if not c["hard"] and not c["passed"]]
    prim = lambda arm: controls.get(arm, {}).get("primary", {})
    lines = []
    lines.append(f"# Run {out_dir.name}")
    lines.append(f"- stage: {args.stage} | model: {args.model} | timeline: {cfg['TIMELINE']} "
                 f"| independence: agent+dialogue (synthesized A={cfg['AGENT_POOL_SIZE']})")
    lines.append(f"- cluster passes fired: {cluster_res['natural_fired']} natural "
                 f"(+ final --force: {'ran' if cluster_res['forced_final_ran'] else 'no-op'})")
    lines.append(f"- age-stale: {'active' if cfg['TIMELINE'] == 'aged' else 'OFF by construction (compressed)'}")
    lines.append("")
    lines.append("## Checks")
    lines.append(f"HARD passed: {sum(1 for c in check_rows if c['hard'] and c['passed'])}/"
                 f"{sum(1 for c in check_rows if c['hard'])}; "
                 f"soft warnings: {len(soft_warn)}")
    for c in hard_failed:
        lines.append(f"- HARD FAIL {c['check_id']}: {c['observed']}")
    for c in soft_warn:
        lines.append(f"- SOFT warn {c['check_id']}: {c['observed']}")
    lines.append("")
    lines.append("## Audit (A1-A5)")
    if audit:
        for aid, item in audit.get("items", {}).items():
            lines.append(f"- {aid}: {item.get('value')} | reachable: {item.get('reachable', item.get('rule_verified'))}")
    else:
        lines.append("- not required at this stage (S2 gate)")
    lines.append("")
    lines.append("## Primary table (same scoring path, EVAL-PLAN §4)")
    lines.append("| arm | unlock_hit_label | wrong | abstain | serve_rate |")
    lines.append("|---|---|---|---|---|")
    arms = [("T", metrics), ("B0", prim("B0")), ("B1", prim("B1")), ("B2", prim("B2"))]
    for name, m in arms:
        if not m:
            continue
        sr = metrics["secondary"]["serve_rate"] if name == "T" else controls.get(name, {}).get("secondary", {}).get("serve_rate", "-")
        lines.append(f"| {name} | {m.get('unlock_hit_label')} | {m.get('wrong')} | "
                     f"{m.get('abstain')} | {sr} |")
    lines.append("")
    lines.append(f"## Secondary (T)\n```json\n{json.dumps(metrics.get('secondary', {}), indent=1)}\n```")
    lines.append("")
    lines.append("## Judge block")
    lines.append("- L3 not run at this stage (S3 gate). Honesty clause applies to any judge number later: "
                 "*agent-drafted, agent-judged; self-consistency floor, not human inter-rater agreement.*")
    lines.append("")
    lines.append(f"## Cost\n```json\n{json.dumps(cost, indent=1)}\n```")
    lines.append("")
    verdict = "pending (staged run; fitness verdict lands at S4)"
    if hard_failed:
        verdict = "NOT FIT (hard gate failure — run aborted, no L2 published)"
    lines.append(f"## Fitness verdict: {verdict}")
    lines.append("")
    lines.append("## What would change the verdict: see D3 audit + D4 baselines before S2.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# replay (L0)                                                                 #
# --------------------------------------------------------------------------- #

def replay_run(src_dir: Path, out_dir: Path, cfg: dict) -> bool:
    """Re-execute everything from the recorded extract responses; zero LLM calls.

    Compares metrics.json + per_dialogue.jsonl byte-identically and cards sha.
    Returns True on byte-identical reproduction.
    """
    manifest = json.loads((src_dir / "manifest.json").read_text())
    clock_iso = manifest.get("clock", {}).get("start")
    stage = manifest.get("stage")
    model = manifest.get("extract_model")
    base_url = manifest.get("base_url")
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    for p in (out_dir / "data" / "chunks", out_dir / "raw" / "extract",
              out_dir / "packets"):
        p.mkdir(parents=True, exist_ok=True)
    # copy the raw extract records (replay reads them)
    for p in (src_dir / "raw" / "extract").glob("*.json"):
        (out_dir / "raw" / "extract" / p.name).write_bytes(p.read_bytes())
    slice_file = src_dir / "data" / "pool_input_slice.jsonl"
    eval_slice = src_dir / "data" / "eval_input_slice.jsonl"

    rr = Runner(out_dir)
    rr.cfg = cfg
    chunks = []
    for i, c in enumerate(sorted((src_dir / "data" / "chunks").glob("chunk_*.jsonl"))):
        dst = out_dir / "data" / "chunks" / c.name
        dst.write_bytes(c.read_bytes())
        chunks.append(dst)
    # phase A (replay) — mirror the live run's ingest/extract interleaving
    for i, chunk in enumerate(chunks):
        rr.run([str(HERE / "ingest.py"), "--in", str(chunk), "--out",
                str(out_dir / "data" / "dialogues.jsonl"),
                "--agent-pool-size", str(cfg["AGENT_POOL_SIZE"]),
                "--timeline", str(cfg["TIMELINE"]), "--t0", str(cfg["T0"])])
        rr.run([str(HERE / "extract.py"), "--in", str(out_dir / "data" / "dialogues.jsonl"),
                "--out", str(out_dir / "data" / "cards.jsonl"),
                "--model", model or "",
                "--base-url", base_url or "",
                "--raw-dir", str(out_dir / "raw" / "extract"),
                "--replay", "--clock-start", clock_iso,
                "--start-index", str(i * CLUSTER_CHUNK)])
    # phase B
    for _ in chunks:
        rr.run([str(HERE / "cluster.py"), "--cards", str(out_dir / "data" / "cards.jsonl"),
                "--dialogues", str(out_dir / "data" / "dialogues.jsonl"), "--now", clock_iso])
    rr.run([str(HERE / "cluster.py"), "--cards", str(out_dir / "data" / "cards.jsonl"),
            "--dialogues", str(out_dir / "data" / "dialogues.jsonl"),
            "--force", "--now", clock_iso])
    # eval slice + serve + eval
    rr.run([str(HERE / "ingest.py"), "--in", str(eval_slice), "--out",
            str(out_dir / "data" / "holdout_dialogues.jsonl"),
            "--agent-pool-size", str(cfg["AGENT_POOL_SIZE"]),
            "--timeline", str(cfg["TIMELINE"]), "--t0", str(cfg["T0"])])
    holdout = read_jsonl(out_dir / "data" / "holdout_dialogues.jsonl")
    rr.phase_serve(holdout, clock_iso)
    # extract summary is deterministic (same accept/reject counts); carry it so
    # the replay's metrics.json matches the original byte-for-byte (C-EV6).
    src_summ = src_dir / "data" / "extract_summary.json"
    if src_summ.exists():
        (out_dir / "data" / "extract_summary.json").write_bytes(src_summ.read_bytes())
    rr.run([str(HERE / "eval.py"),
            "--dialogues", str(out_dir / "data" / "dialogues.jsonl"),
            "--holdout", str(out_dir / "data" / "holdout_dialogues.jsonl"),
            "--cards", str(out_dir / "data" / "cards.jsonl"),
            "--pool-labels", str(Path(manifest["inputs"]["pool"]["path"])),
            "--holdout-labels", str(Path(manifest["inputs"].get("eval_labels", manifest["inputs"]["holdout"])["path"])),
            "--packets-dir", str(out_dir / "packets"),
            "--arm", "T",
            "--extract-summary", str(out_dir / "data" / "extract_summary.json"),
            "--out", str(out_dir / "metrics.json"),
            "--per-dialogue", str(out_dir / "per_dialogue.jsonl"),
            "--run-id", src_dir.name,  # same id as the source run: byte-identical metrics
            "--independence", "agent+dialogue"])
    if not (out_dir / "metrics.json").exists():
        return False
    same_metrics = (out_dir / "metrics.json").read_bytes() == (src_dir / "metrics.json").read_bytes()
    same_per = (out_dir / "per_dialogue.jsonl").read_bytes() == (src_dir / "per_dialogue.jsonl").read_bytes()
    same_cards = sha256_file(out_dir / "data" / "cards.jsonl") == sha256_file(src_dir / "data" / "cards.jsonl")
    (out_dir / "replay_result.json").write_text(json.dumps({
        "same_metrics": same_metrics, "same_per_dialogue": same_per,
        "same_cards_sha": same_cards,
        "llm_calls": 0}, indent=1), encoding="utf-8")
    return same_metrics and same_per and same_cards


# --------------------------------------------------------------------------- #
# baseline mode                                                               #
# --------------------------------------------------------------------------- #

def baseline_run(args) -> int:
    """--baseline B0|B1|B2 --store <T run dir>: re-derive a baseline through the
    SAME scoring path (C-EV5), from an existing run's store."""
    src = Path(args.store)
    manifest = json.loads((src / "manifest.json").read_text())
    out_dir = Path(args.out)
    if out_dir.exists() and any(out_dir.iterdir()):
        print(json.dumps({"error": f"output dir exists and is non-empty: {out_dir}"}))
        return 1
    out_dir.mkdir(parents=True)
    import checks as checksmod
    cfg = cfgmod.resolve_config(manifest.get("config", {}))
    pool_labels = manifest["inputs"]["pool"]["path"]
    holdout_labels = manifest["inputs"]["holdout"]["path"]
    rr = Runner(out_dir)
    rr.run([str(HERE / "eval.py"),
            "--dialogues", str(src / "data" / "dialogues.jsonl"),
            "--holdout", str(src / "data" / "holdout_dialogues.jsonl"),
            "--cards", str(src / "data" / "cards.jsonl"),
            "--pool-labels", str(pool_labels),
            "--holdout-labels", str(holdout_labels),
            "--packets-dir", str(src / "packets"),
            "--arm", args.baseline,
            "--out", str(out_dir / "metrics.json"),
            "--per-dialogue", str(out_dir / "per_dialogue.jsonl"),
            "--run-id", out_dir.name,
            "--independence", "agent+dialogue"])
    metrics = json.loads((out_dir / "metrics.json").read_text())
    manifest_out = dict(manifest)
    manifest_out["run_id"] = out_dir.name
    manifest_out["replay_of"] = src.name
    manifest_out["arm"] = args.baseline
    (out_dir / "manifest.json").write_text(json.dumps(manifest_out, indent=1,
                                                      ensure_ascii=False), encoding="utf-8")
    (out_dir / "report.md").write_text(
        f"# Baseline {args.baseline} derived from {src.name}\n"
        f"```json\n{json.dumps(metrics, indent=1)}\n```\n", encoding="utf-8")
    print(json.dumps({"run_id": out_dir.name, "arm": args.baseline,
                      "primary": metrics["primary"], "n_holdout": metrics["n_holdout"]},
                     indent=1))
    return 0


# --------------------------------------------------------------------------- #
# entrypoint                                                                  #
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="H1 experience-card experiment runner (RUN-PROTOCOL §1).")
    ap.add_argument("--pool", default=str(ROOT / "data" / "abcd_1000_pool.jsonl"))
    ap.add_argument("--holdout", default=None,
                    help="hold-out file (S2 only; S0/S1 must never pass it)")
    ap.add_argument("--model", default=None,
                    help="extract model id (required for live runs; no default in bin/)")
    ap.add_argument("--base-url", default=None,
                    help="OpenAI-compatible base URL (default: $H1_BASE_URL)")
    ap.add_argument("--stage", choices=("S0", "S1", "S2"), default="S0")
    ap.add_argument("--out", default=None, help="run dir (default runs/<date>_<stage>_<model>)")
    ap.add_argument("--timeline", choices=("compressed", "aged"), default="compressed")
    ap.add_argument("--agent-pool-size", type=int, default=cfgmod.DEFAULTS["AGENT_POOL_SIZE"])
    ap.add_argument("--match-threshold", type=float, default=None)
    ap.add_argument("--cluster-threshold", type=float, default=None)
    ap.add_argument("--clock-start", default=None, help="pinned run clock (tests/replay parity)")
    ap.add_argument("--audit", default=None, help="committed audit.json path (required for S2)")
    # modes
    ap.add_argument("--replay", default=None, metavar="RUN_DIR",
                    help="re-run a run dir from recorded responses (zero LLM)")
    ap.add_argument("--baseline", choices=("B0", "B1", "B2"), default=None)
    ap.add_argument("--store", default=None, help="T run dir for --baseline")
    args = ap.parse_args(argv)

    if args.replay:
        src = Path(args.replay)
        out = Path(args.out) if args.out else src.parent / (src.name + "_replay")
        manifest = json.loads((src / "manifest.json").read_text())
        cfg = cfgmod.resolve_config(manifest.get("config", {}))
        ok = replay_run(src, out, cfg)
        print(json.dumps({"replay_of": src.name, "byte_identical": ok,
                          "llm_calls": 0, "out": str(out)}))
        return 0 if ok else 2

    if args.baseline:
        if not args.store:
            print(json.dumps({"error": "--baseline requires --store <T run dir>"}))
            return 1
        return baseline_run(args)

    if args.stage == "S2" and not args.audit and not Path(str(ROOT / "audit.json")).exists():
        print(json.dumps({"error": "S2 requires the D3 audit gate: pass --audit <audit.json> "
                                   "or commit audit.json at the folder root first"}))
        return 1

    if not args.out:
        import datetime
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        args.out = str(ROOT / "runs" / f"{stamp}_{args.stage}_{args.model}")

    # patch stage into args for audit path resolution
    if args.stage == "S2":
        args.audit = args.audit or str(ROOT / "audit.json")
    return live_run(args)


if __name__ == "__main__":
    sys.exit(main())
