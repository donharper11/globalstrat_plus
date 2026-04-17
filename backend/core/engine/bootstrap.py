"""
Round 0 Bootstrap — Generate starting-state results from FirmStarterProfile data.

Students see these results when they first log in, giving them something to
analyze before making Round 1 decisions.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.core import Game, Team, Round
from core.models.scenario import (
    SegmentDefinition, SegmentPreference, FeatureDefinition,
    MarketDefinition, FirmStarterProduct,
)
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel, TeamProduct,
    TeamProductMarket, TeamMarketPresence,
)
from core.models.results import RoundResultAdoption
from core.models.results_financials import (
    RoundResultProductMarket, RoundResultFinancials,
    RoundResultMarketRevenue, RoundResultPerformanceIndex,
    RoundResultCoherence, LeaderboardEntry,
)
from core.engine.utils import gaussian_fit, get_config, clamp

D = Decimal


def _q(val):
    """Quantize to 2 decimal places."""
    return Decimal(str(val)).quantize(D('0.01'), rounding=ROUND_HALF_UP)


def bootstrap_round_zero(game):
    """
    Generate full Round 0 results from starter profile data.
    Populates all Group 6 result tables so students see financials,
    adoption, leaderboard, etc. on first login.
    """
    scenario = game.scenario
    teams = list(Team.objects.filter(game=game))
    markets = list(MarketDefinition.objects.filter(scenario=scenario))
    all_segments = list(SegmentDefinition.objects.filter(scenario=scenario))

    # Ensure Round 0 exists and is processed
    round_obj, _ = Round.objects.get_or_create(
        game=game, round_number=0,
        defaults={'status': 'processed'},
    )
    round_obj.status = 'processed'
    round_obj.save()

    base_unit_cost = D(str(get_config(scenario, 'base_unit_cost', 45.0)))
    admin_overhead = D(str(get_config(scenario, 'admin_overhead_fixed', 500000)))
    interest_rate = D(str(get_config(scenario, 'debt_interest_rate', 0.06)))

    leaderboard_data = []

    # CC-16: Initialize talent state for all teams
    from core.models.talent import TeamTalentState
    for team in teams:
        pool_defaults = {
            'rd': {'headcount': 50, 'salary_level': 3},
            'commercial': {'headcount': 30, 'salary_level': 3},
            'operations': {'headcount': 40, 'salary_level': 3},
        }
        for pool, defaults in pool_defaults.items():
            TeamTalentState.objects.update_or_create(
                team=team, talent_pool=pool, round_number=0,
                defaults={
                    'headcount': defaults['headcount'],
                    'salary_level': defaults['salary_level'],
                    'cumulative_training': D('0'),
                    'talent_level': D('3.00'),
                    'turnover_rate': D('0.1000'),
                },
            )

    for team in teams:
        starter = team.firm_starter_profile
        platforms = list(TeamPlatform.objects.filter(team=team, status='active'))
        products = list(TeamProduct.objects.filter(team=team, status='active'))
        home_presence = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).first()
        home_market = home_presence.market if home_presence else markets[0]

        # Feature levels per platform for preference matching
        platform_feature_levels = {}  # {platform_id: {feature_id: level}}
        for plat in platforms:
            levels = {}
            for fl in TeamPlatformFeatureLevel.objects.filter(team_platform=plat):
                levels[fl.feature_id] = float(fl.current_level)
            platform_feature_levels[plat.id] = levels
        # Aggregate feature levels (best across platforms) for segment scoring
        feature_levels = {}
        for levels in platform_feature_levels.values():
            for fid, lvl in levels.items():
                feature_levels[fid] = max(feature_levels.get(fid, 0), lvl)

        # ── Product-Market Results ──
        team_total_revenue = D('0')
        team_total_cogs = D('0')
        team_total_units = 0

        for product in products:
            product_market = TeamProductMarket.objects.filter(
                team_product=product, market=home_market,
            ).first()
            if not product_market:
                continue

            # Match to starter product for price/volume
            starter_product = starter.starter_products.filter(
                product_name=product.name,
            ).first()
            if not starter_product:
                continue

            price = starter_product.base_price
            volume = starter_product.unit_volume
            units_sold = volume

            revenue = D(str(units_sold)) * price
            unit_cost = _q(base_unit_cost * D(str(home_market.base_manufacturing_cost)))
            cogs = D(str(units_sold)) * unit_cost

            team_total_revenue += revenue
            team_total_cogs += cogs
            team_total_units += units_sold

            RoundResultProductMarket.objects.update_or_create(
                game=game, round_number=0, team=team,
                team_product=product, market=home_market,
                defaults={
                    'units_produced': volume,
                    'units_sold': D(str(units_sold)),
                    'units_unsold': D('0'),
                    'retail_price': price,
                    'local_revenue': revenue,
                    'home_revenue': revenue,
                    'unit_cost': unit_cost,
                    'total_cogs': cogs,
                    'logistics_cost': D('0'),
                    'tariff_cost': D('0'),
                    'inventory_holding_cost': D('0'),
                },
            )

        # ── Segment Adoption ──
        for segment in all_segments:
            seg_market = segment.market if segment.market else home_market

            if segment.segment_type == 'customer' and seg_market == home_market:
                # Preference-weighted fit score
                preferences = SegmentPreference.objects.filter(segment=segment)
                total_wscore = 0.0
                total_weight = 0.0
                for pref in preferences:
                    actual = feature_levels.get(pref.feature_id, float(pref.feature.default_value))
                    fit = gaussian_fit(actual, float(pref.ideal_value), float(pref.tolerance))
                    total_wscore += fit * float(pref.weight)
                    total_weight += float(pref.weight)

                fit_score = total_wscore / total_weight if total_weight > 0 else 0.0

                # Use starter share to estimate adoption
                avg_share = float(
                    sum(sp.market_share_pct for sp in starter.starter_products.all())
                ) / max(starter.starter_products.count(), 1)

                bass_p = float(segment.bass_p)
                pop = float(segment.population_size)
                new_adopters = bass_p * pop * avg_share * 10  # Scale for meaningful numbers

                best_product = products[0] if products else None
                RoundResultAdoption.objects.update_or_create(
                    game=game, round_number=0, team=team,
                    segment=segment, market=seg_market,
                    defaults={
                        'best_product': best_product,
                        'fit_score': _q(fit_score),
                        'adjusted_fit_score': _q(fit_score),
                        'market_readiness_pct': D('1.0000'),
                        'adoption_pool': _q(bass_p * pop),
                        'team_attractiveness': _q(fit_score),
                        'team_share_pct': _q(avg_share),
                        'new_adopters': _q(new_adopters),
                        'cumulative_adopters': _q(new_adopters),
                    },
                )
            else:
                # Non-customer or non-home market — baseline record
                fit_score = 0.5 if segment.segment_type != 'customer' else 0.0
                RoundResultAdoption.objects.update_or_create(
                    game=game, round_number=0, team=team,
                    segment=segment,
                    market=segment.market or home_market,
                    defaults={
                        'best_product': None,
                        'fit_score': D(str(fit_score)),
                        'adjusted_fit_score': D(str(fit_score)),
                        'market_readiness_pct': D('1.0000'),
                        'adoption_pool': D('0'),
                        'team_attractiveness': D(str(fit_score)),
                        'team_share_pct': D('0'),
                        'new_adopters': D('0'),
                        'cumulative_adopters': D('0'),
                    },
                )

        # ── Financial Statements ──
        gross_profit = team_total_revenue - team_total_cogs
        operating_income = gross_profit - admin_overhead
        interest_expense = _q(D(str(team.total_debt)) * interest_rate)
        pre_tax_income = operating_income - interest_expense
        tax_expense = _q(max(pre_tax_income * D(str(home_market.tax_rate)), D('0')))
        net_income = pre_tax_income - tax_expense

        cash_closing = D(str(team.cash_on_hand))
        total_debt = D(str(team.total_debt))
        total_equity = cash_closing - total_debt

        team.total_equity = total_equity
        team.save(update_fields=['total_equity'])

        gross_margin = (gross_profit / team_total_revenue) if team_total_revenue > 0 else D('0')
        net_margin = (net_income / team_total_revenue) if team_total_revenue > 0 else D('0')
        roe = (net_income / total_equity) if total_equity > 0 else D('0')
        d_e = (total_debt / total_equity) if total_equity > 0 else D('0')
        share_price = _q(total_equity / D('1000000'))

        RoundResultFinancials.objects.update_or_create(
            game=game, round_number=0, team=team,
            defaults={
                'total_revenue': team_total_revenue,
                'total_cogs': team_total_cogs,
                'gross_profit': gross_profit,
                'rd_expense': D('0'),
                'marketing_expense': D('0'),
                'strategy_expense': D('0'),
                'research_expense': D('0'),
                'admin_overhead': admin_overhead,
                'logistics_tariff_expense': D('0'),
                'inventory_expense': D('0'),
                'operating_income': operating_income,
                'interest_expense': interest_expense,
                'pre_tax_income': pre_tax_income,
                'tax_expense': tax_expense,
                'net_income': net_income,
                'cash_opening': cash_closing,
                'cash_closing': cash_closing,
                'total_assets': cash_closing,
                'total_debt': total_debt,
                'total_equity': total_equity,
                'plant_book_value': D('0'),
                'inventory_value': D('0'),
                'operating_cash_flow': net_income,
                'investing_cash_flow': D('0'),
                'financing_cash_flow': D('0'),
                'dividends_paid': D('0'),
                'share_price': share_price,
                'roe': clamp(roe, D('-9.9999'), D('9.9999')),
                'debt_to_equity': clamp(d_e, D('0'), D('9.9999')),
                'gross_margin_pct': clamp(gross_margin, D('-9.9999'), D('9.9999')),
                'net_margin_pct': clamp(net_margin, D('-9.9999'), D('9.9999')),
                'shareholder_return_cumulative': D('0'),
            },
        )

        # Market revenue — home market
        home_share = D(str(
            sum(float(sp.market_share_pct) for sp in starter.starter_products.all())
        ))
        RoundResultMarketRevenue.objects.update_or_create(
            game=game, round_number=0, team=team, market=home_market,
            defaults={
                'local_revenue': team_total_revenue,
                'home_revenue': team_total_revenue,
                'market_profit': net_income,
                'market_share_pct': home_share,
            },
        )
        # Zero records for non-home markets
        for market in markets:
            if market != home_market:
                RoundResultMarketRevenue.objects.update_or_create(
                    game=game, round_number=0, team=team, market=market,
                    defaults={
                        'local_revenue': D('0'),
                        'home_revenue': D('0'),
                        'market_profit': D('0'),
                        'market_share_pct': D('0'),
                    },
                )

        # Performance index — base
        RoundResultPerformanceIndex.objects.update_or_create(
            game=game, round_number=0, team=team,
            defaults={
                'satisfaction_score': D('0.5000'),
                'index_change': D('0'),
                'index_value': D(str(scenario.performance_index_base)),
            },
        )

        # Coherence — baseline
        RoundResultCoherence.objects.update_or_create(
            game=game, round_number=0, team=team,
            defaults={
                'formula_score': D('50.00'),
                'rag_score': None,
                'blended_score': D('50.00'),
                'breakdown': {
                    'note': 'Round 0 baseline — no student decisions to evaluate yet.',
                },
            },
        )

        leaderboard_data.append({
            'team': team,
            'index': scenario.performance_index_base,
            'revenue': team_total_revenue,
            'net_income': net_income,
            'share_price': share_price,
        })

        # === CC-26: Initialize AI investor holdings and share price ===
        from core.models.cc26_models import AIInvestorFund, AIInvestorHolding, SharePriceHistory

        investor_funds = AIInvestorFund.objects.filter(scenario=game.scenario)
        book_value = _q(total_equity / D('1000000'))  # total_equity / shares_outstanding

        for fund in investor_funds:
            initial_shares = int(float(fund.initial_holding_pct) * 1000000)
            AIInvestorHolding.objects.update_or_create(
                game=game, fund=fund, team=team, round_number=0,
                defaults={
                    'shares_held': initial_shares,
                    'holding_pct': fund.initial_holding_pct,
                    'satisfaction_score': Decimal('0.5000'),
                    'action': 'initial',
                    'shares_traded': 0,
                    'trade_reason': f'Initial allocation — {fund.name} takes {float(fund.initial_holding_pct)*100:.0f}% position',
                },
            )

        SharePriceHistory.objects.update_or_create(
            game=game, team=team, round_number=0,
            defaults={
                'book_value_per_share': book_value,
                'sentiment_multiplier': Decimal('1.0000'),
                'share_price': book_value,
                'total_shares_outstanding': 1000000,
                'market_cap': book_value * 1000000,
                'velocity_satisfaction': Decimal('0.5000'),
                'granite_satisfaction': Decimal('0.5000'),
                'greenhorizon_satisfaction': Decimal('0.5000'),
                'aggregate_demand': Decimal('0.1500'),
            },
        )

        team.share_price = book_value
        team.save(update_fields=['share_price'])

    # ── Leaderboard ──
    leaderboard_data.sort(key=lambda x: (-float(x['index']), -float(x['revenue'])))
    for rank, data in enumerate(leaderboard_data, 1):
        team = data['team']
        presence = TeamMarketPresence.objects.filter(team=team, status='active')
        share_summary = {}
        for p in presence:
            rev = RoundResultMarketRevenue.objects.filter(
                game=game, round_number=0, team=team, market=p.market,
            ).first()
            if rev:
                share_summary[p.market.code] = float(rev.market_share_pct)

        LeaderboardEntry.objects.update_or_create(
            game=game, round_number=0, team=team,
            defaults={
                'rank': rank,
                'performance_index': D(str(data['index'])),
                'shareholder_return': D('0'),
                'total_revenue': data['revenue'],
                'net_income': data['net_income'],
                'market_share_summary': share_summary,
            },
        )

    print(f"Round 0 bootstrap complete for {len(teams)} teams.")
    for data in leaderboard_data:
        team = data['team']
        print(f"  {team.name}: Revenue=${float(data['revenue']):,.0f}, "
              f"Net Income=${float(data['net_income']):,.0f}, "
              f"Index={float(data['index']):.2f}")
