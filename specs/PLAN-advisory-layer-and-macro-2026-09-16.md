# Plan: Advisory Layer and Macro Layer for globalstrat+

**Status:** Draft plan, 2026-09-16. Not a CC spec. Proposes two CC specs (numbering below) and the preparatory work that needs no spec.
**Observes:** `specs/STANDING-DISCIPLINE.md` (inventory before wiring, no invented names, report mismatches).
**Branch context:** `crv2-release-integration` has uncommitted edits to `llm_runner.py`, `narratives.py`, `narrative_jobs.py` and their tests (proxy-migration work in another session). Workstream 1 depends on those landing first and must not touch those files until they are committed.

---

## 0. Verified starting state

Everything below was checked against the working tree, the Qdrant host and the LiteLLM host on 2026-09-16.

| Item | Finding |
|---|---|
| Persona engine | `backend/core/services/persona_engine.py` (1,273 lines): 5 CSR personas, threaded consults, caps. Imports legacy `SimulationState`, `Program`, `Score`, `TriggeredEvent`, `LeaderboardScore`. Own `requests` call to DashScope (`call_llm`, line 730). Routes mounted at `core/urls.py:253-257`; not referenced by `frontend/globalstrat-frontend/src`. |
| Situation detection | `core/engine/strategy_advisory.py`: ten detectors, `build_strategy_context(team, game, round_number)` at line 1104. |
| LLM routing | `core/engine/llm_runner.py` routes to the LiteLLM proxy when `NARRATIVE_LLM_URL` and `NARRATIVE_LLM_KEY` are set; aliases `analyst` (thinks) and `tutor` (does not) mapped in `narratives.py:84-102`. `backend/.env` currently has DashScope only. |
| Bypasses | `core/rag/views.py:synthesize_research_brief` and `core/engine/briefing.py:_rag_enhance_recommendation` call the DashScope SDK directly. |
| Article RAG | Qdrant `192.168.50.186:6333`, collection `globalstrat_plus_articles`: 475 points, 26 documents, MiniLM 384-dim. Ingested from `docs/rag_sources/staging` (27 PDFs), all 27 of which also exist in `/home/ubuntu/projects/articles` (149 files). |
| Textbook RAG | `core/services/textbook_retrieval.py`: collection `globalstrat_textbook`, bge-m3 1024-dim, host and model hardcoded at lines 21-24. |
| Disclosure | `core/utils/disclosure.get_effective_unlock_round(game, field_path)` honours per-class overrides. |
| Grading precedent | `core/rag/communication_eval.evaluate_communication` persists a score at submit time with a deterministic fallback; Phase 1 reads it (`coherence.py:145-155`). `narrative_jobs.require_safe_rag_configuration` refuses to resolve if RAG could touch a hashed field. |
| Instructor steering | `MarketConditionByRound.rag_source_tags` (scenario.py:436) already filters retrieval per market-round. |
| Macro | None. `MarketEffectiveState` (utils.py:276) seeds growth, FX and tariff from scenario constants; `update_market_conditions` (events.py:332) stacks authored per-round modifiers and event modifiers. `exchange_rate_volatility` (scenario.py:139) is never read. Interest is flat `debt_interest_rate` (costs.py:669). Share price is book value times a sentiment band, clamped 20 percent per round (capital_markets.py:215-270). |
| Determinism | Phase 1 never consumes LLM output. Competitive hash covers the sections in `core/services/manifest_sections.py`; `test_manifest_determinism` fails if a table is added without registration. |
| Spec numbering | `CC-SEQUENCE-PLAN.md` runs to CC-39. Proposed: **CC-40 Advisory Layer**, **CC-41 Macro Layer**. |

---

## 1. Workstream 1: Re-point the persona engine (proposed CC-40, part A)

Goal: the existing threaded consultation engine becomes the advisor layer for globalstrat+, grounded in this team's situation, routed through the shared runner, strictly Phase 2 or on demand.

### 1.1 Inventory first
Produce `specs/reports/CC-40-persona-inventory.md`: every legacy model read in `persona_engine.py` and `views/persona_engine.py`, the globalstrat source that replaces it, and confirmation that `Message` (`core/models/messaging.py`) is neither in `INPUT_SECTIONS` nor `NARRATIVE_SECTIONS`.

### 1.2 Data sources
| Legacy read | Replacement |
|---|---|
| `SimulationState` current round (`_get_current_round`) | `Game.current_round`, `Round.status` |
| `Program`, `ProgramType`, `Score` | `RoundResultFinancials`, `RoundResultProductMarket`, `TeamMarketCompliance`, `HedgePosition`, `resilience` results |
| `TriggeredEvent` | `EventInstance`, `SCEventInstance` |
| `LeaderboardScore` | leaderboard results table used by `leaderboard.py` |
| `_build_team_context` | `strategy_advisory.build_strategy_context(team, game, round_number)` plus a compact financial and market summary |

Thread scoping: `Message.recipient_type='Team'`, `recipient_id=team.id`, `instance_id=game.id`. Verify no other reader of `instance_id` conflicts.

### 1.3 Personas
Replace the five CSR personas with a roster drawn from the library's subject clusters. Each persona is a name, a stance, a tag filter over the unified collection, and a model tier.

| Key | Role | Tag filter | Tier |
|---|---|---|---|
| strategy | Chief strategy advisor | strategy, framework, competitive | tutor |
| expansion | International expansion | market_entry, country_selection, mne | tutor |
| political_risk | Political and country risk | political_risk, trade_policy, emerging_market | tutor |
| cmo | Marketing and consumer insight | marketing, consumer, brand | tutor |
| cfo | Finance | finance, ratios, hedging | tutor |
| counsel | Ethics, governance, legal | ethics, governance, law | tutor |
| supply_chain | Supply chain and logistics | supply_chain, logistics, sourcing | tutor |
| culture | Culture and workforce | culture, sociology, organisation | tutor |
| coach | Executive coach (post-round reactions) | leadership, management | analyst |

Roster is a scenario config key (`advisors_enabled`) so a course can run a subset. Reuse the `team_home_context` variable from CC-06 §3.1 rather than hardcoding the Chinese-firm framing.

### 1.4 LLM path
- Delete `persona_engine.call_llm` and its DashScope constants. Consults and replies use `llm_runner.run_llm_batch_sync` with `model='tutor'`; post-round reactions use `model='analyst'`.
- Same change to `rag/views.synthesize_research_brief` and `briefing._rag_enhance_recommendation`. After this, no code path outside `llm_runner` names DashScope.
- Set `NARRATIVE_LLM_URL=http://192.168.50.220:4100/v1/chat/completions` and key in the deploy env. The proxy applies the thinking floor from `guardrails.py`, so do not pass `enable_thinking`.
- Wait for the uncommitted runner changes to land; then rebase.

### 1.5 Cost and write path
- Consults become purchases: add `ADVISOR_CONSULT` to `research_catalogue` with price key `advisor_consult_price` and cap `max_advisor_consults_per_round`. The consult view mixes in `CompetitionDecisionWriteMixin` exactly as `ResearchQueryView` does, with the same refund-on-failure rule.
- Unsolicited post-round reactions are free and generated in Phase 2 as a `NarrativeJob` type (`advisor_reaction`), so they get the durable worker, retries and provenance.

### 1.6 Citations
Advisor prompts cite source title and page. Requires page numbers in the payload (Workstream 2). Owner decision needed on quote versus paraphrase for licensing; default is paraphrase with attribution.

### 1.7 Frontend
`src/pages/AdvisorsPage.js` from the `MarketResearchPage.js` template: advisor picker, thread view, remaining-consults and cost display. Route in `App.js`, sidebar entry, `src/api/advisors.js`, strings in `src/locales/en` and `zh-CN`.

### 1.8 Tests and evidence
- Routing test in the style of `test_narrative_llm_routing.py`: consult goes to the proxy with `tutor`, reaction with `analyst`, key never in provenance.
- `test_manifest_determinism` unchanged and green. Re-resolve a backed-up round with advisors enabled and confirm `output_sha256` is unchanged (the drill in `handoff_readiness_v2/narrative_provider_drill.py`).
- Instructor audit route `instructor/advisor-consults/` mirroring `instructor/research-queries/`.

Estimate: 1.5 to 2 weeks after the runner changes are committed.

---

## 2. Workstream 2: The articles repo becomes the single source

Goal: one corpus, one embedding model, one collection, page-level citations.

### 2.1 Catalog
- Merge the richer metadata from `docs/rag_sources/catalog.json` (title, author, topic, tags) into `/home/ubuntu/projects/articles/catalog.json`, then retire `docs/rag_sources/staging`.
- Enrichment pass with the `fast` alias over the first two pages of each file: title, author, year, document type, subjects, frameworks, cases, regions. Human review of the output before ingestion.
- Deduplicate by content hash. Known duplicates: Bremmer political risk (4 copies), AHP (3), Alitalia (2), Africa trading blocs (2). Keep one canonical file per work and record aliases in the catalog.
- Controlled tag vocabulary written down in `docs/RAG_SOURCE_CURATION.md` (the guide CC-06 §7 defers to). Persona filters and `rag_source_tags` use only this vocabulary.

### 2.2 Embedding and collection
- bge-m3 via the LiteLLM `embed` alias (`POST http://192.168.50.220:4100/v1/embeddings`), 1024-dim, for both articles and textbook. Remove the local MiniLM path and the zh-to-en query translation in `core/rag/embeddings.py`; bge-m3 is multilingual.
- New collection `globalstrat_plus_library`. Move host, port, collection and model to settings; delete the hardcoded values in `textbook_retrieval.py`.
- Verify per STANDING-DISCIPLINE §1.6 before switching the setting; keep the old collection until the new one passes a retrieval smoke test.

### 2.3 Ingestion
- `core/rag/ingest.py`: chunk per page, carry `page`, `year`, `doc_type`, `tags`, and a `dated_fact` flag for case and report material. Point id derived from content hash so `ingest_articles` is idempotent.
- Run full ingestion of all canonical documents; record counts in the inventory report.

Estimate: 2 to 3 days. No engine risk. Do this first; it unblocks citations in Workstream 1.

---

## 3. Workstream 3: Design around the three constraints (CC-40, part B)

### 3.1 Progressive disclosure
The prompt builder computes, for every decision field an advisor could recommend, `get_effective_unlock_round(game, field_path)` and splits fields into available now and opens in round N. The system prompt instructs the advisor to speak only to available levers and to name the unlock round for anything else. Test: a round-1 team asks the CFO about hedging and receives the unlock round, not a hedge recommendation.

### 3.2 Advisory only, with a documented path to grading
Decision to lock in the CC-06 register: advisor output is advisory and never enters a hashed field. If a future course wants advisor engagement graded, it follows the `communication_eval` precedent: score persisted at submit time, deterministic fallback, Phase 1 reads the stored value. `require_safe_rag_configuration` stays as is.

### 3.3 Instructor steering
- `rag_source_tags` on `MarketConditionByRound` applies to advisor retrieval whenever the question concerns that market.
- Scenario config keys: `advisors_enabled`, `advisor_consult_price`, `max_advisor_consults_per_round`, `advisor_register` (consultancy or mentorship, answering the open tone question in CC-06 §4.7).
- Instructor audit view of consults, as in 1.8.

Estimate: 3 days, threaded through Workstream 1.

---

## 4. Workstream 4: Macro layer with a rate path (proposed CC-41)

Goal: an endogenous, seeded, deterministic macro state per market per round that FX, interest, costs, demand growth and capital markets all consume, so advisors have something moving to advise on.

### 4.1 Spec and inventory first
Draft `specs/CC-41-macro-layer.md` in the CC-03 style with an engine inventory report covering `update_market_conditions`, `_compounded_growth_factor`, `calculate_interest`, bootstrap interest, `calculate_revenue` FX use, `fx_engine`, `_calculate_share_price`, and the manifest sections they write.

### 4.2 State and configuration
- New table `market_macro_state` with natural key (game, market, round_number): `gdp_growth`, `inflation`, `policy_rate`, `exchange_rate`, `country_risk_index`, `cost_index`.
- New `MarketDefinition` fields: `inflation_base`, `policy_rate_base`, `country_risk_base`, `macro_persistence`. The existing `exchange_rate_volatility` is finally consumed.
- Scenario key `macro_enabled`, default false. With it off, the step writes the base constants and every consumer reduces to today's arithmetic. This is what keeps existing scenarios and the replay fixtures byte-identical.

### 4.3 Dynamics (Phase 1, new step between instructor overrides and event firing)
Draws come from `rng.get_rng(class_id, round_number, 'macro')` so replay is exact.
- Growth and inflation: AR(1) around base with persistence and a seeded shock.
- Policy rate: base plus a proportional response to the inflation gap.
- Exchange rate: log random walk with drift equal to the policy-rate differential against the home market per round, volatility from the scenario field, then authored `MarketConditionByRound` modifiers and event modifiers stack on top exactly as today.
- Country risk index: base plus decay toward base, shifted by political and compliance events. Feeds `regulatory_difficulty` friction and the tariff modifier.
- Cost index: cumulative inflation, feeding `base_manufacturing_cost` and logistics base cost.

### 4.4 Consumers
| Consumer | Change |
|---|---|
| `update_market_conditions` | seeds `MarketEffectiveState` from `market_macro_state` instead of scenario constants |
| `calculate_interest`, bootstrap | home `policy_rate` plus a scenario credit spread replaces flat `debt_interest_rate` |
| `calculate_cogs`, logistics | multiplied by `cost_index` |
| segment population growth | uses macro `gdp_growth` in place of `base_growth_rate` |
| `fx_engine` | unchanged; marks against a rate that now moves |
| `_calculate_share_price` | see 4.5 |

### 4.5 Capital markets: the second consumer of the rate path
Today: price equals book value times sentiment, floored and capped in a 0.70 to 1.30 band, clamped 20 percent per round. Add a valuation term that responds to the home policy rate:

- `rate_factor = ((1 + policy_rate_base) / (1 + policy_rate_current)) ** equity_duration`, with `equity_duration` a scenario constant (default around 5).
- `raw_price = book_value * sentiment * rate_factor`, then the existing floor, cap and per-round clamp, with the band re-anchor widened only by the rate factor so a rate shock can move price outside the sentiment band but never below the insolvency floor.
- Investor funds already hold a satisfaction score; growth-tolerant funds get a lower effective duration so they react less to rates. This gives the CFO advisor a real story: rates up, valuation down, more so for growth-positioned teams.

With `macro_enabled` false the rate factor is exactly 1.0.

### 4.6 Manifest and determinism
- Register `market_macro_state` in `WORLD_STATE_SECTIONS` with its natural key; the new `MarketDefinition` fields land in the existing config section. `test_manifest_determinism` must pass with no exclusions added.
- Replay drill: restore game 37 round 1, resolve with the new code and `macro_enabled` false, and confirm the competitive hash is still `129a374e…`. Then a second fixture with it true, resolved twice, hashes equal.

### 4.7 Surfaces
- Team dashboard: macro strip per market (growth, inflation, rate, FX, risk index) with last-round deltas.
- Instructor panel: per-class override of macro bases following the CC-04 A1 override pattern, and a manual shock button that writes an `ActiveModifier` so it stays inside the existing event audit.
- Advisors: `build_strategy_context` gains a macro summary; new detectors for rising rates against floating debt, FX drift beyond hedge cover, and country risk breaching a threshold, feeding the CFO and political-risk personas.

Estimate: spec 3 days; implementation 2 to 3 weeks including fixtures.

---

## 5. Sequence and dependencies

1. Workstream 2 (corpus) first. No engine risk, unblocks citations.
2. Draft CC-40 and CC-41 in parallel with Workstream 2.
3. Workstream 1 and 3 once the in-flight runner changes are committed.
4. Workstream 4 implementation after Workstream 1 lands, so the advisors have a consumer the day the macro state exists.

## 6. Decisions for the owner

- Advisor roster: names and personalities for the nine personas, or a smaller set for v1.
- Whether consults cost cash (recommended yes, same as analyst queries) and the default price.
- Quote or paraphrase from the library in advisor replies (recommended paraphrase with title and page attribution).
- `macro_enabled` default for existing scenarios (recommended false) and which scenario pilots it first (clean energy has the widest FX spread).
- Spec numbers CC-40 and CC-41, and whether CC-41 supersedes any of CC-26 to CC-38 in the sequence plan.

## 7. Risks

- Uncommitted edits to the runner and narrative jobs in the working tree; touching them now would collide.
- Manifest registration is mandatory for the macro table; forgetting it fails the determinism test, which is the intended guardrail.
- `tutor` on a shared GPU: `MAX_CONCURRENT = 4` pacing in the runner must apply to consults too, or a class of thirty teams asking at once will queue past the request timeout.
- Licensing of verbatim quotation from HBR, McKinsey, Economist and Springer material in a product used beyond the course.
