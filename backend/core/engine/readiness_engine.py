"""
Engine Step 7: Market Readiness Gating.
From 03-engine-logic.md Section 7.

Caps the addressable market for products based on their platform
generation's readiness in each market. A Gen 3 product in a market
that's only 20% ready for Gen 3 sees a severely limited addressable market.
"""
from core.models.team_state import TeamProduct, TeamProductMarket
from core.models.scenario import MarketReadiness


def apply_readiness_gating(context):
    """
    Engine Step 7: Look up market readiness for each team's product
    in each market and store readiness_pct in context.
    """
    current_round = context.round_number

    for team in context.teams:
        # Get all active products for this team
        products = TeamProduct.objects.filter(
            team=team, status='active',
        ).select_related('team_platform__platform_generation')

        for product in products:
            platform_gen = product.team_platform.platform_generation

            # Get markets where this product is offered
            product_markets = TeamProductMarket.objects.filter(
                team_product=product, is_active=True,
            ).select_related('market')

            for pm in product_markets:
                market = pm.market

                # Look up readiness
                try:
                    readiness = MarketReadiness.objects.get(
                        market=market,
                        platform_generation=platform_gen,
                        round_number=current_round,
                    )
                    readiness_pct = float(readiness.readiness_pct)
                except MarketReadiness.DoesNotExist:
                    readiness_pct = 1.0  # Default: fully ready

                context.readiness[
                    (team.id, product.id, market.id)
                ] = readiness_pct

    context.log.append('Market readiness gating applied')
