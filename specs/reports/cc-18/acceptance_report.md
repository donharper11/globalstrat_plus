# CC-18 Acceptance Report — Compliance Enforcement

**Spec:** `specs/CC-18-compliance-enforcement.md` · **Rework:** W9 · **Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — the detention → freeze → cost → reputation loop is closed and tested.

## What changed
Compliance regimes were surfaced but never enforced. Now `compliance_engine.
enforce_compliance` (runs before revenue, deterministic) evaluates each regime
whose trigger has a real signal, fires detentions, books remediation/penalty cost
to the P&L, freezes the enforcing market, and records a reputation impact on a new
`ComplianceEnforcementEvent` (migration 0054). Integrated into `financials.py`
(cost → operating income) and `revenue.py` (frozen market → zero sales + lost
revenue). Surfaced on the student SC dashboard and the instructor SC panel.

## Tests — `test_cc18_compliance` (7)
```
$ python3 manage.py test core.tests.test_cc18_compliance --noinput
Ran 7 tests ... OK
```
- `test_uflpa_fires_on_xinjiang_exposure` — 100% smic_china (Xinjiang-adjacent)
  → event with cost **$500,000**, freeze through R2 (2-round), reputation **1.0**;
  cost booked and `(team, NA)` frozen.
- `test_no_xinjiang_exposure_no_uflpa` — TW-only sourcing → no event.
- `test_uflpa_mitigated_flag_and_reduction` — comprehensive tier-2/3 visibility →
  `mitigated=True`, reduction **70%**.
- `test_customs_fires_when_docs_missing` — no customs classification → **$120,000**
  penalty, 1-round hold.
- `test_customs_not_fired_when_docs_present` — classification on file → not triggered.
- `test_freeze_blocks_revenue` — a frozen `(team, market)` → **no revenue booked**,
  `compliance_lost_revenue > 0` (through real `calculate_revenue`).
- `test_compliance_cost_hits_net_income` — $120k cost → `net_income` = **−120,000**
  (through real `generate_financial_statements`).

Full suite green; `manage.py check` clean; migration 0054 applied; frontend build clean.

## Honest scope
Only regimes with a determinable trigger signal are enforced (UFLPA, customs docs);
BIS/product-safety/CBAM are skipped rather than faked. Reputation impact is recorded
and surfaced but not yet fed back into demand — the modeled teeth are the cost +
market freeze.
