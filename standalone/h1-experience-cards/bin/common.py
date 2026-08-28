#!/usr/bin/env python3
"""Shared helpers for the H1 experience-card pipeline.

- parse_prompts(path)          — load the frozen PROMPTS.md strings by section
- tokenize / TFIDF             — the ONE TF-IDF recipe (SPEC §6.3/§6.4)
- card_text / card_id_for      — cluster key / deterministic card id
- scrub_pii                    — SPEC §4 regexes, exactly
- now handling                 — pinned --now support (brief §6)

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

import hashlib
import math
import re
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# PROMPTS.md parsing — scripts MUST load the frozen strings from here.
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^## (\d+)\. (.+)$")
_FENCE_RE = re.compile(r"```\n?(.*?)\n?```", re.DOTALL)


def parse_prompts(path):
    """Load PROMPTS.md sections into a dict keyed by the section title.

    Each value is the raw text of the FIRST fenced ``` block in that section,
    byte-identical to the file (fence markers excluded). Section 4
    ("Serve — packet template") has two fenced blocks; the second one is the
    per-card block and is exposed under the key "<title>#card".
    """
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    sections = {}
    current = None
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current = m.group(2).strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    out = {}
    for title, lines in sections.items():
        body = "\n".join(lines)
        fences = _FENCE_RE.findall(body)
        if fences:
            out[title] = fences[0]
        if len(fences) >= 2:
            out[title + "#card"] = fences[1]
    return out


def prompts_for(path):
    """Convenience wrapper with the keys the scripts actually consume.

    Section titles may carry suffixes ("Serve — packet template (no LLM
    required)"); lookups match by prefix so the frozen text is what counts.
    """
    p = parse_prompts(path)

    def pick(prefix, suffix=None):
        for key, val in p.items():
            if key == prefix or key.startswith(prefix + " "):
                if suffix is None:
                    return val
                if key.endswith(suffix):
                    return val
        return ""

    return {
        "extract_system": pick("Extract — system"),
        "extract_user": pick("Extract — user"),
        "serve_packet": pick("Serve — packet template"),
        "serve_card_block": pick("Serve — packet template", "#card"),
        "feedback_system": pick("Feedback label — system"),
    }


# ---------------------------------------------------------------------------
# Tokenization + TF-IDF (SPEC §6.3/§6.4 — the ONE recipe, used everywhere)
# ---------------------------------------------------------------------------

def tokenize(text):
    """Lowercase alphanumeric tokens (spec'd recipe)."""
    return re.findall(r"[a-z0-9]+", text.lower())


class TFIDF:
    """Sublinear-TF IDF with no stoplist; cosine with a zero vector is 0.0.

    - tf: 1 + log(raw_tf)
    - idf: log((1 + N) / (1 + df)) + 1
    - cosine(query, doc); if either vector is zero → 0.0
    """

    def __init__(self):
        self.idf = {}
        self.doc_vecs = []

    def fit(self, texts):
        N = len(texts)
        df = {}
        tokenized = []
        for t in texts:
            toks = tokenize(t)
            tokenized.append(toks)
            for tok in set(toks):
                df[tok] = df.get(tok, 0) + 1
        self.idf = {tok: math.log((1 + N) / (1 + cnt)) + 1
                    for tok, cnt in df.items()}
        self.doc_vecs = []
        for toks in tokenized:
            tf = {}
            for tok in toks:
                tf[tok] = tf.get(tok, 0) + 1
            self.doc_vecs.append(
                {tok: 1 + math.log(cnt) for tok, cnt in tf.items()})
        return self

    def _vec(self, text):
        tf = {}
        for tok in tokenize(text):
            tf[tok] = tf.get(tok, 0) + 1
        return {tok: (1 + math.log(cnt)) * self.idf.get(tok, 0.0)
                for tok, cnt in tf.items()}

    @staticmethod
    def _norm(vec):
        return math.sqrt(sum(v * v for v in vec.values()))

    def score(self, query_text, doc_text):
        vq = self._vec(query_text)
        vd = self._vec(doc_text)
        nq = self._norm(vq)
        nd = self._norm(vd)
        if nq == 0.0 or nd == 0.0:
            return 0.0
        dot = 0.0
        for tok, w in vq.items():
            if tok in vd:
                dot += w * vd[tok]
        return dot / (nq * nd)


# ---------------------------------------------------------------------------
# Card helpers (SPEC §5, §6.2)
# ---------------------------------------------------------------------------

def card_text(card):
    """Cluster/match key: problem_shape + ' ' + constraint + ' ' + unlock."""
    return " ".join([
        str(card.get("problem_shape", "")),
        str(card.get("constraint", "")),
        str(card.get("unlock", "")),
    ])


def customer_turns_key(dialogue):
    """F5 alternative cluster key (EVAL-PLAN §7.2): the source dialogue's
    customer turns, lowercased and concatenated. Same text as match.live_query
    — hundreds of words of raw transcript instead of the ~36-word card
    paraphrase. Used ONLY when cluster.py runs with --cluster-key
    customer-turns; the serve path is untouched."""
    if not dialogue:
        return ""
    return " ".join(t.get("text", "")
                    for t in dialogue.get("turns", [])
                    if t.get("role") == "customer").lower()


def card_id_for(dialogue_id):
    """Deterministic card id: c- + first 12 hex of sha256(dialogue_id)."""
    return "c-" + hashlib.sha256(str(dialogue_id).encode("utf-8")).hexdigest()[:12]


def dialogue_agent_id(dialogue_id, pool_size):
    """RUN-PROTOCOL §2.2 — deterministic synthesized agent id."""
    digest = int(hashlib.sha256(str(dialogue_id).encode("utf-8")).hexdigest(), 16)
    return "agent-" + chr(ord("a") + digest % max(1, pool_size))


# ---------------------------------------------------------------------------
# PII scrub (SPEC §4 — regexes exactly as specified, in this order)
# ---------------------------------------------------------------------------

_SCRUB_RULES = [
    ("email", re.compile(r"\S+@\S+")),
    ("phone", re.compile(r"\+?\d[\d\-\s]{7,}\d")),
    ("order id", re.compile(r"\d{10,}")),
    ("account", re.compile(r"\bcvv\b|\biban\b|\bssn\b", re.IGNORECASE)),
]
# NOTE: the bare word "card" is deliberately NOT in the rules — support chats
# say "gift card" (C-EX7). Never add it.


def scrub_text(text):
    """Apply the SPEC §4 rules to one string. Returns (scrubbed, replaced)."""
    replaced = False
    for token, rx in _SCRUB_RULES:
        new = rx.sub(token, text)
        if new != text:
            replaced = True
            text = new
    return text, replaced


def scrub_pii(obj):
    """Recursively scrub every string in a card object.

    Applies to every string field and every what_worked item (brief §4).
    Returns (scrubbed_obj, replaced_any). The word "card" is never touched.
    """
    replaced_any = False

    def walk(x):
        nonlocal replaced_any
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, str):
            s, r = scrub_text(x)
            if r:
                replaced_any = True
            return s
        return x

    return walk(obj), replaced_any


def pii_matches(text):
    """True if any SPEC §4 regex matches (used for C-EX5-style checks)."""
    for _, rx in _SCRUB_RULES:
        if rx.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Time handling (brief §6: now is ALWAYS pinned; never datetime.now() inside
# cluster / match / serve / promote / eval).
# ---------------------------------------------------------------------------

def now_iso():
    """Real UTC now, ISO-8601 with Z. Only for the operator/runner entry
    points (tick.py, run_experiment.py, extract.py default) — NEVER inside the
    deterministic scripts."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    """Parse 'YYYY-MM-DDTHH:MM:SSZ' (or with offset) into a tz-aware datetime."""
    if value is None:
        return None
    v = str(value).strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    return datetime.fromisoformat(v)


def days_since(now_iso_value, past_iso_value):
    """Whole-day difference now - past (float days). None-safe."""
    now = parse_iso(now_iso_value)
    past = parse_iso(past_iso_value)
    if now is None or past is None:
        return None
    return (now - past).total_seconds() / 86400.0


def iso_add_days(iso_value, days):
    from datetime import timedelta
    dt = parse_iso(iso_value)
    return (dt + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_add_seconds(iso_value, seconds):
    """Pinned-time arithmetic: iso + N seconds, back to 'YYYY-MM-DDTHH:MM:SSZ'.

    Used by the runner's fixture track to make a scenario's first dialogue
    strictly oldest by created_at (SPEC §5 tie rule; SPEC §10.2 expects the
    oldest card to be the canonical). Deterministic given the pinned now.
    """
    from datetime import timedelta
    dt = parse_iso(iso_value)
    return (dt + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def scope_of(tenant_id, vertical):
    return f"{tenant_id}/{vertical}"
