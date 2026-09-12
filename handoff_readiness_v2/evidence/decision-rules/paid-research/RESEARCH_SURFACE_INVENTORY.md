# Research surface inventory — paid market research

Builder inventory for the "make market research a paid mechanic" handoff.
Date: 2026-09-12. Branch: `crv2-paid-research-reports` (base `e1b744c`).

Assembled from the registries, not from memory: `core/urls.py` (the URL conf,
781 routes), the model registry via `core/models/__init__.py`, the manifest
registry `core/services/manifest_sections.py`, the read registry
`core/services/read_inventory.json`, and a frontend grep over
`frontend/globalstrat-frontend/src`.

Every row is **changed**, **covered** (already correct, no edit) or
**exempt** with a rationale.

---

## A. Research read surfaces (from `core/urls.py`)

| # | Surface | Registry line | Disposition |
|---|---|---|---|
| A1 | `api/games/<g>/teams/<t>/research/reports/<report_type>/` → `ResearchReportsView.get` | `urls.py:371-372` | **changed** — returns purchase state + price; withholds paid content until bought |
| A2 | `api/games/<g>/teams/<t>/research/query/` → `ResearchQueryView.post` (`core/rag/views.py:214`) | `urls.py:311-312` | **changed** — priced per query, charged like a report |
| A3 | `api/games/<g>/teams/<t>/research/queries/` → `ResearchQueriesListView.get` | `urls.py:347-348` | **exempt** — re-reads answers already paid for. Charging again would violate rule 2 (buy once) and rule 6 (stays readable after close). |
| A4 | `api/games/<g>/instructor/research-queries/` → `InstructorResearchQueriesView` | `urls.py:334-335` | **exempt** — instructor oversight of what teams asked. Not a team purchase surface. |

`report_type` is dispatched at `research_reports.py:127-138`: `segments`,
`products`, `markets`, `channels`, `stakeholders`. There is no other
research route in the URL conf, and no DRF router registration for one.

## B. Write paths that would charge

| # | Path | Disposition |
|---|---|---|
| B1 | **new** `research/reports/<report_type>/purchase/` (POST) | **changed** — the only surface that charges. Explicit POST, never a GET. |
| B2 | `core/services/funding_need.py::decision_outlays` (`:80`) | **changed** — new `research` line. Half of the V2-024 pair. |
| B3 | `core/engine/costs.py::calculate_operating_expenses` (`:373`) | **changed** — `research_expense` accumulated from the same rows (was hardcoded `D('0')` at `:650`); the V2-024 parity assertion at `:581-590` extended to cover research. |
| B4 | `core/services/rd_costs.py::committed_outlay` / `budget_assessment` (`:302`/`:328`) | **changed** — purchases become their own committed line, parallel to `platform_development`. |
| B5 | `core/engine/bootstrap.py:243` seeds `research_expense=0` for round 0 | **exempt** — round 0 precedes any submission, so no purchase can exist. Also held by another builder; left untouched. |
| B6 | `core/engine/financials.py:96,107-111,367` | **covered** — already reads `research_expense` into `total_opex`, into `operating_income`, into `cash_closing` (`:457`) and onto `RoundResultFinancials.research_expense` (`core/models/results_financials.py:64`). Nothing to change; it was only ever starved of a value. |

**Deliberately not a charge path:** `DecisionBudgetAllocation.research_budget`
(`core/models/decisions.py:56`). It stays a declaration that feeds coherence
scoring, exactly like `marketing_budget` and `strategy_budget` (A5/R14:
budgets declare, decisions spend). Purchases are **not** written to it.

## C. Displays of research cost

| # | Surface | Disposition |
|---|---|---|
| C1 | `core/views/decisions.py:1308` — decision-summary `research_allocated` | **covered** — the declared bucket, unchanged. Gains a sibling `research_spent`. |
| C2 | `core/views/decisions.py:2299` — finance-context `research_allocated` | **covered** — same. Both derive from `budget_assessment`, so B4 reaches them with no extra plumbing. |
| C3 | `components/BudgetBar.js:19-23` | **changed** — hardcoded to three categories; research is invisible today. Feeds Finance, Summary and Dashboard at once. |
| C4 | `components/design-system/DSBudgetBar.jsx:15-19` | **changed** — a second, parallel bar hardcoded to the same three. Must change together or the two bars disagree. |
| C5 | `pages/MarketResearchPage.js` — six tabs (`:1047-1084`) | **changed** — price before buying, bought/unbought state, purchase action. |
| C6 | `pages/StrategyToolsPage.js:230,457,687,860` — four `markets` fetches | **covered** — these are outside the research UI and must not break or bill. The locked GET payload keeps market identity (name/code), so these call sites keep working unpaid. |
| C7 | `components/GameStatusBar.js:51-55` | **exempt** — the top strip reports the three *declared* budget buckets. A research purchase is decision spend; it surfaces through committed/unallocated, not as a fourth declared bucket. |
| C8 | `pages/FinancePage.js:319-336` allocation inputs | **exempt** — the three budget inputs are declarations. Adding a research *input* would re-introduce the bucket as a gate, which rule 5 forbids. |

**Pre-existing gap recorded here because the mechanic depends on it:**
`research_allocated` is emitted by both backend payloads but rendered by
nothing in the frontend (grep: zero hits across `frontend/`). Research spend
is invisible on every screen today.

## D. Determinism, audit and disclosure

| # | Surface | Disposition |
|---|---|---|
| D1 | `manifest_sections.py:359` `decision_research` → `DecisionResearchAllocation` | **covered** — left exactly as is. The dead model keeps its section and its natural key `('submission_id','market_id')`. |
| D2 | **new** manifest section for the purchase model | **changed** — a new row in `DECISION_SECTIONS`, and therefore a new section in the competitive output envelope. |
| D3 | `MANIFEST_SCHEMA_VERSION` (`core/services/manifest_version.py`) | **changed** — 5 → 6. A new output section changes what bytes a round hashes to, which the module docstring says is exactly when to bump. V2-052 is the finding that forbids re-defining a version in place. |
| D4 | `manifest_schema_history/PROVENANCE.json` + `manifest_schema_v6.json` | **changed** — new version needs a recorded, digest-pinned definition or its stored hashes cannot be interpreted later (`test_the_current_version_has_a_provenance_entry`). |
| D5 | `core/tests/test_manifest_determinism.py:118` `EXPECTED_OUTPUT_SECTIONS` | **changed** — the enumerated competitive set is asserted exactly; a new section must be declared there. |
| D6 | `core/services/read_inventory.json` | **changed** — regenerated. The purchase model is named `Decision*`, so `decision_models()` (`read_inventory.py:56-68`) picks it up and any GET view mentioning it becomes a sensitive read route. A1 is already listed (`research_reports.ResearchReportsView`, `logged: true`). |
| D7 | `DecisionAuditEvent` via `record_decision_event` (`core/services/competition_audit.py:7`) | **changed** — every purchase writes one, on the same path every other decision write uses. |

## E. Model registry

| # | Model | Disposition |
|---|---|---|
| E1 | `DecisionResearchAllocation` (`core/models/decisions.py:414`) | **covered** — untouched. Still unread and unwritten by any code path; its serializer (`core/serializers/decisions.py:646`) and admin registration stay as they are. |
| E2 | **new** `DecisionResearchPurchase` | **changed** — new model in a new module, so the held `core/models/decisions.py` is not edited. |

## Files held by other builders

Confirmed by diffing the live branches against `e1b744c`:

- `core/views/decisions.py`, `core/serializers/decisions.py`,
  `core/models/decisions.py`, `core/utils/participant_messages.py`,
  the three `backend/scenarios/*.yaml`, both locale files,
  `core/services/read_inventory.json`, `core/tests/test_audit_integrity.py`,
  and migration `0085_price_band_blank_price.py` — **`crv2-10-stage5-price-band`**
- `core/engine/bootstrap.py` — **`crv2-11-round-zero-and-preferences`**
- both locale files — also **`crv2-10-stage6-cohort-caps`**

Avoided entirely: `core/views/decisions.py`, `core/serializers/decisions.py`,
`core/engine/bootstrap.py`, `core/models/decisions.py`.
Unavoidable and kept minimal, appended at the end of their blocks:
`participant_messages.py`, the three scenario YAMLs, the two locale files.
Migration numbered **0086** to avoid a filename collision with Stage 5's 0085.
