# Competition owner rulings — 2026-09-21

Four rulings, recorded in the form the programme record requires: the question as
asked, the ruling, the consequence, and what each dispositions. They follow
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

---

## R39 — the campaign-focus relaxation is confirmed

**Question as asked.** V2-130 (the re-audit's A-08). A repair on 2026-09-16
(`1855b25`, V2-107) changed a competition rule without a ruling:
`DecisionMarketingSerializer` went from requiring *one to three* campaign focus
features on every marketing row to *at most three, required only when
`promotion_budget > 0`*. Campaign focus features feed `campaign_engine`. The
re-audit called the change defensible and probably right, and noted that
V2-073 says that is not the test. Confirm or revert?

**The owner's answer, in the owner's words.** "confirmed."

**Ruling.** **The relaxed rule is the rule: at most three campaign focus
features, and at least one only when the row carries a promotion budget.**

**Consequence.**

- No code change. `1855b25` stands as merged, and V2-107's repair — the pricing
  screen's own default row no longer refused while the screen reported success —
  no longer rests on an unruled rule.
- A row with no promotion budget runs no campaign, so requiring a focus for it
  demanded a decision with no effect. That is the rationale the builder gave;
  it is now the owner's.
- The standing lesson is R19's and V2-073's again: the change was right and was
  still a finding, because a rule that moves without a dated answer cannot be
  defended in a dispute.

**Dispositions:** V2-130 — **ruled; closable by the auditor.**

---

## R40 — the model-scored grading component stays, outside the competition

**Question as asked.** V2-123's second residual. R31 severed the language model
from the coherence score. A second route remained: the grading rubric component
`communication_quality` (`grading.py::_extract_communication_quality`) averages
the model's `overall_score` for a team's written communications straight into a
rubric category, and so into a grade. It is dormant unless an instructor's
rubric selects it; the default rubric does not. Remove it, or keep it as an
instructor option outside the competition?

**The owner's answer, in the owner's words.** "Keep as an instructor option
outside the competition."

**Ruling.** **Keep the component for ordinary teaching. A competition heat may
not be graded with it.**

**Consequence.**

- "Outside the competition" is **enforced, not advised.** Left as a convention,
  one rubric edit on a heat's course would put a model's judgement into a
  competition grade, which is what R31 ruled out.
  `grading.refuse_model_derived_components_in_competition` runs at the top of
  `calculate_team_grades`: if the instance carries `is_competition` and its
  active rubric maps any key in `MODEL_DERIVED_COMPONENTS`, it raises before a
  single `TeamGrade` row is written, and `CalculateGradesView` returns **409**
  with `code=model_derived_component_in_competition` and a sentence naming the
  component and what to do.
- The flag is read **strictly**, not through `is_competition_game`, which
  swallows errors and answers "not a competition" — correct for rendering a
  page, wrong for a guard.
- An ordinary class is untouched: same component, same arithmetic, same grade.
- A future model-scored extractor cannot join silently:
  `test_every_model_scored_extractor_is_listed` fails if an extractor reads a
  model evaluation and is absent from the set.
- Evidence: `core/tests/test_r40_model_component_not_in_competition.py`, 5 tests;
  run with `test_r31_llm_not_in_grades`, 11 tests OK. **Falsified:** with the
  guard call removed, the refusal test and the response test fail (2 of 5).
  Disposable PostgreSQL. Outside the hashed manifest: grading is not an engine
  output section, so the envelope stays at 6.
- **Known gap, recorded not repaired here:** the instructor console discards the
  reason — `InstructorDashboard.js:1150` answers every failure with a hardcoded
  English "Failed to calculate grades". To be repaired once
  `crv2-13-assignment-refusal-and-analyst-price`, which edits the same file, has
  merged.
- This guard depends on the heat being flagged, which is already a launch
  checklist item ("For every competition heat, set `is_competition`").

**Dispositions:** V2-123 — residual (2) **ruled and implemented**; residual (1),
the latent `skip_rag=False` blend, remains with `crv2-01-release-identity-guard`.

---

## R41 — the nine manifests with no revision are treated as test play

**Question as asked.** V2-120. Nine stored resolution manifests record no code
revision, cannot be tied to the code that produced them, and cannot be repaired
after the fact. Does any result the owner cares about depend on those rounds?

**The owner's answer, in the owner's words.** "Nothing is live yet on
globalstrat+. So I suspect they are all test play."

**Ruling.** **No result depends on them. GlobalStrat+ has hosted no live play,
so the nine rounds are test play and carry no standing.** This is the same
ground as R20.

**Consequence.**

- V2-120 stops being a question about past results and becomes a hygiene item:
  no competition or graded cohort may run in a game that contains one of those
  rounds. A competition heat is a newly created game, so this holds by
  construction; the freeze-time operator procedure should still say so.
- **What this ruling does not establish.** The owner's word is "suspect", and
  it is recorded as given. That the nine rows belong only to test games has
  **not** been checked against the production database — a read-only query the
  auditor or operator can run (`resolve_stored_revision --all-stored` lists
  them). If one turns out to sit in a game someone was graded on, that is a new
  fact and this ruling does not cover it.
- No new manifest can join the set: production refuses to resolve without an
  explicit revision. Making that revision the *right* one is V2-124.

**Dispositions:** V2-120 — **ruled; closable by the auditor once the nine rows
are confirmed to sit in test games.**
