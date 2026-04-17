"""
Engine Step 10: Revenue Calculation.
From 03-engine-logic.md Section 9.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.decisions import DecisionMarketing, DecisionSubmission
from core.models.results import RoundResultAdoption
from core.models.team_state import TeamProduct, TeamProductMarket, TeamMarketPresence
from core.engine.utils import get_config

# Default channel margin rates by distribution strategy.
# These represent the percentage of the retail price retained by
# distributors/retailers. The firm receives (1 - margin_rate) × retail_price.
# Can be overridden per-scenario via ScenarioConfig keys:
#   channel_margin_mass_retail, channel_margin_selective_retail, etc.
DEFAULT_CHANNEL_MARGINS = {
    'mass_retail': Decimal('0.30'),        # 30% — high volume, retailer takes large cut
    'intensive': Decimal('0.30'),          # alias for mass_retail
    'selective_retail': Decimal('0.25'),   # 25% — curated channel, moderate margin
    'selective': Decimal('0.25'),          # alias for selective_retail
    'exclusive_retail': Decimal('0.35'),   # 35% — premium placement, retailer demands more
    'exclusive': Decimal('0.35'),          # alias for exclusive_retail
    'direct_online': Decimal('0.05'),      # 5%  — platform/payment fees only
    'direct': Decimal('0.05'),             # alias for direct_online
    'hybrid': Decimal('0.20'),             # 20% — blended across channels
}


def _get_channel_margin_rate(scenario, distribution_strategy):
    """Look up the channel margin rate for a distribution strategy.

    Checks ScenarioConfig first (e.g. key 'channel_margin_mass_retail'),
    falling back to DEFAULT_CHANNEL_MARGINS.
    """
    config_key = f'channel_margin_{distribution_strategy}'
    configured = get_config(scenario, config_key, default=None)
    if configured is not None:
        return Decimal(str(configured))
    return DEFAULT_CHANNEL_MARGINS.get(distribution_strategy, Decimal('0.20'))


def calculate_revenue(context):
    """
    For each team, for each market, for each product:
    - Sum new_adopters across all segments served by this product
    - Multiply by retail price to get gross local revenue
    - Apply channel/distributor margin deduction based on distribution strategy
    - Convert to home currency using effective exchange rate
    - Store per product-market and aggregate per market
    """
    game = context.game
    current_round = context.round_number

    # Initialize revenue storage on context
    context.revenue = {}          # (team_id, product_id, market_id) → dict
    context.market_revenue = {}   # (team_id, market_id) → dict

    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()
        if not submission:
            continue

        mkt_decisions = DecisionMarketing.objects.filter(
            submission=submission,
        ).select_related('team_product', 'market')

        for mkt_dec in mkt_decisions:
            product = mkt_dec.team_product
            market = mkt_dec.market

            # Sum new adopters for this product in this market
            units_sold = Decimal('0')
            adoptions = RoundResultAdoption.objects.filter(
                game=game,
                round_number=current_round,
                team=team,
                market=market,
                best_product=product,
            )
            for adoption in adoptions:
                units_sold += adoption.new_adopters

            retail_price = mkt_dec.retail_price
            gross_local_revenue = units_sold * retail_price

            # Channel/distributor margin deduction
            distribution_strategy = mkt_dec.distribution_strategy or 'hybrid'
            channel_margin_rate = _get_channel_margin_rate(context.scenario, distribution_strategy)
            channel_margin_local = (gross_local_revenue * channel_margin_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )
            local_revenue = gross_local_revenue - channel_margin_local

            # Get effective exchange rate
            mkt_state = context.markets.get(market.id)
            exchange_rate = Decimal(str(
                mkt_state.effective_exchange_rate if mkt_state
                else float(market.exchange_rate_base)
            ))
            home_revenue = local_revenue * exchange_rate
            channel_margin_home = (channel_margin_local * exchange_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP,
            )

            units_produced = mkt_dec.production_volume
            units_unsold = max(Decimal(str(units_produced)) - units_sold, Decimal('0'))

            rev_key = (team.id, product.id, market.id)
            context.revenue[rev_key] = {
                'units_sold': units_sold,
                'units_produced': units_produced,
                'units_unsold': units_unsold,
                'retail_price': retail_price,
                'gross_local_revenue': gross_local_revenue,
                'channel_margin_rate': channel_margin_rate,
                'channel_margin_local': channel_margin_local,
                'channel_margin_home': channel_margin_home,
                'distribution_strategy': distribution_strategy,
                'local_revenue': local_revenue,
                'home_revenue': home_revenue,
                'exchange_rate': exchange_rate,
            }

            # Aggregate to market level
            mkt_key = (team.id, market.id)
            if mkt_key not in context.market_revenue:
                context.market_revenue[mkt_key] = {
                    'local_revenue': Decimal('0'),
                    'home_revenue': Decimal('0'),
                    'channel_margin_home': Decimal('0'),
                    'market': market,
                }
            context.market_revenue[mkt_key]['local_revenue'] += local_revenue
            context.market_revenue[mkt_key]['home_revenue'] += home_revenue
            context.market_revenue[mkt_key]['channel_margin_home'] += channel_margin_home

    context.log.append('Revenue calculated (with channel/distributor margins)')
