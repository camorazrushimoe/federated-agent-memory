# Round-2 Strip Plan — PR #38 (evaluation lane) → additive-only

Status: prepared 2026-08-28 ~20:10Z, before PR #35 lands. Gated on the founder
merging #35 (Lead READY posted 19:59:53Z on PR #35). This document is the
execution map; the actual rebase + strip happens after #35 is on main.

## 1. Contract (committed rulings, read before anything)

- `EVAL-PLAN.md` §7.1 — A4 threshold sweep, selection rule FIXED (largest
  threshold with cluster_purity >= 0.70 AND serve_rate_ceiling >= 0.30; ties →
  larger; nothing satisfies both → NOT FIT, publish curve, stop).
- `CHECKS.md` C-EX4a (HARD: no invented numbers/identifiers/tool names/proper
  nouns — every such token in a card must appear in the transcript) and
  C-EX4b (SOFT: lexical overlap rate per field, reported, never aborting,
  flagged cards → L3 judge sample). A single C-EX4 id = stale code.
- `LAB-BRIEF.md` §1.1 — one module, one owner; #38 additive only; three
  redundant branches abandoned; no edits to another lane's module in my tree.

## 2. PR #38 file inventory after the strip

My branch currently has 22 bin/ modules. After rebase onto post-#35 main and
strip:

### KEEP (additive-only, 9 modules)
`audit.py`, `checks.py`, `compare.py`, `a4_verify.py`, `schema.py`, `scrub.py`,
`store.py`, `clock.py`, `prompts.py` + my fixtures + the D8 package files
(runs/REFERENCE.md additions, runs/.gitignore, checks.json/controls.json run
outputs that are genuinely additive).

### DROP (duplicates of canonical #35 modules, 13)
`cluster.py`, `eval.py`, `extract.py`, `match.py`, `serve.py`, `tick.py`,
`run_experiment.py`, `config.py`, `feedback.py`, `ingest.py`, `llm.py`,
`promote.py`, `tfidf.py`.

Rationale: canonical #35 provides all of these (common.py covers tfidf).
Any of mine that is genuinely better = a separate ONE-FILE PR against the
canonical module with the reason — not a second pipeline (LAB-BRIEF 1.1).

### DROP doc edits superseded by round-2 rules
- `EVAL-PLAN.md` +25 (my "A4 prerequisite — TF-IDF recipe fix" note): the
  round-2 rules (PR #40) rewrote §7.1 with the sweep; the smoothed-IDF fix is
  now verified in canonical `common.py:112` by the Lead's re-execution. Drop
  my edit on rebase (resolve conflict → take main's version).

## 3. Import rewire map (my kept modules → canonical modules)

My kept modules import from my dropped modules with DIFFERENT APIs. Each line
below must be rewired during the strip:

| my module | current import | canonical replacement | notes |
|---|---|---|---|
| `audit.py` | `import config as cfgmod` (`cfgmod.DEFAULTS`, `resolve_config`, `utcnow_iso`) | `from common import now_iso`; config via canonical `Config`/`make_config` | canonical config has no `utcnow_iso`/`resolve_config` |
| `audit.py` | `from cluster import compute_votes` → `compute_votes(c, members)` (2 args) | canonical `compute_votes(canonical, members, dialogues)` (3 args) | canonical needs dialogues for `_agent_of` |
| `audit.py` | `from eval import load_labels, score_holdout` | canonical eval has NO `load_labels`/`score_holdout`; use `score_outcome(packet_labels, true_label)` + `card_label_for` or subprocess `eval.py --baseline B2` | the C-EV5 one-scoring-path constraint |
| `audit.py` | `from schema import card_text` | `from common import card_text` | canonical common.card_text identical |
| `audit.py` | `from store import read_jsonl` | `from jsonio import read_jsonl` | store.py stays but delegates IO to jsonio |
| `audit.py` | `from tfidf import TfidfModel` → `TfidfModel(docs).cosine(a,b)` | `from common import TFIDF` → `TFIDF().fit(texts).score(q,d)` | API differs: fit/score, not constructor+cosine |
| `a4_verify.py` | `from tfidf import TfidfModel` (LOCAL import, line 62) + `.cosine()` | `from common import TFIDF` + `.score()` | same API change; two call sites (lines 79-83, 92-95) |
| `checks.py` | `import config as cfgmod` (`cfgmod.DEFAULTS`) | canonical `config.DEFAULTS` | line 361, 1256 |
| `checks.py` | `from clock import RunClock` | KEEP (clock.py is mine) | — |
| `checks.py` | `from cluster import compute_votes, last_closed_at` (2-arg, `last_closed_at`) | canonical `compute_votes(canonical, members, dialogues)` + `compute_last_closed_at(canonical, members, dialogues)` | name AND signature differ |
| `checks.py` | `from eval import score_holdout, load_labels` (control C-EV5 / NC3) | canonical eval CLI or `score_outcome`+`card_label_for` | C-EV5 source-scan regex also changes (canonical has no `def score_holdout`) |
| `checks.py` | `from store import read_jsonl, write_jsonl` | `from jsonio import read_jsonl, write_jsonl` | — |
| `checks.py` | `from tfidf import TfidfModel` | `from common import TFIDF` | — |
| `checks.py` | `from scrub import EMAIL_RE, PHONE_RE, DIGITS_RE, TOKEN_RE` | keep scrub.py (mine) but have it re-export canonical rules or wrap `common.pii_matches` | C-EX5 scan must use ONE source of regexes |
| `checks.py` | `from match import match_cards` (list arg, line 236/1162/1173/1220) | canonical `match_cards(dialogue, cards_path, overrides)` (PATH arg) | canonical reads cards from a path; NC4 helper must write a temp cards file |
| `checks.py` | `from prompts import Prompts` (line 1240) | keep prompts.py (mine); unused in FixtureSuite (`self.prompts` stored, never read) | can drop the fixture-suite prompts param |
| `clock.py` | `from config import iso, parse_iso` | canonical has neither in config; `from common import parse_iso` + local `iso()` formatter | clock.py is additive; keep a local iso() |

## 3b. Discovery (20:25Z, scratch validation): canonical owns the fixture track + the scoring path

Two findings from probing canonical-35 that tighten the rewire:

1. **Canonical `run_experiment.py` ALREADY runs its own §10 fixture track**
   (`run_fixture_track`, `run_experiment.py:229`, proven 9/9 by the Lead's
   re-execution) with its own fixtures (`dialogue_10_*.jsonl`,
   `live_10_2_serve.jsonl`) and its own helpers `_ingest/_extract/_cluster/
   _serve_one`. My `checks.py` FixtureSuite drives the SAME pipeline scripts
   via subprocess — it must be rewired to the CANONICAL CLIs, not to my
   dropped modules:
   - extract: `--replay --clock-start N` → `--replay-dir <fixtures/raw/extract> --now N`
   - serve:   `--packets-dir <dir> --clock-start N` → `--packets-out <dir> --now N`
   - feedback:`--feedback-out <file> --clock-start N`, optional `--card-id`
     → `--feedback <file> --now N`; canonical `--card-id` is REQUIRED
     (argparse). The C-FB4 "ambiguous packet, no card-id" fixture still fails
     (usage error) but for a different reason — note it in the row.
   - ingest/cluster flags are compatible (canonical adds `--timeline`, `--cursor`).

2. **Canonical `eval.py` is a CLI (`run_eval(args)`), not a library** with
   `score_holdout`/`load_labels`. The controls in `checks.py`
   (`run_controls`: NC3, C-EV3/4/5, B0/B1/B2) must shell out to canonical
   `eval.py --baseline B0|B1|B2 ...` with a labels sidecar
   (`{dialogue_id, unlock_guideline}` JSONL — the runner already writes one at
   `data/labels.jsonl`) and read `metrics.json` `primary.unlock_hit_label`.
   This keeps the ONE scoring path (C-EV5) instead of importing a second copy.
   C-EV5's source scan target changes from `def score_holdout` to
   `def score_outcome`.

Both findings are recorded here so the post-#35 strip is mechanical, and both
were validated in the scratch worktree (canonical head aa11260 + my kept
modules) with zero LLM calls.

## 3c. Scratch-validated rewire (20:40Z) — all nine kept modules run against canonical aa11260

Executed in `/opt/data/h1-strip-scratch` (worktree at canonical-35 = what main
becomes after #35) with ZERO LLM calls:

- **clock.py** — self-contained `iso()`/`parse_iso()` (canonical has no
  `iso(dt)` formatter); RunClock tests pass.
- **schema.py** — `card_id_for`/`card_text` now imported from canonical
  `common` (one implementation); `validate_card`/`is_rejected` etc. kept.
- **scrub.py** — thin delegation to canonical `common` (`pii_matches`,
  `scrub_pii`, `scrub_text`); C-EX5 scan now uses `common.pii_matches`.
- **store.py** — re-exports canonical `jsonio` IO; keeps `upsert_rows`/
  `upsert_cards` as the only additive functions.
- **a4_verify.py** — `TfidfModel(docs).cosine(a,b)` → `TFIDF().fit(docs).score(a,b)`.
- **audit.py** — canonical `Config`, `compute_votes(c,m,dialogues_lookup)`,
  `score_outcome` (B2 oracle), `jsonio.read_jsonl`, `TFIDF`. Runs end-to-end:
  A1..A5 computed, B2 oracle = 1.0. **Latent bug found + fixed**: A1 fed the
  raw-pack holdout (`tenant`/`chat_id`) against ingested pool rows
  (`tenant_id`/`dialogue_id`) → KeyError at S1; audit.py now normalizes the
  holdout slice to the ingested shape. (audit.py is my module; fix is in-lane.)
- **checks.py** — FixtureSuite now drives canonical CLIs (`--replay-dir`,
  `--now`, `--packets-out`, `--feedback`, `--card-id` required); `match_cards`
  called path-based; C-EV5 scan targets `def score_outcome`; controls + B0/B1/B2
  shell out to canonical `eval.py --baseline X` via `_run_eval_arm` with a
  labels sidecar (ONE scoring path). Fixture suite exit 0 against canonical
  modules; control arms measured: B0 abstain 1.0, B2 hit 1.0, T abstain 1.0.
- **compare.py / prompts.py** — import-clean, unchanged.

Verification numbers are in the scratch worktree logs
(`/tmp/h1_scratch_fixture.log`, `/tmp/h1_audit_test/audit.json`).

FixtureSuite drives the pipeline by subprocess; canonical CLIs differ:

| step | my flags | canonical flags |
|---|---|---|
| extract | `--replay --clock-start N` | `--replay-dir <dir> --now N` (replay is a dir arg, not a flag) |
| serve | `--packets-dir <dir> --clock-start N` | `--packets-out <dir> --now N` |
| feedback | `--feedback-out <file> --clock-start N`, `--card-id` optional | `--feedback <file> --now N`, `--card-id` REQUIRED (argparse) |
| ingest / cluster | `--in --out` / `--cards --dialogues --now --force` | compatible (canonical adds `--timeline`, `--cursor` defaults) |

Consequence for C-FB4: canonical feedback.py makes `--card-id` mandatory at
argparse level, so the "ambiguous packet, no --card-id" fixture fails for a
different reason (usage error). Fixture expectation must be updated to match
the canonical contract (still a failure; note the reason).

## 5. D8 package files

- runs/REFERENCE.md: merge my additive content onto canonical's version.
- runs/2026-08-28_S0_deepseek-v4-flash/: canonical's files win for
  cost/manifest/metrics/per_dialogue/report/raw; my additive
  checks.json/controls.json (D2 gate outputs) survive.
- MODEL-MATRIX.md / RESULTS.md / README.md: both PRs touch them; take
  canonical's versions as base and re-apply only my additive content
  (compare.py-generated rows, D8 quickstart notes) — no rewrite of canonical
  text.

## 6. Verification gate after the strip (must all pass before push)

1. `python -c "import ast; ..."` or runner: every kept module imports resolve
   (no reference to dropped modules: cluster/eval/extract/match/serve/tick/
   run_experiment/config/feedback/ingest/llm/promote/tfidf).
2. Zero-LLM fixture suite: `python bin/checks.py` green on the canonical
   binaries (no API key needed — replay/fixtures only).
3. `python bin/audit.py` runs on pool slice; A1–A5 numbers appear.
4. grep: no model/endpoint/key literal in bin/ (D8 rule).
5. `--replay` of the committed S0 run still byte-identical (uses canonical
   runner, zero LLM calls).
6. checks.json reports C-EX4a and C-EX4b ids (never a bare C-EX4) — this is
   STEP 3 of the order and lands with/after the sweep.

## 7. Order of execution (do NOT parallelise)

STEP 1: this strip (after #35 merges) → push → founder reviews #38.
STEP 2: A4 threshold sweep on the POOL only (0.05…0.35 step 0.01) with the
        fixed selection rule; commit `audit_threshold_sweep.md` + raw rows in
        `audit.json`. Hold-out stays frozen.
STEP 3: C-EX4a (HARD) / C-EX4b (SOFT) in checks.py; flagged cards → L3 sample.
STEP 4: S1 (200 pool + 40 pool tail) with the derived threshold — only after
        steps 1–3 are landed and merged by the founder.

Structural alternative (clustering on customer turns) = follow-up F5, changes
SPEC.md §5 — NOT implemented in this pass.

## 3e. Post-merge verification (21:40Z) — D2 gate CLI + determinism fixes (`38c08f6`)

After #38 merged, the D2 gate had NO CLI entry (checks.py main() ran only the
fixture suite) and the fixture/NC1 rewires had reproducibility defects that
only surface when the full registry runs against a canonical-runner-produced
run dir. Fixed + verified on a fresh canonical S0 run (59/59 HARD, exit 0):

- `checks.py --run-dir <dir> --pool P --holdout H` — the D2 gate: loads
  manifest/metrics/cost/data, runs fixture suite + negative controls (canonical
  eval CLI) + full registry, writes checks.json/controls.json/audit.json, exits
  2 on any HARD failure.
- FixtureSuite replay source = committed fixtures (read-only); raw output =
  workdir-local (canonical copy_replay_record WRITES to raw-dir — the merged
  version clobbered committed d-*.json on every run, C-L1).
- FixtureSuite + NC1 start from a CLEAN workdir (ingest/extract/cluster/
  feedback UPSERT; stale dirs accumulated duplicates: C-CL10 11 cards,
  C-FB2 14 rows).
- C-EV6 replay runs in-place on an identically-named copy (run_id derives from
  the out-dir basename) → byte-identical confirmed.
- C-EV7 requires shas only where recorded (canonical leaves holdout.sha256
  null at S0); C-EX10 counts fixture-track raw records (16 pool + 26 fx = 42);
  NC1 slice built from RAW pool rows filtered to recorded ids.
- Pipeline-owner finding (reported, not fixed): the canonical runner's S0
  fixture track uses LIVE extraction, not committed replay records —
  non-deterministic (fx10_2 passed/failed across two identical runs).
