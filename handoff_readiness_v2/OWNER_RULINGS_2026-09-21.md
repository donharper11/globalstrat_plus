# Competition owner rulings — 2026-09-21

One ruling, recorded in the form the programme record requires: the question as
asked, the ruling, the consequence, and what it dispositions. It follows
R32–R37 in `OWNER_RULINGS_2026-09-17.md`.

A ruling exists here, dated, or it does not exist (R19). Nothing below was
inferred from a recommendation.

---

## R38 — a compliance-frozen team may take the inactivity cap, provided the freeze stays inside its own market

**Question as asked.** V2-110's remaining question, left open by R32. A team is
frozen out of a market by **its own** avoidable compliance failure (CC-18,
`compliance_engine.py`: UFLPA in NA, or customs documentation after the round-5
unlock). If that takes its realised revenue below the material revenue floor —
1% of the round's highest team revenue — should it be treated as not competing,
and take the bounded 5.00 composite cap and the R32 rank demotion on top of the
freeze? The adopted V2-022 supplementary disposition says yes, the two controls
stack. Put to the owner with the facts that the freeze is recorded per
(team, market), that only a team with no material sales anywhere else can reach
the floor, and that R32 already removed the unbounded drop.

**The owner's answer, in the owner's words.** "If it is only affecting the
market it's frozen out of, then ok. It must not affect all other markets in
which the team is active and compliant."

**Ruling.** **The adopted rule stands: a compliance-frozen team whose realised
revenue is below the floor is commercially inactive, and the controls stack.
The condition is that a freeze blocks sales only in the market it was imposed
in. It must never reduce sales in another market where the team is active and
compliant.**

**Consequence.**

- No engine change. The classification, the 5.00 cap and R32's rank enforcement
  are byte-for-byte what they were, so the determinism envelope and all replay
  evidence are untouched.
- The condition is now a **tested invariant rather than a reading of the code**.
  `test_cc18_compliance.py::test_a_freeze_in_one_market_leaves_the_other_market_to_the_cent`
  puts one team in two markets, freezes one, and compares against an unfrozen
  control run: the compliant market's revenue row is identical, the frozen
  market books nothing, and the team is **not** classified inactive.
  **Falsified:** with `revenue.py`'s freeze test widened to the whole team the
  test fails (`KeyError` on the compliant market's revenue row); the engine file
  was restored and is absent from the diff. Module: 16 tests, OK, disposable
  PostgreSQL.
- The three places that read `context.compliance_freezes` for sales —
  `bass_engine.py` (attractiveness and adoption) and `revenue.py` — each test the
  exact `(team.id, market.id)` pair.
- **Put to the owner beside the ruling, and not ruled on:** a freeze also has
  firm-level effects that are not market effects. The penalty ($120,000 customs,
  $500,000 UFLPA) is booked to the team's P&L; `_stakeholder_component` deducts
  0.12 per active freeze (cap 0.30) and `_execution_resilience_component` 0.18
  per active freeze (cap 0.45); `reputation_impact` is stored on the enforcement
  event and read by nothing. These are recorded here as **described to the owner
  as the firm-level cost of a compliance failure, with no objection raised** —
  which is not the same as a ruling that they are correct. If they are ever
  questioned, that is a new question.
- The customs regime's authored mitigation (60% reduction) is **never applied**:
  `_trigger_applies` returns `mitigated=True` only on the branch where a
  classification is on file, which does not fire at all. Filing the document is
  total protection, so nothing is lost today; noted so nobody later takes the
  authored figure for a live lever.

**Dispositions:** V2-110 — remaining question **ruled**; nothing of V2-110 is
open against the rules owner. V2-022 supplementary disposition — confirmed.
