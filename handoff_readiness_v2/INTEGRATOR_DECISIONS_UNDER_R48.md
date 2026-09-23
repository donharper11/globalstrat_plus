# Integrator decisions under R48 (2026-09-22)

R48 delegated the pending calls with one instruction: the least change that
keeps the platform working; calibration waits for a clean walkthrough. These
are integrator decisions, not owner rulings, and any of them can be reversed by
the owner at the recalibration.

| # | Item | Decision | Why, in one line | Player-visible effect |
|---|---|---|---|---|
| 1 | Clean Energy mainstream tier (six products clamped under the proposed 3700) | **Keep the proposed references; no re-tiering.** | A clamp is a calibration outcome, not a bug; re-tiering edits authored profiles, which is calibration. | None until the walkthrough; the clamps are listed in `KNOWN_RESIDUAL_CLAMPS` for the recalibration. |
| 2 | Mean vs median | **Mean, as implemented.** | Difference is immaterial; changing it now is churn. | None. |
| 3 | Empty budget / ultra-premium tiers | **Keep the extended ladder.** | An unauthored tier makes a round fail to resolve if a team creates a product there — a bug, not a calibration choice. | A product created in those tiers scores against a placeholder reference. |
| 4 | Unused second ("beta") platform blocks | **Leave the data alone; record as decorative.** | No code path reads them; deleting edits 24 profiles for no functional gain. | None. |
| 5 | Web-created games attributed to the first superuser | **Accept.** | Ownership runs through course and section; a creator column is a schema change for an attribution nobody reads. | None. |
| 6 | R42 quota reading | **An empty analyst answer uses no question slot**, as implemented. | A slot spent on nothing is a cost of the same kind as the money. | A team keeps its question. |
| 7 | Chinese word limit never binds | **Count CJK characters at 1.5 per word.** | A limit that binds one language and not the other is a fairness bug. | A Chinese team is limited like an English one. |
| 8 | Two instructor routes that 500 on every call | **Remove them.** | Dead, uncalled, legacy-model dependent; R16 precedent. | None; no console control used them. |
| 9 | Editing an existing product is refused | **Remove the edit control for existing products; products are fixed once created.** | A control that can never succeed is a bug; a product-edit decision is a new rule, which is calibration territory. | Students no longer see an edit control that always fails. |
| 10 | Retention of deletion records | **Keep for the life of the platform.** | Tiny rows; exist for disputes. | None. |
| 11 | Django `LocaleMiddleware` | **Leave off.** | Every reachable message is converted by hand; the layer would change pinned API text and still name storage fields. | None. |
| 12 | Committed compliance spend not shown as a row before lock | **Add the row** on Summary and Finance. | A charge a student can feel in their cash check must be visible as a line. | A "Compliance investment" row before lock. |

Items 7, 8, 9 and 12 are code; assigned 2026-09-22 to `crv2-13-r48-delegated-calls`.

## Second set, 2026-09-23 — the lock a team can never reach

The third walkthrough (`completion/WALKTHROUGH_CE_3_2026-09-23.md`) answered R48's
question with evidence: six rounds processed with no crash, but **no team locked a
round after round 3**, and rounds 4–6 moved only because the operator forced them.
Four teams finished round 6 between −$26.4M and −$49.1M. Three questions had been
queued for the owner; the walkthrough turns two of them from calibration into
bugs, so they are decided here under R48 rather than waiting.

| # | Item | Decision | Why | What a player gets |
|---|---|---|---|---|
| 13 | W-CE3-02 / W-CE-23: a team whose cash is negative can never lock again — the affordability blocker compares committed spend with cash on hand, so once cash is negative no spend is small enough; $4M of payroll and ~$6M of standing commitments are in that figure and no screen can reduce them; raising $25M of debt does not move it. | **The lock must always be reachable. Available funds must count the financing the team has already decided this round, and the blocker must name what a team can actually change.** Standing commitments a screen cannot reduce may not, by themselves, make the lock unreachable. This is the least change that removes a dead end; it changes no price and no competitive rule. | A control that can never succeed is a bug, not a balance outcome (R48). A simulation in which nobody can submit after round 3 is not playable, and the sentence beside the blocker already tells the team to raise financing. | A team in trouble can still submit a round, and is told what to change. |
| 14 | W-CE2-03's residue: a deadline close executes the rest of a draft the lock refused, so teams close at −$6.5M and −$7.4M. | **The deadline close applies the same affordability rule the lock does, once decision 13 makes that rule satisfiable.** No new competitive rule: the lock's own rule, applied consistently. | Two paths to the same submission must not charge different things (the one-calculator rule, V2-024). | The deadline cannot spend what the lock would refuse. |
| 15 | W-CE3-01: the tax structure's setup cost is taken before `cash_opening` is read, so $2,000,000 leaves a team between rounds with no line on any statement. | **Charge it in the engine at resolution with every other decision-driven outlay**, exactly as R36 did for the organisational-structure switch (V2-088). | The same defect, in the same shape, already ruled on once. | The money appears on the statement where it was spent. |
| 16 | Which reconciliation a game already carrying a plant collision should get. | **Combined capacity operational, as implemented.** | No live game has the collision (nothing has been live, R41); the boundary now refuses new ones, so this only ever runs on a repair. | Nothing. |
| 17 | What language a team-wide document uses when members differ. | **Keep the team rule (the first stated enrolment language), unchanged.** | Individually addressed sentences already follow the reader (W-CE2-05). A document written once cannot be in two languages, and choosing a rule for it is a teaching decision, not a bug. Recorded for the owner at recalibration. | Nothing changes today. |

Decisions 13, 14 and 15 are code; assigned 2026-09-23 to `walk-ce3-lock-and-money`.
