# Phase-2 narrative inventory

GSP-CRV2-03, Phase 1. Built before implementation, from two authoritative
registries: the Phase-2 call graph in `core/engine/narratives.py`, and the
certified manifest envelope in `core/services/manifest_sections.py`.

## Every narrative producer

| Type | Writes | Idempotency key | Fallback without LLM | In the competitive hash? |
|---|---|---|---|---|
| `briefing` | `StrategicBriefing` — 7 prose fields | game + team + round | yes, template briefing | no — narrative section |
| `coherence_rag` | `RoundResultCoherence.rag_score`, `.blended_score`, `.breakdown` | game + team + round | none; formula score stands | **yes — all fields hashed** |
| `coaching` | `InstructorAlert` row, `alert_type='coaching'` | game + team + round + type | none; no row created | **yes — row creation is hashed** |
| `outlook` | `MarketIntelligenceBrief.brief_level`, `.brief_content` | game + round+1 + market | yes, base narrative only | no — narrative section |
| `sc_event` | `SCEventInstance.resolution_data['narrative']` | round + event instance | yes, factual template | **yes — field is hashed** |
| `compliance` | `ComplianceEnforcementEvent.narrative` | round + event | yes, factual template | no — declared `narrative_fields` |

Only one of the six — `compliance` — was declared to the manifest as narrative.

## What that cross-reference found

Three of the six write into rows or fields that `output_sha256` covers, *after*
that hash has been taken. The hash itself never moves, because it is computed
inside the Phase-1 transaction before Phase 2 starts; that is why the
GSP-CRV2-01 replays all matched. The divergence is between **the manifest and
the database afterwards**, which no replay compares.

Two new findings, logged before repair:

* **V2-015 (P1)** — the stored round no longer reconciles with the manifest
  that certified it, for `coherence`, `sc_event` and `coaching`.
* **V2-016 (P1)** — `RoundResultCoherence.blended_score` is read by
  `core/services/grading.py`. A student's grade therefore depends on whether an
  LLM was reachable when the round resolved: with it, coherence is
  `0.6·formula + 0.4·RAG`; without it, the formula score stands. Two identical
  competitions grade differently. Neither `performance.py` nor `leaderboard.py`
  reads coherence, so rank and the performance index are unaffected — this is a
  grading defect, not a ranking one.

> **Status at `49d6514`.** Both findings are closed. This section records what
> the Phase-1 inventory found, before repair, and is left as written.
> V2-015 was repaired for all three producers; V2-016 was closed by removing
> the Phase-2 write path entirely rather than defaulting it off. See the
> findings register.

`SCEventInstance.resolution_data` is the clearest case: one JSON column holds
both `{'pending', 'applied'}` — flags that decide whether an
instructor-injected event fires, and which are genuinely competitive — and the
narrative prose Phase 2 appends. A mixed field cannot be classified correctly
either way.

## Job states

The durable record this handoff introduces:

```
pending ──claim──► claimed ──success──► succeeded
   ▲                  │
   │                  ├──retryable error──► pending   (attempts < max)
   │                  ├──terminal error───► failed
   └──claim expiry────┘                    (worker died; claim reclaimed)
```

`failed` is terminal and visible; an operator retries it explicitly. Scoring is
never re-run to retry a narrative.

## Dispatch sites

| Site | Before |
|---|---|
| `core/engine/advance_round.py::process_round` | `transaction.on_commit` starts a daemon thread; no record survives the process |
| `core/engine/narratives.py::generate_round_narratives` | the whole Phase-2 body, called only from that thread |
| `_generate_all_fallbacks` | called inline when no API key is configured |

Nothing else dispatches Phase-2 work.
