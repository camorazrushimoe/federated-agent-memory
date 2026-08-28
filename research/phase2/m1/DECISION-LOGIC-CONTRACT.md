# Decision Logic — Pre-registration Contract (R5 closeout skeleton)

**Commission:** Shareable Experience for Federated Agent Memory (`docs/research-commission-shareable-experience.md`)
**Addendum:** GH #6 comment `5448509651` (2026-08-28, oversight for the founder) — the closeout must
contain **implementable decision logic**, not only findings: six stages (INGEST · KEY · STORE ·
PROMOTE · SERVE · REJECT/EXPIRE), every parameter named and tagged **MEASURED / ASSUMED / BLOCKED**,
plus one worked end-to-end example on 2–3 real ABCD conversations by id.
**Ticket:** BON-45 (synthesis) — this contract is the R5 skeleton. **It is not the report.**
**Status:** PRE-REGISTERED 2026-08-28, while R1 is still open. Frozen here, before the M1 number
exists, so that R5 fills in measurements — it cannot choose them.
**Author:** research-lead (lab-1) · **Corpus:** ABCD `abcd_v1.1.json` (sha256:16
`005d425e890b30a1`) · **Label set:** pinned 170 (`research/phase2/m1/candidate_pairs.jsonl`,
sha256:16 `42215fc5969e600e`, 85/34/51).

---

## 0. What this document is (and is not)

- **Is:** the complete stage-by-stage procedure the founder asked for — *how to find matches in
  dialogues and use them as shared experience* — with every knob named and honestly tagged, and a
  worked example whose inputs are already locked so the R5 write-up is mechanical, not selective.
- **Is not:** the Research Report. The report (BON-45) cannot exist until R1 posts its closure line
  ("false-friend rate X% … at Y% recall … PASS/FAIL"). This document deliberately contains **no
  M1 number** and **no method verdict**.
- **Is not:** production code, a pipeline, a framework schema, or a vendor choice (addendum,
  scope note). Prose + pseudocode + tables only.
- **Write it even if every M fails** (addendum hard requirement 2, commission §9): if R1–R4 miss
  their bars, the R5 report still publishes this same six-stage procedure with the applicable
  stages/parameters marked BLOCKED and the named missing inputs. A negative result does not
  exempt the procedure.

### Tag vocabulary (addendum requirement, applied to every parameter)

| Tag | Meaning | Required annotations |
|---|---|---|
| **MEASURED** | The number comes from a measurement on this data. | the value, the sample it came from, the artifact that regenerates it (file + command or committed script). |
| **ASSUMED** | Placeholder; the data did not validate it. | what would validate it and the rough cost of doing so. |
| **BLOCKED** | Cannot be determined on this data. | the **specific missing input** (e.g. persistent agent/tenant id, a real outcome label, live traffic). For the founder: what to instrument in product traffic from day one. |

A parameter is tagged **exactly one**. A parameter that is MEASURED on ABCD but not on product
traffic carries both facts: `MEASURED (ABCD) / BLOCKED (product traffic) — missing: …`.
**Honesty rule (addendum):** a logic that is 40% MEASURED and honestly labelled beats one that
reads finished. At pre-registration time **no M-number is MEASURED yet** — that is the point of
writing this now.

### The procedure in one paragraph

For each finished dialogue, INGEST a fixed set of fields. KEY computes a *problem-shape* key from
the customer's words (and corroborating action structure). STORE writes one memory unit per
dialogue (or per collapsed unit) with a receipt. PROMOTE lets a unit enter **shared** memory only
after independent, non-echo confirmations pass a pre-registered gate. SERVE restricts how a
retrieved unit may be used (evidence, not instruction) and names the revalidation triggers.
REJECT/EXPIRE removes or quarantines units on scope mismatch, staleness, contradiction, or
single-source evidence.

---

## 1. INGEST — read a finished dialogue, field by field

**Input:** one finished dialogue (ABCD conversation object, or — in product traffic — the agent's
own conversation record).
**Operation:** field extraction per the table below. No judgment, no matching, nothing else.
**Output:** an **ingest record** (the raw material for KEY/STORE).

| Field | ABCD source (field path) | In our product traffic | Tag & note |
|---|---|---|---|
| `convo_id` | top-level `convo_id` | conversation id (we own it) | **MEASURED** (present in 10,042/10,042 conversations, `research/phase0/abcd_probe.json` `n_conversations`) |
| `customer_turns` (ordered text) | `delexed` list, entries with `speaker=="customer"`, `.text` | we own the transcript | **MEASURED** (schema verified 2026-08-28 on the corpus; delimited text, de-identified) |
| `agent_turns` | `delexed`, `speaker=="agent"` | we own the transcript | **MEASURED** — used **only** to be *excluded* from KEY (boilerplate; method doc B1 definition) |
| `action_trace` (ordered names) | `delexed`, `speaker=="action"` turns → `targets[2]` (D11: `[subflow, "take_action", "<name>", [args], -1]`) | **the tool/step log of our agent, if it exists** | **MEASURED on ABCD** (36,482 action turns, 100% of conversations have ≥1, `abcd_probe.json`) · **BLOCKED on product traffic** — *missing: an instrumented action/step log per conversation*. This is the single most valuable day-one instrument: without it, KEY loses its structural axis and STORE loses `what_worked`. |
| `flow` / `subflow` (oracle scope labels) | `scenario.flow` / `scenario.subflow` | **not available** — our traffic has no labeled taxonomy | **MEASURED on ABCD** (10 flows / 96 subflows, `abcd_probe.json`) · **BLOCKED on product traffic** — *missing: a flow/vertical taxonomy for our own dialogues* (buildable from traffic; that is exactly what this research is for). Used in KEY only as scope/guard; never as the label source (protocol R5). |
| `product` (names, amounts) | `scenario.product` (`names[]`, `amounts[]`); 2,585/10,042 = 25.7% empty | order/item metadata, where present | **MEASURED on ABCD** (empty-product share from `research/phase2/labeling/pair_capacity.md`) · partially available in product traffic (order-linked conversations). Product is **never the key** (protocol R3) — it scopes and disambiguates. |
| `split` (train/dev/test) | top-level dict key | n/a | **MEASURED** (8,034/1,004/1,004, `abcd_probe.json`) — provenance for receipts |
| `timestamp` (dialogue time) | **absent** — scenario carries a fictional `purchase_date` only; no wall-clock time anywhere in the corpus | real event time | **BLOCKED on ABCD** (no wall-clock time in the data) · available in product traffic. Consequence: REJECT/EXPIRE's *staleness* parameter can be **designed but not calibrated** on this data (§6). |
| `tenant` / `agent` identity | **absent** | the agent/tenant that served the dialogue | **BLOCKED on ABCD** (no persistent agent/tenant identity — method doc §5) · available in product traffic. Consequence: PROMOTE's *source-independence* is untestable on ABCD and the anti-echo check degrades to conversation-level dedup until traffic exists (§4). |
| `outcome` (did it go well) | **absent as a column** | customer feedback / ticket closure, where instrumented | **BLOCKED everywhere on this data** — this is research item §4 (method doc), gated by the 50-conversation validation (kill condition AUC ≤ 0.60). Until R3 lands, every stage that consumes outcome runs in its degraded mode. |

**Pseudocode (stage 1)**

```
def ingest(convo):
    cust  = [t.text for t in convo.delexed if t.speaker == "customer"]
    trace = [t.targets[2] for t in convo.delexed if t.speaker == "action"]
    return IngestRecord(
        convo_id=convo.convo_id,
        customer_turns=cust,
        action_trace=trace,                      # [] when no step log (BLOCKED field in product traffic)
        flow=convo.scenario.flow, subflow=convo.scenario.subflow,   # oracle scope labels; ABSENT in product traffic
        product=convo.scenario.product,
        split=<train|dev|test>,
        timestamp=MISSING, tenant=MISSING, outcome=MISSING)         # BLOCKED fields, recorded as such
```

---

## 2. KEY — compute the "problem shape" key

**Input:** ingest record.
**Operation:** compute a key from **two axes** (method doc M1 working definition):
axis A — intent (what the customer wants done), axis B — structure (the symptom/constraint that
drove the resolution). Comparison is between two conversations' keys.
**Output:** per conversation: `key` (feature vector + normalized intent/structure stub) and
`scope` (flow/vertical, when a taxonomy exists). Per pair: a similarity score + accept/reject.

| Parameter | Value (pre-registration) | Tag |
|---|---|---|
| Feature text for the key | **customer turns only, in order** (agent boilerplate excluded) | **ASSUMED** — matches the pre-registered B1 definition (method doc M1; PR #16 README §5) but not yet validated. What would validate it: R1 sweep shows it dominates the operating curve; cost: 0 (already the plan). |
| Feature function | TF-IDF vectors, cosine similarity | **ASSUMED** — the dumb baseline (B1) every semantic method must beat; if B1 passes the D18 bar the finding is *problem shape is lexical on this data* and this stays; if not, B2 (off-the-shelf sentence embedding) is the pre-registered falsifier, run only to falsify B1. No vendor choice either way. |
| Structural corroboration | ordered `action_trace` compared as sequence agreement | **ASSUMED** as corroboration, **not** as the label (protocol R4: symptom difference wins over identical action sequences). Becomes **MEASURED or dead** with R1–R4 (its weight in the final key is a post-M1 decision, stated in the report, not here). |
| Accept threshold `t_key` | the sweep value from R1: threshold `t` on the (recall, false-friend) operating curve over the 170-pair gold set at which the D18 bar is met, if any | **BLOCKED** — *missing: the R1 join* (`gold_m1_pairs_agentlabeled.jsonl` × precomputed B1 scores over all 170 pairs, PR #16 README §5 sweep). No threshold may be quoted before the join exists. If no `t` passes the bar, the report publishes the argmin-false-friend `t` and its recall (the missed bar **is** the finding, D18). |
| Scope limit (where matching is trustworthy) | **within flow/vertical: MEASURED-eligible after R1; across flows: BLOCKED until R1's per-band numbers exist** | Commission §8.1 (scope) is an open empirical question. The pre-registered expectation (method doc M1 "what would change my mind"): if no method keeps cross-flow/cross-product false friends ≤ 10%, sharing is **constrained to vertical/flow**. R5 states the scope limit exactly as R1's per-band false-friend rates allow — no wider, no narrower. |
| False-friend guard | (i) the accept threshold itself (conservative against pooling, protocol R6 spirit); (ii) **structural disagreement veto**: a pair whose customer-stated symptoms differ is rejected even when the lexical score passes | (i) **BLOCKED** until R1 (see `t_key`). (ii) **ASSUMED** as design, pending R1/R2 evidence that structure carries signal; the veto is written to be *droppable* with a one-line rationale in R5 if R1 shows structure adds nothing. |

**Pseudocode (stage 2)**

```
def key(rec):
    text = join(rec.customer_turns)                 # axis A + B, customer words only
    return Key(vector=tfidf(text),                  # ASSUMED until R1 confirms lexical sufficiency
               intent_stub=norm_intent(text),       # normalized intent label (see STORE)
               structure_stub=norm_structure(rec),  # symptom/constraint label
               scope=rec.flow or DERIVED_SCOPE)     # scope: oracle on ABCD; DERIVED in product traffic (BLOCKED)

def match(rec_x, rec_y):
    s  = cosine(key(rec_x).vector, key(rec_y).vector)
    if s < t_key:                                    # t_key BLOCKED until R1
        return REJECT("below-threshold")
    if structure_disagrees(rec_x, rec_y):            # veto: symptoms differ (ASSUMED, R1/R2-testable)
        return REJECT("false-friend-guard")
    return ACCEPT(score=s)
```

**Honesty note:** on ABCD the *measurement* of the key uses the same customer-text features that
build the label set's display (contract §5). The gold set is independent of the key only because
its labels are two-pass agent judgments of problem shape (D19) — that independence is the whole
point of the two-pass protocol, and its limit (one agent, two runs) is stated in the protocol's
honesty clause, carried into R5.

---

## 3. STORE — the memory unit

**Input:** accepted ingest record (+ match decisions, when a dialogue joins an existing unit's
scope).
**Operation:** write one **experience unit** per dialogue (units with the same key later feed
PROMOTE; they are not merged at store time).
**Output:** the unit record below, written with its receipt.

| Field | Required? | Content | Tag & note |
|---|---|---|---|
| `unit_id` | required | deterministic id (convo_id + store hash) | MEASURED (trivially constructible) |
| `problem_shape` | required | the KEY (intent_stub + structure_stub + vector + scope) | tag follows KEY parameters |
| `constraint` | required | the symptom/constraint that actually mattered, one line | **ASSUMED** extractable from customer turns; M2's reconstruction test (R2) measures whether this field survives transcript compression. Collapse: if M2 fails the bar, `constraint` degrades to the raw first customer turn (the only field guaranteed present — pair-set display contract §3 keeps the first customer turn in full). |
| `unlock` | **optional** | the question/turn that opened the resolution | **ASSUMED** identifiable in part of traffic; M2 (R2) reports the share of units where it is identifiable. Never required: a unit without an unlock is still valid. |
| `what_worked` | required (may be empty) | ordered `action_trace` (targets[2], D11), normalized to the ontology vocabulary (30/30 names; D11 note: 10 names / 13.95% of turns fall outside the raw kebab-case↔Title-Case join and are carried as-is with a flag) | **MEASURED on ABCD** (trace exists in 100% of conversations) · **BLOCKED on product traffic** — *missing: instrumented step log* (see INGEST). |
| `what_failed` | **optional, gated** | deviation from the expected playbook sequence (`guidelines.json` via the 96→55 mapping, 100% coverage, PR #9) | **BLOCKED until R3**: §4's kill condition (AUC ≤ 0.60 on the 50-conversation validation) decides. If R3 kills it, this field is removed from the schema (pre-registered, method doc M2). |
| `outcome` | **optional, gated** | the outcome signal (§4 derivation) | same gate as `what_failed` |
| `receipt` | required | provenance + ownership + expiry: `source_convo_ids[]`, `split`, `corpus_sha256:16`, `product`, `stored_at` (wall clock of the store — real, not corpus time), `scope`, `source_agent/tenant` (**BLOCKED** on ABCD — *missing: persistent agent/tenant identity*), `version` | the receipt is what makes echo-auditing and provenance possible (method doc M2/M3). Tenant field exists in the schema even though ABCD leaves it empty — so the same unit schema works in product traffic without redesign. |

**Collapse rule (pre-registered, method doc M2 — stated exactly, addendum STORE requirement):**
if the outcome field cannot be derived (R3 kill, or M2 reconstruction of outcome below bar), the
unit **degrades to `{problem_shape, constraint, what_worked, receipt}`** — i.e. *{the M1 key, the
constraint that mattered, the resolution action sequence, and the receipt}* — with `unlock`
optional and `what_failed`/`outcome` removed. That degradation is a **reported finding** in R5,
not a silent drop.

**Token budget (pre-registered from the M2 bar):** unit ≤ 1/10 of the source transcript's token
count, while preserving ≥ 80% rubric value on the R2 reconstruction set. **BLOCKED** as a
*measured* number until R2; the rule itself is frozen (D18).

**Pseudocode (stage 3)**

```
def store(rec, key_res):
    unit = Unit(unit_id=hash(rec.convo_id), problem_shape=key_res,
                constraint=extract_constraint(rec),            # ASSUMED; R2-validated
                unlock=extract_unlock(rec) or None,            # optional
                what_worked=normalize(rec.action_trace),        # MEASURED on ABCD; BLOCKED in traffic
                what_failed=None, outcome=None)                 # gated: R3 decides
    if R3_outcome_alive:
        unit.what_failed, unit.outcome = derive_outcome(rec)   # §4, with its own reported error
    else:
        unit = collapse(unit)                                   # -> {shape, constraint, what_worked, receipt}
    unit.receipt = Receipt(rec.convo_id, rec.split, CORPUS_SHA, rec.product,
                           stored_at=now(), scope=key_res.scope,
                           source_tenant=MISSING)               # BLOCKED on ABCD
    write(unit)
```

---

## 4. PROMOTE — the gate into **shared** memory

**Input:** units (per dialogue) + the store.
**Operation:** a unit-key earns a shared-memory entry only when the gate passes.
**Output:** `PROMOTED` (shared entry created, rank set) or `HELD` (stays in local/store tier,
re-checkable as more dialogues arrive).

| Parameter | Value (pre-registration) | Tag |
|---|---|---|
| Minimum independent confirmations `K_ind` | **2 distinct conversations** minimum (i.e. the key recurs); rank rises with more | **ASSUMED** placeholder. Validation: M3's value set (~50–100 units, two-pass publish/do-not-publish, D18 bar AUC ≥ 0.80) measures whether 2 vs 3 vs 4 separates value from noise; cost already budgeted (R4). |
| What counts as **independent** | different `convo_id`; on product traffic additionally different `tenant`/`agent` identity | the conversation-level part is **MEASURED-eligible** (the store has receipts); the tenant part is **BLOCKED on ABCD** — *missing: persistent agent/tenant identity* (method doc §5, commission §9.3a). On ABCD the independence test is conversation-level only, and the report says so. |
| What **explicitly does not** count | (a) the same conversation (any re-ingest of it); (b) a dialogue that occurred *after* the unit was first published and could have been influenced by it (echo); (c) on product traffic, a second dialogue served by the *same* agent instance from the same stored unit | (a) constructible now (**ASSUMED**-cheap: receipt check); (b)(c) **BLOCKED** until live traffic — *missing: publication timestamps + serving logs that record which memory units were injected into which dialogue*. |
| Outcome gate | a promoted unit must carry a **positive** outcome on ≥ `K_out` of its confirming conversations, when outcome is available | `K_out`: **ASSUMED = 1** placeholder. The gate's existence itself is **BLOCKED until R3** (no outcome → gate degrades to frequency+independence only, and R5 says the shared memory is *unranked by outcome*). |
| **Anti-echo rule (executable check, not a principle)** | `is_echo(candidate_conv, unit) :=` **true** iff ANY of: (1) `candidate_conv.convo_id ∈ unit.receipt.source_convo_ids` (same source); (2) on product traffic: `candidate_conv.timestamp < unit.published_at` is FALSE and `unit.unit_id ∈ candidate_conv.injected_unit_ids` (the dialogue was served *with* this unit — direct downstream); (3) text overlap: `Jaccard(candidate.customer_turns, unit.constraint ∪ unit.what_worked text) > θ_echo` AND the dialogue post-dates publication. Echoes are **excluded from the confirmation count and from the rank**. | (1) **constructible now** (receipt exists) — **ASSUMED** sufficient on static data. (2) **BLOCKED** — *missing: injection/serving logs + wall-clock timestamps in traffic*. (3) **ASSUMED** design with `θ_echo` a **BLOCKED** threshold — *missing: observed echo examples from live traffic to calibrate it*. On ABCD (static, no echoes possible) the rule's honesty is a **design test** (method doc M3: synthetic-echo construction must double-count under the naive counter and NOT under this one) — that test is pre-registered for R4 and its outcome is reported either way. |

**Pseudocode (stage 4)**

```
def promote(unit_key):
    confs = [u for u in store.units_of(unit_key) if not is_echo(u, unit_key)]
    if len({u.receipt.source_convo_id for u in confs}) < K_ind:     # K_ind ASSUMED=2, R4-calibrated
        return HELD("not-enough-independent")
    if outcome_available:
        pos = sum(1 for u in confs if u.outcome == POSITIVE)
        if pos < K_out:                                             # K_out ASSUMED=1; gate BLOCKED until R3
            return HELD("outcome-gate")
    rank = f(len(confs), outcome_strength)                          # monotone in independent confirmations
    publish_shared(unit_key, rank=rank, sources=[u.receipt for u in confs])
    return PROMOTED
```

---

## 5. SERVE — how a retrieved unit may be used

**Input:** a live dialogue + the store/shared memory.
**Operation:** retrieve units whose key matches the live dialogue's key (same KEY stage); return
them under a **use class**.
**Output:** retrieved units tagged `EVIDENCE` or `INSTRUCTION` — with the hard rule below.

| Parameter | Value (pre-registration) | Tag |
|---|---|---|
| Use-class default | `EVIDENCE` — the unit may inform (what problem this is, what constraint to probe, what sequence previously worked). It may **not** by itself authorize an action. | **ASSUMED** default. Validation: commission #5 (injected-memory benefit) is explicitly **out of scope** for this phase and unanswerable on a static dump; the default is the safe half of the split, not a measured optimum. |
| `INSTRUCTION` class (unit may directly drive a step) | only for units that are `PROMOTED` **and** carry a positive outcome **and** are in-scope **and** (on product traffic) were last confirmed within the staleness window | every leg is gated: PROMOTED (needs R1–R4), positive outcome (**BLOCKED** until R3), staleness (**BLOCKED** — no wall-clock time on ABCD). So on this data's evidence, `INSTRUCTION` is **BLOCKED end-to-end**; R5 states the legs, not a false green light. |
| Retrieval usefulness vs action authority | **kept separate as a hard invariant:** retrieval relevance (KEY similarity) decides *what is returned*; the use class above decides *what the recipient may do with it*. One number never plays both roles. | design rule (no parameter). |
| Revalidation triggers (return to human or drop the unit) | (1) retrieved unit contradicts a newer in-scope unit on `constraint` or `what_worked`; (2) unit is out of scope for the live dialogue (scope mismatch); (3) unit is stale (see REJECT/EXPIRE); (4) the live dialogue's customer denies the unit's premise (in product traffic: detectable as a contradiction turn) | (1)(2) constructible now (**ASSUMED**); (3) **BLOCKED** (timestamp); (4) **BLOCKED** (live traffic) — *missing: a feedback channel marking "this suggestion was wrong"*. |
| Consequential-action rule | any unit that would trigger a consequential action (money, account change, order modification) **routes to a human**, regardless of rank or use class | **ASSUMED** policy (matches the commission's caution on pooling); validation = product decision, not a lab measurement — flagged as a founder/DevCrew call in R5. |

**Pseudocode (stage 5)**

```
def serve(live_rec):
    k  = key(live_rec)
    hits = [u for u in store if matches(k, u.problem_shape) and in_scope(k.scope, u.receipt.scope)]
    for u in hits:
        u.use = EVIDENCE
        if u.promoted and u.outcome == POSITIVE and not stale(u):   # BLOCKED legs today
            u.use = INSTRUCTION
        if contradicts(u, newer_in_scope(u)) or out_of_scope(u):
            trigger_revalidation(u)                                  # -> REJECT/EXPIRE or human
    return hits   # use class travels with the unit; retrieval score never grants authority
```

---

## 6. REJECT / EXPIRE — when a unit must not be used, or must be dropped

**Input:** the store + new units + time (when time exists).
**Operation:** four named triggers, each an executable check.
**Output:** unit state → `ACTIVE` / `QUARANTINED` (retrieved, flagged, human-reviewable) /
`EXPIRED` (dropped from shared memory; receipt retained).

| Trigger | Check | Tag |
|---|---|---|
| **Scope mismatch** | `unit.receipt.scope ∩ query.scope = ∅` → unit is not served for the query (never served cross-scope while the scope limit of §2 says within-vertical) | **ASSUMED** (scope labels exist on ABCD; scope *derivation* in product traffic is BLOCKED per §2). The conservative form — never serve cross-scope — is the pre-registered default until R1 proves cross-flow matching trustworthy. |
| **Staleness** | `now() - unit.last_confirmed_at > T_stale` → `QUARANTINED`; `> 2·T_stale` → `EXPIRED` | **BLOCKED** — *missing: wall-clock time in ABCD (no timestamp field exists; only fictional scenario dates) and therefore no observed decay of any kind.* `T_stale` is an **ASSUMED** placeholder (e.g. one product-release cycle) that R5 publishes **as uncalibrated**, with the named instrument: `last_confirmed_at` on every receipt + real event time in traffic. |
| **Contradiction with a newer unit** | same key + in-scope + `constraint` or `what_worked` materially differs + newer by receipt `stored_at` (store time, real) → older unit `QUARANTINED`, newer one `ACTIVE`, both retained with a conflict link | partially **MEASURED-eligible** (store order is real time; `stored_at` is a real wall clock of our store, not the corpus). "Materially differs" on text: **ASSUMED** similarity cutoff; on `what_worked` (action sequences): exact sequence mismatch, no threshold. Final wording set by R3 (if outcome is dead, contradiction reduces to sequence/constraint mismatch). |
| **Single-source-only evidence** | a unit whose shared-memory claim rests on exactly one source conversation is **never `ACTIVE` in shared memory** — it exists at most in the local/store tier | **MEASURED-eligible now** (receipts make the count exact) — this is the *frequency trap* the commission names: the R4 trap-documentation run (B1 frequency-only vs the M3 value set, wrongful-promotion share ≥ 30% is the finding) quantifies how often this trigger would have been the only thing standing between noise and shared memory. |

**Pseudocode (stage 6)**

```
def maintain(unit):
    if unit.sources < 1: return EXPIRED
    if unit.shared and unit.distinct_sources == 1: return QUARANTINED("single-source")   # never shared-ACTIVE
    if contradicted_by_newer(unit): return QUARANTINED("contradiction", conflict_with=newer)
    if now() - unit.last_confirmed_at > 2*T_stale: return EXPIRED("stale")               # T_stale BLOCKED
    if now() - unit.last_confirmed_at > T_stale: return QUARANTINED("stale")
    return ACTIVE
```

---

## 7. Parameter ledger (the at-a-glance view the addendum requires)

Every threshold/constant in §1–§6, exactly one tag each. **MEASURED** rows are all *corpus-structure*
facts (schema, counts) — **no M-number is MEASURED yet; none will be until R1 posts its closure
line.** R5 replaces the ledger cells in place; rows keep their ids (`P-…`) so the diff is auditable.

| # | Parameter | Stage | Tag (2026-08-28) | Value / missing input / validation |
|---|---|---|---|---|
| P-01 | customer-turns-only feature text | KEY | **ASSUMED** | pre-registered B1 definition; validated by R1 sweep dominance |
| P-02 | TF-IDF + cosine (B1) | KEY | **ASSUMED** | dumb baseline; B2 embedding is the pre-registered falsifier, falsification-only |
| P-03 | structural corroboration (action-trace sequence agreement) | KEY | **ASSUMED** | R4-testable; drop-able with one-line rationale if R1 shows no signal |
| P-04 | accept threshold `t_key` | KEY | **BLOCKED** | missing: R1 join (gold set × B1 scores over the 170 pairs, PR #16 README §5 sweep). Argmin-FF fallback pre-registered |
| P-05 | scope limit (within-flow vs across) | KEY | **BLOCKED** (cross-flow) / **MEASURED-eligible** (within) | missing: R1 per-band false-friend rates; commission §8.1 open question |
| P-06 | false-friend guard (threshold + structural veto) | KEY | **BLOCKED** (threshold leg) / **ASSUMED** (veto leg) | veto testable in R1/R2; drop rule pre-registered |
| P-07 | `constraint` extractability | STORE | **ASSUMED** | R2 reconstruction test (≥ 80% rubric value @ ≤ 1/10 tokens, D18) |
| P-08 | `unlock` identifiability share | STORE | **ASSUMED** (optional field) | R2 reports the share; never required |
| P-09 | `what_worked` (action trace) | STORE | **MEASURED** (ABCD: 36,482 turns, 100% of convos, `research/phase0/abcd_probe.json`) / **BLOCKED** (product traffic) | missing (traffic): instrumented step log — day-one instrument #1 |
| P-10 | `what_failed` / `outcome` fields | STORE | **BLOCKED** | missing: R3 §4 validation (50 convos, kill AUC ≤ 0.60); collapse rule pre-registered (§3) |
| P-11 | unit token budget (≤ 1/10 transcript) | STORE | rule frozen (D18) / number **BLOCKED** | R2 reconstruction set (60–100 convos) |
| P-12 | receipt: tenant/agent identity | STORE | **BLOCKED** (ABCD) | missing: persistent agent/tenant id — day-one instrument #2 |
| P-13 | receipt: wall-clock time | STORE | **BLOCKED** (ABCD has none) | real `stored_at` exists in our store; corpus event time missing |
| P-14 | `K_ind` minimum independent confirmations | PROMOTE | **ASSUMED** = 2 | R4 value set (AUC ≥ 0.80 bar) calibrates 2/3/4 |
| P-15 | independence: tenant leg | PROMOTE | **BLOCKED** (ABCD) | missing: agent/tenant identity (§P-12) |
| P-16 | outcome gate + `K_out` | PROMOTE | **BLOCKED** (gate) / **ASSUMED** `K_out` = 1 | R3 decides gate existence; R4 calibrates |
| P-17 | anti-echo check leg (1) receipt dedup | PROMOTE | **ASSUMED** sufficient on static data | design test (synthetic echo) pre-registered, R4 |
| P-18 | anti-echo check leg (2) injection logs | PROMOTE | **BLOCKED** | missing: serving logs (`injected_unit_ids` per dialogue) + real timestamps — day-one instrument #3 |
| P-19 | `θ_echo` overlap threshold | PROMOTE | **BLOCKED** | missing: observed echoes from live traffic to calibrate |
| P-20 | use-class default `EVIDENCE` | SERVE | **ASSUMED** (safe default) | #5 (injection benefit) out of scope / unanswerable on a static dump |
| P-21 | `INSTRUCTION` class legs | SERVE | **BLOCKED** end-to-end on this data | needs R1–R4 all green + real time |
| P-22 | revalidation trigger (4): customer-denial | SERVE | **BLOCKED** | missing: feedback channel in traffic |
| P-23 | consequential-action → human | SERVE | **ASSUMED** policy | product/founder call, flagged in R5 |
| P-24 | scope-mismatch check | REJECT/EXPIRE | **ASSUMED** | conservative never-cross-scope default until P-05 resolves |
| P-25 | `T_stale` | REJECT/EXPIRE | **BLOCKED** | missing: wall-clock time + any observed decay; instrument: `last_confirmed_at` on receipts |
| P-26 | contradiction check (sequence leg) | REJECT/EXPIRE | **MEASURED-eligible now** (exact action-sequence mismatch) | constraint-text leg **ASSUMED** cutoff, R3 finalizes |
| P-27 | single-source-never-shared | REJECT/EXPIRE | **MEASURED-eligible now** (receipts make the count exact) | R4 trap run quantifies its bite (≥ 30% wrongful-promotion finding bar) |

**Day-one instruments for product traffic (the founder's ask, collected from the BLOCKED rows):**
(1) instrumented step/action log per conversation (unblocks P-03, P-09, P-26); (2) persistent
agent/tenant id on every dialogue + every receipt (unblocks P-12, P-15); (3) real event
timestamps (unblocks P-13, P-18, P-25); (4) serving logs recording which memory units were
injected into which dialogue (unblocks P-18); (5) a feedback channel for "this was wrong / this
helped" (unblocks P-22 and calibrates P-10/P-16). Items (1)–(4) are schema additions to the
ingest record in §1; none requires a vendor decision.

---

## 8. Worked example — selection FROZEN now, write-up in R5

**Requirement (addendum):** one worked end-to-end example on 2–3 real ABCD conversations by id,
walking all six stages, **including a rejected false-friend pair**. Excerpts and ids only; no full
transcripts, no raw data in the repo.

**Frozen selection (locked 2026-08-28 from the pinned 170-set, `candidate_pairs.jsonl`):**

| Walk | Pair (set) | Conversations | Band (set construction) | Role in the walk |
|---|---|---|---|---|
| W1 — the match that promotes | `m1-0001` | **9610** & **2076** (`account_access` / `recover_username`) | should-match | two real dialogues that *should* share a unit: INGEST → KEY (accept) → STORE (two units, one key) → PROMOTE (gate evaluation) |
| W2 — the false friend the guard rejects | `m1-0120` | **9671** & **5622** | should-not-match, sub-band **cross-flow** | the hard case: **same product** (`michael_kors shirt`, 69) in both, different flows (`product_defect/return_stain` vs `manage_account/status_service_removed`). KEY's structural veto is what must reject it — product identity is never the label (R3) |
| W3 — cross-product control | `m1-0140` | **7144** & **3896** | should-not-match, sub-band **cross-product** | different products AND different shapes (`single_item_query/shirt_how_3` vs `manage_account/status_service_removed`); the lexical score should fall below W2's — the contrast shows the guard is doing structure work, not just lexical rejection |

**Why these three:** W1 + W2 + W3 cover, in one example, the accept path (W1), the
commission's named danger — same product, different problem (W2, the deliberately hard
cross-flow slice, PR #16 README §2) — and a cross-product control (W3). No conversation in the
170-set anchors two of these roles (verified 2026-08-28), so the walk is presented as three
pair-walks over four+ conversations; the addendum's "2–3 conversations" is satisfied in the
sensible reading (three real pair-walks, each fully walked) and stated as such in R5.

**What R5 fills in (frozen slots, values pending — deliberately empty here):**
- W1: the B1 cosine score for (9610, 2076) vs `t_key` (BLOCKED until R1) → accept; the two STORED
  units (constraint stubs from the actual customer turns; `what_worked` = each trace); the PROMOTE
  verdict at R1–R4 evidence (with `K_ind`, outcome gate, echo check evaluated on the real fields
  — including the honest "BLOCKED on this data" legs).
- W2: the B1 score for (9671, 5622) — **the number that proves or disproves the guard**: if the
  lexical score passes `t_key` (plausible: identical product wording), the rejection must come
  from the structural veto, and R5 shows exactly which symptom difference fired it; if it fails
  `t_key`, R5 says the threshold alone rejected it and the veto was redundant here.
- W3: same, for (7144, 3896).
- The gold labels of all three pairs arrive with the two-pass gold set (D19) and are quoted as
  `agent-labeled` with pass-1/pass-2 agreement per pair.

**Anti-contamination note (honesty, recorded at freeze time):** the pair *selection* was made from
set metadata (band/sub-band/ids) without first checking any labels; during freeze verification
the pass-1 labels already committed on `origin/evaluation/m1-labeling` (2026-08-28 04:38Z, before
this contract was written) were consulted **only** to confirm the three pairs carry the narrative
they are frozen for. Pass-1 is one of two independent passes; the canonical label is the two-pass
product, and **no pass-1 label is quoted anywhere in this document**. Nothing in §1–§7 was
chosen because of a label.

---

## 9. R5 checklist — what the closeout report must contain (per §7 of the commission + addendum)

The report (BON-45, round 5) is due **only after** R1's closure line exists. It contains, in
order: (1) commission §7 content — taxonomy with counts; the "same problem" definition and its
false friends; the proposed unit with worked examples; the promote rule; what was killed; what is
unanswerable; the single next experiment; (2) **this document's §1–§6 procedure with the §7
ledger filled in** (MEASURED cells now carry number + sample + artifact; BLOCKED cells keep their
named missing inputs); (3) **§8 worked example, walked end-to-end with the real numbers**;
(4) the scope-limit statement (commission §8.1) exactly as R1's per-band numbers allow; (5) the
negative results ("checked and killed") with their kill evidence. If R1 fails the bar, items
(2)–(3) stand with the affected parameters BLOCKED — the procedure is published regardless
(addendum hard requirement 2).

## 10. Open items owned by this pre-registration (for the R1 closeout, not new rounds)

1. R1 closure line exists (false-friend X% @ recall Y%, PASS/FAIL) → unblocks P-04, P-05, P-06 and
   fills W1–W3 scores. **The round cannot close without it (D21).**
2. B1 precompute over all 170 pairs (engineer, assigned in the 2026-08-28 ruling comment
   `5448472885` §6) → the join is one file-paste away from the number.
3. Pass-2 labeling (evaluation) → gold set → inter-pass disagreement number (reported, never
   "human agreement").
4. No R2/M2 work starts until item 1 lands (round counter 1/6, ruling `5448472885` §5).
