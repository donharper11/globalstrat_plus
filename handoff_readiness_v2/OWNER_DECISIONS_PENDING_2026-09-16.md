# Decisions pending with the competition owner / PI — 2026-09-16

> ## THIS DOCUMENT CONTAINS NO DECISIONS AND NO RULINGS.
>
> It is a **briefing**. Every "option" below is an option, not a
> recommendation adopted, and nothing here disposes of any finding. No
> sentence in this file may be cited as a decision, an acceptance, or an
> approval — including by the builder who wrote it.
>
> **A ruling exists only in an `OWNER_RULINGS_<date>.md` document, dated and
> attributed to the competition owner, and nowhere else.** That rule is R19,
> issued because it had already been broken once: an "owner accepted this
> risk" sentence recorded only in builder-authored files (V2-048) turned out
> never to have been given, and it was concealing an open P0.
>
> This document exists to make each decision cheap and safe to make. It does
> not make any of them.

Prepared against `crv2-release-integration` at `08cfda5` (the code is unchanged
from `3c99d74`; the later commit adds one planning document), reading the code
and the live competition database rather than the register. Where the register
and the code disagree, the disagreement is stated, not smoothed over.

**Read alongside `specs/PLAN-LAUNCH-AND-BUILD-SEQUENCE-2026-09-16.md`**, which
landed while this was being drafted and names this document at `:144-146`. Its
Phase 1 item 1.4 is "owner rulings on the findings that are blocked on a
decision" — that is what the list below enumerates. Its item 1.2 adds one this
briefing did not originally carry; it is included as **D14a**. Its deadline for
D1 agrees with the one derived independently here: V2-117 must be answered
**before any cohort submits**.

---

## What is actually pending

| # | Decision | Blocks competition launch? |
|---|---|---|
| D1 | What a student's communication mark is worth, now that the marking model has changed | **No** — but it becomes irreversible the first time a cohort submits |
| D2 | Whether the dormant `research_budget` bucket should count against a team's cash at all | **No** — measured: it changes no live answer today |
| D3 | Whether switching organisational structure should charge cash at click time, outside the engine | **No for the shipped scenarios** — measured: the cost is $0 in every structure a team can currently hold. **Yes if any scenario ships a non-zero one** |
| D4 | What market research reports should cost, and whether two of the six are worth selling | **No** — deferred calibration by R23. One narrow sub-question is worth settling first |
| D5 | Whether `scenario_rd_spend_target` survives as a fail-closed guard with no consumer | **No for the three shipped scenarios** — but it will refuse to score any new scenario that omits the key |
| D6 | Whether a firm that earns no revenue in a round should have its **accumulated** performance index destroyed, or merely be ranked below every firm that competed | **Closest to yes of anything here.** It is unbounded, permanent, and can decide a finishing order on one round |
| D7 | Whether missing a free, one-click customs form should cost a team an entire round of trading | **Worth ruling before launch** — 53.6% chance of firing at least once in a ten-round game, on the builder's figure |
| D8–D14a | Eight further items — paid-research rules R23 did not reach, starter-profile spread and tie-breaks, cohort-cap residue, cross-scenario reference prices, one governance ratification, the new advisory-layer plan, the live shared credential (**D14a**), one ops judgement call | Mixed; see each. **D14a sits in the launch-readiness phase** |

### Two items the register still shows as "awaiting a rules-owner ruling" that are already ruled

**They are not in the table above and are not for decision here.** See
"Already ruled — the register rows are stale" at the end of this document.

- **V2-064** (the 409 lock scope) was ruled by **R17** on 2026-09-12.
- **V2-066** (audit record for a refused student write) was ruled and **closed**
  by **R21** on 2026-09-12.

Both are now engineering work, or done. Neither is an owner decision.

---

## D1 — What is a student's communication mark worth?

### The question, in the owner's terms

A team writes an investor letter, a crisis statement, a memo to employees. An
AI marker reads it and that mark becomes part of the team's coherence score.
The marker was swapped on 2026-09-16 and the new one **marks lower**. Should
the marking be re-tuned so a good letter earns what it used to, or is the new,
harsher scale simply the scale?

Registered as **V2-117**. `TeamCommunication` is empty — verified against the
live database, 0 rows — so **no student has ever been marked**, and whatever is
decided, no published mark becomes inconsistent. That stops being true the
first time a cohort submits.

### What is true today, verified in code

**The scoring chain, end to end:**

| Step | Where | What it does |
|---|---|---|
| Model choice | `backend/core/engine/llm_runner.py:42` | `'communication_eval': 'tutor'` — the local fleet alias |
| Override | `llm_runner.py:54-61`, `globalstrat/settings.py:296-301` | `LLM_PURPOSE_MODELS` JSON env var overrides any purpose without a code edit |
| The call | `backend/core/rag/communication_eval.py:196-209` | `temperature=0.2`, `max_tokens=1500` |
| The mark | `communication_eval.py:41-43` | `coherence_contribution = overall_score × assignment.coherence_weight × 100` |
| The sum | `backend/core/engine/coherence.py:266-284` | All non-draft submissions up to this round, summed, capped at 100 |
| The blend | `coherence.py:165-169` | Phase 1 runs `skip_rag=True`, so `blended = 0.90 × formula + 0.10 × comm_score` |

**The authored weights.** Five assignments exist in the live database, all on
Consumer Electronics 2026 (scenario 7), four of them mandatory:

| Code | `coherence_weight` | Word limit | Mandatory |
|---|---:|---:|---|
| `expansion_memo_r2` | 0.05 | 300 | yes |
| `investor_letter_r4` | 0.05 | 300 | yes |
| `employee_message_r6` | 0.05 | 250 | yes |
| `final_review_r8` | 0.08 | 400 | yes |
| `crisis_statement` | 0.03 | 200 | no |
| **total** | **0.26** | | |

The same five weights are authored identically in all three scenario YAMLs
(`backend/scenarios/*.yaml`); only Consumer Electronics is loaded into the live
database.

### What was measured, and by whom

The model comparison is the builder's, recorded in commit `da8631e` and
summarised in `communication_eval.py:178-190`: 8 prompts built by the
platform's own prompt code, each scored twice by each model, 2026-09-16.

| | mean score (0–1) | self-consistency | latency |
|---|---:|---:|---:|
| `qwen-max` (retired) | 0.218 | ±0.036 | 11.4s |
| `tutor` (in force) | 0.129 | ±0.014 | 7.2s |

Its stated caveat stands: the eight test texts run ~50 words against a 300–400
word limit, so every model scored low; the **gap** is the evidence, not the
absolute values.

### What this briefing measured, because the size of the effect was not on the record

Given the authored weights above, the arithmetic of the blend is:

| Quantity | Value |
|---|---|
| Maximum possible `comm_score` (all five assignments, perfect 1.0) | **26.0**, not 100 |
| `comm_score` for a team scoring the `qwen-max` mean on all five | 0.218 × 26 = **5.67** |
| `comm_score` for a team scoring the `tutor` mean on all five | 0.129 × 26 = **3.35** |
| **Effect of the model change on the graded 0–100 blended score** | 0.10 × (5.67 − 3.35) = **0.23 points** |

Live coherence rows for scale: 448 `RoundResultCoherence` rows,
`formula_score` min 50, median 50, max 95.

**So the model change, on its own, is worth about a quarter of one point out of
100, uniformly, with no effect on ranking.** That is the decision as registered.

Three facts that were not on the record, which change what the decision is
about. They are presented as measurement, not as a finding to be dispositioned
here:

1. **Submitting a communication currently lowers a team's coherence score.**
   The blend at `coherence.py:165-169` takes 10% from `comm_score` — but only
   `if comm_score_val > 0`; a team that submits nothing keeps `formula_score`
   whole (`:168-169`). Because `comm_score` maxes at 26 while `formula_score`
   runs to 100, any team whose formula score exceeds ~26 is **worse off for
   submitting**:

   | `formula_score` | Blended, no submission | Blended, all five at the `tutor` mean | Cost of submitting |
   |---:|---:|---:|---:|
   | 50 (live median) | 50.00 | 45.34 | **−4.66** |
   | 95 (live max) | 95.00 | 85.84 | **−9.16** |

   That is **20 to 40 times** the 0.23-point model change. The code's own
   comment at `coherence.py:281-283` says the contribution is "already on a
   0-100ish scale", which would be true only if the weights summed to 1.0;
   they sum to 0.26.

2. **The two questions are coupled.** Raising `coherence_weight` is one of the
   three options on the table, and it is also the lever that closes the gap in
   (1). Weights summing to 1.0 would make `comm_score` a genuine 0–100 scale —
   and would simultaneously multiply the model gap from 0.23 to about
   **0.9 points** (0.09 × 1.0 × 100 × 0.10). Whichever way the marking scale is
   set, it sets both.

3. **A gateway outage marks more generously than either model.** If the
   gateway is unreachable, `communication_eval.py:36-38` falls back to
   `_fallback_evaluation`, which scores `0.4 + 0.3 × length_score`
   (`:228-235`) — a range of **0.40 to 0.70**, three to five times the `tutor`
   mean of 0.129. Worth up to 1.49 blended points, about **6× the model
   change**. Scoring is one-shot and synchronous at submit
   (`core/views/cc32a_views.py:195-196`); there is **no re-evaluation path
   anywhere in the backend** (verified by search), and `TeamCommunication` is
   unique on `(game, team, round, assignment)`, so a fallback mark is
   permanent. The docstring at `communication_eval.py:188-189` names this
   ("which changes marks — so a failure here must stay visible"); the only
   visibility today is a `logger.error` and the fallback text stored in the
   evaluation JSON.

### The realistic options

**Option A — accept the new scale as the baseline.**
*For students:* nothing changes from what they would have experienced anyway;
no mark exists to be inconsistent with. *Work implied:* none.
*Cost if deferred past launch:* none for the model change itself. But the
submit-penalty in (1) ships as-is, and the first cohort's marks are then the
precedent.

**Option B — adjust `coherence_weight`.**
*For students:* directly changes how much a letter is worth. Raising the
weights toward a sum of 1.0 also removes the submit-penalty measured above;
leaving them at 0.26 keeps it. *Work implied:* scenario data only — five values
in each of three YAMLs, `coherence_weight` at `consumer_electronics_2026.yaml:7423,
7474, 7528, 7576, 7623` and the matching lines in the other two — plus a reload.
No code change. *Cost if deferred:* low while the table is empty; after the
first cohort submits, changing it retroactively re-marks published work.

**Option C — adjust the rubric.**
*For students:* the marker is told to mark differently; the same letter earns a
different score. *Work implied:* the rubric is two places —
`assignment.evaluation_criteria` (authored per assignment, scenario data) and
the prompt in `build_evaluation_prompt` (`communication_eval.py:55-127`) plus
the system message at `:200-204`. Changing the prompt is a code change inside a
scored path and would want re-measurement against the same 8 prompts.
*Cost if deferred:* same as B.

**Option D — change nothing now and re-measure against real student writing.**
*For students:* nothing, until the first cohort is marked. *Work implied:*
run the same twice-each comparison against genuine 300–400-word submissions,
which the current 8-prompt sample explicitly does not represent. *Cost if
deferred:* the first cohort is the sample.

These are not exclusive: B and C both set the scale; D sets when.

### What would have to be measured to answer it

- **Already measured:** the model gap (0.09, ±0.014 vs ±0.036, 7.2s vs 11.4s);
  the authored weights; the arithmetic effect on the blended score (0.23
  points); live `formula_score` distribution; that no student has ever been
  marked.
- **Not measured, and it is the material gap:** how either model scores a
  *real* 300–400-word submission. Every number on the record comes from ~50-word
  texts. Cheap to obtain — the prompt builder and both model aliases are live —
  but it needs 8–10 realistic student texts, which do not exist yet.

### Does it block launch?

**No.** The platform resolves rounds, the mark is computed, and nothing is
broken. The decision can be taken after launch **only while
`TeamCommunication` stays empty**; the first submission by a real cohort makes
it retroactive. If the first competition round includes `expansion_memo_r2`
(round 2, mandatory), that is when the window closes.

---

## D2 — Should a research budget a team cannot set still count against its cash?

### The question, in the owner's terms

A team's "committed spend" figure — the number that decides whether a decision
is affordable — includes a research budget line. No screen shows that line, no
student can set it, and the engine never charges it. Should it be in the
affordability sum at all?

Registered as the residual of **V2-057**, after **R23** answered the larger
question it was originally asked inside ("is research free?" — no, and paid
research shipped at `d2059e4`).

### What is true today, verified in code — and the register is not quite right

| Claim | Verified? | Evidence |
|---|---|---|
| `research_budget` counts toward committed spend | **Yes** | `backend/core/services/rd_costs.py:313-314` puts it in `lines`; `:349-350` puts it in `budget_total`; `:356-357` puts `budget_total` into `committed`; `:366` `within_cash` compares `committed` to cash |
| The API cannot write it | **Yes** | `backend/core/serializers/decisions.py:216-220` — the field list is `rd_budget`, `marketing_budget`, `strategy_budget` only. `backend/core/views/decisions.py:459` routes every `budget` write through that serializer, and it is the only such route |
| The engine never charges it | **Yes** | No reference to `research_budget` anywhere under `backend/core/engine/`. What the engine charges is `research_expense`, which reads purchase rows (`costs.py:589`, `services/funding_need.py:161`) |
| It "feeds coherence scoring" | **No — this is wrong** | See below |

**The discrepancy.** R23 records that `research_budget` "remains a
**declaration**, like `marketing_budget` and `strategy_budget` — it feeds
coherence scoring and is not a second cash gate." The register repeats this in
V2-057's status update, and `rd_costs.py:329-332` repeats it again in a code
comment.

In the code, both halves of that sentence are the wrong way round:

- **Coherence does not read it.** `backend/core/engine/coherence.py:446`:
  `total_allocated = float(ba.rd_budget + ba.marketing_budget + ba.strategy_budget)`.
  `research_budget` is absent. It feeds nothing in the coherence score.
- **It is the only live cash effect the field has.** Via
  `rd_costs.py:349-357` it reduces the cash headroom every affordability check
  computes — which is what "a second cash gate" describes.

This is stated as a fact about the code, not as a claim that R23 was wrong.
R23 may have intended the behaviour the code should have; what is on the record
is that the code does not currently do it. **Reconciling the two is not a
builder's call and is not made here.** It is worth noting which way it cuts:
`marketing_budget` and `strategy_budget` *also* enter `budget_total` and are
also never charged from the budget line (the engine charges
`marketing_expense` from actual marketing rows, `costs.py:484`, and
`strategy_expense` from actual decisions, `costs.py:489-568`). So on the "budgets
declare, decisions spend" reading, `research_budget` is being treated
*consistently* with its two siblings in the cash check — and *inconsistently*
with them in coherence, where the other two are read and it is not.

### What was measured against the live database

24 of 67 `DecisionBudgetAllocation` rows carry a non-zero `research_budget`,
totalling **$12,000,000**. All 24 are round 1, all exactly **$500,000**, and
all originate from seeded data — `backend/core/management/commands/load_demo.py:454`
is one of only two places in the tree that writes the field (the other is
`run_cc31i_test.py:295`). No student wrote any of them, consistent with the
field being unwritable through the API.

**The decisive number:** re-running `budget_assessment` over all 24 rows and
comparing the affordability answer with and without the `research_budget` line:

> **0 of 24 rows change their affordability answer.**

Every one is `within_cash=True` either way, with 2.6× to 7.5× headroom
(committed $6.0M–$10.0M against cash $26.8M–$44.8M). The field is dormant in
both senses: nothing writes it in play, and where it has a value it changes
nothing.

### The realistic options

**Option A — remove `research_budget` from the committed sum.**
*For students:* nothing visible; no live answer changes (measured: 0 of 24).
*Work implied:* two lines in `rd_costs.py` (`:313-314`, `:349-350`), and the
test that pins the current behaviour,
`test_rd_costs.AuthoritativePriceTests.test_budget_vs_cash_rule_agrees_on_lock_summary_and_finance_context`.
*Cost if deferred:* a field nobody can set continues to consume cash headroom
it was not meant to consume, in a rule V2-037/V2-038 consolidated precisely so
that one rule exists.

**Option B — leave it in the committed sum and make it settable.**
*For students:* a fourth budget line appears that they can declare, and it is
counted like the other three. *Work implied:* serializer field, validation,
warning, frontend budget bar, both locales. *Cost if deferred:* none — nothing
is broken today.

**Option C — leave it exactly as it is.**
*For students:* nothing. *Work implied:* none. *Cost if deferred:* nil in play;
the cost is that the register, R23 and the code go on disagreeing about what
the field does, which is the condition that produces the next wrong citation.

**Option D — add it to coherence's `total_allocated`, making R23's sentence
true in code.** *For students:* a declared research budget would count toward
the overspend test that scores fiscal discipline (`coherence.py:459-475`).
*Work implied:* one line at `coherence.py:446` — but it is **inside the Phase-1
determinism boundary**, so per R18's standard it needs a focused replay
regression, not only a unit test. *Cost if deferred:* none today, because
nothing can set the field.

### What is measured and what is not

- **Measured:** every claim in the table above, from the code; the 24 live rows
  and their zero effect on affordability; that the field is unwritable through
  the only write route.
- **Not measured, and not measurable today:** what a team would actually
  declare if the field were settable (Option B) — there is no data, because the
  surface has never existed.

### Does it block launch?

**No.** Measured, not asserted: the field changes no affordability answer in
any live row, and no student can set it. It can ship undecided. What should not
ship undecided is the *documentation*: R23, the register and the code comment
all say it feeds coherence, and it does not.

---

## D3 — Should switching organisational structure take the money immediately?

### The question, in the owner's terms

A team switches from a centralised to a matrix structure. The cash leaves its
balance sheet the moment it clicks — but every spending figure the team is
shown, and every figure the instructor sees, ignores it. If the instructor then
reopens the round, the money does not come back, while the decision that paid
for it can be changed again. Should that charge move into the engine with every
other cost, or stay immediate and be added to the calculators?

Registered as **V2-088**, P1, explicitly "awaiting a rules-owner decision, not
repaired".

### What is true today, verified in code

The register's account is **accurate in every particular I checked**:

- The charge is at request time: `backend/core/views/cc32b_views.py:142-149` —
  a sufficiency check at `:142-143`, then `team.cash_on_hand -= new_structure.transition_cost;
  team.save()` at `:148-149`.
- **No calculator knows.** `transition_cost` appears in exactly five places in
  the backend: `cc32b_views.py` (`:73`, `:142`, `:143`, `:145`, `:148`, `:166`),
  the model (`core/models/cc32b_models.py:71`), its migration
  (`core/migrations/0031_cc32b_org_design.py:37`), and the scenario loader
  (`core/management/commands/load_scenario.py:1247`). It is in no engine module,
  not in `rd_costs.budget_assessment`, not in `funding_need.decision_outlays`,
  and not in `views/decisions.py`.
- **Nothing restores it.** `core/engine/advance_round.py`,
  `core/views/round_control.py` and `core/services/lifecycle.py` contain **no
  `cash_on_hand` write at all** (verified by search on this branch), so
  reopening a round leaves the money gone.
- What is sound about the path is also as recorded: the view is
  `OrgStructureContextView(CompetitionDecisionWriteMixin, APIView)`
  (`cc32b_views.py:19`) with `permission_classes = [IsTeamMember, IsCurrentRoundOpen]`
  and `throttle_scope = 'decision_write'` (`:169-170`); it writes
  `record_decision_event(..., 'change_org_structure', request.data)` at
  `:159-161`; and `Team` is a hashed manifest section
  (`core/services/manifest_sections.py:288`, excluding only
  `withdrawal_reason`), so `cash_on_hand` is inside the certified envelope, as
  is `team_org_structure` (`:482`).

### What was measured against the live database

| | |
|---|---|
| Organisational structure types loaded | 4: Centralized **$0**, Networked **$1,000,000**, Regional **$1,500,000**, Matrix **$2,500,000** |
| Teams in the database | 296 |
| Teams **not** on Centralized | **0** |
| Teams mid-transition | **0** |
| `change_org_structure` audit events, all games, all time | **0** |
| Audit actions that do exist | `save` (867), `deadline_lock` (134), `missing_submission_defaulted` (58) |
| Team cash, live | min −$2.5M, median $50.0M, max $69.8M |

**The defect has never fired.** Not once, in 24 games and 264 rounds. Every
team sits on the one structure whose `transition_cost` is $0, so the charge at
`:148` has never executed. Against median cash the largest switch would be
**5.0%** ($2.5M of $50M) — material, not ruinous.

### The realistic options

**Option A — move the charge into the engine at resolution.**
*For students:* the cost appears in committed spend and projected cash like
every other outlay, and reopening a round un-does it along with the decision.
*Work implied:* the largest of the three — the decision must be persisted as a
decision row rather than applied at click time, then charged in `costs.py` and
totalled in `funding_need.decision_outlays` (the one-calculator pair R23 names
explicitly). Inside the determinism boundary, so it needs a replay regression.
*Cost if deferred past launch:* nil while every shipped structure costs $0.

**Option B — keep the immediate charge and join it to the calculators.**
*For students:* the money still leaves at click time, but the figures they are
shown agree with their cash. *Work implied:* smaller — add the charge to
`budget_assessment` and `decision_outlays` and surface it. *Does not fix
irreversibility:* a reopened round still leaves the cash spent.
*Cost if deferred:* as A.

**Option C — leave it, and do not author a non-zero `transition_cost`.**
*For students:* nothing, because no team can reach a priced structure.
*Work implied:* none, plus a standing constraint on scenario authoring.
*Cost if deferred:* the constraint is invisible — nothing in the code or the
scenario files warns an author that pricing a structure activates an unbudgeted,
irreversible cash path. R28 has already opened new scenario authoring.

**Option D — ship with the three shipped structures priced at $0.**
A narrower form of C: change the authored data rather than the code, so the
three non-zero values in all three YAMLs
(`consumer_electronics_2026.yaml:7665, 7686, 7707` and the matching lines in
`clean_energy_tech_2026.yaml` and `media_entertainment_2026.yaml`) become $0
until the mechanic is repaired. *For students:* structure switching becomes
free — a rules change, and a real one.

### What is measured and what is not

- **Measured:** every code claim above; that the path has never executed;
  the authored costs; live cash distribution.
- **Not measured:** how often teams would switch if the structures were priced.
  There is no data, because no team has ever switched. It could be obtained
  only by running the mechanic.

### Does it block launch?

**Not for the shipped scenarios, as the database stands** — measured: all 296
teams are on the $0 structure and the charge has never executed. It becomes a
launch blocker the moment any competition scenario makes a non-zero structure
reachable, because then a team can spend money no figure shows and no reopen
returns. **Whoever authors or loads the competition scenario needs to know
that**, which is why the shape of the decision matters more than its urgency.

---

## D4 — What should market research cost, and are all six items worth selling?

### The question, in the owner's terms

Six research products are now on sale — five reports and an analyst query — and
all six cost the same $50,000 placeholder. What should each really cost? And
two of them are thin: the channels report is a fixed constants table with no
scenario or competitive data in it, and the products report is mostly the
team's own file read back. Should they be priced low, enriched, or given away?

R23 deferred **only the final prices** ("costs can always be calibrated and
fine-tuned later") and the owner recorded report prices as explicitly open at
the close of 2026-09-12. The content question is registered as **V2-089**
(channels) and **V2-090** (products), both P2, both "recommendation on the
record, not applied".

### What is true today, verified in code and in the live database

| | |
|---|---|
| Purchasable items | 5 reports + analyst query (`backend/core/services/research_catalogue.py:33-38`) |
| Market-scoped reports | `segments`, `channels` — bought per market (`research_catalogue.py:41`) |
| Markets in the live scenario | 5 — NA, APAC, EU, AFR, LATAM |
| Authored price, every item, live DB | **$50,000** — all six config keys confirmed against scenario 7 |
| `max_research_queries_per_round`, live | **5** |
| Purchases made, all games, all time | **0** (`DecisionResearchPurchase` is empty) |
| Team cash, live | median **$50.0M** |

**Maximum research spend available to one team in one round, at the placeholder
price:** 5 markets × segments + 5 markets × channels + 3 whole-game reports +
5 analyst queries = **$900,000**, or about **1.8% of median team cash** per
round, up to roughly **18% over a ten-round game**. That is the size of the
lever being deferred.

**A fourth question inside the same area, which the register does not carry.**
`research_catalogue.py:15-21` records its own open point: `DEFAULT_RESEARCH_PRICE`
(`:55`) is a $50,000 fallback used when a scenario does not author a price key,
and the docstring says "whether this should instead be fail-closed is a
rules-owner question". Every shipped scenario authors all six keys, so it never
fires today — but it is the difference between a mis-authored scenario
*refusing to sell* and *silently selling at $50,000*. It is the same shape of
choice as D5 and is cheaper to settle than the price list.

**Note on V2-094, which is not an owner decision.** A team is charged for an
analyst query without being shown the price beforehand — up to $250,000 per
team per round unseen. That is registered as P1 engineering work ("needs either
a catalogue endpoint or the price folded into an existing analyst payload"),
not a rules question. It is listed here only because its severity depends on the
price set: at $50,000 a query it is a P1; at $0 it would not exist.

### The realistic options

On prices:

**Option A — ship at the uniform $50,000 placeholder.**
*For students:* every report costs the same, so the choice of what to buy
carries no cost signal — a thin report costs exactly what the best one does.
*Work implied:* none. *Cost if deferred:* the first competition is the
calibration run, and its teams play a priced mechanic that has never been
priced.

**Option B — set a real price list before launch.**
*For students:* research becomes a genuine trade-off. *Work implied:* **data
only, in every case** — six keys per scenario YAML plus a reload. R23 made this
a deliberate property of the design ("calibration is later a data change and
never a code change"), and `research_catalogue.py:11-13` confirms the prices are
read through `get_config`. No code change, no redeploy.
*Cost if deferred:* prices can still be changed later, but not retroactively for
a round already resolved — `funding_need.py:150-154` reads the purchase rows, so
a resolved round keeps the price it charged.

On the two thin reports (V2-089, V2-090):

**Option C — price them low or at zero** (the builder's recommendation, on the
record and deliberately not applied). *Work implied:* data only, same as B.

**Option D — enrich them before charging.** *For students:* the channels report
would carry real per-market channel economics rather than the constants table
at `backend/core/views/research_reports.py:454-522`. *Work implied:* real
engineering, in the report generator and possibly in scenario authoring.
*Cost if deferred:* a team pays $50,000 for a rules explainer.

**Option E — withdraw them from the catalogue.** *Work implied:* code, since
`REPORT_TYPES` (`research_catalogue.py:34`) is a code constant, not scenario
data — so this is the one option in D4 that is not a data change.

### What is measured and what is not

- **Measured:** the live prices, query cap, market count, purchase count (zero),
  team cash, and therefore the per-round and per-game ceiling.
- **Not measured, and it is the whole question:** what a report is *worth* to a
  team — which cannot be measured before a cohort plays with it priced. That is
  a judgement about pedagogy, which is why R23 left it with the owner.
- **Cheaply measurable if wanted:** the actual content of each of the six
  reports, by reading `core/views/research_reports.py`. V2-089 and V2-090 record
  that assessment for two of the six; the other four have not been assessed the
  same way on the record.

### Does it block launch?

**No** — R23 already settled that a uniform placeholder is acceptable and that
calibration is a later data change. The register is right that this is deferred
calibration and not an open defect. Two smaller things inside it are worth a
look before launch rather than after: the `DEFAULT_RESEARCH_PRICE` fallback
question above, and whether the two thin reports should carry the same price as
the other four on day one.

---

## D5 — Should `scenario_rd_spend_target` survive?

### The question, in the owner's terms

A scenario must declare an "R&D spend target" or the platform refuses to score
the round at all. Nothing uses the number any more — the rule that divided by it
was retired by R10. Should the requirement stay, or go?

Recorded by the owner as explicitly open at the close of 2026-09-12
(`OWNER_RULINGS_2026-09-12.md:446`), and flagged again by the standing-red-tests
builder, who left it untouched rather than decide it.

### What is true today, verified in code

- `backend/core/engine/performance.py:44-60` — `scenario_rd_spend_target` reads
  config key `rd_spend_target` (`:39`) and **raises
  `InvalidScenarioConfiguration` when it is unauthored**. Its own docstring
  states the position plainly: "R10 / V2-053 removed the term that divided by
  this, so nothing scores against it now… It is now an orphaned requirement,
  recorded as such for the owner."
- `performance.py:293` still calls it, with the comment "Fails closed: a
  scenario without a usable target is not scored at all" — so the call survives
  purely as a precondition. Its return value is assigned and not used in any
  score.
- All three shipped scenarios author it: `rd_spend_target: '2000000'` at line 84
  of each of `consumer_electronics_2026.yaml`, `clean_energy_tech_2026.yaml` and
  `media_entertainment_2026.yaml`. Confirmed live: scenario 7 returns
  `rd_spend_target = 2000000.0`.

### The realistic options

**Option A — keep the guard.** *For students:* nothing.
*Work implied:* none. *Cost if deferred:* a new scenario that omits one
otherwise-unused key fails to score its rounds, and the error names a
"strategic capability" that no longer depends on it — a confusing failure at the
worst moment. R28 has opened new scenario authoring, which is exactly when a key
like this gets missed.

**Option B — retire the requirement.** *For students:* nothing.
*Work implied:* remove the call at `performance.py:293` and the function; two
test modules assert the current behaviour
(`core/tests/test_scoring_dispositions.py`, `core/tests/test_rd_scoring_retired.py`),
and two evidence harnesses import it. Inside the Phase-1 determinism boundary,
so R18's replay standard applies. *Cost if deferred:* none in play.

**Option C — keep it and give it a consumer again.** A rules decision to
reintroduce an R&D-spend term into scoring. Not a cleanup; a new rule.

### What is measured

Everything above is verified in code and against the live scenario config.
Nothing further needs measuring — this is a judgement about what a fail-closed
guard with no consumer is for, not a question about data.

### Does it block launch?

**No.** All three shipped scenarios author the key, so nothing can fail today.
It ships undecided safely. It becomes live the first time someone authors a
scenario without reading this.

---

## D6 — Should a firm that sold nothing this round lose the standing it built over the whole game?

### The question, in the owner's terms

A team is frozen out of its markets for a round — it sells nothing. It clearly
should not finish above teams that traded. Today the platform does more than
that: it **overwrites the team's accumulated performance index** with a number
just below the worst active firm's, permanently, and the team carries that
number forward for the rest of the game. Should "must not outrank" mean
*ranked below*, or *index destroyed*?

Raised, with options and measurements, in
`handoff_readiness_v2/completion/ZERO_PRODUCTION_DEFECT_2026-09-12.md:350-449`.
The builder is explicit at `:443-445`: **"changing the guard is a scoring-rule
change and belongs to the rules owner."** It is **not registered as a numbered
finding** and does not appear in `V2_FINDINGS_REGISTER.md`, which is why it is
easy to miss.

### What is true today, verified in code

`backend/core/engine/performance.py:261-279`:

```python
ceiling = max(D('0'), min(active_indexes) - D('0.01'))
for item in candidates:
    if item['commercially_inactive'] and item['new_index'] >= min(active_indexes):
        item['new_index'] = ceiling
        item['guard_applied'] = True
```

- It is applied at `:362`, after the composite is computed.
- The rewritten value is written straight to the carried state:
  `team.performance_index = new_index` at `:374`. It is not a one-round
  deduction; it is the team's standing from then on.
- **It is unbounded.** The size of the loss is the distance between the team's
  own index and the worst active firm's, so the better the team was doing and
  the wider the field, the more it loses. The builder measured up to **−17.81**
  in one round.
- **Two separate controls fire on the same classification.** A bounded
  composite cap costing at most 5.00 (`:332-335`) *and* this guard. The report
  at `:415-419` describes a triple count: the firm loses the revenue, the lost
  revenue depresses its composite, and then the cap and the guard are applied
  on top of the already-depressed composite.
- **The guard's firing is not persisted.** It appears only in
  `context.log` (`:397-398`, "zero-revenue ranking guard applied"); the stored
  row `RoundResultPerformanceIndex` has fields
  `satisfaction_score, index_change, index_value` and no flag. A team cannot
  see from its results that the guard, rather than its own performance, set its
  index.

### What was measured against the live database

448 `RoundResultPerformanceIndex` rows:

| | |
|---|---|
| `index_change` min / median / max | **−5.82** / 0.00 / +5.69 |
| rows at ≤ −5.00 | 86 |
| rows at ≤ −10.00 | **0** |

The distribution is consistent with the **bounded 5.00 composite cap** firing
often and the **unbounded guard never firing** in live data — which matches the
builder's own repaired 8-team run, where "the guard did not fire at all". It
fires when a leader is frozen while the field is spread, which no live game has
yet produced.

### The realistic options

These are the builder's four, restated with their consequences. **The builder's
recommendation is on the record at `:430-449` and is deliberately not repeated
here as a recommendation** — under R19 a builder's preference is not a decision,
and this document does not carry one.

**(a) Leave it.** *For students:* a frozen leader can lose a game's worth of
accumulated standing in one round. *Work implied:* none. *Cost if deferred:* it
is live at launch; if it fires in a competition it will decide that
competition, and the team will not be able to see from its results that it did.

**(b) Exempt a team that submitted decisions.** *Measured to reopen the V2-022
exploit exactly* (+0.1623 composite, +3.25 index, for $181.86 at adoption). The
report says do not do this; recorded here for completeness because it is the
intuitive fix.

**(c) Exempt a team frozen by an engine-imposed market-access freeze.**
Cause-based rather than intent-based, so a voluntarily silent team is still
caught and the V2-022 exploit stays closed. *Directly reverses the V2-022
supplementary disposition* — see the note below.

**(d) Enforce "must not outrank" on rank, not by rewriting the carried index.**
*For students:* a frozen firm is ordered below every active firm on the
leaderboard, still loses the round's revenue and still takes the bounded 5.00
cap, but keeps its accumulated index. *Work implied:* a change inside the
Phase-1 determinism boundary, so R18's replay standard applies.

### A governance point the owner should know before ruling

The report argues the **V2-022 supplementary disposition** was "sound reasoning
applied to a mis-stated fact". That disposition lives in
`V2_FINDINGS_REGISTER.md` (the "compliance-frozen teams (adopted)" section at
`:1935`) and **not** in any `OWNER_RULINGS_*` file. Under R19, a ruling exists
only in a dated, attributed rulings document — so whether that disposition is
an owner ruling that options (c) and (d) would reverse, or a builder-adopted
position that the owner has never been asked about, is itself part of what is
pending. This document does not resolve that.

### What is measured and what is not

- **Measured:** the code; the live index-change distribution; that the guard has
  not fired in any stored round; the builder's 8-team runs (−17.81 worst case,
  4 remaining 5.00 collapses, spread 32.92) recorded in the report.
- **Not measured:** how often a *competition* field, which R28 will make more
  spread than any run so far, produces the leader-frozen-while-field-spread
  condition that makes the guard fire. R28's own instruction — "balance must be
  measured, not asserted" — points at exactly this.
- **A caveat the owner should carry into any measurement:** the report notes at
  `:465` that the calibration baseline never files a customs classification, so
  the balance runs behind these numbers are not measuring competent play. That
  is builder work, but it bears on the evidence for both D6 and D7.

### Does it block launch?

**This is the one where the honest answer is closest to yes.** Nothing is
broken — rounds resolve, and it has never fired. But unlike D1–D5, the
consequence of shipping it undecided is not a tidiness cost: it is that a single
round can rewrite a team's accumulated standing without bound, permanently,
invisibly in the stored result, and decide the finishing order of the
competition the platform is being hardened for. Whether that is the intended
rule is a judgement only the owner can make, and it is cheaper to make now than
to explain afterwards.

---

## D7 — Should missing a free form cost a team an entire round of trading?

### The question, in the owner's terms

A customs classification document is free and always available — one click. A
team that forgets it can be frozen out of a market for a whole round, losing all
its revenue there. Is that the intended lesson, or is it disproportionate to the
omission?

Raised at `ZERO_PRODUCTION_DEFECT_2026-09-12.md:342-347` and again at
`:451-457`, framed by the builder as "a live rules question I am not qualified
to settle". Like D6, it is **not registered as a numbered finding**.

### What is true today, verified in code and scenario data

- The mechanic is probabilistic per round:
  `backend/core/engine/compliance_engine.py:166` reads
  `regime.baseline_enforcement_probability_per_round`.
- Consumer Electronics authors five regimes at 0.15, 0.20, 0.05, 0.12 and 0.08
  (`backend/scenarios/consumer_electronics_2026.yaml:9648, 9666, 9694, 9714,
  9730`).
- The builder's figure for the customs regime is **12% per round across rounds
  5–10**, giving a **53.6%** chance that a team which never files loses a full
  round of trading somewhere in a ten-round game. The arithmetic
  (1 − 0.88⁶ = 0.536) is consistent with the 0.12 authored at `:9714`;
  which of the five regimes is the customs one I did not confirm line by line.
- It compounds with D6: a team frozen out of its markets earns no revenue, which
  is precisely the `commercially_inactive` condition the guard in D6 tests.
  **The two questions should be answered together**, which is how the builder
  filed them.

### The realistic options (the builder's three, plus leaving it)

| Option | For students | Work implied |
|---|---|---|
| Leave it at 0.12 | A forgotten free form can cost a round, ~54% of the time somewhere in a game | none |
| Lower `baseline_enforcement_probability_per_round` | Same rule, less often | **scenario data only** — one number per regime per YAML |
| Reduce the consequence to the $120,000 penalty alone, no market freeze | The omission costs money, not a round | engine change |
| Require the document once rather than per round | A team that files once is safe | engine + scenario change |

*Cost if deferred past launch:* the probability is the only lever that is a pure
data change, and it can be retuned between heats — but not retroactively for a
heat already played.

### What is measured and what is not

- **Measured here:** the authored probabilities; the code path that reads them;
  that the mechanic is live.
- **From the report, not re-derived:** the 12%/53.6% figures and the
  identification of the customs regime.
- **Not measured:** how often real teams forget the form. Zero data — no team in
  the live database has ever been through a competition round of this mechanic,
  and the calibration baseline never files it (`:465`), so the balance runs do
  not measure competent play against it either.

### Does it block launch?

**Not technically** — the mechanic works and is authored. But it is a rule that
can cost a team a round, its lever is a single scenario number, and it is
cheapest to set before a heat rather than between heats. Worth ruling with D6.

---

## D8–D14a — further items, with citations

The items below were surfaced by a documentary sweep of `handoff_readiness_v2/`,
`handoffs_v3/`, `specs/`, `gap_closing/`, `rework/` and `docs/`. Each is
genuinely awaiting an owner decision and is answered by **none** of R1–R29.
They are recorded more briefly than D1–D7 because each is smaller in
consequence, not because it is less open. **Where a claim comes from a source
document rather than from code I read, it is marked as such.**

### D8 — The paid-research rules R23 did not reach

R23 made research paid and deferred **prices only**. Three rules questions
inside the mechanic were never put to the owner, all in
`handoff_readiness_v2/completion/PAID_RESEARCH_REPORTS_2026-09-12.md`:

- **`:350-353`** — is charging the analyst query **per question** the intent,
  and is the quota of 5 per round still right now that each one costs money?
  Verified live: `max_research_queries_per_round = 5` at $50,000 each, so up to
  **$250,000 per team per round**. Distinct from V2-094, which is the
  engineering task of showing the price.
- **`:358-360`** — is **per-round re-purchase** right? A report bought in round
  3 stays readable forever, but round 4's must be bought again. The builder
  calls it "a rules choice".
- **`:361-363`** — should the **unbought `markets` identity list** (market names
  and codes, returned without payment) be free, or is it paid intelligence?
  The builder calls it "a disclosure call".

**Blocks launch: no.** All three ship coherently either way. The first is the
one with a number attached and belongs with D4.

### D9 — Starter-profile spread and near-tie churn

R28 ordered distinct starting profiles and R22 fixed round-zero parity; neither
answers these two, both from the CRV2-11 completion reports:

- **`completion/GSP-CRV2-11-distinct-starter-profiles.md:304-340`** — should
  Consumer Electronics spread its eight `home_market` values? The report's
  measurement: doing so widens the early-round index spread about **4×** and
  creates a **2.5× COGS asymmetry no team chose**. A third option is offered —
  spread the markets but equalise the cost and trust terms. Round-zero parity
  (R22) is unaffected either way, which is why R28 does not settle it. *Report's
  figures, not re-derived here.*
- **`completion/GSP-CRV2-11-round-zero-and-preferences.md:793-798`** — near-tie
  rank churn: 20 of 80 team-rounds reshuffled with no flip crossing 0.5 index
  points. Is a tie-break rule wanted, or is churn accepted? R28 attacks the
  cause (no duplicate archetypes) but issues no tie-break rule.

**Blocks launch: no**, but both are inputs to the authoring task R28 opened, so
they are cheapest to answer before that authoring happens rather than after.

### D10 — Cohort caps: two unruled residues, and one live conflict with R12

From `evidence/decision-rules/stage6/COHORT_CAP_INVENTORY.md:222-256`, mirrored
at `completion/GSP-CRV2-10-stage6-completion.md:288-296`. R12 set the caps at
8 firms and 3–5 members and ruled that enforcement, not the numbers, was
missing.

- **Unruled:** what happens to teams **already over cap** in an existing game
  (the shipped default grandfathers them); and whether `max_teams` counts
  `Team` rows in the game or assigned teams in the section, and whether a
  `withdrawn` team consumes a slot.
- **A live conflict, verified in code.** R12's consequence
  (`OWNER_RULINGS_2026-09-11.md:99-101`) says both write surfaces must refuse
  "a ninth firm, a sixth member, **and a team that would drop below three**, at
  the point of the write". The shipped behaviour does not: `team_size_min` is
  **reported, never refused** — `backend/core/services/cohort_caps.py:237`
  ("Teams below `team_size_min`, reported rather than refused") and
  `backend/core/views/course.py:672` ("team_size_min is reported, never
  refused"). The upper bounds *are* enforced (`cohort_caps.py:217-228`,
  `:283-287`). So a builder default currently contradicts a dated ruling.
  Whether the ruling is narrowed or the code is changed is the owner's call;
  **it is flagged rather than resolved here.**

**Blocks launch: the conflict does, in the narrow sense that shipping code that
contradicts a dated ruling is the exact failure R19 exists to prevent.** The two
unruled residues do not.

### D11 — Every scenario shares one reference-price ladder

Registered as **V2-114** on the unmerged `crv2-register-backlog-2026-09-12`
branch, from `completion/GSP-CRV2-11-distinct-starter-profiles.md:493-498`,
raised to **P1** by the registrar.

**Verified here:** all three scenario YAMLs author byte-identical
`reference_price_budget / mainstream / premium / ultra_premium` =
**250 / 420 / 700 / 1000** (line 84 region of each file; confirmed live for
scenario 7). Consumer Electronics' own starter products run **$220–$750**
(measured, 8 rows), so the ladder is commensurate there. The report states clean
energy's starter prices run **$900–$12,000** and media's **$55–$340** — *their
figures; neither scenario is loaded in the live database, so I could not
re-derive them.* If they hold, `price_ratio = price / reference` sits far
outside the band in both, and `price_competitiveness` clamps to its floor or
ceiling in every round — **the price lever is dead in two of three scenarios.**

The decision is the owner's because re-authoring per scenario reopens the
V2-023 anchor that the current rule rests on. The numbers themselves are
calibration; only the owner sets them.

**Blocks launch: not for Consumer Electronics**, which is the only scenario
loaded. **Yes for either other scenario**, if it is to be used for a heat and
the report's figures are right — a dead price lever in a strategy simulation is
a missing decision, not a cosmetic one. Confirming the two figures is cheap:
load the scenario and read `FirmStarterProduct.base_price`.

### D12 — One authorisation that was never a dated ruling (governance)

`completion/PAID_RESEARCH_REPORTS_2026-09-12.md:364-366`, reinforced by
`completion/REGISTER_BACKLOG_2026-09-12.md:31-44`.

The owner instruction that authorised the **entire paid-research build** reached
the builder **through a handoff, not through a dated `OWNER_RULINGS_*`
document**. R19's own test is that a ruling exists in such a document "and
nowhere else". R23 now records it — but R23 is dated 2026-09-12, after the work.
The registrar adds that five parallel worktrees could not see R15–R22 at all,
and that two builders acted on rulings relayed out of band.

**This is not a request for a new decision; it is a request to ratify an
existing one in the form the programme requires.** It is listed here because
this document exists under R19 and would be inconsistent to leave it out.

**Blocks launch: no, but it blocks a clean certification.** The paid-research
mechanic is merged and shipping on an authorisation that, by the programme's own
rule, is not yet on the record.

### D13 — The advisory-layer and macro plan (new, nothing ruled)

`specs/PLAN-advisory-layer-and-macro-2026-09-16.md:189-194` ("Decisions for the
owner"), plus `:76`. The newest planning document in the tree — **untracked in
git as of this writing**, so it is not yet part of the programme record. Five
questions: the advisor roster (nine personas or a smaller v1); **whether
consults cost cash and at what price** (a direct sibling of D8's first
question); quote-versus-paraphrase from the RAG library, which `:76` marks
"Owner decision needed" and which is a licensing question; the `macro_enabled`
default for existing scenarios and which scenario pilots it; and the spec
numbering, including whether CC-41 supersedes CC-26–CC-38.

**Blocks launch: no.** This is unbuilt future work. It is listed so the owner
sees it alongside D8, because pricing a consult and pricing an analyst query are
the same decision asked twice.

### D14a — The shared database credential is live again: rotate, or accept in writing

Added after this briefing was drafted, from
`specs/PLAN-LAUNCH-AND-BUILD-SEQUENCE-2026-09-16.md:50` (item 1.2) and its
decision list at `:147`. It lands in **Phase 1, the launch-readiness phase**,
where the plan's own rule is that nothing else starts until it closes.

**The claim, as the plan states it:** the 2026-09-04 rotation of the shared
PostgreSQL role was **reverted during the crash recovery**, so the password
that sits in BECSR's Git history is live again. The plan's disposition test is
worth quoting because it is this document's own rule applied to an ops
decision: *"Either rotated (all three consumers updated and verified) or
recorded as a dated, attributed acceptance. **Silence is not a disposition.**"*

**What I verified, without touching any secret:** `ops/rotate-db-credential.sh`
exists, is committed, and is written for exactly this — one role, three
applications (`globalstrat+`, GlobalStrat v1, BECSR), across two repositories,
and it never prints the value. Its header records a measured consequence that
bears on the decision: rotating without updating all three does not break the
other two *at rotation* — pooled connections keep working and fail later, at
reconnect. **I did not verify the revert claim itself**; doing so means reading
the live credential, which this document will not do. That check belongs to
whoever runs the rotation.

This sits directly beside **V2-048** (the committed credential, remediated at
`192b6e1`) and **V2-072** (the open P0 that R19 ruled *is* a launch blocker:
the application must stop running as a database role that can `SET ROLE
postgres`). D14 below is the small residue beside both.

**Blocks launch: the plan places it in the phase that must close before launch,
and R19's history on this exact credential is the reason the bar is a dated,
attributed acceptance rather than an assumption.** If the revert claim is
right, a P0 that was reported as remediated is live again.

### D14 — Three residual secrets: rotate or not

`V2-048_BUNDLE_RETENTION.md:74-77`. Three further secrets that the history-rewrite
drill may have copied elsewhere. The document's own words: rotating them is "a
judgement call for the owner, not a necessity".

**Blocks launch: no**, and it is separate from **V2-072**, the open P0 that R19
ruled *is* a launch blocker (the application must run as a non-owner database
role). D14 is the small residue beside it, not a substitute for it.

---

## Checked and found already ruled — so they are not on the list

Beyond V2-064 and V2-066 below, the following are still written as open
somewhere in the tree but are answered by a dated ruling. They are listed so
nobody re-raises them: **V2-070** (retirement timing) by R18; **V2-073**
(Stage 2 gate) by R22; **V2-072 / V2-048 attribution** by R19; **V2-056**
(P0-vs-P1) by R20; **V2-084** (round-zero share column) by R29; the CRV2-11
decorative-preference and gated-segment questions by R25 and R27; the
round-zero adoption factor by R11; the V2-041 blank-price questions by R15,
R24 and R26.

Two further stale rows worth a registrar's attention, neither an owner
decision: **V2-024** still reads "Open — stops the handoff" at
`V2_FINDINGS_REGISTER.md:1753` although the funding-need rule closed it, and
**V2-016**'s "left for the rules owner" in `completion/GSP-CRV2-03-completion.md`
is superseded by its own rework addendum ("Nothing is outstanding for the rules
owner").

---

## Already ruled — the register rows are stale

Two of the items this briefing was asked to cover **are not open decisions.**
They were ruled by the competition owner on 2026-09-12. The rulings are in
`OWNER_RULINGS_2026-09-12.md`; they are summarised here and **not restated as
new decisions**.

### V2-064 — the 409 lock scope: ruled by R17

`OWNER_RULINGS_2026-09-12.md:91-116`. **"Keep the fast refusal for every
exclusive operator action, and tell the student. Waiting is not restored."**
The ruling also names both consequences: the message must stop claiming the
round is being processed, and the interface must show the edit was not saved
and retry it, in both languages, under GSP-CRV2-12's standard.

**The register row still reads "Open — awaiting rules-owner ruling", and the
question it poses — "whether the fast-fail applies only during Phase-1
resolution or to every exclusive operator action" — was answered four days ago.**
The dispositions table further down the same file records R17 correctly
(`V2_FINDINGS_REGISTER.md:2661`); only the status column in the row is stale.
The register is not edited by this document.

**What is genuinely outstanding is engineering, not a decision**, and it is
unimplemented on this branch:

- The message still claims the round is being processed:
  `backend/core/utils/participant_messages.py:181-184`, key
  `lifecycle_in_progress`, "This round is being processed. Refresh shortly to
  see the results." It is the only string the refusal returns
  (`core/views/decisions.py:249-254`).
- The frontend still swallows the 409:
  `frontend/globalstrat-frontend/src/contexts/DecisionContext.js` — `saveDraft`'s
  `catch` is `console.error('Auto-save failed:', err)` and nothing else. The
  autosave effect re-arms on `[isDirty, draft]`, so with the draft unchanged no
  retry is scheduled, exactly as V2-064 describes.
- `GameStatusBar.js` still renders the last successful save time with no error
  state, so the bar reads "Saved" while the edit is gone.

### V2-066 — audit record for a refused student write: ruled and closed by R21

`OWNER_RULINGS_2026-09-12.md:193-215`. **"Leave it as it is. No audit row is
required for a refused student write."** The ruling is explicit that this does
not weaken V2-036 for operator refusals, and carries one requirement into
certification: CRV2-07's count of 32 busy 409s is client-side only and **must
not be cited as audited evidence**.

The register row still reads "Open" and still poses it as "a rules-owner
question" (`V2_FINDINGS_REGISTER.md:2512`), while the dispositions table at
`:2665` records R21 correctly. Same stale-row pattern as V2-064.

### The pattern worth naming

Both rows, and several others (V2-070/R18, V2-073/R22, V2-084/R29,
V2-085/R25+R27), carry an "Open — awaiting rules-owner ruling" status column
*and* a correct disposition in a table 150 lines below. The register's own note
explains why — "the rulings are the owner's record and are not edited here —
only their effect on findings is" — but the effect was recorded in the
dispositions table rather than in the rows. **Anyone reading the rows alone will
re-raise questions the owner has already answered.** This briefing was
commissioned to cover two such questions. Correcting it is the register owner's
call, not this document's.

---

## Where the code contradicts the record

Collected for the owner in one place. Each is verified by reading the code, and
each is stated as an observation — **none is dispositioned here.**

1. **`research_budget` does not feed coherence scoring.** R23, the V2-057
   register entry and the code comment at `rd_costs.py:329-332` all say it does.
   `coherence.py:446` sums `rd_budget + marketing_budget + strategy_budget` and
   omits it. Conversely, it *is* in the cash-affordability sum
   (`rd_costs.py:349-357`), which is the "second cash gate" the same sentence
   says it is not. → **D2**.

2. **V2-064's register row poses a question R17 answered.** → above.

3. **V2-066's register row poses a question R21 answered and closed.** → above.

4. **The communication mark's scale is not the scale the blend assumes.**
   `coherence.py:281-283` comments that the contribution is "already on a
   0-100ish scale"; the authored weights cap it at 26. The consequence — that
   submitting a communication lowers a team's coherence score for any formula
   score above ~26 — is arithmetic, not a defect claim, and is 20–40× the size
   of the model change V2-117 registers. → **D1**.

5. **V2-117 cites per-prompt numbers that are not where it says they are.** The
   entry says "method and per-prompt numbers in the `da8631e` commit message".
   The commit message gives the method and the summary figures (±0.014 vs
   ±0.036, ~7s vs ~11s, ~0.09 lower) but no per-prompt table. The entry's
   caveat also refers to "all three models" while its table lists two. Minor,
   and recorded only because a citation that does not resolve is how V2-093
   happened.

6. **A rules-owner question exists in code that the register does not carry.**
   `research_catalogue.py:15-21` — whether an unauthored research price should
   be fail-closed rather than falling back to $50,000. → **D4**.

7. **Shipped code contradicts a dated ruling.** R12 requires both write
   surfaces to refuse "a team that would drop below three"
   (`OWNER_RULINGS_2026-09-11.md:99-101`). `cohort_caps.py:237` and
   `views/course.py:672` both state the opposite as the implemented rule:
   `team_size_min` is "reported, never refused". The upper caps *are* enforced.
   → **D10**.

8. **Two rules-owner questions with competition-deciding consequences are in
   no register at all.** The inactivity guard (D6) and the customs-freeze
   proportionality question (D7) exist only in a completion report. Neither has
   a finding ID; neither appears in `V2_FINDINGS_REGISTER.md`. A reader working
   from the register would not know they are open.

9. **The inactivity guard leaves no trace in the stored result.**
   `performance.py:397-398` records "zero-revenue ranking guard applied" in
   `context.log` only; `RoundResultPerformanceIndex` has no corresponding
   field. If the guard ever rewrites a team's index, the team's own results
   screen shows the new number with nothing to say where it came from. → **D6**.

---

## Method, so this can be checked rather than believed

- Read against `crv2-release-integration` at `3c99d74`, working tree clean
  apart from one untracked spec file (the D13 plan).
- Every code citation was opened and read. No claim was taken from the register
  without checking it; the disagreements above are the result.
- D1–D7 and D10–D11 were verified in code and, where the data exists, measured
  against the live database. D8, D9, D12, D13 and D14 were surfaced by a
  documentary sweep and are cited to their source documents; figures taken from
  those documents rather than re-derived are marked as such at each point.
- Two items (D6, D7) are **not registered as findings anywhere**. They are
  included because the brief asked for anything genuinely blocked on an owner
  ruling, and the register is not a complete index of that set.
- Database figures come from read-only ORM queries against the live competition
  database, run with the running service's own environment. Nothing was
  written; no credential appears in this document or in any file it was
  produced from.
- Live counts as at 2026-09-16: 24 games, 264 rounds, 296 teams, 275 decision
  submissions, 448 coherence rows, 1,059 decision audit events, 0 team
  communications, 0 research purchases, 0 organisational-structure changes.

---

**Once more, because it is the rule this document exists under:** nothing above
is a decision. If the owner rules on any of D1–D14a, that ruling belongs in a new
`OWNER_RULINGS_<date>.md`, dated and attributed. Until then every item here is
open, and a later reader should treat any sentence in this file that sounds like
a conclusion as a builder's framing of a question, not an answer to it.
