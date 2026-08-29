# H2 — checks report (S0)

- run dir: `/opt/data/federated-agent-memory/standalone/h2-federated-scoped-memory/runs/2026-08-29_D0_gold_signoff`
- stage: S0 smoke · fixtures only · zero LLM calls (S2 replays the committed bake)
- HARD: 65 passed, 0 failed, 11 deferred · SOFT: 6 total, 0 failed

## Чеки

| id | step | hard | passed | observed | expected | note |
|---|---|---|---|---|---|---|
| C-ISO1 | iso | HARD | PASS | [] | no imports from research/, openspec/, H1, GitLab-POC in bin/ |  |
| C-ISO2 | iso | HARD | PASS | {"forbidden_tokens": [], "urllib_files": ["common.py", "llm.py"], "non_pipeline_files": [" | no embeddings/vector stores/DB drivers; urllib only inside the sanctioned wrappers (common |  |
| C-ISO3 | iso | HARD | PASS | {"issues": [], "call_llm_defs": ["common.py"], "call_llm_callers": ["common.py", "tag.py"] | no key/base-url literals; H2_API_KEY only; the pipeline calls call_llm only via common.py' |  |
| C-ISO4 | iso | HARD | PASS | fx-tenant: d-001 in candidates=True, d-014 (other tenant) in candidates=True | two dialogues with different tenant_id and same tags are both candidates (fixtures d-001/d |  |
| C-ISO5 | iso | HARD | PASS | fixtures byte-identical after the run: True | the run writes only into the workdir; fixtures/ and H1 data/ untouched | fixture files snapshotted before/after the fixture suite |
| C-IN1 | S1 | HARD | PASS | kept 10 + dropped 1 vs input rows 11 | kept + dropped == rows in the input file |  |
| C-IN2 | S1 | HARD | PASS | dropped 1 (fixture d-006 has no customer turn); customer-turn counts: [2, 2, 2, 2, 2, 2, 2 | only the no-customer chat is dropped; every kept row has >=1 customer turn (fx-drop) |  |
| C-IN3 | S1 | HARD | PASS | rows failing schema: [] | required keys + turns[].role in {customer, agent, tool} |  |
| C-IN4 | S1 | HARD | PASS | rows 10, unique 10 | dialogue_id unique |  |
| C-IN5 | S1 | HARD | PASS | re-ingest rewrote the same bytes | re-running ingest is byte-identical (upsert, no append-dupes) |  |
| C-IN6 | S1 | HARD | PASS | ingest.py calls_llm=False, imports_tag=False, tags on S1 output=False | S1 sets no tags and never calls the LLM |  |
| C-PROMPT | S2 | HARD | PASS | {"mismatches": [], "render_ok": true} | prompts.py == PROMPTS.md §2/§3/§5/§6; transcript render per §1 |  |
| C-TG1 | S2 | HARD | PASS | bad session_ids: [] | session_id == 's-' + sha256(source_dialogue_id)[:12] |  |
| C-TG2 | S2 | HARD | PASS | sessions with wrong channel/vertical: [] | channel/vertical copied from the dialogue, not from the model answer |  |
| C-TG3 | S2 | HARD | PASS | tag_key mismatches: [] | tag_key == problem_shape|constraint|ending|channel|vertical, no edge spaces |  |
| C-TG4 | S2 | HARD | PASS | [] | ending in enum; constraint <=12 words or 'none'; problem_shape <=12 words |  |
| C-TG5 | S2 | HARD | PASS | dup source rows after re-tag: []; session_ids stable=True | re-tagging the same dialogue_id updates the same session_id; no second pool row |  |
| C-TG6 | S2 | HARD | PASS | {"pii_no_reject": true, "scrubbed": true, "empty_shape_rejects": true, "contains_pii": tru | reject only when problem_shape is empty after the scrub; PII alone never rejects (fx-pii) |  |
| C-PII | S2 | HARD | PASS | {"patterns": [], "sessions": 10} | no email/phone/>=10 digits/cvv/iban/ssn anywhere in tags and turns of the whole pool |  |
| C-TG7 | S2 | HARD | PASS | d-005 alive=True, contains_pii=True, raw identifiers gone=True | fx-pii: session alive, contains_pii=true, raw email/phone/long number absent |  |
| C-TG8 | S2 | HARD | PASS | d-003 contains_pii=False, transcript has 'gift card'=True | the word 'card' in 'gift card' alone does not set contains_pii |  |
| C-TG9 | S2 | HARD | PASS | {"rejected": true, "tag_calls": 2, "unparseable": 2, "session": false, "raw_files": 1, "re | two consecutive unparseable model answers -> reject, no invented tags; one bad + one good  |  |
| C-TG10 | S2 | HARD | PASS | raw files 10 vs bake tag_calls 10; bad keys [] | raw/tag/<dialogue_id>.json with request/response/model/usage for every S2 call |  |
| C-TG11 | S2 | HARD | PASS | sessions without a starter rating row: []; non-zero starters: [] | every new session gets a starter rating row under its own tag_key with score=0, shows=0 |  |
| C-TG12 | S2 | SOFT | PASS | {"tag_calls": 10, "unparseable": 0, "rejected": 0} | share of unparseable JSON and reject rate are recorded (bake summary) | SOFT |
| C-TG13 | S2 | SOFT | PASS | {"with_shape": 10, "with_constraint": 4, "grounded": 10} | grounding: a >=5-char word of problem_shape present in the transcript; counted, never fail | SOFT |
| C-SELF | S3 | HARD | PASS | query session s-853f4cbd4305 / source d-007 in candidates: False | the query never appears among its own candidates |  |
| C-RT1 | S3 | HARD | PASS | candidates below TAG_FIELDS_MIN=2: [] | a candidate must share >= TAG_FIELDS_MIN tag fields with the query; zero overlap is not a  |  |
| C-RT2 | S3 | HARD | PASS | d-001 in candidates=True, d-002 in candidates=True | fx-similar: d-007's candidates include d-001 and d-002 |  |
| C-RT3 | S3 | HARD | PASS | d-003 overlap 2 vs TAG_FIELDS_MIN 2; in candidates=True | fx-far: d-003 is not required in d-007's candidates when shared fields < TAG_FIELDS_MIN |  |
| C-RT4 | S3 | HARD | PASS | {"src": {"calls_llm_directly": false, "imports_tag": true}, "delegate": {"delegated_calls" | S3 calls no LLM itself; an untagged query is delegated to tag.py with the same PROMPTS.md  |  |
| C-RT5 | S3 | HARD | PASS | first run ['s-09058e959d3b', 's-216689894762', 's-396245ddc31b', 's-4383fa5cf886', 's-6898 | re-running retrieve on the same pool and query yields the same candidate id set |  |
| C-RK1 | S4 | HARD | PASS | top slots ['s-09058e959d3b', 's-216689894762'] with (score,shows) [('s-09058e959d3b', (0.0 | first MAX_PACKET-EXPLORE_SLOTS slots are max-score pairs for (session_id, query tag_key);  |  |
| C-RK2 | S4 | HARD | PASS | explore slot s-396245ddc31b vs recomputed s-396245ddc31b | the last slot is exploration: fewer shows, then older last_shown_at (null oldest), then sm |  |
| C-RK3 | S4 | HARD | PASS | ranked ids ['s-09058e959d3b', 's-216689894762', 's-396245ddc31b'] | exploration never duplicates an already selected id |  |
| C-RK4 | S4 | HARD | PASS | {"ranked_ids": ["s-000000000001", "s-000000000002", "s-000000000003"], "explore_slot": "s- | fx-rotate: five same-tag candidates -> packet of 3 and the third id is not forced to be th |  |
| C-RK5 | S4 | HARD | PASS | ranked.jsonl byte-identical on re-run | no LLM; re-ranking the same ratings is byte-identical |  |
| C-RK6 | S4 | SOFT | PASS | {"ranked_ids": ["s-0000000000bb", "s-0000000000aa"], "len": 2, "top_by_score": "s-00000000 | candidates <= MAX_PACKET -> the packet is all candidates in score order, no invented explo | SOFT |
| C-SIZE | S5 | HARD | PASS | packet sessions 3 (MAX_PACKET=3) | no more than MAX_PACKET sessions; empty ranked -> header-only packet, no invented sessions |  |
| C-MX1 | S5 | HARD | PASS | [] | the packet carries whole turns, not summaries or cards |  |
| C-MX2 | S5 | HARD | PASS | header ok=True, blocks start with [session_id]=True | packet text is the PROMPTS.md §5 template: header on top, every block starts with [session |  |
| C-MX3 | S5 | HARD | PASS | packet ids ['s-09058e959d3b', 's-216689894762', 's-396245ddc31b'] vs ranked ids ['s-09058e | self-mix forbidden; no id outside ranked (C-SELF on the mix output) |  |
| C-MX4 | S5 | HARD | PASS | {"query_id": "d-007", "tag_key": "login fails after password reset|none|unknown|web|retail | serves.jsonl holds query_id, tag_key and the packet session_ids in packet order |  |
| C-MX5 | S5 | HARD | PASS | packet keys: ['packet_session_ids', 'packet_text', 'query_id', 'tag_key'] | packet.json holds both packet_text and the session id list |  |
| C-MX6 | S5 | HARD | PASS | packet.json byte-identical on re-run | re-mixing the same ranked yields the same packet_text |  |
| C-OC1 | S6 | HARD | PASS | {"llm_guard": true, "sources": ["gold"]} | the lab run uses --source gold; the LLM helper is not called in this mode |  |
| C-OC2 | S6 | HARD | PASS | outcome.py good vs gold rule good | gold outcome: packet ∩ useful non-empty -> good; non-empty packet, empty ∩ -> bad; empty p |  |
| C-OC3 | S6 | HARD | PASS | ["good"] | outcome ∈ {good, bad, unclear} only |  |
| C-OC4 | S6 | HARD | PASS | [["closed_at", "outcome", "packet_session_ids", "query_id", "source", "tag_key"]] | outcome row carries query_id, packet_session_ids, tag_key, outcome, source, closed_at |  |
| C-OC5 | S6 | HARD | PASS | --source llm exit code 2 | --source llm is guarded out in this pass (LAB-BRIEF §3); llm-mode rows never mix with gold |  |
| C-DELTA | S7 | HARD | PASS | changed non-packet rows: [] | delta and shows+=1 apply only to (packet session, query tag_key) pairs; other rows stand |  |
| C-UP1 | S7 | HARD | PASS | [] | good -> GOOD_DELTA, bad -> BAD_DELTA, unclear -> UNCLEAR_DELTA; the matching outcome count |  |
| C-UP2 | S7 | HARD | PASS | last_shown_at rows: [] | last_shown_at = outcome.closed_at |  |
| C-UP3 | S7 | HARD | PASS | {"shows": 5, "score": 0.9, "good": 1, "last_shown_at": "2026-08-01T12:00:00Z"} | fx-decay: when shows % DECAY_EVERY_SHOWS == 0 the score drops by DECAY_AMOUNT after the ou |  |
| C-UP4 | S7 | HARD | PASS | non-packet rows with delta/decay: [] | sessions outside the packet get neither delta nor decay |  |
| C-UP5 | S7 | HARD | PASS | second update over the same outcomes.jsonl applied nothing (ratings byte-identical) | update is idempotent per query_id (update_state.json); a second pass does not re-apply |  |
| C-FUTURE | replay | HARD | PASS | future candidates: [] (query closed_at 2026-08-01T12:00:00Z) | no session with closed_at >= query.closed_at in candidates/packet. The replay-order half ( | data-level check at S0; ordering verified statically in C-RP |
| C-RP1 | replay | HARD | PASS | {"own_logic_tokens": [], "steps_called": ["mix", "outcome", "rank", "retrieve", "tag", "up | replay.py has no own prompts/search/rank logic; it only calls the step scripts |  |
| C-RP2 | replay | HARD | PASS | {"candidates": 0, "ranked": 0, "packet_ids": [], "header_only": true} | an empty pool/early dialogues yield a valid empty packet — not an error |  |
| C-REPLAY | replay | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs runner + metrics.json (D4/D5); C-REPLAY closes when th |
| C-RP3 | replay | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | manifest.json with input/artifact shas is written by the run |
| C-EV1 | eval | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs eval.py class counting + a run (D4) |
| C-EV2 | eval | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs eval.py B0 arm (D4) |
| C-EV3 | eval | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs eval.py single scoring path (D4) |
| C-EV4 | eval | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs eval.py B1 --seed (D4) |
| C-EV5 | eval | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs eval.py per_query.jsonl + metrics.json (D4/D5) |
| C-EV6 | eval | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs corpus gold + audit.json (D3/S1) |
| C-EV7 | eval | SOFT | deferred | deferred at S0 | full contract closes at S1/D4/D5 | needs cost.json from a measured run (D5) |
| C-NC1 | control | HARD | PASS | {"candidates": 0, "ranked": 0, "packet_ids": [], "header_only": true} | empty pool -> all packets empty, no self-mix (B0==T closes with eval.py at D4) |  |
| C-NC2 | control | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | future-closed_at control needs the runner order (S1); C-FUTU |
| C-NC3 | control | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | gold_useful empty control needs eval.py T arm on corpus (D4/ |
| C-NC4 | control | HARD | deferred | deferred at S0 | full contract closes at S1/D4/D5 | TAG_FIELDS_MIN=5 control needs corpus pairs (S1) |
| C-NC5 | control | SOFT | deferred | deferred at S0 | full contract closes at S1/D4/D5 | EXPLORE_SLOTS=0 vs B2 needs eval.py (D4) |
| C-GD1 | D0 | HARD | PASS | # AGENT-LABELED GOLD — NOT HUMAN GOLD — labeler=deepseek-v4-pro | # prompt_sha=14e5d5c7921 | # header marking agent-labeled / NOT human gold + sha/created line |  |
| C-GD2 | D0 | HARD | PASS | future/unknown refs: [] | every useful id has closed_at strictly earlier than the query's |  |
| C-GD3 | D0 | HARD | PASS | hits: [] | no email / phone / >=10 digits / cvv / iban / ssn in gold output |  |
| C-GD4 | D0 | HARD | PASS | gold rows 60 vs slice 60; unique 60; extra [] | rows == 60 slice rows; query_id unique and ⊆ d0_slice.jsonl |  |
| C-GD5 | D0 | HARD | PASS | raw files 60 vs gold rows 60; missing [] | data/raw_gold_useful/ has one <query_id>.json per gold row |  |
| C-GD6 | D0 | SOFT | PASS | seed queries with opposite direction: [] | on the 6 seed rows the empty/non-empty direction matches the seed |  |
| C-GD7 | D0 | HARD | PASS | H1-signature rows 3/46 non-empty (['d-1151', 'd-1452', 'd-2385']); howto no-exclusion [] | <=20% of non-empty rows equal the whole same-guideline bucket; every FAQ how-to row exclud |  |
| C-GD8 | D0 | HARD | PASS | manifest model=deepseek-v4-pro labeler_default=deepseek-v4-pro S2_default=deepseek-v4-flas | labeler_model == deepseek-v4-pro; the S2 measured-loop model stays deepseek-v4-flash |  |
| C-REGISTRY | harness | HARD | PASS | rows 81, duplicate ids [], missing ids [] | every CHECKS.md id appears in checks.json exactly once (missing id = fail) |  |

## Deferred (needs runner/eval/corpus)

- C-REPLAY: needs runner + metrics.json (D4/D5); C-REPLAY closes when the runner appears (CHECKS.md)
- C-RP3: manifest.json with input/artifact shas is written by the runner (D5), not at S0
- C-EV1: needs eval.py class counting + a run (D4)
- C-EV2: needs eval.py B0 arm (D4)
- C-EV3: needs eval.py single scoring path (D4)
- C-EV4: needs eval.py B1 --seed (D4)
- C-EV5: needs eval.py per_query.jsonl + metrics.json (D4/D5)
- C-EV6: needs corpus gold + audit.json (D3/S1)
- C-NC2: future-closed_at control needs the runner order (S1); C-FUTURE data-level check runs at S0
- C-NC3: gold_useful empty control needs eval.py T arm on corpus (D4/S1)
- C-NC4: TAG_FIELDS_MIN=5 control needs corpus pairs (S1)

Аудит A1–A6 и вердикт §6.4 — на S1/S2, не на S0 (мало n).
