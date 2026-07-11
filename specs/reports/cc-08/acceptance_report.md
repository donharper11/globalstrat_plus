# CC-08 Acceptance Report — Consumer Electronics Supply-Chain Seed Data

**Spec:** `specs/CC-08-scenario-seed-data.md`
**Branch:** `cc-08-scenario-seed-data`
**Scenario file:** `backend/scenarios/consumer_electronics_2026.yaml`
**Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — all acceptance criteria met.

---

## 1. Verify-Before-Edit (STANDING-DISCIPLINE §1)

Verification performed against the **loader and ORM models** (the authoritative
contract), not the CC-01 prose examples:

- `python3 manage.py check` → *System check identified no issues (0 silenced).*
- `showmigrations core` → SC migrations applied: `0041_sc_scenario_content`,
  `0042_decision_plant_sc_extensions` (+ CC-05 promotions). Graph clean.
- Pre-edit YAML scan: all 6 target SC sections were **absent** (`suppliers`,
  `shipping_lanes`, `trade_finance_instruments`, `compliance_regimes`,
  `resilience_parameters`, `freight_market` → MISSING). Expected — CC-08 adds them.
- Ghost-model check (§1.8): all 6 SC models + `EventTemplateDefinition` are
  `managed=True` and have **physical tables** (`sc_supplier`, `sc_shipping_lane`,
  `sc_trade_finance_instrument`, `sc_compliance_regime`, `sc_resilience_parameters`,
  `sc_freight_market`, `event_template_definition`). No ghosts among CC-08 targets.
- `validate_scenario_yaml()` reviewed: enforces required sections + cultural/
  origin-trust market codes only. The CC-01 §8 SC cross-reference rules are **not**
  runtime-enforced; data was nonetheless authored to satisfy them.

No MISMATCH halts were required (see §5 for two schema-shape resolutions that the
loader itself dictated).

- **Post-load cross-reference audit (CC-01 §8):** all 9 applicable rules were run
  programmatically against the loaded ORM rows. One error was caught and fixed — a
  dangling `multi_source_substitutability.supplier_id: byd_china` on `catcher_taiwan`
  (the actual supplier id is `byd_electronics_china`). The loader's `validate_scenario_yaml()`
  does not enforce §8, so it had loaded silently; corrected in the YAML, reloaded, and
  re-validated → 0 errors. Rules confirmed: R1 (supplier country is a lane origin),
  R5 (`accepts_trade_finance` resolves), R7 (≥2 suppliers per specialization),
  R8 (resilience weights sum 1.0), R9 (substitutability refs resolve).

---

## 2. Content Counts (authored)

| Content | Minimum | Authored |
|---|---:|---:|
| Suppliers | 20 | **25** |
| Shipping lanes | 18 | **20** |
| Trade finance instruments | 6 | **6** |
| Compliance regimes | 5 | **5** |
| Supply-chain event templates | 20 | **20** |
| Resilience parameter singleton | 1 | **1** |
| Freight market singleton | 1 | **1** |

**Required-coverage checks (all PASS):**

- Supplier countries: `CN, DE, JP, KR, MY, TW, US, VN` — covers required CN, TW, KR, JP, VN, MY, DE, US.
- Supplier specializations: `battery, camera_module, display, enclosure, final_assembly, pcb, power_management, semiconductor` — covers all 8 required.
- Xinjiang-exposed suppliers (UFLPA pedagogy, CC-01 §6.1 requires ≥2): `smic_china, boe_china, luxshare_china, sunny_optical_china` (4).
- Trade-finance instruments: `advance_payment, documentary_collection, fx_forward, letter_of_credit, open_account, sinosure_credit_insurance` — all 6 required.
- Compliance regimes: `uflpa, cbam, us_bis_entity_list, customs_documentation, product_safety_certification` — all 5 required themes.
- SC events include all 10 named requirements: Taiwan earthquake, Red Sea disruption,
  container rate shock, supplier financial distress, port congestion, customs
  documentation rejection, LC document rejection, CNY appreciation, UFLPA detention,
  CBAM phase-in cost shock (+10 more incl. BIS expansion, rare-earth licensing,
  Panama drought, typhoon, air-freight crunch, cross-strait, quality recall, and two
  `opportunity`-type events: CNY depreciation windfall, BRI port expansion).
- Lane origins cover all 8 supplier countries; lane modes include sea+air broadly,
  rail on the two China→Europe BRI corridors (`cn_shanghai_to_de_hamburg`,
  `cn_chengdu_to_de_duisburg`), road off.
- `resilience_score_weights` sum = **1.0** (±0.01 tolerance satisfied).

---

## 3. Loader Output (`load_scenario --flush`)

`python3 manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml --flush`

```
Flushed scenario id=3
Created scenario: Consumer Electronics 2026 (id=4)
  Markets loaded: ['AFR', 'APAC', 'EU', 'LATAM', 'NA'] (5-market mode)

=== Scenario Load Complete ===
  ComplianceRegime: 5
  EventTemplateDefinition: 38          # 18 pre-existing + 20 supply_chain
  FreightMarket: 1
  ResilienceParameters: 1
  ShippingLane: 20
  Supplier: 25
  TradeFinanceInstrument: 6
  TOTAL RECORDS: 2144
```

(No live games/teams/rounds existed prior to flush — verified `game=0, team=0,
round=0` — so `--flush` destroyed no gameplay data.)

---

## 4. ORM Count Verification (post-load)

Queried via `manage.py shell` against scenario `Consumer Electronics 2026`:

```
SC events (category=supply_chain): 20
Supplier: 25   supplier countries: CN DE JP KR MY TW US VN
specializations: battery camera_module display enclosure final_assembly pcb power_management semiconductor
xinjiang suppliers: smic_china boe_china luxshare_china sunny_optical_china
tsmc quality/reliability/price: 0.960 / 0.930 / 45.00     (decimal precision intact)
TradeFinanceInstrument: advance_payment documentary_collection fx_forward letter_of_credit open_account sinosure_credit_insurance
ComplianceRegime: cbam customs_documentation product_safety_certification uflpa us_bis_entity_list
ShippingLane destinations: BR CN DE NG US
ResilienceParameters weights sum: 1.0
FreightMarket fuel base: 80.00
rail lanes: cn_shanghai_to_de_hamburg, cn_chengdu_to_de_duisburg
```

`python3 manage.py check` → **System check identified no issues (0 silenced).**

---

## 5. Known Calibration Assumptions & Schema-Shape Decisions

Per spec §5, questionable numeric assumptions and shape decisions are recorded
here rather than blocking the bundle.

### 5.1 Market region → representative country (structural, deliberate)

`ShippingLane.origin_country` / `destination_country` are `CharField(max_length=2)`
(ISO-2). The scenario's markets are **regions** (`NA, APAC, EU, AFR, LATAM`) with no
country field, and `APAC/AFR/LATAM` exceed 2 chars. Destination markets are therefore
represented by a canonical country and the region is carried in `zone`:

| Market | Region name | Canonical dest country |
|---|---|---|
| NA | North America | US |
| APAC | East Asia | CN |
| EU | Western Europe | DE |
| AFR | Africa | NG (matches NGN currency) |
| LATAM | South America | BR (matches BRL currency) |

Downstream lane→market association (CC-10/12/15) should map via this convention or
via `zone`. Flagged for the spec author; not a blocking mismatch.

### 5.2 `trade_finance_instruments` shape (loader-dictated)

CC-01 §6.3 shows a **mapping keyed by instrument name**. The loader
(`load_scenario.py`) iterates a **list** and reads `tf['id']`
(`tf_data if isinstance(list) else tf_data.get('instruments', [])`). The mapping form
would materialize **zero** rows. Authored as a list with explicit `id` — the shape the
loader actually consumes. All 6 rows materialized.

### 5.3 Supply-chain event schema (loader-dictated)

CC-01 §6.5 shows SC events with `id` + `trigger_probability_per_round` + SC-specific
keys. The events loader materializes `EventTemplateDefinition` and **requires `name`**,
reading `probability_per_round` (not `trigger_probability_per_round`). SC events were
authored with the real Event schema (`name`, `category: supply_chain`, `severity`,
`probability_per_round`, …). CC-01-style descriptive keys (`teaches`,
`affected_suppliers`, `affected_lanes`, `mode_rate_multiplier`, `capacity_reduction_pct`,
`type: opportunity`, …) are retained on each entry for documentation and downstream
CC bundles; the current loader ignores unrecognized keys (no crash, no row loss).

### 5.4 Numeric calibration (plausible, not final — per §5 / §7)

- Supplier prices ($10–$45/unit), lead times (22–45 d), quality (0.80–0.96) and
  reliability (0.84–0.95) are spread to make sourcing tradeoffs visible; not sourced
  from real cost curves.
- `origin_trust_to_buyers` skews negative for China/Xinjiang-exposed suppliers into
  NA/EU and positive for JP/DE/US, so dashboard origin-risk signals are visible.
- Lane sea rates ($700–$4,100/TEU) and air rates ($3.80–$12.00/kg) scale roughly with
  distance/route difficulty; event multipliers (e.g., Red Sea sea×2.8) are illustrative.
- Event `probability_per_round` values are low but non-zero (0.03–0.12).
- Compliance enforcement probabilities and penalty magnitudes are pedagogical
  placeholders (e.g., UFLPA 0.15/round, 100% shipment loss; BIS $10M penalty).

None of these block CC-9 through CC-15, which need coherent rows to build/test against.

---

## 6. Acceptance Criteria (spec §6)

1. ✅ `consumer_electronics_2026.yaml` contains all required SC sections.
2. ✅ Scenario loads with `load_scenario --flush`.
3. ✅ ORM counts show all minimums materialized (see §3–§4).
4. ✅ `python3 manage.py check` passes (0 issues).
5. ✅ This report records content counts, loader output, ORM output, and calibration assumptions.
6. ✅ No frontend or engine code changed — only the scenario YAML (+ this report).
