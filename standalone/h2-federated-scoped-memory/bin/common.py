"""H2 — shared helpers for bin/ scripts (SPEC §2 isolation).

- call_llm(system, user) — the ONLY network touch in the pipeline.
- transcript render (PROMPTS.md §1), PII scrub (SPEC §4), session_id/tag_key
  builders (SPEC §4), deterministic JSONL I/O.

No model/base-url/key literals here: model comes from --model (default in
config.DEFAULT_MODEL), base_url from H2_BASE_URL / --base-url, key from the
H2_API_KEY environment variable only. The H1 lane's key is never read.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Scripts are run as `python bin/<script>.py` from the experiment root, so
# bin/ lands on sys.path[0]. Bootstrap explicitly so imports work regardless
# of how the interpreter was invoked.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
import prompts  # noqa: E402

# ---------------------------------------------------------------------------
# LLM — the single call_llm wrapper
# ---------------------------------------------------------------------------


def resolve_endpoint(base_url: str | None) -> str:
    """Base URL from --base-url or H2_BASE_URL. Never a literal."""
    url = base_url or os.environ.get("H2_BASE_URL")
    if not url:
        raise RuntimeError(
            "no base_url: set H2_BASE_URL or pass --base-url "
            "(bin/ has no base_url literal)"
        )
    return url.rstrip("/")


def _post_once(system: str, user: str, model: str, base_url: str, api_key: str) -> dict:
    """One POST to {base_url}/chat/completions. Returns the raw JSON body."""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": config.TEMPERATURE,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_llm(system: str, user: str, *, model: str, base_url: str | None = None,
             api_key: str | None = None) -> dict:
    """call_llm(system, user) -> {"content", "raw", "usage", "model"}.

    The only place that touches the network. On an unparseable API response or
    a transient transport error it retries once with the exact same payload,
    then raises — the caller (S2) decides reject per PROMPTS.md §4.
    """
    key = api_key or os.environ.get("H2_API_KEY")
    if not key:
        raise RuntimeError("H2_API_KEY is not set (bin/ never reads the H1 key)")
    url = resolve_endpoint(base_url)
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            raw = _post_once(system, user, model, url, key)
            choices = raw.get("choices") or []
            if not choices or "message" not in choices[0]:
                raise RuntimeError("API response has no choices[0].message")
            content = choices[0]["message"].get("content")
            if content is None:
                raise RuntimeError("API response content is None")
            return {
                "content": content,
                "raw": raw,
                "usage": raw.get("usage"),
                "model": model,
            }
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                RuntimeError) as exc:  # noqa: PERF203
            last_err = exc
    raise RuntimeError(f"call_llm failed after one retry: {last_err!r}")


# ---------------------------------------------------------------------------
# Deterministic ids and tag_key (SPEC §4)
# ---------------------------------------------------------------------------


def session_id_of(dialogue_id: str) -> str:
    """session_id = "s-" + first 12 hex chars of sha256(source_dialogue_id)."""
    return "s-" + hashlib.sha256(dialogue_id.encode("utf-8")).hexdigest()[:12]


def make_tag_key(tags: dict) -> str:
    """tag_key = problem_shape|constraint|ending|channel|vertical, no edge spaces."""
    return "|".join(str(tags.get(f, "")).strip() for f in config.TAG_FIELDS)


# ---------------------------------------------------------------------------
# Transcript render (PROMPTS.md §1)
# ---------------------------------------------------------------------------


def render_transcript(turns: list) -> str:
    """One line per turn: customer:/agent:/tool {name}:. No blank lines."""
    lines = []
    for turn in turns:
        role = turn.get("role")
        text = turn.get("text") or ""
        if role == "customer":
            lines.append(f"customer: {text}")
        elif role == "agent":
            lines.append(f"agent: {text}")
        elif role == "tool":
            name = (turn.get("name") or "").strip()
            lines.append(f"tool {name}: {text}" if name else f"tool: {text}")
        else:  # other roles must have been dropped at S1
            raise ValueError(f"unexpected turn role: {role!r}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PII scrub (SPEC §4, C-PII)
# ---------------------------------------------------------------------------

# email, phone, >=10 consecutive digits, cvv/iban/ssn -> placeholder.
# Long digit runs are scrubbed BEFORE phone so an order number becomes
# [number], not [phone].
_PII_PATTERNS = [
    (re.compile(r"\S+@\S+"), "[email]"),
    (re.compile(r"\d{10,}"), "[number]"),
    (re.compile(r"(?:\+?\d[\d\s\-\.\(\)]{5,}\d)"), "[phone]"),
    (re.compile(r"\bcvv\b", re.IGNORECASE), "[card-code]"),
    (re.compile(r"\biban\b", re.IGNORECASE), "[card-code]"),
    (re.compile(r"\bssn\b", re.IGNORECASE), "[card-code]"),
]


def scrub_text(text: str) -> tuple[str, bool]:
    """Return (scrubbed_text, contains_pii). Placeholder per pattern type."""
    out = text
    hit = False
    for pattern, placeholder in _PII_PATTERNS:
        new, n = pattern.subn(placeholder, out)
        if n:
            hit = True
            out = new
    return out, hit


def scrub_turns(turns: list) -> tuple[list, bool]:
    """PII-scrub every turn's text in place; returns (turns, any_hit)."""
    hit = False
    for turn in turns:
        if "text" in turn:
            turn["text"], h = scrub_text(turn["text"])
            hit = hit or h
    return turns, hit


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue  # C-GD1: consumers MUST skip `#` header lines (gold)
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    """Deterministic rewrite (upsert semantics live in the callers)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: str | Path, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, obj) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_of(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def print_summary(obj: dict) -> None:
    """Every script prints exactly ONE JSON summary to stdout."""
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def fail(msg: str, code: int = 2) -> int:
    """Uniform failure line: one JSON object with ok:false on stderr? No —
    keep stdout clean; the summary is only printed on success."""
    sys.stderr.write(f"{Path(sys.argv[0]).name}: {msg}\n")
    return code
