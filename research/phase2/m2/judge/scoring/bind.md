# M2 scoring BIND layer (frozen 2-call structure)

80 convos. Two fresh-context calls: **reference** (transcript ONLY → R1-R3) and **scoring** (transcript + 3 anonymized candidates + the committed reference → scores). Reference + base are committed here; the scoring input is built at stage time from the committed reference. Budget: 80 reference + 80 scoring = 160 (round total 640, the frozen ceiling).
Stage: `stage_scoring_pass.py stage-reference --bind <this dir> --stage-dir <dir>` (Call 1); then `stage_scoring_pass.py stage-scoring --bind <this dir> --stage-dir <dir> --reference <reference_answers.jsonl>` (Call 2). Hand each staged directory (only) to a fresh agent session.

- `PROTOCOL-m2-scoring.md`
- `bind.md`
- `convo_mapping.json`
- `reference_input.jsonl`
- `scoring_base.jsonl`
- `scoring_manifest.json`
