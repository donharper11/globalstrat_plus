"""
CC-32A: Stakeholder Communications API.

Endpoints:
- GET  assignments/           — active assignments for current round
- GET  communications/<id>/   — specific assignment + team draft/submission
- POST communications/<id>/draft/  — save draft
- POST communications/<id>/submit/ — submit for LLM evaluation
- GET  communications/history/     — all past submissions with evaluations
- GET  instructor/communications/<round>/ — instructor view (all teams)
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, Round
from core.models.cc32_models import CommunicationAssignment, TeamCommunication
from core.models.results import EventInstance
from core.utils.localization import get_localized_field, get_user_language


class CommunicationAssignmentsView(APIView):
    """GET — active assignments for the current round."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)
        scenario = game.scenario
        current_round = game.current_round

        rnd = Round.objects.filter(game=game, round_number=current_round).first()
        if not rnd:
            return Response({'assignments': []})

        # Find triggered assignments
        assignments = []

        for ca in CommunicationAssignment.objects.filter(scenario=scenario):
            triggered = False
            event_context = {}

            if ca.trigger_type == 'ROUND_MILESTONE':
                triggered = (ca.trigger_condition or {}).get('round') == current_round

            elif ca.trigger_type == 'EVENT_BASED':
                categories = (ca.trigger_condition or {}).get('event_category', [])
                if isinstance(categories, str):
                    categories = [categories]
                events = EventInstance.objects.filter(
                    game=game, round_number=current_round,
                ).select_related('event_template')
                for ev in events:
                    if (ev.event_template.category or '').upper() in [c.upper() for c in categories]:
                        triggered = True
                        event_context = {
                            'event_name': get_localized_field(ev.event_template, 'name', language),
                            'event_description': ev.narrative or get_localized_field(ev.event_template, 'description_template', language),
                        }
                        break

            elif ca.trigger_type == 'DECISION_BASED':
                # Future extension
                pass

            if not triggered:
                continue

            # Check if team already has a submission
            tc = TeamCommunication.objects.filter(
                game=game, team=team, round=rnd, assignment=ca,
            ).first()

            # Populate prompt template variables
            prompt_text = get_localized_field(ca, 'prompt_text', language)
            if team.home_market:
                prompt_text = prompt_text.replace('{home_market}', get_localized_field(team.home_market, 'name', language))
            from core.models.team_state import TeamMarketPresence
            active_markets = list(TeamMarketPresence.objects.filter(
                team=team, status='active',
            ).values_list('market__name', flat=True))
            prompt_text = prompt_text.replace('{active_markets}', ', '.join(active_markets) if active_markets else 'N/A')
            if event_context:
                prompt_text = prompt_text.replace('{event_name}', event_context.get('event_name', ''))
                prompt_text = prompt_text.replace('{event_description}', event_context.get('event_description', ''))

            assignments.append({
                'id': ca.id,
                'code': ca.code,
                'name': get_localized_field(ca, 'name', language),
                'audience': ca.audience,
                'audience_display': ca.get_audience_display(),
                'prompt_text': prompt_text,
                'word_limit': ca.word_limit,
                'evaluation_criteria': ca.evaluation_criteria,
                'is_mandatory': ca.is_mandatory,
                'coherence_weight': float(ca.coherence_weight),
                'status': 'submitted' if tc and not tc.is_draft else ('draft' if tc else 'new'),
                'draft_content': tc.content if tc and tc.is_draft else None,
                'draft_word_count': tc.word_count if tc and tc.is_draft else 0,
                'evaluation': tc.evaluation if tc and not tc.is_draft else None,
                'coherence_contribution': float(tc.coherence_contribution) if tc else 0,
            })

        return Response({'round': current_round, 'assignments': assignments})


class CommunicationDraftView(APIView):
    """POST — save draft for a specific assignment."""

    def post(self, request, game_id, team_id, assignment_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        if not rnd:
            return Response({'detail': 'No active round.'}, status=400)

        ca = get_object_or_404(CommunicationAssignment, id=assignment_id)
        content = request.data.get('content', '')
        word_count = len(content.split())

        tc, _ = TeamCommunication.objects.update_or_create(
            game=game, team=team, round=rnd, assignment=ca,
            defaults={
                'content': content,
                'word_count': word_count,
                'is_draft': True,
            },
        )

        return Response({
            'id': tc.id,
            'word_count': tc.word_count,
            'is_draft': True,
            'status': 'draft_saved',
        })


class CommunicationSubmitView(APIView):
    """POST — submit for LLM evaluation. One-shot, cannot resubmit."""

    def post(self, request, game_id, team_id, assignment_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)
        rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
        if not rnd:
            return Response({'detail': 'No active round.'}, status=400)

        ca = get_object_or_404(CommunicationAssignment, id=assignment_id)

        tc = TeamCommunication.objects.filter(
            game=game, team=team, round=rnd, assignment=ca,
        ).first()

        if not tc:
            # Allow submit without prior draft
            content = request.data.get('content', '')
            tc = TeamCommunication.objects.create(
                game=game, team=team, round=rnd, assignment=ca,
                content=content, word_count=len(content.split()),
                is_draft=True,
            )

        if not tc.is_draft:
            return Response({'detail': 'Already submitted. Cannot resubmit.'}, status=400)

        # Update content if provided in submit request
        content = request.data.get('content')
        if content is not None:
            tc.content = content
            tc.word_count = len(content.split())
            tc.save()

        if tc.word_count == 0:
            return Response({'detail': 'Cannot submit empty communication.'}, status=400)

        if tc.word_count > ca.word_limit * 1.1:  # 10% grace
            return Response({
                'detail': f'Exceeds word limit. Maximum {ca.word_limit} words, you have {tc.word_count}.',
            }, status=400)

        # Trigger LLM evaluation
        from core.rag.communication_eval import evaluate_communication
        evaluation = evaluate_communication(tc)

        return Response({
            'id': tc.id,
            'word_count': tc.word_count,
            'is_draft': False,
            'evaluation': evaluation,
            'coherence_contribution': float(tc.coherence_contribution),
            'status': 'evaluated',
        })


class CommunicationHistoryView(APIView):
    """GET — all past submissions with evaluations."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        submissions = TeamCommunication.objects.filter(
            game=game, team=team, is_draft=False,
        ).select_related('assignment', 'round').order_by('round__round_number')

        history = []
        for tc in submissions:
            history.append({
                'id': tc.id,
                'round_number': tc.round.round_number,
                'assignment_name': get_localized_field(tc.assignment, 'name', language),
                'assignment_code': tc.assignment.code,
                'audience': tc.assignment.get_audience_display(),
                'content': tc.content,
                'word_count': tc.word_count,
                'submitted_at': tc.submitted_at.isoformat() if tc.submitted_at else None,
                'evaluation': tc.evaluation,
                'coherence_contribution': float(tc.coherence_contribution),
                'overall_score': tc.evaluation.get('overall_score', 0) if tc.evaluation else 0,
            })

        return Response({'history': history})


class InstructorCommunicationsView(APIView):
    """GET — all team submissions for a round (instructor only)."""

    def get(self, request, game_id, round_number):
        game = get_object_or_404(Game, id=game_id)

        submissions = TeamCommunication.objects.filter(
            game=game, round__round_number=round_number,
        ).select_related('assignment', 'team', 'round').order_by('team__name', 'assignment__display_order')

        teams_data = {}
        for tc in submissions:
            team_name = tc.team.name
            if team_name not in teams_data:
                teams_data[team_name] = {'team_id': tc.team.id, 'team_name': team_name, 'submissions': []}
            teams_data[team_name]['submissions'].append({
                'assignment_name': tc.assignment.name,
                'audience': tc.assignment.get_audience_display(),
                'content': tc.content,
                'word_count': tc.word_count,
                'is_draft': tc.is_draft,
                'submitted_at': tc.submitted_at.isoformat() if tc.submitted_at else None,
                'evaluation': tc.evaluation,
                'overall_score': tc.evaluation.get('overall_score', 0) if tc.evaluation else None,
                'coherence_contribution': float(tc.coherence_contribution),
            })

        return Response({
            'round_number': int(round_number),
            'teams': list(teams_data.values()),
        })
