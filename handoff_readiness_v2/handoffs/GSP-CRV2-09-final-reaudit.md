# GSP-CRV2-09 — Independent integrated release walkthrough and re-audit

**Status:** Run last, only after GSP-CRV2-01 through 08 and GSP-CRV2-10 through
13 are complete, integrated, and deployed to an isolated release-candidate
environment. Handoff numbers are identifiers rather than execution order; the
binding sequence is in `handoffs/README.md`.
**Owner:** independent competition-readiness auditor

## Purpose

Decide whether the integrated product works and whether prior claims still apply.
Do not reproduce every branch-level certification. Validate provenance and
checksums, run one realistic competition playthrough, and independently sample
only the highest-risk boundaries.

The auditor does not implement fixes. A failure receives a narrow rework handoff
and only the affected path is repeated before the final integrated smoke.

## Phase 1 — evidence reconciliation (read-only)

1. Verify release revision, clean migrations/build provenance, evidence indexes,
   and the findings register.
2. Map files changed after each certified handoff to the boundary it proved.
   Accept intact prior evidence when the relevant runtime boundary did not
   change. Require a focused regression when it did.
3. Verify stored commands and runbooks are still executable with `--help`, static
   checks, or non-mutating dry runs where available.

Do not automatically rerun four-environment determinism, 1,200 operator races,
provider matrices, load profiles, or repeated failure drills. Those are repeated
only if provenance is inconsistent, evidence is invalid, or later changes touch
the proven mechanism.

## Phase 2 — one end-to-end competition playthrough

On the isolated release candidate, use supported browser/API flows:

1. instructor creates/configures a game and students join;
2. multiple teams save, edit, submit, and lock realistic decisions;
3. instructor closes and processes at least three rounds;
4. results, grades, narratives, dashboards, history, manifests, and audit records
   appear and reconcile;
5. exercise one deadline change, one correction/operator action, one event, and
   one narrative retry without rerunning scoring;
6. complete the game and verify rankings, exports, post-close retrieval, and the
   six dispute answers;
7. restart the application/workers between rounds and confirm the supported
   operational workflow resumes.

Reuse CRV2-07's isolated stack and CRV2-08's seeded/completed game when doing so
does not hide the create/join/advance flows. A playthrough step may cite their
frozen-candidate artifact rather than repeat an identical action.

## Phase 3 — bounded independent samples

Run exactly one sample for each area unless it fails:

- one same-host deterministic replay plus one input-tamper refusal;
- one representative concurrent-operator barrier race;
- one narrative worker restart/recovery check;
- one optimizer sample including the strongest known line;
- review the field and 3× load reconciliation; no new load run unless invalid;
- one backup/restore or recovery walkthrough if CRV2-07's artifact is not from
  this exact candidate.

Use focused automated tests for V2-001/003/004/005/008 and any later-touched
interfaces. Do not rerun historical matrices merely to increase artifact count.

## Phase 4 — single integrated regression

After the playthrough and focused samples pass, run backend and frontend
regression suites once from the final frozen candidate. If a suite fails, stop,
diagnose with focused tests, repair under a targeted handoff, refreeze, rerun the
affected verification, then run one final integrated smoke/suite. Never use full
suites as a flake detector.

## Verdict rules

- P0 open or a failed core playthrough: **NO-GO**.
- P1 open: **NO-GO** unless resolved by the named owner and verified; no “pass
  with accepted limitations.”
- Missing redundant evidence is not a failure when valid prior evidence and an
  unchanged boundary are documented.
- PASS requires exact revision/configuration, artifact paths and hashes, suite
  counts, playthrough results, and reproducible commands.
- Human volunteer/sign-off activities remain separate and cannot repair a failed
  technical gate.

Deliver `V2_FINAL_READINESS_REPORT.md`, reconciled findings register, final
launch checklist, immutable evidence index, and a binary GO/NO-GO recommendation.
