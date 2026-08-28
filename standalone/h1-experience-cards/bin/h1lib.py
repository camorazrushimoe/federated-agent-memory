#!/usr/bin/env python3
"""h1lib.py — shared helpers for the H1 experience-card pipeline.

Contract: SPEC.md (standalone/h1-experience-cards/SPEC.md), CHECKS.md.
Stdlib only (SPEC §2). No imports from anywhere else in the repository (C-L3).
All functions deterministic unless stated otherwise.

The one config object (SPEC §5: "Defaults (change only in one config object)").
The values below are the defaults; every script accepts --config key=value
overrides and records the merged object in the manifest.
"""

import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

H1_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS_PATH = os.path.join(H1_DIR, "PROMPTS.md")

# --------------------------------------------------------------------------
# Config (the ONE config object, SPEC §5)
# --------------------------------------------------------------------------

DEFAULTS = {
    "K_INDEPENDENT": 2,
    "MAX_PACKET": 3,
    "STALE_AFTER_DAYS": 30,
    "MATCH_THRESHOLD": 0.18,
    "CLUSTER_THRESHOLD": 0.35,
    "CLUSTER_EVERY_N_CHATS": 100,
    # Run timeline origin (RUN-PROTOCOL §2.3): compressed timeline sets
    # closed_at = t0 + (index mod 20) days; aged spreads 0..60 days BEFORE t0.
    # Fixed per run, recorded in the manifest, reused by --replay so the
    # deterministic half is byte-identical across machines.
    "t0": "2026-08-28T00:00:00Z",
    # 'now' for the age rule. None -> real wall clock at run time.
    # The runner pins now_override=t0 for S1/S2 so age-stale is a pure
    # function of the run's own timeline (deterministic replay).
    "now_override": None,
}

INT_KEYS = {"K_INDEPENDENT", "MAX_PACKET", "STALE_AFTER_DAYS",
            "CLUSTER_EVERY_N_CHATS"}
FLOAT_KEYS = {"MATCH_THRESHOLD", "CLUSTER_THRESHOLD"}


def load_config(cli_overrides=None):
    """Return the merged config object. cli_overrides: list of "k=v" strings."""
    cfg = dict(DEFAULTS)
    for kv in (cli_overrides or []):
        if "=" not in kv:
            raise SystemExit(f"bad --config value: {kv!r} (want k=v)")
        k, v = kv.split("=", 1)
        if k not in cfg:
            raise SystemExit(f"unknown config key: {k!r}")
        if k in INT_KEYS:
            cfg[k] = int(v)
        elif k in FLOAT_KEYS:
            cfg[k] = float(v)
        elif k in ("now_override", "t0"):
            cfg[k] = v if v else None
        else:
            raise SystemExit(f"cannot set config key {k!r} from CLI")
    return cfg


def config_fingerprint(cfg):
    """Deterministic sha256 over the config object (used in the manifest)."""
    return sha256(json.dumps(cfg, sort_keys=True))


def now_iso(cfg=None):
    """'now' per the config clock (now_override) or the real wall clock."""
    if cfg and cfg.get("now_override"):
        return cfg["now_override"]
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def datetime_now_day():
    """Today UTC at 00:00:00 — the default T0 for synthesized closed_at."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")


def parse_iso(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso_add(s, **kw):
    """s ISO + timedelta kw -> ISO string (Z)."""
    dt = parse_iso(s)
    if dt is None:
        return s
    return (dt + timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Hashing / IO
# --------------------------------------------------------------------------


def sha256(text):
    if isinstance(text, str):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path):
    """Rows in file order. Missing file -> []."""
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows, mode="w"):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, mode, encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")


def upsert_by_key(rows, key="card_id"):
    """Stable upsert: later rows with the same key replace earlier ones,
    preserving the first-seen position."""
    out, seen = [], set()
    for r in rows:
        k = r[key]
        if k in seen:
            for i, o in enumerate(out):
                if o[key] == k:
                    out[i] = r
                    break
        else:
            seen.add(k)
            out.append(r)
    return out


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


# --------------------------------------------------------------------------
# Card identity / text / scope
# --------------------------------------------------------------------------


def card_id_of(dialogue_id):
    return "c-" + sha256(dialogue_id)[:12]


def scope_of(tenant_id, vertical):
    return f"{tenant_id}/{vertical}"


def card_text(card):
    """Card-text = problem_shape + constraint + unlock (SPEC §5/§7)."""
    parts = [card.get("problem_shape") or "", card.get("constraint") or "",
             card.get("unlock") or ""]
    return " ".join(parts)


def fresh_card(dialogue, at_iso):
    """Build a freshly extracted card (SPEC §4). `at_iso` is the deterministic
    run timestamp; created_at = closed_at + 1min when closed_at exists, else
    `at_iso` (keeps created_at deterministic and ordered)."""
    receipt = {
        "source_dialogue_id": dialogue["dialogue_id"],
        "tenant_id": dialogue["tenant_id"],
        "vertical": dialogue["vertical"],
        "agent_id": dialogue.get("agent_id") or "unknown",
        "closed_at": dialogue.get("closed_at"),
        "last_closed_at": dialogue.get("closed_at"),
        "scope": scope_of(dialogue["tenant_id"], dialogue["vertical"]),
    }
    cid = card_id_of(dialogue["dialogue_id"])
    created_at = iso_add(dialogue["closed_at"], minutes=1) if dialogue.get(
        "closed_at") else at_iso
    return {
        "card_id": cid,
        "status": "private",
        "role": "canonical",
        "cluster_id": cid,
        "votes": 1,
        "members": [],
        "problem_shape": "",
        "constraint": "none",
        "unlock": "none",
        "what_worked": [],
        "contains_pii": False,
        "receipt": receipt,
        "served_to": [],
        "created_at": created_at,
        "updated_at": created_at,
    }


# --------------------------------------------------------------------------
# Tokenization / TF-IDF / cosine (SPEC §6.3/§6.4, EVAL-PLAN A1/A4)
# Recipe: unigram, sublinear TF (1 + ln tf), smooth idf ln((1+N)/(1+df))+1,
# L2-normalised rows — i.e. scikit-learn TfidfVectorizer semantics with
# sublinear_tf=True and no stoplist. Deterministic (vocab sorted).
# --------------------------------------------------------------------------


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return TOKEN_RE.findall((text or "").lower())


def content_words(text, min_len=5):
    """Lowercased words >= min_len chars (for grounding / smoke checks)."""
    return {w for w in TOKEN_RE.findall((text or "").lower()) if len(w) >= min_len}


def build_tfidf(docs):
    """docs: list of str. Returns (vectors, vocab)."""
    tokenized = [tokenize(d) for d in docs]
    vocab = sorted({t for doc in tokenized for t in doc})
    n = len(docs)
    df = {t: 0 for t in vocab}
    for doc in tokenized:
        for t in set(doc):
            df[t] += 1
    idf = {t: math.log((1.0 + n) / (1.0 + df[t])) + 1.0 for t in vocab}
    vectors = []
    for doc in tokenized:
        tf = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        v = {}
        norm = 0.0
        for t, c in tf.items():
            w = (1.0 + math.log(c)) * idf[t]
            v[t] = w
            norm += w * w
        if norm > 0.0:
            inv = 1.0 / math.sqrt(norm)
            v = {t: w * inv for t, w in v.items()}
        vectors.append(v)
    return vectors, vocab


def cosine(v1, v2):
    if not v1 or not v2:
        return 0.0
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(w * v2.get(t, 0.0) for t, w in v1.items())


def score_query_vs_docs(query, docs):
    """Cosine of `query` against each doc in `docs`, fitted on
    {query} ∪ docs (SPEC §6.4: same recipe, sublinear TF, no stoplist).
    Returns a list of floats aligned to `docs`. Deterministic."""
    corpus = [query] + list(docs)
    vecs, _ = build_tfidf(corpus)
    qv = vecs[0]
    return [cosine(qv, v) for v in vecs[1:]]


def customer_text(dialogue):
    """Concatenation of all customer turns — the live query (SPEC §7)."""
    parts = [t["text"] for t in dialogue["turns"]
             if t.get("role") == "customer" and t.get("text")]
    return " ".join(parts)


# --------------------------------------------------------------------------
# PII scrub (SPEC §4). Order matters: emails, phones, digit runs, tokens.
# --------------------------------------------------------------------------

PII_PATTERNS = [
    (re.compile(r"\S+@\S+"), "email"),
    (re.compile(r"\+?\d[\d\-\s]{7,}\d"), "phone"),
    (re.compile(r"\d{10,}"), "order id"),
    (re.compile(r"\bcvv\b", re.I), "account"),
    (re.compile(r"\biban\b", re.I), "account"),
    (re.compile(r"\bssn\b", re.I), "account"),
]
# The bare word "card" is deliberately NOT a pattern (SPEC §4: "Do not match
# the bare word card. Support chats say 'gift card'.")


def scrub_text(text):
    """Replace PII hits with generic tokens. Returns (scrubbed, replaced)."""
    replaced = False
    for rx, tok in PII_PATTERNS:
        new = rx.sub(tok, text)
        if new != text:
            replaced = True
            text = new
    return text, replaced


def scrub_card_fields(card):
    """Scrub every model-generated string field; set contains_pii if any hit.
    Receipt / ids / timestamps are machine-set and never scrubbed."""
    changed = False
    for f in ("problem_shape", "constraint", "unlock"):
        if card.get(f):
            s, hit = scrub_text(card[f])
            if hit:
                changed = True
            card[f] = s
    ww = []
    for item in card.get("what_worked") or []:
        s, hit = scrub_text(item)
        if hit:
            changed = True
        ww.append(s)
    card["what_worked"] = ww
    if changed:
        card["contains_pii"] = True
    return card


def card_is_rejected(card):
    """Post-scrub reject rule (SPEC §4): empty problem_shape, or both
    constraint/unlock none AND empty what_worked."""
    if not (card.get("problem_shape") or "").strip():
        return True
    c = (card.get("constraint") or "").strip().lower()
    u = (card.get("unlock") or "").strip().lower()
    if c == "none" and u == "none" and not (card.get("what_worked") or []):
        return True
    return False


# --------------------------------------------------------------------------
# Card schema validation (SPEC §4) — used by extract and C-EX1
# --------------------------------------------------------------------------

CARD_KEYS = ["card_id", "status", "role", "cluster_id", "votes", "members",
             "problem_shape", "constraint", "unlock", "what_worked",
             "contains_pii", "receipt", "served_to", "created_at", "updated_at"]
RECEIPT_KEYS = ["source_dialogue_id", "tenant_id", "vertical", "agent_id",
                "closed_at", "last_closed_at", "scope"]


def validate_card(card, fresh=False):
    """Return list of schema violations. fresh=True asserts the §4
    fresh-extract state (status=private, role=canonical, votes=1, ...)."""
    errs = []
    if not isinstance(card, dict):
        return ["card is not an object"]
    for k in CARD_KEYS:
        if k not in card:
            errs.append(f"missing field {k}")
    if card.get("status") not in ("private", "shared", "merged", "stale",
                                  "rejected"):
        errs.append(f"bad status {card.get('status')!r}")
    if card.get("role") not in ("canonical", "member"):
        errs.append(f"bad role {card.get('role')!r}")
    if not isinstance(card.get("members"), list):
        errs.append("members not a list")
    if not isinstance(card.get("served_to"), list):
        errs.append("served_to not a list")
    if not isinstance(card.get("what_worked"), list):
        errs.append("what_worked not a list")
    if not isinstance(card.get("votes"), int):
        errs.append("votes not an int")
    if not isinstance(card.get("contains_pii"), bool):
        errs.append("contains_pii not a bool")
    r = card.get("receipt")
    if not isinstance(r, dict):
        errs.append("receipt missing")
    else:
        for k in RECEIPT_KEYS:
            if k not in r:
                errs.append(f"receipt missing {k}")
        if r.get("scope") != scope_of(r.get("tenant_id"), r.get("vertical")):
            errs.append("receipt.scope != tenant_id/vertical")
    if fresh:
        if card.get("status") != "private":
            errs.append("fresh card status != private")
        if card.get("role") != "canonical":
            errs.append("fresh card role != canonical")
        if card.get("votes") != 1:
            errs.append("fresh card votes != 1")
        if card.get("members") != []:
            errs.append("fresh card members != []")
        if card.get("cluster_id") != card.get("card_id"):
            errs.append("fresh card cluster_id != card_id")
        if card.get("receipt", {}).get("last_closed_at") != card.get(
                "receipt", {}).get("closed_at"):
            errs.append("fresh receipt.last_closed_at != receipt.closed_at")
    return errs


# --------------------------------------------------------------------------
# Dialogue schema checks (SPEC §3)
# --------------------------------------------------------------------------


def dialogue_ok(d):
    """Return list of violations, or [] if the record is a valid dialogue."""
    errs = []
    if not isinstance(d, dict):
        return ["not an object"]
    for k in ("dialogue_id", "tenant_id", "vertical", "agent_id", "channel",
              "closed_at", "turns"):
        if k not in d:
            errs.append(f"missing {k}")
    turns = d.get("turns") or []
    if not isinstance(turns, list):
        errs.append("turns not a list")
        return errs
    for t in turns:
        if t.get("role") not in ("customer", "agent", "tool"):
            errs.append(f"bad turn role {t.get('role')!r}")
        if "text" not in t:
            errs.append("turn missing text")
    if not any(t.get("role") == "customer" for t in turns):
        errs.append("no customer turn")
    return errs


def render_transcript(dialogue):
    """SPEC §6.2 / PROMPTS.md §2 rendering: customer:/agent:/tool {name}:"""
    lines = []
    for t in dialogue["turns"]:
        if t["role"] == "tool":
            name = t.get("name") or "tool"
            lines.append(f"tool {name}: {t['text']}")
        else:
            lines.append(f"{t['role']}: {t['text']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Prompts (loaded from PROMPTS.md so scripts can never drift from the file;
# the file's sha256 goes into the manifest — C-EV7)
# --------------------------------------------------------------------------


def load_prompts(path=PROMPTS_PATH):
    """Parse PROMPTS.md: headers '## N. Title' followed by fenced blocks.
    Returns {extract_system, extract_user, extract_example, serve_template,
    serve_card_block, feedback_system}."""
    text = open(path, "r", encoding="utf-8").read()
    header = None
    fence = None
    buf = []
    fences = {}   # header -> list of fenced block strings
    for line in text.splitlines():
        m = re.match(r"^## \d+\.\s+(.+)$", line)
        if m:
            header = m.group(1).strip()
            fences.setdefault(header, [])
            fence = None
            buf = []
            continue
        if header is None:
            continue
        if line.strip().startswith("```"):
            if fence is None:
                fence = line.strip()
            else:
                fences[header].append("\n".join(buf).strip())
                buf = []
                fence = None
            continue
        if fence is not None:
            buf.append(line)

    def first(prefix):
        for h, blocks in fences.items():
            if h.startswith(prefix) and blocks:
                return blocks[0]
        return None

    serve_blocks = None
    for h, blocks in fences.items():
        if h.startswith("Serve — packet template"):
            serve_blocks = blocks
    out = {
        "extract_system": first("Extract — system"),
        "extract_user": first("Extract — user"),
        "extract_example": first("Extract — expected shape"),
        "serve_template": serve_blocks[0] if serve_blocks else None,
        "serve_card_block": serve_blocks[1] if serve_blocks and len(
            serve_blocks) > 1 else None,
        "feedback_system": first("Feedback label — system"),
    }
    missing = [k for k, v in out.items() if not v]
    if missing:
        raise SystemExit(f"PROMPTS.md parse incomplete, missing: {missing}")
    return out


# --------------------------------------------------------------------------
# LLM (the single swappable call_llm — SPEC §2)
# --------------------------------------------------------------------------


class LlmFatal(Exception):
    """401/429 — provider/key problem. Founder rule: stop and tell oversight."""


class LlmError(Exception):
    pass


def resolve_llm_env():
    """Base URL and key come ONLY from the portable contract
    (DELIVERABLE-PACKAGE.md §6): H1_BASE_URL and H1_API_KEY. There is
    deliberately no fallback to a secrets file or a hardcoded endpoint —
    a stranger's clone must behave identically to the lab's machine, and a
    missing key is an error with a clear message, never a silent default."""
    base_url = os.environ.get("H1_BASE_URL")
    api_key = os.environ.get("H1_API_KEY")
    return base_url, api_key


def call_llm(system, user, model, temperature=0, max_tokens=2000, timeout=300,
             base_url=None, api_key=None, max_retries=2):
    """One chat completion. Returns (content, usage, ms, finish_reason).
    `model` is REQUIRED — there is no default model anywhere in bin/
    (DELIVERABLE-PACKAGE.md §6). base_url/api_key may come from args
    (--base-url / --api-key) or env (H1_BASE_URL / H1_API_KEY).
    Raises LlmFatal on 401/429 (never retried, never provider-swapped),
    LlmError on other failures after max_retries."""
    if not model:
        raise LlmError("no model: pass --model (there is no default model "
                       "in bin/)")
    base_url = base_url or resolve_llm_env()[0]
    api_key = api_key or resolve_llm_env()[1]
    if not api_key:
        raise LlmError("no API key: set H1_API_KEY (or pass --api-key)")
    if not base_url:
        raise LlmError("no base URL: set H1_BASE_URL (or pass --base-url)")
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_err = None
    for attempt in range(max_retries + 1):
        t0 = time.monotonic()
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            ms = int((time.monotonic() - t0) * 1000)
            choice = data["choices"][0]
            content = (choice.get("message") or {}).get("content") or ""
            usage = data.get("usage") or {}
            return content, usage, ms, choice.get("finish_reason")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            if e.code in (401, 429):
                raise LlmFatal(
                    f"HTTP {e.code} from {url} — provider/key problem. "
                    f"Founder rule: stop and report to oversight, do not swap "
                    f"providers. body: {body}") from e
            last_err = f"HTTP {e.code}: {body}"
            if e.code >= 500 and attempt < max_retries:
                time.sleep(2 * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < max_retries:
                time.sleep(2 * (attempt + 1))
                continue
            break
    raise LlmError(f"LLM call failed after {max_retries + 1} attempts: "
                   f"{last_err}")


def parse_model_json(response_text):
    """Strip markdown fences, then json.loads. Returns (obj, error)."""
    text = (response_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, str(e)


# --------------------------------------------------------------------------
# Independence / votes (SPEC §5.1) — shared by cluster, promote and eval
# --------------------------------------------------------------------------


def compute_votes(canonical, members, dialogue_agent_ids=None):
    """SPEC §5.1. Returns (votes, independence_mode, n_dropped_served).
    dialogue_agent_ids: optional map dialogue_id -> agent_id to use in place
    of card receipts (cluster.py always uses receipts; eval may re-derive).
    """
    cand = {canonical["receipt"]["source_dialogue_id"]}
    for m in members:
        cand.add(m["receipt"]["source_dialogue_id"])
    served_ids = {s["dialogue_id"] for s in canonical.get("served_to") or []}
    cand = cand - served_ids
    canon_agent = canonical["receipt"].get("agent_id") or "unknown"
    agents = {canonical["receipt"]["source_dialogue_id"]: canon_agent}
    for m in members:
        agents[m["receipt"]["source_dialogue_id"]] = m["receipt"].get(
            "agent_id") or "unknown"
    if dialogue_agent_ids:
        for k in list(agents):
            if k in dialogue_agent_ids:
                agents[k] = dialogue_agent_ids[k]
    remaining = list(cand)
    all_unknown = bool(remaining) and all(
        (agents.get(d) or "unknown") == "unknown" for d in remaining)
    if not remaining:
        return 0, "dialogue-only", 0
    if all_unknown:
        return len(remaining), "dialogue-only", 0
    kept = [d for d in remaining
            if (agents.get(d) or "unknown") != canon_agent
            or d == canonical["receipt"]["source_dialogue_id"]]
    return len(kept), "agent+dialogue", 0


def last_closed_at(canonical, members):
    """SPEC §5.3: max closed_at over canonical + members that have one."""
    values = []
    for c in [canonical] + list(members):
        if c["receipt"].get("closed_at"):
            values.append(parse_iso(c["receipt"]["closed_at"]))
    if not values:
        return None
    return max(values).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_stale(canonical, members, cfg, now=None):
    """Age rule (SPEC §5): now - last_closed_at > STALE_AFTER_DAYS.
    `now` may be a datetime or an ISO string (scripts pass strings)."""
    last = last_closed_at(canonical, members)
    if not last:
        return False
    if now is None:
        now = parse_iso(now_iso(cfg))
    elif isinstance(now, str):
        now = parse_iso(now)
    last_dt = parse_iso(last)
    if now is None or last_dt is None:
        return False
    return (now - last_dt) > timedelta(days=cfg["STALE_AFTER_DAYS"])


def apply_status(canonical, members, cfg, now=None):
    """The vote -> status + age-stale tail (SPEC §5). Used by cluster.py and
    promote.py (C-PR1: promote changes only status). Returns new status.
    Stale is absorbing: a card that is already stale never returns to shared
    within a run (C-PR4)."""
    if canonical.get("status") == "stale":
        return "stale"
    if is_stale(canonical, members, cfg, now):
        return "stale"
    votes, mode, _ = compute_votes(canonical, members)
    if votes >= cfg["K_INDEPENDENT"]:
        return "shared"
    return "private"


def word_count(s):
    return len(TOKEN_RE.findall((s or "").lower()))


def print_json(obj):
    print(json.dumps(obj, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit("h1lib is a library, not a script")
