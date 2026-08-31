# GSP-CRV2-08 final audit — REWORK

## Decision

**FAIL / REWORK**

Revision audited: `ef9aca6`.

The six required disputes are answerable, the browser/API evidence is accepted, and the archive is internally sound: all 31 manifest entries independently match their sizes and SHA-256 digests. One P1 operator-tooling gap remains in the data dictionary.

## Blocking finding — authorization-refusal evidence has no supported reader

Register a new finding before repair: **V2-036, P1**.

`AuthorizationRefusalEvent` now captures and seals cross-cohort mutation attempts, but no endpoint, management command or screen returns those rows. Investigation requires ad hoc database access. This is the same sufficiency class as V2-030: an append-only audit row that the operator cannot retrieve through supported tooling does not answer the incident it was created to investigate.

Calling database access a “deliberate boundary” does not close the gap. Django admin/database access was explicitly rejected as the supported path for V2-030.

## Required repair

Provide one supported, read-only forensic path. A management command is sufficient and is the preferred bounded repair; no new browser feature is required.

The command must support exact filtering by:

- game ID;
- request ID;
- actor ID or username;
- time range;
- method/route where practical.

It must return actor, attempted game, method, route/endpoint, timestamp, rejected outcome, ownership reason and request ID, with stable human-readable output and a JSON option suitable for an incident archive. It must never return request payloads, headers or credentials.

Document the exact command in the operator runbook and data dictionary. Demonstrate that a known refusal can be retrieved by game and request ID and that an unrelated refusal is excluded by the filters.

If an API/UI is chosen instead, it must enforce the shared game-ownership boundary and receive equivalent focused authorization tests. Do not add both surfaces.

## Focused acceptance

- a seeded `AuthorizationRefusalEvent` is returned by the supported command using game and request-ID filters;
- actor/time/method/route/outcome/reason/request ID are present;
- JSON output parses and contains the same row as text output;
- nonmatching game, actor, request ID and time filters exclude the row;
- output contains no payload, token, password or credential field;
- the command is read-only and does not alter the refusal row, audit chain or competition state;
- V2-036 is registered before implementation and closed only after this proof.

## Documentation and archive reconciliation

1. Update `DATA_DICTIONARY.md` to name the supported reader and remove the no-read-surface gap.
2. Correct “the four audit tables” in the chain-seal row: the chain now covers the decision, operator, sensitive-read and authorization-refusal ledgers plus completed resolution manifests (and its own chain entries).
3. Generate the required final `GSP-CRV2-08_COMPLETION_REPORT.md` under `handoff_readiness_v2/`, following the universal completion-report contract: baseline/freeze revisions, changed files/migrations, focused tests and commands, isolated-stack identity, evidence paths/hashes, findings/dispositions, rollback notes, unresolved items outside this handoff, and counts/durations of any expensive runs.
4. Regenerate `WALKTHROUGH_RECORD.json` only if its current-state findings/path summary changes; do not rewrite historical artifacts.
5. Regenerate `ARCHIVE_MANIFEST.json` and `SHA256SUMS` last, then verify both scopes.

## Verification budget

Run only focused command tests and one command walkthrough against existing refusal data, documentation/static checks, archive/checksum verification, `git diff --check` and clean-tree verification.

Do not repeat the browser walkthrough, disputes, ownership scan, replay, fixture, full suites, load, concurrency, determinism, provider or failure drills.
