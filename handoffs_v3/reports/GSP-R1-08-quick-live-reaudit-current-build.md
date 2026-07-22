# GSP-R1-08 — Round 1 Live-Play Re-Audit

## ⚠️ SCOPE: QUICK RE-AUDIT OF THE CURRENT LIVE BUILD (BASELINE)

**This is a quick, current-state baseline re-audit run on the live build BEFORE the second-wave
builder handoffs (GSP-R1-04 finance-budget, -05 R&D/submit-guidance, -06 guided-navigation,
-07 instructor-monitoring-polish) have been built.** It was run at explicit user direction against the
**existing game 12** (prior drafts exist for teams 18/19/21, which affect proof). It is **not** the
final post-fix sign-off audit. Its purpose is to show which second-wave blockers actually reproduce on
the current build, so the R1-04..07 dispatch can be prioritised.

**Date:** 2026-07-22 · **Target:** `https://globalstrat.camdani.com` · game 12 · viewport 1440x1000.
**Personas exercised:** `student1` (finance/R&D/review/dashboard), `instructor` (game control / teams /
students / supply chain). (A full 4-student completion play was not run — this is the quick pass.)

## Verdict: **FAIL (current build)** — one hard completion blocker remains.

A student cannot reliably enter Round 1 finance budgets, so Round 1 is not live-ready on the current
build. Several other second-wave items, however, already appear **improved/addressed** (see Good).

---

## Blockers

**B1 — Finance budget input mangles typed values (Round 1 completion blocker).**
- Route: `/games/12/teams/18/decisions/finance` · Persona: student1.
- Action: typed `2000000` into the Strategy Budget field (as a novice would).
- Observed: the live per-keystroke currency formatter mangled it to **`$ 20`**; Total Allocated
  dropped to $2.2M; on reload the mangled `$ 20` **persisted**. (An atomic paste/`fill` of `1500000`
  formats correctly to `$ 1,500,000` — so the bug is specifically **human character-by-character
  typing**, which is how a student enters values.)
- Expected: typing `2000000` yields `$ 2,000,000` and persists exactly as entered (per the field's own
  help: "Enter dollar amounts directly. Examples: 2500000, $2,500,000, or 2.5M").
- This is the root cause of the second-wave finding ("entered budget values but persisted zeros/tiny").
  It is **not fixed** on the current build → this is what GSP-R1-04 (finance-budget) must address.
- Screenshot: `gsp08_finance.png`, `gsp08_finance_afterreload.png`.

---

## Major Friction

**M1 — Instructor vs student round/status inconsistency for the same game 12.**
- Instructor Game Control shows **"DECISION ROUND 1 of 10, STATUS setup"**; the student workspace shows
  **"R1 of 8, IN PROGRESS"** — same game 12. The round total (10 vs 8) and status (setup vs in-progress)
  disagree between the two surfaces. Confusing for monitoring. (GSP-R1-07 target.)
- Screenshot: `gsp08_inst_teams.png` (Game Control), `gsp08_finance.png` (student top bar "R1 of 8").

## Minor Friction

**m1 — Instructor Supply Chain per-team audit rows render blank.** The "Per-team supply-chain audit"
table shows headers (TEAM / RESILIENCE / SOURCING STRATEGY / …) but the data rows are blank/empty.
(GSP-R1-07 target: SC row formatting.) Screenshot: `gsp08_inst_sc.png`.

**m2 — Finance has no explicit Save button;** relies on a 30s auto-save (no save POST observed during
short windows). A student who edits and navigates/reloads quickly may lose input. Worth an explicit
Save + save confirmation as part of the finance fix.

---

## Good / Ready Moments (already improved on the current build — contrary to some second-wave findings)

- **R&D (GSP-R1-05 area) looks feasible now:** "You have $3.3M of R&D budget remaining and 4 of 5 slots
  open. Upgrade an existing feature when a new platform is over budget." Enabled **"Invest next level"**
  buttons on existing features (clear within-budget actions) plus "Create New R&D Platform". Honest
  guidance present. Screenshot: `gsp08_rd.png`.
- **Review & Submit (GSP-R1-05 area) already has a clear checklist with clickable fix-paths:** each item
  shows Complete / Not started / configured + guidance + **"Fix in Product Portfolio / Marketing Mix /
  Strategy Mix / Financing"** links. Screenshot: `gsp08_review.png`.
- **Dashboard Guided Next (GSP-R1-06 area):** "Continue to 2. Product Portfolio" opens the next
  actionable decision page.
- **Instructor monitoring (GSP-R1-07 area) partly addressed:** game **ID is shown ("Game #12")**, all
  **4 teams** appear (Zenith, Helix, Photon, Nova Circuit), and **Students & Logins is honestly labeled**
  ("4 active sessions … This is not a unique-person count").
- No shell-only pages, no indefinite spinners, and **no 5xx** in any flow exercised.

## Data Changed

- **student1 / team 18 Strategy Budget** was changed during the B1 persistence test
  ($1,500,000 → mangled `$ 20`) and then **restored to `$ 1,500,000`** via an atomic fill; restoration
  verified after reload. R&D ($900,000) and Marketing ($1,300,000) were untouched. **Net change: none**
  (draft left as found). No game advanced/processed/reset/archived; no events injected; no lock/submit.

## Screenshots / Artifacts (scratchpad)

`gsp08_finance.png`, `gsp08_finance_afterreload.png`, `gsp08_finance_restored.png`, `gsp08_rd.png`,
`gsp08_review.png`, `gsp08_inst_teams.png`, `gsp08_inst_sc.png`.

## Recommendation

**Rework again — but the second-wave scope is narrower than the overview implies.** On the current build:
- **GSP-R1-04 (finance-budget) is the real blocker** — the budget input's per-keystroke formatter is
  broken for normal typing; fix it (and add an explicit Save + confirmation).
- **GSP-R1-05 (R&D / submit guidance) appears largely already satisfied** (feasible R&D action; Review &
  Submit checklist with fix-links) — verify and likely close.
- **GSP-R1-06 (guided navigation)** — Guided Next opens actionable pages; verify the full novice path.
- **GSP-R1-07 (instructor polish)** — two real items remain: the round/status inconsistency (M1) and the
  blank Supply Chain audit rows (m1); game-ID and session-label findings are already addressed.

Do **not** proceed to a full Round 1 live-play rehearsal until B1 (finance input) is fixed and
re-proven. Re-run the full 4-student GSP-R1-08 protocol after GSP-R1-04..07 land.
