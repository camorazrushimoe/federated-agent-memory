# M2 results (R2) — the join

**Round:** R2 (M2 extraction) · join per GH #6 `5449115746` s4 item 4 (frozen contract). Created 2026-08-28 by `join_m2.py`.

**Question:** does the structured experience record (B2) preserve >= 80% of the
transcript's rubric value at <= 1/10 of its token count? (frozen D18 bar; collapse rule
pre-registered: if B1 (the action trace) alone reaches >= 80%, the unit collapses to
trace + label.)

## 1. Inputs (pinned, verified by sha256:16 at join time)

| input | sha256:16 | state |
|---|---|---|
| `candidates.jsonl` (B0/B1 renders + FILLED B2 unit + frozen token counts) | `a54f52a557ce38b5` | R2 fix-forward (5450060638), supersedes PR #22 @601c310 |
| `b2_draft.jsonl` (the 80 B2 units) | `5063a85c4ab79465` | PR #23, main @d8a8f33 |
| `sample.jsonl` (frozen 80-convo sample) | `f2195e7a6abe2221` | PR #21 (D22) |
| blind pass1 answers | `62ad3fe9b8b7c09c` | evaluation, 240 items |
| blind pass2 answers | `4ddcffb8a86b805f` | evaluation, 240 items |
| reference answers (scoring Call 1) | `bc23e6af7412daeb` | evaluation, 80 rows |
| scoring answers (scoring Call 2) | `61acca99c66c8427` | evaluation, 80 rows |

`n_tokens_b2` was recomputed on each draft unit with the frozen counter
(whitespace-split of `json.dumps(unit)`, default separators) — 80/80 equal to the draft's
stored value (gate 5 of the join); the committed `b2_unit` equals the pinned draft's
unit on all 80 rows (gate 2, FILLED mode — slot, never mutate).

## 2. The frozen bar (never tuned — D18)

- **Per convo:** value(B2) >= 0.8 x value(B0) **AND** tokens(B2) <= tokens(B0)/10.
- **Round passes iff** >= 70% of the 80 convos meet the per-convo criterion **AND** the
  aggregate token ratio sum(tokens(B2))/sum(tokens(B0)) <= 0.1.
- value(candidate) = (s1+s2+s3)/3 under the frozen scoring rubric; B0 is scored under
  identical treatment — the ceiling's value is MEASURED, not assumed 1.0.

### The token half — structural finding (frozen schema, reported not negotiated)

The empty-unit schema floor is **23 tokens** under the frozen counter. Per-convo, the
floor exceeds `tokens(B0)/10` on **61/80** convos (median B0 187 -> allowance
18.7; only a unit with its judgment fields hollowed could pass those, and the draft passes
0/80). The other 19/80 convos' allowances reach the floor (max B0 417 -> 41.7),
but the **aggregate-ratio floor** — the empty unit on all 80 rows — is 23x80/15340 = **0.1199 > 0.1**,
so round criterion 2 (aggregate ratio <= 0.1) fails **no matter how the units are drafted**. The
token half is unreachable as a pass of the round — a property of frozen schema + counter +
sample, independent of drafting effort. **The value half is the judge's measurement; the token
half reports as this structural finding.** A missed bar is the finding (D18) — the bar
was not negotiated after seeing results.

*Doc corrections (arithmetic slips in B2-DRAFT-NOTES.md s2 / lead 5449935167 s3, measured from the
pinned rows at join; both leave the structural finding unchanged): (1) the quoted 'B0 sum 13,396' is
off — the measured B0 sum over the 80 pinned rows is **15340** (candidates/sample meta total: 15340);
the aggregate floor is 0.1199 (vs 0.137 from the slipped total). (2) 'exceeds tokens(B0)/10 for
all 80 convos' is the AGGREGATE floor's property — per-convo the floor exceeds the allowance on
61/80, not all 80. Both floors exceed 0.1; a pass requires BOTH halves.*

## 3. Per-convo table (80 rows; value = (s1+s2+s3)/3; tokens = frozen counter)

| convo_id | flow | subflow | tok B0/B1/B2 | value B0/B1/B2 | per-convo bar |
|---|---|---|---|---|---|
| 116 | subscription_inquiry | status_questions | 417/3/45 | 1.000 / 0.083 / 0.500 | FAIL (v no, t no) |
| 274 | order_issue | status_delivery_date | 253/3/45 | 1.000 / 0.083 / 0.583 | FAIL (v no, t no) |
| 345 | single_item_query | boots_other_3 | 207/3/47 | 1.000 / 0.083 / 0.583 | FAIL (v no, t no) |
| 374 | manage_account | manage_change_name | 285/5/57 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 429 | shipping_issue | cost | 206/4/44 | 1.000 / 0.167 / 0.500 | FAIL (v no, t no) |
| 455 | order_issue | status_delivery_time | 242/4/43 | 1.000 / 0.167 / 0.833 | FAIL (v ok, t no) |
| 581 | manage_account | manage_payment_method | 267/8/57 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 605 | shipping_issue | status | 269/6/47 | 1.000 / 0.167 / 0.833 | FAIL (v ok, t no) |
| 678 | purchase_dispute | mistimed_billing_never_bought | 197/4/44 | 1.000 / 0.500 / 0.833 | FAIL (v ok, t no) |
| 755 | storewide_query | policy_3 | 94/2/45 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 778 | product_defect | refund_initiate | 232/5/47 | 1.000 / 0.083 / 0.833 | FAIL (v ok, t no) |
| 921 | manage_account | manage_change_phone | 194/3/43 | 1.000 / 0.500 / 0.833 | FAIL (v ok, t no) |
| 1224 | single_item_query | boots_how_1 | 350/6/45 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 1328 | troubleshoot_site | credit_card | 259/6/53 | 1.000 / 0.250 / 0.667 | FAIL (v no, t no) |
| 2154 | purchase_dispute | promo_code_invalid | 177/3/44 | 1.000 / 0.083 / 0.667 | FAIL (v no, t no) |
| 2212 | subscription_inquiry | manage_dispute_bill | 157/4/42 | 1.000 / 0.167 / 0.500 | FAIL (v no, t no) |
| 2410 | manage_account | status_credit_missing | 187/4/52 | 1.000 / 0.083 / 0.667 | FAIL (v no, t no) |
| 2639 | subscription_inquiry | manage_dispute_bill | 188/3/47 | 1.000 / 0.083 / 0.833 | FAIL (v ok, t no) |
| 2695 | subscription_inquiry | status_due_date | 186/4/48 | 1.000 / 0.167 / 0.333 | FAIL (v no, t no) |
| 2782 | shipping_issue | manage | 179/4/46 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 2856 | product_defect | refund_initiate | 186/4/50 | 1.000 / 0.167 / 0.500 | FAIL (v no, t no) |
| 2969 | troubleshoot_site | slow_speed | 230/4/41 | 1.000 / 0.083 / 0.667 | FAIL (v no, t no) |
| 3092 | storewide_query | policy_1 | 216/3/49 | 1.000 / 0.083 / 0.583 | FAIL (v no, t no) |
| 3161 | manage_account | manage_change_address | 398/7/51 | 1.000 / 0.083 / 0.500 | FAIL (v no, t no) |
| 3167 | troubleshoot_site | slow_speed | 173/2/45 | 1.000 / 0.083 / 0.583 | FAIL (v no, t no) |
| 3411 | purchase_dispute | mistimed_billing_already_returned | 245/3/44 | 1.000 / 0.333 / 0.833 | FAIL (v ok, t no) |
| 3539 | product_defect | return_color | 268/5/56 | 1.000 / 0.333 / 0.500 | FAIL (v no, t no) |
| 3650 | storewide_query | membership_1 | 181/2/43 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 3658 | troubleshoot_site | shopping_cart | 111/2/51 | 1.000 / 0.500 / 0.667 | FAIL (v no, t no) |
| 4158 | manage_account | status_service_added | 160/3/42 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 4265 | shipping_issue | missing | 235/5/45 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 4332 | product_defect | return_size | 262/3/45 | 1.000 / 0.083 / 0.583 | FAIL (v no, t no) |
| 4416 | storewide_query | policy_2 | 139/2/47 | 1.000 / 0.083 / 0.667 | FAIL (v no, t no) |
| 4697 | subscription_inquiry | manage_extension | 157/4/49 | 1.000 / 0.167 / 0.833 | FAIL (v ok, t no) |
| 4894 | troubleshoot_site | search_results | 219/3/51 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 5059 | troubleshoot_site | search_results | 205/4/51 | 1.000 / 0.083 / 0.583 | FAIL (v no, t no) |
| 5111 | storewide_query | membership_2 | 139/5/43 | 1.000 / 0.167 / 1.000 | FAIL (v ok, t no) |
| 5157 | product_defect | refund_status | 120/2/39 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 5365 | troubleshoot_site | shopping_cart | 221/2/51 | 1.000 / 0.083 / 0.667 | FAIL (v no, t no) |
| 5386 | account_access | recover_password | 169/4/53 | 1.000 / 0.083 / 0.833 | FAIL (v ok, t no) |
| 5424 | single_item_query | boots_how_2 | 189/2/43 | 1.000 / 0.500 / 0.833 | FAIL (v ok, t no) |
| 5544 | account_access | recover_username | 119/2/38 | 1.000 / 0.250 / 0.583 | FAIL (v no, t no) |
| 5640 | single_item_query | boots_other_4 | 166/3/42 | 1.000 / 0.083 / 0.333 | FAIL (v no, t no) |
| 5687 | purchase_dispute | bad_price_yesterday | 199/3/42 | 1.000 / 0.083 / 0.750 | FAIL (v no, t no) |
| 5716 | account_access | recover_username | 109/2/37 | 1.000 / 0.333 / 0.500 | FAIL (v no, t no) |
| 5989 | order_issue | manage_downgrade | 153/2/43 | 1.000 / 0.083 / 0.750 | FAIL (v no, t no) |
| 6026 | order_issue | status_payment_method | 211/4/41 | 1.000 / 0.500 / 0.500 | FAIL (v no, t no) |
| 6028 | account_access | recover_password | 165/3/44 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 6121 | storewide_query | membership_4 | 116/3/43 | 1.000 / 0.083 / 0.500 | FAIL (v no, t no) |
| 6517 | shipping_issue | missing | 222/5/47 | 1.000 / 0.167 / 0.500 | FAIL (v no, t no) |
| 6629 | account_access | reset_2fa | 220/3/48 | 1.000 / 0.083 / 0.833 | FAIL (v ok, t no) |
| 6902 | shipping_issue | manage | 249/4/45 | 1.000 / 0.167 / 0.833 | FAIL (v ok, t no) |
| 7053 | purchase_dispute | promo_code_out_of_date | 221/5/52 | 1.000 / 0.167 / 0.833 | FAIL (v ok, t no) |
| 7061 | subscription_inquiry | status_due_amount | 207/5/56 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 7079 | single_item_query | boots_other_2 | 105/3/41 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 7523 | order_issue | manage_upgrade | 134/4/45 | 1.000 / 0.167 / 0.500 | FAIL (v no, t no) |
| 7534 | product_defect | refund_update | 65/1/40 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 7608 | single_item_query | boots_how_4 | 177/3/45 | 1.000 / 0.083 / 0.250 | FAIL (v no, t no) |
| 7666 | manage_account | status_shipping_question | 139/3/46 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 7861 | account_access | recover_password | 176/3/49 | 1.000 / 0.167 / 0.833 | FAIL (v ok, t no) |
| 7933 | storewide_query | membership_3 | 149/2/43 | 1.000 / 0.417 / 0.583 | FAIL (v no, t no) |
| 7961 | order_issue | manage_create | 201/3/44 | 1.000 / 0.083 / 0.833 | FAIL (v ok, t no) |
| 8300 | manage_account | status_service_removed | 149/3/44 | 1.000 / 0.083 / 0.333 | FAIL (v no, t no) |
| 8363 | account_access | reset_2fa | 165/3/52 | 1.000 / 0.167 / 0.833 | FAIL (v ok, t no) |
| 8538 | product_defect | return_stain | 206/5/47 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 8725 | storewide_query | policy_4 | 144/3/41 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 8806 | product_defect | refund_status | 97/2/38 | 1.000 / 0.500 / 0.667 | FAIL (v no, t no) |
| 8890 | purchase_dispute | out_of_stock_general | 247/3/46 | 1.000 / 0.500 / 0.833 | FAIL (v ok, t no) |
| 8974 | purchase_dispute | out_of_stock_one_item | 140/3/41 | 1.000 / 0.167 / 0.500 | FAIL (v no, t no) |
| 9142 | subscription_inquiry | manage_pay_bill | 134/5/55 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 9321 | single_item_query | boots_how_3 | 174/3/45 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 9451 | purchase_dispute | bad_price_competitor | 164/3/41 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 9468 | account_access | recover_username | 86/2/37 | 1.000 / 0.417 / 0.833 | FAIL (v ok, t no) |
| 9472 | order_issue | manage_cancel | 187/6/48 | 1.000 / 0.083 / 0.417 | FAIL (v no, t no) |
| 9707 | single_item_query | boots_other_1 | 102/3/39 | 1.000 / 0.083 / 0.500 | FAIL (v no, t no) |
| 9816 | order_issue | status_mystery_fee | 196/5/49 | 1.000 / 0.333 / 0.500 | FAIL (v no, t no) |
| 9847 | troubleshoot_site | credit_card | 190/3/49 | 1.000 / 0.083 / 0.833 | FAIL (v ok, t no) |
| 9953 | shipping_issue | cost | 254/4/46 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 9968 | shipping_issue | status | 156/4/45 | 1.000 / 0.167 / 0.667 | FAIL (v no, t no) |
| 10059 | subscription_inquiry | manage_extension | 277/5/43 | 1.000 / 0.500 / 0.833 | FAIL (v ok, t no) |

- per-convo bar: **0/80** (value half 21/80; token half 0/80 — structural).
- aggregates: tokens B0/B1/B2 = 15340/286/3667; ratio B1/B0 = 0.0186; ratio B2/B0 = 0.239.
- mean value: B0 1.0000 / B1 0.1771 / B2 0.6219.

## 4. Round verdict (frozen bar)

**ROUND FAILS the frozen bar: per-convo bar 0/80 = 0.0% (criterion: >= 70%); aggregate token ratio 0.239 (criterion: <= 0.1). Value half met by 21/80; token half met by 0/80 (structural finding, see structural_token_half).**

## 5. B1-vs-B2 falsification outcome

B1 (action trace, scored identically): value-half share **0/80 = 0**, token-half share 80/80 = 1.

**NO COLLAPSE — B1 (action trace) meets the 0.8 value bar on only 0/80 convos (< 70%); NEITHER candidate carries >= 80% of B0's value on the mean — the unit's value claim is not met (a finding, D18) (adjudicated per lead 5449935167 s4 on the measured numbers)**

## 6. Per-field loss ledger (what is lost per field when the transcript drops)

Loss = mean over the 80 convos of score(field, B0) - score(field, candidate).

| field | B2 vs B0 (n convos w/ loss, total/80, mean) | B1 vs B0 (n, total/80, mean) |
|---|---|---|
| Q1 problem (intent + structure) | 51, 25.5/80, 0.31875 | 80, 76.0/80, 0.95 |
| Q2 binding constraint | 37, 20.5/80, 0.25625 | 78, 71.0/80, 0.8875 |
| Q3 what worked (in order) | 78, 44.75/80, 0.559375 | 80, 50.5/80, 0.63125 |
| value = (s1+s2+s3)/3 | 79, 30.25/80, 0.3781 | 80, 65.8333/80, 0.8229 |

## 7. Two-pass agreement (blind answering passes)

**472/720 = 0.655556** of item-questions agree across passes (exact string match after lowercasing + whitespace collapse, per (item, question), between blind pass 1 and pass 2 (both passes blind, fresh staged context, different order — PROTOCOL-m2-blind.md)); per-convo all-questions-agree 0/80; items with all 3 questions agreeing 82/240.

DISAGREEMENT > 15%: per the frozen protocol, a 20-item sample goes to the founder (never the whole set).

> self-consistency floor, NOT human inter-rater agreement.

## 8. Vocab guard (note for the report — so the D11 record does not resurface)

`what_worked` uses the canonical 30-name ontology vocab. Vs that vocab the measured value
on this corpus is **0/30 unmapped** (286/286 sample action turns; guard intact, never
fired on this corpus). The R1-era '10 unmapped' was vs guidelines.json Title-Case button
names — a different denominator. **0 is the number.**

## 9. Honesty clause (rides with every number in this report)

> All M2 numbers are AGENT-JUDGED (blind answering passes 1+2 + the scoring pass in the frozen two-call structure — reference call, then scoring call against the committed reference; frozen protocols). The two-pass agreement is a judge self-consistency floor under frozen rules, NOT human inter-rater agreement, and is never cited as 'human agreement'. The B2 units are AGENT-DRAFTED (lead); the falsification is the independent blind judge.

## 10. Re-run contract

See `README.md` in this directory: pinned inputs verified by sha on every run; the join
is one command, deterministic, and a pure function of the judge files (recorded by sha).
