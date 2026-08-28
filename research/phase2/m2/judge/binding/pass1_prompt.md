You are performing PASS 1 of the M2 blind reconstruction test (Federated Agent Memory, round R2).
Files you may and should use (the ONLY files you have):
- research/phase2/m2/judge/binding/PROTOCOL-m2-blind.md — the frozen protocol v1.0 (READ IT FIRST: Q1–Q3, rules R1–R4, output contract, honesty clause).
- research/phase2/m2/judge/binding/pass1_input.jsonl — 240 items, one JSON object per line, fields: item_id, codename, question, render.
Constraints (non-negotiable):
- Answer every item on Q1, Q2, Q3 from the render ONLY (protocol sections 2–3).
- You are not told which conversation or which candidate type any item is — do not try to work it out; it is irrelevant to the task.
- No access to any other pass's answers — by design (pass independence).
- Work in English.
Output: write research/phase2/m2/judge/binding/pass1_answers.jsonl with one JSON object per line, in the order the input file presents the items:
{"item_id": "<id>", "pass": 1, "q1": "...", "q2": "...", "q3": "..."}
Every item exactly once, in input order.
Then report: (1) the path you wrote, (2) the count of lines, (3) confirmation that you used only the two staged files.

