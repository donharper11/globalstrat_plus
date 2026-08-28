# Determinism boundary

Authoritative for the v2 working tree. Evidence: `evidence/determinism/`.

`process_round()` commits Phase 1 before dispatching Phase 2. Phase 1 contains
scores, financials, ranking, resilience, agent actions and next-round state. It
sets `skip_rag=True`; no Phase-1 function consumes an LLM response. Phase 2 is a
daemon-thread presentation path for narratives, briefings, RAG commentary,
coaching alerts and market-outlook prose.

That claim is no longer only structural. Round 1 of game 32 was restored from
its pre-resolution backup and re-resolved four times — original model, a
substitute endpoint returning deliberately unrelated prose, an unreachable
endpoint, and a second container on a different base OS, Python, timezone and
locale. All four produced competitive hash
`ba9f711194866fe36226def40e3dee636dfc2864301e98e57abc212e96dd3393`. The
narrative hash taken *after* Phase 2 differed in all four.

## What the competitive hash covers

`output_sha256` is the SHA-256 of the canonical serialisation of 72 sections —
the complete enumeration in `core/services/manifest_sections.py`, reproduced
field by field with every exclusion's justification in
`backend/core/services/manifest_schema_v2.json`. In outline:

| Group | Sections |
|---|---|
| Lifecycle and roster | `game`, `round`, `team` |
| Accepted decisions | all 15 `decision_*` tables, `talent_allocation`, `compliance_investment`, all 10 `sc_*` decision tables |
| World state | `event_instance`, `active_modifier`, `sc_event_instance`, `supplier_state`, `lane_state`, `government_action`, `government_satisfaction`, `compliance_enforcement`, `ai_investor_holding` |
| Carried team state | `team_platform`, `team_platform_feature_level`, `pending_feature_gain`, `team_product`, `team_product_market`, `team_market_presence`, `team_market_modifier`, `team_strategy_feature_level`, `team_talent_state`, `team_plant`, `team_partnership`, `team_acquisition`, `team_alliance_state`, `team_governance_commitment`, `team_market_compliance`, `team_tax_structure`, `team_org_structure`, `hedge_position` |
| Published results | `financials`, `market_revenue`, `product_market`, `adoption`, `performance`, `coherence`, `resilience`, `share_price`, `leaderboard`, `esg_impact`, `talent_impact`, `partnership_impact`, `agent_cycle`, `instructor_alert` |

The output envelope also carries `config_digests`: the digest of every
scenario-configuration section, recomputed after resolution. A replay that
matches proves the engine did not rewrite its own configuration mid-round.

`input_sha256` covers all of the above plus the 41 scenario/engine
configuration sections, the roster (`team_member`), the ordered decision audit
trail (`decision_audit_event`), the RNG seed derivation inputs, and the applied
migration list.

## What is deliberately outside it, and why

- **Phase-2 prose.** `strategic_briefing` and `market_intelligence`, plus the
  narrative fields on otherwise-competitive rows (`event_instance.narrative`,
  `government_action.narrative`, `compliance_enforcement.narrative`,
  `agent_cycle.narrative_items`/`agent_summary`, event and market-outlook
  templates). Hashed separately as `narrative_sha256` and reported separately.
- **Measured wall clock.** Every field in
  `manifest_sections.MEASURED_TIME_FIELDS` — `created_at`, `updated_at`,
  `processed_at`, `locked_at`, `generated_at` and the rest — plus
  `phase_1_duration` / `phase_2_duration`. These record when the machine did
  something, not what it computed. They *are* kept in the input envelope, where
  they are frozen facts about the state resolution started from and are what a
  "when was this accepted" dispute is settled with.
- **Surrogate primary keys.** Replaced everywhere by natural-key tokens (see
  below), because sequence values move with unrelated inserts.
- **Operator free text and localised labels.** Each listed with its
  justification in the registry; `test_manifest_determinism` fails if any field
  is dropped without one.
- **The code revision.** Recorded in `ResolutionManifest.code_revision` and in
  the exported manifest, but not inside `input_sha256`: it is a property of the
  host, not of the input, and a clean checkout in a second environment reports
  it differently from a dirty working tree. The *migration* state, which is
  read from the database being resolved, is inside the hash.
- **The environment fingerprint.** `ResolutionManifest.environment` records
  Python, Django, OS, host timezone, locale, encoding and database version
  precisely so a replay can vary them. Hashing it would make a
  cross-environment match impossible by construction.

## Canonical serialisation

`core/services/canonical_json.py`. Four representation hazards are neutralised:
Decimal exponent and trailing zeros (`1234.5600`, `1234.56` and `1.23456E+3`
all render `"1234.56"`), locale (ASCII-only output, no locale-aware
formatting), timezone (aware datetimes normalised to UTC with fixed microsecond
precision; naive ones tagged), and mapping iteration order (keys coerced to
strings and sorted by code point). Numbers are emitted as strings so no JSON
encoder's float formatting can reach the hashed bytes.

## Row identity and ordering

Rows are identified by a **natural-key token** built from the section's
declared key with every foreign key replaced by the referenced row's token,
recursively — for example:

```
decision_marketing(decision_submission(team(game("DETERMINISM-FIXTURE")|"Nova Circuit")
  |round(game("DETERMINISM-FIXTURE")|"1"))|team_product(...)|market_definition(
  scenario("Consumer Electronics 2026")|"NA"))
```

Sections are sorted by token, so a manifest does not depend on physical row
order, planner choice or insertion sequence. Tables with no natural key get a
content-derived token plus an occurrence index — still free of sequence values.

Iteration order inside the engine is covered by `ORDERING_AUDIT.md` and
enforced by an AST test.

## Residual boundary conditions

These are properties of the design, not defects to be silently relied on.

1. **Seeded RNG operation ids embed surrogate primary keys.**
   `get_rng(class_id, round, "event_trigger:{template.id}")` and its siblings
   key on row ids. Replay is exact against a *restored database*, where those
   ids are preserved — which is the supported reconstruction path. A scenario
   re-imported into a fresh database would receive different ids and therefore
   different draws. `ResolutionManifest.input_manifest['seed_inputs']` records
   this explicitly rather than leaving it implicit.
2. **Two different cohort keys are in use.** `core/engine/rng.py` keys on
   `game.section_id or game.id`; `sc_engine._seed()` and
   `compliance_engine` key on `game.id`. Two sections of one class running the
   same scenario therefore share an event stream but not a supply-chain
   stream. Recorded as V2-010; not changed here, because changing a seed
   changes published results.
3. **The supply-chain and compliance passes share one RNG stream across
   teams.** Draw *n* belongs to whichever (team, regime, market) triple reached
   the roll *n*-th. The order is now explicit and stable, so replay is exact —
   but adding or withdrawing a team shifts every later team's draw. Recorded as
   V2-011.
4. **Django normalises the process timezone.** It assigns
   `os.environ['TZ']` from `settings.TIME_ZONE` and calls `tzset()`, so a
   differing host timezone cannot reach the process. The fingerprint records
   the host's own setting (`system_timezone`) so the cross-environment claim
   rests on what the machine was configured to, not on what Django left in the
   environment.
