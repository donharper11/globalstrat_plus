"""
CC-15: New Feature Page Views.

Endpoints for Industry News, Research Queries list, Strategy Tools CRUD,
Financial Reports history, and Company Forecast.
"""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, Round
from core.models.scenario import (
    MarketDefinition, MarketConditionByRound,
    EntryModeDefinition,
)
from core.models.results import EventInstance
from core.models.results_financials import (
    RoundResultFinancials, RoundResultMarketRevenue,
    RoundResultProductMarket, MarketIntelligenceBrief,
)
from core.models.rag import ResearchQueryLog
from core.models.decisions import (
    DecisionSubmission, DecisionMarketing, DecisionRDInvestment,
    DecisionBudgetAllocation, DecisionFinancing,
    DecisionMarketEntry, DecisionResearchAllocation,
)
from core.models.cc15_models import TeamFrameworkAnalysis, ForecastScenario
from core.utils.localization import get_localized_field, get_user_language


def _dec(v):
    if v is None:
        return 0
    return float(v)


# ---------------------------------------------------------------------------
# 1. Industry News & Market Report
# ---------------------------------------------------------------------------

class IndustryNewsView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/news/round/{round_number}/"""

    def get(self, request, game_id, team_id, round_number):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        # Market outlooks
        scenario = game.scenario
        markets = MarketDefinition.objects.filter(scenario=scenario).order_by('display_order')
        market_outlooks = []
        for mkt in markets:
            cond = MarketConditionByRound.objects.filter(
                market=mkt, round_number=round_number,
            ).first()
            fx_rate = _dec(float(mkt.exchange_rate_base) * (1 + float(cond.exchange_rate_modifier)) if cond else mkt.exchange_rate_base)
            # Previous round FX for comparison
            prev_cond = MarketConditionByRound.objects.filter(
                market=mkt, round_number=round_number - 1,
            ).first() if round_number > 0 else None
            prev_fx = _dec(float(mkt.exchange_rate_base) * (1 + float(prev_cond.exchange_rate_modifier)) if prev_cond else mkt.exchange_rate_base)
            fx_change_pct = ((fx_rate - prev_fx) / max(prev_fx, 0.001)) if prev_fx else 0

            market_outlooks.append({
                'market': get_localized_field(mkt, 'name', language),
                'market_code': mkt.code,
                'currency_code': mkt.currency_code,
                'narrative': cond.market_outlook_narrative if cond else '',
                'growth_rate': _dec(mkt.base_growth_rate + (cond.growth_rate_modifier if cond else 0)),
                'exchange_rate': round(fx_rate, 4),
                'exchange_rate_change_pct': round(fx_change_pct, 4),
                'tariff_rate': _dec(mkt.tariff_rate + (cond.tariff_rate_modifier if cond else 0)),
            })

        # Events
        events_qs = EventInstance.objects.filter(
            game=game, round_number=round_number,
        ).select_related('event_template', 'target_market')
        events = []
        for ev in events_qs:
            tmpl = ev.event_template
            events.append({
                'name': get_localized_field(tmpl, 'name', language),
                'narrative': ev.narrative or get_localized_field(tmpl, 'description_template', language),
                'category': tmpl.category,
                'severity': tmpl.severity,
                'market': get_localized_field(ev.target_market, 'name', language) if ev.target_market else 'Global',
            })

        # Intelligence briefs (global + team-specific)
        briefs_qs = MarketIntelligenceBrief.objects.filter(
            game=game, round_number=round_number,
        ).filter(
            # Global briefs (team=null) or team-specific
            **{}
        ).select_related('market')
        # Filter: team is null (global) or team matches
        from django.db.models import Q
        briefs_qs = MarketIntelligenceBrief.objects.filter(
            game=game, round_number=round_number,
        ).filter(
            Q(team__isnull=True) | Q(team=team)
        ).select_related('market')

        intelligence_briefs = []
        for b in briefs_qs:
            intelligence_briefs.append({
                'market': get_localized_field(b.market, 'name', language),
                'level': b.brief_level,
                'content': b.brief_content,
            })

        headline = f"Round {round_number} Market Report"
        home_currency = team.home_market.currency_code if team.home_market else 'USD'

        return Response({
            'round_number': round_number,
            'headline': headline,
            'home_currency_code': home_currency,
            'market_outlooks': market_outlooks,
            'events': events,
            'intelligence_briefs': intelligence_briefs,
        })


# ---------------------------------------------------------------------------
# 2. Research Queries List
# ---------------------------------------------------------------------------

class ResearchQueriesListView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/research/queries/"""

    def get(self, request, game_id, team_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        round_number = request.query_params.get('round_number', game.current_round)

        queries = ResearchQueryLog.objects.filter(
            team=team, round_number=round_number,
        ).order_by('-queried_at')

        data = [{
            'query_text': q.query_text,
            'response_text': q.response_text,
            'queried_at': q.queried_at.isoformat(),
        } for q in queries]

        return Response({
            'round_number': int(round_number),
            'queries': data,
            'query_count': len(data),
        })


# ---------------------------------------------------------------------------
# 3. Strategy Tools — Framework Analysis CRUD
# ---------------------------------------------------------------------------

class FrameworkAnalysisView(APIView):
    """
    GET  /api/games/{game_id}/teams/{team_id}/tools/analysis/ — list analyses
    POST /api/games/{game_id}/teams/{team_id}/tools/analysis/ — save analysis
    """

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        framework = request.query_params.get('framework')
        market_code = request.query_params.get('market')

        qs = TeamFrameworkAnalysis.objects.filter(team=team).order_by('-updated_at')
        if framework:
            qs = qs.filter(framework_type=framework)
        if market_code:
            qs = qs.filter(market__code=market_code)

        data = []
        for a in qs:
            data.append({
                'id': a.id,
                'round_number': a.round_number,
                'framework_type': a.framework_type,
                'market': a.market.code if a.market else None,
                'market_name': get_localized_field(a.market, 'name', language) if a.market else None,
                'analysis_data': a.analysis_data,
                'updated_at': a.updated_at.isoformat(),
            })

        return Response({'analyses': data})

    def post(self, request, game_id, team_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        framework_type = request.data.get('framework_type')
        market_code = request.data.get('market')
        analysis_data = request.data.get('analysis_data', {})
        round_number = request.data.get('round_number', game.current_round)

        if not framework_type:
            return Response(
                {'error': 'framework_type is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        market = None
        if market_code:
            market = MarketDefinition.objects.filter(
                scenario=game.scenario, code=market_code,
            ).first()

        # Upsert: update if same framework+market+round exists
        existing = TeamFrameworkAnalysis.objects.filter(
            team=team, round_number=round_number,
            framework_type=framework_type, market=market,
        ).first()

        if existing:
            existing.analysis_data = analysis_data
            existing.save(update_fields=['analysis_data', 'updated_at'])
            obj = existing
        else:
            obj = TeamFrameworkAnalysis.objects.create(
                team=team,
                round_number=round_number,
                framework_type=framework_type,
                market=market,
                analysis_data=analysis_data,
            )

        return Response({
            'id': obj.id,
            'message': 'Analysis saved.',
        }, status=status.HTTP_201_CREATED)


class FrameworkAnalysisHistoryView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/tools/analysis/history/"""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        qs = TeamFrameworkAnalysis.objects.filter(team=team).order_by('-updated_at')
        data = []
        for a in qs:
            data.append({
                'id': a.id,
                'round_number': a.round_number,
                'framework_type': a.framework_type,
                'market': a.market.code if a.market else None,
                'market_name': get_localized_field(a.market, 'name', language) if a.market else None,
                'analysis_data': a.analysis_data,
                'updated_at': a.updated_at.isoformat(),
            })

        return Response({'analyses': data})


class EntryMatrixDataView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/tools/entry-matrix-data/
    Pre-populate entry matrix with scenario data."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        scenario = game.scenario

        markets = MarketDefinition.objects.filter(scenario=scenario).order_by('display_order')
        entry_modes = EntryModeDefinition.objects.filter(scenario=scenario)

        market_data = [{
            'code': m.code,
            'name': get_localized_field(m, 'name', language),
            'tariff_rate': _dec(m.tariff_rate),
            'regulatory_difficulty': _dec(m.regulatory_difficulty),
            'entry_cost_base': _dec(m.entry_cost_base),
            'base_growth_rate': _dec(m.base_growth_rate),
        } for m in markets]

        mode_data = [{
            'code': em.code,
            'name': get_localized_field(em, 'name', language),
            'capital_requirement': _dec(em.capital_requirement),
            'setup_rounds': em.setup_rounds,
            'control_level': _dec(em.control_level),
            'risk_level': _dec(em.risk_level),
            'tariff_applies': em.tariff_applies,
        } for em in entry_modes]

        return Response({
            'markets': market_data,
            'entry_modes': mode_data,
        })


# ---------------------------------------------------------------------------
# 4. Financial Reports History
# ---------------------------------------------------------------------------

class FinancialReportsHistoryView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/financial-reports/history/"""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        financials = RoundResultFinancials.objects.filter(
            game=game, team=team,
        ).order_by('round_number')

        rounds = []
        for fin in financials:
            # Per-market revenue for this round
            market_revenues = RoundResultMarketRevenue.objects.filter(
                game=game, team=team, round_number=fin.round_number,
            ).select_related('market')

            markets = []
            for mr in market_revenues:
                mkt = mr.market
                cond = MarketConditionByRound.objects.filter(
                    market=mkt, round_number=fin.round_number,
                ).first()
                fx_rate = _dec(mkt.exchange_rate_base) + (_dec(cond.exchange_rate_modifier) if cond else 0)
                # Get previous round FX for comparison
                prev_cond = MarketConditionByRound.objects.filter(
                    market=mkt, round_number=fin.round_number - 1,
                ).first() if fin.round_number > 0 else None
                prev_fx = _dec(mkt.exchange_rate_base) + (_dec(prev_cond.exchange_rate_modifier) if prev_cond else 0)
                fx_change_pct = ((fx_rate - prev_fx) / max(prev_fx, 0.001)) if prev_fx else 0
                tariff = _dec(mkt.tariff_rate) + (_dec(cond.tariff_rate_modifier) if cond else 0)

                markets.append({
                    'market_code': mkt.code,
                    'market_name': get_localized_field(mkt, 'name', language),
                    'home_revenue': _dec(mr.home_revenue),
                    'market_profit': _dec(mr.market_profit),
                    'market_share_pct': _dec(mr.market_share_pct),
                    'currency_code': mkt.currency_code,
                    'exchange_rate': round(fx_rate, 4),
                    'exchange_rate_change_pct': round(fx_change_pct, 4),
                    'tariff_rate': round(tariff, 4),
                })

            # Product-level data (CC-20: inventory visibility)
            prod_results = RoundResultProductMarket.objects.filter(
                game=game, team=team, round_number=fin.round_number,
            ).select_related('team_product', 'market')
            products = []
            for pr in prod_results:
                units_sold = _dec(pr.units_sold)
                units_produced = pr.units_produced or 0
                units_unsold = _dec(pr.units_unsold)
                unit_cost = _dec(pr.unit_cost)
                revenue = _dec(pr.home_revenue)
                total_cogs_prod = _dec(pr.total_cogs)
                gross_margin = revenue - total_cogs_prod if revenue else 0
                gross_margin_pct_prod = gross_margin / revenue if revenue > 0 else 0
                inv_turnover = units_sold / max(units_unsold, 1) if units_unsold > 0 else (
                    float('inf') if units_sold > 0 else 0
                )
                products.append({
                    'product_name': pr.team_product.name,
                    'positioning': pr.team_product.positioning,
                    'market_name': get_localized_field(pr.market, 'name', language),
                    'market_code': pr.market.code,
                    'units_produced': units_produced,
                    'units_sold': units_sold,
                    'units_unsold': units_unsold,
                    'retail_price': _dec(pr.retail_price),
                    'revenue': revenue,
                    'unit_cost': unit_cost,
                    'total_cogs': total_cogs_prod,
                    'gross_margin': gross_margin,
                    'gross_margin_pct': gross_margin_pct_prod,
                    'inventory_holding_cost': _dec(pr.inventory_holding_cost),
                    'inventory_value': units_unsold * unit_cost,
                    'inventory_turnover': round(inv_turnover, 1) if inv_turnover != float('inf') else None,
                    'logistics_cost': _dec(pr.logistics_cost),
                    'tariff_cost': _dec(pr.tariff_cost),
                })

            rounds.append({
                'round_number': fin.round_number,
                # Income statement
                'total_revenue': _dec(fin.total_revenue),
                'total_cogs': _dec(fin.total_cogs),
                'gross_profit': _dec(fin.gross_profit),
                'gross_margin_pct': _dec(fin.gross_margin_pct),
                'rd_expense': _dec(fin.rd_expense),
                'marketing_expense': _dec(fin.marketing_expense),
                'strategy_expense': _dec(fin.strategy_expense),
                'admin_overhead': _dec(fin.admin_overhead),
                'logistics_tariff_expense': _dec(fin.logistics_tariff_expense),
                'inventory_expense': _dec(fin.inventory_expense),
                'operating_income': _dec(fin.operating_income),
                'interest_expense': _dec(fin.interest_expense),
                'pre_tax_income': _dec(fin.pre_tax_income),
                'tax_expense': _dec(fin.tax_expense),
                'net_income': _dec(fin.net_income),
                'net_margin_pct': _dec(fin.net_margin_pct),
                # Balance sheet
                'cash_opening': _dec(fin.cash_opening),
                'cash_closing': _dec(fin.cash_closing),
                'total_assets': _dec(fin.total_assets),
                'total_debt': _dec(fin.total_debt),
                'total_equity': _dec(fin.total_equity),
                'plant_book_value': _dec(fin.plant_book_value),
                'inventory_value': _dec(fin.inventory_value),
                # Cash flow
                'operating_cash_flow': _dec(fin.operating_cash_flow),
                'investing_cash_flow': _dec(fin.investing_cash_flow),
                'financing_cash_flow': _dec(fin.financing_cash_flow),
                'dividends_paid': _dec(fin.dividends_paid),
                # Ratios
                'share_price': _dec(fin.share_price),
                'roe': _dec(fin.roe),
                'debt_to_equity': _dec(fin.debt_to_equity),
                'shareholder_return_cumulative': _dec(fin.shareholder_return_cumulative),
                # Markets
                'markets': markets,
                # Products (CC-20)
                'products': products,
            })

        return Response({'rounds': rounds})


# ---------------------------------------------------------------------------
# 5. Company Forecast
# ---------------------------------------------------------------------------

class ForecastView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/forecast/
    Simplified projection based on current draft decisions."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        current_round = game.current_round
        rnd = Round.objects.filter(game=game, round_number=current_round).first()
        if not rnd:
            return Response({'message': 'No round found.'})

        submission = DecisionSubmission.objects.filter(
            team=team, round=rnd,
        ).first()

        if not submission:
            return Response({'message': 'No draft decisions yet.', 'has_draft': False})

        # Revenue projection from marketing decisions
        revenue_lines = []
        total_revenue = Decimal('0')
        total_cogs_est = Decimal('0')
        total_marketing_cost = Decimal('0')

        for mktg in DecisionMarketing.objects.filter(submission=submission).select_related('team_product', 'market'):
            units = mktg.demand_estimate
            price = mktg.retail_price
            line_revenue = Decimal(str(units)) * price
            promo = mktg.promotion_budget
            distrib = mktg.distribution_investment

            # Get FX rate for this market
            mkt = mktg.market
            cond = MarketCondition.objects.filter(market=mkt, round=rnd).first()
            fx_rate = _dec(mkt.exchange_rate_base) + (_dec(cond.exchange_rate_modifier) if cond else 0)

            revenue_lines.append({
                'product': mktg.team_product.name,
                'market': get_localized_field(mktg.market, 'name', language),
                'market_code': mktg.market.code,
                'currency_code': mkt.currency_code,
                'exchange_rate': round(float(fx_rate), 4),
                'price': float(price),
                'units': units,
                'revenue': float(line_revenue),
                'promotion_budget': float(promo),
                'distribution_investment': float(distrib),
            })
            total_revenue += line_revenue
            total_marketing_cost += promo + distrib
            # Rough COGS estimate: use 17.5% of revenue as placeholder
            total_cogs_est += line_revenue * Decimal('0.175')

        # R&D costs
        rd_cost = Decimal('0')
        for d in DecisionRDInvestment.objects.filter(submission=submission):
            rd_cost += d.amount

        # Strategy/research costs from budget allocation
        budget = DecisionBudgetAllocation.objects.filter(submission=submission).first()
        strategy_cost = Decimal(str(budget.strategy_budget)) if budget else Decimal('0')

        # Financing
        financing = DecisionFinancing.objects.filter(submission=submission).first()
        new_debt = Decimal(str(financing.new_debt)) if financing else Decimal('0')
        debt_repayment = Decimal(str(financing.debt_repayment)) if financing else Decimal('0')
        new_equity = Decimal(str(financing.new_equity)) if financing else Decimal('0')

        # Market entries
        entry_costs = Decimal('0')
        for entry in DecisionMarketEntry.objects.filter(submission=submission):
            entry_costs += entry.initial_investment

        # Compute projections
        admin_overhead = total_revenue * Decimal('0.025')  # ~2.5% admin
        interest_est = Decimal(str(_dec(team.total_debt))) * Decimal('0.06')  # ~6% interest
        total_costs = total_cogs_est + rd_cost + total_marketing_cost + strategy_cost + admin_overhead + entry_costs
        operating_income = total_revenue - total_costs
        pre_tax = operating_income - interest_est
        tax = max(pre_tax * Decimal('0.21'), Decimal('0'))
        net_income = pre_tax - tax

        projected_cash = (
            Decimal(str(_dec(team.cash_on_hand)))
            + total_revenue - total_costs - interest_est - tax
            + new_debt - debt_repayment + new_equity
        )

        return Response({
            'has_draft': True,
            'revenue_lines': revenue_lines,
            'total_revenue': float(total_revenue),
            'costs': {
                'cogs': float(total_cogs_est),
                'rd': float(rd_cost),
                'marketing': float(total_marketing_cost),
                'strategy': float(strategy_cost),
                'admin': float(admin_overhead),
                'entry_costs': float(entry_costs),
                'interest': float(interest_est),
                'tax': float(tax),
            },
            'gross_profit': float(total_revenue - total_cogs_est),
            'operating_income': float(operating_income),
            'projected_net_income': float(net_income),
            'projected_cash': float(projected_cash),
            'current_cash': float(team.cash_on_hand),
        })


class ForecastScenarioView(APIView):
    """
    GET  /api/games/{game_id}/teams/{team_id}/forecast/scenarios/ — list scenarios
    POST /api/games/{game_id}/teams/{team_id}/forecast/scenarios/ — save scenario
    """

    def get(self, request, game_id, team_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        round_number = request.query_params.get('round_number', game.current_round)
        scenarios = ForecastScenario.objects.filter(
            team=team, round_number=round_number,
        ).order_by('-created_at')

        data = [{
            'id': s.id,
            'name': s.name,
            'parameters': s.parameters,
            'projected_results': s.projected_results,
            'created_at': s.created_at.isoformat(),
        } for s in scenarios]

        return Response({'scenarios': data})

    def post(self, request, game_id, team_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        name = request.data.get('name', 'Unnamed Scenario')
        parameters = request.data.get('parameters', {})
        projected_results = request.data.get('projected_results', {})

        scenario = ForecastScenario.objects.create(
            team=team,
            round_number=game.current_round,
            name=name,
            parameters=parameters,
            projected_results=projected_results,
        )

        return Response({
            'id': scenario.id,
            'message': 'Scenario saved.',
        }, status=status.HTTP_201_CREATED)
