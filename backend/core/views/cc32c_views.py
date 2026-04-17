"""CC-32C: Tax Structure & Transfer Pricing API."""
from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.cc32c_models import TaxStructureType, TeamTaxStructure
from core.models.cc31_models import TeamGovernanceCommitment
from core.models.results_financials import RoundResultFinancials
from core.utils.localization import get_localized_field, get_user_language


class TaxStructureContextView(APIView):
    """
    GET — tax structure options and current team state.
    POST — switch tax structure.
    """

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, pk=game_id)
        team = get_object_or_404(Team, pk=team_id)
        scenario = game.scenario

        # Available structures
        structures = []
        for ts in TaxStructureType.objects.filter(scenario=scenario):
            structures.append({
                'code': ts.code,
                'name': get_localized_field(ts, 'name', language),
                'description': get_localized_field(ts, 'description', language),
                'setup_cost': float(ts.setup_cost),
                'annual_maintenance_cost': float(ts.annual_maintenance_cost),
                'effective_tax_reduction_pct': float(ts.effective_tax_reduction_pct),
                'repatriation_cost_reduction_pct': float(ts.repatriation_cost_reduction_pct),
                'audit_probability_per_round': float(ts.audit_probability_per_round),
                'audit_penalty_multiplier': float(ts.audit_penalty_multiplier),
                'value_investor_modifier': float(ts.value_investor_modifier),
                'esg_investor_modifier': float(ts.esg_investor_modifier),
                'regulator_modifier': float(ts.regulator_modifier),
                'anti_corruption_conflict': ts.anti_corruption_conflict,
            })

        # Current team state
        tts, _ = TeamTaxStructure.objects.get_or_create(
            game=game, team=team,
            defaults={'current_structure': None},
        )
        current = {
            'code': tts.current_structure.code if tts.current_structure else 'direct',
            'adopted_round': tts.adopted_round,
            'setup_cost_paid': tts.setup_cost_paid,
            'times_audited': tts.times_audited,
            'cumulative_audit_penalties': float(tts.cumulative_audit_penalties or 0),
            'cumulative_tax_savings': float(tts.cumulative_tax_savings or 0),
            'last_audit_round': tts.last_audit_round,
        }

        # Check anti-corruption commitment
        has_anti_corruption = TeamGovernanceCommitment.objects.filter(
            game=game, team=team,
            commitment_type__code='anti_corruption',
            is_active=True,
        ).exists()

        # Current foreign revenue and tax data for impact preview
        latest_round = max(game.current_round - 1, 0)
        latest_financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=latest_round,
        ).first()

        foreign_revenue = 0
        foreign_tax_paid = 0
        repatriation_costs = 0
        avg_foreign_tax_rate = 0.25

        if latest_financials:
            # Get per-market revenue data
            from core.models.results_financials import RoundResultMarketRevenue
            market_revs = RoundResultMarketRevenue.objects.filter(
                game=game, team=team, round_number=latest_round,
            )
            for mr in market_revs:
                if mr.market_id != getattr(team, 'home_market_id', None):
                    foreign_revenue += float(mr.home_revenue or 0)

            foreign_tax_paid = float(latest_financials.tax_expense or 0)
            # Estimate repatriation from total costs
            total_rev = float(latest_financials.total_revenue or 1)
            if total_rev > 0 and foreign_revenue > 0:
                foreign_ratio = foreign_revenue / total_rev
                # Approximate foreign tax as proportional
                foreign_tax_paid = float(latest_financials.tax_expense or 0) * foreign_ratio

        # Total rounds in scenario
        total_rounds = game.total_rounds if hasattr(game, 'total_rounds') else 12
        rounds_remaining = max(total_rounds - game.current_round, 0)

        return Response({
            'structures': structures,
            'current': current,
            'has_anti_corruption': has_anti_corruption,
            'foreign_revenue': foreign_revenue,
            'foreign_tax_paid': foreign_tax_paid,
            'repatriation_costs': repatriation_costs,
            'avg_foreign_tax_rate': avg_foreign_tax_rate,
            'rounds_remaining': rounds_remaining,
        })

    def post(self, request, game_id, team_id):
        game = get_object_or_404(Game, pk=game_id)
        team = get_object_or_404(Team, pk=team_id)

        structure_code = request.data.get('structure_code')
        if not structure_code:
            return Response({'error': 'structure_code required'}, status=400)

        if structure_code == 'direct':
            # Switch to direct = no structure
            tts, _ = TeamTaxStructure.objects.get_or_create(
                game=game, team=team,
                defaults={'current_structure': None},
            )
            tts.current_structure = None
            tts.adopted_round = game.current_round
            tts.setup_cost_paid = True  # Direct has no setup cost
            tts.save()
            return Response({'status': 'ok', 'structure': 'direct'})

        structure = get_object_or_404(
            TaxStructureType, scenario=game.scenario, code=structure_code,
        )

        tts, _ = TeamTaxStructure.objects.get_or_create(
            game=game, team=team,
            defaults={'current_structure': None},
        )

        # Only charge setup cost if switching to a new structure
        if tts.current_structure != structure:
            tts.current_structure = structure
            tts.adopted_round = game.current_round
            tts.setup_cost_paid = False  # Will be paid during engine processing
            tts.save()

        return Response({'status': 'ok', 'structure': structure_code})
