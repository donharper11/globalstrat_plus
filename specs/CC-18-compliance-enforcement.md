# CC-18 — Compliance Enforcement

**Bundle:** CC-18 · **Depends on:** CC-9 (customs/compliance decisions), CC-8 (regime seed data), CC-19B (P&L plumbing)
**Observes:** `STANDING-DISCIPLINE.md`, rework `REWORK_SPEC_2026-07-13.md` §4 W9
**Status:** Built (this rework).

## 1. Purpose
Compliance regimes were surfaced but never enforced — the **detention →
market-freeze → remediation-cost → reputation** loop was open, so UFLPA/CBAM/etc.
teaching value was unrealized. This closes the loop for the regimes whose triggers
have a real signal in team decisions.

## 2. Enforcement model (`core/engine/compliance_engine.py`)
Runs **before revenue** (a freeze must block this round's sales). Deterministic
(seeded). Per team × regime × enforcing market:

1. **Carry forward** still-active freezes from prior `ComplianceEnforcementEvent`s
   (`freeze_until_round >= this round`).
2. **Trigger** — evaluated only where a signal exists (else skipped, not faked):
   - `tier_2_3_xinjiang_exposure_above_threshold` (UFLPA): fires when the team's
     allocation to Xinjiang-adjacent suppliers (`supplier.tier_2_3_profile.
     risk_flags.xinjiang_adjacent`) exceeds `trigger_threshold_pct`; **mitigated**
     by `tier_2_3_visibility_investment == 'comprehensive'`.
   - `incomplete_or_misclassified_customs_documentation`: fires when the team has
     no `CustomsClassificationDecision` for the destination market.
   - other triggers (BIS restricted-tech, product-safety cert) → **skipped** (no
     determinable signal — no fake enforcement).
3. **Probability** = `baseline_enforcement_probability_per_round`, reduced by the
   regime's mitigation `reduces_enforcement_probability_pct` when mitigated.
4. **Fire** → a `ComplianceEnforcementEvent` records: remediation/penalty **cost**
   (booked to the P&L via `context.compliance_costs`), a **market-access freeze**
   through `freeze_until_round` (blocks sales in `calculate_revenue` via
   `context.compliance_freezes`), and a **reputation impact**
   (`shipment_value_loss_pct`).

## 3. Integration
- `financials.py` — `operating_income` subtracts `compliance_cost`.
- `revenue.py` — a frozen `(team, market)` books **zero** sales and records
  `compliance_lost_revenue`.
- New model `ComplianceEnforcementEvent` (migration `0054`).
- Endpoints: `GET .../sc/compliance-events/` (student); events also aggregated
  into the instructor SC panel per team.
- Frontend: enforcement actions shown on the student SC dashboard **Compliance
  Risk** card and the instructor SC panel **Compliance** column.

## 4. Acceptance — `test_cc18_compliance` (7)
UFLPA fires on Xinjiang exposure (cost 500k, 2-round freeze, reputation 1.0); no
exposure → no fire; mitigation flag + 70% reduction; customs fires on missing docs
(120k, 1-round hold); docs present → no fire; **freeze blocks revenue** (zero sales
+ lost-revenue recorded); **compliance cost hits net income**. Full suite green;
`manage.py check` clean; migration applied; frontend build clean.

## 5. Out of scope
Reputation impact is recorded (and surfaced) but not yet fed back into demand;
the modeled teeth are the cost + market freeze (real P&L / sales impact). CBAM
(carbon-sector, no CE product overlap) and BIS/product-safety (no signal) are not
enforced.
