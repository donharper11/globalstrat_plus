# Rework Completion Note — 2026-07-13

Against `rework/REWORK_SPEC_2026-07-13.md`. Per §6, each item states **what was
observed** (not "wired up"), with deferrals listed honestly. All work is committed
to `main`; the working tree is clean.

## Gates (rework §6 / §5.2)
- `manage.py check` → **0 issues**.
- `makemigrations --check --dry-run` → **No changes** (migration `0054` for the compliance model applied).
- Ghost-model delta (§1.8) → **0 ghosts** (175 registered models, all physically backed).
- Frontend `react-scripts build` → **compiled** (warnings only).
- Full backend suite → **`Ran 151 tests … OK`** (baseline 132 → 151: +2 W6, +1 W5, +4 CC-16/W4, +5 W8, +7 W9).

*Update:* after the initial P0+W4–W7 pass, the deferred **W8–W10 were subsequently built** (see below); this note reflects the completed state.

## P0
- **W1 — full suite green.** Observed: `Ran 132 tests in 18.211s … OK` at baseline; **`Ran 139 tests … OK`** after all rework changes. Verbatim lines recorded in commits.
- **W2 — roadmap truthful + tree clean.** Observed: `CC-SEQUENCE-PLAN.md` reconciled to git reality (CC-5/7 Not-drafted→merged with migration/commit evidence; CC-8–15 Drafted→built; CC-19 re-titled + merged; CC-19B added; CC-22 marked smoke; CC-16 added as built). `git status` **clean**; previously-uncommitted spec edits + `serve_plus.js` committed.
- **W3 — data oddities.** Observed:
  - *#1 (bug, fixed):* SC read serializers exposed `round` = Round **PK** (e.g. 15) on a round-1 decision. Added `round_number` (source `round.round_number`) to all 14 SC read serializers; live shell shows `round=15 / round_number=1`. Regression test added.
  - *#2 (benign, documented):* resilience score **does** respond to sourcing — concentrated single-source → `multi_sourcing 0.0`, diversified two-source → `1.0` (sum 0.93 → 1.915). Identical game-10 scores were identical seeded decisions copied across rounds, not an inert mechanic.

## P1
- **W4 — CC-16 instructor SC panel (built + browser-verified).** Observed in the real UI (puppeteer, disposable game, live data left as found, **0 console errors**): instructor opens the Supply Chain tab → sees per-team resilience audit (Fragile 12.6 / single-source-flagged vs Resilient 74.2 / contingency-ready) → injects the Taiwan Earthquake → on advance the panel shows **3 suppliers at 60% capacity, 3 recovery rounds** and the fragile team's tsmc allocation flagged **disrupted**. Backend: injection creates a pending `SCEventInstance` and `run_sc_state` applies its effects on advance (tsmc→0.6) — proven by `test_cc16_instructor_sc` (4 tests, incl. student-403 tenancy). Spec `CC-16-instructor-sc-panel.md`; evidence `reports/cc-16/`.
- **W5 — real 10-round outcome E2E.** Observed trajectory (`test_cc22_multiround_e2e`, deterministic): R1–4 both teams undisrupted; **R5 Taiwan Earthquake** → fragile cf 1.00→0.60 / **$160k lost sales**, resilient only cf 0.90 / $40k (dual-source + reroute); persists R5–R8; **full recovery R9–10**; resilient out-scores fragile every round; identical parallel game reproduces the trajectory. Outcome table in `reports/cc-22/w5_multiround_outcome_report.md`.
- **W6 — fail-open SC hardening.** Observed: the three SC steps now route through `_run_sc_step`, which logs every failure at **ERROR** with a distinct marker `[SC-ENGINE-FAILURE]` (step/game/round) and **re-raises in strict mode** (`SC_ENGINE_STRICT`, default ON outside production) so a bug fails the round loud in dev/test instead of silently "no disruptions ever". Two tests cover swallow-and-log vs strict-reraise.

## P2
- **W7 — fail-closed prod secrets.** Observed: with `GLOBALSTRAT_ENV=production` and secrets unset, `settings.py` **raises `ImproperlyConfigured`** naming the missing `DJANGO_SECRET_KEY`/`DB_PASSWORD` (refuses to boot); with secrets set, and in dev, it boots. Verified by direct import under each env.
- **W8 — CC-20 FX hedge lifecycle (built).** Observed: the FX decision is no longer inert. `fx_engine.process_fx_hedges` opens a `HedgePosition` (locking the round rate on `hedge_ratio%` of foreign receivables), marks it to market each round, and settles at maturity — realized P&L booked into pre-tax income. Tests (5): open+MTM+**settle gain +100k** when USD weakens to 0.9; **settle loss −50k** when it strengthens; **P&L reaches `net_income`** through the real financials; no-basis currency skipped; zero-exposure opens nothing. Positions surfaced on the Trade Finance page. `reports/cc-20/`.
- **W9 — CC-18 compliance enforcement (built).** Observed: the detention → freeze → cost → reputation loop is closed. `compliance_engine.enforce_compliance` fires UFLPA on Xinjiang-adjacent sourcing (**$500k**, 2-round freeze, reputation 1.0) and customs on missing docs (**$120k**, 1-round hold); mitigation reduces probability. Tests (7) incl. **freeze blocks revenue** (zero sales + lost-revenue recorded) and **cost hits `net_income`** (−120k). New model `ComplianceEnforcementEvent` (migration 0054). Surfaced on the student SC dashboard + instructor panel. `reports/cc-18/`.
- **W10 — CC-23 EN/ZH i18n (built, SC surfaces).** Observed in-browser (puppeteer, `gs_language='zh-CN'`): the Sourcing page renders **采购 / 回合 1 / 已保存 / 您的采购策略 / 多源采购策略 / 供应链可视性投资 / 关键投入** — all correct Chinese (screenshot `reports/cc-23/`). New `sc` EN+ZH namespace wired into the shared state vocabulary + the 4 SC decision pages + dashboard. Deep per-field strings + instructor-panel i18n are documented follow-on.
- **W11 — deferred items (explicitly listed, not silently skipped):** CC-11 RAG corpus (`globalstrat_plus_articles` empty), CC-17 LLM narratives, CC-24/25 additional scenarios. Gated/optional for a numeric v1.

## Discipline
No new stubs, placeholders, hardcodes, or mock data were introduced. Every "done"
above is backed by a green test, a live shell/API observation, and/or a browser
screenshot — not by "wired up". Anything not built is named as deferred.
