# CC-17 Acceptance Report — SC + compliance narratives

**Spec:** `specs/CC-17-sc-narratives.md` · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — RAG-grounded LLM narratives for SC events + compliance, verified live.

## What was built
SC disruption events and compliance detentions now get prose narratives, generated
in Phase 2 by extending the existing narrative orchestrator (`narratives.py`) and
LLM client (`llm_runner.py`, DashScope/Qwen):
- SC event narrative → stored on `SCEventInstance.resolution_data['narrative']`.
- Compliance narrative → new `ComplianceEnforcementEvent.narrative` field (migration 0055).
- RAG-grounded via `search_articles` over the CC-11 corpus; hard "describe, don't
  compute" guardrail; template fallback when no API key; EN/ZH; surfaced on the
  student SC dashboard (Recent Disruptions + Compliance Risk cards).

Also fixed a latent transaction-poisoning bug: `get_team_language` /
`get_instructor_language` swallowed a DB error (missing `enrollment` table in the
test DB) without a savepoint, aborting the caller's transaction — now contained in
`transaction.atomic()`.

## Tests — `test_cc17_narratives` (5, deterministic, no live LLM)
Prompt builders include the right facts + RAG grounding + guardrail; store
functions use LLM content when present and a factual template fallback when
absent; `_generate_all_fallbacks` populates narratives with no API key.
Full suite: **157 tests OK**. `manage.py check` clean; migration applied; build clean.

## Live verification (real DashScope/Qwen, disposable game, deleted after)
2/2 LLM calls succeeded. Sample output:

**SC event (Taiwan Earthquake):** a 3-paragraph analyst briefing naming TSMC/UMC/
AU Optronics, the 40% capacity cut, the 3-round recovery, framed in single-source
risk + geopolitical/ASEAN context **drawn from the RAG corpus** — using only the
facts provided (no invented numbers; guardrail held).

**Compliance (UFLPA):** "Your shipment was detained under the Uyghur Forced Labor
Prevention Act due to 100% Xinjiang exposure, exceeding the 5% threshold.
Remediation requires a $500,000 payment, and market access remains frozen through
Round 2. To mitigate future detentions, eliminate supply chain exposure to
Xinjiang-sourced inputs entirely."

## Operational note
Live LLM narratives require `DASHSCOPE_API_KEY` on the running backend. The dev
`:8012` process has no key, so it produces the **template fallbacks**; set the key
(the same one the sibling `globalstrat` service uses) to enable full LLM narratives.

## Deferred (documented)
Supplier-persona updates, trade-finance institution voices, and a whole-dashboard
summary narrative — same pattern, follow-on.
