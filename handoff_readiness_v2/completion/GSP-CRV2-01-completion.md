# GSP-CRV2-01 completion report — deterministic reconstruction and replay

**Findings closed:** V2-001 (P0), V2-002 (P1), V2-012 (P0), V2-013 (P1), V2-014 (P1)
**Findings opened, rules disposition required:** V2-010 (P1), V2-011 (P1)
**Date:** 2026-08-28
**Revision:** `1189a50d41a502955f77fc505610165735ba6fac` on branch
`crv2-01-deterministic-reconstruction`; source tree digest
`642b5884460e82f6420e6ca7ca877f5c9cdacfe1a5f29bac47fc43eeb7b0206a`

## Second submission — what the audit sent back, and what changed

`rework/GSP-CRV2-01-AUDIT-REWORK.md` returned FAIL on four points. All four are
addressed, and chasing the first two turned up three further defects — one of
them a P0 that the first submission's evidence had not caught.

1. **Evidence was not tied to identifiable source.** Every artifact reported
   `<commit>-dirty`, which names the commit but not the patch on top of it. The
   change set is now isolated across three commits on a named branch, and
   `core/services/build_identity.py` adds a content digest over every runtime
   source file under `backend/`. Resolution refuses an unidentified build when
   `COMPETITION_REQUIRE_CLEAN_BUILD` is on; `replay_round` refuses a source
   mismatch before it mutates anything. A negative test shows the digest
   catching an untracked file that `git status --untracked-files=no` calls
   clean.
2. **The different-timezone run was not different.** Django assigns
   `os.environ['TZ']` from `settings.TIME_ZONE` and calls `tzset()`, so the
   process ran on UTC whatever the container's clock said. `TIME_ZONE` is now
   environment-overridable and run D sets it: the process reports
   `tz_env=Asia/Kolkata`, `time.tzname == ('IST','IST')`, Django current
   timezone `Asia/Kolkata`. `--require-env` asserts all eight environment
   claims and exits before doing anything if the process is not what the run
   says it is. Labels are no longer evidence.
3. **README commands referenced files that were not there.** `--expected-manifest`
   now reads gzip directly and resolves a `.json` path to the `.json.gz` beside
   it; the transcript was re-run as written and `MANIFEST.sha256` regenerated.
4. **V2-010/V2-011 were mis-triaged as cosmetic.** Both re-triaged to P1 —
   escalating to P0 for V2-010 if parallel sections are ever scored together —
   with an owner named and the specific rules choice each requires written out
   in the register.

Regenerating evidence from the clean revision is what exposed the rest:

5. **V2-012 (P0, repaired).** Replaying game 34 round 1 produced a *different*
   competitive hash from the original resolution, with all three same-host
   replays agreeing with each other. The section diff named `coherence` and a
   reordered `entry_mode_risk` list. Cause: the first ordering sweep inspected
   only inline loop iterators, so `rows = X.objects.filter(...)` followed by
   `for row in rows` was never checked — 75 further sites, including the
   unordered `TeamMarketPresence` scan behind the failure. A published round
   did not reproduce; that is a P0 and it is now fixed and guarded.
6. **V2-013 (P1, repaired).** The output snapshot held only competitive
   sections, so foreign keys into configuration fell back to
   `core.Scenario#surrogate:7`. The competitive hash carried raw sequence
   values.
7. **V2-014 (P1, repaired).** A narrative section's prose is separated into
   `narrative_rows`; the narrative envelope was built from `rows` alone, so
   `narrative_sha256` hashed briefing ids and not a word of text. Two runs
   against deliberately different models produced the same narrative hash — the
   first submission's "narrative differs" claim was, for one pair of runs,
   accidentally true and unprovable.

Items 5–7 are the direct answer to why a same-process replay is insufficient,
and why the audit was right to refuse evidence whose source could not be named.

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

- `manage.py replay_round` — export, assert environment (`--require-env`),
  verify source identity, restore, **verify input before mutation**, replay,
  per-section diffs. Refuses a source mismatch outright; exit 2 = input
  mismatch (engine not run); exit 3 = competitive hash mismatch. Reads gzipped
  manifests.
- `manage.py dump_manifest_schema [--check]` — regenerate / CI-guard the
  reviewed field inventory.
- `manage.py recover_competition_round` — now verifies the restored state
  against the recorded input manifest before re-running, and refuses on
  mismatch.

## Changed files

```
backend/core/services/build_identity.py                (new)
backend/core/services/canonical_json.py                (new)
backend/core/services/manifest_sections.py             (new)
backend/core/services/manifest_snapshot.py             (new)
backend/core/services/manifest_schema.py               (new)
backend/core/services/manifest_schema_v2.json          (new, generated)
backend/core/services/resolution_manifest.py           (rewritten)
backend/core/models/competition_audit.py               (ResolutionManifest fields)
backend/core/migrations/0061_resolutionmanifest_decision_event_count_and_more.py (new)
backend/core/migrations/0062_resolutionmanifest_source_tree_sha256.py (new)
backend/globalstrat/settings.py                        (TIME_ZONE/LANGUAGE_CODE
                                                        overridable, clean-build gate)
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
python3 manage.py test core --noinput             # 328 passed
python3 manage.py test core.tests.test_manifest_determinism --noinput  # 50 passed
python3 manage.py dump_manifest_schema --check    # inventory current
python3 manage.py makemigrations --check --dry-run  # no changes detected
```

Run the suite from `backend/`. `core/tests/test_cc_gaps.py` opens
`scenarios/consumer_electronics_2026.yaml` by relative path in `setUpTestData`,
so running it from the repository root fails that class's setup (8 tests) with
`FileNotFoundError`. Pre-existing; not touched here.

The 50 new tests cover: canonical serialisation (11), envelope enumeration and
schema drift (10), the engine iteration-order contract (3, now including
querysets reached through a local name), build identity (8), the replay
command's fail-closed gates (5), and real-database snapshot behaviour (13) —
natural-key uniqueness, absence of surrogate keys in *all three* envelopes,
decision payloads present, forward/reverse insertion for both the input
manifest and the whole Phase-1 pipeline, three corruption detections, prose in
the narrative hash and not in the competitive hash, the version-1 gate, and the
v2 write path.

## Isolated stack

Fixture and recording: dev database `globalstrat_plus` on `192.168.50.38`
(PostgreSQL 16.13), game 37 (`DETERMINISM-FIXTURE`, 4 bot teams, section id
90001), round 1.
Replays: disposable database `globalstrat_replay` on the same server; every
`--restore` drops and rebuilds its schema. Second environment: container image
`globalstrat-replay:crv2-01` (Debian 12, Python 3.11.16, pg client 18.6), built
from `handoff_readiness_v2/replay_environment.Dockerfile` and run with
`DJANGO_TIME_ZONE=Asia/Kolkata` and `LC_ALL=de_DE.UTF-8` so the resolving
process — not just the host — is in a different zone and locale.

## Evidence

`handoff_readiness_v2/evidence/determinism/` — `README.md` (full command
transcript), `SUMMARY.json`, `MANIFEST.sha256`.

- Source tree digest, verified before every run:
  `642b5884460e82f6420e6ca7ca877f5c9cdacfe1a5f29bac47fc43eeb7b0206a`
- Competitive hash, all four runs:
  `129a374ec6a82f22da9514ad3c263b856381024f46ad31790e5a36e08589b383`
- Input hash, verified before every run:
  `408fe6ebb847e00287fec854a87f093359f59acffdb809425805c83951b55c84`
- Backup sha256:
  `bdd0bac52a771a3d38d2899698acdfa0b09013cc4e19aa7d2cffa9b6c4ddddb5`
- Post-Phase-2 narrative hashes: four runs, four different values, with the
  prose that produced each stored alongside.
- Negative tests: corrupted decision payload, scenario value, carried-state
  value and altered source tree each fail before processing, naming the exact
  row and field or the differing digest.
- `MANIFEST.sha256` verifies (`sha256sum -c`).

## Baseline

Branch `crv2-01-deterministic-reconstruction`, five commits on `30cc26e`:

| Commit | Contents |
|---|---|
| `bb982b0` | The pre-existing uncommitted v2 repairs (V2-001 first pass, V2-003/004/005/008), reconstructed byte-for-byte as they were found — 168 insertions, 13 deletions, matching the working tree at handoff — so the GSP-CRV2-01 diff is reviewable on its own. |
| `61c43da` | GSP-CRV2-01: canonical serialisation, the enumerated envelope, build identity, the first ordering sweep, the commands. |
| `7df03ed` | Harness fix so the documented transcript runs as written (outside `backend/`; source digest unchanged). |
| `564bb3c` | V2-012: the 75 querysets iterated through a local name. |
| `1189a50` | V2-013 and V2-014: identity closure for both envelopes, prose in the narrative hash. |

`gap_closing/` is untracked and out of scope, as the handoff directs. The
working tree is clean; `resolve_code_revision()` returns `1189a50…` with no
`-dirty` suffix and `source_tree_digest()` returns `642b5884…` over 312 files.

Evidence was generated *by* `1189a50` and committed after it, so the artifacts
record the revision that produced them rather than the one that stores them.

The release owner still chooses the tag name; the branch is here to be tagged.

## Rollback

Revert to `30cc26e` (or to `bb982b0` to keep the prior v2 repairs) and
`manage.py migrate core 0060`. The migration only
adds columns, so rolling back loses the v2 envelope on any manifest written in
the meantime but does not damage a v1 manifest. Ordering changes are additive
`.order_by(...)` clauses; reverting them restores the previous (unordered)
behaviour and would reopen the sweep.

## Unresolved risks

1. **V2-010 / V2-011** — two RNG cohort keys are in use, and the supply-chain
   and compliance passes share one stream across teams. Both are P1, owned by
   the competition-rules owner via GSP-CRV2-09, with the specific choice each
   needs written out in the register. Not changed here: altering a seed changes
   published results, which is a rules decision rather than a hardening one.
   V2-010 escalates to P0 if parallel sections are ever scored against one
   another.
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
   separate VM). Base OS, Python, process and host timezone, locale, and
   PostgreSQL client version all differ; the kernel and CPU do not. A separate
   VM or a different architecture would be a stronger test and is available to
   GSP-CRV2-09 if the re-audit wants it.
6. **`COMPETITION_REQUIRE_CLEAN_BUILD` defaults off outside production.** That
   is deliberate — a developer's working tree is dirty by definition — but it
   means the gate only protects an environment that sets `IS_PRODUCTION` or the
   variable. The competition stack must set one of them, and the launch
   checklist should carry that as a line item.
7. **The source digest covers `backend/` only.** Frontend code, deployment
   configuration and the operating system are outside it. Those cannot change a
   competitive hash, but they can change what a participant saw; the
   environment fingerprint records the OS and interpreter, not the deployed
   frontend build.
