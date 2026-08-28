# CRV2 builder execution protocol

**Status:** Binding for GSP-CRV2-02 through 09 and all rework.  
**Purpose:** Preserve release-grade acceptance without repeatedly paying for
release-grade evidence while code is still changing.

## Core rule

Expensive evidence is a post-freeze certification step, not a development loop.
Inventory, contract tests and small samples must find defects first. A builder
who changes runtime code after certification starts returns to the freeze
checkpoint; they do not regenerate evidence while exploring.

Certification is **task-local**. A later handoff does not regenerate an earlier
handoff's replay matrix, load run, browser archive or soak merely because the
integrated source digest changed. It runs focused regression tests for the
interfaces it touched. GSP-CRV2-09 regenerates the complete integrated evidence
set once against the final release-candidate commit. Earlier evidence remains an
immutable record of its own named commit, not evidence for the later one.

## Phase 0 — exclusive test environment

Before any test:

1. Confirm no other Django suite, matrix, replay, migration check or evidence
   job is using the same test/replay database.
2. Acquire a host runner lock, for example:

   ```bash
   flock -n /tmp/globalstrat-backend-test.lock bash -lc '<test command>'
   ```

3. Long commands on the same database are strictly sequential. Parallel agents,
   background suites and shell parallelism are prohibited unless each job has a
   separately named database and isolated stack.
4. Record database name, PID, branch and revision when a command starts. A suite
   may not destroy a database owned by another PID.

If safe isolation cannot be proved, stop before running the command.

## Phase 1 — inventory before implementation

Produce the task's checked-in inventory first: registered mutation routes,
model/field envelope, job states, permission matrix, load actors, or equivalent.
Build it from authoritative registries (`urls.py`, Django router/model registry,
settings), not by grepping for the new helper correct code is expected to call.

Map every inventory row to changed/covered, intentionally removed, or explicitly
exempt with a testable rationale. No soak, full suite or evidence generation is
allowed in this phase.

## Phase 2 — cheap development loop

Use the smallest test that can falsify the edit:

- focused unit/contract tests;
- one barrier race per pair;
- one local replay;
- one failure injection;
- focused schema/migration checks where relevant.

Do not write evidence directories. Harnesses must accept an iteration/profile
option: cheap defaults for development, explicit release settings for evidence.
Do not run the full backend suite merely because a local edit compiled.

## Phase 3 — preflight and code freeze

1. Run the task's inventory reconciliation and static coverage guard.
2. Run focused tests.
3. Run a medium sample: normally 10 races per pair, one same-host replay, or one
   instance of each failure mode.
4. Complete the auditor preflight checklist below.
5. Fix defects and rerun only affected focused checks, then repeat preflight.
6. Commit the candidate and confirm runtime source identity/migrations are clean.

This commit is the code freeze. No final evidence exists before this point.

## Auditor preflight checklist

- Did inventory start from registered routes/models/jobs, not only code using
  the new abstraction?
- Is there an active legacy or alternate entry point?
- Does a failure/refusal audit survive rollback?
- Is each correlation ID generated once and identical in response/audit/log?
- Is background/external work delayed until the outer transaction commits?
- Do claimed environment values describe the executing process?
- Does provenance identify runtime bytes, including required untracked files?
- Do README commands run exactly as written against stored artifacts?
- Do P0/P1/P2 labels match their definitions?
- Does each negative test prove mutation/engine execution did not occur?

The completion report answers every applicable question.

## Phase 4 — final certification, once

From the frozen commit, run in this order:

1. migration/schema/static guards;
2. release-scale task harness;
3. full backend/frontend regression suite once;
4. checksum/index generation last;
5. `git diff --check` and clean-source verification.

If certification fails: stop remaining expensive jobs, diagnose with focused
tests, repair, create a new freeze commit, then certify once from that commit.
Do not rerun full suites/matrices to see if a failure flakes.

Do not run another handoff's release-scale harness here. For example, CRV2-02
runs its concurrency matrix but not CRV2-01's four-environment replay. Cross-task
integrated certification is reserved for CRV2-09.

## Phase 5 — handoff to audit

Submit frozen revision/source digest, inventory/coverage guard, preflight
results, every expensive command's duration and count, evidence checksums, new
findings and confirmation that runtime code did not change after evidence began.

The auditor verifies artifacts and focused adversarial samples. The auditor does
not automatically repeat the full soak unless evidence is inconsistent or the
handoff explicitly requires independent full reproduction.

## Command budget per freeze candidate

| Operation | Development | Preflight | Final certification |
|---|---:|---:|---:|
| Full backend suite | 0 | 0 | 1 |
| Concurrency matrix | 1 race/pair | 10 races/pair | 100 races/pair once |
| Determinism matrix | 1 local replay | 1 replay + negative smoke | 4 environments + negatives once |

Exceeding the budget is allowed only after a real failed freeze candidate and
must be explained in the completion report. Silent repeated release runs are
prohibited.
