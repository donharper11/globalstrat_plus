# GSP-CRV2-02 second re-audit — FAIL / REWORK

**Audited:** 2026-08-28  
**Decision:** **FAIL / REWORK**

The route-boundary and request-ID defects appear repaired. This rework is
limited to certification discipline. Do not redesign the lifecycle work.

## Blocking defect 1 — certification predates the freeze commit

The binding `handoffs/EXECUTION_PROTOCOL.md` requires final evidence to run
from the frozen commit. The completion report states the actual order was
matrix → documentation → full suite → freeze commit. File mtimes are not a
substitute for running from an identifiable committed source, and the protocol
explicitly disallows accepting that argument.

### Required repair

1. Complete the harness parameterization below.
2. Commit all backend runtime/test changes. This is the new freeze commit.
3. Confirm `git status --untracked-files=no` is clean and record the source-tree
   digest from that commit.
4. From that commit, run guards → final matrix → full backend suite once →
   checksums → clean/diff checks, in the prescribed order.
5. Evidence reports must record the frozen commit and source digest observed by
   the executing process, not values inserted afterward.

## Blocking defect 2 — no cheap or medium harness profile

`backend/core/tests/test_operator_concurrency.py` hard-codes
`ITERATIONS = 100`. This violates the required 1/10/100 staged loop and caused
release-scale focused runs during development.

### Required repair

1. Read the iteration count from a documented environment variable or explicit
   harness option, with validation and a cheap default. Recommended:
   `GSP_CRV2_02_ITERATIONS=1` by default.
2. Development command uses 1, preflight uses 10, final evidence explicitly
   sets 100. Evidence generation must refuse a value other than 100 so cheap
   output cannot overwrite release artifacts.
3. Make assertions derive expected totals from the selected iteration count.
4. Add a contract test for default, 10 and 100 profiles without running the
   entire matrix three times.
5. Correct the module documentation: current text says each pair runs
   `ITERATIONS` “in each arrival order,” while the evidence reports 100 total
   races per pair with both orders controlled. State one unambiguous definition
   and make code, summary and handoff agree.

## Minimal certification sequence

After the new freeze commit:

```bash
cd backend
python3 manage.py dump_route_inventory --check
python3 manage.py dump_manifest_schema --check
python3 manage.py makemigrations --check --dry-run

GSP_CRV2_02_ITERATIONS=100 \
GSP_CRV2_02_EVIDENCE_DIR=../handoff_readiness_v2/evidence/operator-concurrency \
python3 manage.py test core.tests.test_operator_concurrency -v 2 --noinput

python3 manage.py test core --noinput
```

Then regenerate the evidence checksum inventory and run `git diff --check` plus
source-identity/clean-tree verification. Run these expensive commands once.

## Re-audit entry criteria

- Parameterized 1/10/100 profiles exist and their semantics are tested.
- Backend/test changes are committed before final evidence starts.
- Final matrix is 12 pairs × 100 total races per pair, with controlled coverage
  of both arrival orders, unless the implementation deliberately specifies and
  documents a different total.
- Matrix and full suite each run exactly once from the frozen commit.
- Route inventory remains 0 unguarded and request-ID tests remain green.
- Evidence checksums and all guards pass.
- Completion report contains the actual command order, durations and counts.
- V2-004 remains open until this re-audit passes.

## Checks that passed

These do not alter the fail verdict:

- Branch history is committed; only pre-existing `gap_closing/` is untracked.
- Route inventory guard reports current.
- Submitted summary reports 214 mutating routes, 36 lifecycle routes and zero
  unguarded routes.
- Submitted matrix reports 1200 races, zero deadlocks and zero 5xx.
- The completion report openly identifies both protocol violations.
