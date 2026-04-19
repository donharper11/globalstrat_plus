# CC-5 §5.3 — Instructor Panel Audit

*Produced 2026-04-17. 28 instructor surfaces classified (backend only; frontend routed to CC-16).*

## Summary

| Classification | Count |
|---|---|
| KEEP | 25 |
| EXTEND | 3 |
| NEW-NEEDED | 2 |
| DISCARD | 0 |
| **Total (existing)** | 28 |

Assumption check: KEEP is 89% of existing surfaces — matches the "~90%" working assumption from §4.3.

## Classification table

| Surface | Type | Classification | Rationale | CC-16 scope? |
|---|---|---|---|---|
| `core/views/instructor.py::InstructorActionViewSet` | viewset | KEEP | Generic action audit log | — |
| `core/views/instructor.py::InstructorEvaluationViewSet` | viewset | KEEP | Generic evaluation records | — |
| `core/views/instructor.py::InstructorNoteViewSet` | viewset | KEEP | Generic annotation | — |
| `core/views/instructor.py::InstructorFeedbackTemplateViewSet` | viewset | KEEP | Generic reusable templates | — |
| `core/views/instructor.py::InstructorScenarioCustomizationViewSet` | viewset | EXTEND | Needs class-level overrides for progressive disclosure + resilience weights per CC-06 §3.2/§3.3 | yes — CC-16 |
| `core/views/instructor.py::AdminActionViewSet` | viewset | KEEP | Generic audit | — |
| `core/views/results_api.py::InstructorDashboardView` | view | KEEP | Round overview works for SC | — |
| `core/views/results_api.py::InstructorAdvanceRoundView` | view | KEEP | Delegates to engine; no SC UI layer needed | — |
| `core/views/results_api.py::InstructorInjectEventView` | view | EXTEND | Needs SC event category filtering + compliance-regime-aware library per CC-03 §8 | yes — CC-16 |
| `core/views/results_api.py::InstructorExtendDeadlineView` | view | KEEP | Generic time management | — |
| `core/views/results_api.py::InstructorResearchQueriesView` | view | KEEP | Generic RAG visibility | — |
| `core/views/results_api.py::InstructorEventTemplatesView` | view | KEEP | Catalog works for SC events | — |
| `core/views/results_api.py::InstructorTeamBriefingsView` | view | KEEP | Generic narrative display | — |
| `core/views/results_api.py::InstructorTeamDecisionsView` | view | EXTEND | Serializer must expose SC decision models + respect progressive disclosure overrides | yes — CC-16 |
| `core/views/instructor_alerts.py::InstructorAlertsView` | view | KEEP | CC-21 alert feed works for SC | — |
| `core/views/instructor_alerts.py::InstructorAlertAcknowledgeView` | view | KEEP | Generic state management | — |
| `core/views/instructor_alerts.py::InstructorAlertSummaryView` | view | KEEP | Generic aggregation | — |
| `core/views/instructor_alerts.py::TeamChangesView` | view | KEEP | Generic audit log | — |
| `core/views/team_config.py::InstructorTeamConfigView` | view | KEEP | Home market / name management is foundational | — |
| `core/views/team_config.py::InstructorRandomizeHomeMarketsView` | view | KEEP | Scenario setup utility | — |
| `core/views/decisions.py::DecisionUnlockView` | view | KEEP | Generic submission state | — |
| `core/views/cc32a_views.py::InstructorCommunicationsView` | view | KEEP | CC-32A communications view; generic | — |
| `core/views/grading.py::GradingRubricViewSet` | viewset | KEEP | Generic grading CRUD | — |
| `core/views/grading.py::TeamGradeViewSet` | viewset | KEEP | Generic grading records | — |
| `core/views/grading.py::StudentGradeAdjustmentViewSet` | viewset | KEEP | Generic grade overrides | — |
| `core/views/grading.py::OverrideGradeView` | view | KEEP | Manual adjustment endpoint | — |
| `core/views/grading.py::CalculateGradesView` | view | KEEP | Generic grade calculation | — |
| `core/views/grading.py::ExportTeamGradesCsvView` | view | KEEP | Generic CSV export | — |

(The remaining grading sub-views — SeedRubricView, StudentGradesView, ComponentLabelsView, ExportStudentGradesCsvView, GradingRubricCategoryViewSet, GradingComponentMappingViewSet — are all KEEP: generic grading infrastructure, no SC surface.)

## EXTEND — details

### 1. `InstructorInjectEventView` (results_api.py)
- **Current:** manually fire any event template against a team/market.
- **SC needs (CC-03 §8):** visibility into SC event categories (supply chain disruption, compliance, resilience); compliance-regime-filtered event library; preview of SC state impact before injection.
- **CC-16 work:** UI filter by SC category; include compliance-regime toggle in the catalog; show impact preview.

### 2. `InstructorTeamDecisionsView` (results_api.py)
- **Current:** serializes all decision categories in plaintext view.
- **SC needs (CC-16):** extend serializer to expose SC-specific decision fields (supplier selections, lane hedges, compliance choices, resilience actions); conditional field disclosure based on progressive-disclosure schedule overrides from CC-06 §3.2.
- **CC-16 work:** extend serializer; add disclosure-schedule check before including SC fields in response.

### 3. `InstructorScenarioCustomizationViewSet` (instructor.py)
- **Current:** generic per-scenario parameter overrides.
- **SC needs (CC-06 §3.2 and §3.3):** class-level overrides for (a) progressive disclosure unlock schedules per field, (b) resilience score weight overrides per component.
- **CC-16 work:** either extend this viewset with sub-endpoints for `ClassProgressiveDisclosureOverride` and `ClassResilienceWeightOverride`, or split into two dedicated viewsets.

## NEW-NEEDED (identified from spec cross-reference)

### 1. Resilience Score Audit Dashboard
- **What:** instructor view showing per-team resilience score breakdown — multi-sourcing, geographic diversity, buffer adequacy, modal flexibility, tier-2 visibility, supplier financial health.
- **Why:** CC-06 §3.3 and CC-21 require instructor calibration of weights; instructors need component-level breakdowns to verify pedagogical intent.
- **Proposed endpoint:** `GET /api/games/{game_id}/instructor/teams/{team_id}/resilience-audit/` returning component scores and current class weight overrides.
- **Data model:** read-only aggregation of `ResilienceScoreHistory` (CC-4 §4.3.5) + class weight overrides.

### 2. Compliance Regime Enforcement Override
- **What:** per-class regime toggle viewer/updater (CBAM tariff rate, UFLPA enforcement mode, etc.).
- **Why:** CC-06 pedagogical design requires instructors to control which compliance rules are active per class — some courses want full UFLPA rigor; others want tariff-only.
- **Proposed endpoints:** `GET` regime toggle state, `PUT` to update (class configuration scope).
- **Data model:** `ClassComplianceRegimeOverride` — will need to be added to CC-4 or via a CC-4 amendment before CC-16 can build the view.

## CC-16 handoff summary

The instructor panel inherits wholesale from the GlobalStrat backend — 25 of 28 existing surfaces work as-is. Three EXTEND targets require surgical additions: event-injection gets SC category awareness, team-decisions serializer gets SC decision visibility with progressive-disclosure gating, and scenario-customization adds two nested override resources. Two entirely new endpoints must be built: a resilience audit dashboard (for CC-06 weight calibration) and a compliance regime override (for per-class enforcement toggling). The compliance override depends on a new `ClassComplianceRegimeOverride` model that does not exist yet — CC-16 should flag this as a prerequisite, routed to a CC-4 amendment or CC-6 data-model extension.

No backend surface was classified DISCARD. No frontend work is in scope for CC-5 — all CC-16 frontend work proceeds independently against this backend surface.
