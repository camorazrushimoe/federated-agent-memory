"""H1 experience-card pipeline — central config object.

SPEC.md §5: "Defaults (change only in one config object)". All thresholds and
timing constants live here and are recorded in the run manifest.
"""

from __future__ import annotations

import datetime as _dt


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# Fixed reference epoch for the `compressed` timeline (RUN-PROTOCOL §2.3).
# closed_at = T0 + (index mod 20) days, so every dialogue is < STALE_AFTER_DAYS
# old w.r.t. any plausible run date and the age-stale rule is off by construction.
T0_ISO = "2026-08-08T00:00:00Z"

DEFAULTS = {
    # SPEC §5 promotion/matching constants
    "K_INDEPENDENT": 2,
    "MAX_PACKET": 3,
    "STALE_AFTER_DAYS": 30,
    "MATCH_THRESHOLD": 0.18,
    "CLUSTER_THRESHOLD": 0.35,
    "CLUSTER_EVERY_N_CHATS": 100,
    # RUN-PROTOCOL §2.2 agent synthesis
    "AGENT_POOL_SIZE": 4,
    # RUN-PROTOCOL §2.3 timelines
    "TIMELINE": "compressed",  # compressed | aged
    "T0": T0_ISO,
    # LLM call parameters (DELIVERABLE-PACKAGE §6: no model name, endpoint or
    # key literal in code — the model id and base URL come from CLI/env only)
    "TEMPERATURE": 0,
    "MAX_TOKENS": 2000,
    # 55-guideline ontology used for labels (from data/README.md)
    "LABEL_SOURCE": "unlock_guideline",
}

# Keys present in the raw pack / spec records that are ground truth and MUST be
# stripped before extract.py ever sees them (RUN-PROTOCOL §2.1, EVAL-PLAN §1).
GROUND_TRUTH_KEYS = ("unlock", "unlock_guideline", "split", "n_turns")

# Fields that a raw record may carry in SPEC §3 form and we pass through.
SPEC_FIELDS = (
    "dialogue_id", "tenant_id", "vertical", "agent_id", "channel",
    "closed_at", "turns",
)


def resolve_config(overrides: dict | None = None) -> dict:
    """Merge CLI/runner overrides on top of DEFAULTS; unknown keys are an error."""
    cfg = dict(DEFAULTS)
    for k, v in (overrides or {}).items():
        if k not in DEFAULTS:
            raise ValueError(f"unknown config key: {k}")
        cfg[k] = v
    return cfg


def llm_params(model: str, base_url: str) -> dict:
    """LLM identity from CLI/env (DELIVERABLE-PACKAGE §6) — never from code."""
    if not model or not base_url:
        raise ValueError("model and base_url must be provided via CLI/env "
                         "(H1_MODEL / --model, H1_BASE_URL / --base-url)")
    return {"MODEL": model, "BASE_URL": base_url}


def manifest_config(cfg: dict) -> dict:
    """The slice of config recorded in manifest.json (RUN-PROTOCOL §3.1)."""
    return {
        "K_INDEPENDENT": cfg["K_INDEPENDENT"],
        "MAX_PACKET": cfg["MAX_PACKET"],
        "STALE_AFTER_DAYS": cfg["STALE_AFTER_DAYS"],
        "MATCH_THRESHOLD": cfg["MATCH_THRESHOLD"],
        "CLUSTER_THRESHOLD": cfg["CLUSTER_THRESHOLD"],
        "CLUSTER_EVERY_N_CHATS": cfg["CLUSTER_EVERY_N_CHATS"],
    }


def parse_iso(iso: str) -> _dt.datetime:
    """Parse an ISO timestamp to a tz-aware datetime (UTC)."""
    dt = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def iso(dt: _dt.datetime) -> str:
    return dt.astimezone(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utcnow_iso() -> str:
    return _utcnow()
