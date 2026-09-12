# GSP-CRV2-13 — Stage 3/4 browser verification of the participant- and instructor-facing UI

**Date:** 2026-09-12
**Branch:** `crv2-13-frontend-verification`, cut from `crv2-release-integration` at `46b4bbe`
**Role:** QA. I implemented none of CRV2-10, -11 or -12.
**Evidence:** `handoff_readiness_v2/evidence/bug-sweep/frontend-verification-2026-09-12/`

Five builder streams landed student- and instructor-facing UI and every one of
them reported the same gap: the frontend was never built, linted or driven.
This pass builds it and drives it in Chromium, in English and Simplified
Chinese, against a disposable stack.

**No gate is closed by this report.** It records what was seen and what was
not.

---

## 1. Build, lint and tests

`node_modules` was symlinked read-only from the main checkout as instructed;
nothing was installed, and the main checkout was not modified.

| Command | Result |
|---|---|
| `npm run build` (`react-scripts build`, Node 22.17.1 / npm 10.8.2) | **exit 0** — compiled with warnings |
| ESLint | no separate script; CRA runs it during `build`. **Warnings only, no errors** |
| `CI=true npx react-scripts test --watchAll=false` | **exit 0** — 4 suites, 19 tests, all passed |

The build emits a long tail of `no-unused-vars` and
`react-hooks/exhaustive-deps` warnings across many pages, and warns that the
bundle is large (`main.js` 762.44 kB gzipped). None is an error and none
blocked this pass. A `react-router` v7 deprecation warning is logged during
`App.test.js`; the suite still passes.

**The build is not a finding.** It passes.

---

## 2. How this was run

* **Database:** a disposable PostgreSQL 16 container of my own on port 55432,
  created and dropped by this pass. The production database at
  `192.168.50.38` was never contacted, no systemd environment file was read,
  and the production service on port 8002 was not touched. The repo harnesses
  default `DB_HOST` to the production host and require a `DB_PASSWORD` I do
  not have, so they were read for their shape and not used to reach a database.
* **Stack:** `gunicorn` under `GLOBALSTRAT_ENV=production` on a run-time port,
  with the built frontend served on one origin by CRV2-08's `serve_app.py`
  (`/api` proxied), so the deployed same-origin arrangement is what was driven.
* **Browser:** real Chromium via Python `playwright` (`puppeteer-core`, which
  CRV2-08's script uses, is not installed in this worktree).
* **Fixture:** `load_scenario` + `initialize_game`, 3 firms, section authored
  at `max_teams=8`, `team_size_min=3`, `team_size_max=5`, filled to exactly 5
  members a team. Two starter products carry a round-0 price (band anchored on
  a real prior price); one extra product, **Aurora NX**, was created with no
  price history so its anchor falls back to the positioning reference — the
  "could not be priced" case.

---

## 3. The seven items, in both languages

`verified` = seen on screen in that language. Screenshot names below omit the
`-en` / `-zh-CN` suffix; both exist unless stated.

| # | Item | EN | ZH | Proof |
|---|---|---|---|---|
| 1 | Legal price range on the pricing surface | **verified** | **verified** | `01-item1-price-band-range` — screen shows `$315 – $585` / `本回合允许区间：$315 – $585`, matching `price_bands` from the API exactly |
| 2 | Out-of-band price accepted with an alert, number kept | **verified** | **verified** | `02-item2-out-of-band-alert` — 1755 entered against a 315–585 band; alert shown, value kept in the box, stored as `1755.00`, and still there after a reload |
| 3 | Clearing the price submits a blank and alerts about the floor | **verified**, with one failing case | **verified**, same failing case | `03-item3-blank-price-alert` — alert names the $315 floor; a `retail_price: null` PATCH reaches the server and the row persists blank. **Fails** when the row carries no other spend: `04-item3-edge-empty-row` → **F2** |
| 4 | Results screen shows the price adjustment notice | **failed (no screen)** | **failed (no screen)** | API carries the correct bilingual notice (`student-results-*.json`); no student-reachable screen renders it: `30-results-route_*`, `31-dashboard-after-processing` → **F3** |
| 5 | A product that could not be priced shows a not-for-sale notice | **failed (no screen)**, and pricing-screen wording is wrong | same | API returns the not-for-sale notice for Aurora NX; no screen shows it (**F3**). The pricing screen actively promises a floor that will never arrive: `05-item5-new-product-pricing-screen` → **F1** |
| 6 | Game name on every screen/confirmation that can act on a round | **verified except Extend** | **verified except Extend** | `11-item6-round-control-card`, `12-…close`, `13-…set-deadline`, `14-…close-and-process`, `43-confirm-process`, `44-confirm-advance`, `42-confirm-reopen` all name *CRV2-13 Verification Heat*. `15-item6-confirm-extend-deadline` does not → **F5** |
| 7 | Cohort cap refusal in business language | **wording verified, delivery failed** | **wording verified, delivery failed** | Both caps refuse in business language naming the cap (EN and ZH). The sixth-member refusal is delivered as HTTP 200 and the console reports success → **F4**. `21-item7-cohort-caps` |

Item 5's engine behaviour is correct and was confirmed in the database: at
close, Nexus One's blank became `315.00` (the band floor) and Aurora NX stayed
`NULL`, with audit events `price_blank_defaulted` and `price_not_offered`
carrying the submitted value, applied value and rule. The defect is entirely
in what the student is shown.

---

## 4. Findings

Severity per the register legend: **P0 blocks; P1 degrades; P2 cosmetic**, and
the register's own rule that anything which can change a published result is
never P2. IDs are left blank for the register owner. I did not edit
`V2_FINDINGS_REGISTER.md`.

### F1 — The pricing screen promises a floor to a product that will not get one (P1)

**Area:** student pricing surface / price band.
`MarketingPage.js:268` computes `priceBlank = !!band && !priceEntered` and
renders `marketing.price_blank` with `band.min` as the floor, **ignoring
`anchor_source`**, which the payload already carries. For an anchor of
`positioning_reference`, `price_band.blank_price()` returns `None` by design
(owner's ruling of 2026-09-12): the product is **not offered for sale**, not
priced at the floor. The backend's own `alert_for()` deliberately refuses to
promise a floor in this case and returns `marketing_price_invalid` instead —
the screen says the opposite of the rule.

*Reproduction:* price Aurora NX's row blank → screen reads "No price set. If it
is still blank when the round closes, it will be priced at **$490**, the lowest
price allowed this round" / "将按本回合允许的最低价 **$490** 定价". Actual
outcome at close: not offered, sold nothing.
*Evidence:* `05-item5-new-product-pricing-screen-{en,zh-CN}.png`,
`student-walkthrough-*.json` (`item5_pricing.band.anchor_source =
positioning_reference`), audit event `price_not_offered`.

### F2 — Clearing the price of an otherwise-empty row deletes the decision instead of submitting a blank (P1)

**Area:** student pricing surface / decision persistence.
`MarketingPage.js:103` filters the payload to rows where
`retail_price > 0 || production_volume > 0 || promotion_budget > 0`. Clearing
the price of a row with no other spend drops it from the PATCH entirely; the
server then holds no row, so `_apply_price_band` never sees it, no floor is
applied, no audit event is written and no results notice appears. The product
silently vanishes — the exact outcome item 5 exists to prevent. The comment on
that line claims the opposite ("a row the team is filling in but has not priced
must still be sent, or 'submitted blank' cannot reach the server at all").

*Reproduction:* save Nexus Lite with a price and production; set production to
0; clear the price. The PATCH body omits the row and the database row is gone.
*Evidence:* `04-item3-edge-empty-row-{en,zh-CN}.png`, `student-walkthrough-*.json`
(`item3_edge.row_present_in_payload = false`, `row_still_on_server = null`),
confirmed by direct query.

### F3 — The price adjustment notice has no screen a student can reach (P1)

**Area:** student results.
`price_adjustments` is rendered in exactly one place, `ResultsPage.js:269`.
**Nothing routes to `ResultsPage`** — `App.js` has no route for it, nothing
imports it, and there are no lazy routes. The sidebar's Results group links
only to Leaderboard and Team Activity. Three candidate URLs were driven and
none renders the notice; the landing dashboard does not show it either. So the
disclosure that makes the substitution legitimate — the half of Ruling 2 that
answers "our decision was recorded differently from what we entered" — is
unreachable in the product, in both languages, though the API returns it
correctly.

*Evidence:* `30-results-route_*-{en,zh-CN}.png`,
`31-dashboard-after-processing-{en,zh-CN}.png`, `student-results-*.json`
(`route_probe`, `dashboard_shows_adjustments: false`).

### F4 — A refused cohort assignment is reported to the instructor as success (P1)

**Area:** instructor roster / cohort caps.
`PUT /api/team-management/` refuses correctly and in good bilingual business
language — *"Zenith Hardware already has 5 members, the maximum this section
allows…"* / *"…已达本班级允许的上限。"* — but returns **HTTP 200** with
`{"updated":0,"errors":[…]}`. `InstructorDashboard.js` awaits the call and then
shows `message.success('N student(s) assigned')` without inspecting
`res.data.errors`, so the instructor is told the assignment succeeded when it
was refused, and the cap's wording is never displayed. The cap itself holds.

*Evidence:* `instructor-walkthrough-*.json` (`item7_sixth_member`),
`21-item7-cohort-caps-{en,zh-CN}.png`.

### F5 — The Extend Deadline confirmation does not name the game (P1)

**Area:** instructor round control / game identity.
Every other lifecycle confirmation carries `{{game}}` in both locales. The
Extend Deadline modal — a control that acts on the round — is titled from
`instructor.extend_deadline` ("Extend Deadline" / "延长截止时间") with no game
name, and it lives on `InstructorDashboard.js:2084`, outside the
`RoundControlCard` the CRV2-10 Stage 6 work hardened. Rated P1 rather than P2
because acting on the wrong heat's deadline changes a published result, which
is the risk the game-identity work exists to remove; the owner may prefer P2 on
the grounds that the modal opens from within a selected game's dashboard.

*Evidence:* `15-item6-confirm-extend-deadline-{en,zh-CN}.png`.

### F6 — Student pages poll an instructor-only endpoint and 403 forever (P2)

**Area:** student decision screens / noise.
`TeamActivityBanner` is rendered on `MarketingPage`, `FinancePage` and
`CorporateStrategyPage` and calls `GET …/changes/` every 30s. That endpoint is
`IsInstructor` since the V2-035 hardening, so every student generates a 403 on
every poll. The error is swallowed, so nothing breaks visibly — the guard is
working correctly and nothing leaks — but a student's main decision screens
produce a permanent stream of console and network errors, which is exactly the
noise that hides a real failure on launch day.

*Evidence:* 6 × `403 …/changes/?exclude_user=2&round_number=1` across runs.

### F7 — The pricing screen's own default row cannot be saved, and the failure is silent (P1, recommend the owner consider P0)

**Area:** student pricing surface / decision persistence.
`MarketingPage.js` initialises every row with `campaign_focus_feature_ids: []`
and `production_source_market: null`. The API refuses exactly that:
`{"campaign_focus_feature_ids":["Choose one to three campaign focus features."],
"production_source_market":["This field may not be null."]}` → **400**. A
student whose first action is to type a price — the obvious first action on a
pricing screen — has it refused. `autoSave` wraps the call in
`catch { /* ignore */ }`, so nothing is shown; meanwhile the client-side band
alert reads *"Your entry is saved"*. In my first pass **every one of six saves
was refused and the screen reported success throughout**; the same rows saved
cleanly once a source market and one campaign feature were set, which a student
can do but is never told to do.

Rated P1 because a fully-filled row does save and the lock path validates
server-side, so it is not a total block; flagged for possible P0 because a team
can believe a price is submitted when it is not, and on launch day that loses
decisions silently.

*Reproduction and both responses:* `default-row-refusal.txt`.

---

## 5. Console and network errors

Every error seen across all eight runs, and whose they are:

| Count | Error | Whose |
|---|---|---|
| 72 console / 32 network | `net::ERR_FAILED` on `fonts.googleapis.com` | **Mine.** Google Fonts are unreachable from this sandbox and a pending font request stops the page settling at all, so the harness aborts them deliberately. Not a product defect — but note the product hard-depends on two external font stylesheets, which will also fail in any air-gapped competition venue. |
| 6 | `403` on `…/teams/1/changes/` | **The product's** — finding **F6**. |
| 2 | `400` on `/api/games/create/` | **Mine.** The deliberate ninth-firm cap probe; a refusal is the expected result. |
| 6 (first pass, since superseded) | `400` on `…/decisions/round/1/marketing/` | **The product's** — finding **F7**. Reproduced in `default-row-refusal.txt`. |

The final instructor-lifecycle and student-results runs recorded **zero**
network errors beyond the font aborts. There were no uncaught page errors in
any run.

---

## 6. What I changed

**No runtime behaviour was changed.** No file under `frontend/` or `backend/`
was modified. The only additions are this report and the evidence directory.
The `node_modules` symlink is untracked and local to the worktree. All fixes
made during the pass were to my own harness scripts, which live in the
scratchpad, not the repository:

* navigation waits moved off `networkidle` (external fonts kept it from firing);
* Google Font requests aborted;
* the language assertion stopped counting the `中文` toggle as page copy;
* the source-market dropdown selector scoped to the visible portal.

---

## 7. What remains unverified

Stated plainly, because an implied pass is worth less than an honest gap.

* **Only one firm, one market, one scenario.** Team 1 (Zenith Hardware), North
  America, `consumer_electronics_2026`. The other two firms, the other markets
  and the other two scenarios were not driven through the UI.
* **Item 7 was exercised through the API from the signed-in browser session,
  not by clicking the roster and assignment widgets.** The cap wording and the
  HTTP status are browser facts; the success-toast behaviour in F4 is read from
  `InstructorDashboard.js`, **not observed on screen**.
* **The Chinese cohort-cap wording was obtained with the `Accept-Language`
  header that `api/client.js` sends**, not from the in-page fetch in the ZH
  instructor run (my probe omitted the header, so that run shows English text).
* **`Extend Deadline` was inspected but never executed** — only its
  confirmation was opened.
* **Close was always manual.** The deadline-expiry auto-close path, and the
  scheduler, were not exercised.
* Not covered at all: round 3 and game completion; leaderboard, grading and
  export surfaces; session expiry mid-edit; the browser back button after a
  lock; slow connections; pagination boundaries; mobile widths; accessibility;
  and every decision area other than marketing (R&D, platforms, products,
  market entry, financing, communications, org structure, tax, alliances,
  government relations, supply chain).
* **No focused automated test was added for any finding.** The handoff requires
  P0/P1 repairs to be proven by a test that fails without the repair; nothing
  was repaired here, so nothing was proven that way.
* No full backend suite was run — CRV2-09 owns it.

---

## 8. Disposition

Seven findings, five of them P1 and one flagged for possible P0. Items 1, 2 and
3 are genuinely verified in both languages and the price-band engine behaves
exactly as the ruling specifies. The student-visible half of items 4 and 5 does
not exist as a screen, and two of the pricing screen's own behaviours
contradict the rule the server enforces.

**No gate is closed and no finding is repaired by this report.**
