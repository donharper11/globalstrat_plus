# CC-16 Acceptance Report — Instructor Supply-Chain Panel

**Spec:** `specs/CC-16-instructor-sc-panel.md` · **Rework:** W4 · **Observes:** `STANDING-DISCIPLINE.md`, rework §5
**Status:** Complete — backend + frontend, browser-verified end to end (0 console errors).

## 1. What was built

The instructor facilitation surface for an SC-enabled game. Without it there was
no way for an instructor to see team SC decisions, inject a disruption, or audit
resilience.

**Engine** (`core/engine/sc_engine.py`): `run_sc_state` gained a deterministic
instructor-injection path. `SCEventInstance.fired_by_instructor` (schema was
already ready) now drives a pre-staged event: on the next advance, `run_sc_state`
applies its `sc_effects` via the extracted `_apply_sc_effects` helper — the same
code path as seeded probabilistic firing — and clears the pending flag. Recovery
carry-forward is unchanged, so injected disruptions recover like seeded ones.

**Endpoints** (`core/views/instructor_sc.py`, all `IsInstructor`):
- `GET  /games/{id}/instructor/sc-panel/[?round=N]` — per-team SC snapshot
  (sourcing + single-source flags, buffer/contingency posture, resilience audit)
  + effective resilience weights + active disruptions.
- `GET  /games/{id}/instructor/sc-event-catalog/` — injectable SC event templates
  with a plain-language effect summary.
- `POST /games/{id}/instructor/inject-sc-event/` — pre-stages an injection onto
  the current open round.

**Frontend** (`components/instructor/InstructorSCPanel.js`): a self-contained
**Supply Chain** tab in `InstructorDashboard`. Inject control + active-disruption
alert + per-team resilience audit table (expandable to component breakdown +
sourcing allocations) + class resilience-weight override editor. Wired to the real
endpoints via `api/sc.js`; no mock data, honest empty states.

Resilience-weight and progressive-disclosure overrides reuse the CC-04 A1
endpoints; compliance regimes are surfaced read-only (full per-class compliance
enforcement is CC-18, deliberately out of scope — not faked).

## 2. Backend tests

```
$ python3 manage.py test core.tests.test_cc16_instructor_sc --noinput
Ran 4 tests in ~3.6s
OK
```
- `test_inject_creates_pending_then_fires_on_advance` — injection creates a pending
  `SCEventInstance`; **no disruption yet**; after `run_sc_state`, `tsmc_taiwan`
  drops to 0.6 capacity and the event is marked applied. (The proof the injected
  event actually hits the round.)
- `test_panel_returns_per_team_snapshot` — real per-team sourcing, single-source
  flags, resilience score.
- `test_catalog_lists_sc_events_with_effect_summary`.
- `test_student_forbidden` — students get 403 on panel + inject (tenancy).

Full suite regression: **`Ran 139 tests … OK`**. `manage.py check` clean.

## 3. Browser verification (puppeteer, real stack)

Real CRA build served on :4196/:4197, `/api` proxied to a runserver (:8019) on the
real `globalstrat_plus` DB against a **disposable** game (`CC16-BROWSER-VERIFY`,
deleted afterward — live data left as found). Only `/api/auth/me` mocked.

**Phase 1** (`browser_verify.js`, screenshots `01_panel.png`, `02_injected.png`):
- Supply Chain tab opens; per-team audit shows Fragile Single-Source (resilience
  **12.6**, single-source semiconductor flagged red) vs Resilient Diversified
  (**74.2**, dual source, contingency ready).
- Instructor picks "Taiwan Earthquake — Semiconductor Capacity Shock" (catalog
  shows its effect summary: −40% capacity, affected suppliers, recovers in 3
  rounds) and clicks **Inject** → confirmation "queued — fires when round 1 is
  advanced." **0 console errors.**

**Phase 2** (`browser_verify2.js`, screenshots `03_disruption.png`,
`04_disrupted_allocation.png`) — after the injected event fires on advance:
- Active-disruption alert: **3 disruption(s) active this round** — Taiwan
  Semiconductor / United Microelectronics / AU Optronics all at **capacity 60%,
  3 recovery rounds left**.
- Fragile team's expanded row shows its 100% tsmc allocation flagged **disrupted**.
- **0 console errors.**

This satisfies the rework §5.3 pass condition: an instructor runs an SC-enabled
game — views team SC posture, injects an event, and sees it hit a team's next
round — observed in the real UI.

## 4. Honest scope
- Compliance-regime **enforcement** is CC-18 (not built here; regimes surfaced
  read-only only).
- Phase-2 browser step fired the injected event via the engine step server-side
  (a controlled advance) rather than clicking the full "advance round" button, to
  avoid running the whole financials pipeline on a throwaway game; the injection →
  disruption → UI-reflects-it loop is real and observed.
