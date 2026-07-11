# CC-10 Acceptance Report — Frontend: Sourcing & Suppliers

**Spec:** `specs/CC-10-frontend-sourcing-suppliers.md`
**Branch:** `cc-10-frontend-sourcing-suppliers`
**Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — all acceptance criteria met, with real-browser verification.

---

## 1. Verify-Before-Wire (STANDING-DISCIPLINE §1)

Verified the real frontend patterns before writing (not assumptions):
- `src/api/client.js` — axios base `/api`, sends `Authorization: Bearer` + legacy `X-User-Id` from `localStorage.gs_user` (matches the backend header-auth path used by CC-9).
- `src/App.js` — student routes live at `/games/:gameId/teams/:teamId/decisions/<name>` inside `GameProvider`/`DecisionProvider`.
- `src/components/Sidebar.js` — Ant Design `Menu`; decisions group; `selectedKey` derived from pathname.
- `src/contexts/GameContext.js` — exposes `gameId/teamId/currentRound/roundStatus` from the authenticated user; **did not** expose `scenarioId` (see §5.1).
- `src/contexts/DecisionContext.js` — `locked` = team locked its round.
- Existing decision page (`RDPage.js`) — `PageHeader`/`PanelCard` from `components/design-system`, `useGame()`, `message`, `Alert`, `LoadingSpinner`.
- CC-2 enumerations confirmed from `specs/CC-02-decision-taxonomy.md`: `multi_sourcing_strategy ∈ {single_source, primary_backup, balanced_split, geographic_diversity}`, `tier_2_3_visibility_investment ∈ {none, basic, comprehensive}`; unlocks R3 (multi-supplier + strategy), R4 (payment_terms), R5 (tier-2/3 + volume commitments) — matching `core/utils/disclosure.DEFAULT_UNLOCK_ROUNDS`.
- CC-8 supplier rows present; CC-9 hardened sourcing endpoint present.

No invented names. One minimal backend enablement was required (§5.1).

---

## 2. What Was Built

| File | Change |
|---|---|
| `src/pages/SourcingPage.js` | **New.** Student Sourcing & Suppliers decision page. |
| `src/api/sc.js` | **New.** `getSuppliers`, `getSourcing`, `saveSourcing`. |
| `src/App.js` | Import + route `/games/:gameId/teams/:teamId/decisions/sourcing`. |
| `src/components/Sidebar.js` | Nav item (Decisions group, `faIndustry`) + `selectedKey`. |
| `src/contexts/GameContext.js` | Expose `scenarioId` (from `user.scenario_id`). |
| `backend/core/views/auth.py` | Add `scenario_id` to `/auth/me/` payload (see §5.1). |

**Page UX (spec §3):** supplier options review table (name, country, specialization, unit price, quality, reliability, lead time); critical-input categories derived from supplier specializations; per-category allocation rows (supplier select, allocation %, payment terms, volume commitment) with add/remove; page-level multi-sourcing strategy and tier-2/3 visibility selects; per-category live "% allocated" indicator; client-side validation (sum-to-100 per category, supplier required); server-error display (flattened DRF errors in an Alert); save + reload. Locked fields are disabled with a "Round N" tooltip tag; round-locked fields are stripped from the payload before POST so early-round submissions succeed. Uses the existing design-system components and Ant Design.

---

## 3. `npm run build` (spec §4.7)

```
$ CI=false npx react-scripts build
Compiled with warnings.   (warnings are pre-existing, in other files)
File sizes after gzip:
  680.07 kB (+3.45 kB)  build/static/js/main.ccb8c261.js
The build folder is ready to be deployed.
```

`eslint` on the six changed/added files → clean (no errors, no warnings). `python3 manage.py check` → 0 issues (backend change).

---

## 4. Browser Verification (spec §4.8, STANDING-DISCIPLINE §5.5)

The **real production build** was served and driven in **system Chromium** via `puppeteer-core` (headless). `/api` was intercepted with contract-accurate responses (contracts independently verified by the 19 CC-9 API tests and a live `SupplierSerializer` dump of the loaded `Consumer Electronics 2026` scenario). This exercises the actual bundle, routing, React/Ant Design rendering, client-side validation, and the real POST payload — i.e. the frontend user workflow, not a backend echo.

Screenshots: `01_sourcing.png` (page), `02_saved.png` (post-save), `03_validation.png` (client-side block). Machine results: `browser_results.json`.

| Acceptance criterion | Result | Evidence |
|---|---|---|
| §4.1 Reachable from navigation | ✅ | `nav_reachable=true`; "Sourcing & Suppliers" in sidebar (screenshot). |
| §4.2 Loads suppliers from scenario endpoint | ✅ | `suppliers_loaded=true`; all 25 suppliers render in the options table. |
| §4.3 Loads existing sourcing decision state | ✅ | Pre-seeded semiconductor 100% allocation renders as a green "100% ALLOCATED" card (screenshot). |
| §4.4 Submit valid + persists after reload | ✅ | `valid_save_success_msg=true`, `post_fired=true`; POST body `{"allocations":[{"critical_input_category":"semiconductor","supplier":27,"allocation_pct":100}]}`; page reloads persisted state. |
| §4.5 Invalid totals blocked client-side (+ server-side) | ✅ | Setting the allocation to 60% and saving → `client_validation_blocked=true` (no POST). Server-side rejection independently proven by CC-9 `test_invalid_allocation_total_rejected`. |
| §4.6 Locked fields disabled / explained | ✅ | At round 1: 2 disabled strategy selects; "Round 3" and "Round 5" lock tags (screenshot). Payload correctly **omits** the locked `multi_sourcing_strategy`/`tier_2_3_visibility_investment` fields. |
| Runtime health | ✅ | `console_errors=[]` — no JS/React errors during the workflow. |

**Note on the automated text-assertion `existing_allocation_loaded=false`:** a false negative — Chromium's `innerText` applies the card tag's CSS `text-transform:uppercase`, so the check for lowercase "100% allocated" missed the rendered "100% ALLOCATED". The screenshot and the successful POST of that exact allocation confirm the state loaded correctly.

---

## 5. Notes / Minimal Deviations

1. **Backend enablement — `scenario_id` in `/auth/me/` (1 line).** No student-accessible endpoint exposed the active scenario id, which is structurally required to call the scenario-content suppliers endpoint (§4.2). Added `payload['scenario_id'] = _game.scenario_id` in the block that already loads `_game` for sidebar labels — mirroring how CC-16 added `sidebar_labels` to the same payload. This is API enablement, not engine logic; documented here per STANDING-DISCIPLINE rather than done silently. **Deployment note:** the live gunicorn (`globalstrat.wsgi` on :8002) must be restarted to serve the new field; not restarted here (shared service, and deployment is out of build-bundle scope).

2. **Client-side unlock schedule is a mirror.** The page disables locked fields using the CC-2 §8 baseline (`UNLOCK` constant). The server (`get_effective_unlock_round`, which honors per-class overrides) remains the source of truth; a class-specific override that unlocks earlier would still be enforced server-side, and any locked-field rejection is surfaced via the server-error Alert. Documented as a known limitation.

3. **Critical-input categories are data-driven** from the distinct supplier specializations in the scenario (plus any category on an existing allocation) — `critical_input_category` is a free-form field on the model, so no invented enumeration was introduced.

4. **Browser test used a network-level API mock.** The frontend workflow ran in a real browser against the real bundle; the backend was stubbed at the network boundary with contract-accurate payloads. The contracts themselves are verified live (suppliers) and by CC-9's 19 tests (sourcing GET/POST + validation). A full live-stack click-through would additionally cover the auth/session integration seam, which was not stood up here (0 seeded games/users in `globalstrat_plus`; shared live backend not disrupted).

---

## 6. Acceptance Criteria (spec §4)

1. ✅ Sourcing page reachable from app navigation.
2. ✅ Loads suppliers from the scenario-content endpoint.
3. ✅ Loads existing sourcing decision state for the active team/round.
4. ✅ Submit valid allocations; persisted values shown after reload.
5. ✅ Invalid allocation totals blocked client-side and rejected server-side.
6. ✅ Locked fields visibly disabled and explained by round state.
7. ✅ `npm run build` succeeds.
8. ✅ Browser verification recorded here (screenshots + results).

No logistics / trade finance / inventory / dashboard / engine work included (§5 non-scope respected).
