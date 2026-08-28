"""The documented baseline every screening probe deviates from.

Not invented for this handoff. These are the numbers the project's own
`load_demo` command scripts as competent play — budget split, price and volume
by positioning, channel mix, sales staffing, talent pools — copied here so the
baseline is a fixed, citable artefact rather than whatever the demo command
happens to do next month.

`setup_test_game` supplies the state the decisions need: two active products per
team with a positioning, one platform, one active market, and $60,000,000 of
cash. `load_demo` cannot be used directly — on a freshly migrated database its
flush path raw-deletes into an aborted transaction and leaves no game.
"""
from decimal import Decimal as D

# load_demo._add_budget defaults.
BUDGET = {
    'rd_budget': D('2000000'),
    'marketing_budget': D('3000000'),
    'strategy_budget': D('1000000'),
    'research_budget': D('500000'),
}

# load_demo._add_marketing_decision, keyed by product positioning.
PRICE_BY_POSITIONING = {'budget': D('250'), 'mainstream': D('420'),
                        'premium': D('700'), 'ultra_premium': D('1000')}
VOLUME_BY_POSITIONING = {'budget': 25000, 'mainstream': 20000,
                         'premium': 12000, 'ultra_premium': 8000}
PROMO_BY_POSITIONING = {'budget': D('200000'), 'mainstream': D('300000'),
                        'premium': D('400000'), 'ultra_premium': D('500000')}
DEFAULT_PRICE = D('400')
DEFAULT_VOLUME = 20000
DEFAULT_PROMO = D('300000')

MARKETING = {
    'channel_digital_pct': D('0.4000'),
    'channel_traditional_pct': D('0.3000'),
    'channel_trade_pct': D('0.3000'),
    'distribution_strategy': 'hybrid',
    'distribution_investment': D('200000'),
    'sales_team_count': 10,
    'distribution_channel_detail': {'direct_online': 5, 'selective_retail': 3,
                                    'mass_retail': 2},
}

# load_demo._add_default_talent: rd, commercial, operations.
TALENT = {
    'rd_headcount': 50, 'commercial_headcount': 30, 'operations_headcount': 40,
    'rd_salary_level': 3, 'commercial_salary_level': 3,
    'operations_salary_level': 3,
    'rd_training_budget': D('0'), 'commercial_training_budget': D('0'),
    'operations_training_budget': D('0'),
}

ESG = {'environmental_investment': D('0'), 'social_investment': D('0')}


def build(submission, team):
    """Write the baseline decision set for one team."""
    from core.models.decisions import (DecisionBudgetAllocation, DecisionESG,
                                       DecisionMarketing)
    from core.models.talent import DecisionTalent
    from core.models.team_state import (TeamPlatformFeatureLevel, TeamProduct,
                                        TeamProductMarket)

    DecisionBudgetAllocation.objects.filter(submission=submission).delete()
    DecisionBudgetAllocation.objects.create(submission=submission, **BUDGET)

    DecisionESG.objects.filter(submission=submission).delete()
    DecisionESG.objects.create(submission=submission, **ESG)

    DecisionTalent.objects.filter(submission=submission).delete()
    DecisionTalent.objects.create(submission=submission, **TALENT)

    DecisionMarketing.objects.filter(submission=submission).delete()
    home = team.home_market
    for product in TeamProduct.objects.filter(
            team=team, status='active').order_by('id'):
        positioning = product.positioning
        focus = list(
            TeamPlatformFeatureLevel.objects
            .filter(team_platform=product.team_platform, current_level__gt=0)
            .order_by('-current_level')
            .values_list('feature_id', flat=True)[:3])
        for tpm in TeamProductMarket.objects.filter(
                team_product=product, is_active=True).order_by('id'):
            volume = VOLUME_BY_POSITIONING.get(positioning, DEFAULT_VOLUME)
            DecisionMarketing.objects.create(
                submission=submission,
                team_product=product,
                market_id=tpm.market_id,
                retail_price=PRICE_BY_POSITIONING.get(positioning, DEFAULT_PRICE),
                promotion_budget=PROMO_BY_POSITIONING.get(positioning, DEFAULT_PROMO),
                campaign_focus_feature_ids=focus or [],
                production_volume=volume,
                production_source_market_id=home.id,
                demand_estimate=int(volume * 1.5),
                **MARKETING,
            )
    return submission


# ---------------------------------------------------------------------------
# Optional baseline rows
# ---------------------------------------------------------------------------
# The five decision types above cover about two thirds of the screenable
# dimensions. The rest — R&D, plants, partnerships, market entry, platform
# development — carry real cost-bearing fields, and a dimension with no row to
# vary is a dimension nobody screened. Each is built where the seeded scenario
# supplies the foreign keys it needs, and each failure is recorded rather than
# swallowed, so "not screened" is always a stated reason.

OPTIONAL_AMOUNT = D('100000')


def build_optional(submission, team):
    """Add one row of each remaining decision type. Returns {type: status}."""
    from core.models.decisions import (DecisionMarketEntry, DecisionPartnership,
                                       DecisionPlant,
                                       DecisionPlatformDevelopment,
                                       DecisionRDInvestment)
    from core.models.scenario import (EntryModeDefinition, FeatureDefinition,
                                      PlatformFeatureCeiling,
                                      PlatformGenerationDefinition,
                                      StrategyOptionDefinition)
    from core.models.team_state import TeamMarketPresence, TeamPlatform

    status = {}
    home = team.home_market
    platform = TeamPlatform.objects.filter(team=team).order_by('id').first()
    present = list(TeamMarketPresence.objects
                   .filter(team=team, status='active')
                   .values_list('market_id', flat=True))

    def attempt(name, fn):
        try:
            fn()
            status[name] = 'built'
        except Exception as error:
            status[name] = f'not built: {type(error).__name__}: {error}'

    def rd():
        DecisionRDInvestment.objects.filter(submission=submission).delete()
        if platform is None:
            raise ValueError('team has no platform')
        ceiling = (PlatformFeatureCeiling.objects
                   .filter(platform_generation=platform.platform_generation,
                           ceiling_value__gt=0)
                   .order_by('feature_id').first())
        if ceiling is None:
            raise ValueError('no feature is reachable on this platform')
        DecisionRDInvestment.objects.create(
            submission=submission, team_platform=platform,
            feature_id=ceiling.feature_id, method='in_house',
            amount=OPTIONAL_AMOUNT, target_level=1)

    def plants():
        DecisionPlant.objects.filter(submission=submission).delete()
        DecisionPlant.objects.create(
            submission=submission, market=home, action='build',
            capacity_units=1000, contract_mfg_volume=0)

    def partnerships():
        DecisionPartnership.objects.filter(submission=submission).delete()
        option = StrategyOptionDefinition.objects.order_by('id').first()
        if option is None:
            raise ValueError('scenario defines no strategy option')
        DecisionPartnership.objects.create(
            submission=submission, market=home, strategy_option=option,
            annual_investment=OPTIONAL_AMOUNT, action='form')

    def market_entry():
        DecisionMarketEntry.objects.filter(submission=submission).delete()
        mode = EntryModeDefinition.objects.order_by('id').first()
        from core.models.scenario import MarketDefinition
        candidate = (MarketDefinition.objects
                     .filter(scenario=team.game.scenario)
                     .exclude(id__in=present).order_by('id').first())
        if mode is None or candidate is None:
            raise ValueError('no entry mode or no market left to enter')
        DecisionMarketEntry.objects.create(
            submission=submission, market=candidate, entry_mode=mode,
            initial_investment=OPTIONAL_AMOUNT, action='enter')

    def platforms():
        DecisionPlatformDevelopment.objects.filter(submission=submission).delete()
        generation = (PlatformGenerationDefinition.objects
                      .filter(scenario=team.game.scenario)
                      .order_by('generation_order').first())
        if generation is None:
            raise ValueError('scenario defines no platform generation')
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=generation,
            method='in_house', committed_cost=OPTIONAL_AMOUNT)

    attempt('rd', rd)
    attempt('plants', plants)
    attempt('partnerships', partnerships)
    attempt('market-entry', market_entry)
    attempt('platforms', platforms)
    return status
