"""The one swappable LLM function — call_llm(system, user) -> str (SPEC §2).

- stdlib urllib only (C-L4: no other network use anywhere in bin/)
- DELIVERABLE-PACKAGE §6: the model id and base URL are REQUIRED arguments that
  come from CLI flags / environment (--model, --base-url / H1_BASE_URL,
  H1_API_KEY). No model name, endpoint or key literal lives in bin/.
  A 401/429 here is news: raise a clear error and STOP — the factory does not
  swap providers on its own (LAB-BRIEF §3).
- temperature=0; max_tokens from the caller (reasoning models cut content if
  max_tokens is too small).
- Every call is recorded to raw/extract/<dialogue_id>.json
  {request, response, model, usage, ms} when a raw_dir is given — that file is
  what `--replay` consumes (L0, EVAL-PLAN §2).
- API key resolution order: H1_API_KEY (portable, DELIVERABLE-PACKAGE §6),
  then CUSTOM_API_KEY (factory box environment).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


class LLMError(RuntimeError):
    pass


def _load_key() -> str:
    for name in ("H1_API_KEY", "CUSTOM_API_KEY", "DEEPSEEK_API_KEY"):
        key = os.environ.get(name)
        if key:
            return key
    raise LLMError("no API key: set H1_API_KEY (or CUSTOM_API_KEY)")


def call_llm(system: str, user: str, *,
             model: str, base_url: str,
             temperature: float = 0.0,
             max_tokens: int = 2000,
             raw_dir: str | None = None,
             dialogue_id: str | None = None,
             replay: bool = False,
             record: dict | None = None) -> tuple[str, dict]:
    """Return (content, meta). meta holds {model, usage, ms, replayed}.

    `record` is an optional dict the caller supplies so that request/response
    can be persisted by the caller without a second copy of the payload.
    """
    if not model and not base_url and not replay:
        raise LLMError("call_llm requires model and base_url (CLI/env only, "
                       "DELIVERABLE-PACKAGE §6)")
    if replay:
        if not raw_dir or not dialogue_id:
            raise LLMError("replay mode requires raw_dir and dialogue_id")
        rp = Path(raw_dir) / f"{dialogue_id}.json"
        if not rp.exists():
            raise LLMError(f"replay: no recorded extract response at {rp}")
        rec = json.loads(rp.read_text())
        if record is not None:
            record.update(rec)
        return rec["response"], {"model": rec.get("model", model),
                                 "usage": rec.get("usage"),
                                 "ms": rec.get("ms"),
                                 "replayed": True}

    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    # bounded retry for transient network failures (timeout / 5xx). A
    # persistent 401/429 is NOT retried — that is news to report, not noise
    # (LAB-BRIEF §5: the factory does not swap providers).
    last_exc: Exception | None = None
    for attempt in (0, 1):
        req = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + _load_key(),
                     "Content-Type": "application/json"},
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            if e.code in (401, 429) or attempt == 1:
                raise LLMError(f"LLM HTTP {e.code}: {detail} "
                               f"(model={model}, base_url={base_url})") from e
            last_exc = e  # 5xx: one retry
        except (TimeoutError, ConnectionError, OSError) as e:
            if attempt == 1:
                raise LLMError(f"LLM transport failure after retry: {e} "
                               f"(model={model}, base_url={base_url})") from e
            last_exc = e
    else:
        raise LLMError(f"LLM call failed: {last_exc}") from last_exc
    ms = int((time.time() - t0) * 1000)
    try:
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage")
    except (KeyError, IndexError) as e:
        raise LLMError(f"unexpected LLM response shape: {json.dumps(body)[:300]}") from e
    meta = {"model": body.get("model", model), "usage": usage, "ms": ms, "replayed": False}
    if raw_dir and dialogue_id:
        rec = {"dialogue_id": dialogue_id,
               "request": {"system": system, "user": user},
               "response": content,
               "model": meta["model"],
               "usage": usage,
               "ms": ms}
        p = Path(raw_dir) / f"{dialogue_id}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        if record is not None:
            record.update(rec)
    return content, meta
