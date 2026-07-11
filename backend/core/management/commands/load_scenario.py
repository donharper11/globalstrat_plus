"""
Load a complete scenario from a YAML configuration file.

Usage:
    python manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml --flush
    python manage.py load_scenario --preset electronics --flush
    python manage.py load_scenario --file scenarios/fashion_2026.yaml --flush --markets 3
"""
import yaml
import os
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection

from core.models.scenario import (
    Scenario, ScenarioConfig,
    FeatureDefinition, PlatformGenerationDefinition,
    PlatformFeatureCeiling, MarketDefinition, MarketReadiness,
    SegmentDefinition, SegmentPreference,
    EntryModeDefinition, StrategyOptionDefinition, StrategyOptionEffect,
    EventTemplateDefinition, EventImpactDefinition, EventResponseDefinition,
    MarketConditionByRound,
    FirmStarterProfile, FirmStarterPlatformConfig, FirmStarterProduct,
    AICompetitorDefinition, AICompetitorFitByRound,
    FeatureLevelCost,
    AcquisitionTarget, AICompetitorBehavior,
)
from core.models.cc26_models import AIInvestorFund, AIInvestorPreference
from core.models.cc31_models import CulturalDistanceMatrix, OriginTrustModifier, GovernanceCommitmentType
from core.models.cc32_models import CommunicationAssignment
from core.models.cc32b_models import OrganizationalStructureType
from core.models.cc32c_models import TaxStructureType
from core.models.cc32d_models import AlliancePartnerProfile
from core.models.cc32f_models import GovernmentProfile
from core.models.sc_models import (
    Supplier, ShippingLane, TradeFinanceInstrument, ComplianceRegime,
    ResilienceParameters, FreightMarket,
)


# Abstract features used by non-customer segments (not in FeatureDefinition)
ABSTRACT_FEATURES = {
    'rd_intensity', 'revenue_growth', 'market_expansion', 'tech_leadership',
    'tech_independence', 'revenue_growth_rate', 'platform_generation',
    'revenue_scale', 'financial_leverage_inv', 'net_margin_score',
    'cash_runway_score', 'talent_rd_quality', 'talent_operations_quality',
    'esg_composite', 'sustainability_level', 'market_diversity',
}


def _dec(val):
    """Convert a value to Decimal, handling strings and numbers."""
    if val is None:
        return None
    return Decimal(str(val))


def _validate_supply_chain(data, market_codes):
    """
    CC-1 §8 supply-chain cross-reference validation. Only runs when the scenario
    declares a `suppliers` section, so non-SC scenarios are unaffected. Returns a
    list of structured error strings; a non-empty list halts the load.
    """
    errors = []
    suppliers = data.get('suppliers') or []
    if not suppliers:
        return errors

    supplier_ids = {s.get('id') for s in suppliers}
    lane_origins = {ln.get('origin_country') for ln in data.get('shipping_lanes', []) or []}
    lane_ids = {ln.get('id') for ln in data.get('shipping_lanes', []) or []}
    regime_ids = {r.get('id') for r in data.get('compliance_regimes', []) or []}

    # Trade finance instruments: list-with-id OR dict-with-'instruments' OR mapping.
    tf = data.get('trade_finance_instruments')
    if isinstance(tf, list):
        tf_ids = {i.get('id') for i in tf}
    elif isinstance(tf, dict):
        tf_ids = {i.get('id') for i in tf.get('instruments', [])} if 'instruments' in tf else set(tf.keys())
    else:
        tf_ids = set()

    # Specializations → suppliers, for rule 7.
    spec_counts = {}
    for s in suppliers:
        for sp in (s.get('specialization') or []):
            spec_counts[sp] = spec_counts.get(sp, 0) + 1

    # Rule 1: every supplier country is a declared lane origin.
    for s in suppliers:
        if s.get('country') not in lane_origins:
            errors.append(f"Supplier '{s.get('id')}' country '{s.get('country')}' is not a declared shipping_lane origin.")
    # Rule 2: origin_trust_to_buyers markets exist.
    for s in suppliers:
        for mk in (s.get('origin_trust_to_buyers') or {}):
            if mk not in market_codes:
                errors.append(f"Supplier '{s.get('id')}' origin_trust_to_buyers references unknown market '{mk}'.")
    # Rule 3: markets.*.compliance_regimes exist.
    for m in data.get('markets', []):
        for rg in (m.get('compliance_regimes') or []):
            if rg not in regime_ids:
                errors.append(f"Market '{m.get('code')}' references unknown compliance_regime '{rg}'.")
    # Rule 4: plants.upstream_suppliers_required specializations are resolvable.
    for p in data.get('plants', []) or []:
        for sp in (p.get('upstream_suppliers_required') or []):
            if sp not in spec_counts:
                errors.append(f"Plant '{p.get('id')}' upstream_suppliers_required '{sp}' has no supplier with that specialization.")
    # Rule 5: accepts_trade_finance instruments exist.
    for s in suppliers:
        for inst in (s.get('accepts_trade_finance') or []):
            if tf_ids and inst not in tf_ids:
                errors.append(f"Supplier '{s.get('id')}' accepts_trade_finance references unknown instrument '{inst}'.")
    # Rule 6: lanes referenced in events exist.
    for e in data.get('events', []) or []:
        for ln in (e.get('affected_lanes') or []):
            if ln not in lane_ids:
                errors.append(f"Event '{e.get('name', e.get('id'))}' affected_lanes references unknown lane '{ln}'.")
    # Rule 7: every critical input category (specialization) has >= 2 suppliers.
    for sp, n in spec_counts.items():
        if n < 2:
            errors.append(f"Critical input category '{sp}' has only {n} supplier(s); at least 2 required (multi-sourcing).")
    # Rule 8: resilience_score_weights sum to 1.0 (±0.01).
    rp = data.get('resilience_parameters') or {}
    weights = rp.get('resilience_score_weights') or {}
    if weights:
        total = sum(float(v) for v in weights.values())
        if abs(total - 1.0) > 0.01:
            errors.append(f"resilience_score_weights sum to {total:.4f}; must be 1.0 (±0.01).")
    # Rule 9: multi_source_substitutability supplier_ids resolve.
    for s in suppliers:
        for sub in (s.get('multi_source_substitutability') or []):
            sid = sub.get('supplier_id')
            if sid not in supplier_ids:
                errors.append(f"Supplier '{s.get('id')}' multi_source_substitutability references unknown supplier '{sid}'.")
    return errors


def validate_scenario_yaml(data):
    """Check required sections and cross-references."""
    errors = []
    for section in ['scenario', 'markets', 'features']:
        if section not in data:
            errors.append(f"Missing required section: {section}")
    if errors:
        return errors

    # Cross-reference: cultural distance references valid market codes
    market_codes = {m['code'] for m in data.get('markets', [])}
    for cd in data.get('cultural_distance', []):
        if cd[0] not in market_codes:
            errors.append(f"Cultural distance references unknown market: {cd[0]}")
        if cd[1] not in market_codes:
            errors.append(f"Cultural distance references unknown market: {cd[1]}")

    # Cross-reference: origin trust references valid market codes
    for ot in data.get('origin_trust', []):
        if ot[0] not in market_codes:
            errors.append(f"Origin trust references unknown market: {ot[0]}")
        if ot[1] not in market_codes:
            errors.append(f"Origin trust references unknown market: {ot[1]}")

    # CC-1 §8: supply-chain cross-reference validation (runs only when SC present)
    errors.extend(_validate_supply_chain(data, market_codes))

    return errors


class Command(BaseCommand):
    help = 'Load a scenario from a YAML configuration file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, default=None,
            help='Path to scenario YAML file (e.g., scenarios/consumer_electronics_2026.yaml)'
        )
        parser.add_argument(
            '--preset', type=str, default=None,
            choices=['electronics'],
            help='Shorthand for built-in scenarios'
        )
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete existing scenario data before loading'
        )
        parser.add_argument(
            '--markets', type=int, default=None,
            help='Limit to first N markets. Default: all markets in YAML.'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        scenarios_dir = base_dir / 'scenarios'

        # Resolve file path from --file or --preset
        file_path = options.get('file')
        preset = options.get('preset')

        if preset:
            preset_map = {
                'electronics': 'consumer_electronics_2026.yaml',
            }
            file_path = str(scenarios_dir / preset_map[preset])
        elif file_path:
            if not os.path.isabs(file_path):
                # Try relative to scenarios dir first, then project root
                candidate = scenarios_dir / file_path
                if candidate.exists():
                    file_path = str(candidate)
                else:
                    file_path = str(base_dir / file_path)
        else:
            raise CommandError('Provide --file or --preset')

        if not os.path.exists(file_path):
            raise CommandError(f"Scenario file not found: {file_path}")

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        # Validate
        errors = validate_scenario_yaml(data)
        if errors:
            for e in errors:
                self.stderr.write(self.style.ERROR(e))
            raise CommandError(f"YAML validation failed with {len(errors)} errors")

        scenario_name = data['scenario']['name']

        if options['flush']:
            self._flush(scenario_name)

        if Scenario.objects.filter(name=scenario_name).exists():
            raise CommandError(f'Scenario "{scenario_name}" already exists. Use --flush to replace.')

        market_limit = options.get('markets')
        self._load(data, market_limit)

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def _flush(self, scenario_name):
        for old in Scenario.objects.filter(name=scenario_name):
            sid = old.pk
            game_tables = [
                # SC engine state and decisions (must precede round/team)
                'sc_resilience_score_history', 'sc_hedge_position',
                'sc_event_instance', 'sc_lane_state', 'sc_supplier_state',
                'sc_contingency_plan', 'sc_inventory_decision',
                'sc_fx_hedge_decision', 'sc_sinosure_enrollment',
                'sc_trade_finance_decision', 'sc_customs_classification_decision',
                'sc_incoterms_decision', 'sc_logistics_decision',
                'sc_sourcing_allocation', 'sc_sourcing_decision',
                # Original game tables
                'team_product_market', 'decision_marketing', 'decision_rd_investment',
                'decision_platform_development', 'decision_product_create', 'decision_product_retire',
                'decision_market_entry', 'decision_financing', 'decision_talent',
                'decision_budget_allocation', 'decision_esg', 'decision_partnership',
                'decision_plant', 'decision_acquisition', 'decision_event_response',
                'decision_research_allocation', 'decision_change_log', 'decision_submission',
                'round_result_adoption', 'round_result_product_market',
                'round_result_financials', 'round_result_market_revenue',
                'round_result_performance_index', 'round_result_coherence',
                'leaderboard_entry', 'instructor_alert',
                'forecast_scenario', 'research_query_log',
                'market_intelligence_brief', 'team_framework_analysis',
                'active_modifier', 'event_instance', 'pending_feature_gain',
                'team_talent_state', 'team_platform_feature_level',
                'team_strategy_feature_level', 'team_market_modifier',
                'team_partnership', 'team_plant', 'team_acquisition',
                'team_product', 'team_platform', 'team_market_presence',
                'team_alliance_state',
                'government_action', 'government_satisfaction',
                'team_market_compliance', 'compliance_investment', 'talent_allocation',
                'team_member', 'team',
                'round', 'simulation_instance', 'game',
            ]
            with connection.cursor() as cur:
                for tbl in game_tables:
                    try:
                        cur.execute(f'TRUNCATE TABLE {tbl} CASCADE')
                    except Exception:
                        pass
            # Delete SC scenario-scoped models
            FreightMarket.objects.filter(scenario=old).delete()
            ResilienceParameters.objects.filter(scenario=old).delete()
            ComplianceRegime.objects.filter(scenario=old).delete()
            TradeFinanceInstrument.objects.filter(scenario=old).delete()
            ShippingLane.objects.filter(scenario=old).delete()
            Supplier.objects.filter(scenario=old).delete()

            # Delete scenario-scoped models in reverse dependency order
            GovernmentProfile.objects.filter(scenario=old).delete()
            AlliancePartnerProfile.objects.filter(scenario=old).delete()
            TaxStructureType.objects.filter(scenario=old).delete()
            CulturalDistanceMatrix.objects.filter(scenario=old).delete()
            OriginTrustModifier.objects.filter(scenario=old).delete()
            AIInvestorPreference.objects.filter(fund__scenario=old).delete()
            OrganizationalStructureType.objects.filter(scenario=old).delete()
            CommunicationAssignment.objects.filter(scenario=old).delete()
            GovernanceCommitmentType.objects.filter(scenario=old).delete()
            AIInvestorFund.objects.filter(scenario=old).delete()
            AICompetitorFitByRound.objects.filter(ai_competitor__scenario=old).delete()
            AICompetitorBehavior.objects.filter(ai_competitor__scenario=old).delete()
            AcquisitionTarget.objects.filter(scenario=old).delete()
            FirmStarterProduct.objects.filter(firm_starter_profile__scenario=old).delete()
            FirmStarterPlatformConfig.objects.filter(firm_starter_profile__scenario=old).delete()
            EventResponseDefinition.objects.filter(event_template__scenario=old).delete()
            EventImpactDefinition.objects.filter(event_template__scenario=old).delete()
            SegmentPreference.objects.filter(segment__scenario=old).delete()
            MarketConditionByRound.objects.filter(market__scenario=old).delete()
            FirmStarterProfile.objects.filter(scenario=old).delete()
            EventTemplateDefinition.objects.filter(scenario=old).delete()
            SegmentDefinition.objects.filter(scenario=old).delete()
            StrategyOptionEffect.objects.filter(strategy_option__scenario=old).delete()
            MarketReadiness.objects.filter(market__scenario=old).delete()
            FeatureLevelCost.objects.filter(feature__scenario=old).delete()
            PlatformFeatureCeiling.objects.filter(platform_generation__scenario=old).delete()
            AICompetitorDefinition.objects.filter(scenario=old).delete()
            StrategyOptionDefinition.objects.filter(scenario=old).delete()
            EntryModeDefinition.objects.filter(scenario=old).delete()
            MarketDefinition.objects.filter(scenario=old).delete()
            PlatformGenerationDefinition.objects.filter(scenario=old).delete()
            FeatureDefinition.objects.filter(scenario=old).delete()
            ScenarioConfig.objects.filter(scenario=old).delete()
            old.delete()
            self.stdout.write(f"Flushed scenario id={sid}")

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def _load(self, data, market_limit=None):
        counts = {}
        sd = data['scenario']

        # 1. Scenario
        scenario = Scenario.objects.create(
            name=sd['name'],
            industry_label=sd.get('industry_label', ''),
            description=sd.get('description', ''),
            num_rounds=sd.get('num_rounds', 10),
            round_duration_label=sd.get('round_duration_label', 'Quarter'),
            starting_cash=_dec(sd.get('starting_cash', 50000000)),
            currency_code=sd.get('currency_code', 'USD'),
            max_platforms_per_team=sd.get('max_platforms_per_team', 3),
            max_products_per_platform=sd.get('max_products_per_platform', 3),
            max_products_total=sd.get('max_products_total', 6),
            performance_index_base=_dec(sd.get('performance_index_base', 55)),
            is_active=sd.get('is_active', True),
        )
        counts['Scenario'] = 1
        self.stdout.write(f"Created scenario: {scenario.name} (id={scenario.pk})")

        # 1b. Company names (stored as ScenarioConfig JSON)
        company_names = sd.get('company_names', [])
        if company_names:
            import json
            ScenarioConfig.objects.create(
                scenario=scenario, config_key='company_names',
                config_value=json.dumps(company_names),
                description='Auto-assigned company names for new teams',
            )
            self.stdout.write(f"  Loaded {len(company_names)} company names")

        # 2. Config
        config_data = data.get('config', {})
        for key, val_desc in config_data.items():
            if isinstance(val_desc, list) and len(val_desc) >= 2:
                ScenarioConfig.objects.create(
                    scenario=scenario, config_key=key,
                    config_value=str(val_desc[0]), description=str(val_desc[1]),
                )
            else:
                ScenarioConfig.objects.create(
                    scenario=scenario, config_key=key,
                    config_value=str(val_desc), description='',
                )
        counts['ScenarioConfig'] = len(config_data)

        # 3. Features
        feature_objs = {}
        features = data.get('features', {})
        all_features = (
            features.get('platform', []) +
            features.get('marketing', []) +
            features.get('strategy', []) +
            features.get('derived', [])
        )
        for fd in all_features:
            obj = FeatureDefinition.objects.create(
                scenario=scenario,
                code=fd['code'], layer=fd['layer'], name=fd['name'],
                name_zh=fd.get('name_zh', ''),
                description=fd.get('description', ''),
                description_zh=fd.get('description_zh', ''),
                category=fd.get('category', ''),
                min_value=fd.get('min_value', 0),
                max_value=fd.get('max_value', 20),
                default_value=fd.get('default_value', 1),
                cost_curve_type=fd.get('cost_curve_type', 'linear'),
                cost_base=fd.get('cost_base', 0),
                time_lag_rounds=fd.get('time_lag_rounds', 0),
                is_licensable=fd.get('is_licensable', False),
                license_cost_multiplier=_dec(fd.get('license_cost_multiplier', '1.00')),
                display_order=fd.get('display_order', 0),
                is_derived=fd.get('is_derived', False),
                is_market_specific=fd.get('is_market_specific', False),
            )
            feature_objs[fd['code']] = obj
        counts['FeatureDefinition'] = len(all_features)

        # 4. Platform Generations + Ceilings + Level Costs
        gen_objs = {}
        ceiling_count = 0
        level_cost_count = 0
        for gd in data.get('platform_generations', []):
            ceilings = gd.get('ceilings', {})
            gen_obj = PlatformGenerationDefinition.objects.create(
                scenario=scenario,
                name=gd['name'],
                name_zh=gd.get('name_zh', ''),
                description=gd.get('description', ''),
                description_zh=gd.get('description_zh', ''),
                generation_order=gd['generation_order'],
                unlock_round=gd.get('unlock_round', 0),
                development_cost=gd.get('development_cost', 0),
                development_rounds=gd.get('development_rounds', 0),
                license_cost=gd.get('license_cost', 0),
                annual_maintenance_cost=gd.get('annual_maintenance_cost', 0),
                is_starting_platform=gd.get('is_starting_platform', False),
            )
            gen_objs[gd['generation_order']] = gen_obj

            for feat_code, vals in ceilings.items():
                ceil_val, start_val = vals[0], vals[1]
                PlatformFeatureCeiling.objects.create(
                    platform_generation=gen_obj,
                    feature=feature_objs[feat_code],
                    ceiling_value=ceil_val,
                    starting_value=start_val,
                )
                ceiling_count += 1

                # Level costs
                feat_obj = feature_objs[feat_code]
                cost_base = Decimal(str(feat_obj.cost_base))
                cumulative = Decimal('0')
                for level in range(1, ceil_val + 1):
                    increment = cost_base * Decimal(str(1 + (level - 1) * 0.5))
                    cumulative += increment
                    FeatureLevelCost.objects.create(
                        feature=feat_obj, platform_generation=gen_obj,
                        level=level, incremental_cost=increment,
                        cumulative_cost=cumulative,
                    )
                    level_cost_count += 1

        counts['PlatformGenerationDefinition'] = len(gen_objs)
        counts['PlatformFeatureCeiling'] = ceiling_count
        counts['FeatureLevelCost'] = level_cost_count

        # 5. Markets
        markets_data = data.get('markets', [])
        if market_limit:
            markets_data = markets_data[:market_limit]
        market_objs = {}
        for md in markets_data:
            obj = MarketDefinition.objects.create(
                scenario=scenario,
                name=md['name'], code=md['code'],
                name_zh=md.get('name_zh', ''),
                display_name_zh=md.get('display_name_zh', ''),
                description=md.get('description', ''),
                market_description_zh=md.get('market_description_zh', ''),
                currency_code=md.get('currency_code', 'USD'),
                exchange_rate_base=_dec(md.get('exchange_rate_base', 1)),
                exchange_rate_volatility=_dec(md.get('exchange_rate_volatility', 0)),
                base_growth_rate=_dec(md.get('base_growth_rate', 0)),
                entry_cost_base=md.get('entry_cost_base', 0),
                tariff_rate=_dec(md.get('tariff_rate', 0)),
                tax_rate=_dec(md.get('tax_rate', 0)),
                regulatory_difficulty=md.get('regulatory_difficulty', 5),
                infrastructure_quality=md.get('infrastructure_quality', 5),
                base_manufacturing_cost=_dec(md.get('base_manufacturing_cost', 1)),
                allows_manufacturing=md.get('allows_manufacturing', True),
                plant_build_cost=md.get('plant_build_cost'),
                plant_build_rounds=md.get('plant_build_rounds', 0),
                plant_capacity_units=md.get('plant_capacity_units'),
                contract_mfg_available=md.get('contract_mfg_available', False),
                contract_mfg_cost_multiplier=_dec(md.get('contract_mfg_cost_multiplier', 1)),
                contract_mfg_capacity_cap=md.get('contract_mfg_capacity_cap'),
                display_order=md.get('display_order', 0),
            )
            market_objs[md['code']] = obj
        counts['MarketDefinition'] = len(market_objs)
        active_market_codes = set(market_objs.keys())
        self.stdout.write(f"  Markets loaded: {sorted(active_market_codes)} ({len(market_objs)}-market mode)")

        # 6. Market Readiness
        readiness_count = 0
        for rd in data.get('readiness_data', []):
            mkt_code = rd['market']
            if mkt_code not in market_objs:
                continue
            gen_obj = gen_objs.get(rd['generation'])
            if not gen_obj:
                continue
            for rnd, pct in rd['rounds'].items():
                MarketReadiness.objects.create(
                    market=market_objs[mkt_code],
                    platform_generation=gen_obj,
                    round_number=int(rnd),
                    readiness_pct=_dec(pct),
                )
                readiness_count += 1
        counts['MarketReadiness'] = readiness_count

        # 7. Entry Modes
        for emd in data.get('entry_modes', []):
            EntryModeDefinition.objects.create(
                scenario=scenario,
                code=emd['code'], name=emd['name'],
                name_zh=emd.get('name_zh', ''),
                description=emd.get('description', ''),
                description_zh=emd.get('description_zh', ''),
                capital_requirement=emd.get('capital_requirement', 0),
                setup_rounds=emd.get('setup_rounds', 0),
                control_level=emd.get('control_level', 5),
                risk_level=emd.get('risk_level', 5),
                local_presence_score=emd.get('local_presence_score', 5),
                logistics_cost_multiplier=_dec(emd.get('logistics_cost_multiplier', 1)),
                tariff_applies=emd.get('tariff_applies', True),
            )
        counts['EntryModeDefinition'] = len(data.get('entry_modes', []))

        # 8. Strategy Options + Effects
        effect_count = 0
        for sod in data.get('strategy_options', []):
            effects = sod.get('effects', [])
            obj = StrategyOptionDefinition.objects.create(
                scenario=scenario,
                category=sod.get('category', ''),
                code=sod['code'], name=sod['name'],
                name_zh=sod.get('name_zh', ''),
                description=sod.get('description', ''),
                description_zh=sod.get('description_zh', ''),
                capital_cost_base=sod.get('capital_cost_base', 0),
                recurring_cost_per_round=sod.get('recurring_cost_per_round', 0),
                time_lag_rounds=sod.get('time_lag_rounds', 0),
                is_reversible=sod.get('is_reversible', True),
                reversal_cost_multiplier=_dec(sod.get('reversal_cost_multiplier', 0)),
            )
            for eff in effects:
                feat_code, eff_type, eff_val, mkt_specific = eff[0], eff[1], eff[2], eff[3]
                StrategyOptionEffect.objects.create(
                    strategy_option=obj,
                    feature=feature_objs[feat_code],
                    effect_type=eff_type,
                    effect_value=_dec(eff_val),
                    market_specific=mkt_specific,
                )
                effect_count += 1
        counts['StrategyOptionDefinition'] = len(data.get('strategy_options', []))
        counts['StrategyOptionEffect'] = effect_count

        # 9. Segments (customer + non-customer)
        segment_objs = {}
        market_codes = sorted(active_market_codes)

        for tmpl in data.get('customer_segments', []):
            for mkt_code in market_codes:
                pops = tmpl.get('populations', {})
                grs = tmpl.get('growth_rates', {})
                if mkt_code not in pops:
                    continue
                seg = SegmentDefinition.objects.create(
                    scenario=scenario,
                    market=market_objs[mkt_code],
                    name=tmpl['name'],
                    name_zh=tmpl.get('name_zh', ''),
                    segment_type=tmpl['segment_type'],
                    description=tmpl.get('description', ''),
                    description_zh=tmpl.get('description_zh', ''),
                    population_size=pops[mkt_code],
                    population_growth_rate=_dec(grs.get(mkt_code, 0)),
                    bass_p=_dec(tmpl.get('bass_p', 0)),
                    bass_q=_dec(tmpl.get('bass_q', 0)),
                    performance_index_weight=_dec(tmpl.get('performance_index_weight', 0)),
                    revenue_per_unit=_dec(tmpl.get('revenue_per_unit')),
                    min_generation_required=tmpl.get('min_generation_required'),
                )
                segment_objs[(tmpl['name'], mkt_code)] = seg

        for ncs in data.get('non_customer_segments', []):
            mkt = ncs.get('market')
            if mkt == '__per_market__':
                for mkt_code in market_codes:
                    seg = SegmentDefinition.objects.create(
                        scenario=scenario,
                        market=market_objs[mkt_code],
                        name=ncs['name'],
                        name_zh=ncs.get('name_zh', ''),
                        segment_type=ncs['segment_type'],
                        description=ncs.get('description', ''),
                        description_zh=ncs.get('description_zh', ''),
                        population_size=ncs.get('population_size', 1),
                        population_growth_rate=Decimal('0'),
                        bass_p=_dec(ncs.get('bass_p', 0)),
                        bass_q=_dec(ncs.get('bass_q', 0)),
                        performance_index_weight=_dec(ncs.get('performance_index_weight', 0)),
                        revenue_per_unit=_dec(ncs.get('revenue_per_unit')),
                    )
                    segment_objs[(ncs['name'], mkt_code)] = seg
            elif mkt is not None:
                if mkt not in market_objs:
                    continue
                seg = SegmentDefinition.objects.create(
                    scenario=scenario,
                    market=market_objs[mkt],
                    name=ncs['name'],
                    name_zh=ncs.get('name_zh', ''),
                    segment_type=ncs['segment_type'],
                    description=ncs.get('description', ''),
                    description_zh=ncs.get('description_zh', ''),
                    population_size=ncs.get('population_size', 1),
                    population_growth_rate=Decimal('0'),
                    bass_p=_dec(ncs.get('bass_p', 0)),
                    bass_q=_dec(ncs.get('bass_q', 0)),
                    performance_index_weight=_dec(ncs.get('performance_index_weight', 0)),
                    revenue_per_unit=_dec(ncs.get('revenue_per_unit')),
                )
                segment_objs[(ncs['name'], mkt)] = seg
            else:
                seg = SegmentDefinition.objects.create(
                    scenario=scenario,
                    market=None,
                    name=ncs['name'],
                    name_zh=ncs.get('name_zh', ''),
                    segment_type=ncs['segment_type'],
                    description=ncs.get('description', ''),
                    description_zh=ncs.get('description_zh', ''),
                    population_size=ncs.get('population_size', 1),
                    population_growth_rate=Decimal('0'),
                    bass_p=_dec(ncs.get('bass_p', 0)),
                    bass_q=_dec(ncs.get('bass_q', 0)),
                    performance_index_weight=_dec(ncs.get('performance_index_weight', 0)),
                    revenue_per_unit=_dec(ncs.get('revenue_per_unit')),
                )
                segment_objs[(ncs['name'], None)] = seg

        counts['SegmentDefinition'] = len(segment_objs)

        # Normalize performance_index_weights
        all_segments = list(segment_objs.values())
        raw_total = sum(float(s.performance_index_weight) for s in all_segments)
        if abs(raw_total - 1.0) > 0.001:
            self.stdout.write(f"  Normalizing performance_index_weight: raw total={raw_total:.4f}")
            for seg in all_segments:
                seg.performance_index_weight = Decimal(str(
                    float(seg.performance_index_weight) / raw_total
                ))
                seg.save(update_fields=['performance_index_weight'])

        # 10. Segment Preferences
        pref_count = 0
        pref_data = data.get('segment_preferences', {})
        for seg_name, markets_prefs in pref_data.items():
            for mkt_code, pref_list in markets_prefs.items():
                # mkt_code may be "None" string for global segments
                key_mkt = None if mkt_code == 'None' else mkt_code
                if (seg_name, key_mkt) not in segment_objs:
                    continue
                seg_obj = segment_objs[(seg_name, key_mkt)]
                for pref in pref_list:
                    feat_code = pref[0]
                    ideal = pref[1]
                    weight = pref[2]
                    tolerance = pref[3]
                    if feat_code not in feature_objs:
                        continue
                    SegmentPreference.objects.create(
                        segment=seg_obj,
                        feature=feature_objs[feat_code],
                        ideal_value=_dec(round(ideal, 2)),
                        weight=_dec(round(weight, 4)),
                        tolerance=_dec(round(tolerance, 2)),
                    )
                    pref_count += 1
        counts['SegmentPreference'] = pref_count

        # 11. Events + Impacts
        impact_count = 0
        evt_loaded = 0
        for evt in data.get('events', []):
            target_mkt_code = evt.get('target_market_code')
            if target_mkt_code and target_mkt_code not in market_objs:
                continue

            # Filter affected_markets
            orig_affected = evt.get('affected_markets')
            filtered_affected = None
            if orig_affected:
                filtered_affected = [c for c in orig_affected if c in market_objs]
                if not filtered_affected:
                    continue

            evt_kwargs = {
                'scenario': scenario,
                'name': evt['name'],
                'name_zh': evt.get('name_zh', ''),
                'description_template': evt.get('description_template', ''),
                'description_template_zh': evt.get('description_template_zh', ''),
                'category': evt.get('category', ''),
                'severity': evt.get('severity', 'medium'),
                'probability_per_round': _dec(evt.get('probability_per_round', 0)),
                'earliest_round': evt.get('earliest_round', 1),
                'max_occurrences': evt.get('max_occurrences', 1),
                'affects_all_markets': evt.get('affects_all_markets', False),
                'target_market': market_objs.get(target_mkt_code) if target_mkt_code else None,
                'response_required': evt.get('response_required', False),
                'rag_source_tags': evt.get('rag_source_tags', ''),
            }
            # Optional CC-31E fields
            if 'target_type' in evt:
                evt_kwargs['target_type'] = evt['target_type']
            if 'trigger_condition' in evt:
                evt_kwargs['trigger_condition'] = evt['trigger_condition']
            if filtered_affected is not None:
                evt_kwargs['affected_markets'] = filtered_affected

            evt_obj = EventTemplateDefinition.objects.create(**evt_kwargs)
            evt_loaded += 1

            for impact_tuple in evt.get('impacts', []):
                impact_type = impact_tuple[0]
                impact_mkt_code = impact_tuple[1]
                impact_seg_name = impact_tuple[2]
                impact_feat_code = impact_tuple[3]

                if impact_type in ('cost_change', 'market_condition', 'exchange_rate'):
                    target_field = impact_tuple[4]
                    impact_value = impact_tuple[5]
                    duration = impact_tuple[6]
                else:
                    target_field = None
                    impact_value = impact_tuple[4]
                    duration = impact_tuple[5]

                target_seg = None
                if impact_seg_name:
                    if impact_mkt_code:
                        target_seg = segment_objs.get((impact_seg_name, impact_mkt_code))
                    else:
                        for mc in [None, 'NA', 'APAC', 'EU', 'AFR', 'LATAM']:
                            if (impact_seg_name, mc) in segment_objs:
                                target_seg = segment_objs[(impact_seg_name, mc)]
                                break

                EventImpactDefinition.objects.create(
                    event_template=evt_obj,
                    impact_type=impact_type,
                    target_market=market_objs.get(impact_mkt_code) if impact_mkt_code else None,
                    target_segment=target_seg,
                    target_feature=feature_objs.get(impact_feat_code) if impact_feat_code else None,
                    target_field=target_field,
                    impact_value=_dec(impact_value),
                    duration_rounds=duration,
                )
                impact_count += 1

        counts['EventTemplateDefinition'] = evt_loaded
        counts['EventImpactDefinition'] = impact_count

        # 12. AI Competitors + Fit Scores
        ai_objs = []
        for acd in data.get('ai_competitors', []):
            obj = AICompetitorDefinition.objects.create(
                scenario=scenario,
                name=acd['name'],
                name_zh=acd.get('name_zh', ''),
                description=acd.get('description', ''),
                description_zh=acd.get('description_zh', ''),
            )
            ai_objs.append(obj)
        counts['AICompetitorDefinition'] = len(ai_objs)

        # Generate fit scores from affinity data
        fit_data = data.get('ai_competitor_fit_data', {})
        market_affinity = fit_data.get('market_affinity', {})
        segment_affinity = fit_data.get('segment_affinity', {})
        growth_per_round = fit_data.get('growth_per_round', 0.008)
        fit_min = fit_data.get('fit_min', 0.15)
        fit_max = fit_data.get('fit_max', 0.85)

        fit_count = 0
        customer_seg_names = [t['name'] for t in data.get('customer_segments', [])]
        for ai_obj in ai_objs:
            ai_name = ai_obj.name
            ai_mkt_affinity = market_affinity.get(ai_name, {})
            ai_seg_affinity = segment_affinity.get(ai_name, {})
            for mkt_code in market_codes:
                if mkt_code not in market_objs:
                    continue
                for seg_name in customer_seg_names:
                    if (seg_name, mkt_code) not in segment_objs:
                        continue
                    seg_obj = segment_objs[(seg_name, mkt_code)]
                    base_fit = ai_mkt_affinity.get(mkt_code, 0.15)
                    seg_offset = ai_seg_affinity.get(seg_name, 0.0)
                    for rnd in range(1, scenario.num_rounds + 1):
                        growth = growth_per_round * (rnd - 1)
                        fit = min(base_fit + seg_offset + growth, fit_max)
                        fit = max(fit, fit_min)
                        AICompetitorFitByRound.objects.create(
                            ai_competitor=ai_obj,
                            segment=seg_obj,
                            market=market_objs[mkt_code],
                            round_number=rnd,
                            fit_score=_dec(round(fit, 4)),
                        )
                        fit_count += 1
        counts['AICompetitorFitByRound'] = fit_count

        # 13. Acquisition Targets
        at_loaded = 0
        for at_data in data.get('acquisition_targets', []):
            mkt_code = at_data['market']
            if mkt_code not in market_objs:
                continue
            AcquisitionTarget.objects.create(
                scenario=scenario,
                market=market_objs[mkt_code],
                target_name=at_data['target_name'],
                target_name_zh=at_data.get('target_name_zh', ''),
                description=at_data.get('description', ''),
                description_zh=at_data.get('description_zh', ''),
                base_acquisition_cost=_dec(at_data.get('base_acquisition_cost', 0)),
                market_share_gained=_dec(at_data.get('market_share_gained', 0)),
                includes_plant=at_data.get('includes_plant', False),
                plant_capacity=at_data.get('plant_capacity', 0),
                includes_distribution=at_data.get('includes_distribution', False),
                distribution_reach_bonus=_dec(at_data.get('distribution_reach_bonus', 0)),
                talent_bonus=at_data.get('talent_bonus', {}),
                min_round_available=at_data.get('min_round_available', 1),
                requires_market_presence=at_data.get('requires_market_presence', True),
                integration_rounds=at_data.get('integration_rounds', 2),
                integration_cost_per_round=_dec(at_data.get('integration_cost_per_round', 0)),
            )
            at_loaded += 1
        counts['AcquisitionTarget'] = at_loaded

        # 14. AI Competitor Behaviors
        ai_obj_map = {obj.name: obj for obj in ai_objs}
        for ab_data in data.get('ai_behaviors', []):
            ai_name = ab_data['ai_competitor']
            AICompetitorBehavior.objects.create(
                ai_competitor=ai_obj_map[ai_name],
                strategy_type=ab_data.get('strategy_type', ''),
                price_sensitivity=_dec(ab_data.get('price_sensitivity', 0)),
                innovation_rate=_dec(ab_data.get('innovation_rate', 0)),
                market_entry_threshold=_dec(ab_data.get('market_entry_threshold', 0)),
                primary_segments=ab_data.get('primary_segments', []),
            )
        counts['AICompetitorBehavior'] = len(data.get('ai_behaviors', []))

        # 15. Starter Profiles (supports dual-platform format)
        gen1_obj = gen_objs.get(1)
        for sp in data.get('starter_profiles', []):
            profile = FirmStarterProfile.objects.create(
                scenario=scenario,
                profile_name=sp['profile_name'],
                profile_name_zh=sp.get('profile_name_zh', ''),
                description=sp.get('description', ''),
                description_zh=sp.get('description_zh', ''),
                home_market=market_objs[sp['home_market']],
                starting_cash=_dec(sp.get('starting_cash', 50000000)),
                starting_debt=_dec(sp.get('starting_debt', 0)),
                starting_revenue=_dec(sp.get('starting_revenue', 0)),
            )
            # Support new 'platforms' dict or legacy flat 'features' dict
            platforms_dict = sp.get('platforms')
            if platforms_dict is None:
                # Legacy format: wrap single features dict as alpha
                platforms_dict = {'alpha': sp.get('features', {})}
            for plat_label, feat_dict in platforms_dict.items():
                for feat_code, level in feat_dict.items():
                    FirmStarterPlatformConfig.objects.create(
                        firm_starter_profile=profile,
                        platform_generation=gen1_obj,
                        platform_label=plat_label,
                        feature=feature_objs[feat_code],
                        starting_level=_dec(level),
                    )
            for prod in sp.get('products', []):
                if len(prod) >= 7:
                    prod_name, positioning, price, mkt_code, volume, share, plat_label = prod
                else:
                    prod_name, positioning, price, mkt_code, volume, share = prod
                    plat_label = 'alpha'
                FirmStarterProduct.objects.create(
                    firm_starter_profile=profile,
                    product_name=prod_name,
                    positioning_label=positioning,
                    base_price=_dec(price),
                    market=market_objs[mkt_code],
                    unit_volume=volume,
                    market_share_pct=_dec(share),
                    platform_label=plat_label,
                )
        counts['FirmStarterProfile'] = len(data.get('starter_profiles', []))

        # 16. Market Conditions
        mc_count = 0
        for mkt_code, conditions in data.get('market_conditions', {}).items():
            if mkt_code not in market_objs:
                continue
            for cond in conditions:
                rnd, growth_mod, exch_mod, tariff_mod, demand_mult, narrative = cond
                MarketConditionByRound.objects.create(
                    market=market_objs[mkt_code],
                    round_number=rnd,
                    growth_rate_modifier=_dec(growth_mod),
                    exchange_rate_modifier=_dec(exch_mod),
                    tariff_rate_modifier=_dec(tariff_mod),
                    demand_multiplier=_dec(demand_mult),
                    market_outlook_narrative=narrative,
                )
                mc_count += 1
        counts['MarketConditionByRound'] = mc_count

        # 17. AI Investor Funds
        ai_fund_pref_count = 0
        for fund_data in data.get('ai_investor_funds', []):
            prefs = fund_data.get('preferences', [])
            fund = AIInvestorFund.objects.create(
                scenario=scenario,
                name=fund_data['name'],
                name_zh=fund_data.get('name_zh', ''),
                code=fund_data.get('code', ''),
                description=fund_data.get('description', ''),
                description_zh=fund_data.get('description_zh', ''),
                investment_philosophy=fund_data.get('investment_philosophy', ''),
                initial_holding_pct=_dec(fund_data.get('initial_holding_pct', 0)),
                max_holding_pct=_dec(fund_data.get('max_holding_pct', 0)),
                min_holding_pct=_dec(fund_data.get('min_holding_pct', 0)),
                trade_aggressiveness=_dec(fund_data.get('trade_aggressiveness', 0)),
                profile=fund_data.get('profile', {}),
            )
            for pref in prefs:
                AIInvestorPreference.objects.create(fund=fund, **pref)
                ai_fund_pref_count += 1
        counts['AIInvestorFund'] = len(data.get('ai_investor_funds', []))
        counts['AIInvestorPreference'] = ai_fund_pref_count

        # 18. Cultural Distance Matrix
        cd_count = 0
        for cd in data.get('cultural_distance', []):
            from_code, to_code, level, effectiveness, repat_cost = cd
            if from_code not in market_objs or to_code not in market_objs:
                continue
            CulturalDistanceMatrix.objects.create(
                scenario=scenario,
                from_market=market_objs[from_code],
                to_market=market_objs[to_code],
                distance_level=level,
                base_effectiveness=_dec(effectiveness),
                repatriation_cost_pct=_dec(repat_cost),
            )
            cd_count += 1
        counts['CulturalDistanceMatrix'] = cd_count

        # 19. Origin Trust Modifiers
        ot_count = 0
        for ot in data.get('origin_trust', []):
            origin_code, host_code, trust_mult, reg_mod, erosion = ot
            if origin_code not in market_objs or host_code not in market_objs:
                continue
            OriginTrustModifier.objects.create(
                scenario=scenario,
                origin_market=market_objs[origin_code],
                host_market=market_objs[host_code],
                customer_trust_multiplier=_dec(trust_mult),
                regulator_origin_modifier=_dec(reg_mod),
                trust_erosion_rate=_dec(erosion),
            )
            ot_count += 1
        counts['OriginTrustModifier'] = ot_count

        # 20. Local Strategic Partners (as StrategyOptionDefinitions)
        lsp_count = 0
        for lsp in data.get('local_strategic_partners', []):
            if lsp['market'] not in market_objs:
                continue
            effects = lsp.get('effects', [])
            obj = StrategyOptionDefinition.objects.create(
                scenario=scenario,
                category=lsp.get('category', 'Partnerships'),
                code=lsp['code'], name=lsp['name'],
                name_zh=lsp.get('name_zh', ''),
                description=lsp.get('description', ''),
                description_zh=lsp.get('description_zh', ''),
                capital_cost_base=lsp.get('capital_cost_base', 0),
                recurring_cost_per_round=lsp.get('recurring_cost_per_round', 0),
                time_lag_rounds=lsp.get('time_lag_rounds', 0),
                is_reversible=lsp.get('is_reversible', True),
                reversal_cost_multiplier=_dec(lsp.get('reversal_cost_multiplier', 0)),
            )
            for eff in effects:
                feat_code, eff_type, eff_val, mkt_specific = eff[0], eff[1], eff[2], eff[3]
                StrategyOptionEffect.objects.create(
                    strategy_option=obj,
                    feature=feature_objs[feat_code],
                    effect_type=eff_type,
                    effect_value=_dec(eff_val),
                    market_specific=mkt_specific,
                )
            lsp_count += 1
        counts['LocalStrategicPartner'] = lsp_count

        # 21. Governance Commitment Types
        for gct in data.get('governance_commitments', []):
            GovernanceCommitmentType.objects.create(
                scenario=scenario,
                code=gct['code'], name=gct['name'],
                name_zh=gct.get('name_zh', ''),
                description=gct.get('description', ''),
                description_zh=gct.get('description_zh', ''),
                ongoing_cost_per_round=gct.get('ongoing_cost_per_round', 0),
                benefits=gct.get('benefits', []),
                interactions=gct.get('interactions', []),
                revocation_penalty=gct.get('revocation_penalty', {}),
                prerequisite=gct.get('prerequisite'),
                amplifier=gct.get('amplifier'),
                display_order=gct.get('display_order', 0),
            )
        counts['GovernanceCommitmentType'] = len(data.get('governance_commitments', []))

        # 22. Tax Structures
        for ts in data.get('tax_structures', []):
            TaxStructureType.objects.create(
                scenario=scenario,
                code=ts['code'], name=ts['name'],
                name_zh=ts.get('name_zh', ''),
                description=ts.get('description', ''),
                description_zh=ts.get('description_zh', ''),
                setup_cost=ts.get('setup_cost', 0),
                annual_maintenance_cost=ts.get('annual_maintenance_cost', 0),
                effective_tax_reduction_pct=_dec(ts.get('effective_tax_reduction_pct', 0)),
                repatriation_cost_reduction_pct=_dec(ts.get('repatriation_cost_reduction_pct', 0)),
                audit_probability_per_round=_dec(ts.get('audit_probability_per_round', 0)),
                audit_penalty_multiplier=_dec(ts.get('audit_penalty_multiplier', 1)),
                value_investor_modifier=_dec(ts.get('value_investor_modifier', 0)),
                esg_investor_modifier=_dec(ts.get('esg_investor_modifier', 0)),
                regulator_modifier=_dec(ts.get('regulator_modifier', 0)),
                anti_corruption_conflict=ts.get('anti_corruption_conflict', False),
                display_order=ts.get('display_order', 0),
            )
        counts['TaxStructureType'] = len(data.get('tax_structures', []))

        # 23. Communication Assignments
        for ca in data.get('communication_assignments', []):
            CommunicationAssignment.objects.create(
                scenario=scenario,
                code=ca['code'], name=ca['name'],
                name_zh=ca.get('name_zh', ''),
                trigger_type=ca.get('trigger_type', ''),
                trigger_condition=ca.get('trigger_condition', {}),
                audience=ca.get('audience', ''),
                prompt_text=ca.get('prompt_text', ''),
                prompt_text_zh=ca.get('prompt_text_zh', ''),
                word_limit=ca.get('word_limit', 300),
                evaluation_criteria=ca.get('evaluation_criteria', []),
                is_mandatory=ca.get('is_mandatory', True),
                coherence_weight=_dec(ca.get('coherence_weight', 0)),
                display_order=ca.get('display_order', 0),
            )
        counts['CommunicationAssignment'] = len(data.get('communication_assignments', []))

        # 24. Organizational Structures
        for os_data in data.get('org_structures', []):
            OrganizationalStructureType.objects.update_or_create(
                scenario=scenario,
                code=os_data['code'],
                defaults={
                    'name': os_data['name'],
                    'name_zh': os_data.get('name_zh', ''),
                    'description': os_data.get('description', ''),
                    'description_zh': os_data.get('description_zh', ''),
                    'base_overhead_per_round': _dec(os_data.get('base_overhead_per_round', 0)),
                    'per_market_coordination_cost': _dec(os_data.get('per_market_coordination_cost', 0)),
                    'hq_talent_effectiveness_modifier': _dec(os_data.get('hq_talent_effectiveness_modifier', 1)),
                    'local_talent_effectiveness_modifier': _dec(os_data.get('local_talent_effectiveness_modifier', 1)),
                    'innovation_modifier': _dec(os_data.get('innovation_modifier', 1)),
                    'coordination_efficiency': _dec(os_data.get('coordination_efficiency', 1)),
                    'decision_speed_modifier': _dec(os_data.get('decision_speed_modifier', 1)),
                    'optimal_market_range_min': os_data.get('optimal_market_range_min', 1),
                    'optimal_market_range_max': os_data.get('optimal_market_range_max', 5),
                    'overextension_cost_per_market': _dec(os_data.get('overextension_cost_per_market', 0)),
                    'overextension_effectiveness_penalty': _dec(os_data.get('overextension_effectiveness_penalty', 0)),
                    'transition_cost': _dec(os_data.get('transition_cost', 0)),
                    'transition_disruption_rounds': os_data.get('transition_disruption_rounds', 0),
                    'display_order': os_data.get('display_order', 0),
                },
            )
        counts['OrganizationalStructureType'] = len(data.get('org_structures', []))

        # 25. Alliance Partner Profiles
        ap_count = 0
        for ap_data in data.get('alliance_partner_profiles', []):
            mkt_code = ap_data['market']
            if mkt_code not in market_objs:
                continue
            AlliancePartnerProfile.objects.create(
                scenario=scenario,
                partnership_code=ap_data['partnership_code'],
                market=market_objs[mkt_code],
                name=ap_data['name'],
                name_zh=ap_data.get('name_zh', ''),
                partner_type=ap_data['partner_type'],
                description=ap_data.get('description', ''),
                description_zh=ap_data.get('description_zh', ''),
                preferences=ap_data.get('preferences', []),
                satisfaction_floor=_dec(ap_data.get('satisfaction_floor', 0)),
                renegotiation_threshold=_dec(ap_data.get('renegotiation_threshold', 0)),
                patience_rounds=ap_data.get('patience_rounds', 2),
                benefit_curve=ap_data.get('benefit_curve', 'LINEAR'),
            )
            ap_count += 1
        counts['AlliancePartnerProfile'] = ap_count

        # 26. Government Profiles
        gp_count = 0
        for gp_data in data.get('government_profiles', []):
            mkt_code = gp_data['market']
            if mkt_code not in market_objs:
                continue
            GovernmentProfile.objects.create(
                scenario=scenario,
                market=market_objs[mkt_code],
                name=gp_data['name'],
                name_zh=gp_data.get('name_zh', ''),
                description=gp_data.get('description', ''),
                description_zh=gp_data.get('description_zh', ''),
                policy_priorities=gp_data.get('policy_priorities', []),
                incentive_threshold=_dec(gp_data.get('incentive_threshold', 0)),
                warning_threshold=_dec(gp_data.get('warning_threshold', 0)),
                restriction_threshold=_dec(gp_data.get('restriction_threshold', 0)),
                max_incentive_value_per_round=_dec(gp_data.get('max_incentive_value_per_round', 0)),
                procurement_budget_per_round=_dec(gp_data.get('procurement_budget_per_round', 0)),
                procurement_frequency=gp_data.get('procurement_frequency', 3),
                policy_volatility=_dec(gp_data.get('policy_volatility', 0)),
                patience_rounds=gp_data.get('patience_rounds', 2),
            )
            gp_count += 1
        counts['GovernmentProfile'] = gp_count

        # ------- SC: Suppliers (CC-04) -------
        supplier_objs = {}
        for sd_item in data.get('suppliers', []):
            obj = Supplier.objects.create(
                scenario=scenario,
                supplier_id=sd_item['id'],
                name=sd_item['name'],
                country=sd_item['country'],
                tier=sd_item['tier'],
                capacity_units_per_round=sd_item.get('capacity_units_per_round', 0),
                base_unit_price_usd=_dec(sd_item.get('base_unit_price_usd', 0)),
                quality_rating=_dec(sd_item.get('quality_rating', 0)),
                reliability_rating=_dec(sd_item.get('reliability_rating', 0)),
                lead_time_days_baseline=sd_item.get('lead_time_days_baseline', 0),
                min_order_commitment=sd_item.get('min_order_commitment', 0),
                specialization=sd_item.get('specialization', []),
                volume_discount_tiers=sd_item.get('volume_discount_tiers', []),
                tier_2_3_profile=sd_item.get('tier_2_3_profile', {}),
                origin_trust_to_buyers=sd_item.get('origin_trust_to_buyers', {}),
                certifications=sd_item.get('certifications', []),
                accepts_trade_finance=sd_item.get('accepts_trade_finance', []),
                political_risk_profile=sd_item.get('political_risk_profile', {}),
                multi_source_substitutability=sd_item.get('multi_source_substitutability', []),
            )
            supplier_objs[sd_item['id']] = obj
        counts['Supplier'] = len(supplier_objs)

        # ------- SC: Shipping Lanes (CC-04) -------
        lane_count = 0
        for ln in data.get('shipping_lanes', []):
            ShippingLane.objects.create(
                scenario=scenario,
                lane_id=ln['id'],
                origin_country=ln.get('origin_country', ''),
                origin_port=ln.get('origin_port', ''),
                destination_country=ln.get('destination_country', ''),
                destination_port=ln.get('destination_port', ''),
                zone=ln.get('zone', ''),
                modes=ln.get('modes', {}),
                chokepoints=ln.get('chokepoints', {}),
                disruption_exposure=ln.get('disruption_exposure', {}),
                customs_processing_days_baseline=ln.get('customs_processing_days_baseline', 0),
                reverse_logistics_available=ln.get('reverse_logistics_available', False),
                reverse_logistics_cost_multiplier=_dec(ln.get('reverse_logistics_cost_multiplier', 1)),
            )
            lane_count += 1
        counts['ShippingLane'] = lane_count

        # ------- SC: Trade Finance Instruments (CC-04) -------
        tf_data = data.get('trade_finance_instruments', {})
        tf_items = tf_data if isinstance(tf_data, list) else tf_data.get('instruments', [])
        tf_count = 0
        for tf in tf_items:
            TradeFinanceInstrument.objects.create(
                scenario=scenario,
                instrument_id=tf['id'],
                display_name=tf.get('display_name', tf['id']),
                cost_bps_of_transaction=tf.get('cost_bps_of_transaction'),
                cost_pct_of_insured_value=_dec(tf.get('cost_pct_of_insured_value')) if tf.get('cost_pct_of_insured_value') is not None else None,
                processing_lead_days=tf.get('processing_lead_days', 0),
                seller_protection=tf.get('seller_protection', 'medium'),
                buyer_cash_requirement=tf.get('buyer_cash_requirement', 'medium'),
                available_in_markets=tf.get('available_in_markets', ['all']),
                available_to_home_countries=tf.get('available_to_home_countries', ['all']),
                rejection_probability_baseline=_dec(tf.get('rejection_probability_baseline')) if tf.get('rejection_probability_baseline') is not None else None,
                buyer_default_probability_baseline=_dec(tf.get('buyer_default_probability_baseline')) if tf.get('buyer_default_probability_baseline') is not None else None,
                coverage_ceiling_pct=tf.get('coverage_ceiling_pct'),
                bri_market_premium_subsidy_pct=tf.get('bri_market_premium_subsidy_pct'),
                tenor_options_days=tf.get('tenor_options_days', []),
                currency_pairs_available=tf.get('currency_pairs_available', []),
            )
            tf_count += 1
        counts['TradeFinanceInstrument'] = tf_count

        # ------- SC: Compliance Regimes (CC-04) -------
        cr_count = 0
        for cr in data.get('compliance_regimes', []):
            ComplianceRegime.objects.create(
                scenario=scenario,
                regime_id=cr['id'],
                name=cr.get('name', cr['id']),
                enforcing_market=cr.get('enforcing_market'),
                enforcing_country=cr.get('enforcing_country'),
                applies_to_products=cr.get('applies_to_products', []),
                trigger_condition=cr.get('trigger_condition'),
                trigger_threshold_pct=cr.get('trigger_threshold_pct'),
                baseline_enforcement_probability_per_round=_dec(cr.get('baseline_enforcement_probability_per_round', 0)),
                detention_consequence=cr.get('detention_consequence', {}),
                mitigation_investments=cr.get('mitigation_investments', {}),
                phase_in_schedule=cr.get('phase_in_schedule', []),
                tariff_per_ton_co2_usd=_dec(cr.get('tariff_per_ton_co2_usd')) if cr.get('tariff_per_ton_co2_usd') is not None else None,
                sectors_covered=cr.get('sectors_covered', []),
                restricted_technologies=cr.get('restricted_technologies', []),
                target_countries_baseline=cr.get('target_countries_baseline', []),
            )
            cr_count += 1
        counts['ComplianceRegime'] = cr_count

        # ------- SC: Resilience Parameters (CC-04) -------
        rp = data.get('resilience_parameters', {})
        if rp:
            ResilienceParameters.objects.create(
                scenario=scenario,
                single_source_threshold_pct=rp.get('single_source_threshold_pct', 70),
                geographic_concentration_threshold_pct=rp.get('geographic_concentration_threshold_pct', 60),
                critical_component_buffer_days_recommended=rp.get('critical_component_buffer_days_recommended', 45),
                bullwhip_coefficient_baseline=_dec(rp.get('bullwhip_coefficient_baseline', 1.40)),
                resilience_score_weights=rp.get('resilience_score_weights', {}),
                disruption_cascade_coefficient=_dec(rp.get('disruption_cascade_coefficient', 0.30)),
                recovery_rate_with_alternatives_multiplier=_dec(rp.get('recovery_rate_with_alternatives_multiplier', 0.50)),
            )
            counts['ResilienceParameters'] = 1

        # ------- SC: Freight Market (CC-04) -------
        fm = data.get('freight_market', {})
        if fm:
            FreightMarket.objects.create(
                scenario=scenario,
                rate_dynamics_model=fm.get('rate_dynamics_model', 'demand_capacity_elastic'),
                baseline_capacity_abundance=fm.get('baseline_capacity_abundance', 'normal'),
                fuel_index_baseline_usd_per_barrel=_dec(fm.get('fuel_index_baseline_usd_per_barrel', 80)),
                fuel_index_volatility_sigma=_dec(fm.get('fuel_index_volatility_sigma', 0.12)),
                container_rate_volatility_sigma=_dec(fm.get('container_rate_volatility_sigma', 0.15)),
                demand_elasticity_coefficient=_dec(fm.get('demand_elasticity_coefficient', 1.30)),
                capacity_response_lag_rounds=fm.get('capacity_response_lag_rounds', 2),
            )
            counts['FreightMarket'] = 1

        # Summary
        self.stdout.write(self.style.SUCCESS("\n=== Scenario Load Complete ==="))
        total = 0
        for table, count in sorted(counts.items()):
            self.stdout.write(f"  {table}: {count}")
            total += count
        self.stdout.write(self.style.SUCCESS(f"  TOTAL RECORDS: {total}"))

        weight_sum = sum(float(s.performance_index_weight) for s in segment_objs.values())
        self.stdout.write(f"\n  Performance index weight sum: {weight_sum:.4f}")

        for sp in data.get('starter_profiles', []):
            platforms_dict = sp.get('platforms', {'alpha': sp.get('features', {})})
            for plabel, feats in platforms_dict.items():
                feat_total = sum(feats.values())
                self.stdout.write(f"  {sp['profile_name']} [{plabel}] feature total: {feat_total}")

        self.stdout.write(f"\n  Scenario ID: {scenario.pk}")
