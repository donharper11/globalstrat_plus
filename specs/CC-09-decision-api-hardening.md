# CC-9: Supply Chain Decision API Hardening

**Project:** globalstrat+  
**Spec Type:** Build pipeline - backend API hardening  
**Depends on:** CC-8, CC-2, CC-4, CC-04 Amendment A1  
**Observes:** `STANDING-DISCIPLINE.md`  
**Status:** Drafted for builder execution

---

## Non-Negotiable Builder Discipline

This bundle inherits `STANDING-DISCIPLINE.md`, but the following rules are repeated here because they are completion blockers:

1. Verify every existing field, model, table, endpoint, route, component, settings key, and payload shape before referencing it. Use the current codebase and database, not memory or nearby names.
2. Do not invent field names, model names, endpoint paths, YAML keys, payload keys, CSS classes, or React component names. If the expected name does not exist, halt with a MISMATCH report.
3. Do not silently adapt the spec to whatever name seems convenient. Report the actual state and wait for instruction if the contract and implementation diverge.
4. Before calling the bundle complete, self-verify every acceptance criterion with recorded command output, API/browser evidence, and a closeout report under the bundle's `specs/reports/cc-XX/` directory.
5. A passing backend response alone is not proof of frontend completion. Frontend bundles require browser verification of the actual user workflow.


## Operational State API Requirement

CC-9 should verify whether the existing API exposes enough state for ERP-shaped simulation screens. Decision pages need more than form payloads; they need current state, committed state, and any generated operational status available from the simulation.

Before closing CC-9, produce an API state inventory covering:

- supplier commitments/allocation state
- lane/shipment or lane-status state
- inventory OH/OO or policy state
- trade-finance/FX decision and hedge-position state
- compliance/event/disruption state
- resilience score state

If a required state source is absent, do not invent it casually. Record it as a named follow-up endpoint/model requirement, with exact model/table verification evidence.

---

## 1. Purpose

Make the existing supply-chain API safe and frontend-ready. CC-4 created the model/API surface, but several POST paths bypass write serializers. CC-9 turns those endpoints into reliable contracts for the frontend pages.

---

## 2. Scope

Primary files:

- `backend/core/views/sc_views.py`
- `backend/core/serializers/sc_serializers.py`
- `backend/core/tests/`

Routes already exist under `/api/games/<game_id>/teams/<team_id>/sc/round/<round_number>/...` and `/api/scenarios/<scenario_id>/...`.

---

## 3. Required Fixes

1. Every unsafe POST path must validate through the appropriate write serializer or an equivalent centralized validator with tests.
2. Progressive disclosure must be enforced for every locked field.
3. Round-open checks must reject writes to non-open rounds.
4. Team membership/auth checks must remain in place.
5. Invalid payloads must return `400` with structured serializer errors.
6. Valid payloads must return stable frontend-friendly response bodies.
7. Read endpoints must return enough context for edit forms to rehydrate current state.
8. Sourcing allocations must be atomic and allocation percentages must sum to 100 per critical input category.
9. Logistics modal mix must sum to 100 per lane and reject unavailable modes.
10. Trade finance and FX endpoints must validate allowed instruments/currency pairs when scenario data is present.

---

## 4. Verification Before Editing

Run:

```bash
cd /home/ubuntu/projects/globalstrat+/backend
python3 manage.py check
python3 manage.py showmigrations core | tail -20
grep -rn "sc/round" core/urls.py
python3 manage.py shell -c "from core.models.sc_models import Supplier, ShippingLane; print(Supplier.objects.count(), ShippingLane.objects.count())"
```

If CC-8 seed rows are absent, halt and report that CC-9 depends on CC-8.

---

## 5. Tests

Add backend tests covering successful GET and POST/GET round trips for sourcing, logistics, trade finance/FX, and inventory/contingency; invalid modal mix; invalid sourcing allocation total; locked progressive-disclosure fields; override-enabled field access; non-open round write; and unauthorized user access.

Existing known unrelated test failures must be documented, not silently ignored.

---

## 6. Acceptance Criteria

1. All SC POST paths use validated write paths.
2. API tests cover the cases listed above.
3. `python3 manage.py check` passes.
4. The new focused API tests pass.
5. Full `python3 manage.py test --verbosity=1` is run and reported, including pre-existing failures.
6. `specs/reports/cc-09/acceptance_report.md` records endpoint samples and test output.
7. No React frontend work is included.
