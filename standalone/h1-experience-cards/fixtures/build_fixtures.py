#!/usr/bin/env python3
"""Build the SPEC §10 fixture dialogues (deterministic).

    python fixtures/build_fixtures.py

Writes every `*.jsonl` dialogue file under fixtures/ as SPEC §3 records.
The baked extract responses (fixtures/raw/extract/*.json) are produced by
`bake_fixtures.py` (one real LLM call per extracted dialogue, committed so the
fixture suite runs with zero LLM calls).

Dialogue roster:
- d001.jsonl            §10.1 worked example (d-001, agent-a)
- ten_dupes_2agents.jsonl  d-001..d-010 same story, agents alternate a/b
- ten_dupes_1agent.jsonl   same ten dialogues, every agent = agent-a
- live_d011.jsonl       d-011 same-scope live query (served, never extracted)
- live_d012.jsonl       d-012 vertical=billing (cross-vertical serve must be empty)
- live_d013.jsonl       d-013 same story, agent-c (anti-echo test)
- gift_card.jsonl       d-gc1 "gift card" chat, no identifiers (C-EX7)
- freshness_new_member.jsonl d-fa1 (40d ago) + d-fa2 (yesterday), same story
- freshness_quiet.jsonl      d-fb1 (35d ago), single card
- two_clusters.jsonl    d-tc1..d-tc4: two stories x two agents (C-FB4 packet)
- live_two_clusters.jsonl    d-tc5 bridging both stories (2-card packet)
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCOPE_T = "abcd-shop"
VERTICAL = "customer-support"
BILLING = "billing"


def rec(dialogue_id: str, tenant_id: str, vertical: str, agent_id: str,
        turns: list[dict], closed_at: str | None = None) -> dict:
    r = {
        "dialogue_id": dialogue_id,
        "tenant_id": tenant_id,
        "vertical": vertical,
        "agent_id": agent_id,
        "channel": "web",
        "turns": turns,
    }
    if closed_at:
        r["closed_at"] = closed_at
    return r


def t(role: str, text: str, name: str | None = None) -> dict:
    d = {"role": role, "text": text}
    if name:
        d["name"] = name
    return d


# ---- §10.1 worked example ---------------------------------------------------
D001_TURNS = [
    t("customer", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off"),
    t("agent", "exchanges without a tag are blocked by policy"),
    t("customer", "that is not acceptable, the box was wrong"),
    t("agent", "if you send a photo of the pair and the order number I can open this as a defect"),
    t("customer", "photo sent, order 4412"),
    t("tool", "order 4412, size 42 shipped, size 41 scanned at warehouse", name="lookup_order"),
    t("agent", "defect ticket opened, warehouse will pick up"),
]

# ---- the ten near-duplicates (SPEC §10.2) -----------------------------------
# The ten chats carry the SAME story with identical wording — only the
# dialogue_id and agent differ. This is a wiring fixture (does clustering
# merge, do votes/promotion/echo work); extraction variance across near-dupes
# is a generalization question measured by the real-run audit A4, not by the
# S0 fixture. Identical transcripts -> near-identical baked cards -> the ten
# MUST form one cluster, deterministically.
DUPES = [
    ("d-001", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-002", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-003", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-004", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-005", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-006", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-007", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-008", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-009", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
    ("d-010", "ordered size 42 sneakers, got 41, want an exchange, tag is already cut off",
     "exchanges without a tag are blocked by policy",
     "if you send a photo of the pair and the order number I can open this as a defect",
     "photo sent, order 4412"),
]

GIFT_CARD = [
    t("customer", "hi do you sell gift cards in the store"),
    t("agent", "yes we do, digital and physical gift cards are available"),
    t("customer", "great, and can I use one for any product"),
    t("agent", "gift cards can be used on most items, there are a few exclusions"),
    t("customer", "thanks that helps"),
]

STORY_A = "wrong size tag removed exchange blocked"
STORY_A_CUSTOMER = [
    "ordered size 42 sneakers got 41 and the tag is cut off, exchange blocked",
    "same issue here, wrong size and the tag is already removed so no exchange",
]
STORY_B = "item arrived damaged wants refund"
STORY_B_CUSTOMER = [
    "the jacket arrived damaged with a tear, I want a refund",
    "my order came with a damaged pair, please refund it",
]
STORY_A_AGENT = "send a photo and the order id to open a defect ticket"
STORY_B_AGENT = "for damaged items we can refund once you return the item"

LIVE_D011 = [
    t("customer", "I need to exchange sneakers but the tag is already cut off, is there any way"),
    t("agent", "let me check what we can do for you"),
]
LIVE_D012 = [
    t("customer", "my credit card was charged twice this month, can you help"),
    t("agent", "I can look into the billing statement"),
]
LIVE_D013 = [
    t("customer", "wrong size sneakers, tag cut off, exchange refused, same story as before"),
    t("agent", "we can open this as a defect with a photo and the order number"),
    t("customer", "photo and order id sent"),
]
LIVE_TWO_CLUSTERS = [
    t("customer", "I got the wrong size sneakers and the tag is cut so the exchange is blocked, "
                  "and on top of that the jacket I ordered arrived damaged and I want a refund"),
    t("agent", "let me handle both: defect ticket for the sneakers and a return for the jacket"),
]

AGENTS2 = ["agent-a", "agent-b"]  # d-001 -> agent-a, d-002 -> agent-b, ...
ECHO_AGENT = "agent-c"


def build() -> None:
    out: dict[str, list[dict]] = {}

    # §10.1
    out["d001.jsonl"] = [rec("d-001", SCOPE_T, VERTICAL, "agent-a", D001_TURNS)]

    # ten dupes (2 agents, alternating)
    dupes2 = []
    for i, (did, cust, pol, unlock_line, cust2) in enumerate(DUPES):
        dupes2.append(rec(did, SCOPE_T, VERTICAL, AGENTS2[i % 2], [
            t("customer", cust),
            t("agent", pol),
            t("customer", "that is not acceptable"),
            t("agent", unlock_line),
            t("customer", cust2),
            t("agent", "defect ticket opened, warehouse will pick up"),
        ]))
    out["ten_dupes_2agents.jsonl"] = dupes2
    out["ten_dupes_1agent.jsonl"] = [
        rec(d["dialogue_id"], d["tenant_id"], d["vertical"], "agent-a", d["turns"],
            d.get("closed_at")) for d in dupes2]

    out["live_d011.jsonl"] = [rec("d-011", SCOPE_T, VERTICAL, "agent-a", LIVE_D011)]
    out["live_d012.jsonl"] = [rec("d-012", SCOPE_T, BILLING, "agent-a", LIVE_D012)]
    out["live_d013.jsonl"] = [rec("d-013", SCOPE_T, VERTICAL, ECHO_AGENT, LIVE_D013)]

    out["gift_card.jsonl"] = [rec("d-gc1", SCOPE_T, VERTICAL, "agent-a", GIFT_CARD)]

    # freshness (explicit closed_at; pinned staleness clock 2026-08-28T00:00:00Z)
    out["freshness_new_member.jsonl"] = [
        rec("d-fa1", SCOPE_T, VERTICAL, "agent-a", [
            t("customer", STORY_A_CUSTOMER[0]), t("agent", STORY_A_AGENT),
            t("customer", "photo and order id sent")],
            closed_at="2026-07-19T10:00:00Z"),  # 40 days before the pinned clock
        rec("d-fa2", SCOPE_T, VERTICAL, "agent-b", [
            t("customer", STORY_A_CUSTOMER[1]), t("agent", STORY_A_AGENT),
            t("customer", "photo and order id sent")],
            closed_at="2026-08-27T10:00:00Z"),  # yesterday
    ]
    out["freshness_quiet.jsonl"] = [
        rec("d-fb1", SCOPE_T, VERTICAL, "agent-a", [
            t("customer", STORY_A_CUSTOMER[0]), t("agent", STORY_A_AGENT),
            t("customer", "photo and order id sent")],
            closed_at="2026-07-24T10:00:00Z"),  # 35 days -> stale
    ]

    # two clusters, one scope (C-FB4 multi-card packet)
    out["two_clusters.jsonl"] = [
        rec("d-tc1", SCOPE_T, VERTICAL, "agent-a", [
            t("customer", STORY_A_CUSTOMER[0]), t("agent", STORY_A_AGENT),
            t("customer", "photo sent")]),
        rec("d-tc2", SCOPE_T, VERTICAL, "agent-b", [
            t("customer", STORY_A_CUSTOMER[1]), t("agent", STORY_A_AGENT),
            t("customer", "photo sent")]),
        rec("d-tc3", SCOPE_T, VERTICAL, "agent-a", [
            t("customer", STORY_B_CUSTOMER[0]), t("agent", STORY_B_AGENT),
            t("customer", "returning it")]),
        rec("d-tc4", SCOPE_T, VERTICAL, "agent-b", [
            t("customer", STORY_B_CUSTOMER[1]), t("agent", STORY_B_AGENT),
            t("customer", "returning it")]),
    ]
    out["live_two_clusters.jsonl"] = [
        rec("d-tc5", SCOPE_T, VERTICAL, "agent-a", LIVE_TWO_CLUSTERS)]

    for name, rows in out.items():
        p = HERE / name
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                     encoding="utf-8")
        print(f"{name}: {len(rows)} dialogues")


if __name__ == "__main__":
    build()
