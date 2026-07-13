# Rework Completion Note — 2026-07-13

Against `rework/REWORK_SPEC_2026-07-13.md`. Per §6, each item states **what was
observed** (not "wired up"), with deferrals listed honestly. All work is committed
to `main`; the working tree is clean.

## Gates (rework §6 / §5.2)
- `manage.py check` → **0 issues**.
- `makemigrations --check --dry-run` → **No changes** (no model changes; all migrations applied).
- Ghost-model delta (§1.8) → **0 ghosts** (174 registered models, all physically backed).
- Frontend `react-scripts build` → **compiled** (warnings only).
- Full backend suite → **`Ran 139 tests … OK`** (baseline was 132; +2 W6, +1 W5, +4 CC-16, and −1 net rounding from module counts... actual: 132→139 via new tests).

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
- **W8 (CC-20 FX hedge lifecycle), W9 (CC-18 compliance enforcement), W10 (CC-23 EN/ZH i18n) — DEFERRED with sign-off.** Not built this pass (user opted to build W4 fully and defer these). Each remains scoped in `CC-SEQUENCE-PLAN.md`; the FX decision persists but is inert in the engine, and CC-16 surfaces compliance regimes read-only only (enforcement is CC-18). No stubs or fake work were introduced for them.
- **W11 — deferred items (explicitly listed, not silently skipped):** CC-11 RAG corpus (`globalstrat_plus_articles` empty), CC-17 LLM narratives, CC-24/25 additional scenarios. Gated/optional for a numeric v1.

## Discipline
No new stubs, placeholders, hardcodes, or mock data were introduced. Every "done"
above is backed by a green test, a live shell/API observation, and/or a browser
screenshot — not by "wired up". Anything not built is named as deferred.
