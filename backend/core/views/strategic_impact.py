"""
CC-24: Strategic Investment Impact Report API.

GET /api/games/{game_id}/teams/{team_id}/financial-reports/strategic-impact/
Returns all ESG, talent, partnership, and plant economic impact data
across all rounds for the team.

Optional query param: ?round_number=N to get a single round.
"""
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.models.cc24_models import (
    ESGEconomicImpact, TalentEconomicImpact, PartnershipEconomicImpact,
)
from core.models.results_financials import RoundResultFinancials
from core.models.team_state import TeamPlant, TeamPartnership
from core.models.decisions import DecisionESG, DecisionSubmission
from core.models.core import Game, Team
from core.utils.localization import get_localized_field, get_user_language

D = Decimal


class StrategicImpactView(APIView):
    """Strategic Investment Impact Report."""

    def get(self, request, game_id, team_id):
        try:
            game = Game.objects.get(id=game_id)
            team = Team.objects.get(id=team_id, game=game)
        except (Game.DoesNotExist, Team.DoesNotExist):
            return Response({'error': 'Game or team not found'}, status=status.HTTP_404_NOT_FOUND)

        self._language = get_user_language(request)
        round_number = request.query_params.get('round_number')
        round_filter = {}
        if round_number:
            round_filter['round_number'] = int(round_number)

        result = {
            'team_id': team_id,
            'game_id': game_id,
            'esg': self._get_esg_data(game, team, round_filter),
            'talent': self._get_talent_data(game, team, round_filter),
            'partnerships': self._get_partnership_data(game, team, round_filter),
            'plants': self._get_plant_data(game, team, round_filter),
            'summary': self._get_summary(game, team, round_filter),
        }

        return Response(result)

    def _get_esg_data(self, game, team, round_filter):
        """Assemble ESG economic impact data."""
        impacts = ESGEconomicImpact.objects.filter(
            game=game, team=team, **round_filter,
        ).select_related('market').order_by('round_number', 'benefit_type')

        # Group by round
        by_round = {}
        for imp in impacts:
            rn = imp.round_number
            if rn not in by_round:
                by_round[rn] = {'benefits': [], 'total_savings': D('0')}
            by_round[rn]['benefits'].append({
                'type': imp.benefit_type,
                'market': get_localized_field(imp.market, 'name', self._language) if imp.market else 'All',
                'base_value': str(imp.base_value),
                'effective_value': str(imp.effective_value),
                'savings': str(imp.savings),
                'esg_level': str(imp.esg_level),
                'description': imp.description,
            })
            by_round[rn]['total_savings'] += imp.savings

        # Get ESG investment totals per round
        for rn in by_round:
            sub = DecisionSubmission.objects.filter(
                team=team, round__game=game, round__round_number=rn,
            ).first()
            esg_cost = D('0')
            if sub:
                try:
                    esg = sub.esg
                    if esg:
                        esg_cost = esg.environmental_investment + esg.social_investment
                except Exception:
                    pass
            by_round[rn]['esg_investment'] = str(esg_cost)
            by_round[rn]['total_savings'] = str(by_round[rn]['total_savings'])
            savings_d = D(by_round[rn]['total_savings'])
            if esg_cost > 0:
                by_round[rn]['roi_pct'] = str(
                    (savings_d / esg_cost * D('100')).quantize(D('0.1'))
                )
            else:
                by_round[rn]['roi_pct'] = '0.0'

        # Cumulative totals
        all_impacts = ESGEconomicImpact.objects.filter(game=game, team=team)
        cumulative_savings = sum(float(i.savings) for i in all_impacts)

        return {
            'by_round': {str(k): v for k, v in by_round.items()},
            'cumulative_savings': str(round(cumulative_savings, 2)),
        }

    def _get_talent_data(self, game, team, round_filter):
        """Assemble talent economic impact data."""
        impacts = TalentEconomicImpact.objects.filter(
            game=game, team=team, **round_filter,
        ).order_by('round_number')

        rounds = []
        for imp in impacts:
            rounds.append({
                'round_number': imp.round_number,
                'rd_talent': {
                    'level': str(imp.rd_talent_level),
                    'modifier': str(imp.rd_cost_modifier),
                    'savings': str(imp.rd_cost_savings),
                },
                'commercial_talent': {
                    'level': str(imp.commercial_talent_level),
                    'modifier': str(imp.campaign_effectiveness_modifier),
                    'uplift': str(imp.campaign_revenue_uplift),
                },
                'operations_talent': {
                    'level': str(imp.operations_talent_level),
                    'modifier': str(imp.cogs_modifier),
                    'savings': str(imp.cogs_savings),
                },
                'total_cost': str(imp.total_talent_cost),
                'total_benefit': str(imp.total_talent_benefit),
                'net_roi': str(imp.net_talent_roi),
            })

        return {'rounds': rounds}

    def _get_partnership_data(self, game, team, round_filter):
        """Assemble partnership economic impact data."""
        impacts = PartnershipEconomicImpact.objects.filter(
            game=game, team=team, **round_filter,
        ).select_related('partnership__strategy_option', 'partnership__market').order_by('round_number')

        by_partnership = {}
        for imp in impacts:
            p_id = imp.partnership_id
            if p_id not in by_partnership:
                p = imp.partnership
                by_partnership[p_id] = {
                    'partnership_name': get_localized_field(p.strategy_option, 'name', self._language) if p.strategy_option else 'Unknown',
                    'market': get_localized_field(p.market, 'name', self._language) if p.market else 'Global',
                    'annual_investment': str(p.annual_investment),
                    'benefits': [],
                    'total_benefit': D('0'),
                }
            by_partnership[p_id]['benefits'].append({
                'round_number': imp.round_number,
                'type': imp.benefit_type,
                'amount': str(imp.benefit_amount),
                'description': imp.description,
            })
            by_partnership[p_id]['total_benefit'] += imp.benefit_amount

        for p_id in by_partnership:
            by_partnership[p_id]['total_benefit'] = str(by_partnership[p_id]['total_benefit'])

        return {'partnerships': list(by_partnership.values())}

    def _get_plant_data(self, game, team, round_filter):
        """Assemble plant ownership economic data."""
        plants = TeamPlant.objects.filter(team=team).select_related('market')

        plant_list = []
        for plant in plants:
            plant_mkt_name = get_localized_field(plant.market, 'name', self._language) if plant.market else 'Unknown'
            plant_list.append({
                'market': plant_mkt_name,
                'status': plant.status,
                'capacity': plant.capacity_units,
                'construction_started': plant.construction_started_round,
                'completion_round': plant.completion_round,
                'cumulative_production': plant.cumulative_production,
                'tariff_savings_note': (
                    f'Products manufactured in {plant_mkt_name} pay zero tariff in that market'
                    if plant.status == 'operational' else
                    f'Under construction — operational in round {plant.completion_round}'
                ),
            })

        return {'plants': plant_list}

    def _get_summary(self, game, team, round_filter):
        """Aggregate totals across all strategic investments."""
        # ESG totals
        esg_impacts = ESGEconomicImpact.objects.filter(game=game, team=team, **round_filter)
        esg_savings = sum(float(i.savings) for i in esg_impacts)

        # Talent totals
        talent_impacts = TalentEconomicImpact.objects.filter(game=game, team=team, **round_filter)
        talent_benefit = sum(float(i.total_talent_benefit) for i in talent_impacts)
        talent_cost = sum(float(i.total_talent_cost) for i in talent_impacts)

        # Partnership totals
        partner_impacts = PartnershipEconomicImpact.objects.filter(game=game, team=team, **round_filter)
        partner_benefit = sum(float(i.benefit_amount) for i in partner_impacts)

        # ESG investment totals
        esg_investment = D('0')
        subs = DecisionSubmission.objects.filter(
            team=team, round__game=game,
        )
        if round_filter.get('round_number'):
            subs = subs.filter(round__round_number=round_filter['round_number'])
        for sub in subs:
            try:
                esg = sub.esg
                if esg:
                    esg_investment += esg.environmental_investment + esg.social_investment
            except Exception:
                pass

        # Partnership investment
        partner_investment = D('0')
        for p in TeamPartnership.objects.filter(team=team, status='active'):
            partner_investment += p.annual_investment

        total_strategic_cost = float(esg_investment) + talent_cost + float(partner_investment)
        total_strategic_return = esg_savings + talent_benefit + partner_benefit
        net_roi_pct = (
            (total_strategic_return / total_strategic_cost * 100)
            if total_strategic_cost > 0 else 0
        )

        return {
            'total_strategic_cost': str(round(total_strategic_cost, 2)),
            'total_strategic_return': str(round(total_strategic_return, 2)),
            'net_roi_pct': str(round(net_roi_pct, 1)),
            'esg_savings': str(round(esg_savings, 2)),
            'talent_net': str(round(talent_benefit - talent_cost, 2)),
            'partnership_savings': str(round(partner_benefit, 2)),
        }
