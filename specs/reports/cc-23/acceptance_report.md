# CC-23 Acceptance Report — SC EN/ZH i18n

**Spec:** `specs/CC-23-sc-i18n.md` · **Rework:** W10 · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — SC surfaces bilingual (EN + ZH), verified in the browser.

## What changed
The SC frontend used **zero** `t()` calls (English-only). Added a new `sc`
translation namespace (EN + ZH) and wired it into the shared state vocabulary
(`scState.js` — used on every SC page), the four SC decision pages (Sourcing,
Logistics, Trade Finance, Inventory), and the SC dashboard — titles, subtitles,
section headers, help text, notices, toasts, and state badges.

## Verification (puppeteer, real stack, disposable game deleted after)
`gs_language='zh-CN'` on the Sourcing page renders correct Chinese, confirmed:
```
zh_title (采购)                 => true
zh_approach_header (您的采购策略) => true
zh_critical_inputs (关键投入)    => true
zh_state_badge (已保存)          => true
```
Screenshot `01_sourcing_zh.png` shows 采购 / 回合 1 / 已保存 / 您的采购策略 /
多源采购策略 / 供应链可视性投资 / 关键投入 all in Chinese. English is the base /
fallback language (`fallbackLng: en`), so the en.json values are the pre-existing
English strings. `react-scripts build` clean.

## Honest scope
Deep per-field strings (column headers, option labels, inline validation detail)
and the left-nav SC labels (app nav config, not the `sc` namespace) remain English
— mechanical follow-on. Instructor panel + FX/compliance additions surface their
own English strings; the student-facing SC decision + dashboard surfaces are the
bilingual priority delivered here.
