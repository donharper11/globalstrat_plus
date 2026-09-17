# Competition owner rulings — 2026-09-17

Two rulings, recorded in the form the programme record requires: the question
as asked, the ruling, the consequence, and what each dispositions. They follow
R30–R31 in `OWNER_RULINGS_2026-09-16.md`.

A ruling exists here, dated, or it does not exist (R19). Nothing below was
inferred from a recommendation.

---

## R32 — the inactivity guard enforces on rank, not by rewriting the carried index

**Question as asked.** V2-119: `performance.py::_enforce_inactive_revenue_invariant`
does not cap a commercially inactive firm's *change* for the round — it
**replaces its carried performance index** with `min(active indexes) − 0.01`.
The drop is therefore bounded only by how far above the lowest active rival the
team had climbed: on one identical event a leading firm lost **17.81** points
where a mid-table firm lost **5.00**. For scale, the strongest single decision
lever measured anywhere in this programme is worth about **12.40**. Is replacing
a carried index the intended severity?

**Ruling.** **No. Keep the classification and keep the rule that an inactive
firm must not outrank one that competed — but enforce it on the standings,
not by overwriting the team's carried score.**

**Consequence.**

- The anti-free-rider property the rule exists for (V2-021, V2-022) is preserved
  exactly: a firm that did not compete still cannot finish above one that did.
- The unbounded, success-scaling penalty goes. A control whose severity grows
  with how well a team had been playing is capable of deciding a competition on
  one round, which is the V2-024 class of defect — an outcome play cannot
  overcome.
- The **composite cap stays as authored**: bounded at 5.00, proportionate, and
  applied to the round. That remains the round-level consequence of not
  competing.
- This is an engine change inside the CRV2-01 determinism boundary. It needs a
  focused test that fails without it, and it changes stored index values, so
  earlier replay evidence covers its own commit and not the new one.
- **Prophylactic, and known to be so.** The 2026-09-16 measurement found the
  ceiling has **never fired** in stored play — 448 index rows, worst observed
  `index_change` −5.82, none at or below −10. This is being ruled before a
  competition rather than discovered during one.

**Deliberately NOT ruled here — V2-119's second question.** Whether a firing
must be **visible in the stored row** rather than only in the resolution log is
untouched by this ruling and stays open against the rules owner. Today a team
cannot be told why its index moved and a dispute cannot see it in the data.

**Also still open — V2-110's remaining question.** Whether a team frozen out of
a market by **its own** compliance failure should be treated as not competing at
all is a separate rules judgement and is not answered here.

**Dispositions:** V2-119 — question 1 ruled; question 2 open. Implementation
open against the engine owner.

---

## R33 — V2-072 is mitigated for GlobalStrat+; the estate is a separate item

**Question as asked.** GlobalStrat+ was cut over on 2026-09-16 to
`globalstrat_plus_app`, a non-owner role that cannot become `postgres`, create
roles or databases, or drop an audit trigger — each refusal exercised against
`192.168.50.38` itself rather than inferred from a container. But the old shared
credential `donwh` still exists, still inherits `postgres`, is still shared with
GlobalStrat v1 and BECSR, and is still the credential V2-048 exposed in Git
history. How should the finding be rated for this competition?

**Ruling.** **Mitigated for GlobalStrat+, recorded as closed on evidence. The
remaining shared-credential exposure is carried as its own operations item,
outside this competition's launch gate.**

**Consequence.**

- V2-072 **no longer blocks this competition's launch**. The checklist gate for
  the non-owner database role is satisfied by the cutover evidence, not by
  assertion.
- The estate exposure — `donwh` inheriting `postgres` across three applications,
  and the unreviewable access history — becomes a distinct operations finding
  with its own owner. It is not closed, not excepted, and not folded into a
  competition gate it does not belong to.
- **This is a re-rating by the owner, dated.** It is not the 2026-09-05
  acceptance R19 withdrew as never given, and it does not revive it. The earlier
  claim stays withdrawn; this ruling stands on the cutover that has since been
  performed and proven.

**Dispositions:** V2-072 — mitigated for GlobalStrat+ on evidence; estate
exposure re-opened as a separate operations finding. The launch-checklist entry
added 2026-09-12 may be ticked against the cutover record.

---

## R34 — a guard firing is recorded as an audit event, not as a hashed field

**Question as asked.** V2-119's second question, left open by R32. Under R32 the
standings place a commercially inactive firm below every firm that competed,
whatever its score — so a team can hold a **higher** performance index than the
team above it and still finish below them. Today that firing is written only to
the resolution log. Nothing in stored data explains the inversion: the rows read
"index 90.00, rank 8" beside "index 60.00, rank 3" and say nothing about why.
Must the firing be visible in the stored row?

**Ruling.** **It must be visible in stored data — recorded as an audit event,
not by adding a field to the hashed performance or leaderboard rows.**

**Consequence.**

- A round in which the guard fires becomes **answerable from stored data**,
  which is the standard the whole programme is built to: dispute 6 ("the result
  is wrong — prove the calculation") has an answer for that round, and an
  instructor can say why a team finished below one it outscored.
- **The determinism envelope does not move.** `performance` and `leaderboard`
  are hashed output sections; adding a field to either would take the manifest
  from v6 to v7, exactly as the paid-research section did, and every hash
  comparison across that point would differ while no outcome had changed. The
  audit trail sits deliberately outside the hashed output, so recording the
  reason there costs no envelope bump and no re-run of the replay evidence.
- CRV2-08's dispute tooling already reads audit events, so the answer lands
  where a disputing instructor already looks.
- **Ranking behaviour does not change.** R32's enforcement stands exactly as
  merged; this ruling adds the explanation, not a new effect.
- Recorded honestly: the control has **never fired** in 448 stored rounds, so
  this is again prophylactic. It is being built because the one time it fires it
  reorders a competition, and that is the worst moment to discover the reason
  exists only in a log.

**Dispositions:** V2-119 — **question 2 ruled.** Both of its questions are now
answered; implementation open against the engine owner.

---

## R35 — the demoted team is told on its own results screen

**Question as asked.** R34 records a guard firing as an audit event, and
CRV2-08's instructor drill-down surfaces it without change — so an instructor
can answer "why are we below a firm we outscored". But the **team's own** results
screen filters to the three price-band actions, so the team sees itself ranked
below firms it outscored by some 37 index points with **no explanation on
screen**. Should the team be told directly?

**Ruling.** **Yes. Tell the team on its own results screen.**

**Consequence.**

- The team's results view must surface the demotion alongside the price-band
  adjustments it already shows — the same receipt principle Ruling 2 established
  for a substituted price, applied to a substituted finishing position.
- The wording is participant-facing and therefore bound by GSP-CRV2-12's
  standard: state the rule and what it means — placed below every firm that
  competed, because the team sold nothing that round — in **English and
  Simplified Chinese**, naming no column, code or internal identifier. The
  static participant-string gate must pass.
- **Nothing else moves.** Ranking behaviour is R32's and is unchanged; the audit
  payload is R34's and is unchanged; and because the results view reads audit
  events, which sit outside the hashed output envelope, the manifest stays at
  **v6** and no replay evidence is invalidated.
- Prophylactic, as R32 and R34 were: the control has never fired in 448 stored
  rounds. It is being finished now because the one time it fires it reorders a
  competition, and a team reading an unexplained standing is how a dispute
  starts.

**Dispositions:** V2-119 — the finding's user-facing remainder. Implementation
open; V2-119 is closable by the auditor once this lands, R32 and R34 having
answered its two recorded questions.

---

## R36 — the organisational-structure charge moves into the engine

**Question as asked.** V2-088: switching organisational structure charges the
team's cash **in the view, at the moment of the click** (`cc32b_views.py:145-149`,
`team.cash_on_hand -= new_structure.transition_cost`). The write is audited,
lock-guarded, permissioned, and inside the hashed envelope — but the amount
appears in **no calculator**. It is absent from `rd_costs.budget_assessment`,
from `funding_need.decision_outlays` and from every engine module, so the team's
committed-spend and Finance figures never show it, the equity funding rule never
counts it, and reopening a round does not give the money back.

**Ruling.** **Charge it at resolution, in the engine, with every other outlay.**

**Consequence.**

- The cost joins the one-calculator path the programme already enforces:
  `funding_need.decision_outlays` totals it and `costs.py` books it, so the
  figure a team is shown and the figure it is charged are the same number.
  V2-037/V2-038 exist because that invariant drifted once already.
- The team's committed spend, projected cash and Finance screens include it, so
  a team's own numbers stop disagreeing with its cash.
- Reopening or re-processing a round unwinds it exactly as it unwinds every
  other decision-driven outlay, instead of leaving money gone against a decision
  that can still be changed.
- This is an engine change inside the CRV2-01 determinism boundary: it moves
  when cash moves, so it needs a focused test that fails without it, and earlier
  replay evidence covers its own commit.
- The audit record stays as it is. R34's principle holds here too — the
  explanation belongs in the audit trail, and nothing about this ruling requires
  a new hashed field.

**Dispositions:** V2-088 — ruled; implementation open against the engine owner.
