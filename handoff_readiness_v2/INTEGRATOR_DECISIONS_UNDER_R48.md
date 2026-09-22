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
