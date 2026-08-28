"""Pinned run clock — makes every timestamp in a run deterministic.

L0 (EVAL-PLAN §2) requires the deterministic half of the pipeline to be
byte-identical across re-runs, including `--replay`. Real `datetime.now()`
calls would make `created_at`, `served_to.at` and the staleness `now` drift.

Design: the runner pins a run clock (the run's real start time, or the
manifest's recorded clock on replay). Every timestamp the pipeline writes is
derived from that clock plus a deterministic offset, so a replay reproduces
the exact same bytes.

The age-stale rule uses the pinned clock as "now"; with the `compressed`
timeline nothing can be stale by construction, and the staleness contract
tests pass an explicit `--now` instead.
"""

from __future__ import annotations

import datetime as _dt

from common import parse_iso


def iso(dt: _dt.datetime) -> str:
    """ISO-8601 UTC with Z, seconds precision (same format as common.now_iso)."""
    return dt.astimezone(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class RunClock:
    def __init__(self, start_iso: str):
        self.start: _dt.datetime = parse_iso(start_iso)

    def at(self, offset_seconds: int = 0) -> str:
        """ISO timestamp = clock start + offset seconds (deterministic)."""
        return iso(self.start + _dt.timedelta(seconds=offset_seconds))

    def now(self) -> str:
        return iso(self.start)

    def age_days(self, closed_at_iso: str | None) -> float | None:
        """Days between the pinned 'now' and a closed_at; None if absent."""
        if not closed_at_iso:
            return None
        return (self.start - parse_iso(closed_at_iso)).total_seconds() / 86400.0

    def to_manifest(self) -> dict:
        return {"start": iso(self.start), "tz": "UTC"}


def make_clock(start_iso: str | None = None) -> RunClock:
    if start_iso is None:
        start_iso = iso(_dt.datetime.now(_dt.timezone.utc))
    return RunClock(start_iso)
