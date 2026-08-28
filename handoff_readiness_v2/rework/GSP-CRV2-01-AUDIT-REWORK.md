# GSP-CRV2-01 audit verdict — FAIL / REWORK

**Audited:** 2026-08-28  
**Scope:** GSP-CRV2-01 deterministic reconstruction and cross-environment replay  
**Decision:** **FAIL / REWORK**

Do not mark V2-001 or V2-002 closed from the current evidence. Do not begin
GSP-CRV2-02 through 05 from this unnamed dirty baseline.

## Blocking defect 1 — evidence is not tied to identifiable source

Every recorded and replayed artifact reports:

`30cc26e93c7fb1e3edc23c19e54c051f6194067c-dirty`

That value identifies the old commit but not the large uncommitted patch that
implemented manifest v2. Any different dirty working tree on the same HEAD
produces the same revision string. The evidence therefore cannot prove which
canonicaliser, registry, ordering changes, migration or replay command produced
the hashes. A disputed round could not be reconstructed from this provenance.
This directly fails V2-002 and the handoff's named-baseline/evidence requirement.

### Required repair

1. Isolate the CRV2-01 change set from prior v2 work and unrelated files.
2. Commit it on a named integration revision after review. The release owner may
   choose the branch/tag name; the resulting commit must be immutable and clean.
3. Make production resolution and `replay_round` refuse a dirty or unidentified
   build. Alternatively, record and verify a deterministic full source-tree
   digest that includes tracked modifications and required untracked source and
   migration files. A literal `-dirty` suffix is not sufficient.
4. Record the exact commit/tree digest in the manifest, replay report, evidence
   summary and environment fingerprint. Replay must reject a source mismatch
   before engine mutation.
5. Regenerate all positive and negative evidence from that exact clean source.

## Blocking defect 2 — the different-timezone acceptance run was not different

Run D is labelled `TZ=Asia/Kolkata`, but its own replay report records:

- `tz_env: "UTC"`
- `time_tzname: ["UTC", "UTC"]`
- Django time zone: `UTC`

Only the container's `system_timezone` label says Asia/Kolkata. The Python
process performing canonicalisation ran under UTC, so this does not satisfy the
handoff requirement for a replay under a different timezone.

### Required repair

1. Remove whatever forces `TZ=UTC` in Run D or add a second clean environment
   whose replay process genuinely runs with `TZ=Asia/Kolkata`.
2. Before replay, capture `os.environ['TZ']`, `time.tzname`, `datetime.now()`
   with its effective zone, Django current timezone, OS timezone, locale,
   Python, Django and PostgreSQL versions.
3. Require the evidence generator to fail if the requested timezone/locale do
   not match the observed process environment. Labels are not evidence.
4. Replay from the same clean source revision and show the same competitive
   hash.

## Required evidence cleanup

The README transcript passes `expected-manifest.json`, while the checked-in
artifact is only `expected-manifest.json.gz`. Make the documented commands
directly reproducible: either teach `replay_round` to read gzip, retain the JSON
used by the command, or include the explicit decompression step. Regenerate
`MANIFEST.sha256` after replacing evidence.

## Finding triage correction

V2-010 and V2-011 are marked P2 even though the register says they can change
published results. Under the project's severity definition, P2 is cosmetic.
Re-triage both with the competition-rules owner:

- If cohort identity is intended to produce equal scenario streams, inconsistent
  cohort keys are at least P1; otherwise document the intentional rule and test it.
- If one team's presence can shift another team's random outcome, classify and
  resolve the fairness/rules consequence explicitly. Do not leave a
  result-changing behavior labelled cosmetic.

These findings need not be implemented inside CRV2-01 if their approved rule is
outside its scope, but their classification and owner cannot remain ambiguous.

## Re-audit entry criteria

Return for audit only when all are true:

- Working tree for CRV2-01 is clean and identified by immutable commit/tree hash.
- Manifest/replay rejects source mismatch before mutation.
- Schema and migration checks pass.
- Full backend suite passes with exact count.
- All four positive replays and three corruption tests were regenerated from
  the clean revision.
- Run D proves a genuinely non-UTC replay process and different locale/Python
  environment.
- Evidence checksum inventory verifies.
- README commands reproduce the stored artifacts without undocumented steps.
- V2-010/V2-011 have valid severity, owner and rules disposition.

The next audit is binary. Any unmet item above remains FAIL / REWORK.

## Checks that passed in this audit

These do not alter the fail verdict:

- `dump_manifest_schema --check`: pass.
- `makemigrations --check --dry-run`: no changes detected.
- Targeted manifest + competition-hardening tests: 46/46 pass.
- Current evidence checksum inventory: all listed files verify.
- `git diff --check`: pass.
