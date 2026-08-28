# Determinism boundary

Authoritative for the v2 working tree. Evidence: `evidence/determinism/`.

`process_round()` commits Phase 1 before dispatching Phase 2. Phase 1 contains
scores, financials, ranking, resilience, agent actions and next-round state. It
sets `skip_rag=True`; no Phase-1 function consumes an LLM response. Phase 2 is a
daemon-thread presentation path for narratives, briefings, RAG commentary,
coaching alerts and market-outlook prose.

That claim is no longer only structural. Round 1 of game 37 was restored from
its pre-resolution backup and re-resolved four times — original model, a
substitute endpoint returning deliberately unrelated prose, an unreachable
endpoint, and a second container on a different base OS and Python whose
*resolving process* ran under `Asia/Kolkata` and `de_DE.UTF-8`. All four
produced competitive hash
`129a374ec6a82f22da9514ad3c263b856381024f46ad31790e5a36e08589b383`. The
narrative hash taken *after* Phase 2 differed in all four, and the prose behind
each is stored with the evidence.

All four ran the same code, proven by content and not by label: every run
verified the source tree digest
`642b5884460e82f6420e6ca7ca877f5c9cdacfe1a5f29bac47fc43eeb7b0206a` before
touching the database, and asserted its own environment fingerprint with
`--require-env` rather than claiming it in a run name.

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
  The narrative envelope carries the text itself (`prose`), not only the rows'
  metadata — hashing the metadata and calling it the narrative hash made the
  claim untestable, which is how V2-014 went unnoticed until two deliberately
  different models produced the same narrative hash.
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
- **The build identity.** `ResolutionManifest.code_revision` and
  `source_tree_sha256` are recorded and *verified*, but not inside
  `input_sha256`: they are properties of the host, not of the input. Verifying
  them separately is stronger than hashing them, because a mismatch produces a
  named error before any mutation instead of an opaque hash difference. The
  *migration* state, read from the database being resolved, is inside the hash.

  The source digest exists because a commit hash is not enough. `-dirty` names
  the commit and says only that something else was present; two different
  patches on one HEAD produce the same string. The digest covers every runtime
  source file under `backend/` regardless of git state, so it catches an
  untracked file that `git status --untracked-files=no` calls clean — which is
  exactly what the negative test in the evidence demonstrates.
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
   `os.environ['TZ']` from `settings.TIME_ZONE` and calls `tzset()`, so setting
   a container's clock alone leaves the resolving process on UTC no matter what
   the host says. `TIME_ZONE` and `LANGUAGE_CODE` are therefore
   environment-overridable (`DJANGO_TIME_ZONE`, `DJANGO_LANGUAGE_CODE`), and
   the cross-environment replay sets the first so the process genuinely runs
   under `Asia/Kolkata`. Nothing in the Phase-1 call graph reads local time —
   the only `astimezone` is the canonicaliser's own conversion to UTC — which
   is why the competitive hash does not move. The fingerprint records both the
   process timezone and the host's own `system_timezone`, and the replay
   asserts them.
