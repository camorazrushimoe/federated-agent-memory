"""Conformance check for the M2 blind pass-1 answers file."""
import json, sys
rows = [json.loads(l) for l in open(r"research/phase2/m2/judge/binding/pass1_answers.jsonl") if l.strip()]
inp = [json.loads(l) for l in open(r"research/phase2/m2/judge/binding/pass1_input.jsonl") if l.strip()]
assert len(rows) == len(inp), f"row count {len(rows)} != {len(inp)}"
assert [r['item_id'] for r in rows] == [r['item_id'] for r in inp], 'order mismatch'
for r in rows:
    assert set(r.keys()) == {'item_id','pass','q1','q2','q3'}, f"fields {sorted(r.keys())}"
    assert r['pass'] == 1
    for k in ('q1','q2','q3'):
        assert isinstance(r[k], str) and len(r[k].strip()) >= 1, f"empty {k}"
print(f"PASS1 ANSWERS CONFORM: {len(rows)}/{len(inp)} items")
