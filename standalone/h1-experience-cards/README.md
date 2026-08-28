# Hypothesis 1 — Experience cards (standalone)

Isolated slice. Do not import, call, or depend on anything else in this
repository: not `openspec/`, not Google Memory Bank, not the DSPy compiler,
not the M1–M3 lab code under `research/`.

Issue: [#28](https://github.com/camorazrushimoe/federated-agent-memory/issues/28)

## What you implement

A handful of scripts that turn finished customer chats into short cards,
keep most of them private, and — when a later chat looks the same — hand
the next agent a **recommendation packet**, never a rule.

```
chat closed
    → extract_card     (prompt in PROMPTS.md)
    → store            (status = private)
    → match            (same scope, lexical)
    → promote          (private → shared at K=2 independent hits)
    → serve_packet     (evidence prompt in PROMPTS.md)
    → feedback         (helpful keeps it; wrong/stale expires it)
```

## Files

| file | role |
|--|--|
| `SPEC.md` | contract: data, scripts, states, matching, promotion, eval |
| `PROMPTS.md` | frozen prompts: extract, serve, feedback-label |
| `fixtures/` | added when scripts land; keep empty until then |

## Order of work

1. Read `SPEC.md` + `PROMPTS.md`. Do not invent extra fields.
2. Implement the script list in `SPEC.md` §6.
3. Run the fixture dialogues.
4. Print the numbers in `SPEC.md` §9.

No service, no database, no vector DB. JSONL on disk is enough for this hypothesis.
