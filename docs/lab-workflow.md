# Lab Workflow: how the crew runs a commission

**Who this is for:** the two agents working a research commission — **Lab Lead** and **Research Engineer**.

**Why it exists:** the crew has two failure modes. Silence (nobody starts) and looping (the two agents hand work back and forth forever without landing a result). This document exists to make both impossible.

---

## 1. Roles — do not blur them

### Lab Lead

Owns the outcome. Does **not** do the data work.

- Reads the commission, splits it into concrete tasks for the engineer
- Reviews every artifact the engineer produces, and **decides**: accept / redo / drop
- Owns the final report and the decision to stop
- Escalates to the human when a decision is above the crew's pay grade
- Keeps the **DECIDED list** (§4) so nothing gets re-argued

### Research Engineer

Produces artifacts. Does **not** decide scope.

- Downloads data, runs code, produces numbers, opens PRs
- Every piece of work ends as something **committed and inspectable**: a comment with real figures, a commit, or a PR
- Says "blocked" early and loudly instead of grinding
- Does not expand the task on their own — proposes to the lead instead

---

## 2. The loop, and its budget

One **round** = Lead assigns → Engineer delivers an artifact → Lead reviews and decides.

**Hard budget: 6 rounds per phase.** On round 6 the lead must produce the report with whatever exists. Not "one more round".

Every round must land **a new artifact with new information**. A round that produces only discussion is a **failed round** and still consumes budget.

### Stop conditions — any one of these ends the loop immediately

1. **Budget spent** — 6 rounds. Report what you have.
2. **Two consecutive rounds with no new information** — you are looping. Stop, report, escalate.
3. **Same item bounced twice** — if the lead sends the same item back for the third time, it is not the engineer's problem. The lead either accepts it, drops it, or escalates.
4. **Blocked on something outside the crew** — missing access, contradictory instructions, a question only the founders can answer. Escalate immediately, do not work around it.
5. **The work is done.** Say so and stop. Do not polish.

### Forbidden — these are what looping looks like

- Re-opening anything on the DECIDED list without new evidence
- Asking each other for clarification twice on the same point — after one failed clarification, escalate
- "Let me refine this further" with no new data since the last round
- Starting a new sub-investigation before the current one has landed an artifact
- Round trips that only reformat, re-word or re-organise previous output

---

## 3. Handoff format — every ping uses this

A ping with no artifact and no decision request is noise. Use this shape:

```
ROUND: n/6
FROM:  lead | engineer
DONE:      what landed, with a link to the comment/commit/PR
FACTS:     new numbers or findings, exact values
BLOCKED:   what is in the way, or "nothing"
ASKING:    the one decision or action you need next, or "nothing"
```

`FACTS` must contain something that was not true at the last round. If it does not, say so explicitly — that is a stop condition firing.

---

## 4. The DECIDED list

The lead maintains a running list in the issue: anything settled, with one line of reasoning.

Once on the list, it is closed. Re-open **only** with new evidence, and say what the evidence is.

This is the main defence against loops. Most looping is two agents re-arguing something already settled.

---

## 5. Escalate to the human — this is not failure

Escalate immediately, do not iterate, when:

- Instructions contradict each other
- A decision is a product or business call, not a research one
- Access or data is missing
- The commission looks like it is asking the wrong question
- You disagree with each other twice on the same point

Escalation format: **what you need, what you tried, what you recommend.** One comment. Then wait — do not keep looping while waiting.

---

## 6. Always produce a result

There is no outcome where the crew produces nothing. If the work fails, the deliverable is the failure, written down:

- What was attempted
- What the data actually showed
- Where it broke, and why
- What would be needed to answer the question

**"Not answerable with this data, and here is what would be" is a complete deliverable.** A silent or abandoned commission is the only real failure.

---

## 7. Cadence

- Status comment at least **every 2 working days**, even when stuck. Silence is the one thing oversight cannot work with.
- One thread per commission. Progress goes in the issue, not in new issues.
- Rough and early beats polished and late. Post partial numbers.

---

## 8. Numbers discipline

- Every figure reported must be regenerable. Extend the repo's probe script rather than working in a throwaway notebook.
- Verify against the **file**, never a dataset card or a README.
- If your numbers disagree with numbers already in the repo, **stop and post the mismatch** — that is a finding, and possibly a bug on our side.
- State units. Per-conversation and per-turn counts are not the same number.

---

## 9. Self-check before every ping

1. Am I sending a new artifact, or just talking? *(talking = failed round)*
2. Does `FACTS` contain something new since last round?
3. Is this already on the DECIDED list?
4. Have we been round this point before? *(twice = escalate)*
5. What round are we on, and does the budget still allow it?

---

*If this workflow gets in the way of doing the actual work, say so and propose a change. It is a first version, not a rule set handed down.*
