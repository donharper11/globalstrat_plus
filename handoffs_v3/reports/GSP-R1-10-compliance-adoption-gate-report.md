# GSP-R1-10 Compliance Adoption Gate

Date: 2026-07-23  
Target repo: `/home/ubuntu/projects/globalstrat+`  
Issue traced from: GSP-R1-09 fresh-game Round 1 rehearsal, where Vertex/Meridian-style Workhorse team could rank first despite a compliance freeze causing zero revenue.

## Finding

The original flow was only partially wired:

1. Compliance engine created a market-access freeze for a missing customs classification.
2. Revenue engine honored the freeze and booked no sales in that market.
3. Bass adoption still awarded customer adoption and adjusted fit in the frozen market.
4. Performance index used those fit signals, so the frozen team could receive a strong customer-performance score even though it could not sell.

This made compliance punishment visible financially, but not in adoption/performance scoring.

## Fix

Updated `backend/core/engine/bass_engine.py` so compliance freezes gate customer adoption before demand is awarded:

- If `(team_id, market_id)` is in `context.compliance_freezes`, the team gets zero attractiveness in that market.
- The team-market customer segment adjusted fit is set to `0.0` before performance scoring reads it.
- The adoption result writes zero adopters, zero readiness, and no best product for the frozen team-market.

This keeps the logic order coherent:

`fit -> compliance eligibility -> adoption/demand -> revenue -> performance index`

## Regression Test

Added `CC18ComplianceTest.test_freeze_blocks_customer_adoption_credit`.

Verified:

- Frozen market creates a RoundResultAdoption row with `new_adopters = 0.00`.
- `adjusted_fit_score = 0.0000`.
- `best_product = None`.
- Context adjusted fit is zeroed before downstream performance scoring.

Test command:

`python3 manage.py test core.tests.test_cc18_compliance.CC18ComplianceTest --verbosity=2`

Result: 8 tests passed.

System check:

`python3 manage.py check` -> no issues.

## Controlled Rerun

Created fresh game #18 and processed Round 1 with a controlled customs setup:

- Three teams received North America customs classification.
- Meridian Tech intentionally had no North America customs classification.
- Customs enforcement was temporarily forced to 100% for the run and restored afterward.
- UFLPA was temporarily disabled for isolation and restored afterward.

Post-process comparison:

| Rank | Team | PI | Revenue | Net income | Nonzero adoption rows |
|---:|---|---:|---:|---:|---:|
| 1 | Nova Circuit | 51.63 | $13,184,400.00 | $5,316,299.52 | 3 |
| 2 | Solaris Consumer | 51.63 | $13,184,400.00 | $5,837,699.52 | 3 |
| 3 | Lumen Devices | 51.60 | $17,864,400.00 | $9,471,383.52 | 3 |
| 4 | Meridian Tech | 49.81 | $0.00 | -$4,095,000.00 | 0 |

The controlled non-compliant team now falls to last place and receives zero successful adoption credit.

## Carry-Forward

R1-10-F1 [LOW/MED] — Customs enforcement currently evaluates markets even when the team does not have active sales/presence there. In the controlled run, compliant teams still received customs events in inactive/non-home markets. It did not distort adoption/revenue for active North America sales, but it can add confusing remediation costs and noisy event trails. Next fix should scope customs enforcement to markets where the team has active presence, product offerings, or explicit shipping/sales decisions.
