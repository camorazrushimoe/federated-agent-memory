"""Conformance check for the M2 scoring answers file."""
import json
rows = [json.loads(l) for l in open(r"research/phase2/m2/judge/scoring/scoring_answers.jsonl") if l.strip()]
inp = [json.loads(l) for l in open(r"research/phase2/m2/judge/scoring/scoring_input.jsonl") if l.strip()]
assert len(rows) == len(inp), f"row count {len(rows)} != {len(inp)}"
for row, it in zip(rows, inp):
    assert row['convo_codename'] == it['convo_codename'], 'codename/order mismatch'
    assert set(row.keys()) == {'convo_codename','r1','r2','r3','scores'}, f"fields {sorted(row.keys())}"
    for k in ('r1','r2','r3'):
        assert isinstance(row[k], str) and len(row[k].strip()) >= 1, f"empty {k}"
    want = {c['codename'] for c in it['candidates']}
    assert set(row['scores'].keys()) == want, f"candidate coverage {{set(row['scores'].keys())}}"
    for c, sc in row['scores'].items():
        assert set(sc.keys()) == {'s1','s2','s3'}, f"{c}: {{sorted(sc.keys())}}"
        assert sc['s1'] in (0, 0.5, 1), f"{c} s1 {{sc['s1']}}"
        assert sc['s2'] in (0, 0.5, 1), f"{c} s2 {{sc['s2']}}"
        assert sc['s3'] in (0, 0.25, 0.5, 1), f"{c} s3 {{sc['s3']}}"
print(f"SCORING ANSWERS CONFORM: {len(rows)}/{len(inp)} items, all candidates scored")
