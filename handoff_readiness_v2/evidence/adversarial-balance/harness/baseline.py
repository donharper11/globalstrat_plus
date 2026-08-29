"""The documented baseline every screening probe deviates from.

R&D note: the baseline invests the scenario's `rd_spend_target` in actual
`DecisionRDInvestment.amount`. It previously carried a $100,000 placeholder
while declaring a $2,000,000 budget, which V2-021 had already established
scoring ignores. Anything measured against that baseline was measured against
an opponent earning five per cent of the available R&D capability.

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


class ScenarioLimit(Exception):
    """A decision type this scenario cannot express, with the rule that says so.

    Distinct from a harness failure. "No baseline row" is not an answer to
    "is this dimension flat?" — it is an admission that nobody looked. A
    genuine configuration limit names the rule; anything else is a bug in this
    harness and must stop the run rather than quietly shrink the screen.
    """

    def __init__(self, rule):
        super().__init__(rule)
        self.rule = rule


def build_optional(submission, team):
    """Add one row of every remaining decision type this scenario supports.

    Returns `{decision_type: {'built': bool, 'rule': str | None}}`. A False
    with a rule is a scenario limit; a False without one cannot happen — the
    exception propagates instead.
    """
    from core.models.decisions import (DecisionFinancing, DecisionMarketEntry,
                                       DecisionPartnership, DecisionPlant,
                                       DecisionPlatformDevelopment,
                                       DecisionProductCreate,
                                       DecisionProductRetire,
                                       DecisionRDInvestment)
    from core.models.scenario import (EntryModeDefinition, MarketDefinition,
                                      PlatformFeatureCeiling,
                                      PlatformGenerationDefinition,
                                      StrategyOptionDefinition)
    from core.models.team_state import (TeamMarketPresence, TeamPlatform,
                                        TeamProduct)

    scenario = team.game.scenario
    home = team.home_market
    platform = TeamPlatform.objects.filter(team=team).order_by('id').first()
    present = list(TeamMarketPresence.objects
                   .filter(team=team, status='active')
                   .values_list('market_id', flat=True))

    status = {}

    def attempt(name, fn):
        try:
            fn()
            status[name] = {'built': True, 'rule': None}
        except ScenarioLimit as limit:
            status[name] = {'built': False, 'rule': limit.rule}

    def financing():
        DecisionFinancing.objects.filter(submission=submission).delete()
        DecisionFinancing.objects.create(
            submission=submission, new_debt=D('0'), debt_repayment=D('0'),
            new_equity=D('0'), dividend_per_share=D('0'))

    def rd():
        DecisionRDInvestment.objects.filter(submission=submission).delete()
        if platform is None:
            raise ScenarioLimit(
                'the starter profile grants this team no platform, so no R&D '
                'row can name a team_platform')
        ceiling = (PlatformFeatureCeiling.objects
                   .filter(platform_generation=platform.platform_generation,
                           ceiling_value__gt=0)
                   .order_by('feature_id').first())
        if ceiling is None:
            raise ScenarioLimit(
                f'no PlatformFeatureCeiling with ceiling_value > 0 exists for '
                f'platform generation {platform.platform_generation_id}, so no '
                f'feature is reachable for R&D on this platform')
        # The baseline spends the scenario's R&D target, not the $100,000
        # placeholder this row used to carry. V2-021 made the declared
        # `rd_budget` inert and scores actual `DecisionRDInvestment.amount`
        # against the target, so a baseline declaring $2,000,000 while
        # investing $100,000 earned five per cent of the available capability
        # credit and was not competent play in the only sense scoring reads.
        # Every margin measured against it was a margin over a weak opponent.
        from core.engine.performance import scenario_rd_spend_target
        DecisionRDInvestment.objects.create(
            submission=submission, team_platform=platform,
            feature_id=ceiling.feature_id, method='in_house',
            amount=scenario_rd_spend_target(scenario), target_level=1)

    def plants():
        DecisionPlant.objects.filter(submission=submission).delete()
        DecisionPlant.objects.create(
            submission=submission, market=home, action='build',
            capacity_units=1000, contract_mfg_volume=0)

    def partnerships():
        DecisionPartnership.objects.filter(submission=submission).delete()
        option = (StrategyOptionDefinition.objects
                  .filter(scenario=scenario).order_by('id').first()
                  or StrategyOptionDefinition.objects.order_by('id').first())
        if option is None:
            raise ScenarioLimit(
                'the scenario defines no StrategyOptionDefinition rows, so a '
                'partnership cannot name a strategy_option')
        DecisionPartnership.objects.create(
            submission=submission, market=home, strategy_option=option,
            annual_investment=OPTIONAL_AMOUNT, action='form')

    def market_entry():
        DecisionMarketEntry.objects.filter(submission=submission).delete()
        mode = (EntryModeDefinition.objects.filter(scenario=scenario)
                .order_by('id').first()
                or EntryModeDefinition.objects.order_by('id').first())
        if mode is None:
            raise ScenarioLimit(
                'the scenario defines no EntryModeDefinition rows, so a market '
                'entry cannot name an entry_mode')
        candidate = (MarketDefinition.objects.filter(scenario=scenario)
                     .exclude(id__in=present).order_by('id').first())
        if candidate is None:
            raise ScenarioLimit(
                f'the team is already present in every market this scenario '
                f'defines ({len(present)} of '
                f'{MarketDefinition.objects.filter(scenario=scenario).count()}), '
                f'so there is no market left to enter')
        DecisionMarketEntry.objects.create(
            submission=submission, market=candidate, entry_mode=mode,
            initial_investment=OPTIONAL_AMOUNT, action='enter')

    def platforms():
        DecisionPlatformDevelopment.objects.filter(submission=submission).delete()
        generation = (PlatformGenerationDefinition.objects
                      .filter(scenario=scenario)
                      .order_by('generation_order').first())
        if generation is None:
            raise ScenarioLimit(
                'the scenario defines no PlatformGenerationDefinition rows, so '
                'a platform development cannot name a generation')
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=generation,
            method='in_house', committed_cost=OPTIONAL_AMOUNT)

    def products():
        DecisionProductCreate.objects.filter(submission=submission).delete()
        if platform is None:
            raise ScenarioLimit(
                'the starter profile grants this team no platform, so a new '
                'product cannot name a team_platform')
        DecisionProductCreate.objects.create(
            submission=submission, team_platform=platform,
            product_name='Screening Baseline Product',
            positioning='mainstream',
            target_market_ids=[home.id])

    def product_retires():
        DecisionProductRetire.objects.filter(submission=submission).delete()
        product = (TeamProduct.objects.filter(team=team, status='active')
                   .order_by('id').first())
        if product is None:
            raise ScenarioLimit(
                'the team has no active product, so nothing can be retired')
        DecisionProductRetire.objects.create(
            submission=submission, team_product=product, timing='end_of_round')

    attempt('financing', financing)
    attempt('rd', rd)
    attempt('plants', plants)
    attempt('partnerships', partnerships)
    attempt('market-entry', market_entry)
    attempt('platforms', platforms)
    attempt('products', products)
    attempt('product-retires', product_retires)
    return status
