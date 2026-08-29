"""H2 — pipeline configuration (SPEC §6).

Single place for the numeric knobs of the experiment. Scripts import from here;
the numbers MUST NOT be redefined anywhere else in bin/.
"""
from __future__ import annotations

# SPEC §6 — packet and rotation
MAX_PACKET = 3
EXPLORE_SLOTS = 1
TAG_FIELDS_MIN = 2

# SPEC §6 — decay and outcome deltas
DECAY_EVERY_SHOWS = 5
DECAY_AMOUNT = 0.1
GOOD_DELTA = 1.0
BAD_DELTA = -1.0
UNCLEAR_DELTA = 0.0

# The five tag fields that participate in S3 matching (SPEC §4).
TAG_FIELDS = ["problem_shape", "constraint", "ending", "channel", "vertical"]

# Round 4 (founder dispatch 2026-08-29, PR #63): S3 matching fields ONLY.
# channel/vertical are constant across the pool ('web'/'customer-support'),
# so counting them makes TAG_FIELDS_MIN=2 admit every session (whole-pool
# candidates, ranker degenerates to tie-break). The overlap count now uses
# these three variable fields; the tag schema (TAG_FIELDS) and the S4/S7
# rating key (TAG_KEY_FIELDS) are unchanged.
S3_MATCH_FIELDS = ["problem_shape", "constraint", "ending"]

# Round 3 (lead dispatch 2026-08-29 13:34Z): the S4/S7 RATING key is coarse —
# problem_shape|ending only. S3 matching still uses TAG_FIELDS above; only the
# rating key coarsens, so queries in the same shape/ending bucket share rating
# cells (R1: 60/60 unique 5-field keys => ratings never transfer, rank
# degenerated to tie-break, T.hit 0.0667 == B2).
TAG_KEY_FIELDS = ["problem_shape", "ending"]

# Default tag model. Overridable via --model on every script that can call the
# LLM (tag.py and anything that delegates to it). No key/base-url literals here.
DEFAULT_MODEL = "deepseek-v4-flash"

# Temperature for the only live call in v1 (S2 tag). Frozen at 0.
TEMPERATURE = 0

# SPEC §9 — default state file locations (relative to the experiment root).
DEFAULT_PATHS = {
    "dialogues": "data/dialogues.jsonl",
    "sessions": "data/sessions.jsonl",
    "ratings": "data/ratings.jsonl",
    "candidates": "data/candidates.jsonl",
    "ranked": "data/ranked.jsonl",
    "packet": "data/packet.json",
    "serves": "data/serves.jsonl",
    "outcomes": "data/outcomes.jsonl",
    "query_meta": "data/query_meta.json",
    "update_state": "data/update_state.json",
    "raw_tag": "data/raw/tag",
}
