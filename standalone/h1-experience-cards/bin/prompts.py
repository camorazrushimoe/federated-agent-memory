"""Frozen-prompt loader — reads the strings from PROMPTS.md at runtime.

PROMPTS.md: "Frozen for v1. Change them in this file only. Scripts MUST load
these strings from here." Loading at runtime (instead of copy-pasting) keeps
PROMPTS.md the single source of truth; its sha256 goes into the manifest, so a
prompt edit forces a new run id by construction (EVAL-PLAN §11).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_FENCE = re.compile(r"^```\w*\s*$", re.MULTILINE)


def _sections(md: str, header: str) -> list[str]:
    """Fenced code blocks under `## <header>...`, in order (title prefix match)."""
    sections = re.split(r"^## ", md, flags=re.MULTILINE)
    for s in sections:
        if s.startswith(header):
            body = s[len(header):].strip()
            parts = _FENCE.split(body)
            # split pieces alternate: [before, BLOCK, between, BLOCK, after]
            blocks = [parts[i].strip() for i in range(1, len(parts), 2)]
            return blocks
    raise ValueError(f"PROMPTS.md section not found: ## {header}")


class Prompts:
    def __init__(self, prompts_path: str | None = None):
        root = Path(prompts_path) if prompts_path else Path(__file__).resolve().parent.parent
        p = root if root.name == "PROMPTS.md" else root / "PROMPTS.md"
        md = p.read_text(encoding="utf-8")
        self.path = str(p)
        self.sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
        self.extract_system = _sections(md, "1. Extract — system")[0]
        self.extract_user = _sections(md, "2. Extract — user")[0]
        self.serve_template = _sections(md, "4. Serve — packet template")[0]
        self.serve_rewrite_system = _sections(md, "5. Serve — optional rewrite")[0]
        fb = _sections(md, "6. Feedback label — system")
        self.feedback_system = fb[0]
        self.feedback_user = fb[1] if len(fb) > 1 else ""

    def extract_user_text(self, *, tenant_id, vertical, channel, transcript) -> str:
        return self.extract_user.format(tenant_id=tenant_id, vertical=vertical,
                                        channel=channel, transcript=transcript)

    def serve_packet(self, *, scope: str, cards: list[dict]) -> str:
        """Render the packet template (PROMPTS.md §4). Deterministic, no LLM.

        Card blocks are built here per §4; the template's own inner
        {card_id}/{problem_shape}/... placeholders are inert text.
        """
        blocks = []
        for c in cards:
            lines = [f"- [{c['card_id']}] When the request looked like: {c['problem_shape']}"]
            if c.get("constraint") and c["constraint"] != "none":
                lines.append(f"  Blocked by: {c['constraint']}")
            if c.get("unlock") and c["unlock"] != "none":
                lines.append(f"  What unblocked it: {c['unlock']}")
            lines.append(f"  Steps that ran: {' → '.join(c.get('what_worked', []))}")
            blocks.append("\n".join(lines))
        return (self.serve_template
                .replace("{scope}", scope)
                .replace("{cards}", "\n\n".join(blocks)))
