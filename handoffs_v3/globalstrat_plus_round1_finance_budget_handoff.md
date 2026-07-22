# GSP-R1-04 - Finance Budget Allocation Reliability

**Status:** Ready for builder dispatch.
**Scope owner:** Student Finance page budget entry, persistence, validation, and browser guidance.
**Repo:** `/home/ubuntu/projects/globalstrat+`
**Primary URL:** `https://globalstrat.camdani.com`
**Observes:** `specs/STANDING-DISCIPLINE.md`

---

## Required Reading Before Work

Before taking action, read:

1. `handoffs_v3/globalstrat_plus_round1_live_play_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

---

## Problem

During the Round 1 live-play attempt, multiple students could not reliably save Finance budget allocations from the browser.

Observed failures:

- `student1` entered Strategy Budget `$2.5M`; after reload, Strategy remained `$0` while R&D and Marketing persisted.
- `student2` entered values but the request persisted zeros.
- `student4` entered large currency values; the UI saved tiny or zero values such as `$10` or `$50`.
- The page can show confusing totals such as `Unallocated: $50.0M` even when the Round 1 usable budget appears much smaller.
- Sidebar text navigation for Finance can accidentally match Trade Finance when automated or novice selection is imprecise.

This blocks Review & Submit because required checklist items remain incomplete or misleading.

---

## Required Behavior

1. Finance budget inputs must be browser-operable with normal typing, clearing, tabbing, and saving.
2. Values must persist exactly as displayed after reload.
3. Units must be unambiguous. If the field accepts millions, the label and helper text must say so. If it accepts raw dollars, formatting must not corrupt typed values.
4. Save state must be visible: saving, saved, failed, validation error.
5. Strategy budget must persist using the same reliability as R&D and Marketing budgets.
6. Budget totals must explain available budget, allocated budget, and remaining/unallocated budget in the same unit system.
7. Validation must tell the student what to fix without requiring backend knowledge.
8. The Finance navigation target must be unambiguous from normal UI clicks.

---

## Investigation Targets

Verify names before wiring:

- `frontend/globalstrat-frontend/src/pages/FinancePage.js`
- `frontend/globalstrat-frontend/src/api/decisions.js`
- `frontend/globalstrat-frontend/src/components/Sidebar.js`
- Backend decision endpoints and serializers for finance/budget allocation.
- Database fields used for R&D, marketing, and strategy budget values.

If the frontend names do not match backend fields, report the mismatch explicitly before changing persistence logic.

---

## Browser Exit Proof

Use at least two teams to avoid a single-account artifact:

- `student1 / student1pass`
- `student4 / student4pass`

Steps:

1. Login and open game 12 Finance through normal sidebar navigation.
2. Enter distinct nonzero values for R&D, Marketing, and Strategy.
3. Save using the visible page affordance.
4. Reload the page.
5. Confirm all three values persist exactly as shown before reload.
6. Change one value downward and one upward; save and reload again.
7. Confirm totals recalculate correctly and validation is clear.
8. Capture network failures and screenshots before and after reload.

Report all data changed.
