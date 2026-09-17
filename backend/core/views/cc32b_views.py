"""
CC-32B: Organizational Design API Views.
"""
from decimal import Decimal

from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.models.core import Game, Team
from core.models.team_state import TeamMarketPresence
from core.models.cc32b_models import OrganizationalStructureType, TeamOrganizationalStructure
from core.utils.localization import get_localized_field, get_user_language
from core.views.decisions import (
    CompetitionDecisionWriteMixin, IsTeamMember, IsCurrentRoundOpen)

D = Decimal


class _SwitchUnaffordable(Exception):
    """A structure switch the team's cash cannot cover, carrying the figures.

    Raised inside the switch transaction so the switch is rolled back with it
    (R36): a refusal must leave no trace of the structure change it refused.
    """

    def __init__(self, assessment):
        super().__init__('organisational structure switch exceeds cash')
        self.assessment = assessment


class OrgStructureContextView(CompetitionDecisionWriteMixin, APIView):
    """
    GET: Returns available org structures, team's current structure, costs, and transition info.
    POST: Switch to a new structure.
    """

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        try:
            game = Game.objects.get(id=game_id)
            team = Team.objects.get(id=team_id, game=game)
        except (Game.DoesNotExist, Team.DoesNotExist):
            return Response({'error': 'Game or team not found'}, status=status.HTTP_404_NOT_FOUND)

        scenario = game.scenario
        structures = OrganizationalStructureType.objects.filter(scenario=scenario).order_by('display_order')

        # Get team's current structure
        org, _ = TeamOrganizationalStructure.objects.get_or_create(
            game=game, team=team,
            defaults={
                'current_structure': structures.filter(code='centralized').first(),
                'adopted_round': 0,
            },
        )

        active_markets = TeamMarketPresence.objects.filter(team=team, status='active').count()

        # Build structure data
        structures_data = []
        for s in structures:
            overextension = max(0, active_markets - s.optimal_market_range_max)
            coordination_cost = s.per_market_coordination_cost * active_markets
            overextension_cost = s.overextension_cost_per_market * overextension
            total_per_round = s.base_overhead_per_round + coordination_cost + overextension_cost

            is_current = org.current_structure_id == s.id

            structures_data.append({
                'id': s.id,
                'code': s.code,
                'name': get_localized_field(s, 'name', language),
                'description': get_localized_field(s, 'description', language),
                'base_overhead_per_round': float(s.base_overhead_per_round),
                'per_market_coordination_cost': float(s.per_market_coordination_cost),
                'hq_talent_effectiveness_modifier': float(s.hq_talent_effectiveness_modifier),
                'local_talent_effectiveness_modifier': float(s.local_talent_effectiveness_modifier),
                'innovation_modifier': float(s.innovation_modifier),
                'coordination_efficiency': float(s.coordination_efficiency),
                'decision_speed_modifier': float(s.decision_speed_modifier),
                'optimal_market_range_min': s.optimal_market_range_min,
                'optimal_market_range_max': s.optimal_market_range_max,
                'overextension_cost_per_market': float(s.overextension_cost_per_market),
                'overextension_effectiveness_penalty': float(s.overextension_effectiveness_penalty),
                'transition_cost': float(s.transition_cost),
                'transition_disruption_rounds': s.transition_disruption_rounds,
                'display_order': s.display_order,
                # Computed for this team
                'is_current': is_current,
                'coordination_cost': float(coordination_cost),
                'overextension_markets': overextension,
                'overextension_cost': float(overextension_cost),
                'total_cost_per_round': float(total_per_round),
                'within_optimal_range': active_markets <= s.optimal_market_range_max and active_markets >= s.optimal_market_range_min,
            })

        current_data = None
        if org.current_structure:
            current_data = {
                'id': org.current_structure.id,
                'code': org.current_structure.code,
                'name': get_localized_field(org.current_structure, 'name', language),
                'adopted_round': org.adopted_round,
            }

        return Response({
            'structures': structures_data,
            'current_structure': current_data,
            'active_markets': active_markets,
            'transitioning': org.transition_rounds_remaining > 0,
            'transition_rounds_remaining': org.transition_rounds_remaining,
            'transitioning_from': get_localized_field(org.transitioning_from, 'name', language) if org.transitioning_from else None,
        })

    def post(self, request, game_id, team_id):
        """Switch organizational structure."""
        try:
            game = Game.objects.get(id=game_id)
            team = Team.objects.get(id=team_id, game=game)
        except (Game.DoesNotExist, Team.DoesNotExist):
            return Response({'error': 'Game or team not found'}, status=status.HTTP_404_NOT_FOUND)

        structure_id = request.data.get('structure_id')
        if not structure_id:
            return Response({'error': 'structure_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_structure = OrganizationalStructureType.objects.get(
                id=structure_id, scenario=game.scenario,
            )
        except OrganizationalStructureType.DoesNotExist:
            return Response({'error': 'Structure not found'}, status=status.HTTP_404_NOT_FOUND)

        org, _ = TeamOrganizationalStructure.objects.get_or_create(
            game=game, team=team,
            defaults={
                'current_structure': new_structure,
                'adopted_round': game.current_round,
            },
        )

        # Check if already this structure
        if org.current_structure_id == new_structure.id:
            return Response({'error': 'Already using this structure'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if already transitioning
        if org.transition_rounds_remaining > 0:
            return Response(
                {'error': 'Cannot switch during an active transition'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # R36 / V2-088: the transition cost is NOT deducted here.
        #
        # This view used to do `team.cash_on_hand -= transition_cost` at
        # request time. The money left the business at click time while every
        # committed-spend, projected-cash and Finance figure the team is shown
        # ignored it, the equity funding rule never counted it, and nothing
        # restored it -- reopening a round left the cash gone while the
        # decision it paid for could still be changed. That is the "cost shown
        # is not the cost charged" defect V2-037/V2-038 consolidated the budget
        # rule to end, on a different surface.
        #
        # The charge is now booked at resolution by
        # `engine/costs.calculate_operating_expenses`, from the switch this
        # view records, through `funding_need.org_transition_charge` -- the one
        # function both the engine and the funding rule read. Nothing is
        # written here but the switch itself, so a reopened round has nothing
        # to unwind: the money never moved.
        #
        # Affordability goes through the one existing rule rather than a second
        # copy of the cash arithmetic, exactly as a research purchase does:
        # record the switch, ask `budget_assessment` whether the team can still
        # afford what it has committed, and undo the switch if it cannot.
        from core.models.decisions import DecisionSubmission
        from core.services.competition_audit import record_decision_event
        from core.services.rd_costs import budget_assessment

        rnd = game.rounds.filter(round_number=game.current_round).first()
        if rnd is None:
            return Response({'error': 'No current round for this game.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # The switch is a decision, so it needs the round's submission to hang
        # its committed spend on -- the same reason a research purchase creates
        # one. Without it the affordability rule has nothing to assess.
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})

        old_structure = org.current_structure
        try:
            with transaction.atomic():
                org.transitioning_from = old_structure
                org.current_structure = new_structure
                org.adopted_round = game.current_round
                org.transition_rounds_remaining = new_structure.transition_disruption_rounds
                org.save()

                assessment = budget_assessment(submission, team)
                if not assessment['within_cash']:
                    raise _SwitchUnaffordable(assessment)

                # The audit record stays exactly as it was: R34's principle --
                # the explanation lives in the audit trail, and this needs no
                # new hashed field.
                record_decision_event(request, game, team, rnd,
                                      'change_org_structure', request.data)
        except _SwitchUnaffordable as refusal:
            found = refusal.assessment
            return Response(
                {'error': (
                    f'Insufficient cash. This switch would take committed '
                    f'spend to ${Decimal(found["committed_total"]):,.0f}, '
                    f'against ${Decimal(found["cash_on_hand"]):,.0f} of cash.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            'success': True,
            'new_structure': new_structure.name,
            'transition_cost': float(new_structure.transition_cost),
            'disruption_rounds': new_structure.transition_disruption_rounds,
        })
    permission_classes = [IsTeamMember, IsCurrentRoundOpen]
    throttle_scope = 'decision_write'
