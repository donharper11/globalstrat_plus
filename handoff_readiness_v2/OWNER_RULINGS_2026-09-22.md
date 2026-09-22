# Competition owner rulings — 2026-09-22

One ruling, recorded in the form the programme record requires. It follows
R42–R46 in `OWNER_RULINGS_2026-09-21.md`.

A ruling exists here, dated, or it does not exist (R19). Nothing below was
inferred from a recommendation.

---

## R47 — compliance investment costs money, charged from cash

**Question as asked.** V2-137's repair made compliance investment saveable for
the first time. The decision (`ComplianceInvestment`, up to $10,000,000 per
market per round by the serializer's own validator) raises a team's
`TeamMarketCompliance.compliance_level`, which the engine consumes, but the
amount is charged nowhere: it appears in neither `funding_need.decision_outlays`
nor `costs.calculate_operating_expenses`. Should it cost money, and from which
budget?

**The owner's answer, in the owner's words.** "Yes, compliance investment
should cost money, charge it from cash."

**Ruling.** **The invested amount is an outlay the team's own decision
determines, charged from cash at resolution.**

**Consequence.**

- It joins the one-calculator pair: one shared line in
  `funding_need.decision_outlays`, booked by the engine in
  `costs.calculate_operating_expenses` from the same rows through the same
  function, and covered by the assertion that stops the round if the two
  sides ever disagree (V2-024, R36's precedent).
- Charged from cash means it counts toward committed spend, so the
  affordability check and the equity funding rule see it, and a team cannot
  invest what it does not have.
- The authored figure is the amount the team typed; no price is invented and
  no scenario data changes.
- Inside the CRV2-01 determinism boundary: it changes a charged amount, so it
  needs a focused test that fails without it, and it invalidates replay
  evidence for any round carrying a compliance investment — of which, by
  V2-137, there are none.
- **Presentation, ruled the same day.** Asked whether the charge shows as its
  own line on the income statement or within strategy expense, the owner
  answered: "Show its own line on the income statement." So it is a distinct
  line — in the engine's opex record, on the statements a student and an
  instructor read, in the tax deduction total and in committed spend — named
  "Compliance investment" in both languages.

**Dispositions:** the silent-saves builder's owner question — ruled;
implementation open against the engine owner.

---

## R48 — bugs first; calibration is deferred to a clean walkthrough, and the pending calls are delegated

**Question as asked.** Twelve items were put to the owner with context: five on the
reference-price ladder (V2-114 and its follow-ons), the analyst quota reading
under R42, the Chinese word limit, two dead instructor routes, editing an existing
product, retention of deletion records, the framework translation layer, and a
missing pre-lock row for committed compliance spend.

**The owner's answer, in the owner's words.** "I'm not gonna rule on any. It's
gonna be your call. Why? Cuz, I don't understand when, how, or why, globalstrat+'s
pricing set up got so complex. And I gonna guess, that no matter what I rule now,
it's still not gonna work the way I expect. Builders just seem to be doing
whatever. So, here's what's gonna happen, the most important thing is to get the
platform working - free of bugs! How companies decisions end up playing out is
what we're gonna recalibrate when we're done, have a working platform, and do a
full walkthough. When that happens without bugs, we can play clean games and fix
ridiculous scoring, pricing, etc."

**Ruling.**

1. **Priority is a working, bug-free platform.** Correctness of behaviour comes
   before calibration of outcomes.
2. **Calibration is deferred.** How decisions play out — scoring, pricing bands,
   reference prices, starting-field balance — is recalibrated after a full
   walkthrough of the working platform, by playing clean games. No calibration
   question is put to the owner until then.
3. **The pending calls are delegated to the integrator**, to be decided in the
   direction of the least change that keeps the platform working, and recorded
   as integrator decisions under this ruling, not as owner rulings.
4. **Standing complaint, recorded:** the owner cannot trace how the pricing
   set-up reached its present complexity, and finds builders deciding things on
   their own. Every future change to a rule that a player can feel must be
   traceable to a dated ruling or a decision under this one, in plain language,
   in one place.

**Consequence.** The freeze is no longer blocked on rulings. The next gate is a
full walkthrough, in a real browser, in both roles and both languages, across
whole games; every defect found is a finding first and a repair second.

**Dispositions:** the twelve pending items — delegated; see
`INTEGRATOR_DECISIONS_UNDER_R48.md`.
