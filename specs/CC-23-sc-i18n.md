# CC-23 — Supply-Chain EN/ZH Internationalization

**Bundle:** CC-23 · **Depends on:** CC-10/12/13/14/15 (SC frontend)
**Observes:** `STANDING-DISCIPLINE.md`, rework `REWORK_SPEC_2026-07-13.md` §4 W10
**Status:** Built (this rework) — SC surfaces bilingual (EN + ZH), verified in-browser.

## 1. Purpose
The new SC frontend (CC-10/12/13/14/15) was English-only — none of the SC pages
used `t()`. Since the sim targets Chinese-executive / BNBU audiences, this is
adoption-relevant. This adds a real EN/ZH bilingual layer for the SC surfaces on
the existing i18next stack (`gs_language` in localStorage, `en` + `zh-CN`
resources, `fallbackLng: en`).

## 2. What was internationalized
A new **`sc` translation namespace** in `locales/en.json` + `locales/zh-CN.json`
(sections: `state`, `common`, `sourcing`, `logistics`, `trade_finance`,
`inventory`, `dashboard`), wired into:

- **`components/sc/scState.js`** — the shared operational-state vocabulary
  (Saved / Unsaved / Locked / View only / Not yet + legend) used on **every** SC
  page and the dashboard. Highest-leverage: one change localizes the state badges
  everywhere.
- **Sourcing page** — title, subtitle, section headers (Your Sourcing Approach,
  Critical Inputs), help text, lock/read-only notices, validation banner, toasts,
  supplier-catalog title.
- **Logistics / Trade Finance / Inventory pages** — title, subtitle, primary
  section headers (Trade Finance Instruments, FX Hedging, Open FX hedge positions),
  load/save toasts, notices.
- **SC dashboard (`SupplyChainPanel`)** — card titles (Resilience Score, Supplier
  Concentration, Compliance Risk), the enforcement-actions alert, empty states.

## 3. Verification
`react-scripts build` clean. Browser (puppeteer, real stack, disposable game
deleted after): the Sourcing page with `gs_language='zh-CN'` renders **采购**
(title), **回合 1** (Round 1), **已保存** (Saved badge), **您的采购策略**
(approach), **多源采购策略 / 供应链可视性投资**, **关键投入** + its help text — all
correct Chinese. Screenshot `reports/cc-23/01_sourcing_zh.png`. English is the
base/fallback language (unchanged strings).

## 4. Out of scope (honest)
Deep per-field strings (individual table column headers, option labels like
"Single source", inline validation detail messages) and the left-nav SC labels
(sourced from the app nav config, not the `sc` namespace) remain English — they
follow the same pattern and are mechanical follow-on. The instructor SC panel
(CC-16) and the FX/compliance additions surface their own English strings; the
student-facing SC decision + dashboard surfaces are the bilingual priority here.
