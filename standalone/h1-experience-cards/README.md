# Hypothesis 1 — Experience cards (standalone)

Isolated slice. Do not import, call, or depend on anything else in this
repository: not `openspec/`, not Google Memory Bank, not the DSPy compiler,
not the M1–M3 lab code under `research/`.

Issue: [#28](https://github.com/camorazrushimoe/federated-agent-memory/issues/28)
PR: [#29](https://github.com/camorazrushimoe/federated-agent-memory/pull/29)

## What you implement

A handful of scripts that turn finished customer chats into short cards,
merge the ones that are the same story, and — when a later chat looks the
same — hand the next agent a **recommendation packet**, never a rule.

```
chat closed
    → tick.py               ingest + extract + (cluster if 100 new chats)
    → extract               private canonical, votes = 1
    → cluster               same-scope cards collapse; inherit better fields
    →                       votes ≥ K and independent agents → shared
    → live chat             match+serve top-3 shared canonical cards
    → feedback              wrong/stale expires the canonical card
```

Clustering is a **volume trigger**, not a timer. `tick.py` is the only entry
point an operator needs. `--force` exists for fixtures.

## Files

| file | role |
|--|--|
| `SPEC.md` | contract: data, states, scripts, clustering, eval |
| `PROMPTS.md` | frozen prompts: extract, serve, feedback-label |
| `fixtures/` | added when scripts land |

## Order of work

1. Read `SPEC.md` + `PROMPTS.md`. Do not invent extra fields.
2. Implement the script list in `SPEC.md` §6.
3. Run the fixture dialogues.
4. Print the numbers in `SPEC.md` §9.

No service, no database, no vector DB. JSONL on disk is enough for this hypothesis.
