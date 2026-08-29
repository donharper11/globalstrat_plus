# GSP-CRV2-06 final documentation rework

## Decision

**FAIL / REWORK — documentation only.** Runtime and focused verification pass,
but the canonical findings register contradicts the accepted evidence and
leaves a rules question unresolved.

## Blocking inconsistencies

1. `V2_FINDINGS_REGISTER.md` still states that the scenario declares no
   trade-finance instruments and that the mechanism could not be exercised.
   The final capable fixture, populated through the authoritative
   `consumer_electronics_2026` loader, proves the opposite: 6 instruments,
   25 suppliers, 20 lanes and 5 regimes; the trade-finance probe was exercised.
2. The register leaves pre-unlock catalogue visibility as an unresolved rules
   question, while the completion report claims every acceptance mechanism has
   a disposition.

## Adopted catalogue rule

Scenario supplier, lane, trade-finance-instrument and compliance catalogues are
authenticated scenario reference data available from round 1. Progressive
disclosure governs team decision fields and stored team decision values, not
the existence or contents of shared scenario catalogues. Catalogue visibility
is symmetric across competitors and contains no team-specific decision value.

Record this as the adopted rule, not as an open question or limitation.

## Required edits

- Replace the stale “mechanism could not be exercised” paragraph with the final
  capable-fixture result and its measured trade-finance disposition.
- Replace the catalogue rules question with the adopted rule above.
- Check the completion report and findings register for any remaining statement
  that the authoritative scenario lacks trade-finance instruments.
- Commit the documentation correction and report the clean revision.

Do not change runtime code, tests, harnesses or evidence. Do not rerun tests,
checksums, probes, tournament or suites. Existing evidence checksums remain the
evidence inventory; only confirm that the evidence directory was untouched.

## Audit evidence already accepted

- Evidence inventory: 26/26 verified.
- Focused post-tournament runtime audit:
  `test_disclosure_read_gate` plus `test_user_endpoint`, 18/18 passed.
- Final report-only commit changed no runtime or evidence artifact.
