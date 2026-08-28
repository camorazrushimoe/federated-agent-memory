#!/usr/bin/env python3
"""llm.py — THE single LLM entry point (SPEC §2, DELIVERABLE-PACKAGE §6).

    call_llm(system, user, *, model, base_url, api_key,
             raw_path=None, replay_dir=None, temperature=0.0) -> str

- Live mode: POST {base_url}/chat/completions with temperature=0 and
  thinking={"type": "disabled"} (lead decision 2026-08-28: this provider's
  v4 models default to thinking-enabled; disabled for deterministic JSON
  extraction). Returns choices[0].message.content.
- raw_path: write {request, response, model, usage, ms} JSON (live mode).
- Replay mode (replay_dir): read replay_dir/<basename(raw_path)> (the raw
  record written in live mode), return the stored response, perform ZERO
  network calls, and record usage from the stored record.
- 401/429 -> LLMError (aborts the run; NO retry loop, NO provider swap).
- Unparseable model JSON is handled by the CALLER (extract.py) as a recorded
  rate (C-EX11), never as a silent retry here.

D8 rule (DELIVERABLE-PACKAGE §6): the model id, base URL and API key come
from the caller — CLI flags (--model, --base-url/--api-key) or the
environment (H1_BASE_URL, H1_API_KEY). There are NO model-name, endpoint or
key literals in this file, not even as a default that silently works.
resolve_llm_params() is the single place that turns flags/env into values
and raises a clear usage error when one is missing.

Stdlib only (urllib). No imports from outside standalone/h1-experience-cards/.
"""

import json
import os
import time
import urllib.error
import urllib.request


class LLMError(Exception):
    """Fatal LLM failure (auth/rate/network/shape). Aborts the run."""


# Provider quirk, not a model literal: the request body must disable the
# provider's default thinking mode so JSON extraction is deterministic.
LLM_EXTRA = {"thinking": {"type": "disabled"}}


class _Usage:
    """Cumulative usage accounting for the current process.

    Replay reads count as calls (network=False) so a replay run reports the
    same extract.calls as the live run it reproduces.
    """

    def __init__(self):
        self.calls = 0
        self.network_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.ms_list = []

    def record(self, model, usage, ms, network):
        self.calls += 1
        if network:
            self.network_calls += 1
        self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
        self.ms_list.append(int(ms or 0))

    def snapshot(self):
        return {
            "calls": self.calls,
            "network_calls": self.network_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "ms_list": list(self.ms_list),
        }


USAGE = _Usage()


def resolve_llm_params(model, base_url, api_key):
    """Turn flags/env values into (model, base_url, api_key); fail loudly.

    - --model has NO default (D8 rule): a model swap is a flag, never an edit.
    - base_url: --base-url, else env H1_BASE_URL.
    - api_key:  --api-key,  else env H1_API_KEY (never printed anywhere).
    Missing any of the three is a usage error, not a silent default.
    """
    b = base_url or os.environ.get("H1_BASE_URL")
    k = api_key or os.environ.get("H1_API_KEY")
    missing = []
    if not model:
        missing.append("--model")
    if not b:
        missing.append("--base-url or H1_BASE_URL")
    if not k:
        missing.append("--api-key or H1_API_KEY")
    if missing:
        raise LLMError(
            "missing LLM configuration: " + ", ".join(missing) +
            " (model/endpoint/key are never hard-coded; see DELIVERABLE-PACKAGE §6)"
        )
    return model, b.rstrip("/"), k


def _read_replay_record(replay_dir, raw_path):
    fname = os.path.basename(raw_path) if raw_path else None
    if not fname:
        raise LLMError("replay mode requires raw_path (<dialogue_id>.json)")
    path = os.path.join(replay_dir, fname)
    if not os.path.exists(path):
        raise LLMError(f"replay record missing: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def call_llm(system, user, *, model, base_url=None, api_key=None,
             raw_path=None, replay_dir=None, temperature=0.0):
    """Return the assistant text for (system, user).

    replay_dir is not None -> replay mode: read the raw record stored under
    replay_dir/<basename(raw_path)>, return its stored response, perform ZERO
    network calls, record usage from the stored record.
    """
    if replay_dir is not None:
        rec = _read_replay_record(replay_dir, raw_path)
        usage = rec.get("usage") or {}
        USAGE.record(rec.get("model") or model, usage,
                     int(rec.get("ms", 0) or 0), network=False)
        return rec["response"]

    model, base_url, api_key = resolve_llm_params(model, base_url, api_key)
    assert base_url and api_key  # resolve_llm_params raises otherwise

    payload = {
        "model": model,
        "temperature": temperature,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    url = base_url + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code in (401, 429):
            raise LLMError(
                f"LLM provider HTTP {exc.code} on {url}: {detail} — "
                f"aborting (no retry, no provider swap)"
            ) from None
        raise LLMError(f"LLM provider HTTP {exc.code} on {url}: {detail}") from None
    except urllib.error.URLError as exc:
        raise LLMError(f"LLM network error on {url}: {exc}") from None
    except Exception as exc:  # body JSON parse failure etc.
        raise LLMError(f"LLM response error: {exc}") from None

    ms = int((time.time() - t0) * 1000)
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(
            f"unexpected LLM response shape: {json.dumps(body)[:300]}"
        ) from None
    if not isinstance(content, str):
        raise LLMError(f"unexpected LLM content type: {type(content).__name__}")

    usage = body.get("usage") or {}
    USAGE.record(model, usage, ms, network=True)

    if raw_path:
        os.makedirs(os.path.dirname(raw_path) or ".", exist_ok=True)
        # NOTE: the record stores {request, response, model, usage, ms} —
        # never headers, never the API key (RUN-PROTOCOL §4 / brief §4).
        record = {
            "request": {"system": system, "user": user},
            "response": content,
            "model": model,
            "usage": usage,
            "ms": ms,
        }
        with open(raw_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return content


def copy_replay_record(replay_dir, raw_path):
    """Copy a stored raw record into the new run's raw dir (replay runs).

    Replay mode reads from the old run and writes the identical record into
    the new run's raw dir so raw/extract/ stays complete and C-EX10 holds —
    without any network call.
    """
    rec = _read_replay_record(replay_dir, raw_path)
    os.makedirs(os.path.dirname(raw_path) or ".", exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    return rec["response"]


def peak_window(now_dt_utc):
    """True if now (tz-aware UTC datetime) falls in the provider's peak hours.

    Peak hours: Mon-Fri 01:00-04:00 and 06:00-10:00 UTC (from the dated price
    sheet the runner records in cost.json). Off-peak otherwise. If the window
    cannot be determined, the caller falls back to the PEAK rate (conservative)
    and states it (brief §2).
    """
    if now_dt_utc.weekday() >= 5:  # Sat/Sun
        return False
    hour = now_dt_utc.hour
    return (1 <= hour < 4) or (6 <= hour < 10)
