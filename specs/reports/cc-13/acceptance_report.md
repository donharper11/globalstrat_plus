# CC-13 Acceptance Report — Frontend: Trade Finance & FX

**Spec:** `specs/CC-13-frontend-trade-finance-fx.md` · **Branch:** `cc-13-frontend-trade-finance-fx` · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — all acceptance criteria met, real-browser verified.

## 1. Verify-Before-Wire
Confirmed against the running code/DB: CC-9 trade-finance endpoint accepts `{trade_finance, sinosure, fx_hedges}`, validates `buyer_payment_instrument` against the scenario instrument catalog and `currency_pair` against FX instruments' `currency_pairs_available`. `/scenarios/<id>/trade-finance-instruments/` returns 6 instruments; `fx_forward` carries pairs `[USD_CNY, EUR_CNY, JPY_CNY, GBP_CNY]` and tenors `[30,60,90,180]`. `/scenarios/<id>/segments/?segment_type=customer` returns 25 customer segments (with `market_id`); `/scenarios/<id>/markets/` returns 5. `lc_doc_prep_investment ∈ {minimal, standard, diligent}` from the model. Unlocks (`DEFAULT_UNLOCK_ROUNDS`): buyer_payment_instrument/lc_doc_prep/sinosure R4, fx_hedging R5.

## 2. What Was Built
- `pages/TradeFinancePage.js` (new): instrument catalog table with CC-6 Chinese-firm-going-overseas framing; buyer payment instruments by customer segment/market (add/remove rows, instrument + LC doc-prep selects); Sinosure export-credit coverage per market; FX hedge ratio + tenor per currency pair. Server-error Alert, save/reload; round-locked sections disabled with "Round N" tags and stripped from the POST payload. Selecting a segment auto-fills its market.
- `api/sc.js`: `getInstruments`, `getSegments`, `getTradeFinance`, `saveTradeFinance` (added in CC-12's shared module).
- `App.js` route + `Sidebar.js` nav item (`faMoneyBillWave`).
- Uses the `/scenarios/<id>/segments/` endpoint added as enablement in CC-12.

## 3. Build
`CI=false npx react-scripts build` → **Compiled** (`+2.07 kB`). eslint clean on changed files. `manage.py check` → 0 issues.

## 4. Browser Verification (§3.7, STANDING-DISCIPLINE §5.5)
Real production build in system Chromium (puppeteer-core), `/api` intercepted with contract-accurate payloads (contracts verified by CC-9 tests + live serializer dumps). Round 4 (trade finance + Sinosure unlocked; FX locked). Screenshots: `cc13_01.png`, `cc13_02.png`. Results: `cc13_results.json`.

| Criterion | Result | Evidence |
|---|---|---|
| §3.1 Reachable from nav | ✅ | `nav_reachable=true`; sidebar item (screenshot). |
| §3.2 Instruments load from scenario endpoint | ✅ | `instruments_loaded=true`; all 6 instruments render. |
| §3.3 Existing trade-finance + FX state reloads | ✅ | Pre-seeded payment row (Value Seekers · Africa / Letter of Credit) and Sinosure NA=80 render (screenshot). |
| §3.4 Valid entries save + persist | ✅ | `valid_save_success=true`; POST `trade_finance=[{segment:149,market:24,buyer_payment_instrument:"letter_of_credit",lc_doc_prep_investment:"standard"}]`; reload persists. |
| §3.5 Locked fields disabled/marked | ✅ | 8 disabled FX controls; "ROUND 5" tag on FX Hedging (screenshot). FX correctly stripped from payload (`post_fx_locked_empty=true`). |
| Runtime health | ✅ | `console_errors=[]`. |

## 5. Acceptance Criteria
1. ✅ Reachable from nav. 2. ✅ Instruments load. 3. ✅ Existing state reloads. 4. ✅ Valid entries save+persist. 5. ✅ Locked fields disabled/marked. 6. ✅ `npm run build` succeeds. 7. ✅ Browser verification recorded. No FX mark-to-market / settlement logic (§4 respected).
