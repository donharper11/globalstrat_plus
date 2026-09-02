"""
CC-10: Results API Views.

Read-only endpoints for round results, leaderboard, competitor intel,
and instructor dashboard/actions.
"""
import logging
from decimal import Decimal

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, TeamMember, Round, User
from core.models.results import EventInstance, ActiveModifier, RoundResultAdoption
from core.models.results_financials import (
    RoundResultProductMarket, RoundResultFinancials,
    RoundResultMarketRevenue, RoundResultPerformanceIndex,
    RoundResultCoherence, LeaderboardEntry, MarketIntelligenceBrief,
)
from core.models.team_state import (
    TeamProduct, TeamProductMarket, TeamMarketPresence,
    TeamStrategyFeatureLevel,
)
from core.models.scenario import MarketDefinition, EventTemplateDefinition
from core.models.decisions import DecisionSubmission
from core.models.cc26_models import SharePriceHistory
from core.permissions import IsInstructor
from core.services.lifecycle import (
    LifecycleConflict, LifecyclePrecondition, lifecycle_view, operator_action)
from core.utils.localization import get_localized_field, get_user_language

logger = logging.getLogger(__name__)


def _dec(v):
    """Convert Decimal to float for JSON."""
    if v is None:
        return 0
    return float(v)


# Human-readable labels for each submission origin, for instructor UI/disputes.
SUBMISSION_ORIGIN_LABELS = {
    'no_submission': 'No submission',
    'draft': 'Draft (not locked)',
    'student_locked': 'Locked by team',
    'deadline_locked': 'Auto-locked at deadline',
    'defaulted_missing': 'Never submitted — defaulted at close',
}


def classify_submission_origin(game, team, rnd, submission):
    """Classify how a submission reached its current state, for dispute clarity.

    Distinguishes a team that never submitted (its submission exists only because
    close auto-created an empty default) from one that produced a draft which was
    then locked — a distinction the raw ``status`` field ('locked') hides. Derived
    from the immutable DecisionAuditEvent log so instructors need no database
    access to answer "did this team actually submit?".
    """
    if submission is None:
        return 'no_submission'
    from core.models import DecisionAuditEvent
    close_events = DecisionAuditEvent.objects.filter(
        game=game, team=team, round=rnd, endpoint='engine:close_round')
    # "Ever defaulted" is robust to a reopen+reclose cycle: once a team has been
    # defaulted for a round, the record only exists because it never submitted.
    if close_events.filter(action='missing_submission_defaulted').exists():
        return 'defaulted_missing'
    if submission.status != 'locked':
        return 'draft'
    if close_events.filter(action='deadline_lock').exists():
        return 'deadline_locked'
    return 'student_locked'


# ---------------------------------------------------------------------------
# 1a. Round Results
# ---------------------------------------------------------------------------

class RoundResultsView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/results/round/{round_number}/"""

    def get(self, request, game_id, team_id, round_number):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        # Performance index
        perf = RoundResultPerformanceIndex.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()
        prev_perf = RoundResultPerformanceIndex.objects.filter(
            game=game, team=team, round_number=round_number - 1,
        ).first()

        performance = {
            'index_value': _dec(perf.index_value) if perf else _dec(team.performance_index),
            'index_change': _dec(perf.index_change) if perf else 0,
            'satisfaction_score': _dec(perf.satisfaction_score) if perf else 0,
            'previous_index': _dec(prev_perf.index_value) if prev_perf else _dec(team.performance_index),
        }

        # Financials
        fin = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()
        financials = {}
        if fin:
            financials = {
                'total_revenue': _dec(fin.total_revenue),
                'total_cogs': _dec(fin.total_cogs),
                'gross_profit': _dec(fin.gross_profit),
                'gross_margin_pct': _dec(fin.gross_margin_pct),
                'operating_income': _dec(fin.operating_income),
                'net_income': _dec(fin.net_income),
                'cash_opening': _dec(fin.cash_opening),
                'cash_closing': _dec(fin.cash_closing),
                'total_debt': _dec(fin.total_debt),
                'total_equity': _dec(fin.total_equity),
                'roe': _dec(fin.roe),
                'debt_to_equity': _dec(fin.debt_to_equity),
                'shareholder_return_cumulative': _dec(fin.shareholder_return_cumulative),
                'rd_expense': _dec(fin.rd_expense),
                # A team's own results only. The competitor block below
                # deliberately does not carry it: when a rival re-based, and
                # what it cost them, is not public information.
                'platform_switch_write_off': _dec(fin.platform_switch_write_off),
                'marketing_expense': _dec(fin.marketing_expense),
                'strategy_expense': _dec(fin.strategy_expense),
                'interest_expense': _dec(fin.interest_expense),
                'tax_expense': _dec(fin.tax_expense),
                'logistics_tariff_expense': _dec(fin.logistics_tariff_expense),
                'inventory_expense': _dec(fin.inventory_expense),
            }

        # Market results
        market_revenues = RoundResultMarketRevenue.objects.filter(
            game=game, team=team, round_number=round_number,
        ).select_related('market')

        markets = []
        for mr in market_revenues:
            mkt = mr.market
            # Adoption data for this market
            adoptions = RoundResultAdoption.objects.filter(
                game=game, team=team, round_number=round_number, market=mkt,
            ).select_related('segment', 'best_product')

            customer_segs = []
            non_customer_segs = []
            for a in adoptions:
                seg_data = {
                    'segment_name': get_localized_field(a.segment, 'name', language),
                    'segment_type': a.segment.segment_type,
                    'fit_score': _dec(a.fit_score),
                    'adjusted_fit_score': _dec(a.adjusted_fit_score),
                }
                if a.segment.segment_type == 'customer':
                    seg_data.update({
                        'new_adopters': _dec(a.new_adopters),
                        'cumulative_adopters': _dec(a.cumulative_adopters),
                        'team_share_pct': _dec(a.team_share_pct),
                        'best_product': a.best_product.name if a.best_product else None,
                    })
                    customer_segs.append(seg_data)
                else:
                    non_customer_segs.append(seg_data)

            markets.append({
                'market_code': mkt.code,
                'market_name': get_localized_field(mkt, 'name', language),
                'local_revenue': _dec(mr.local_revenue),
                'home_revenue': _dec(mr.home_revenue),
                'market_profit': _dec(mr.market_profit),
                'market_share_pct': _dec(mr.market_share_pct),
                'segments': customer_segs,
                'non_customer_segments': non_customer_segs,
            })

        # Product results
        prod_results = RoundResultProductMarket.objects.filter(
            game=game, team=team, round_number=round_number,
        ).select_related('team_product', 'market')
        products = []
        for pr in prod_results:
            products.append({
                'product_name': pr.team_product.name,
                'market': get_localized_field(pr.market, 'name', language),
                'units_produced': pr.units_produced,
                'units_sold': _dec(pr.units_sold),
                'units_unsold': _dec(pr.units_unsold),
                'retail_price': _dec(pr.retail_price),
                'home_revenue': _dec(pr.home_revenue),
                'unit_cost': _dec(pr.unit_cost),
                'total_cogs': _dec(pr.total_cogs),
                'logistics_cost': _dec(pr.logistics_cost),
                'tariff_cost': _dec(pr.tariff_cost),
                'inventory_holding_cost': _dec(pr.inventory_holding_cost),
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
                'response_required': tmpl.response_required if hasattr(tmpl, 'response_required') else False,
                'team_response': None,
            })

        # Coherence
        coh = RoundResultCoherence.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()
        coherence = {}
        if coh:
            coherence = {
                'formula_score': _dec(coh.formula_score),
                'blended_score': _dec(coh.blended_score),
                'breakdown': coh.breakdown or {},
            }

        # Strategy feature levels (includes ESG)
        strategy_features = []
        for sfl in TeamStrategyFeatureLevel.objects.filter(
            team=team, round_number=round_number,
        ).select_related('feature'):
            strategy_features.append({
                'feature_code': sfl.feature.code,
                'feature_name': get_localized_field(sfl.feature, 'name', language),
                'level': _dec(sfl.current_level),
                'max_level': _dec(sfl.feature.max_value),
            })

        return Response({
            'round_number': round_number,
            'performance': performance,
            'financials': financials,
            'markets': markets,
            'products': products,
            'events': events,
            'coherence': coherence,
            'strategy_features': strategy_features,
        })


# ---------------------------------------------------------------------------
# 1b. Leaderboard
# ---------------------------------------------------------------------------

class LeaderboardView(APIView):
    """GET /api/games/{game_id}/leaderboard/round/{round_number}/"""

    def get(self, request, game_id, round_number):
        game = get_object_or_404(Game, id=game_id)
        entries = LeaderboardEntry.objects.filter(
            game=game, round_number=round_number,
        ).select_related('team').order_by('rank')

        rankings = []
        for e in entries:
            # Get index change from performance table
            perf = RoundResultPerformanceIndex.objects.filter(
                game=game, team=e.team, round_number=round_number,
            ).first()

            # Get share price data from SharePriceHistory
            sph = SharePriceHistory.objects.filter(
                game=game, team=e.team, round_number=round_number,
            ).first()
            share_price = _dec(sph.share_price) if sph else None
            investor_confidence = None
            if sph:
                investor_confidence = _dec(sph.aggregate_demand)

            entry = {
                'rank': e.rank,
                'team_name': e.team.name,
                'team_id': e.team.id,
                'performance_index': _dec(e.performance_index),
                'index_change': _dec(perf.index_change) if perf else 0,
                'total_revenue': _dec(e.total_revenue),
                'net_income': _dec(e.net_income),
                'shareholder_return': _dec(e.shareholder_return),
                'market_share': e.market_share_summary or {},
                'share_price': share_price,
                'investor_confidence': investor_confidence,
            }
            rankings.append(entry)

        return Response({
            'round_number': round_number,
            'rankings': rankings,
        })


# ---------------------------------------------------------------------------
# 1c. Leaderboard History
# ---------------------------------------------------------------------------

class LeaderboardHistoryView(APIView):
    """GET /api/games/{game_id}/leaderboard/history/"""

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        teams = Team.objects.filter(game=game).order_by('id')

        # Get all performance index records
        all_perf = RoundResultPerformanceIndex.objects.filter(
            game=game,
        ).order_by('round_number')

        all_fin = RoundResultFinancials.objects.filter(
            game=game,
        ).order_by('round_number')

        # Build round list
        rounds_set = set()
        rounds_set.add(0)  # Starting round
        for p in all_perf:
            rounds_set.add(p.round_number)
        rounds = sorted(rounds_set)

        team_data = []
        for t in teams:
            index_history = [_dec(t.performance_index)]  # Round 0 = starting index
            revenue_history = [0]  # Round 0 = no revenue
            share_price_history = [50.0]  # Default starting share price

            for rnd in rounds:
                if rnd == 0:
                    continue
                perf = all_perf.filter(team=t, round_number=rnd).first()
                fin = all_fin.filter(team=t, round_number=rnd).first()
                index_history.append(_dec(perf.index_value) if perf else index_history[-1])
                revenue_history.append(_dec(fin.total_revenue) if fin else 0)
                share_price_history.append(_dec(fin.share_price) if fin else share_price_history[-1])

            team_data.append({
                'team_id': t.id,
                'team_name': t.name,
                'index_history': index_history,
                'revenue_history': revenue_history,
                'share_price_history': share_price_history,
            })

        return Response({
            'rounds': rounds,
            'teams': team_data,
        })


# ---------------------------------------------------------------------------
# 1d. Competitor Intelligence
# ---------------------------------------------------------------------------

class CompetitorIntelView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/competitors/round/{round_number}/"""

    def get(self, request, game_id, team_id, round_number):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        other_teams = Team.objects.filter(game=game).exclude(id=team_id)
        competitors = []

        for ot in other_teams:
            # Market presence
            presences = TeamMarketPresence.objects.filter(
                team=ot, status='active',
            ).select_related('market')
            markets_present = [get_localized_field(p.market, 'name', language) for p in presences]

            # Market share
            rev_results = RoundResultMarketRevenue.objects.filter(
                game=game, team=ot, round_number=round_number,
            ).select_related('market')
            approx_share = {get_localized_field(r.market, 'name', language): _dec(r.market_share_pct) for r in rev_results}

            # Products
            products = TeamProduct.objects.filter(team=ot, status='active')
            product_count = products.count()
            positioning_set = set(products.values_list('positioning', flat=True))

            # Approximate price ranges per market
            prod_mkts = RoundResultProductMarket.objects.filter(
                game=game, team=ot, round_number=round_number,
            ).select_related('market')
            price_ranges = {}
            for pm in prod_mkts:
                mkt_name = get_localized_field(pm.market, 'name', language)
                price = _dec(pm.retail_price)
                if mkt_name not in price_ranges:
                    price_ranges[mkt_name] = [price, price]
                else:
                    price_ranges[mkt_name][0] = min(price_ranges[mkt_name][0], price)
                    price_ranges[mkt_name][1] = max(price_ranges[mkt_name][1], price)

            approx_prices = {
                k: f"{int(v[0])}-{int(v[1])}" for k, v in price_ranges.items()
            }

            competitors.append({
                'team_name': ot.name,
                'markets_present': markets_present,
                'approximate_market_share': approx_share,
                'product_count': product_count,
                'positioning_observed': list(positioning_set),
                'approximate_price_range': approx_prices,
                'recent_moves': [],  # Could be built from decision history
            })

        # AI competitors with behavior hints (CC-20)
        from core.models.scenario import AICompetitorDefinition, AICompetitorBehavior
        ai_comps = AICompetitorDefinition.objects.filter(
            scenario=game.scenario,
        )
        all_market_objs = MarketDefinition.objects.filter(scenario=game.scenario)
        all_markets = [get_localized_field(m, 'name', language) for m in all_market_objs]
        ai_competitors = []
        for ai in ai_comps:
            behavior = AICompetitorBehavior.objects.filter(ai_competitor=ai).first()
            strategy_label = behavior.get_strategy_type_display() if behavior else 'Unknown'

            # Build behavior hints
            recent_moves = []
            if behavior:
                if behavior.strategy_type == 'aggressive':
                    recent_moves.append('Appears to be expanding aggressively')
                    if float(behavior.price_sensitivity) > 0.5:
                        recent_moves.append('Pricing reportedly competitive — may be undercutting')
                elif behavior.strategy_type == 'defensive':
                    recent_moves.append('Focused on protecting existing market position')
                if float(behavior.innovation_rate) > 0.4:
                    recent_moves.append('Investing heavily in product innovation')

            ai_competitors.append({
                'name': get_localized_field(ai, 'name', language),
                'description': get_localized_field(ai, 'description', language),
                'markets_present': all_markets,
                'strategy_hint': strategy_label,
                'recent_moves': recent_moves,
            })

        # === Market Report: products with features and segment positions ===
        from core.models.team_state import TeamPlatformFeatureLevel
        all_teams = Team.objects.filter(game=game)
        market_report = []
        for t in all_teams:
            t_products = TeamProduct.objects.filter(team=t, status='active').select_related('team_platform')
            for prod in t_products:
                # Get feature levels
                features = {}
                if prod.team_platform:
                    for fl in TeamPlatformFeatureLevel.objects.filter(
                        team_platform=prod.team_platform,
                    ).select_related('feature'):
                        features[get_localized_field(fl.feature, 'name', language)] = float(fl.current_level)

                # Get price and market data
                prod_markets = RoundResultProductMarket.objects.filter(
                    game=game, team=t, team_product=prod, round_number=round_number,
                ).select_related('market')
                for pm in prod_markets:
                    # Find best segment position for this product
                    segment_positions = []
                    adoptions = RoundResultAdoption.objects.filter(
                        game=game, team=t, round_number=round_number,
                        best_product=prod, market=pm.market,
                    ).select_related('segment')
                    for a in adoptions:
                        if a.segment.segment_type == 'customer':
                            segment_positions.append({
                                'segment': get_localized_field(a.segment, 'name', language),
                                'fit_score': _dec(a.adjusted_fit_score),
                                'share_pct': _dec(a.team_share_pct),
                            })

                    market_report.append({
                        'team_name': t.name,
                        'is_own_team': t.id == team.id,
                        'product_name': prod.name,
                        'positioning': prod.positioning,
                        'market': pm.market.code,
                        'price': _dec(pm.retail_price),
                        'units_sold': _dec(pm.units_sold),
                        'features': features,
                        'segment_positions': segment_positions,
                    })

        # === Financial Performance summary per team ===
        financial_summary = []
        for t in all_teams:
            t_fin = RoundResultFinancials.objects.filter(
                game=game, team=t, round_number=round_number,
            ).first()
            t_perf = RoundResultPerformanceIndex.objects.filter(
                game=game, team=t, round_number=round_number,
            ).first()
            if t_fin:
                financial_summary.append({
                    'team_name': t.name,
                    'is_own_team': t.id == team.id,
                    'revenue': _dec(t_fin.total_revenue),
                    'net_income': _dec(t_fin.net_income),
                    'gross_margin_pct': _dec(t_fin.gross_margin_pct),
                    'net_margin_pct': _dec(t_fin.net_margin_pct),
                    'cash': _dec(t_fin.cash_closing),
                    'debt_to_equity': _dec(t_fin.debt_to_equity),
                    'share_price': _dec(t_fin.share_price),
                    'performance_index': _dec(t_perf.index_value) if t_perf else 0,
                    'rd_expense': _dec(t_fin.rd_expense),
                    'marketing_expense': _dec(t_fin.marketing_expense),
                })

        return Response({
            'competitors': competitors,
            'ai_competitors': ai_competitors,
            'market_report': market_report,
            'financial_summary': financial_summary,
        })


# ---------------------------------------------------------------------------
# 1e. Instructor Endpoints
# ---------------------------------------------------------------------------

class InstructorSessionReadinessView(APIView):
    """GET /api/games/{game_id}/instructor/session-readiness/

    Who is signed in, as distinct from who is on the roster. The dashboard
    answers roster membership; opening a round needs authenticated sessions,
    and CRV2-07 recorded a readiness claim built from an enrollment count,
    which is why the two are separately named here.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        from core.permissions import instructor_can_access_game
        from core.services.session_readiness import readiness
        game = get_object_or_404(Game, id=game_id)
        # IsInstructor checks the role and nothing else, so without this an
        # instructor could read another cohort's participant names, team
        # membership and who is signed in, missing, stale or duplicated, just
        # by changing the game id in the URL. The ownership rule is the one
        # already used elsewhere -- owner of the course behind the game's
        # section, with unowned courses visible to any instructor for the live
        # pilot -- and is deliberately not restated here.
        if not instructor_can_access_game(request, game):
            return Response(
                {'error': 'This game belongs to another instructor.'},
                status=status.HTTP_403_FORBIDDEN)
        teams = request.query_params.get('teams')
        cohort = ([int(t) for t in teams.split(',') if t.strip().isdigit()]
                  if teams else None)
        return Response(readiness(game, cohort))


class InstructorDashboardView(APIView):
    """GET /api/games/{game_id}/instructor/dashboard/"""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        teams = Team.objects.filter(game=game).order_by('id')

        team_data = []
        teams_locked = 0
        teams_pending = 0

        for t in teams:
            # Get team members from Enrollment (the real source of truth)
            from core.models.course import Enrollment
            enrollments = Enrollment.objects.filter(
                team_id=t.id, is_active=True,
            )
            member_info = []
            for enr in enrollments:
                u = User.objects.filter(user_id=enr.user_id).first()
                if u:
                    member_info.append(
                        u.display_name or u.email or u.username
                    )

            # Latest performance
            perf = RoundResultPerformanceIndex.objects.filter(
                game=game, team=t,
            ).order_by('-round_number').first()

            # Latest coherence
            coh = RoundResultCoherence.objects.filter(
                game=game, team=t,
            ).order_by('-round_number').first()

            # Latest financials
            fin = RoundResultFinancials.objects.filter(
                game=game, team=t,
            ).order_by('-round_number').first()

            # Decision status for current round
            current_rnd = Round.objects.filter(
                game=game, round_number=game.current_round,
            ).first()
            dec_sub = None
            if current_rnd:
                dec_sub = DecisionSubmission.objects.filter(
                    team=t, round=current_rnd,
                ).first()
            dec_status = 'empty'
            if dec_sub:
                dec_status = 'locked' if dec_sub.status == 'locked' else 'draft'
                if dec_sub.status == 'locked':
                    teams_locked += 1
                else:
                    teams_pending += 1
            else:
                teams_pending += 1

            # Markets entered
            presences = TeamMarketPresence.objects.filter(
                team=t, status='active',
            ).select_related('market')
            markets_entered = [p.market.code for p in presences]

            team_data.append({
                'team_id': t.id,
                'team_name': t.name,
                'members': member_info,
                'performance_index': _dec(perf.index_value) if perf else _dec(t.performance_index),
                'cash_on_hand': _dec(t.cash_on_hand),
                'is_in_distress': t.is_in_distress,
                'decision_status': dec_status,
                'submission_origin': classify_submission_origin(
                    game, t, current_rnd, dec_sub),
                'coherence_score': _dec(coh.blended_score) if coh else None,
                'total_revenue': _dec(fin.total_revenue) if fin else 0,
                'markets_entered': markets_entered,
            })

        _current_round = Round.objects.filter(
            game=game, round_number=game.current_round,
        ).first()

        # Events this round
        events_qs = EventInstance.objects.filter(
            game=game, round_number=game.current_round,
        ).select_related('event_template', 'target_market')
        language = get_user_language(request)
        events = [{
            'name': get_localized_field(ev.event_template, 'name', language),
            'severity': ev.event_template.severity,
            'market': get_localized_field(ev.target_market, 'name', language) if ev.target_market else 'Global',
        } for ev in events_qs]

        return Response({
            'game_name': game.name,
            'scenario': game.scenario.name if game.scenario else None,
            'current_round': game.current_round,
            'status': game.status,
            'teams': team_data,
            'round_status': {
                'total_teams': teams.count(),
                'teams_locked': teams_locked,
                'teams_pending': teams_pending,
                # Read the deadline off the current Round. This used to read
                # Game.round_deadline, which the round-schedule editor never
                # writes, so the console always showed no deadline.
                'deadline': (_current_round.deadline.isoformat()
                             if _current_round and _current_round.deadline else None),
                'round_state': _current_round.status if _current_round else None,
                'close_reason': (_current_round.close_reason or ''
                                 if _current_round else ''),
                'processing_status': (_current_round.processing_status
                                      if _current_round else None),
            },
            'events_this_round': events,
        })


class InstructorAdvanceRoundView(APIView):
    """POST /api/games/{game_id}/instructor/advance-round/

    The legacy one-step route: process the current round and open the next.
    It passes through the same coordination boundary as the round-control
    endpoints, so mixing the two consoles cannot resolve a round twice.
    """
    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'advance_round_legacy') as action:
            game = action.game
            round_obj = action.require_round()
            before = action.before = {'round_number': round_obj.round_number,
                                      'status': round_obj.status,
                                      'current_round': game.current_round}
            force = bool(request.data.get('force', False))
            reason = ''

            if round_obj.status == 'processed':
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} has already been processed.',
                    guidance='Refresh the console and advance instead.',
                    code='round_already_processed')
                raise error

            if force:
                # Overriding the all-teams-locked check resolves the round with
                # whatever a team had at that moment, so it needs a reason.
                reason = action.require_reason()
            else:
                unlocked = _first_unlocked_team(game, round_obj)
                if unlocked is not None:
                    error = LifecyclePrecondition(
                        f'Team "{unlocked}" has not locked decisions.',
                        guidance='Lock or close the round first, or resend with '
                                 'force=true and a written reason.',
                        code='team_not_locked')
                    raise error

            from core.engine.advance_round import advance_round, RoundNotReadyError
            try:
                advance_round(game.id)
            except RoundNotReadyError as e:
                error = LifecyclePrecondition(str(e), code='round_not_ready')
                raise error
            except ValueError as e:
                error = LifecycleConflict(str(e), code='advance_refused',
                                          guidance='Refresh the console.')
                raise error
            except Exception as e:
                logger.exception('Legacy advance failed for game %s', game_id)
                action.record_fault(f'Round advance failed: {e}',
                                    code='advance_failed')
                return Response(
                    {'error': f'Round advance failed: {e}',
                     'request_id': action.request_id},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            game.refresh_from_db()
            after = {'current_round': game.current_round}
            action.commit(before, after, reason=reason)
            return Response({
                'message': f'Round advanced to {game.current_round}.',
                'current_round': game.current_round,
                'request_id': action.request_id,
            })


def _first_unlocked_team(game, round_obj):
    """The name of the first active team without a locked submission, or None."""
    locked_team_ids = set(DecisionSubmission.objects.filter(
        round=round_obj, status='locked').values_list('team_id', flat=True))
    team = Team.objects.filter(
        game=game, participation_status='active',
    ).exclude(id__in=locked_team_ids).order_by('id').first()
    return team.name if team else None


class InstructorInjectEventView(APIView):
    """POST /api/games/{game_id}/instructor/inject-event/"""
    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'inject_event') as action:
            game = action.game
            round_obj = action.require_round()
            before = action.before = {'round_number': round_obj.round_number,
                                      'status': round_obj.status}

            # An event injected while Phase 1 is running would land on one side
            # or the other of fire_events depending on timing, so the round's
            # inputs would depend on the clock. The boundary makes that
            # impossible; this check makes the refusal explicit.
            if round_obj.status == 'processed':
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} has already been processed; '
                    f'an event injected now would not be part of it.',
                    guidance='Advance to the next round and inject there.',
                    code='round_already_processed')
                raise error

            template_id = request.data.get('event_template_id')
            market_id = request.data.get('target_market_id')
            template = get_object_or_404(EventTemplateDefinition, id=template_id)
            target_market = None
            if market_id:
                target_market = get_object_or_404(MarketDefinition, id=market_id)

            event = EventInstance.objects.create(
                game=game,
                event_template=template,
                round_number=game.current_round,
                target_market=target_market,
                narrative=template.description_template,
            )
            action.commit(before, {
                'event_template': template.name,
                'round_number': game.current_round,
                'target_market': target_market.code if target_market else None,
            })

            return Response({
                'message': f'Event "{template.name}" injected.',
                'event_id': event.id,
                'request_id': action.request_id,
            }, status=status.HTTP_201_CREATED)


class InstructorExtendDeadlineView(APIView):
    """POST /api/games/{game_id}/instructor/extend-deadline/"""
    permission_classes = [IsInstructor]

    @lifecycle_view
    def post(self, request, game_id):
        with operator_action(request, game_id, 'extend_deadline') as action:
            game = action.game
            round_obj = action.require_round()
            before = action.before = {
                'round_number': round_obj.round_number,
                'status': round_obj.status,
                'deadline': round_obj.deadline.isoformat()
                            if round_obj.deadline else None}
            try:
                hours = int(request.data.get('hours', 24))
            except (TypeError, ValueError):
                raise LifecyclePrecondition('hours must be a number.')

            # This route reopens a closed round as a side effect. That is a
            # real state change, so it is refused once results exist and, like
            # every other reopen, it is audited rather than silent.
            if round_obj.status == 'processed':
                error = LifecycleConflict(
                    f'Round {round_obj.round_number} has already been processed; '
                    f'its deadline cannot be extended.',
                    guidance='Advance to the next round and set its deadline there.',
                    code='round_already_processed')
                raise error

            reason = ''
            if round_obj.status == 'closed':
                # Reopening returns students to a round the deadline already
                # ended. Same bar as an explicit reopen.
                reason = action.require_reason()

            base = round_obj.deadline or timezone.now()
            if base < timezone.now():
                # Extending an already-expired deadline should give students the
                # full extension from now, not a window that is already spent.
                base = timezone.now()
            round_obj.deadline = base + timezone.timedelta(hours=hours)

            reopened = False
            unlocked = 0
            fields = ['deadline']
            if round_obj.status == 'closed':
                round_obj.status = 'open'
                round_obj.closed_at = None
                round_obj.close_reason = ''
                round_obj.decisions_locked = False
                round_obj.lock_reason = ''
                fields += ['status', 'closed_at', 'close_reason',
                           'decisions_locked', 'lock_reason']
                reopened = True
                unlocked = DecisionSubmission.objects.filter(
                    round=round_obj, team__in=Team.objects.filter(game=game),
                    status='locked',
                ).update(status='draft', locked_at=None)

            round_obj.save(update_fields=fields)
            action.commit(before, {
                'status': round_obj.status,
                'deadline': round_obj.deadline.isoformat(),
                'reopened': reopened, 'submissions_unlocked': unlocked,
            }, reason=reason)

            msg = f'Deadline extended by {hours} hour(s).'
            if reopened:
                msg += (' The round was closed, so it has been reopened and '
                        f'{unlocked} submission(s) unlocked.')

            return Response({
                'message': msg,
                'reopened': reopened,
                'new_deadline': round_obj.deadline.isoformat(),
                'request_id': action.request_id,
            })


class InstructorResearchQueriesView(APIView):
    """GET /api/games/{game_id}/instructor/research-queries/"""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        teams = Team.objects.filter(game=game)

        from core.models.rag import ResearchQueryLog
        queries = ResearchQueryLog.objects.filter(
            team__in=teams,
        ).select_related('team').order_by('-queried_at')

        data = [{
            'team_name': q.team.name,
            'round_number': q.round_number,
            'query_text': q.query_text,
            'timestamp': q.queried_at.isoformat(),
        } for q in queries]

        return Response({'queries': data})


class InstructorEventTemplatesView(APIView):
    """GET /api/games/{game_id}/instructor/event-templates/ — list available event templates."""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        templates = EventTemplateDefinition.objects.filter(
            scenario=game.scenario,
        ).order_by('category', 'name')
        markets = MarketDefinition.objects.filter(scenario=game.scenario).order_by('name')

        language = get_user_language(request)
        return Response({
            'event_templates': [{
                'id': t.id,
                'name': get_localized_field(t, 'name', language),
                'category': t.category,
                'severity': t.severity,
                'description': get_localized_field(t, 'description_template', language)[:200] if get_localized_field(t, 'description_template', language) else '',
            } for t in templates],
            'markets': [{
                'id': m.id,
                'name': get_localized_field(m, 'name', language),
                'code': m.code,
            } for m in markets],
        })


class InstructorTeamBriefingsView(APIView):
    """GET /api/games/{game_id}/instructor/briefings/ — list all team briefings."""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        from core.models.cc27_models import StrategicBriefing
        briefings = StrategicBriefing.objects.filter(
            game=game,
        ).select_related('team').order_by('-round_number', 'team__name')

        data = []
        for b in briefings:
            data.append({
                'id': b.id,
                'team_id': b.team_id,
                'team_name': b.team.name,
                'round_number': b.round_number,
                'executive_summary': b.executive_summary,
                'performance_analysis': b.performance_analysis,
                'investment_returns': b.investment_returns,
                'competitive_landscape': b.competitive_landscape,
                'strategic_recommendations': b.strategic_recommendations,
                'risk_alerts': b.risk_alerts,
                'generated_at': b.generated_at.isoformat() if b.generated_at else None,
            })

        return Response({'briefings': data})


class InstructorOperatorEventsView(APIView):
    """GET /api/games/{game_id}/instructor/operator-events/

    What the operators did to this game, in timestamp order.

    Every lifecycle action already wrote one of these rows -- close, reopen,
    deadline change, process, advance, event injection, correction unlock,
    team withdrawal -- and refusals wrote one too. Nothing read them. CRV2-08
    found the runbook telling an operator to "review operator events in
    timestamp order" to answer a dispute, with no screen or endpoint that
    returns any, so the only way to see them was the Django admin: a separate
    maintenance login that competition instructors do not have.

    Read-only, by design. These rows are evidence; the database triggers
    enforce that regardless of what this view does, and the view offers no
    write of any kind.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        from core.models import OperatorAuditEvent
        from core.permissions import instructor_can_access_game
        game = get_object_or_404(Game, id=game_id)
        # Same ownership rule as every other instructor read: without it an
        # instructor could read another cohort's operator trail -- who acted,
        # when, and the written reason for every override -- by changing the
        # game id in the URL.
        if not instructor_can_access_game(request, game):
            return Response(
                {'error': 'This game belongs to another instructor.'},
                status=status.HTTP_403_FORBIDDEN)

        events = (OperatorAuditEvent.objects
                  .filter(game=game).select_related('user', 'round'))
        round_number = request.query_params.get('round')
        if round_number and str(round_number).isdigit():
            events = events.filter(round__round_number=int(round_number))
        action = request.query_params.get('action')
        if action:
            events = events.filter(action=action)
        outcome = request.query_params.get('outcome')
        if outcome in ('committed', 'rejected'):
            events = events.filter(outcome=outcome)

        try:
            limit = min(int(request.query_params.get('limit', 200)), 500)
        except (TypeError, ValueError):
            limit = 200

        rows = list(events.order_by('-created_at', '-id')[:limit])
        return Response({
            'game_id': game.id,
            'count': len(rows),
            'events': [{
                'id': event.id,
                'server_timestamp': event.created_at.isoformat(),
                'actor': ((event.user.display_name or event.user.email or
                           event.user.username) if event.user else 'system'),
                'actor_user_id': event.user_id,
                'action': event.action,
                'outcome': event.outcome,
                'round_number': (event.round.round_number
                                 if event.round_id else None),
                # A refusal carries an empty `after` and the conflict that
                # caused it; that is the shape the runbook tells an operator
                # to look for when reading a race after the fact.
                'before': event.before,
                'after': event.after,
                'conflict': event.conflict,
                'reason': event.reason,
                'request_id': event.request_id,
            } for event in rows],
        })


class InstructorTeamDecisionsView(APIView):
    """GET /api/games/{game_id}/instructor/teams/{team_id}/decisions/ — view a team's decisions."""
    permission_classes = [IsInstructor]

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)
        round_number = request.query_params.get('round', game.current_round)
        try:
            round_number = int(round_number)
        except (ValueError, TypeError):
            round_number = game.current_round

        from core.models.core import Round
        from core.models.decisions import (
            DecisionSubmission, DecisionBudgetAllocation,
            DecisionMarketing, DecisionRDInvestment,
            DecisionPlatformDevelopment, DecisionMarketEntry,
            DecisionFinancing, DecisionESG,
        )
        from core.models.talent import DecisionTalent

        rnd = Round.objects.filter(game=game, round_number=round_number).first()
        if not rnd:
            return Response({'error': 'Round not found'}, status=404)

        sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
        if not sub:
            return Response({
                'status': 'no_submission', 'round': round_number,
                'submission_origin': 'no_submission',
                'submission_origin_label': SUBMISSION_ORIGIN_LABELS['no_submission'],
            })

        origin = classify_submission_origin(game, team, rnd, sub)
        locked_by = None
        if sub.locked_by_id:
            lb = User.objects.filter(user_id=sub.locked_by_id).first()
            if lb:
                locked_by = lb.display_name or lb.email or lb.username
        result = {
            'status': sub.status,
            'round': round_number,
            'locked_at': sub.locked_at.isoformat() if sub.locked_at else None,
            'locked_by': locked_by,
            'submission_origin': origin,
            'submission_origin_label': SUBMISSION_ORIGIN_LABELS.get(origin, origin),
        }

        # V2-G: expose the immutable evidence behind the snapshot so an
        # operator can answer submission disputes without database access.
        from core.models import DecisionAuditEvent
        result['audit_events'] = [{
            'id': event.id,
            'action': event.action,
            'actor': (event.user.display_name or event.user.email or
                      event.user.username) if event.user else 'system',
            'server_timestamp': event.created_at.isoformat(),
            'endpoint': event.endpoint,
            'request_id': event.request_id,
            'payload_sha256': event.payload_sha256,
            'payload': event.payload,
        } for event in DecisionAuditEvent.objects.filter(
            game=game, team=team, round=rnd,
        ).select_related('user').order_by('id')]

        # Budget
        try:
            b = sub.budget_allocation
            result['budget'] = {
                'rd_budget': float(b.rd_budget),
                'marketing_budget': float(b.marketing_budget),
                'strategy_budget': float(b.strategy_budget),
            }
        except DecisionBudgetAllocation.DoesNotExist:
            result['budget'] = None

        # R&D
        rd_investments = [{
            'feature': get_localized_field(inv.feature, 'name', language) if inv.feature else '—',
            'amount': float(inv.amount),
            'method': inv.method,
        } for inv in sub.rd_investments.select_related('feature').all()]
        platform_devs = [{
            'name': pd.platform_name or get_localized_field(pd.platform_generation, 'name', language),
            'method': pd.method,
            'cost': float(pd.committed_cost),
        } for pd in sub.platform_developments.select_related('platform_generation').all()]
        result['rd'] = {'investments': rd_investments, 'platform_developments': platform_devs}

        # Marketing
        marketing = [{
            'product': md.team_product.name if md.team_product else '—',
            'market': get_localized_field(md.market, 'name', language) if md.market else '—',
            'retail_price': float(md.retail_price),
            'production_volume': md.production_volume or 0,
            'promotion_budget': float(md.promotion_budget),
            'sales_team_count': md.sales_team_count or 0,
            'distribution_strategy': md.distribution_strategy,
        } for md in sub.marketing_decisions.select_related('team_product', 'market').all()]
        result['marketing'] = marketing

        # Market entries
        entries = [{
            'market': get_localized_field(me.market, 'name', language) if me.market else '—',
            'action': me.action,
            'entry_mode': get_localized_field(me.entry_mode, 'name', language) if me.entry_mode else '—',
            'investment': float(me.initial_investment),
        } for me in sub.market_entries.select_related('market', 'entry_mode').all()]
        result['market_entries'] = entries

        # Financing
        try:
            f = sub.financing
            result['financing'] = {
                'new_debt': float(f.new_debt),
                'debt_repayment': float(f.debt_repayment),
                'new_equity': float(f.new_equity),
                'dividend_per_share': float(f.dividend_per_share),
            }
        except DecisionFinancing.DoesNotExist:
            result['financing'] = None

        # ESG
        try:
            e = sub.esg
            result['esg'] = {
                'environmental_investment': float(e.environmental_investment),
                'social_investment': float(e.social_investment),
            }
        except DecisionESG.DoesNotExist:
            result['esg'] = None

        # Talent
        try:
            t = sub.talent
            result['talent'] = {
                'rd_headcount': t.rd_headcount, 'rd_salary_level': t.rd_salary_level,
                'commercial_headcount': t.commercial_headcount, 'commercial_salary_level': t.commercial_salary_level,
                'operations_headcount': t.operations_headcount, 'operations_salary_level': t.operations_salary_level,
            }
        except DecisionTalent.DoesNotExist:
            result['talent'] = None

        return Response(result)
