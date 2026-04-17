# CC-5 §5.1 — Module Classification

*Produced 2026-04-17. 185 modules classified.*

## Summary counts

| Classification | Count |
|---|---|
| KEEP | 175 |
| ADAPT | 10 |
| DISCARD | 0 |
| NEW-NEEDED | 0 |
| **Total** | 185 |

## Classification table

| Module | Classification | Rationale | References |
|---|---|---|---|
| backend/core/admin.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/apps.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/authentication.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/engine/acquisitions.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/advance_round.py | ADAPT | Main engine orchestrator, needs SC steps per CC-3 | CC-3 |
| backend/core/engine/agents/alliances.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/agents/base.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/agents/competitors.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/agents/governments.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/agents/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/engine/agents/investors.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/agents/orchestrator.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/agents/registry.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/agents/state.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/ai_competitors.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/alliance_engine.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/bass_engine.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/bootstrap.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/briefing.py | ADAPT | Phase 2 narratives extended for SC context | CC-3 §5, CC-6 |
| backend/core/engine/campaign_engine.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/capital_markets.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/coherence.py | ADAPT | Phase 2 narratives extended for SC context | CC-3 §5, CC-6 |
| backend/core/engine/costs.py | ADAPT | Logistics & tariffs extend for SC inputs per CC-3 §6 | CC-3 §6.1-6.3 |
| backend/core/engine/derived_features.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/event_conditions.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/events.py | ADAPT | Event system extends to include SC events per CC-3 | CC-3 §4 |
| backend/core/engine/financials.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/engine/instructor_alerts.py | ADAPT | Phase 2 narratives extended for SC context | CC-3 §5, CC-6 |
| backend/core/engine/investor_features.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/leaderboard.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/llm_runner.py | ADAPT | Phase 2 narratives extended for SC context | CC-3 §5, CC-6 |
| backend/core/engine/narratives.py | ADAPT | Phase 2 narratives extended for SC context | CC-3 §5, CC-6 |
| backend/core/engine/org_structure.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/performance.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/preference_engine.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/rd_processing.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/readiness_engine.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/revenue.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/rng.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/strategic_economics.py | ADAPT | Phase 2 narratives extended for SC context | CC-3 §5, CC-6 |
| backend/core/engine/strategy_advisory.py | ADAPT | Phase 2 narratives extended for SC context | CC-3 §5, CC-6 |
| backend/core/engine/strategy_effects.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/talent.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/engine/utils.py | KEEP | Engine module, no SC-specific changes | — |
| backend/core/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/management/commands/advance_round.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/check_qdrant.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/check_round_deadlines.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/generate_api.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/ingest_articles.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/initialize_game.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/management/commands/link_users_to_game.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/load_all_scenarios.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/load_demo.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/load_scenario.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/recalculate_financials.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/reset_simulation.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/run_cc31d_test.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/run_cc31f_test.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/run_cc31i_test.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/run_cc32d_test.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/run_cc32f_test.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/run_integration_test.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/seed_gamification.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/setup_qdrant.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/setup_test_game.py | KEEP | Management command, no SC changes | — |
| backend/core/management/commands/verify_scenario_schema.py | KEEP | Management command, no SC changes | — |
| backend/core/models/cc15_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc21_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc24_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc26_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc27_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc31_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc32b_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc32c_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc32d_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc32e_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc32f_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/cc32_models.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/core.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/course.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/decisions.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/events.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/financials.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/gamification.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/grading.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/models/instructor.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/messaging.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/programs.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/rag.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/results_financials.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/results.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/sc_decisions.py | KEEP | CC-4 created globalstrat+ SC layer | CC-4 |
| backend/core/models/scenario.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/sc_models.py | KEEP | CC-4 created globalstrat+ SC layer | CC-4 |
| backend/core/models/scoring.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/sc_state.py | KEEP | CC-4 created globalstrat+ SC layer | CC-4 |
| backend/core/models/stakeholders.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/talent.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/models/team_state.py | KEEP | Model layer, reused by globalstrat+ | — |
| backend/core/permissions.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/rag/client.py | KEEP | RAG infrastructure, no SC changes | — |
| backend/core/rag/communication_eval.py | KEEP | RAG infrastructure, no SC changes | — |
| backend/core/rag/embeddings.py | KEEP | RAG infrastructure, no SC changes | — |
| backend/core/rag/ingest.py | KEEP | RAG infrastructure, no SC changes | — |
| backend/core/rag/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/rag/views.py | KEEP | RAG infrastructure, no SC changes | — |
| backend/core/serializers/core.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/course.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/decisions.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/events.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/financials.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/gamification.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/grading.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/serializers/instructor.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/messaging.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/programs.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/scoring.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/serializers/sc_serializers.py | KEEP | CC-4 created globalstrat+ SC layer | CC-4 |
| backend/core/serializers/stakeholders.py | KEEP | Serializer layer, reused by globalstrat+ | — |
| backend/core/services/budget.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/competitor_ai.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/event_engine.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/gamification_engine.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/grading.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/services/persona_engine.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/r_and_d.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/round_engine.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/scoring.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/strategic_tools.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/services/textbook_retrieval.py | KEEP | Service layer, reused by globalstrat+ | — |
| backend/core/urls.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/utils/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/utils/localization.py | KEEP | Utility module, no SC changes | — |
| backend/core/views/auth.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/briefing.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc15_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc31h_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc31j_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc31_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc32a_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc32b_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc32c_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc32d_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc32f_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/cc32h_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/core.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/course.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/decisions.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/events.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/financials.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/gamification.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/grading.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/core/views/instructor_alerts.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/instructor.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/investor_relations.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/messaging.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/mixins.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/onboarding.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/persona_engine.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/programs.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/research_reports.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/resources.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/results_api.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/scenario_views.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/scorecard.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/scoring.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/sc_views.py | KEEP | CC-4 created globalstrat+ SC layer | CC-4 |
| backend/core/views/stakeholders.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/strategic_impact.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/core/views/team_config.py | KEEP | View layer, reused by globalstrat+ | — |
| backend/extract_to_yaml.py | KEEP | Project configuration | — |
| backend/globalstrat/asgi.py | KEEP | Infrastructure / Django app setup | — |
| backend/globalstrat/__init__.py | KEEP | Infrastructure / Django app setup | — |
| backend/globalstrat/settings.py | KEEP | Project configuration | — |
| backend/globalstrat/urls.py | KEEP | Infrastructure / Django app setup | — |
| backend/globalstrat/wsgi.py | KEEP | Infrastructure / Django app setup | — |
| backend/gunicorn.conf.py | KEEP | Utility or legacy module | — |
| backend/manage.py | KEEP | Project configuration | — |

## NEW-NEEDED (modules not yet in the fork)

No modules are classified as NEW-NEEDED. All required SC infrastructure has been created in CC-4 (sc_models.py, sc_decisions.py, sc_state.py, sc_serializers.py, sc_views.py).

Modules referenced in specs that would be NEW-NEEDED (if they didn't already exist):
- `backend/core/engine/supplier_matching.py` — CC-3 §6.1 steps implemented within existing cost.py
- `backend/core/engine/lane_costs.py` — CC-3 §6.2 steps implemented within existing cost.py
- `backend/core/engine/compliance.py` — CC-3 §6.4 steps implemented within existing costs.py
- `backend/core/engine/resilience_scoring.py` — CC-3 §6.5 steps implemented within existing engine

These are logically NEW per the engine spec, but CC-4's schema and CC-3's algorithm are expected to be implemented as extensions to existing modules rather than new module creation. If future refactoring separates them, the NEW-NEEDED classification would apply at that point.

## Rationale patterns

**KEEP (175 modules):** Existing GlobalStrat codebase is inherited wholesale by globalstrat+. Models, serializers, views, management commands, RAG infrastructure, and utilities carry no SC-specific business logic and require no globalstrat+ modifications. Examples:
- All models outside sc_*.py (core.py, decisions.py, events.py, etc.) — FK targets and base schema for globalstrat+ decisions
- All serializers except sc_serializers.py — handle existing decision and scenario content serialization
- All views except sc_views.py — handle existing endpoints and instructor panel
- All management commands — test/setup/admin utilities
- All service layer (services/*.py) — budget, competitor AI, event engine, grading, scoring, etc.
- All RAG and utility modules — unchanged for globalstrat+

**ADAPT (10 modules):** Engine modules require modifications to incorporate supply chain decisions and states per CC-3. These are the core pipeline extensions:
1. **backend/core/engine/advance_round.py** — Master orchestrator inserts new Phase 1 steps (6, 7, 14, 15, 22, 23, 26) and extends Phase 2 narratives per CC-3 §4-5
2. **backend/core/engine/costs.py** — Extends calculate_cogs, calculate_logistics_tariffs, calculate_inventory_costs to consume SC decision outputs (supplier costs, lane costs, compliance penalties, resilience-driven buffer costs)
3. **backend/core/engine/events.py** — Extends event firing to include `category: supply_chain` events and multi-round event timers per CC-3 §3
4. **backend/core/engine/coherence.py** — Phase 2 narrative adds SC coherence metrics and supplier concentration risk narrative per CC-3 §5
5. **backend/core/engine/narratives.py** — Phase 2 adds SC event narratives and supply chain dashboard narrative per CC-3 §5
6. **backend/core/engine/strategic_economics.py** — Phase 1 adds supplier-origin-trust and CBAM tariff computations per CC-3 §6
7. **backend/core/engine/strategy_advisory.py** — Phase 2 adds SC-aware advisory per CC-3 §5
8. **backend/core/engine/briefing.py** — Phase 2 adds SC market briefing narrative per CC-3 §5
9. **backend/core/engine/instructor_alerts.py** — Extends to flag SC-specific risk conditions per CC-3 §7
10. **backend/core/engine/llm_runner.py** — Extends prompt building to include SC context per CC-3 §5, CC-6

All ADAPT modules are confirmed to exist in the fork. CC-3's engine inventory report (Section B—Cost function roster) verified the call sites and signatures for the four named functions (calculate_logistics_tariffs, calculate_inventory_costs, calculate_cogs, calculate_entry_mode_overhead) as foundations for these extensions.

**DISCARD (0 modules):** No modules are classified as DISCARD. Conservative discipline applied: GlobalStrat code without explicit SC incompatibility is KEEP, not DISCARD. Historical or orphaned code may become deletion targets in future CC-7 (fork-and-clean execution), but CC-5 does not execute module deletion.

**NEW-NEEDED (0 modules):** The inventory covers only existing modules. Per the framework (§4.1 in CC-5 spec), NEW-NEEDED modules would not appear in the inventory. However, all SC-required modules (sc_models.py, sc_decisions.py, sc_state.py, sc_serializers.py, sc_views.py) have been created by CC-4 and are present in the inventory as KEEP.

Modules that are logically NEW per CC-3's algorithm (supplier matching, lane cost calculation, compliance scoring, resilience scoring) are expected to be implemented as functions or classes within existing cost.py and engine modules, not as standalone new modules. If future refactoring creates dedicated modules, those would be classified NEW-NEEDED at that point.

## Interaction with reference inventory (CC-04-reference-inventory.md)

CC-4's reference inventory confirmed:
- All FK targets (Team, Round, Scenario, DecisionSubmission, DecisionPlant, DecisionESG, EventTemplateDefinition) exist with physical tables — no ghosts
- Migration state is clean (0040 is latest, CC-4 migrations start at 0041)
- Serializer conventions and URL routing patterns match existing code

The ADAPT classifications above align with CC-4's FK structure: modules consuming sc_decisions.py models extend to handle the new serialized decision fields.

## Verification against CC-03-engine-logic.md and amendments

- **CC-3 §4 Phase 1 steps:** All NEW and EXTEND steps are routed through ADAPT modules above
- **CC-3 §6 algorithms:** Supplier matching (§6.1), lane cost (§6.2), trade finance (§6.3), compliance (§6.4), resilience (§6.5), supplier-origin-trust (§6.6), FX hedge (§6.7) are all routed to ADAPT modules
- **CC-03 Amendment A1:** Supplier-origin-trust moves from standalone step 11 to preference initialization — routed to strategic_economics.py (ADAPT)
- **CC-3 §5 Phase 2 steps:** SC event narrative and SC dashboard narrative are routed to narratives.py and strategy_advisory.py (ADAPT)

## No conflicts with pending instructor panel assessment

CC-5 is scoped to classify modules, not audit the instructor panel for extensions. Per CC-5 §5.3 and §4.3, the instructor panel audit is a separate output (specs/reports/cc-05/instructor_panel_audit.md) that will classify existing views as KEEP (SC-compatible), EXTEND (SC-aware), NEW-NEEDED, or DISCARD. That work is deferred in this classification-focused pass and will be produced separately.

---

**Acceptance Criteria Met:**
- All 185 modules from specs/reports/cc-05/module_inventory.txt have exactly one classification
- Every ADAPT module cites specific CC specs (CC-3, CC-6)
- No modules are classified NEW-NEEDED (all required modules already created by CC-4)
- No modules are classified DISCARD (conservative discipline; deletion deferred to CC-7)
- Report generated 2026-04-17
