"""
CC-19 Part A: Research Reports endpoints.

GET /api/games/{game_id}/teams/{team_id}/research/reports/{report_type}/
Where report_type is: segments, products, markets, channels
"""
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.scenario import (
    MarketDefinition, SegmentDefinition, SegmentPreference,
    MarketConditionByRound, ScenarioConfig,
)
from core.models.results import RoundResultAdoption
from core.models.results_financials import (
    RoundResultProductMarket, RoundResultFinancials,
)
from core.models.team_state import (
    TeamProduct, TeamProductMarket, TeamPlatform,
    TeamPlatformFeatureLevel, TeamPlant, TeamMarketPresence,
    TeamPartnership,
)
from core.models.decisions import (
    DecisionSubmission, DecisionMarketing,
)
from core.utils.localization import get_localized_field, get_user_language


def _f(v):
    """Safely convert Decimal/None to float."""
    if v is None:
        return 0
    return float(v)


def _importance_label(weight):
    w = float(weight)
    if w > 0.15:
        return 'Critical'
    if w >= 0.08:
        return 'High'
    if w >= 0.04:
        return 'Moderate'
    return 'Low'


def _fit_label(score):
    s = float(score)
    if s > 0.7:
        return 'Strong'
    if s >= 0.5:
        return 'Moderate'
    if s >= 0.3:
        return 'Weak'
    return 'Very Weak'


def _growth_label(rate):
    r = float(rate)
    if r >= 0.08:
        return 'Fastest'
    if r >= 0.05:
        return 'Fast'
    if r >= 0.03:
        return 'Moderate growth'
    return 'Slow growth'


def _price_sensitivity_label(weight):
    """Derive from weight of price-related feature in segment preferences."""
    w = float(weight)
    if w > 0.15:
        return 'Very High'
    if w >= 0.10:
        return 'High'
    if w >= 0.05:
        return 'Moderate'
    return 'Low'


def _opportunity_signal(seg_data):
    """Rule-based opportunity signal from segment data."""
    growth = float(seg_data.get('growth_rate', 0))
    your_share = float(seg_data.get('your_share', 0))
    fit_label = seg_data.get('your_fit_score_label', 'Very Weak')
    underserved = seg_data.get('underserved', False)
    population = seg_data.get('population', 0)
    price_sens = seg_data.get('price_sensitivity', 'Moderate')

    if growth >= 0.05 and your_share < 0.10:
        return 'Growing segment you\'re not capturing. Investigate fit gaps.'
    if your_share > 0.20 and fit_label in ('Weak', 'Very Weak'):
        return 'Your lead may be eroding. Check competitor moves.'
    if population > 50000 and underserved:
        return 'Large underserved segment. First-mover advantage available.'
    if price_sens == 'Low' and fit_label in ('Weak', 'Very Weak'):
        return 'High-margin segment. Your capabilities may not match their expectations.'
    if price_sens in ('Very High', 'High') and your_share > 0.15:
        return 'Dominated by price competition. Margins thin.'
    if growth >= 0.03 and fit_label == 'Strong':
        return 'Growing segment where you have strong fit. Protect and expand.'
    return ''


class ResearchReportsView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/research/reports/{report_type}/"""

    def get(self, request, game_id, team_id, report_type):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)
        scenario = game.scenario
        language = get_user_language(request)

        # Use requested round or default to last completed round
        requested_round = request.query_params.get('round')
        if requested_round is not None and requested_round != '':
            try:
                last_round = max(min(int(requested_round), game.current_round - 1), 0)
            except (ValueError, TypeError):
                last_round = max(game.current_round - 1, 0)
        else:
            last_round = max(game.current_round - 1, 0)

        if report_type == 'segments':
            return self._segment_report(request, game, team, scenario, last_round, language)
        elif report_type == 'products':
            return self._product_report(game, team, scenario, last_round, language)
        elif report_type == 'markets':
            return self._market_report(game, team, scenario, last_round, language)
        elif report_type == 'channels':
            return self._channel_report(request, game, team, scenario, last_round)
        elif report_type == 'stakeholders':
            return self._stakeholder_report(game, team, scenario, last_round, language)
        else:
            return Response({'error': f'Unknown report type: {report_type}'}, status=400)

    def _segment_report(self, request, game, team, scenario, last_round, language='en'):
        market_code = request.query_params.get('market', 'all')

        segments_qs = SegmentDefinition.objects.filter(
            scenario=scenario, segment_type='customer',
        ).order_by('display_order')

        if market_code != 'all':
            market = MarketDefinition.objects.filter(scenario=scenario, code=market_code).first()
            if market:
                segments_qs = segments_qs.filter(Q(market=market) | Q(market__isnull=True))

        segments_data = []
        for seg in segments_qs:
            # Get preferences (top 3 by weight)
            prefs = SegmentPreference.objects.filter(
                segment=seg,
            ).select_related('feature').order_by('-weight')[:3]

            top_features = [{
                'name': get_localized_field(p.feature, 'name', language),
                'importance': _importance_label(p.weight),
            } for p in prefs]

            # Price sensitivity from price-related feature weight
            price_pref = SegmentPreference.objects.filter(
                segment=seg, feature__code__in=['price_competitiveness', 'retail_price'],
            ).first()
            price_sensitivity = _price_sensitivity_label(price_pref.weight if price_pref else 0.05)

            # Adoption data for this team
            adoption = RoundResultAdoption.objects.filter(
                game=game, team=team, segment=seg, round_number=last_round,
            ).first()

            # All team adoption for this segment to find top competitor
            all_adoption = RoundResultAdoption.objects.filter(
                game=game, segment=seg, round_number=last_round,
            ).select_related('team').order_by('-team_share_pct')

            your_share = _f(adoption.team_share_pct) if adoption else 0
            your_fit = _f(adoption.adjusted_fit_score) if adoption else 0

            # Rank
            your_rank = 1
            top_competitor = None
            top_competitor_share = 0
            for i, a in enumerate(all_adoption):
                if a.team_id == team.id:
                    your_rank = i + 1
                elif top_competitor is None:
                    top_competitor = a.team.name
                    top_competitor_share = _f(a.team_share_pct)

            # Adoption trend across rounds
            trend = []
            for r in range(max(last_round - 3, 0), last_round + 1):
                a = RoundResultAdoption.objects.filter(
                    game=game, team=team, segment=seg, round_number=r,
                ).first()
                trend.append(int(_f(a.new_adopters)) if a else None)

            # Check if underserved (no team > 20% share)
            max_share = max([_f(a.team_share_pct) for a in all_adoption] or [0])
            underserved = max_share < 0.20

            seg_entry = {
                'name': get_localized_field(seg, 'name', language),
                'type': seg.segment_type,
                'market': get_localized_field(seg.market, 'name', language) if seg.market else 'All Markets',
                'population': seg.population_size,
                'growth_rate': _f(seg.population_growth_rate),
                'growth_label': _growth_label(seg.population_growth_rate),
                'your_fit_score_label': _fit_label(your_fit),
                'your_share': your_share,
                'your_rank': your_rank,
                'top_competitor': top_competitor or 'N/A',
                'top_competitor_share': top_competitor_share,
                'adoption_trend': trend,
                'price_sensitivity': price_sensitivity,
                'top_valued_features': top_features,
                'underserved': underserved,
            }
            seg_entry['opportunity_signal'] = _opportunity_signal(seg_entry)
            segments_data.append(seg_entry)

        market_name = 'All Markets'
        if market_code != 'all':
            mkt = MarketDefinition.objects.filter(scenario=scenario, code=market_code).first()
            if mkt:
                market_name = get_localized_field(mkt, 'name', language)

        return Response({
            'market': market_name,
            'segments': segments_data,
        })

    def _product_report(self, game, team, scenario, last_round, language='en'):
        products_data = []

        for p in TeamProduct.objects.filter(team=team, status='active').select_related(
            'team_platform__platform_generation',
        ):
            # Get markets
            pm_list = TeamProductMarket.objects.filter(
                team_product=p, is_active=True,
            ).select_related('market')

            markets = []
            for pm in pm_list:
                # Product-market results
                rpm = RoundResultProductMarket.objects.filter(
                    game=game, team=team, team_product=p,
                    market=pm.market, round_number=last_round,
                ).first()

                # Segment fit for this product in this market
                adoptions = RoundResultAdoption.objects.filter(
                    game=game, team=team, best_product=p,
                    market=pm.market, round_number=last_round,
                ).select_related('segment')

                seg_fits = []
                strongest = None
                weakest = None
                strongest_fit = -1
                weakest_fit = 2

                for a in adoptions:
                    fit = _f(a.adjusted_fit_score)
                    label = _fit_label(fit)
                    seg_fits.append({
                        'segment': get_localized_field(a.segment, 'name', language),
                        'fit_label': label,
                        'adoption': int(_f(a.new_adopters)),
                    })
                    if fit > strongest_fit:
                        strongest_fit = fit
                        strongest = get_localized_field(a.segment, 'name', language)
                    if fit < weakest_fit:
                        weakest_fit = fit
                        weakest = get_localized_field(a.segment, 'name', language)

                # Recommendation
                recommendation = ''
                if strongest and weakest and strongest != weakest:
                    # Find top features for weakest segment
                    weak_seg = SegmentDefinition.objects.filter(
                        scenario=scenario, name=weakest,
                    ).first()
                    if weak_seg:
                        top_prefs = SegmentPreference.objects.filter(
                            segment=weak_seg,
                        ).select_related('feature').order_by('-weight')[:2]
                        feature_names = [get_localized_field(p.feature, 'name', language) for p in top_prefs]
                        if feature_names:
                            recommendation = (
                                f'Strong with {strongest} but weak {weakest} appeal. '
                                f'{" and ".join(feature_names)} improvements would broaden appeal.'
                            )

                # Revenue rank in market
                all_pm = RoundResultProductMarket.objects.filter(
                    game=game, market=pm.market, round_number=last_round,
                ).order_by('-home_revenue')
                rank = 1
                for i, apm in enumerate(all_pm):
                    if apm.team_id == team.id and apm.team_product_id == p.id:
                        rank = i + 1
                        break

                margin = 0
                if rpm and _f(rpm.home_revenue) > 0:
                    margin = (_f(rpm.home_revenue) - _f(rpm.total_cogs)) / _f(rpm.home_revenue)

                markets.append({
                    'market': get_localized_field(pm.market, 'name', language),
                    'units_sold': int(_f(rpm.units_sold)) if rpm else 0,
                    'revenue': _f(rpm.home_revenue) if rpm else 0,
                    'margin_pct': round(margin, 4),
                    'market_rank': rank,
                    'segment_fit': seg_fits,
                    'strongest_segment': strongest,
                    'weakest_segment': weakest,
                    'recommendation': recommendation,
                })

            # Feature levels
            features = [{
                'name': get_localized_field(fl.feature, 'name', language),
                'level': _f(fl.current_level),
            } for fl in TeamPlatformFeatureLevel.objects.filter(
                team_platform=p.team_platform,
            ).select_related('feature')]

            products_data.append({
                'name': p.name,
                'platform': p.team_platform.name or get_localized_field(p.team_platform.platform_generation, 'name', language),
                'positioning': p.positioning,
                'features': features,
                'markets': markets,
            })

        return Response({'products': products_data})

    def _market_report(self, game, team, scenario, last_round, language='en'):
        markets_data = []

        for mkt in MarketDefinition.objects.filter(scenario=scenario).order_by('display_order'):
            cond = MarketConditionByRound.objects.filter(
                market=mkt, round_number=last_round,
            ).first()

            # Your presence
            presence = TeamMarketPresence.objects.filter(
                team=team, market=mkt, status='active',
            ).select_related('entry_mode').first()

            # Exchange rate trend (last 4 rounds)
            fx_trend = []
            for r in range(max(last_round - 3, 0), last_round + 1):
                c = MarketConditionByRound.objects.filter(market=mkt, round_number=r).first()
                rate = _f(mkt.exchange_rate_base) + (_f(c.exchange_rate_modifier) if c else 0)
                fx_trend.append(round(rate, 4))

            # Total market size from adoption
            total_adopters = RoundResultAdoption.objects.filter(
                game=game, market=mkt, round_number=last_round,
            ).aggregate(total=Sum('new_adopters'))['total'] or 0

            # Your total share
            your_rev = RoundResultProductMarket.objects.filter(
                game=game, team=team, market=mkt, round_number=last_round,
            ).aggregate(total=Sum('home_revenue'))['total'] or 0
            all_rev = RoundResultProductMarket.objects.filter(
                game=game, market=mkt, round_number=last_round,
            ).aggregate(total=Sum('home_revenue'))['total'] or 1
            your_share = _f(your_rev) / max(_f(all_rev), 1)

            # Segment breakdown
            segs = SegmentDefinition.objects.filter(
                scenario=scenario, segment_type='customer',
            ).filter(Q(market=mkt) | Q(market__isnull=True)).order_by('display_order')

            total_pop = sum(s.population_size for s in segs) or 1
            seg_breakdown = [{
                'segment': get_localized_field(s, 'name', language),
                'pct_of_market': round(s.population_size / total_pop, 2),
                'growth': _growth_label(s.population_growth_rate).replace(' growth', ''),
            } for s in segs]

            # Competitor count
            teams_in_market = TeamMarketPresence.objects.filter(
                market=mkt, status='active',
            ).values('team').distinct().count()

            current_fx = _f(mkt.exchange_rate_base) + (_f(cond.exchange_rate_modifier) if cond else 0)
            current_tariff = _f(mkt.tariff_rate) + (_f(cond.tariff_rate_modifier) if cond else 0)
            current_growth = _f(mkt.base_growth_rate) + (_f(cond.growth_rate_modifier) if cond else 0)

            your_plant = TeamPlant.objects.filter(
                team=team, market=mkt, status='operational',
            ).exists()

            mkt_name = get_localized_field(mkt, 'name', language)
            entry = {
                'name': mkt_name,
                'code': mkt.code,
                'total_market_size': int(_f(total_adopters)),
                'growth_rate': round(current_growth, 4),
                'your_presence': presence is not None,
                'your_entry_mode': get_localized_field(presence.entry_mode, 'name', language) if presence else None,
                'your_total_share': round(your_share, 4),
                'currency_code': mkt.currency_code,
                'exchange_rate': round(current_fx, 4),
                'exchange_rate_trend': fx_trend,
                'exchange_rate_volatility': _f(mkt.exchange_rate_volatility),
                'tariff_rate': round(current_tariff, 4),
                'tax_rate': _f(mkt.tax_rate),
                'regulatory_difficulty': _f(mkt.regulatory_difficulty),
                'infrastructure_quality': _f(mkt.infrastructure_quality),
                'manufacturing_available': mkt.allows_manufacturing,
                'your_plant': your_plant,
                'contract_mfg_available': mkt.contract_mfg_available,
                'segment_breakdown': seg_breakdown,
                'competitive_intensity': f'{teams_in_market} competitors present',
                'entry_cost_base': _f(mkt.entry_cost_base),
            }

            # Opportunity summary
            if not presence:
                entry['opportunity_summary'] = (
                    f'You are not present in {mkt_name}. '
                    f'Entry cost: ${int(_f(mkt.entry_cost_base)):,}. '
                    f'Growth rate: {current_growth*100:.1f}%.'
                )
            elif your_share < 0.05:
                entry['opportunity_summary'] = (
                    f'Small presence in a {"growing" if current_growth > 0.03 else "stable"} market. '
                    f'Consider investing in distribution and marketing to grow share.'
                )
            else:
                entry['opportunity_summary'] = (
                    f'Established presence with {your_share*100:.1f}% share. '
                    f'{"Growing market offers expansion potential." if current_growth > 0.03 else "Mature market — defend position."}'
                )

            markets_data.append(entry)

        return Response({'markets': markets_data})

    def _channel_report(self, request, game, team, scenario, last_round):
        market_code = request.query_params.get('market')

        BASE_REACH = {
            'mass_retail': 0.9, 'selective_retail': 0.6,
            'exclusive_retail': 0.3, 'direct_online': 0.5, 'hybrid': 0.7,
        }

        # Check if team is operating in the selected market
        from core.models.core import Round
        is_present = False
        mkt = None
        if market_code:
            mkt = MarketDefinition.objects.filter(scenario=scenario, code=market_code).first()
            if mkt:
                is_present = TeamMarketPresence.objects.filter(
                    team=team, market=mkt, status='active',
                ).exists()

        # Get your current marketing decisions for distribution info
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        sub = DecisionSubmission.objects.filter(team=team, round=rnd).first() if rnd else None

        your_strategy = None
        your_reps = 0
        your_reach = 0

        if is_present and sub and mkt:
            md = DecisionMarketing.objects.filter(
                submission=sub, market=mkt,
            ).first()
            if md:
                your_strategy = md.distribution_strategy
                your_reps = md.sales_team_count

                # Estimate reach
                base_reach = BASE_REACH.get(your_strategy, 0.5)
                try:
                    rep_cost = float(ScenarioConfig.objects.get(
                        scenario=scenario, config_key='sales_rep_cost_per_round',
                    ).config_value)
                except ScenarioConfig.DoesNotExist:
                    rep_cost = 100000
                effective_invest = your_reps * rep_cost
                try:
                    dist_cap = float(ScenarioConfig.objects.get(
                        scenario=scenario, config_key='distribution_investment_cap',
                    ).config_value)
                except ScenarioConfig.DoesNotExist:
                    dist_cap = 5000000
                bonus = min(effective_invest / max(dist_cap, 1), 0.1)
                your_reach = round(base_reach + bonus, 2)

        # Channel comparison: show theoretical reach if present, 0 if not in market
        reach_multiplier = 1.0 if is_present else 0.0
        channel_comparison = [
            {'strategy': 'Mass Retail', 'key': 'mass_retail',
             'reach': round(0.90 * reach_multiplier, 2), 'theoretical_reach': 0.90,
             'margin_impact': -0.05, 'fit_with_budget': 'Excellent', 'fit_with_premium': 'Poor'},
            {'strategy': 'Selective Retail', 'key': 'selective_retail',
             'reach': round(0.60 * reach_multiplier, 2), 'theoretical_reach': 0.60,
             'margin_impact': 0.00, 'fit_with_budget': 'Good', 'fit_with_premium': 'Good'},
            {'strategy': 'Exclusive Retail', 'key': 'exclusive_retail',
             'reach': round(0.30 * reach_multiplier, 2), 'theoretical_reach': 0.30,
             'margin_impact': 0.10, 'fit_with_budget': 'Poor', 'fit_with_premium': 'Excellent'},
            {'strategy': 'Direct Online', 'key': 'direct_online',
             'reach': round(0.50 * reach_multiplier, 2), 'theoretical_reach': 0.50,
             'margin_impact': 0.08, 'fit_with_budget': 'Moderate', 'fit_with_premium': 'Moderate'},
            {'strategy': 'Hybrid', 'key': 'hybrid',
             'reach': round(0.70 * reach_multiplier, 2), 'theoretical_reach': 0.70,
             'margin_impact': 0.03, 'fit_with_budget': 'Good', 'fit_with_premium': 'Good'},
        ]

        return Response({
            'market': market_code or 'all',
            'is_present_in_market': is_present,
            'your_distribution_strategy': your_strategy,
            'your_sales_reps': your_reps,
            'your_reach_estimate': your_reach,
            'channel_comparison': channel_comparison,
        })

    def _stakeholder_report(self, game, team, scenario, last_round, language='en'):
        """CC-25: Non-customer stakeholder satisfaction report."""
        from core.models.team_state import TeamStrategyFeatureLevel
        from core.models.scenario import FeatureDefinition

        segments = SegmentDefinition.objects.filter(
            scenario=scenario,
        ).exclude(segment_type='customer').order_by('segment_type', 'display_order')

        groups = {}
        for seg in segments:
            stype = seg.segment_type
            if stype not in groups:
                groups[stype] = {
                    'type': stype,
                    'label': stype.replace('_', ' ').title() + 's',
                    'segments': [],
                }

            # Get adoption/fit data
            adoption = RoundResultAdoption.objects.filter(
                game=game, team=team, segment=seg, round_number=last_round,
            ).first()

            satisfaction = _f(adoption.adjusted_fit_score) if adoption else 0.5

            # Get segment preferences and team's feature levels for gap analysis
            prefs = SegmentPreference.objects.filter(
                segment=seg,
            ).select_related('feature').order_by('-weight')

            gaps = []
            for p in prefs[:5]:
                # Get team's current level for this feature
                feature_level = TeamStrategyFeatureLevel.objects.filter(
                    team=team,
                    feature=p.feature,
                    round_number=last_round,
                ).order_by('-current_level').first()

                actual = _f(feature_level.current_level) if feature_level else 0
                ideal = _f(p.ideal_value)
                gap = round(ideal - actual, 1)

                gaps.append({
                    'feature': get_localized_field(p.feature, 'name', language),
                    'feature_code': p.feature.code,
                    'weight': round(_f(p.weight), 3),
                    'ideal': ideal,
                    'actual': actual,
                    'gap': gap,
                    'status': 'aligned' if abs(gap) <= 1 else ('over' if gap < -1 else 'under'),
                })

            # Trend
            trend = []
            for r in range(max(last_round - 3, 0), last_round + 1):
                a = RoundResultAdoption.objects.filter(
                    game=game, team=team, segment=seg, round_number=r,
                ).first()
                trend.append(round(_f(a.adjusted_fit_score), 3) if a else None)

            groups[stype]['segments'].append({
                'name': get_localized_field(seg, 'name', language),
                'market': get_localized_field(seg.market, 'name', language) if seg.market else 'Global',
                'description': get_localized_field(seg, 'description', language),
                'satisfaction': round(satisfaction, 3),
                'satisfaction_label': _fit_label(satisfaction),
                'weight': round(_f(seg.performance_index_weight), 4),
                'trend': trend,
                'gaps': gaps,
            })

        return Response({
            'stakeholder_groups': list(groups.values()),
        })
