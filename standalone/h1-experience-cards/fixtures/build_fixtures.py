#!/usr/bin/env python3
"""build_fixtures.py — deterministic generator for the SPEC §10 fixtures.

Writes:
  fixtures/spec10_dialogues.jsonl        normalized §3 records (two-agent)
  fixtures/spec10_dialogues_a1.jsonl     same, every agent_id=agent-a (§10.3)
  fixtures/raw_extract/<dialogue_id>.json  canned extract responses (replay
                                          fuel for the deterministic checks)

Re-running this script reproduces the files byte-for-byte. No LLM calls.

Canned responses deliberately exercise: markdown fences (d-001), unlock=none
on the oldest card of a pair (d-x1), rejection by empty problem_shape
(d-rej1), rejection by empty everything (d-rej2), contains_pii=true with a
raw email the scrub must replace (d-pii), and a 'gift card' transcript that
must NOT set contains_pii (d-gift).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                + "/bin")
import h1lib as H  # noqa: E402

FIX = os.path.dirname(os.path.abspath(__file__))

MODEL = "deepseek-v4-flash"  # fixture metadata only — canned responses are
# model-agnostic; extract.py still requires an explicit --model (D8)

USAGE = {"prompt_tokens": 320, "completion_tokens": 64,
         "total_tokens": 384}


def dialogue(did, tenant, vertical, agent, closed, turns):
    return {
        "dialogue_id": did,
        "tenant_id": tenant,
        "vertical": vertical,
        "agent_id": agent,
        "channel": "web",
        "closed_at": closed,
        "turns": turns,
    }


def t(role, text, name=None):
    d = {"role": role, "text": text}
    if name:
        d["name"] = name
    return d


EXCHANGE = [
    t("customer", "ordered size 42 sneakers, got 41, want an exchange, tag is "
                   "already cut off"),
    t("agent", "exchanges without a tag are blocked by policy"),
    t("customer", "that is not acceptable, the box was wrong"),
    t("agent", "if you send a photo of the pair and the order number I can "
               "open this as a defect"),
    t("customer", "photo sent, order 4412"),
    t("tool", "order 4412, size 42 shipped, size 41 scanned at warehouse",
      name="lookup_order"),
    t("agent", "defect ticket opened, warehouse will pick up"),
]

EXCHANGE_VARIANTS = [
    "received the wrong size and the tag is cut off, need an exchange",
    "sneakers came in size 41 instead of 42 and the tag is gone",
    "want to swap for the right size but the tag was removed already",
    "box had the wrong size and I cut the tag before noticing",
    "need an exchange for a size 41 pair that should have been 42",
    "tag is already off and the size is wrong, can you exchange it",
    "got the wrong size sneakers and the tag is missing",
    "the pair I got is size 41, tag removed, need the right size",
    "wrong size delivered and the tag was already cut off",
]

EXCHANGE_AGENT = [
    "exchanges without a tag are blocked by policy, but if you send a photo "
    "of the pair and the order number I can reclassify this as a defect",
    "policy blocks exchanges without a tag; a photo and order id let me open "
    "a defect instead",
    "no exchange without the tag; send a photo and the order number and I "
    "will reclassify it as a defect",
    "without the tag an exchange is blocked; a photo plus the order id "
    "unblocks a defect ticket",
    "policy blocks the exchange; with a photo and order number I can "
    "reclassify it as a defect",
    "exchange blocked by policy without the tag; a photo and order id let me "
    "open a defect",
    "the tag is required for an exchange; otherwise reclassify as a defect "
    "with a photo and order id",
    "policy blocks this exchange without the tag; send a photo and order "
    "number for a defect ticket",
    "no tag means no exchange; a photo and the order number let me "
    "reclassify as a defect",
]

# §10.1 / §10.2: d-001 exactly the worked example; d-002..d-010 variants.
# closed_at within STALE_AFTER_DAYS of the pinned fixture clock
# (2026-08-28T00:00:00Z) so the age rule never fires on these — §10.2/10.3
# must produce shared/private by votes alone. Freshness (§10.5) uses its own
# deliberately old timestamps further down.
DIALOGUES = [
    dialogue("d-001", "shop-acme", "retail-support", "agent-a",
             "2026-08-08T10:00:00Z", EXCHANGE),
]
for i, (cv, av) in enumerate(zip(EXCHANGE_VARIANTS, EXCHANGE_AGENT)):
    did = f"d-{i + 2:03d}"
    agent = "agent-a" if (i + 2) % 2 == 1 else "agent-b"  # d-002 b, d-003 a..
    DIALOGUES.append(dialogue(
        did, "shop-acme", "retail-support", agent,
        f"2026-08-{i + 9:02d}T10:00:00Z",
        [t("customer", cv), t("agent", av),
         t("customer", "photo sent, order 4412"),
         t("agent", "defect ticket opened, warehouse will pick up")]))

# d-011: live chat in the same scope (serve test — must match the cluster)
DIALOGUES.append(dialogue(
    "d-011", "shop-acme", "retail-support", "agent-a", "2026-08-25T10:00:00Z",
    [t("customer", "I need an exchange, wrong size and the tag is already "
                   "removed"),
     t("agent", "policy blocks exchanges without a tag, but a photo and the "
                "order id let me reclassify this as a defect"),
     t("customer", "here is the photo and the order number"),
     t("agent", "defect ticket opened")]))

# d-012: billing vertical (cross-vertical serve test — must be empty)
DIALOGUES.append(dialogue(
    "d-012", "shop-acme", "billing", "agent-a", "2026-08-25T10:00:00Z",
    [t("customer", "I was charged twice for my subscription this month"),
     t("agent", "I can see two charges on the account, issuing one refund"),
     t("customer", "thank you")]))

# d-013: same scope as the exchange cluster (served_to / anti-echo test)
DIALOGUES.append(dialogue(
    "d-013", "shop-acme", "retail-support", "agent-b", "2026-08-26T10:00:00Z",
    [t("customer", "wrong size delivered, tag cut off, want an exchange"),
     t("agent", "without the tag an exchange is blocked; a photo and the "
                "order number let me reclassify it as a defect"),
     t("customer", "photo sent"),
     t("agent", "defect ticket opened")]))

# Freshness fixture (§10.5): a separate story, two clusters.
#  d-10x (canonical, closed 40+ days ago) + d-10y (member, closed yesterday)
#  -> last_closed_at = yesterday -> NOT stale with now=2026-08-28.
#  d-10z + d-10w (both closed 69 days ago) -> quiet cluster -> stale.
FRESH_A = "order shows delivered but I never received the package"
FRESH_B = ("carrier marked it delivered, send the delivery photo and I will "
           "open a missing package claim")
DIALOGUES.append(dialogue(
    "d-10x", "shop-acme", "retail-support", "agent-a", "2026-06-20T10:00:00Z",
    [t("customer", FRESH_A), t("agent", FRESH_B),
     t("customer", "I have the photo"), t("agent", "claim opened")]))
DIALOGUES.append(dialogue(
    "d-10y", "shop-acme", "retail-support", "agent-b", "2026-08-27T10:00:00Z",
    [t("customer", FRESH_A), t("agent", FRESH_B),
     t("customer", "photo attached"), t("agent", "claim opened")]))
DIALOGUES.append(dialogue(
    "d-10z", "shop-acme", "retail-support", "agent-a", "2026-06-20T11:00:00Z",
    [t("customer", "subscription shows active but my access is locked"),
     t("agent", "the account has a payment hold, pay the invoice to unlock"),
     t("customer", "paid it"), t("agent", "access restored")]))
DIALOGUES.append(dialogue(
    "d-10w", "shop-acme", "retail-support", "agent-b", "2026-06-21T10:00:00Z",
    [t("customer", "subscription active but access locked"),
     t("agent", "payment hold on the account, pay the invoice"),
     t("customer", "done"), t("agent", "access restored")]))

# Inheritance pair (C-CL8): oldest card unlock=none, member has a real unlock
DIALOGUES.append(dialogue(
    "d-x1", "shop-acme", "retail-support", "agent-a", "2026-08-18T10:00:00Z",
    [t("customer", "I forgot my password and cannot log in"),
     t("agent", "password reset is blocked without identity verification"),
     t("customer", "what can I do"), t("agent", "answer the security "
                                                "questions to reset it"),
     t("customer", "answered"), t("agent", "password reset sent")]))
DIALOGUES.append(dialogue(
    "d-x2", "shop-acme", "retail-support", "agent-b", "2026-08-19T10:00:00Z",
    [t("customer", "locked out, forgot the password"),
     t("agent", "reset is blocked without verification; answer the security "
                "questions"),
     t("customer", "answered them"), t("agent", "reset email sent")]))

# C-EX7: bare word "card" must not set contains_pii
DIALOGUES.append(dialogue(
    "d-gift", "shop-acme", "retail-support", "agent-a", "2026-08-20T10:00:00Z",
    [t("customer", "what is the balance on my gift card"),
     t("agent", "the gift card balance is 50"),
     t("customer", "thanks")]))

# C-EX8: rejection fixtures
DIALOGUES.append(dialogue(
    "d-rej1", "shop-acme", "retail-support", "agent-a", "2026-08-21T10:00:00Z",
    [t("customer", "hi"), t("agent", "hello how can I help"),
     t("customer", "nothing thanks")]))
DIALOGUES.append(dialogue(
    "d-rej2", "shop-acme", "retail-support", "agent-a", "2026-08-22T10:00:00Z",
    [t("customer", "never mind"), t("agent", "ok")]))

# Scrub test: model left a raw email inside what_worked
DIALOGUES.append(dialogue(
    "d-pii", "shop-acme", "retail-support", "agent-b", "2026-08-23T10:00:00Z",
    [t("customer", "please email the receipt to albert@example.com"),
     t("agent", "the receipt was emailed to albert@example.com"),
     t("customer", "got it")]))


# --------------------------------------------------------------------------
# Canned extract responses
# --------------------------------------------------------------------------

EXCHANGE_CARD = {
    "problem_shape": "exchange wrong size tag removed",
    "constraint": "policy blocks exchange without tag",
    "unlock": "reclassify as defect with photo and order id",
    "what_worked": ["lookup order", "policy check", "request defect photo",
                    "open defect ticket"],
    "contains_pii": True,
}


def canned(did, obj, fences=False, contains_pii=None):
    if contains_pii is not None:
        obj = dict(obj)
        obj["contains_pii"] = contains_pii
    text = json.dumps(obj)
    if fences:
        text = "```json\n" + text + "\n```"
    return {
        "dialogue_id": did,
        "model": MODEL,
        "request": {"system": "", "user": ""},
        "response_text": text,
        "parsed": True,
        "usage": dict(USAGE),
        "ms": 0,
        "finish_reason": "stop",
        "error": None,
    }


RESPONSES = []
RESPONSES.append(canned("d-001", EXCHANGE_CARD, fences=True))
for i in range(2, 11):
    RESPONSES.append(canned(f"d-{i:03d}", EXCHANGE_CARD))
RESPONSES.append(canned("d-011", EXCHANGE_CARD))
RESPONSES.append(canned("d-012", {
    "problem_shape": "charged twice for subscription",
    "constraint": "billing system shows duplicate charge",
    "unlock": "issue refund for duplicate charge",
    "what_worked": ["look up charges", "issue refund"],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-013", EXCHANGE_CARD))
RESPONSES.append(canned("d-10x", {
    "problem_shape": "order not delivered marked delivered",
    "constraint": "carrier marked package delivered",
    "unlock": "request delivery photo and open claim",
    "what_worked": ["check carrier status", "request delivery photo",
                    "open missing package claim"],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-10y", {
    "problem_shape": "order not delivered marked delivered",
    "constraint": "carrier marked package delivered",
    "unlock": "request delivery photo and open claim",
    "what_worked": ["check carrier status", "request delivery photo",
                    "open missing package claim"],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-10z", {
    "problem_shape": "subscription active but access locked",
    "constraint": "payment hold on account",
    "unlock": "pay invoice to unlock access",
    "what_worked": ["check account status", "take payment"],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-10w", {
    "problem_shape": "subscription active but access locked",
    "constraint": "payment hold on account",
    "unlock": "pay invoice to unlock access",
    "what_worked": ["check account status", "take payment"],
    "contains_pii": False,
}))
# inheritance pair: canonical unlock=none, member has a real unlock
RESPONSES.append(canned("d-x1", {
    "problem_shape": "password reset blocked by policy",
    "constraint": "cannot reset password without verification",
    "unlock": "none",
    "what_worked": ["check identity", "offer security questions"],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-x2", {
    "problem_shape": "password reset blocked by policy",
    "constraint": "cannot reset password without verification",
    "unlock": "reset password with security questions",
    "what_worked": ["check identity", "answer security questions",
                    "send reset link"],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-gift", {
    "problem_shape": "gift card balance query",
    "constraint": "none",
    "unlock": "none",
    "what_worked": ["check gift card balance"],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-rej1", {
    "problem_shape": "",
    "constraint": "none",
    "unlock": "none",
    "what_worked": [],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-rej2", {
    "problem_shape": "nothing happened in the chat",
    "constraint": "none",
    "unlock": "none",
    "what_worked": [],
    "contains_pii": False,
}))
RESPONSES.append(canned("d-pii", {
    "problem_shape": "receipt email request",
    "constraint": "none",
    "unlock": "send receipt to email",
    "what_worked": ["look up receipt", "email support@shop.com"],
    "contains_pii": True,
}))


def main():
    H.write_jsonl(os.path.join(FIX, "spec10_dialogues.jsonl"), DIALOGUES,
                  mode="w")
    a1 = [dict(d, agent_id="agent-a") for d in DIALOGUES]
    H.write_jsonl(os.path.join(FIX, "spec10_dialogues_a1.jsonl"), a1,
                  mode="w")
    raw_dir = os.path.join(FIX, "raw_extract")
    os.makedirs(raw_dir, exist_ok=True)
    for r in RESPONSES:
        with open(os.path.join(raw_dir, f"{r['dialogue_id']}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(DIALOGUES)} dialogues (2-agent + a1 variants), "
          f"{len(RESPONSES)} canned responses")


if __name__ == "__main__":
    main()
