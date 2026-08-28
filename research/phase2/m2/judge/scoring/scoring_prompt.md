You are performing the M2 reconstruction SCORING pass (Federated Agent Memory, round R2).
Files you may and should use (the ONLY files you have):
- research/phase2/m2/judge/scoring/PROTOCOL-m2-scoring.md — the frozen scoring protocol v1.0 (READ IT FIRST: references R1-R3, the frozen rubric, rules R1-R5, output contract, honesty clause).
- research/phase2/m2/judge/scoring/scoring_input.jsonl — 80 items, one JSON object per line: convo_codename, transcript, candidates (3 renders with codenames, shuffled).
Constraints (non-negotiable):
- For each item: write your OWN references R1-R3 from the transcript FIRST, then score ALL THREE candidates against your reference with the frozen rubric.
- Candidate codenames are random — do not infer candidate type (rule R2).
- Work in English; scores use ONLY the frozen values.
Output: write research/phase2/m2/judge/scoring/scoring_answers.jsonl with one JSON object per line, in the order the input file presents the items (see protocol section 4):
{"convo_codename": "<codename>", "r1": "...", "r2": "...", "r3": "...", "scores": {"<cand codename>": {"s1": <v>, "s2": <v>, "s3": <v>}, ...}}
Every item exactly once; `scores` must cover all 3 candidates per item.
Then report: (1) the path you wrote, (2) the count of lines, (3) confirmation that you used only the two staged files.

