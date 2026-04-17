# CC-3: globalstrat+ Engine Logic

**Project:** globalstrat+ (Chinese executive supply-chain-centered strategy simulation)
**Spec Type:** Foundation — per-round engine pipeline and algorithmic behavior
**Depends on:** `specs/CC-01-scenario-schema.md`, `specs/CC-02-decision-taxonomy.md`
**Observes:** `specs/STANDING-DISCIPLINE.md` (including §1.8 model-to-table verification and §1.9 client version alignment)
**Status:** Ready for Claude Code execution

---

## 1. Purpose

This spec defines how the globalstrat+ engine consumes supply chain decisions (from CC-2) and scenario content (from CC-1) to produce per-round outcomes. It specifies:

- Which existing GlobalStrat pipeline steps are inherited unchanged.
- Which existing steps need extending to incorporate SC inputs.
- Which entirely new steps need inserting, and where.
- The algorithmic behavior (as pseudocode) for every new or extended step.
- The discipline separating deterministic Phase 1 math from LLM-driven Phase 2 narrative.
- How supply-chain events perturb configuration over single and multi-round windows.
- Instructor override hooks and determinism guarantees.

It does NOT define Django models (CC-4), migration code, serializers, API endpoints, or frontend rendering. CC-3 is the algorithmic contract; CC-4 translates that contract into models and code.

---

## 2. Preconditions — Engine Inventory Report

Per STANDING-DISCIPLINE.md §1, CC-3 requires an explicit inventory of the existing engine before extending it. EXTEND in CC-3 means modifying live code paths (`calculate_cogs`, `calculate_logistics_tariffs`, the `advance_round` orchestration), not just adding fields. A naming mismatch or missed call site is far more expensive than in CC-2.

### 2.1 Engine Inventory Report

Claude Code produces a report at `specs/reports/CC-03-engine-inventory.md` with four sections:

**Section A — Pipeline orchestration:**
- File containing `advance_round` (or whatever the round-advance entry point is called)
- Function signature and ordered list of Phase 1 steps (sync, deterministic)
- Ordered list of Phase 2 steps (background thread, LLM-driven)
- How the two phases are invoked (async task queue, threading, etc.)

**Section B — Cost function roster:**

For every function in `engine/costs.py` (or wherever costs live):

```
Function: <name>
File: <path:line>
Signature: <args and return type>
Called from: <list of call sites with file:line>
Consumes decisions from: <which Decision model fields>
Consumes scenario fields: <which scenario YAML sections>
Produces: <what values>
```

Minimum coverage: `calculate_logistics_tariffs`, `calculate_inventory_costs`, `calculate_cogs`, `calculate_entry_mode_overhead`. Enumerate any additional cost functions discovered.

**Section C — Event system:**
- How events are declared (model, table, scenario YAML section)
- How trigger probabilities are evaluated per round
- Random seed handling (does the engine use a seeded RNG for reproducibility?)
- How event effects are applied to team state
- Whether multi-round events are already supported (duration_rounds, recovery_rounds) or whether this is a new capability

**Section D — Model-to-table sanity pass:**

For every engine-referenced model — `RoundState`, `TeamState`, `Event`, `DecisionPlant`, `DecisionESG`, and any others surfaced in Sections A–C — verify physical table existence per STANDING-DISCIPLINE §1.8. Report any ghosts.

### 2.2 Halt Conditions

Per STANDING-DISCIPLINE §3, Claude Code halts with a MISMATCH report if:

1. `advance_round` (or the actual entry point) does not exist or has a different signature than this spec assumes.
2. Any of the four named cost functions does not exist, has a different name, or has a different signature.
3. The event system does not support probabilistic triggers or does not use a seeded RNG (this would require a design decision by the spec author before CC-3 proceeds).
4. Any engine-referenced model turns out to be a ghost (per §1.8).
5. Phase 1 / Phase 2 split does not exist as described in the CC-1 scan (the scan indicated it does; verify).

### 2.3 Commit the Inventory

```bash
git checkout -b cc-03-engine-logic
git add specs/reports/CC-03-engine-inventory.md
git commit -m "CC-3: engine inventory report for GlobalStrat pipeline"
```

CC-3 proceeds only after the inventory is clean and the spec author has reviewed any halt conditions.

---

## 3. Pipeline Classification Framework

Every engine step in globalstrat+ is classified as:

- **INHERIT** — GlobalStrat step, no changes.
- **EXTEND** — GlobalStrat step, modified to consume new SC inputs.
- **NEW** — step does not exist in GlobalStrat.

The principle established in the design conversation holds: most of GlobalStrat's pipeline INHERITs. The SC layer extends four existing steps and inserts seven new ones.

---

## 4. Phase 1 Pipeline — Full Ordered Sequence

Phase 1 is synchronous, deterministic, and produces the round's financial and operational outcomes. Every Phase 1 step must be reproducible given the same inputs and RNG seed.

The proposed globalstrat+ Phase 1 ordering (final ordering confirmed after the inventory report in §2):

| # | Step | Class | Notes |
|---|---|---|---|
| 1 | Lock team submissions for the round | INHERIT | — |
| 2 | Apply instructor overrides (if any) | INHERIT | — |
| 3 | Evaluate probabilistic events (including SC events) | EXTEND | Existing event firing extended to include `category: supply_chain` events |
| 4 | Apply event effects to team state | EXTEND | Extended to handle SC event effect fields (affected_suppliers, affected_lanes, mode_rate_multiplier, etc.) |
| 5 | Decrement active multi-round event timers | NEW | Support for `duration_rounds` and `recovery_rounds` |
| 6 | **Supplier matching & procurement cost** | NEW | §6.1 algorithm |
| 7 | **Lane cost & lead time calculation** | NEW | §6.2 algorithm |
| 8 | R&D / platform investment processing | INHERIT | — |
| 9 | Feature unlock check | INHERIT | — |
| 10 | Marketing mix matching to segments | INHERIT | — |
| 11 | **Supplier-origin trust adjustment** (applied to segment preferences) | NEW | §6.6 algorithm — symmetric extension of existing origin-trust |
| 12 | Bass adoption & competitive share calculation | INHERIT | — |
| 13 | Base revenue calculation | INHERIT | — |
| 14 | **Compliance scoring & enforcement check** | NEW | §6.4 algorithm |
| 15 | Apply compliance enforcement consequences (if triggered) | NEW | Revenue penalties, market access freezes |
| 16 | COGS calculation | EXTEND | Incorporates §6 step 6 procurement cost + §6 step 7 logistics cost |
| 17 | Logistics/tariffs calculation | EXTEND | Now consumes lane-level modal mix, CBAM carbon-tariff adjustments |
| 18 | Inventory & buffer cost | EXTEND | Extended to incorporate buffer policy from Inventory & Resilience decisions |
| 19 | Entry mode overhead | EXTEND | Adds SC build-out costs for new markets |
| 20 | Plant cost | INHERIT | Still contributes; now one input among several |
| 21 | OpEx accumulation (non-SC categories) | INHERIT | R&D opex, marketing opex, org, comms, gov relations, alliances |
| 22 | **Trade finance cost & cash conversion** | NEW | §6.3 algorithm |
| 23 | **FX hedge settlement** | NEW | §6.7 algorithm — mark hedges to market at round end |
| 24 | Interest & financing | INHERIT | — |
| 25 | Tax | INHERIT | — |
| 26 | **Resilience scoring** | NEW | §6.5 algorithm — composite score, component breakdown retained for instructor panel |
| 27 | Performance index / Balanced Scorecard | EXTEND | BSC already exists; resilience score added as a new KPI under the operations perspective |
| 28 | Update market state for next round | INHERIT | — |
| 29 | Seed next-round event probability evaluation state | INHERIT | — |

The exact insertion points for NEW steps and the precise order of EXTEND invocations are confirmed against the inventory report in §2 before CC-4 implements.

---

## 5. Phase 2 Pipeline — LLM-Driven Narrative

Phase 2 runs in a background thread. Its outputs are text and structured-for-display only — **Phase 2 outputs never feed back into Phase 1 scoring.** This invariant is load-bearing: it ensures the simulation remains deterministic, reproducible, and replay-safe regardless of LLM availability, latency, or content variation.

### 5.1 INHERIT Phase 2 steps

| Step | Notes |
|---|---|
| Competitor AI reactions | Existing reactive-AI system |
| Event narrative generation (non-SC events) | Existing |
| Stakeholder briefings (investors, analysts, journalists) | Existing; extended with SC-awareness via prompt tuning (see §8) |
| Instructor-facing round summaries | Existing |

### 5.2 NEW Phase 2 steps

| Step | Notes |
|---|---|
| **SC event narrative** | When an SC event fires in Phase 1 step 3, generate a scenario-grounded narrative explaining what happened, who's affected, and what the team's exposure looked like |
| **Supply Chain Dashboard narrative** | Per-team narrative summarizing posture, concentration risks, resilience score drivers, suggested next-round priorities |
| **Supplier persona updates** | When a supplier enters disrupted or distressed state, generate a persona-voiced update (e.g., TSMC sales rep notifying of allocation cuts during post-earthquake recovery) |
| **Compliance warning notice** | When a team's compliance enforcement probability crosses a threshold (e.g., UFLPA exposure high, CBAM reporting gap widening), generate a warning narrative |
| **Trade finance institution interactions** | When relevant (LC rejection, Sinosure claim processing, FX hedge settlement with significant P&L), generate institution-voiced narrative |

### 5.3 Inference routing

Per the model-routing philosophy established elsewhere in the portfolio: persona-heavy narrative generation (supplier voices, institution interactions) routes to cloud Qwen-Max for quality; structured/bounded tasks (dashboard summaries with fixed templates) route to local Qwen 2.5 family via the centralized dispatcher. The exact routing configuration is a runtime infrastructure decision, not a CC-3 algorithmic concern. CC-3 only requires that the Phase 2 orchestrator support both paths.

---

## 6. Key Algorithms

Pseudocode for the seven NEW and four EXTEND algorithms. All names use the CC-2 decision field names and CC-1 scenario schema fields verbatim — Claude Code cross-checks each name against the engine inventory report per STANDING-DISCIPLINE §1 before implementation.

### 6.1 Supplier matching & procurement cost

**Purpose:** Convert supplier allocation decisions into per-category procurement cost, effective quality, effective reliability, and weighted lead time.

```
FUNCTION calculate_procurement_cost(team, round_state):
    procurement_output = {}
    FOR EACH critical_input_category IN team.product_bom.critical_inputs:
        allocations = team.sourcing_decisions.for_category(critical_input_category)
        category_total_cost = 0
        weighted_quality = 0
        weighted_reliability = 0
        weighted_lead_time = 0

        FOR EACH (supplier_id, allocation_pct, volume_commitment) IN allocations:
            supplier = scenario.suppliers[supplier_id]
            supplier_state = round_state.supplier_states[supplier_id]

            # Base unit price
            unit_price_src_ccy = supplier.base_unit_price_usd

            # Volume discount tier application
            FOR EACH tier IN supplier.volume_discount_tiers (descending threshold):
                IF volume_commitment >= tier.threshold_units:
                    unit_price_src_ccy *= (1 - tier.discount_pct / 100)
                    BREAK

            # Supplier state modifiers (from active events)
            IF supplier_state.in_disrupted_state:
                unit_price_src_ccy *= supplier_state.disruption_cost_multiplier

            # Reliability degradation (for events like supplier_financial_distress)
            effective_reliability = supplier.reliability_rating * supplier_state.reliability_modifier

            # FX conversion to team home currency
            fx_rate = round_state.fx_rates[supplier.country_currency, team.home_currency]
            unit_price_home_ccy = unit_price_src_ccy * fx_rate

            # Volume from this supplier
            category_demand_units = team.product_bom.demand_for_category(critical_input_category)
            units_from_supplier = category_demand_units * (allocation_pct / 100)

            # Accumulate
            category_total_cost += units_from_supplier * unit_price_home_ccy
            weighted_quality += supplier.quality_rating * (allocation_pct / 100)
            weighted_reliability += effective_reliability * (allocation_pct / 100)

            # Lead time with event adjustments
            supplier_lead_time = supplier.lead_time_days_baseline + supplier_state.additional_lead_time_days
            weighted_lead_time += supplier_lead_time * (allocation_pct / 100)

        procurement_output[critical_input_category] = {
            "total_cost": category_total_cost,
            "effective_quality": weighted_quality,
            "effective_reliability": weighted_reliability,
            "weighted_lead_time_days": weighted_lead_time
        }

    RETURN procurement_output
```

**Feeds into:** Phase 1 step 16 (COGS) consumes `total_cost` per category. Product-level quality scores (used in revenue/Bass adoption, step 10) incorporate `effective_quality` from this output — this is the pathway by which supplier selection affects market outcomes, not just cost.

### 6.2 Lane cost & lead time calculation

**Purpose:** Convert modal mix decisions into per-lane logistics cost and weighted lead time.

```
FUNCTION calculate_lane_cost_and_lead_time(team, round_state):
    lane_output = {}
    FOR EACH lane_id IN team.active_lanes:
        lane = scenario.shipping_lanes[lane_id]
        lane_state = round_state.lane_states[lane_id]
        lane_volume_teu = round_state.team_volume_by_lane[lane_id]

        lane_total_cost = 0
        lane_weighted_lead_time = 0

        FOR EACH mode IN [sea, air, rail, road]:
            mode_pct = team.logistics_decisions[lane_id][f"mode_{mode}_pct"]
            IF mode_pct == 0 OR NOT lane.modes[mode].available:
                CONTINUE

            # Base rate
            base_rate = lane.modes[mode].baseline_cost_per_teu_usd   # (or per_kg for air)

            # Freight market multiplier (global, time-varying)
            current_rate = base_rate * round_state.freight_market.current_multiplier[mode]

            # Fuel pass-through adjustment
            fuel_delta_pct = (round_state.fuel_index - scenario.freight_market.fuel_index_baseline) / scenario.freight_market.fuel_index_baseline
            current_rate *= (1 + fuel_delta_pct * lane.modes[mode].fuel_pass_through_pct / 100)

            # Event-driven lane state multipliers
            IF lane_state.active_disruption:
                current_rate *= lane_state.active_disruption.mode_rate_multiplier.get(mode, 1.0)

            # Mode-specific volume and cost
            mode_volume = lane_volume_teu * (mode_pct / 100)
            lane_total_cost += mode_volume * current_rate

            # Lead time
            mode_lead_time = lane.modes[mode].baseline_lead_time_days
            IF lane_state.active_disruption:
                mode_lead_time += lane_state.active_disruption.additional_lead_time_days
            lane_weighted_lead_time += (mode_pct / 100) * mode_lead_time

        # Customs processing (CN home teams using processing trade get a lead-time reduction)
        IF team.home_country == CN AND team.customs_classification[lane.destination_country] == processing_trade:
            lane_weighted_lead_time += lane.customs_processing_days_baseline * 0.6   # 40% faster
        ELSE:
            lane_weighted_lead_time += lane.customs_processing_days_baseline

        lane_output[lane_id] = {
            "total_cost": lane_total_cost,
            "weighted_lead_time_days": lane_weighted_lead_time
        }

    RETURN lane_output
```

**Feeds into:** Phase 1 step 17 (logistics/tariffs EXTEND) consumes `total_cost`. Lead times feed into inventory calculations (step 18) and delivery reliability for revenue (step 13).

### 6.3 Trade finance cost & cash conversion

**Purpose:** Compute payment instrument cost for each buyer transaction, determine cash conversion cycle impact, evaluate LC rejection and open-account default probabilities.

```
FUNCTION calculate_trade_finance(team, round_state):
    trade_finance_cost = 0
    cash_conversion_adjustment_days = 0
    revenue_at_risk = 0

    FOR EACH (segment, market) IN team.sales_matrix:
        instrument_id = team.trade_finance_decisions[segment, market].buyer_payment_instrument
        instrument = scenario.trade_finance_instruments[instrument_id]
        transaction_value = team.revenue_by_segment_market[segment, market]

        # Instrument cost
        instrument_cost = transaction_value * (instrument.cost_bps_of_transaction / 10000)
        trade_finance_cost += instrument_cost

        # Cash conversion impact (days of receivable delay)
        cash_conversion_adjustment_days += instrument.processing_lead_days * (transaction_value / team.total_revenue)

        # Risk: LC rejection probability
        IF instrument_id == letter_of_credit:
            doc_prep = team.trade_finance_decisions[segment, market].lc_doc_prep_investment
            rejection_prob = instrument.rejection_probability_baseline * doc_prep_modifier(doc_prep)
            IF seeded_random() < rejection_prob:
                # Revenue for this transaction delayed 1 round + remediation cost
                delay_transaction(segment, market, rounds=1)
                fire_event("lc_rejection", affected_segment=segment, market=market)

        # Risk: open account buyer default
        IF instrument_id == open_account:
            default_prob = instrument.buyer_default_probability_baseline
            IF seeded_random() < default_prob:
                revenue_at_risk += transaction_value
                fire_event("buyer_default", affected_segment=segment, market=market)

    # Apply Sinosure coverage if team is CN home and enrolled
    IF team.home_country == CN:
        FOR EACH market IN team.sinosure_enrolled_markets:
            coverage_pct = team.sinosure_coverage_pct_per_market[market]
            sinosure_premium = team.receivables[market] * (scenario.trade_finance_instruments.sinosure_coverage.cost_pct_of_insured_value / 100) * (coverage_pct / 100)
            # BRI market subsidy
            IF market IN scenario.bri_markets:
                sinosure_premium *= (1 - scenario.trade_finance_instruments.sinosure_coverage.bri_market_premium_subsidy_pct / 100)
            trade_finance_cost += sinosure_premium
            # Sinosure absorbs losses up to coverage ceiling when default events fire
            # (handled in event effect application, not here)

    RETURN {
        "trade_finance_cost": trade_finance_cost,
        "cash_conversion_adjustment_days": cash_conversion_adjustment_days,
        "revenue_at_risk": revenue_at_risk
    }
```

**Feeds into:** Phase 1 step 22 (new NEW step). Cash conversion adjustment flows into working capital calculations in interest/financing (step 24).

### 6.4 Compliance scoring & enforcement

**Purpose:** For each compliance regime active in the scenario, evaluate whether enforcement fires against the team this round based on exposure and mitigation.

```
FUNCTION evaluate_compliance_enforcement(team, round_state):
    enforcement_events = []
    FOR EACH regime IN scenario.compliance_regimes:
        IF team.is_not_exposed_to(regime):
            CONTINUE

        # Base probability
        base_prob = regime.baseline_enforcement_probability_per_round

        # Exposure multiplier — regime-specific
        IF regime.id == "uflpa":
            xinjiang_exposure_pct = compute_tier_2_3_xinjiang_exposure(team)
            IF xinjiang_exposure_pct < regime.trigger_threshold_pct:
                CONTINUE
            exposure_multiplier = xinjiang_exposure_pct / regime.trigger_threshold_pct

        ELIF regime.id == "cbam":
            carbon_intensity = compute_team_carbon_intensity(team)
            current_coverage_pct = regime.phase_in_schedule.coverage_for_round(round_state.round_number)
            exposure_multiplier = (carbon_intensity / industry_benchmark) * (current_coverage_pct / 100)

        ELIF regime.id == "us_bis_entity_list":
            # Enforcement fires if team uses restricted tech with restricted countries
            IF NOT team_uses_restricted_tech_with_restricted_country(team, regime):
                CONTINUE
            exposure_multiplier = 1.0   # binary exposure

        ELIF ...   # additional regimes as declared in scenario

        # Mitigation investment reduction
        mitigation_reduction = 0
        FOR EACH (investment_name, investment_config) IN regime.mitigation_investments:
            IF team.has_mitigation_investment(investment_name):
                mitigation_reduction += investment_config.reduces_enforcement_probability_pct / 100

        effective_prob = base_prob * exposure_multiplier * (1 - min(mitigation_reduction, 0.95))

        # Fire or not
        IF seeded_random() < effective_prob:
            enforcement_events.append({
                "regime": regime.id,
                "team": team.id,
                "consequence": regime.detention_consequence  # or equivalent field per regime
            })

    RETURN enforcement_events
```

**Feeds into:** Phase 1 step 15 (apply compliance enforcement consequences). Applied consequences include revenue loss (shipment detention), market access freeze (temporary exclusion from the enforcing market), remediation cost, and reputation impact feeding into stakeholder preferences in subsequent rounds.

### 6.5 Resilience scoring

**Purpose:** Compute a composite resilience score with component breakdown. The score is a KPI displayed to the team; the breakdown is retained for the instructor panel.

```
FUNCTION compute_resilience_score(team, round_state):
    weights = scenario.resilience_parameters.resilience_score_weights
    components = {}

    # Multi-sourcing: 1.0 when every critical category has 2+ suppliers with no single allocation > single_source_threshold
    components["multi_sourcing"] = compute_multi_sourcing_score(
        team, scenario.resilience_parameters.single_source_threshold_pct
    )

    # Geographic diversity: 1.0 when no country supplies > geographic_concentration_threshold across all categories
    components["geographic_diversity"] = compute_geo_diversity_score(
        team, scenario.resilience_parameters.geographic_concentration_threshold_pct
    )

    # Buffer adequacy: fraction of critical SKU-market pairs meeting recommended buffer days
    components["buffer_inventory_adequacy"] = compute_buffer_adequacy_score(
        team, scenario.resilience_parameters.critical_component_buffer_days_recommended
    )

    # Modal flexibility: 1.0 when every active lane has at least 2 available modes with non-zero allocation
    components["modal_flexibility"] = compute_modal_flex_score(team)

    # Tier-2 visibility: function of ESG supplier_audit_program level + sourcing tier_2_3_visibility_investment
    components["tier_2_visibility"] = compute_tier_2_visibility_score(team)

    # Supplier financial health: weighted by supplier reliability_rating and presence in disrupted state
    components["supplier_financial_health"] = compute_supplier_health_score(team, round_state)

    # Weighted sum
    resilience_score = SUM(weights[k] * components[k] FOR k IN components)

    RETURN {
        "score": resilience_score,
        "components": components,
        "weights_used": weights
    }
```

**Feeds into:** Phase 1 step 27 (Balanced Scorecard EXTEND) — resilience score becomes a KPI under the operations perspective. Also feeds into Phase 2 Dashboard narrative (§5.2).

**Pedagogical note:** the component breakdown is the teaching surface. A team with a low score should see *why* — "your multi-sourcing score is 0.3 because semiconductors are 100% TSMC" — not just a scalar.

### 6.6 Supplier-origin trust (symmetric extension of existing origin-trust)

**Purpose:** Extend GlobalStrat's buyer-side origin-trust mechanic to cover supplier origins as well. The same `origin_trust` matrix is read, but applied symmetrically.

```
FUNCTION apply_supplier_origin_trust(team, segment_preferences, round_state):
    # For each segment's preference vector, adjust based on the team's supplier composition
    FOR EACH (segment, market) IN team.active_segments:
        preference = segment_preferences[segment]
        supplier_trust_adjustment = 0

        # Aggregate supplier origin countries weighted by allocation
        FOR EACH (supplier_id, category_allocation_pct) IN team.all_sourcing_decisions:
            supplier = scenario.suppliers[supplier_id]
            # Per-supplier origin-trust-to-buyer contribution
            supplier_trust_adjustment += supplier.origin_trust_to_buyers[market] * (category_allocation_pct / total_across_categories)

        preference.apply_trust_modifier(supplier_trust_adjustment)

    RETURN segment_preferences
```

**Feeds into:** Phase 1 step 11 (new NEW step) — adjusted segment preferences flow into step 12 (Bass adoption) and subsequent revenue steps.

**Interaction with existing buyer-side origin trust:** both mechanics apply. A team based in China (buyer-side) selling to the US with Taiwanese suppliers (supplier-side) accumulates both trust adjustments. They can compound positively or negatively.

### 6.7 FX hedge settlement

**Purpose:** Mark FX forward contracts to market at round end; book P&L on closed positions; roll forward unclosed positions.

```
FUNCTION settle_fx_hedges(team, round_state):
    hedge_pnl = 0
    FOR EACH position IN team.fx_hedge_positions:
        IF position.matures_this_round:
            # Settle at current spot vs. locked forward rate
            spot = round_state.fx_rates[position.currency_pair]
            pnl = (position.locked_rate - spot) * position.notional
            IF position.direction == short:
                pnl = -pnl
            hedge_pnl += pnl
            position.status = closed
        ELSE:
            # Mark to market for reporting; no cash flow
            position.mark_to_market(round_state.fx_rates)

    # Settlement of new hedge decisions made this round
    FOR EACH (currency_pair, hedge_ratio, tenor_days) IN team.fx_hedging_decisions:
        exposure = team.foreign_receivables[currency_pair]
        notional_to_hedge = exposure * (hedge_ratio / 100)
        forward_rate = compute_forward_rate(currency_pair, tenor_days, round_state)
        premium = notional_to_hedge * (scenario.trade_finance_instruments.fx_forward.cost_bps / 10000)
        hedge_pnl -= premium   # upfront premium is a cost

        team.fx_hedge_positions.append({
            "currency_pair": currency_pair,
            "notional": notional_to_hedge,
            "locked_rate": forward_rate,
            "maturity_round": round_state.round_number + ceil(tenor_days / round_days),
            "direction": short if team.home_currency_will_appreciate_expectation else long,
            "status": open
        })

    RETURN hedge_pnl
```

**Feeds into:** Phase 1 step 23. P&L flows into round financials; unrealized MTM is reported but not realized until settlement.

---

## 7. Event System Integration

### 7.1 SC event firing

SC events live in the same `events` section of the scenario YAML as existing events, distinguished by `category: supply_chain`. They integrate with the existing probabilistic trigger mechanism unchanged:

```
FOR EACH event_template IN scenario.events:
    IF seeded_random() < event_template.trigger_probability_per_round:
        IF event_template.condition_function IS NOT NULL:
            IF NOT evaluate_condition(event_template.condition_function, team_states):
                CONTINUE
        fire_event(event_template)
```

The `condition_function` dispatcher recognizes new SC-specific conditions: `team_has_xinjiang_tier2_exposure_above_threshold`, `team_uses_lc_with_discrepancies`, `team_over_indexed_on_sinosure_bri_markets`, etc. Each condition function is a pure function of team state and scenario config — no side effects.

### 7.2 Event effect application

When an event fires, its declared effects are applied to the relevant state objects:

```
FUNCTION apply_event_effects(event, round_state):
    # Supplier state effects
    FOR EACH supplier_id IN event.affected_suppliers:
        state = round_state.supplier_states[supplier_id]
        IF event.capacity_reduction_pct:
            state.capacity_multiplier *= (1 - event.capacity_reduction_pct / 100)
        IF event.quality_rating_degradation:
            state.quality_modifier *= (1 - event.quality_rating_degradation)
        IF event.recovery_rounds:
            state.recovery_rounds_remaining = event.recovery_rounds

    # Lane state effects
    FOR EACH lane_id IN event.affected_lanes:
        state = round_state.lane_states[lane_id]
        IF event.mode_rate_multiplier:
            state.active_disruption = {
                "mode_rate_multiplier": event.mode_rate_multiplier,
                "additional_lead_time_days": event.additional_lead_time_days,
                "rounds_remaining": event.duration_rounds
            }

    # Market-level effects (for policy events like BIS expansion, CBAM tightening)
    # ... etc per event schema
```

### 7.3 Multi-round event timers

Each round, after events fire, active multi-round states are decremented:

```
FUNCTION decrement_event_timers(round_state):
    FOR EACH supplier_id, state IN round_state.supplier_states:
        IF state.recovery_rounds_remaining > 0:
            state.recovery_rounds_remaining -= 1
            IF state.recovery_rounds_remaining == 0:
                state.reset_to_baseline()
            ELSE:
                # Partial recovery — linearly interpolate back toward baseline
                state.capacity_multiplier = linear_interp(state.capacity_multiplier, 1.0, 1 / (state.recovery_rounds_remaining + 1))

    FOR EACH lane_id, state IN round_state.lane_states:
        IF state.active_disruption IS NOT NULL AND state.active_disruption.rounds_remaining > 0:
            state.active_disruption.rounds_remaining -= 1
            IF state.active_disruption.rounds_remaining == 0:
                state.active_disruption = NULL
```

### 7.4 Recovery acceleration with alternatives

Per CC-1 §6.6's `recovery_rate_with_alternatives_multiplier`, teams with multi-sourcing recover faster:

```
IF team.has_active_alternative_for(affected_supplier):
    # Halve the effective recovery burden for this team's operations
    team_perceived_recovery_rounds = ceil(event.recovery_rounds * scenario.resilience_parameters.recovery_rate_with_alternatives_multiplier)
```

This is computed per-team, not per-supplier — different teams sourcing from the same affected supplier recover at different rates based on their own portfolio.

---

## 8. Instructor Override Hooks

The engine supports instructor-initiated interventions at three points:

**Event injection:** instructor panel can manually fire any event template against any team or all teams. Inserted into the event queue before Phase 1 step 3's automatic evaluation, flagged as instructor-injected in the audit log.

**Pre-advance state override:** instructor can modify team state (e.g., forgive an LC rejection, lift a UFLPA market freeze) between Phase 1 and Phase 2, with override logged and visible to students as "instructor adjustment" in the round report.

**Scenario parameter override per class:** instructor can adjust scenario-level parameters (e.g., raise CBAM tariff rate for a policy-simulation class, lower resilience thresholds for an introductory class). Overrides are class-scoped, not global.

Every instructor override is logged with timestamp, user, action, and audit trail.

Prompt tuning for autonomous actors with new SC awareness (governments, competitors, partners, analysts, investors) is a CC-39 concern. CC-3 only requires that Phase 2 prompts can reference team SC state and event history so downstream prompt work has the hooks it needs.

---

## 9. Determinism and Reproducibility

Every probabilistic operation in Phase 1 uses a seeded RNG where the seed is a deterministic function of (class_id, round_number, operation_id). This means:

- Re-running a round with the same decisions produces identical outcomes.
- Instructors can replay rounds for post-mortem analysis.
- Two students running the same simulation configuration get identical event sequences (important for fairness).

Phase 2 is intentionally non-deterministic (LLM output varies), but because Phase 2 outputs never feed back into Phase 1, this variance does not affect scoring.

The existing GlobalStrat seeding mechanism is verified in §2 Section C of the inventory report; if it does not already produce reproducible outcomes, that gap is flagged as a halt and resolved before CC-3 proceeds.

---

## 10. What This Spec Does NOT Cover

| Concern | Spec |
|---|---|
| Django model definitions (SupplierState, LaneState, HedgePosition, etc.) | **CC-4** |
| Serializers and API endpoints for decision submission and round outcomes | **CC-4** |
| Frontend components rendering decision pages and results | Later frontend CC |
| Specific LLM prompts for Phase 2 narratives | Later content CC |
| Seed data for Consumer Electronics scenario (actual supplier rosters, lane rates, event catalog) | Later build-pipeline CC |
| Autonomous actor prompt extensions for SC awareness | **CC-39** |
| Integration testing across full 10-round simulation | Later test CC |

---

## 11. Acceptance Criteria

CC-3 is complete when:

1. Claude Code has produced the engine inventory report at `specs/reports/CC-03-engine-inventory.md` covering Sections A (pipeline orchestration), B (cost function roster), C (event system), and D (model-to-table sanity).
2. No MISMATCH halts remain unresolved. Named cost functions exist with expected signatures; `advance_round` exists; event system supports seeded RNG; no ghost models among engine-referenced models.
3. `specs/CC-03-engine-logic.md` exists (this file).
4. Branch `cc-03-engine-logic` contains the engine inventory report commit and is merged to `main` after verification.
5. No code-level implementation of engine changes is required at this stage — pipeline specification and inventory only.

**Report back to the user with:** the engine inventory report contents, explicit confirmation that all four halt conditions cleared, `git log --oneline` for the branch, and explicit confirmation that no engine code, models, or migrations were modified during CC-3.

---

## 12. Open Questions for CC-6

Flagged here so they don't get lost; resolved in CC-6:

- **Phase ordering for supplier-origin trust (step 11).** The spec places it between marketing-mix matching (step 10) and Bass adoption (step 12). An alternative placement is earlier, folded into the segment preference initialization. Whether the current ordering is correct depends on how GlobalStrat's existing buyer-side origin trust is injected — confirmed against the inventory report, but the interaction order may benefit from pedagogical review.
- **Recovery interpolation shape.** §7.3 uses linear interpolation from disrupted state back to baseline. Alternative shapes (step function, exponential recovery) have different pedagogical signatures — linear is the most transparent but not necessarily the most realistic. CC-6 can revisit if empirical calibration suggests.
- **Resilience score weighting per scenario vs. global.** Weights are declared per scenario in CC-1 §6.6. Whether instructors should be able to tune weights per class is an open question aligned with the instructor override conversation.

---

## 13. Interaction with Prior CC Findings

- **Ghost models (CC-1 deviation D2, CC-2 Section B).** The §2 engine inventory Section D applies STANDING-DISCIPLINE §1.8 to engine-referenced models. If any engine code path references a ghost model, that's a halt. Given that `core.Decision` is itself a ghost (per CC-2 Section B), any engine code path calling `Decision.objects.*` would fail at runtime — Section A inventory specifically surfaces this.
- **pg_dump version alignment (CC-1 deviation D3).** Not directly relevant to CC-3 execution (no dumps anticipated), but listed for completeness — if CC-3's acceptance checks require any schema snapshot, STANDING-DISCIPLINE §1.9 applies.
