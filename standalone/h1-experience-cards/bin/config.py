#!/usr/bin/env python3
"""One config object for the H1 experience-card pipeline (SPEC §5).

"change only in one config object" — every threshold, limit and knob that the
SPEC defines lives here. Scripts read values through Config and may override
any key with --set key=value (needed, e.g., for negative control C-NC4:
MATCH_THRESHOLD=0.99 / MATCH_THRESHOLD=0.0).

Stdlib only. No imports from outside standalone/h1-experience-cards/.
"""

DEFAULTS = {
    # SPEC §5 defaults
    "K_INDEPENDENT": 2,             # votes needed for a canonical to go shared
    "MAX_PACKET": 3,                # max cards in a served packet
    "STALE_AFTER_DAYS": 30,         # age-stale threshold
    "MATCH_THRESHOLD": 0.18,        # live chat -> canonical card (serve)
    "CLUSTER_THRESHOLD": 0.35,      # card -> card (merge; stricter than serve)
    "CLUSTER_EVERY_N_CHATS": 100,   # global ingested-dialogue cursor (SPEC §5)
    # RUN-PROTOCOL §2.2 — synthesized agent pool
    "AGENT_POOL_SIZE": 4,
    # RUN-PROTOCOL §2.3 — fixed timeline origin, recorded in the manifest
    "T0": "2026-08-28T00:00:00Z",
    # SPEC §4 field limits
    "MAX_WORDS_FIELD": 12,          # problem_shape / constraint / unlock
    "MAX_WORKED": 8,                # what_worked items
}

TIMELINE_MODES = ("compressed", "aged")

# Coercion order for --set values: int, float, else keep the string.
def _coerce(value):
    for cast in (int, float):
        try:
            return cast(value)
        except ValueError:
            continue
    return value


def parse_overrides(set_args):
    """Turn a list of 'key=value' --set args into a dict of config overrides.

    Unknown keys are a hard error: a typo must not silently tune nothing.
    """
    out = {}
    for item in set_args or []:
        if "=" not in item:
            raise ValueError(f"--set expects KEY=VALUE, got {item!r}")
        key, _, raw = item.partition("=")
        if key not in DEFAULTS:
            raise ValueError(
                f"unknown config key {key!r} (known: {sorted(DEFAULTS)})"
            )
        out[key] = _coerce(raw)
    return out


class Config:
    """Immutable-ish view over DEFAULTS plus optional overrides."""

    def __init__(self, overrides=None):
        self.values = dict(DEFAULTS)
        if overrides:
            for key, val in overrides.items():
                if key not in DEFAULTS:
                    raise ValueError(f"unknown config key {key!r}")
                self.values[key] = val

    def __getattr__(self, name):
        # only called when normal attribute lookup fails
        try:
            return self.values[name]
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, name):
        return self.values[name]

    def get(self, name, default=None):
        return self.values.get(name, default)

    def as_dict(self):
        return dict(self.values)


def add_set_flag(parser):
    """Attach the standard --set flag to an argparse parser."""
    parser.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE",
        help="override a config key (repeatable), e.g. --set MATCH_THRESHOLD=0.99",
    )


def make_config(set_args):
    return Config(parse_overrides(set_args))
