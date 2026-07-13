# CC-17 — Phase-2 LLM Narratives (SC slice)

**Bundle:** CC-17 · **Depends on:** CC-3 (Phase-2 pipeline), CC-11 (RAG corpus), CC-19/19B (SC events), CC-18 (compliance events)
**Observes:** `STANDING-DISCIPLINE.md`
**Status:** Built (this rework) — SC + compliance narratives; other narrative types deferred.

## 1. Purpose
SC events fired and compliance regimes detained shipments, but the student saw
only numbers/tags — no prose explaining *what happened and why it matters*. CC-17
adds LLM-generated, RAG-grounded narratives, reusing the existing Phase-2
narrative orchestrator (`core/engine/narratives.py`) and LLM client
(`llm_runner.py`, DashScope/Qwen).

## 2. Scope (this build)
Two narrative types, matched to the surfaces the rework built:
1. **SC disruption event narratives** — one per `SCEventInstance` that fired this
   round, grounded in the event template + its `sc_effects` (affected suppliers,
   capacity reduction, recovery window) + a retrieved SC-corpus snippet. Stored on
   `SCEventInstance.resolution_data['narrative']`.
2. **Compliance enforcement narratives** — one per `ComplianceEnforcementEvent`
   this round, grounded in the regime + market + the (deterministic) cost / freeze
   / trigger + a retrieved compliance-corpus snippet. Stored on a new
   `ComplianceEnforcementEvent.narrative` field.

Deferred (documented, not built): supplier-persona updates, trade-finance
institution voices, and a whole-dashboard summary narrative.

## 3. Design (reuses the established pattern)
- **Orchestration:** `generate_round_narratives` (Phase 2, background thread)
  gains SC-event + compliance calls in its concurrent batch; `_generate_all_
  fallbacks` gains the same as templates when there is no API key.
- **RAG grounding (CC-11 payoff):** `_rag_snippet(query, tags)` embeds a query
  from the event and pulls the top corpus chunks via `search_articles` to ground
  the prose.
- **Guardrail:** the SC/compliance system prompts state — *describe the situation
  and business implications in prose; use ONLY the facts provided; never invent or
  compute numbers, prices, or percentages.* The deterministic engine owns all
  numbers; the LLM only narrates them.
- **Fallback:** no `DASHSCOPE_API_KEY` (or a failed call) → a factual template
  narrative (from the event template / regime facts). Never blank, never a crash.
- **Language:** SC events (game-wide) use the game/instructor language; compliance
  events (per team) use the team language — via `build_language_instruction`.

## 4. Surfacing
- Dashboard **Recent Disruptions** card shows each event's narrative.
- Dashboard **Compliance Risk** card + instructor panel show the compliance
  narrative (compliance events already carry it via the serializer).

## 5. Acceptance
- Tests (deterministic, no live LLM): the SC + compliance prompt builders include
  the right facts + the guardrail + a RAG snippet; the store functions write LLM
  content when present and a template fallback when absent; `_generate_all_
  fallbacks` populates narratives with no API key.
- `manage.py check` clean; migration applied; full suite green; frontend build clean.

## 6. Operational note
The narratives are LLM-generated only when `DASHSCOPE_API_KEY` is set for the
running backend. The dev `:8012` process currently has no key, so it produces the
**template fallbacks** (still useful); set the key to enable full LLM narratives
(the same key the sibling `globalstrat` service uses).
