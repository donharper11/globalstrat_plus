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
