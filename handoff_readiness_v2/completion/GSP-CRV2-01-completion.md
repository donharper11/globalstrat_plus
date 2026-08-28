# GSP-CRV2-01 completion report — deterministic reconstruction and replay

**Findings closed:** V2-001 (P0), V2-002 (P1)
**Findings opened:** V2-010 (P2), V2-011 (P2)
**Date:** 2026-08-28

## Baseline

Working tree at `30cc26e` ("Add final competition-readiness report and
declaration") plus the pre-existing uncommitted v2 repairs for V2-001, V2-003,
V2-004, V2-005 and V2-008, which were preserved. The manifest work replaces the
uncommitted `resolution_manifest.py` expansion; nothing else was reverted.
`gap_closing/` was left untouched.

## What was built

### 1. Canonical serialisation — `core/services/canonical_json.py`

Decimal exponent and trailing zeros collapse (`1234.5600`, `1234.56`,
`1.23456E+3` → `"1234.56"`); floats render from their bits via `repr` with
`-0.0` folded and non-finite values tagged; aware datetimes normalise to UTC at
fixed microsecond precision and naive ones are tagged; mapping keys are coerced
to strings and sorted by code point; output is ASCII-only. Numbers are emitted
as strings so no JSON encoder's float formatting reaches the hashed bytes.
Unknown types raise rather than falling back to `str()`.

### 2. Section registry — `core/services/manifest_sections.py`

115 input sections (72 of them in the competitive output envelope, 41
scenario/engine configuration, 2 input-only provenance sections) and 2
narrative sections. Each declares its model, scope, filter path, natural key,
narrative fields, a one-line rationale, and a written justification for every
excluded field. Natural keys default to the model's single `unique_together`,
so they follow the schema rather than a hand-maintained copy of it.

### 3. Sequence-independent snapshots — `core/services/manifest_snapshot.py`

Rows are identified by a natural-key token with foreign keys replaced by the
referenced row's token, resolved recursively in dependency order; tables with
no natural key get a content-derived token plus an occurrence index. Sections
are sorted by token, so a manifest depends on neither surrogate ids nor
physical row order. A reference to a row with no resolvable natural key fails
the build rather than emitting a primary key.

### 4. Manifest v2 — `core/services/resolution_manifest.py`, migration `0061`

`prepare_manifest` records the full input state before a value is mutated;
`complete_manifest` records the competitive output, the narrative envelope
hashed separately, and `config_digests` proving configuration was not rewritten
mid-round. New `ResolutionManifest` fields: `schema_version`,
`input_section_digests`, `output_section_digests`, `narrative_manifest`,
`narrative_sha256`, `environment`, `input_body_path`, `output_body_path`,
`decision_event_count`. Each envelope is also written to a content-addressed
file under `<COMPETITION_BACKUP_DIR>/manifests/` so it survives losing the
database. `require_schema_version` refuses to read a v1 row as a v2 envelope.

### 5. Ordering — 93 sites across `core/engine/`

Every iterated queryset now declares an order except six documented exemptions.
Rows participants insert are ordered by natural key, not by primary key, because
id order *is* insertion order. See `ORDERING_AUDIT.md`.

### 6. Commands

- `manage.py replay_round` — export, restore, **verify before mutation**,
  replay, per-section diffs. Exit 2 = input mismatch (engine not run); exit 3 =
  competitive hash mismatch.
- `manage.py dump_manifest_schema [--check]` — regenerate / CI-guard the
  reviewed field inventory.
- `manage.py recover_competition_round` — now verifies the restored state
  against the recorded input manifest before re-running, and refuses on
  mismatch.

## Changed files

```
backend/core/services/canonical_json.py                (new)
backend/core/services/manifest_sections.py             (new)
backend/core/services/manifest_snapshot.py             (new)
backend/core/services/manifest_schema.py               (new)
backend/core/services/manifest_schema_v2.json          (new, generated)
backend/core/services/resolution_manifest.py           (rewritten)
backend/core/models/competition_audit.py               (ResolutionManifest fields)
backend/core/migrations/0061_resolutionmanifest_decision_event_count_and_more.py (new)
backend/core/management/commands/replay_round.py       (new)
backend/core/management/commands/dump_manifest_schema.py (new)
backend/core/management/commands/recover_competition_round.py (verify before re-run)
backend/core/tests/test_manifest_determinism.py        (new, 34 tests)
backend/core/tests/test_competition_hardening.py       (v2 envelope assertion)
backend/core/engine/{advance_round,acquisitions,alliance_engine,bootstrap,
  capital_markets,coherence,compliance_engine,costs,derived_features,events,
  financials,fx_engine,instructor_alerts,investor_features,performance,
  rd_processing,sc_engine,strategy_effects,talent}.py  (explicit ordering)
backend/core/engine/agents/{state,governments}.py      (explicit ordering)
handoff_readiness_v2/DETERMINISM_BOUNDARY.md           (rewritten)
handoff_readiness_v2/ORDERING_AUDIT.md                 (new)
handoff_readiness_v2/V2_FINDINGS_REGISTER.md           (closures, V2-010/011)
handoff_readiness_v2/LAUNCH_CHECKLIST_V2.md            (two gates closed)
handoff_readiness_v2/{determinism_fixture,llm_stub,corrupt_one_value}.py (new)
handoff_readiness_v2/replay_environment.Dockerfile     (new)
handoff_readiness_v2/evidence/determinism/             (new)
handoff_readiness/OPERATOR_RUNBOOK.md                  (replay procedure)
```

Migration `0061` adds nullable/defaulted columns only. Existing manifest rows
keep `schema_version=1` and are never reinterpreted.

## Tests

```bash
cd backend
python3 manage.py test core                       # 312 passed
python3 manage.py test core.tests.test_manifest_determinism   # 34 passed
python3 manage.py dump_manifest_schema --check    # inventory current
```

Run the suite from `backend/`. `core/tests/test_cc_gaps.py` opens
`scenarios/consumer_electronics_2026.yaml` by relative path in `setUpTestData`,
so running it from the repository root fails that class's setup (8 tests) with
`FileNotFoundError`. Pre-existing; not touched here.

The 34 new tests cover: canonical serialisation (11), envelope enumeration and
schema drift (10), the engine iteration-order contract (3), and real-database
snapshot behaviour (10) — natural-key uniqueness, absence of surrogate keys,
decision payloads present, forward/reverse insertion for both the input
manifest and the whole Phase-1 pipeline, three corruption detections, the
version-1 gate, and the v2 write path.

## Isolated stack

Fixture and recording: dev database `globalstrat_plus` on `192.168.50.38`
(PostgreSQL 16.13), game 32 (`DETERMINISM-FIXTURE`, 4 bot teams, section id
90001), round 1.
Replays: disposable database `globalstrat_replay` on the same server; every
`--restore` drops and rebuilds its schema. Second environment: container image
`globalstrat-replay:crv2-01` (Debian 12, Python 3.11.16, `TZ=Asia/Kolkata`,
`LC_ALL=de_DE.UTF-8`, pg client 18.6), built from
`handoff_readiness_v2/replay_environment.Dockerfile`.

## Evidence

`handoff_readiness_v2/evidence/determinism/` — `README.md` (full command
transcript), `SUMMARY.json`, `MANIFEST.sha256`.

- Competitive hash, all four runs:
  `ba9f711194866fe36226def40e3dee636dfc2864301e98e57abc212e96dd3393`
- Input hash, verified before every run:
  `9637354593d58fd7727c89bdc7f4b383bc2d868a2fd2569464bf922988a3bf1b`
- Backup sha256:
  `cdddee4d40c92a8e157becac213b32146cceb8e80ba970fc469ebcee32c0540e`
- Post-Phase-2 narrative hashes: four runs, four different values.
- Negative tests: corrupted decision payload, scenario value and carried-state
  value each fail verification before processing, naming the exact row and
  field.

## Baseline

The work is in the working tree, uncommitted, alongside the pre-existing v2
repairs it was asked to preserve. Establishing the named integration baseline
(commit + tag) that `handoffs/README.md` asks for is the next action and is left
to the release owner, since it is the point at which 02–05 branch from this.

## Rollback

Revert the listed files and `manage.py migrate core 0060`. The migration only
adds columns, so rolling back loses the v2 envelope on any manifest written in
the meantime but does not damage a v1 manifest. Ordering changes are additive
`.order_by(...)` clauses; reverting them restores the previous (unordered)
behaviour and would reopen the sweep.

## Unresolved risks

1. **V2-010 / V2-011** — two RNG cohort keys are in use, and the supply-chain
   and compliance passes share one stream across teams. Both are recorded, not
   changed: altering a seed changes published results, which is a
   competition-rules decision rather than a hardening one.
2. **Seeded RNG operation ids embed surrogate primary keys.** Replay is exact
   against a restored database — the supported reconstruction path — but a
   scenario re-imported into a fresh database would draw a different stream.
   Recorded in `seed_inputs` and in `DETERMINISM_BOUNDARY.md`.
3. **The evidence covers one round of one four-team game.** It exercises
   revenue, R&D, market entry, plant, compliance, talent and supply-chain
   paths, but a full-field (24-team) multi-round replay has not been captured;
   that belongs with GSP-CRV2-07's load work.
4. **Manifest size.** An input envelope is ~2 MB of canonical JSON per round
   (~3.3 MB before the configuration/state split is considered). At competition
   scale this is tens of MB in the database plus the same again in the
   content-addressed store — budgeted for, but worth watching.
5. **The second environment shares the host kernel** (a container, not a
   separate VM). Base OS, Python, timezone, locale, and PostgreSQL client
   version all differ; the kernel does not.
