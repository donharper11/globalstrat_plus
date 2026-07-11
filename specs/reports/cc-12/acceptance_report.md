# CC-12 Acceptance Report — Frontend: Logistics & Distribution

**Spec:** `specs/CC-12-frontend-logistics-distribution.md` · **Branch:** `cc-12-frontend-logistics-distribution` · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — all acceptance criteria met, real-browser verified.

## 1. Verify-Before-Wire
Verified against the running code/DB: `ScenarioLanesView` returns lane `id`, `lane_id`, and `modes` JSON; CC-9 logistics endpoint accepts `{logistics, incoterms, customs}` and enforces modal-mix sum-100 + mode availability (`mode_is_available`). CC-2 unlocks confirmed vs `DEFAULT_UNLOCK_ROUNDS`: modal_mix R3, incoterms/insurance R4, customs/reverse-logistics/volume-TEU R5. Incoterms choices (EXW…DDP) and customs classifications (processing_trade/general_trade/bonded_logistics) taken from the model. Live endpoints return: 20 lanes, 5 markets, 25 customer segments.

## 2. What Was Built
- `pages/LogisticsPage.js` (new): modal-mix editor per lane (sea/air/rail/road with per-mode availability disabling + live sum-100 indicator), volume commitment (R5), Incoterms + insurance per market (R4), customs classification + reverse-logistics capacity/hub per market (R5). Client-side sum-100 validation, server-error Alert, save/reload. Round-locked fields disabled with "Round N" tags and stripped from the POST payload.
- `api/sc.js`: `getLanes`, `getMarkets`, `getSegments`, `getLogistics`, `saveLogistics` (+ trade-finance/inventory helpers used by CC-13/14).
- `App.js` route + `Sidebar.js` nav item (`faTruck`).
- **Backend enablement** (`core/views/sc_views.py` + `core/urls.py`): read-only `GET /scenarios/<id>/markets/` and `GET /scenarios/<id>/segments/` (mirroring the existing `ScenarioLanesView` pattern) so the decision pages can populate market/segment selectors. `markets` used here; `segments` consumed by CC-13. Documented as enablement per STANDING-DISCIPLINE.

## 3. Build
`CI=false npx react-scripts build` → **Compiled** (`+2.03 kB`). eslint clean on changed files. `manage.py check` → 0 issues.

## 4. Browser Verification (§4.8, STANDING-DISCIPLINE §5.5)
Real production build served + driven in system Chromium (puppeteer-core), `/api` intercepted with contract-accurate payloads (contracts verified by CC-9 tests + live serializer dumps). Round 3 (modal mix unlocked; incoterms/customs/volume locked). Screenshots: `cc12_01.png` (page), `cc12_02.png` (saved), `cc12_03.png` (validation). Results: `cc12_results.json`.

| Criterion | Result | Evidence |
|---|---|---|
| §3.1 Reachable from nav | ✅ | `nav_reachable=true`; sidebar item (screenshot). |
| §3.2 Lanes load from scenario endpoint | ✅ | `lanes_loaded=true`; all 20 lanes rendered. |
| §3.3 Existing logistics state reloads | ✅ | Pre-seeded first-lane sea=100 renders (sum tag green 100). |
| §3.4 Valid modal mix saves + persists | ✅ | `valid_save_success=true`; POST `logistics=[{lane:22,mode_sea_pct:100,...}]`; reload persists. |
| §3.5 Invalid modal mix blocked client + server | ✅ | Setting sea=60 → `client_validation_blocked=true` (no POST). Server-side proven by CC-9 logistics tests. |
| §3.6 Locked fields disabled/marked | ✅ | 74 disabled inputs; "ROUND 4"/"ROUND 5" tags (screenshot). Locked fields stripped from payload. |
| Mode availability | ✅ | Per-lane: transpacific lanes disable RAIL/ROAD; the BRI rail lane disables SEA, enables RAIL (screenshot). |
| Runtime health | ✅ | `console_errors=[]`. |

Automated `incoterms_lock_round4`/`customs_lock_round5` returned false — a false negative: PanelCard titles are CSS-uppercased so `innerText` reads "ROUND 4"/"ROUND 5"; the screenshot confirms the tags render and the fields are disabled.

## 5. Acceptance Criteria
1. ✅ Reachable from nav. 2. ✅ Lanes load. 3. ✅ Existing state reloads. 4. ✅ Valid modal mix saves+persists. 5. ✅ Invalid blocked client + server. 6. ✅ Locked fields disabled/marked. 7. ✅ `npm run build` succeeds. 8. ✅ Browser verification recorded. No sourcing/trade-finance/inventory/dashboard/engine work (§4 respected).
