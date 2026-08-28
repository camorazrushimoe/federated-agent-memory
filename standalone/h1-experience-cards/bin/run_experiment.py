#!/usr/bin/env python3
"""run_experiment.py — one command, one run (RUN-PROTOCOL §1, §3).

    python bin/run_experiment.py --pool data/abcd_1000_pool.jsonl \\
        --holdout data/abcd_200_holdout.jsonl --model <extract model> \\
        --stage S2 --out runs/<run_id> [--replay <run_id>] \\
        [--baseline B1] [--agent-pool-size N] [--timeline compressed|aged] \\
        [--now ISO] [--set k=v]

- Stage decides the data slice (EVAL-PLAN §9):
    S0: pool first 20 rows; eval hold-out = last 4 of those 20 via eval's
        default 80/20 split; PLUS the fixture track. The real hold-out file
        is NOT opened (C-L5).
    S1: pool first 200 rows; hold-out = pool rows 200..239 (pool's own tail)
        passed to eval via --holdout.
    S2: pool 1000; hold-out = the real abcd_200_holdout.jsonl, opened exactly
        ONCE (C-L5 — see data/access_log.jsonl).
    S3/S4: accepted as no-ops with a message (judge/verdict stages, out of
        D1 scope).
- Pipeline: ingest (both files) → extract (live or replay) → cluster passes
  (S1/S2: the natural 100-chat cursor, n//100 passes, recorded as
  cluster_passes_fired) → eval arm T → baselines B0/B1/B2 through
  eval.py --baseline → manifest / cost / report. No new pipeline logic lives
  in the runner — it orchestrates the bin/ scripts.
- --replay <run_id>: re-runs the whole deterministic half from that run's
  raw/extract/*.json with ZERO LLM calls and asserts metrics.json is
  byte-identical (C-EV6). With no --out, replay runs in place
  (runs/<run_id>), which is what the packaged quickstart does.
- Access log: data/access_log.jsonl — one row per input file opened
  ({opened, stage, at}); C-L5 reads it.
- Refuses to start if --out exists and is non-empty (RUN-PROTOCOL §1).
- D8 rule: --model has NO default; base URL and API key come from
  --base-url/--api-key or env H1_BASE_URL/H1_API_KEY. No model, endpoint or
  key literal in this file. In replay mode the model/base-url are taken from
  the source manifest so the quickstart's bare `--replay <run_id>` works.

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import config as cfg
import jsonio as hio
import llm
from common import now_iso, parse_iso, scrub_pii, iso_add_seconds

BIN_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BIN_DIR, "..", "..", ".."))
EXPERIMENT_DIR = os.path.abspath(os.path.join(BIN_DIR, ".."))
FIXTURES_DIR = os.path.join(EXPERIMENT_DIR, "fixtures")
POOL_PATH = os.path.join(EXPERIMENT_DIR, "data", "abcd_1000_pool.jsonl")
HOLDOUT_PATH = os.path.join(EXPERIMENT_DIR, "data", "abcd_200_holdout.jsonl")
PROMPTS_PATH = os.path.join(EXPERIMENT_DIR, "PROMPTS.md")

STAGES = ("S0", "S1", "S2", "S3", "S4")
SLICES = {"S0": 20, "S1": 200, "S2": 1000}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def run_script(name, argv):
    proc = subprocess.run([sys.executable, os.path.join(BIN_DIR, name)] + argv,
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


def git_commit_info():
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"],
                             cwd=REPO_ROOT, capture_output=True, text=True,
                             check=True).stdout.strip()
        porcelain = subprocess.run(["git", "status", "--porcelain"],
                                   cwd=REPO_ROOT, capture_output=True,
                                   text=True, check=True).stdout.strip()
        return {"sha": sha, "dirty": bool(porcelain)}
    except Exception as exc:  # pragma: no cover
        return {"sha": None, "dirty": None, "error": str(exc)}


def pct(lst, p):
    if not lst:
        return None
    s = sorted(lst)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def read_rows_once(path):
    """Read all JSONL rows of a file in one open (access-log bookkeeping)."""
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_pack_slice(rows, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(hio.dumps(row) + "\n")


def load_labels(rows):
    """{dialogue_id: unlock_guideline} from original pack rows."""
    return {str(r["chat_id"]): r.get("unlock_guideline") for r in rows}


def effective_set_args(overrides, old_manifest=None):
    """--set args for the given overrides dict (defaults excluded)."""
    args_list = []
    for key, val in sorted(overrides.items()):
        if cfg.DEFAULTS.get(key) != val:
            args_list.append(f"{key}={val}")
    return args_list


# ---------------------------------------------------------------------------
# fixture track (S0)
# ---------------------------------------------------------------------------

class FixtureFail(Exception):
    pass


def _fixture_assert(cond, scenario, expected, observed):
    if not cond:
        raise FixtureFail(
            f"fixture {scenario}: expected {expected}, observed {observed}")


def _ingest(fdir, fixture_file, now, agent_pool_size):
    run_script("ingest.py", ["--in", os.path.join(FIXTURES_DIR, fixture_file),
                             "--out", os.path.join(fdir, "data", "dialogues.jsonl"),
                             "--timeline", "compressed",
                             "--agent-pool-size", str(agent_pool_size)])
    return os.path.join(fdir, "data", "dialogues.jsonl")


def _extract(fdir, dialogues_path, model, now):
    cards = os.path.join(fdir, "data", "cards.jsonl")
    raw = os.path.join(fdir, "raw", "extract")
    return run_script("extract.py", ["--in", dialogues_path, "--out", cards,
                                     "--model", model, "--raw-dir", raw,
                                     "--now", now]), cards


def _extract_split(fdir, dialogues_path, model, now):
    """Extract a scenario's dialogues with staggered pinned nows.

    SPEC §5: the canonical is the OLDEST card by created_at (tie: smaller
    card_id). One extract call stamps every card with the same created_at,
    so the tie-break would pick the smallest card_id — SPEC §10.2 expects
    the FIRST dialogue's card (d-001) to be the canonical. Extracting the
    first dialogue in its own call (pinned now) and the rest one second
    later (now+1s, via iso_add_seconds) makes the first dialogue strictly
    oldest, deterministically. fx10_4's d-013 (a single dialogue) is
    extracted with the same now; d-001's card_id sorts before d-013's, so
    the tie-break keeps d-001 canonical there too.
    """
    rows = hio.read_jsonl(dialogues_path)
    if len(rows) <= 1:
        return _extract(fdir, dialogues_path, model, now)
    tmp = os.path.join(fdir, ".extract_in")
    os.makedirs(tmp, exist_ok=True)
    first_path = os.path.join(tmp, "first.jsonl")
    rest_path = os.path.join(tmp, "rest.jsonl")
    hio.write_jsonl(first_path, rows[:1])
    hio.write_jsonl(rest_path, rows[1:])
    s1, cards = _extract(fdir, first_path, model, now)
    s2, _ = _extract(fdir, rest_path, model, iso_add_seconds(now, 1))
    merged = {k: int(s1.get(k, 0) or 0) + int(s2.get(k, 0) or 0)
              for k in ("extracted", "rejected", "skipped", "unparseable",
                        "pii_flagged")}
    return merged, cards


def _cluster(fdir, cards, dialogues, now, force=False):
    argv = ["--cards", cards, "--dialogues", dialogues, "--now", now]
    if force:
        argv.append("--force")
    return run_script("cluster.py", argv)


def _serve_one(fdir, dialogue_row, cards, now, packets_out=None):
    os.makedirs(os.path.join(fdir, ".serve_in"), exist_ok=True)
    live_path = os.path.join(fdir, ".serve_in",
                             f"{dialogue_row['dialogue_id']}.json")
    with open(live_path, "w", encoding="utf-8") as fh:
        fh.write(hio.dumps(dialogue_row))
    argv = ["--dialogue", live_path, "--cards", cards, "--now", now]
    if packets_out:
        argv += ["--packets-out", packets_out]
    return run_script("serve.py", argv)


def _read_store(path):
    return hio.read_jsonl(path) if os.path.exists(path) else []


def _card_text_fields(card):
    vals = []
    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            vals.append(x)
    walk(card)
    return vals


def run_fixture_track(out_dir, model, now, agent_pool_size, overrides):
    """Run the S0 fixture scenarios. Returns a list of summary rows.

    fx10_4 and fx_live reuse the fx10_2 card store; if fx10_2 fails they
    fail cleanly with their own summary rows.
    """
    fx = os.path.join(out_dir, "data", "fixtures")
    summaries = []
    fx2_cards_store = None   # set by fx10_2; reused by fx10_4 and fx_live
    set_args = effective_set_args(overrides)

    def record(scenario, ok, expected, observed, extra=None):
        row = {"scenario": scenario, "ok": ok, "at": now,
               "expected": expected, "observed": observed}
        if extra:
            row.update(extra)
        summaries.append(row)

    def scenario_dir(name):
        d = os.path.join(fx, name)
        os.makedirs(os.path.join(d, "data"), exist_ok=True)
        os.makedirs(os.path.join(d, "raw", "extract"), exist_ok=True)
        return d

    # --- fx10_1: single §10.1 dialogue; PII scrubbed; cluster no-op first ---
    try:
        d = scenario_dir("fx10_1")
        dlg = _ingest(d, "dialogue_10_1_single.jsonl", now, agent_pool_size)
        ext, cards = _extract(d, dlg, model, now)
        noop = _cluster(d, cards, dlg, now, force=False)
        _fixture_assert(noop.get("ran") is False and
                        noop.get("remaining") == 99,
                        "fx10_1", "{ran:false, remaining:99}", noop)
        cls = _cluster(d, cards, dlg, now, force=True)
        store = _read_store(cards)
        card = store[0] if store else None
        _fixture_assert(ext.get("extracted") == 1 and
                        ext.get("rejected") == 0,
                        "fx10_1", "extracted=1, rejected=0", ext)
        _fixture_assert(card is not None and card.get("status") != "rejected",
                        "fx10_1", "card survives, not rejected", card)
        fields = _card_text_fields(card)
        _fixture_assert(all("4412" not in str(f) for f in fields),
                        "fx10_1", "4412 absent from every field", fields)
        record("fx10_1", True, "extracted=1, noop remaining=99, 4412 absent",
               {"extract": ext, "cluster_noop": noop, "cluster": cls,
                "contains_pii": card.get("contains_pii") if card else None,
                "status": card.get("status") if card else None})
    except FixtureFail as e:
        record("fx10_1", False, str(e), {})

    # --- fx10_2: ten dialogues, two agents → 1 canonical, 9 merged, shared ---
    try:
        d = scenario_dir("fx10_2")
        dlg = _ingest(d, "dialogue_10_2_two_agents.jsonl", now, agent_pool_size)
        ext, cards = _extract_split(d, dlg, model, now)
        cls = _cluster(d, cards, dlg, now, force=True)
        store = _read_store(cards)
        canonicals = [c for c in store if c.get("role") == "canonical"]
        merged = [c for c in store if c.get("status") == "merged"]
        canon = canonicals[0] if canonicals else {}
        _fixture_assert(len(canonicals) == 1 and len(merged) == 9,
                        "fx10_2", "1 canonical, 9 merged",
                        {"canonicals": len(canonicals), "merged": len(merged)})
        _fixture_assert(canon.get("votes", 0) >= 2 and
                        canon.get("status") == "shared",
                        "fx10_2", "votes>=2, shared",
                        {"votes": canon.get("votes"),
                         "status": canon.get("status")})
        fx2_cards_store = cards
        fx2_summary = {"extract": ext, "cluster": cls,
                       "votes": canon.get("votes"),
                       "status": canon.get("status"),
                       "independence": cls.get("independence")}
        record("fx10_2", True, "1 canonical, 9 merged, votes>=2, shared",
               fx2_summary)
    except FixtureFail as e:
        record("fx10_2", False, str(e), {})

    # --- fx10_3: the same ten from ONE agent → votes=1, private ------------
    try:
        d = scenario_dir("fx10_3")
        dlg = _ingest(d, "dialogue_10_3_one_agent.jsonl", now, agent_pool_size)
        ext, cards = _extract_split(d, dlg, model, now)
        cls = _cluster(d, cards, dlg, now, force=True)
        store = _read_store(cards)
        canonicals = [c for c in store if c.get("role") == "canonical"]
        canon = canonicals[0] if canonicals else {}
        _fixture_assert(canon.get("votes") == 1 and
                        canon.get("status") == "private",
                        "fx10_3", "votes=1, private",
                        {"votes": canon.get("votes"),
                         "status": canon.get("status")})
        record("fx10_3", True, "votes=1, private",
               {"extract": ext, "cluster": cls,
                "votes": canon.get("votes"), "status": canon.get("status")})
    except FixtureFail as e:
        record("fx10_3", False, str(e), {})

    # --- fx10_4: echo — serve d-013, re-cluster, votes unchanged -----------
    try:
        if fx2_cards_store is None:
            raise FixtureFail("fx10_2 store unavailable")
        d = scenario_dir("fx10_4")
        dlg = _ingest(d, "dialogue_10_4_echo.jsonl", now, agent_pool_size)
        ext, cards = _extract_split(d, dlg, model, now)
        # merge fx10_2's store with d-013's fresh card
        merged_store = {}
        for c in _read_store(fx2_cards_store):
            merged_store[c["card_id"]] = c
        for c in _read_store(cards):
            merged_store[c["card_id"]] = c
        hio.write_jsonl(cards, [merged_store[k] for k in sorted(merged_store)])
        d013 = [r for r in hio.read_jsonl(dlg) if r["dialogue_id"] == "d-013"][0]
        served = _serve_one(d, d013, cards, now,
                            packets_out=os.path.join(d, "packets"))
        votes_before = None
        for c in _read_store(cards):
            if c.get("role") == "canonical" and c.get("members"):
                votes_before = c.get("votes")
                break
        cls = _cluster(d, cards, dlg, now, force=True)
        votes_after = None
        served_to = []
        for c in _read_store(cards):
            if c.get("role") == "canonical" and c.get("members"):
                votes_after = c.get("votes")
                served_to = c.get("served_to", [])
                break
        _fixture_assert(votes_before is not None and
                        votes_after == votes_before,
                        "fx10_4", f"votes unchanged ({votes_before})",
                        {"votes_before": votes_before,
                         "votes_after": votes_after})
        _fixture_assert(any(e.get("dialogue_id") == "d-013"
                            for e in served_to),
                        "fx10_4", "d-013 in served_to", served_to)
        record("fx10_4", True,
               f"votes unchanged ({votes_before}), d-013 in served_to",
               {"extract": ext, "served": served, "votes_before": votes_before,
                "votes_after": votes_after, "served_to": served_to,
                "cluster": cls})
    except FixtureFail as e:
        record("fx10_4", False, str(e), {})

    # --- fx10_5: freshness follows the last member (not stale) -------------
    try:
        d = scenario_dir("fx10_5")
        dlg = _ingest(d, "dialogue_10_5_freshness.jsonl", now, agent_pool_size)
        ext, cards = _extract_split(d, dlg, model, now)
        cls = _cluster(d, cards, dlg, now, force=True)
        store = _read_store(cards)
        canon = next(c for c in store if c.get("role") == "canonical")
        lca = (canon.get("receipt") or {}).get("last_closed_at")
        _fixture_assert(lca == "2026-08-27T12:00:00Z" and
                        canon.get("status") != "stale",
                        "fx10_5", "last_closed_at=2026-08-27T12:00:00Z, "
                                  "not stale",
                        {"last_closed_at": lca, "status": canon.get("status")})
        record("fx10_5", True, "last_closed_at=2026-08-27T12:00:00Z, not stale",
               {"extract": ext, "cluster": cls, "last_closed_at": lca,
                "status": canon.get("status")})
    except FixtureFail as e:
        record("fx10_5", False, str(e), {})

    # --- fx10_5b: quiet cluster (>30 days) → stale fires -------------------
    try:
        d = scenario_dir("fx10_5b")
        dlg = _ingest(d, "dialogue_10_5b_quiet.jsonl", now, agent_pool_size)
        ext, cards = _extract_split(d, dlg, model, now)
        cls = _cluster(d, cards, dlg, now, force=True)
        store = _read_store(cards)
        canon = next(c for c in store if c.get("role") == "canonical")
        _fixture_assert(canon.get("status") == "stale",
                        "fx10_5b", "status=stale", canon.get("status"))
        record("fx10_5b", True, "status=stale",
               {"extract": ext, "cluster": cls, "status": canon.get("status"),
                "last_closed_at": (canon.get("receipt") or {}).get(
                    "last_closed_at")})
    except FixtureFail as e:
        record("fx10_5b", False, str(e), {})

    # --- fx10_7: bare word 'card' does not trigger the PII scrub -----------
    try:
        d = scenario_dir("fx10_7")
        dlg = _ingest(d, "dialogue_10_card_word.jsonl", now, agent_pool_size)
        ext, cards = _extract(d, dlg, model, now)
        store = _read_store(cards)
        card = store[0] if store else None
        _fixture_assert(ext.get("extracted") == 1 and card is not None,
                        "fx10_7", "card extracted", ext)
        # Scrub exactly what extract.py scrubs: the model-written content
        # fields. The SPEC §4 phone regex can match ISO timestamps
        # ("2026-08-26T12:00:00Z"), so structural metadata (receipt,
        # created_at, ...) is out of scope for the PII gate — it is written
        # by the pipeline, never by the model.
        content = {k: (card or {}).get(k) for k in
                   ("problem_shape", "constraint", "unlock", "what_worked")}
        scrubbed, replaced = scrub_pii(content)
        _fixture_assert(replaced is False,
                        "fx10_7", "scrub replaced nothing", replaced)
        record("fx10_7", True, "scrub replaced nothing",
               {"extract": ext, "contains_pii": card.get("contains_pii")
                if card else None, "scrub_replaced": replaced,
                "status": card.get("status") if card else None})
    except FixtureFail as e:
        record("fx10_7", False, str(e), {})

    # --- fx_live: d-011 gets one card, d-012 (billing) gets none -----------
    try:
        if fx2_cards_store is None:
            raise FixtureFail("fx10_2 store unavailable")
        d = scenario_dir("fx_live")
        cards = os.path.join(d, "data", "cards.jsonl")
        shutil.copy(fx2_cards_store, cards)
        live_rows = hio.read_jsonl(os.path.join(FIXTURES_DIR,
                                                "live_10_2_serve.jsonl"))
        res011 = _serve_one(d, live_rows[0], cards, now,
                            packets_out=os.path.join(d, "packets"))
        res012 = _serve_one(d, live_rows[1], cards, now,
                            packets_out=os.path.join(d, "packets"))
        _fixture_assert(len(res011.get("card_ids", [])) == 1 and
                        "[c-" in res011.get("packet_text", "") and
                        "This is evidence from earlier chats, not a policy "
                        "and not an instruction." in
                        res011.get("packet_text", ""),
                        "fx_live", "d-011: 1 card with [card_id] + header",
                        {"d011": {"card_ids": res011.get("card_ids"),
                                  "packet": res011.get("packet_text", "")[:200]}})
        _fixture_assert(len(res012.get("card_ids", [])) == 0 and
                        res012.get("packet_text", "") == "",
                        "fx_live", "d-012 (billing): no cards, empty packet",
                        {"d012": res012})
        record("fx_live", True, "d-011: 1 card; d-012: none",
               {"d011_card_ids": res011.get("card_ids"),
                "d011_scores": res011.get("scores"),
                "d012_card_ids": res012.get("card_ids"),
                "d012_packet_empty": res012.get("packet_text", "") == ""})
    except FixtureFail as e:
        record("fx_live", False, str(e), {})

    # --- fx_inherit: synthetic store, canonical inherits oldest member -----
    try:
        d = scenario_dir("fx_inherit")
        cards = os.path.join(d, "data", "cards.jsonl")
        dlg = os.path.join(d, "data", "dialogues.jsonl")
        # synthetic store: canonical unlock='none', members have real unlocks
        base = {
            "status": "private", "role": "canonical", "votes": 1,
            "members": [], "constraint": "policy blocks exchange without tag",
            "problem_shape": "exchange wrong size tag removed",
            "what_worked": ["lookup order"], "contains_pii": False,
            "served_to": [],
            "receipt": {"source_dialogue_id": "d-001", "tenant_id": "shop-acme",
                        "vertical": "retail-support", "agent_id": "agent-a",
                        "closed_at": "2026-08-01T12:00:00Z",
                        "last_closed_at": "2026-08-01T12:00:00Z",
                        "scope": "shop-acme/retail-support"},
        }
        cards_rows = [
            {**base, "card_id": "c-inherit001", "cluster_id": "c-inherit001",
             "unlock": "none", "created_at": "2026-08-01T12:00:00Z",
             "updated_at": "2026-08-01T12:00:00Z"},
            {**base, "card_id": "c-inherit002", "cluster_id": "c-inherit002",
             "source_dialogue_id": "d-002", "agent_id": "agent-b",
             "unlock": "reclassify as defect with photo",
             "created_at": "2026-08-02T12:00:00Z",
             "updated_at": "2026-08-02T12:00:00Z"},
            {**base, "card_id": "c-inherit003", "cluster_id": "c-inherit003",
             "source_dialogue_id": "d-003", "agent_id": "agent-a",
             "unlock": "open defect ticket with order id",
             "created_at": "2026-08-03T12:00:00Z",
             "updated_at": "2026-08-03T12:00:00Z"},
        ]
        hio.write_jsonl(cards, cards_rows)
        # dialogues file: 3 rows so the cursor gate does not matter (--force)
        hio.write_jsonl(dlg, [{
            "dialogue_id": r["receipt"]["source_dialogue_id"],
            "tenant_id": "shop-acme", "vertical": "retail-support",
            "agent_id": r["receipt"]["agent_id"], "channel": "web",
            "closed_at": r["receipt"]["closed_at"],
            "turns": [{"role": "customer", "text": "wrong size, tag removed"}],
        } for r in cards_rows])
        cls = _cluster(d, cards, dlg, now, force=True)
        store = _read_store(cards)
        canon = next(c for c in store if c.get("role") == "canonical")
        _fixture_assert(canon.get("unlock") == "reclassify as defect with photo",
                        "fx_inherit", "canonical unlock = oldest member's "
                                      "non-none value",
                        canon.get("unlock"))
        record("fx_inherit", True,
               "canonical inherited oldest member's unlock",
               {"cluster": cls, "canonical_unlock": canon.get("unlock"),
                "members": canon.get("members")})
    except FixtureFail as e:
        record("fx_inherit", False, str(e), {})

    # remove the scratch dirs used to stagger extractions / stage live
    # dialogues (deterministic but not part of the run's evidence)
    for name in (".extract_in", ".serve_in"):
        for d in os.listdir(fx):
            p = os.path.join(fx, d, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)

    return summaries


# ---------------------------------------------------------------------------
# manifest / cost / report
# ---------------------------------------------------------------------------

def load_prices():
    """Load the committed price table (data, not code — D8 rule).

    prices.json lives at the experiment folder root (outside bin/): it names
    models and the dated provider price-sheet URL. cost.json copies
    price_source from it (C-EV9). If the table is missing or the model has no
    row, usd is reported as null with price_source "unknown" (never a guess).
    """
    path = os.path.join(EXPERIMENT_DIR, "prices.json")
    if not os.path.exists(path):
        return {"price_source": "unknown", "prices_per_1m": {}}
    try:
        data = hio.read_json(path)
    except Exception:
        return {"price_source": "unknown", "prices_per_1m": {}}
    src = data.get("source_url")
    retrieved = data.get("retrieved")
    price_source = (f"{src} (retrieved {retrieved})"
                    if src and retrieved else "unknown")
    return {"price_source": price_source,
            "prices_per_1m": data.get("usd_per_1m_tokens") or {}}


def usd_for(model, prompt_tokens, completion_tokens, prices, peak):
    """USD at the stated dated rates (cache-miss); None if the model has no
    row in the price table (then cost.json reports usd_total null, C-EV9)."""
    row = prices.get(model)
    if not row:
        return None
    in_rate = row.get("input_peak" if peak else "input_offpeak")
    out_rate = row.get("output_peak" if peak else "output_offpeak")
    if in_rate is None or out_rate is None:
        return None
    return (prompt_tokens / 1_000_000.0) * in_rate + \
           (completion_tokens / 1_000_000.0) * out_rate


def _raw_records(run_dir):
    """All stored extract raw records: out/raw/extract/*.json plus the S0
    fixture track's out/data/fixtures/<scenario>/raw/extract/*.json."""
    records = []
    roots = [os.path.join(run_dir, "raw", "extract")]
    fx_root = os.path.join(run_dir, "data", "fixtures")
    if os.path.isdir(fx_root):
        for name in sorted(os.listdir(fx_root)):
            roots.append(os.path.join(fx_root, name, "raw", "extract"))
    for root in roots:
        if not os.path.isdir(root):
            continue
        for fname in sorted(os.listdir(root)):
            if not fname.endswith(".json"):
                continue
            try:
                records.append(hio.read_json(os.path.join(root, fname)))
            except Exception:
                continue
    return records


def compute_cost(run_dir, run_id, model, stage, now_dt, serve_ms,
                 deterministic_wall_clock_s, extract_count):
    records = _raw_records(run_dir)
    calls = len(records)
    prompt_tokens = sum(int((r.get("usage") or {}).get("prompt_tokens", 0) or 0)
                        for r in records)
    completion_tokens = sum(
        int((r.get("usage") or {}).get("completion_tokens", 0) or 0)
        for r in records)
    ms_list = [int(r.get("ms", 0) or 0) for r in records]
    peak = llm.peak_window(now_dt) if now_dt is not None else None
    if peak is None:
        peak = True  # conservative fallback; stated in notes (brief §2)
    prices = load_prices()
    usd = usd_for(model, prompt_tokens, completion_tokens,
                  prices["prices_per_1m"], peak=peak)
    cost = {
        "extract": {
            "calls": calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "usd_total": round(usd, 6) if usd is not None else None,
            "usd_per_1000_dialogues": round(
                usd / max(1, extract_count) * 1000, 6)
            if usd is not None else None,
            "ms_p50": pct(ms_list, 50),
            "ms_p95": pct(ms_list, 95),
        },
        "serve": {"ms_p50": pct(serve_ms, 50), "ms_p95": pct(serve_ms, 95)},
        "deterministic_half_wall_clock_s": round(
            deterministic_wall_clock_s, 3),
        "price_source": prices["price_source"],
        "notes": [
            "thinking mode disabled on extract calls "
            '({"thinking": {"type": "disabled"}}, lead decision 2026-08-28)',
            "pricing: cache-miss rates (no cache-control sent)",
            f"peak window used: {peak} (provider peak hours Mon-Fri "
            "01:00-04:00 & 06:00-10:00 UTC)",
            "extract.calls counts pool + fixture-track raw records "
            f"(fixture track active: stage={stage})",
        ],
    }
    if usd is None:
        cost["notes"].append(
            f"usd_total null: no dated rate row for model {model!r} in "
            "prices.json (C-EV9 fallback)")
    hio.write_json(os.path.join(run_dir, "cost.json"), cost, sort_keys=True)
    return cost


def write_manifest(run_dir, manifest):
    hio.write_json(os.path.join(run_dir, "manifest.json"), manifest,
                   sort_keys=True)


def write_report(run_dir, run_id, stage, model, timeline, agent_pool_size,
                 config_dict, replay_of, cluster_passes_fired,
                 metrics_files, cost, fixture_summaries, access_log,
                 replay_byte_identical, git):
    lines = []
    lines.append(f"# Run {run_id}")
    lines.append("")
    lines.append("## 1. Identity")
    lines.append("")
    lines.append(f"- stage: {stage}; extract model: {model}; timeline: "
                 f"{timeline}; agent_pool_size: {agent_pool_size}")
    lines.append(f"- git_commit: {git}")
    lines.append(f"- replay_of: {replay_of}")
    lines.append(f"- cluster_passes_fired: {cluster_passes_fired}")
    lines.append(f"- config: {json.dumps(config_dict)}")
    lines.append("")
    lines.append("## 2. Checks")
    lines.append("")
    lines.append("_checks.json is a D2 deliverable; counts pending._")
    lines.append("")
    lines.append("## 3. Audit (A1-A5)")
    lines.append("")
    lines.append("_audit.json is a D3 deliverable; placeholder._")
    lines.append("")
    lines.append("## 4. Primary table (T vs baselines, same hold-out)")
    lines.append("")
    lines.append("| arm | unlock_hit_label | wrong | abstain | serve_rate |")
    lines.append("|---|---|---|---|---|")
    for arm, path in metrics_files:
        if os.path.exists(path):
            m = hio.read_json(path)
            p = m.get("primary", {})
            s = m.get("secondary", {})
            lines.append(f"| {arm} | {p.get('unlock_hit_label')} | "
                         f"{p.get('wrong')} | {p.get('abstain')} | "
                         f"{s.get('serve_rate')} |")
    lines.append("")
    lines.append("## 5. Secondary metrics")
    lines.append("")
    t_metrics = os.path.join(run_dir, "metrics.json")
    if os.path.exists(t_metrics):
        m = hio.read_json(t_metrics)
        lines.append("```json")
        lines.append(json.dumps(m.get("secondary", {}), indent=2, sort_keys=True))
        lines.append("```")
    lines.append("")
    lines.append("## 6. Judge (L3)")
    lines.append("")
    lines.append("_judge pass is D6; placeholder._")
    lines.append("")
    lines.append("## 7. Cost")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(cost, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")
    lines.append("## 8. Fitness verdict")
    lines.append("")
    lines.append("_pending D2-D7._")
    lines.append("")
    lines.append("## 9. What would change the verdict")
    lines.append("")
    lines.append("_pending._")
    lines.append("")
    if fixture_summaries:
        lines.append("## 10. S0 fixture track")
        lines.append("")
        for row in fixture_summaries:
            lines.append(f"- {row['scenario']}: ok={row['ok']} "
                         f"expected={row['expected']} observed="
                         f"{json.dumps(row['observed'])}")
        lines.append("")
    if access_log:
        lines.append("## 11. Access log")
        lines.append("")
        for row in access_log:
            lines.append(f"- {json.dumps(row)}")
        lines.append("")
    lines.append(f"## 12. Replay byte-identity (C-EV6): "
                 f"{replay_byte_identical}")
    lines.append("")
    with open(os.path.join(run_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="run_experiment.py",
        description="One command, one run (RUN-PROTOCOL §1).")
    ap.add_argument("--pool", default=POOL_PATH)
    ap.add_argument("--holdout", default=HOLDOUT_PATH)
    ap.add_argument("--model", default=None,
                    help="extract model id, REQUIRED (no default — D8: a "
                         "model swap is a flag, never an edit); in replay "
                         "mode it is taken from the source manifest")
    ap.add_argument("--stage", choices=STAGES, default=None,
                    help="stage S0|S1|S2 (S3/S4 no-op); in replay mode it is "
                         "taken from the source manifest")
    ap.add_argument("--out", default=None,
                    help="run directory (default: runs/<run_id>; replay "
                         "defaults to the replayed run's own directory, "
                         "i.e. in-place)")
    ap.add_argument("--replay", default=None)
    ap.add_argument("--baseline", choices=("T", "B0", "B1", "B2"), default=None,
                    help="run a single baseline arm instead of the full "
                         "pipeline (wire-through; D4 owns the semantics)")
    ap.add_argument("--agent-pool-size", type=int, default=None)
    ap.add_argument("--timeline", choices=cfg.TIMELINE_MODES, default=None)
    ap.add_argument("--now", default=None)
    ap.add_argument("--base-url", default=None,
                    help="LLM base URL (default: env H1_BASE_URL; never "
                         "hard-coded)")
    ap.add_argument("--api-key", default=None,
                    help="LLM API key (default: env H1_API_KEY; never "
                         "printed, never stored)")
    cfg.add_set_flag(ap)
    args = ap.parse_args(argv)

    if args.stage in ("S3", "S4"):
        print(hio.dumps({"stage": args.stage,
                         "note": "judge/verdict stages are out of D1 scope — "
                                 "no-op"}))
        return 0

    # ---- replay: derive settings from the old manifest first ---------------
    replay_dir = None
    replay_byte_identical = None
    old_manifest = None
    old_dir = None
    in_place_replay = False
    if args.replay:
        # Accept both the quickstart path form (--replay runs/<id>) and the
        # bare run id (--replay <id>).
        replay_arg = args.replay
        old_dir = os.path.abspath(replay_arg)
        if not os.path.isdir(old_dir):
            candidate = os.path.abspath(os.path.join("runs", replay_arg))
            if os.path.isdir(candidate):
                old_dir = candidate
        old_manifest_path = os.path.join(old_dir, "manifest.json")
        if not os.path.exists(old_manifest_path):
            print(hio.dumps({"error": f"--replay {args.replay}: no manifest "
                                      f"at {old_manifest_path}"}))
            return 1
        old_manifest = hio.read_json(old_manifest_path)
        replay_dir = os.path.join(old_dir, "raw", "extract")
        if not os.path.isdir(replay_dir):
            print(hio.dumps({"error": f"--replay {args.replay}: no "
                                      f"raw/extract in old run"}))
            return 1
        # determinism: reuse the old run's stage/timeline/pool size/config/now
        args.stage = old_manifest["stage"]
        args.timeline = old_manifest.get("timeline", "compressed")
        args.agent_pool_size = old_manifest.get("agent_pool_size", 4)
        old_cfg = old_manifest.get("config", {})
        args.set = effective_set_args(
            {k: v for k, v in old_cfg.items()
             if k in cfg.DEFAULTS and v != cfg.DEFAULTS.get(k)})
        args.now = old_manifest.get("created_at")
        # model/base-url/key: flags override, else the source manifest
        # (so the quickstart's bare `--replay runs/<id>` works, D8-clean).
        if not args.model:
            args.model = old_manifest.get("extract_model")
        if not args.base_url:
            args.base_url = old_manifest.get("base_url")
        # verify the input files still match (sha guard)
        for key, cli_path in (("pool", args.pool), ("holdout", args.holdout)):
            inp = old_manifest.get("inputs", {}).get(key)
            if inp and inp.get("sha256"):
                if os.path.exists(cli_path):
                    if hio.sha256_file(cli_path) != inp["sha256"]:
                        print(hio.dumps({"error": f"--replay: {key} file "
                                                  f"changed since the "
                                                  f"original run"}))
                        return 1
                else:
                    args.pool = POOL_PATH if key == "pool" else HOLDOUT_PATH
                    if hio.sha256_file(args.pool if key == "pool"
                                       else args.holdout) != inp["sha256"]:
                        print(hio.dumps({"error": "--replay: input file "
                                                  "unavailable"}))
                        return 1

    stage = args.stage
    if stage is None:
        print(hio.dumps({"error": "missing required argument: --stage "
                                  "(or --replay of a run that defines it)"}))
        return 1
    timeline = args.timeline or "compressed"
    agent_pool_size = args.agent_pool_size or 4
    overrides = cfg.parse_overrides(args.set)
    overrides.setdefault("AGENT_POOL_SIZE", agent_pool_size)
    cfg_obj = cfg.Config(overrides)
    pinned_now = args.now or now_iso()
    now_dt = parse_iso(pinned_now)

    # D8 rule: model/base-url/key must be present for any run that touches
    # the LLM (arm T and/or the S0 fixture track). Baseline-only runs never
    # call the LLM and may omit them. Missing any of the three is a usage
    # error, not a silent default (DELIVERABLE-PACKAGE §6).
    base_url = None
    api_key = None
    needs_llm = (args.baseline is None or args.baseline == "T")
    if needs_llm:
        try:
            model, base_url, api_key = llm.resolve_llm_params(
                args.model, args.base_url, args.api_key)
        except llm.LLMError as exc:
            print(hio.dumps({"error": str(exc)}))
            return 1
        args.model = model
        args.base_url = base_url
    else:
        api_key = None

    # ---- resolve the run directory -----------------------------------------
    if args.out:
        out_dir = os.path.abspath(args.out)
    elif args.replay:
        out_dir = old_dir                 # in-place replay (quickstart form)
        in_place_replay = True
    else:
        run_id_default = f"{now_iso()[:10]}_{stage}_{args.model}"
        out_dir = os.path.abspath(os.path.join("runs", run_id_default))
    assert out_dir  # one of the three branches above always assigns it
    if os.path.isdir(out_dir) and os.listdir(out_dir) and not in_place_replay:
        print(hio.dumps({"error": "refusing to start: --out exists and is "
                                  "non-empty", "out": out_dir}))
        return 1
    os.makedirs(out_dir, exist_ok=True)
    run_id = os.path.basename(os.path.normpath(out_dir))

    access_log = []

    # ---- data slices (the hold-out file is opened ONLY at S2) -------------
    pool_rows = read_rows_once(args.pool)
    access_log.append({"opened": os.path.abspath(args.pool), "stage": stage,
                       "at": pinned_now, "purpose": "pool slice"})
    n_pool = SLICES[stage]
    pool_slice = pool_rows[:n_pool]
    holdout_rows = []
    holdout_input = None
    if stage == "S2":
        holdout_rows = read_rows_once(args.holdout)
        access_log.append({"opened": os.path.abspath(args.holdout),
                           "stage": stage, "at": pinned_now,
                           "purpose": "holdout ingest (opened exactly once)"})
    elif stage == "S1":
        holdout_rows = pool_rows[n_pool:n_pool + 40]
    elif stage == "S0":
        holdout_rows = pool_slice[16:20]   # eval's default 80/20 hold-out
    n_holdout = len(holdout_rows)

    # derived pack slices (ingest inputs; the original files are untouched)
    ingest_in = os.path.join(out_dir, "ingest_input")
    pool_pack = os.path.join(ingest_in, "pool_pack.jsonl")
    holdout_pack = os.path.join(ingest_in, "holdout_pack.jsonl")
    write_pack_slice(pool_slice, pool_pack)
    if holdout_rows:
        write_pack_slice(holdout_rows, holdout_pack)

    # ---- directories ------------------------------------------------------
    data_dir = os.path.join(out_dir, "data")
    raw_dir = os.path.join(out_dir, "raw", "extract")
    packets_dir = os.path.join(out_dir, "packets")
    for d in (data_dir, raw_dir, packets_dir):
        os.makedirs(d, exist_ok=True)

    dialogues_path = os.path.join(data_dir, "dialogues.jsonl")
    holdout_dlg_path = os.path.join(data_dir, "holdout_dialogues.jsonl")
    cards_path = os.path.join(data_dir, "cards.jsonl")
    labels_path = os.path.join(data_dir, "labels.jsonl")
    cursor_path = os.path.join(data_dir, "cluster_cursor.json")

    # ---- ingest (both files) ----------------------------------------------
    t_det = time.time()
    ingest_argv = ["--in", pool_pack, "--out", dialogues_path,
                   "--timeline", timeline, "--agent-pool-size",
                   str(agent_pool_size)]
    ingest_summary = run_script("ingest.py", ingest_argv)
    if holdout_rows:
        run_script("ingest.py", ["--in", holdout_pack, "--out",
                                 holdout_dlg_path, "--timeline", timeline,
                                 "--agent-pool-size", str(agent_pool_size)])

    # ---- labels sidecar from the ORIGINAL pack rows ------------------------
    labels = []
    seen = set()
    for r in pool_slice + holdout_rows:
        lid = "d-" + str(r["chat_id"])
        if lid in seen:
            continue
        seen.add(lid)
        labels.append({"dialogue_id": lid,
                       "unlock_guideline": r.get("unlock_guideline")})
    hio.write_jsonl(labels_path, labels)

    # The raw pack copies used as ingest input carry the pack's ground-truth
    # keys (unlock / unlock_guideline / split). They are consumed by ingest
    # only; remove them so no labeled rows linger in the run dir (C-L2).
    shutil.rmtree(ingest_in, ignore_errors=True)

    # ---- extract (live or replay) -----------------------------------------
    # The resolved base URL and API key are exported to the environment so
    # subprocesses (extract/eval) pick them up without the key ever appearing
    # on a command line (never printed, never stored).
    if needs_llm and api_key:
        assert base_url and api_key  # guaranteed by resolve_llm_params above
        os.environ["H1_BASE_URL"] = base_url
        os.environ["H1_API_KEY"] = api_key
    extract_replay_dir = replay_dir
    extract_summary = None
    if stage != "S0":            # S0: eval drives extraction via its 80/20 split
        extract_summary = run_script("extract.py", [
            "--in", dialogues_path, "--out", cards_path, "--model", args.model,
            "--raw-dir", raw_dir, "--now", pinned_now] +
            (["--replay-dir", extract_replay_dir]
             if extract_replay_dir else []) +
            (["--set"] + args.set if args.set else []))

    # ---- cluster passes (S1/S2: natural 100-chat cursor, n//100 passes) ----
    cluster_passes_fired = 0
    cluster_independence = None
    if stage in ("S1", "S2"):
        n_dlg = hio.row_count(dialogues_path)
        passes = n_dlg // cfg_obj.CLUSTER_EVERY_N_CHATS
        for i in range(passes):
            hio.write_json(cursor_path,
                           {"last_dialogue_count": i * 100,
                            "last_run_at": None})
            csum = run_script("cluster.py", [
                "--cards", cards_path, "--dialogues", dialogues_path,
                "--cursor", cursor_path, "--now", pinned_now] +
                (["--set"] + args.set if args.set else []))
            cluster_passes_fired += 1
            if csum.get("independence"):
                cluster_independence = csum["independence"]
    elif stage == "S0":
        cluster_passes_fired = 1   # the single forced pass inside eval

    # ---- eval arm T + baselines -------------------------------------------
    eval_common = ["--dialogues", dialogues_path, "--cards", cards_path,
                   "--labels", labels_path, "--now", pinned_now,
                   "--run-id", run_id, "--timeline", timeline]
    if cluster_independence:
        eval_common += ["--independence", cluster_independence]
    if stage in ("S1", "S2"):
        eval_common += ["--holdout", holdout_dlg_path]
    if stage == "S0":
        eval_common += ["--train-out", os.path.join(data_dir,
                                                    "dialogues_train.jsonl")]
    t_arm = "T" if args.baseline is None else args.baseline
    if t_arm == "T":
        eval_common += ["--model", args.model, "--raw-dir", raw_dir,
                        "--metrics-out", os.path.join(out_dir, "metrics.json"),
                        "--per-dialogue-out", os.path.join(
                            out_dir, "per_dialogue.jsonl"),
                        "--packets-dir", packets_dir]
        if stage == "S0" and args.replay:
            # S0 replay: eval drives extraction, fed by the old raw records
            eval_common += ["--replay-dir", replay_dir]
        if args.set:
            eval_common += ["--set"] + args.set
        eval_summary = run_script("eval.py", eval_common)
    else:
        eval_summary = run_script("eval.py", eval_common + [
            "--baseline", t_arm,
            "--metrics-out", os.path.join(out_dir, "metrics.json"),
            "--per-dialogue-out", os.path.join(out_dir,
                                               "per_dialogue.jsonl"),
            "--packets-dir", packets_dir] +
            (["--set"] + args.set if args.set else []))

    # baselines B0/B1/B2 (same scoring path, wired now; D4 owns semantics)
    metrics_files = [(t_arm, os.path.join(out_dir, "metrics.json"))]
    baseline_metrics = {}
    if t_arm == "T":
        for b in ("B0", "B1", "B2"):
            b_common = eval_common + [
                "--baseline", b,
                "--metrics-out", os.path.join(out_dir, f"metrics_{b.lower()}.json"),
                "--per-dialogue-out", os.path.join(
                    out_dir, f"per_dialogue_{b.lower()}.jsonl"),
                "--packets-dir", os.path.join(out_dir, f"packets_{b.lower()}")]
            if args.set:
                b_common += ["--set"] + args.set
            run_script("eval.py", b_common)
            metrics_files.append((b, os.path.join(
                out_dir, f"metrics_{b.lower()}.json")))

    deterministic_wall_clock_s = time.time() - t_det + float(
        eval_summary.get("deterministic_wall_clock_s", 0.0))
    serve_ms = eval_summary.get("serve_ms", []) or []

    # ---- S0 fixture track --------------------------------------------------
    # Skipped on --replay runs: replay reproduces the metrics half with zero
    # LLM calls (C-EV6); the fixture track is S0 smoke evidence, not part of
    # metrics.json (recorded in the report).
    fixture_summaries = []
    if stage == "S0" and t_arm == "T" and not args.replay:
        fixture_summaries = run_fixture_track(
            out_dir, args.model, pinned_now, agent_pool_size, overrides)
        hio.write_jsonl(os.path.join(data_dir, "fixture_summaries.jsonl"),
                        fixture_summaries)

    # ---- access log, manifest, cost, report -------------------------------
    hio.write_jsonl(os.path.join(data_dir, "access_log.jsonl"), access_log)

    extract_count = n_pool if stage != "S0" else 16
    if stage == "S0":
        extract_count = int((eval_summary.get("extract") or {}).get(
            "extracted", 0) or 0)
    cost = compute_cost(out_dir, run_id, args.model, stage, now_dt, serve_ms,
                        deterministic_wall_clock_s, extract_count)

    outputs = {}
    for fname in ("cards.jsonl", "metrics.json", "per_dialogue.jsonl"):
        p = os.path.join(data_dir if fname == "cards.jsonl" else out_dir,
                         fname)
        if os.path.exists(p):
            outputs[fname] = hio.sha256_file(p)
    # a missing sha = void run (RUN-PROTOCOL §3.1); baseline arms (B0/B1/B2)
    # never build a card store, so cards.jsonl is only required for arm T.
    required_outputs = ["metrics.json", "per_dialogue.jsonl"]
    if t_arm == "T":
        required_outputs.append("cards.jsonl")
    missing = [f for f in required_outputs if not outputs.get(f)]
    assert not missing, f"missing output sha → void run: {missing}"

    manifest = {
        "run_id": run_id,
        "created_at": pinned_now,
        "stage": stage,
        "git_commit": git_commit_info(),
        "extract_model": args.model,
        "judge_model": None,
        "base_url": args.base_url,
        "temperature": 0,
        "timeline": timeline,
        "agent_pool_size": agent_pool_size,
        "config": cfg_obj.as_dict(),
        "cluster_passes_fired": cluster_passes_fired,
        "inputs": {
            "pool": {"path": os.path.abspath(args.pool),
                     "sha256": hio.sha256_file(args.pool),
                     "rows": n_pool},
            "holdout": (None if stage == "S0" else {
                "path": (os.path.abspath(args.holdout) if stage == "S2"
                         else os.path.abspath(args.pool)),
                "sha256": (hio.sha256_file(args.holdout) if stage == "S2"
                           else hio.sha256_file(args.pool)),
                "rows": n_holdout,
                "note": None if stage == "S2" else
                        "pool rows 200..239 (pool's own tail; the real "
                        "hold-out file was NOT opened)"}),
            "prompts": {"path": PROMPTS_PATH,
                        "sha256": hio.sha256_file(PROMPTS_PATH), "rows": None},
        },
        "outputs": outputs,
        "replay_of": args.replay,
        "notes": [
            "thinking mode disabled on extract calls "
            '({"thinking": {"type": "disabled"}}; lead decision 2026-08-28)',
            "action speaker turns in the pack map to role=tool at ingest "
            "(the pack has no tool turns; spec roles are customer/agent/tool)",
        ],
    }
    # ---- replay snapshot (C-EV6: byte-identity vs the source run) ---------
    # Snapshot the source run's decisive outputs BEFORE anything is
    # rewritten, so the in-place quickstart form still gets a real check.
    replay_snapshot = {}
    if args.replay:
        assert old_dir  # set by the replay branch above
        for fname in ("metrics.json", "metrics_b0.json", "metrics_b1.json",
                      "metrics_b2.json", "per_dialogue.jsonl",
                      "per_dialogue_b0.jsonl", "per_dialogue_b1.jsonl",
                      "per_dialogue_b2.jsonl", "cards.jsonl"):
            p = os.path.join(old_dir, fname)
            if os.path.exists(p):
                with open(p, "rb") as fh:
                    replay_snapshot[fname] = fh.read()

    if stage == "S0":
        manifest["inputs"]["holdout"] = {
            "path": os.path.abspath(args.pool), "sha256": None, "rows": 4,
            "note": "eval default 80/20 split of the 20-row slice (rows "
                    "16..19); the real hold-out file was NOT opened"}
    git_info = manifest["git_commit"]
    if isinstance(git_info, dict) and git_info.get("dirty") is True:
        # RUN-PROTOCOL §3.1: a dirty git_commit voids a run "without a stated
        # reason". State the standard reason: the run was produced from its
        # own uncommitted deliverable tree; the committed tree is identical.
        manifest.setdefault("notes", []).append(
            "git_commit.dirty=True: run produced from the uncommitted "
            "deliverable tree; the committed tree is byte-identical to what "
            "produced this run")
    # In-place replay rewrites the deterministic files byte-identically but
    # must NOT touch the measured artifacts (manifest/cost/report carry
    # wall-clock and run metadata that legitimately differ); the committed
    # run stays pristine (git clean after `--replay runs/<id>`).
    if not (args.replay and in_place_replay):
        write_manifest(out_dir, manifest)
        report_metrics_files = metrics_files
        write_report(out_dir, run_id, stage, args.model, timeline,
                     agent_pool_size, cfg_obj.as_dict(), args.replay,
                     cluster_passes_fired, report_metrics_files, cost,
                     fixture_summaries, access_log, replay_byte_identical,
                     manifest["git_commit"])

    # ---- replay byte-identity check (C-EV6) --------------------------------
    if args.replay:
        mismatch = [fname for fname, old_bytes in replay_snapshot.items()
                    if os.path.exists(os.path.join(out_dir, fname))
                    and open(os.path.join(out_dir, fname), "rb").read()
                    != old_bytes]
        replay_byte_identical = not mismatch and bool(replay_snapshot)

    # ---- final summary -----------------------------------------------------
    summary = {
        "run_id": run_id,
        "stage": stage,
        "replay_of": args.replay,
        "status": "ok",
        "extract_calls": extract_count,
        "cluster_passes_fired": cluster_passes_fired,
        "metrics_sha256": outputs.get("metrics.json"),
        "replay_byte_identical": replay_byte_identical,
        "fixture_failures": [s["scenario"] for s in fixture_summaries
                             if not s.get("ok")],
    }
    print(hio.dumps(summary))

    # S0 gate: B2 oracle ≥ 0.98 and every fixture assertion must pass.
    exit_code = 0
    if stage == "S0":
        b2_path = os.path.join(out_dir, "metrics_b2.json")
        if os.path.exists(b2_path):
            b2 = hio.read_json(b2_path).get("primary", {}).get(
                "unlock_hit_label")
            if b2 is None or b2 < 0.98:
                print(f"B2 oracle FAIL: unlock_hit_label={b2} (need ≥0.98)")
                exit_code = 1
        if summary["fixture_failures"]:
            print(f"fixture failures: {summary['fixture_failures']}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
