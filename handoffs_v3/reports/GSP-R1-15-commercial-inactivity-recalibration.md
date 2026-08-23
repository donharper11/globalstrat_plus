# GSP-R1-15 — Commercial Inactivity PI Recalibration

Date: 2026-08-23  
Motivation: Game #20 Apex Devices scored PI 55.23 despite zero commercial activity, zero revenue, and a $1.665M loss.

## Policy

A team is voluntarily commercially inactive when, for the current round:

- total revenue is zero or lower; and
- every marketing decision has zero production;
- zero promotion budget;
- zero distribution investment; and
- zero sales-team count.

A missing submission or a submission with no marketing decisions also qualifies. Zero revenue by itself does not qualify: a team with production or any go-to-market commitment retains normal strategic credit even if demand, compliance enforcement, or disruption prevents sales.

The final five-component composite is capped at `0.25` for a voluntarily inactive team. With the configured PI sensitivity of 20:

```text
index change = (0.25 - 0.50) × 20 = -5.00
```

The cap is applied before the existing zero-revenue ordering guard. Engine logs record `commercial-inactivity cap applied`.

## Game #20 counterfactual

Apex Devices had:

- promotion: $0;
- distribution: $0;
- sales staff: 0;
- production: 0;
- adoption and revenue: 0;
- net income: -$1,665,000;
- original composite: 0.5115;
- original Round 1 PI: 55.23 (`+0.23` from 55).

Under GSP-R1-15, the same decisions produce:

- capped composite: 0.2500;
- index change: -5.00;
- Round 1 PI: 50.00;
- gap behind Lumen Devices: 8.60 points instead of 3.37.

Game #20 is not backfilled or modified; it remains historical verification evidence. The recalibration applies prospectively when rounds are processed after deployment.

## Regression coverage

Added three tests:

1. `test_voluntary_commercial_inactivity_caps_composite`
   - Gives an Apex-shaped team dominant fit signals but zero commercial commitment.
   - Asserts composite `0.25`, index change `-5.00`, and index value `95.00` from a test starting PI of 100.
2. `test_pre_revenue_commercial_commitment_is_not_inactive`
   - Zero revenue with production, promotion, distribution, and sales staffing does not trigger the cap.
3. `test_compliance_blocked_seller_is_not_commercially_inactive`
   - A frozen zero-revenue seller with real commercial decisions does not trigger the voluntary-inactivity cap.

Verification:

```text
Targeted recalibration tests: 3/3 passed
Fresh core.tests.test_cc18_compliance suite: 14/14 passed
python3 manage.py check: no issues
```

## Pedagogical result

R&D, product development, ESG, leverage, and resilience remain visible and credited in their own components and reports. They can no longer cause a team with no production and no go-to-market commitment to improve its overall PI. A fully inactive Round 1 firm now falls from the 55 starting baseline to 50, while genuine pre-revenue strategies remain eligible for the normal composite.
