# CC-16 — Instructor Supply-Chain Panel

**Bundle:** CC-16 · **Depends on:** CC-15 (dashboard), CC-19/19B (SC engine), CC-5 (instructor-panel fork audit)
**Observes:** `STANDING-DISCIPLINE.md`, rework `REWORK_SPEC_2026-07-13.md` §4 W4 + §5
**Status:** Drafted + built (this rework).

## Non-Negotiable Builder Discipline
1. Verify every existing field/model/table/endpoint/route/component before referencing it. Use the codebase + DB, not memory.
2. Do not invent names. Halt with a MISMATCH report if the contract diverges.
3. No stubs, placeholders, hardcodes, or mock data.
4. Self-verify every acceptance criterion with recorded command/API/browser evidence in `specs/reports/cc-16/`.
5. A passing backend response is not proof of frontend completion — browser-verify the actual instructor workflow.

## 1. Purpose

Give the instructor a **facilitation surface** for an SC-enabled game. Without it,
an instructor cannot run a supply-chain classroom sim: they cannot see what teams
decided, cannot inject a disruption, and cannot audit or tune resilience. CC-5's
instructor-panel audit routed five SC-facing needs here; the panel closes them.

## 2. Scope (five surfaces)

1. **Per-team SC decision viewing** — for the current round, each team's sourcing
   allocations (supplier + country + %), single-source flags, multi-sourcing
   strategy, logistics modal mix, inventory buffer posture, contingency readiness.
2. **Event injection** — the instructor picks a supply-chain event template and
   injects it; it fires on the **next round advance** and creates real supplier/
   lane disruption state (`SupplierState`/`LaneState`) that hits every team
   sourcing the affected supplier. (Not the generic `EventInstance` path, which
   the SC engine ignores.)
3. **Resilience audit** — per team: the computed resilience score, its 6-component
   weighted breakdown, the effective weights (including class overrides), and the
   current-round disruption impact.
4. **Resilience-weight overrides per class** — reuse the CC-04 A1
   `ClassResilienceWeightOverride` endpoints (sum-to-1.0 enforced).
5. **Progressive-disclosure overrides per class** — reuse the CC-04 A1
   `ClassProgressiveDisclosureOverride` endpoints.

Compliance-regime toggles are surfaced read-only (list the scenario's regimes);
full per-class compliance enforcement is CC-18 (out of scope here — do not fake it).

## 3. Backend

### 3.1 Engine — instructor-forced SC event firing
`core/engine/sc_engine.py::run_sc_state` gains a deterministic injection path.
`SCEventInstance` already carries `fired_by_instructor` (schema was ready). An
injected event is a pre-staged `SCEventInstance(round=<open round>,
fired_by_instructor=True, resolution_data={'pending': True})`. On advance,
`run_sc_state` applies its `sc_effects` (via the extracted `_apply_sc_effects`
helper — the same code path as probabilistic firing) and clears the pending flag.
Recovery carry-forward is unchanged, so injected disruptions recover like seeded
ones.

### 3.2 Endpoints (all `IsInstructor`)
- `GET  /api/games/{game_id}/instructor/sc-panel/[?round=N]` — aggregate per-team
  SC snapshot + effective resilience weights + active disruptions.
- `GET  /api/games/{game_id}/instructor/sc-event-catalog/` — supply-chain event
  templates with a plain-language effect summary (affected suppliers/lanes,
  capacity reduction, recovery rounds).
- `POST /api/games/{game_id}/instructor/inject-sc-event/` — body
  `{event_template_id}`; pre-stages the injection onto the current open round.
- Reused: `.../instructor/disclosure-overrides/`, `.../instructor/resilience-weight-overrides/`
  (CC-04 A1), `.../scenarios/{id}/compliance-regimes/`.

## 4. Frontend
A self-contained `InstructorSCPanel` React component mounted as a **Supply Chain**
tab in the existing `InstructorDashboard`. It shows the per-team SC table +
resilience audit, an inject-event control, and the resilience-weight override
editor. Wired to the real endpoints via `api/sc.js` (instructor helpers) — no
mock data, honest empty states.

## 5. Acceptance
- Backend tests: injection → real `SupplierState` on next advance; panel
  aggregation returns real per-team data; tenancy (`IsInstructor` blocks students).
- Browser (puppeteer, :8014): instructor opens the SC tab, sees per-team resilience,
  injects an event, advances the round, and the injected disruption shows on a
  team's next-round state. Screenshots in `specs/reports/cc-16/`.
- `manage.py check` clean; migrations applied; full suite green.
