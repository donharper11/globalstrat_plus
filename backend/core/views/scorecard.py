"""
CC-16 Part B: Balanced Scorecard Dashboard endpoint.
"""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel, TeamProduct,
    TeamMarketPresence,
)
from core.models.scenario import (
    PlatformFeatureCeiling, PlatformGenerationDefinition, MarketDefinition,
)
from core.models.results import RoundResultAdoption
from core.models.results_financials import (
    RoundResultFinancials, RoundResultMarketRevenue,
)
from core.models.talent import TeamTalentState
from core.utils.localization import get_localized_field, get_user_language


class BalancedScorecardView(APIView):
    """GET — Balanced Scorecard data for the team dashboard."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, pk=game_id)
        team = get_object_or_404(Team, pk=team_id)
        latest_round = max(game.current_round - 1, 0)

        financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=latest_round,
        ).first()

        adoptions = RoundResultAdoption.objects.filter(
            game=game, team=team, round_number=latest_round,
        ).select_related('segment')

        talent_states = TeamTalentState.objects.filter(
            team=team, round_number=latest_round,
        )

        # === Financial Perspective ===
        financial = {
            'revenue': float(financials.total_revenue) if financials else 0,
            'net_margin': float(financials.net_margin_pct) if financials else 0,
            'cash_position': float(team.cash_on_hand),
            'debt_to_equity': float(financials.debt_to_equity) if financials else 0,
            'share_price': float(financials.share_price) if financials else 0,
            'shareholder_return': float(financials.shareholder_return_cumulative) if financials else 0,
        }

        # CC-26: Share price sentiment
        from core.models.cc26_models import SharePriceHistory, AIInvestorHolding
        price_hist = SharePriceHistory.objects.filter(
            game=game, team=team, round_number=latest_round,
        ).first()
        prev_price_hist = SharePriceHistory.objects.filter(
            game=game, team=team, round_number=latest_round - 1,
        ).first() if latest_round > 0 else None

        if price_hist:
            financial['share_price'] = float(price_hist.share_price)
            if prev_price_hist and prev_price_hist.share_price > 0:
                financial['share_price_change_pct'] = round(
                    float((price_hist.share_price - prev_price_hist.share_price) / prev_price_hist.share_price) * 100, 1
                )
            else:
                financial['share_price_change_pct'] = 0

        fund_holdings = AIInvestorHolding.objects.filter(
            game=game, team=team, round_number=latest_round,
        )
        if fund_holdings.exists():
            avg_sat = sum(float(h.satisfaction_score) for h in fund_holdings) / fund_holdings.count()
            if avg_sat >= 0.6:
                financial['sentiment_label'] = 'Positive'
                financial['sentiment_direction'] = 'buying'
            elif avg_sat >= 0.45:
                financial['sentiment_label'] = 'Neutral'
                financial['sentiment_direction'] = 'holding'
            else:
                financial['sentiment_label'] = 'Negative'
                financial['sentiment_direction'] = 'selling'
        else:
            financial['sentiment_label'] = 'Neutral'
            financial['sentiment_direction'] = 'holding'

        # === Customer Perspective ===
        customer_adoptions = [a for a in adoptions if a.segment.segment_type == 'customer']
        total_satisfaction = 0
        total_weight = 0
        segment_shares = []

        for a in customer_adoptions:
            w = float(a.segment.performance_index_weight)
            total_satisfaction += float(a.adjusted_fit_score) * w
            total_weight += w
            if a.new_adopters > 0:
                segment_shares.append({
                    'segment': get_localized_field(a.segment, 'name', language),
                    'share_pct': float(a.team_share_pct),
                    'adopters': float(a.new_adopters),
                })

        avg_satisfaction = total_satisfaction / total_weight if total_weight > 0 else 0.5
        segment_shares.sort(key=lambda x: x['share_pct'], reverse=True)

        # Total market share from market revenue
        market_revs = RoundResultMarketRevenue.objects.filter(
            game=game, team=team, round_number=latest_round,
        )
        total_share = sum(float(mr.market_share_pct) for mr in market_revs) / max(market_revs.count(), 1) if market_revs.exists() else 0

        customer = {
            'satisfaction': round(avg_satisfaction, 3),
            'total_market_share': round(total_share * 100, 1),
            'top_segment': segment_shares[0] if segment_shares else None,
            'weakest_segment': segment_shares[-1] if len(segment_shares) > 1 else None,
        }

        # === Stakeholder Perspective (CC-25) ===
        non_customer_adoptions = [a for a in adoptions if a.segment.segment_type != 'customer']

        stakeholder_type_labels = {
            'en': {
                'investor': 'Investor', 'regulator': 'Regulator',
                'channel_partner': 'Channel Partner', 'global': 'Global',
            },
            'zh-CN': {
                'investor': '投资者', 'regulator': '监管机构',
                'channel_partner': '渠道合作伙伴', 'global': '全球',
            },
        }
        type_labels = stakeholder_type_labels.get(language, stakeholder_type_labels['en'])

        stakeholder_groups = {}
        for a in non_customer_adoptions:
            stype = a.segment.segment_type
            if stype not in stakeholder_groups:
                stakeholder_groups[stype] = {
                    'type': stype,
                    'label': type_labels.get(stype, stype.replace('_', ' ').title()),
                    'segments': [],
                    'avg_satisfaction': 0,
                    'total_weight': 0,
                }
            grp = stakeholder_groups[stype]
            w = float(a.segment.performance_index_weight)
            sat = float(a.adjusted_fit_score)
            grp['segments'].append({
                'name': get_localized_field(a.segment, 'name', language),
                'market': get_localized_field(a.segment.market, 'name', language) if a.segment.market else type_labels.get('global', 'Global'),
                'satisfaction': round(sat, 3),
                'weight': round(w, 4),
            })
            grp['avg_satisfaction'] += sat * w
            grp['total_weight'] += w

        for grp in stakeholder_groups.values():
            if grp['total_weight'] > 0:
                grp['avg_satisfaction'] = round(grp['avg_satisfaction'] / grp['total_weight'], 3)
            del grp['total_weight']

        stakeholders = list(stakeholder_groups.values())

        # === Capability Perspective ===
        platform = TeamPlatform.objects.filter(team=team, status='active').order_by('-platform_generation__generation_order').first()
        tech_rating = 0
        platform_name = 'None'
        if platform:
            platform_name = platform.name or platform.platform_generation.name
            feature_levels = TeamPlatformFeatureLevel.objects.filter(team_platform=platform)
            ceilings = PlatformFeatureCeiling.objects.filter(
                platform_generation=platform.platform_generation,
            )
            ceiling_map = {c.feature_id: float(c.ceiling_value) for c in ceilings}
            total_level = sum(float(fl.current_level) for fl in feature_levels)
            total_ceiling = sum(ceiling_map.get(fl.feature_id, 10) for fl in feature_levels)
            tech_rating = (total_level / total_ceiling * 100) if total_ceiling > 0 else 0

        talent_data = {}
        for ts in talent_states:
            talent_data[ts.talent_pool] = {
                'level': float(ts.talent_level),
                'turnover': float(ts.turnover_rate),
            }

        capability = {
            'technology_rating_pct': round(tech_rating, 1),
            'platform_generation': platform_name,
            'talent': talent_data,
        }

        # === Growth & Innovation Perspective ===
        markets_entered = TeamMarketPresence.objects.filter(team=team, status='active').count()
        total_markets = MarketDefinition.objects.filter(scenario=game.scenario).count()

        rd_pct = 0
        if financials and financials.total_revenue > 0:
            rd_pct = float(financials.rd_expense / financials.total_revenue * 100)

        product_count = TeamProduct.objects.filter(team=team, status='active').count()

        current_gen_order = platform.platform_generation.generation_order if platform else 1
        next_gen = PlatformGenerationDefinition.objects.filter(
            scenario=game.scenario,
            generation_order=current_gen_order + 1,
        ).first()
        max_gen = PlatformGenerationDefinition.objects.filter(scenario=game.scenario).count()

        growth = {
            'rd_as_pct_of_revenue': round(rd_pct, 1),
            'markets_entered': markets_entered,
            'total_markets': total_markets,
            'platform_generation': current_gen_order,
            'max_generation': max_gen,
            'next_gen_available_round': next_gen.unlock_round if next_gen else None,
            'product_count': product_count,
        }

        # === Strategic Signals ===
        signals = []
        if growth['rd_as_pct_of_revenue'] < 5:
            signals.append({
                'type': 'warning',
                'text': f"R&D investment is {growth['rd_as_pct_of_revenue']}% of revenue. "
                        f"Competitors may be outpacing your innovation.",
            })
        if capability['technology_rating_pct'] < 50 and next_gen and next_gen.unlock_round <= game.current_round:
            signals.append({
                'type': 'warning',
                'text': f"Technology capability at {capability['technology_rating_pct']}%. "
                        f"A next-generation platform is available for development.",
            })
        if customer['satisfaction'] < 0.4:
            signals.append({
                'type': 'alert',
                'text': "Customer satisfaction is below average. Review Market Research "
                        "to identify underperforming segments.",
            })
        if growth['markets_entered'] == 1 and game.current_round >= 2:
            signals.append({
                'type': 'info',
                'text': f"Operating in {growth['markets_entered']} of {growth['total_markets']} markets. "
                        f"International expansion could unlock growth.",
            })
        if financial['debt_to_equity'] > 1.5:
            signals.append({
                'type': 'warning',
                'text': f"Debt-to-equity ratio at {financial['debt_to_equity']:.2f}. "
                        f"Conservative investors may be concerned.",
            })

        return Response({
            'round_number': latest_round,
            'financial': financial,
            'customer': customer,
            'stakeholders': stakeholders,
            'capability': capability,
            'growth': growth,
            'signals': signals[:4],
        })
