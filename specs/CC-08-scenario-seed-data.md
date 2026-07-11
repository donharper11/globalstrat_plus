# CC-8: Consumer Electronics Supply Chain Seed Data

**Project:** globalstrat+  
**Spec Type:** Build pipeline - scenario content  
**Depends on:** `CC-01-scenario-schema.md`, `CC-04-data-model.md`, `CC-06-pedagogical-design-note.md`  
**Observes:** `STANDING-DISCIPLINE.md`  
**Status:** Drafted for builder execution

---

## 1. Purpose

Create enough Consumer Electronics supply-chain seed data for an end-to-end playable loop. Calibration realism is secondary in this bundle; the primary goal is complete, coherent data that exercises every supply-chain surface and engine input.

---

## 2. Scope

Edit the production scenario YAML:

- `backend/scenarios/consumer_electronics_2026.yaml`

Add or extend these top-level sections:

- `suppliers`
- `shipping_lanes`
- `trade_finance_instruments`
- `compliance_regimes`
- `resilience_parameters`
- `freight_market`
- supply-chain `events` entries with `category: supply_chain`

Use `backend/scenarios/consumer_electronics_plus_skeleton.yaml` only as a schema reference. Do not make the skeleton the production scenario.

---

## 3. E2E-First Content Requirements

Minimum production content:

| Content | Minimum |
|---|---:|
| Suppliers | 20 |
| Shipping lanes | 18 |
| Trade finance instruments | 6 |
| Compliance regimes | 5 |
| Supply-chain event templates | 20 |
| Resilience parameter singleton | 1 |
| Freight market singleton | 1 |

Supplier countries must cover CN, TW, KR, JP, VN, MY, DE, and US.

Supplier specialization must cover semiconductor, display, battery, enclosure, pcb, final_assembly, camera_module, and power_management.

Shipping lanes must connect key supplier origins to destination markets already present in the scenario. Verify market codes and country assumptions from the existing YAML before writing.

Trade finance instruments must include open_account, letter_of_credit, documentary_collection, advance_payment, sinosure_credit_insurance, and fx_forward.

Compliance regimes must include UFLPA-like forced-labor detention risk, CBAM-like carbon reporting/cost risk, BIS/entity-list export-control risk, customs documentation risk, and product safety/certification risk.

Supply-chain events must include Taiwan earthquake, Red Sea disruption, container rate shock, supplier financial distress, port congestion, customs documentation rejection, LC document rejection, CNY appreciation, UFLPA detention, and CBAM phase-in cost shock.

---

## 4. Verification Before Editing

Run and record:

```bash
cd /home/ubuntu/projects/globalstrat+/backend
python3 manage.py check
python3 manage.py showmigrations core | tail -20
python3 - <<'CHECK'
import yaml
from pathlib import Path
p = Path('scenarios/consumer_electronics_2026.yaml')
data = yaml.safe_load(p.read_text())
print(data.keys())
print('markets', [m.get('code') for m in data.get('markets', [])])
print('events', len(data.get('events', [])))
CHECK
```

If required sections use a different shape than CC-1 assumes, halt with a MISMATCH report.

---

## 5. Implementation Guidance

Use simple, transparent calibration values. Prefer consistency over realism:

- prices and lead times should be plausible but not final
- reliability and quality should vary enough to test tradeoffs
- country/origin trust should vary enough to make dashboard risks visible
- lane mode availability should include sea and air broadly, rail/road selectively
- event probabilities should be low but non-zero

Mark questionable numeric assumptions in `specs/reports/cc-08/acceptance_report.md`. Do not block the bundle on perfect calibration.

---

## 6. Acceptance Criteria

CC-8 is complete when:

1. `consumer_electronics_2026.yaml` contains all required SC sections.
2. The scenario loads with `python3 manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml --flush`.
3. ORM counts show the minimum records materialized.
4. `python3 manage.py check` passes.
5. `specs/reports/cc-08/acceptance_report.md` records content counts, loader output, ORM count output, and known calibration assumptions.
6. No frontend or engine code is changed in this bundle.

---

## 7. Builder Notes

This is an E2E enablement bundle. Do not overfit supplier values. The objective is enough valid content for CC-9 through CC-15 to build and test against real rows.
