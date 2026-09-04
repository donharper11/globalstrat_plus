# Phase 3 CI receipt audit — rework required

Date: 2026-09-04  
Audited GlobalStrat+ commit: `eb5683a`  
Audited vendored revision at that commit: `eefb8c7`  
Corrective upstream revision: `e710f26` (`aide-checks` `origin/main`)

## Verdict

**Phase 3 is not audit-accepted yet.**

The previous green CI run and receipt prove that the older receipt-producing
path ran. They do not prove that the receipt gate rejects a receipt stating the
opposite of its required claim. The original assertion validated JSON shape but
not the required values, so a synthetic CI-shaped receipt with mismatched
revisions, no executed checks, and `exit_code: 1` returned success.

The corrective package change is accepted in principle and has been published
upstream. The GlobalStrat+ vendor sync is present in the working tree but has
not yet been committed or exercised by CI. This report is a rework handoff, not
a closure.

## Evidence accepted — do not redo

- Upstream `aide-checks` commit `e710f26` is present at `origin/main`; it is a
  normal fast-forward from the prior `eefb8c7` revision.
- The GlobalStrat+ working vendor sync is limited to the expected files:
  `checks/.aide-checks-rev`, `checks/bin/assert-ci-receipt`,
  `checks/bin/run-checks`, and `checks/selftest/run`.
- The vendored `assert-ci-receipt` and `selftest/run` are byte-identical to
  upstream `e710f26`; the runner's sync stamp and sidecar both name `e710f26`.
- Independent execution of the vendored selftest passed: **111 passed,
  0 failed**.
- The new selftests independently reject each required bad state: non-CI
  environment, disagreement between receipt revisions, matching but
  checkout-wrong revisions, no executed run, empty `checks_run` despite a
  positive run count, and a nonzero exit code. An unaltered control receipt
  passes.
- The GitHub Actions workflow runs `assert-ci-receipt` after the runner under
  `if: always()`, uploads the hidden receipt explicitly, and independently
  gates both the selftest and runner outcomes.

## Finding — blocking

### Receipt assertion previously accepted false proof

At `eb5683a`, `checks/bin/assert-ci-receipt` accepted a receipt that named CI
but asserted incompatible revisions, `ran: 0`, an empty executed-check list,
and `exit_code: 1`. The gate therefore established only that JSON with the
right fields existed, not that CI ran the committed vendored package
successfully.

The corrected assertion at `e710f26` now requires all of the following:

1. `environment == "ci"`.
2. `vendored_revision == committed_revision == checks/.aide-checks-rev`.
3. `ran > 0` and a non-empty `checks_run`.
4. `exit_code == 0`.

It additionally anchors matching receipt revisions to the checkout's revision
sidecar, preventing two matching-but-wrong revisions from being accepted.

## Required builder completion

1. Commit the existing GlobalStrat+ vendor sync normally, including only the
   four expected `checks/` files listed above. Do not alter the accepted
   upstream package revision or weaken its selftests.
2. Push the resulting GlobalStrat+ commit normally; do not force-push.
3. Let the push-triggered `aide-checks` workflow finish successfully.
4. Provide the run identifier/URL and the unexpired `aide-checks-receipt`
   artifact for that new commit.
5. Confirm from that artifact that `environment` is `ci`, both receipt
   revisions and `checks/.aide-checks-rev` are `e710f26`, `ran > 0`,
   `checks_run` is non-empty, and `exit_code` is `0`.

## Re-audit checklist

- [ ] GlobalStrat+ committed revision contains the four-file vendor sync and
  has no unrelated changes.
- [ ] The committed marker and runner stamp both name `e710f26`.
- [ ] Push is a normal, non-forced update.
- [ ] The new CI run is green, including selftest, runner, receipt assertion,
  artifact upload, and final outcome gate.
- [ ] The artifact receipt carries CI environment, matching `e710f26`
  revisions, at least one executed check, and exit code zero.
- [ ] The receipt assertion rejects the pre-fix synthetic false proof.

## Final disposition

**REWORK REQUIRED:** the implementation is verified locally, but the required
committed-and-CI-proven chain does not exist yet. The earlier green run at
`eb5683a` is not evidence for the strengthened assertion and must not be used
for Phase 3 acceptance.
