# GSP-R1-02 - Student Decision Page Readiness

**Status:** Ready for builder dispatch.
**Scope owner:** Round 1 student decision pages.
**Repo:** `/home/ubuntu/projects/globalstrat+`
**Primary URL:** `https://globalstrat.camdani.com`

---

## Required Reading Before Work

Before taking action, the assigned agent must read:

1. `handoffs_v3/globalstrat_plus_round1_rework_overview.md`
2. `specs/STANDING-DISCIPLINE.md`

The overview gives the Round 1 playtest context and sequencing. `STANDING-DISCIPLINE.md` is binding: verify before wiring, do not invent names, report mismatches explicitly, preserve migration hygiene, and prove changes through browser-visible behavior.

---

## Problem

Synthetic student play reported many Round 1 decision pages as blank, thin, or confusing.
Some of this may be caused by shallow-route navigation, but nested-route checks still suggest
that at least Sourcing is unusually thin and needs focused verification.

The student must be able to open each visible Round 1 decision page and understand:

- what the decision is for
- what fields can be changed now
- whether this is a draft/current/locked/unavailable state
- how to save
- what to do next

---

## Pages In Scope

Verify every page through normal sidebar navigation after login, not by guessing URLs:

- Sourcing
- Logistics
- Trade Finance / FX
- Inventory / Resilience
- R&D Investment
- Product Portfolio
- Marketing Mix
- Corporate Strategy
- Market Strategy
- Finance
- Company Forecast
- Stakeholder Communications
- Review & Submit

Adjacent info/results pages to smoke:

- Financial Reports
- Industry News
- Market Research
- Competitive Intelligence
- Strategy Tools
- Leaderboard
- Team Activity

---

## Required Behavior

For each decision page:

- Page body renders meaningful content, not just global shell/sidebar.
- Header identifies the decision and current round.
- Controls are visible and usable at `1440x1000`.
- Disabled/gated fields explain why they are disabled.
- Save/draft action is visible when editing is allowed.
- Validation failures explain what to fix.
- If the page is intentionally unavailable in Round 1, it shows an honest state and why.
- No indefinite loading spinners without timeout, empty-state text, or retry path.

For Sourcing specifically:

- Supplier allocation workflow should be visible.
- Student can tell allocation totals must sum to 100%.
- Save/validation path should be clear.
- If sourcing is already current/saved, the page should still show the actual allocation and how to
  revise it before lock.

---

## Suggested Investigation Targets

Verify before wiring:

- `frontend/globalstrat-frontend/src/pages/SourcingPage.js`
- `frontend/globalstrat-frontend/src/pages/LogisticsPage.js`
- `frontend/globalstrat-frontend/src/pages/TradeFinancePage.js`
- `frontend/globalstrat-frontend/src/pages/InventoryPage.js`
- `frontend/globalstrat-frontend/src/pages/RDPage.js`
- `frontend/globalstrat-frontend/src/pages/ProductsPage.js`
- `frontend/globalstrat-frontend/src/pages/MarketingPage.js`
- `frontend/globalstrat-frontend/src/pages/CorporateStrategyPage.js`
- `frontend/globalstrat-frontend/src/pages/MarketStrategyPage.js`
- `frontend/globalstrat-frontend/src/pages/FinancePage.js`
- `frontend/globalstrat-frontend/src/pages/CompanyForecastPage.js`
- `frontend/globalstrat-frontend/src/pages/CommunicationsPage.js`
- `frontend/globalstrat-frontend/src/pages/SummaryPage.js`

---

## Browser Exit Proof

Use `student2 / student2pass`.

1. Login.
2. Navigate using the sidebar only.
3. For each in-scope page, click visible tabs, expanders, modals, dropdowns, and save/draft affordances
   where safe.
4. Record any data changed.
5. Capture screenshots for:
   - Sourcing
   - Trade Finance / FX
   - Inventory / Resilience
   - Review & Submit
   - any previously blank page after the fix
6. Browser console/network must have no unexplained 5xx and no unexplained blank-page route.

