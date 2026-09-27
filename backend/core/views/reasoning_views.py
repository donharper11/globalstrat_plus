"""
Strategic Reasoning Evaluator API Views.

Student endpoint: bands + qualitative feedback (no numeric scores).
Instructor/Judge endpoints: full scores, breakdowns, comparison, aggregate.
"""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.cc_reasoning import (
    RoundResultReasoningAnalysis, CompetitionReasoningAggregate,
)
from core.views.decisions import IsTeamMember
from core.permissions import IsInstructor
from core.utils.participant_messages import (
    language_for_participant, participant_message,
)


class StudentReasoningView(APIView):
    """
    GET /games/{game_id}/teams/{team_id}/rounds/{round}/reasoning/

    Returns: overall_band, per-dimension bands + qualitative feedback.
    No numeric scores.
    """
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id, round_number):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        analysis = RoundResultReasoningAnalysis.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()

        if not analysis:
            language = language_for_participant(team, request)
            return Response({
                'available': False,
                'message': participant_message(
                    'reasoning_not_available', language=language),
            })

        # Student view: bands + qualitative feedback only, no raw scores
        feedback = analysis.feedback_student or {}
        dimensions = feedback.get('dimensions', {})

        student_data = {
            'available': True,
            'round_number': analysis.round_number,
            'overall_band': analysis.overall_band,
            'trajectory_pattern': analysis.trajectory_pattern,
            'dimensions': {},
        }

        for dim_key, dim_data in dimensions.items():
            student_data['dimensions'][dim_key] = {
                'band': dim_data.get('band', 'developing'),
                'feedback': dim_data.get('feedback', ''),
            }
            if 'pattern' in dim_data:
                student_data['dimensions'][dim_key]['pattern'] = dim_data['pattern']
            if 'depth' in dim_data:
                student_data['dimensions'][dim_key]['depth'] = dim_data['depth']

        # Include narrative if Phase 2 completed
        if analysis.phase2_completed and feedback.get('narrative'):
            student_data['narrative'] = feedback['narrative']

        return Response(student_data)


class StudentReasoningHistoryView(APIView):
    """
    GET /games/{game_id}/teams/{team_id}/reasoning/history/

    Returns band progression across rounds for trend display.
    """
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        analyses = RoundResultReasoningAnalysis.objects.filter(
            game=game, team=team,
        ).order_by('round_number')

        history = [
            {
                'round_number': a.round_number,
                'overall_band': a.overall_band,
                'trajectory_pattern': a.trajectory_pattern,
            }
            for a in analyses
        ]

        return Response({'history': history})


class InstructorReasoningAllTeamsView(APIView):
    """
    GET /instructor/games/{game_id}/reasoning/
    GET /instructor/games/{game_id}/reasoning/?round=N

    All teams, current or specified round. Full numeric view.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        round_number = request.query_params.get('round')

        if round_number:
            round_number = int(round_number)
        else:
            round_number = game.current_round

        analyses = RoundResultReasoningAnalysis.objects.filter(
            game=game, round_number=round_number,
        ).select_related('team').order_by('team__name')

        teams_data = []
        for a in analyses:
            teams_data.append({
                'team_id': a.team_id,
                'team_name': a.team.name,
                'round_number': a.round_number,
                'reasoning_score_deterministic': float(a.reasoning_score_deterministic),
                'reasoning_score_full': float(a.reasoning_score_full) if a.reasoning_score_full else None,
                'coherence_ext_score': float(a.coherence_ext_score),
                'responsiveness_score': float(a.responsiveness_score),
                'trajectory_score': float(a.trajectory_score),
                'justification_score': float(a.justification_score) if a.justification_score else None,
                'trajectory_pattern': a.trajectory_pattern,
                'overall_band': a.overall_band,
                'phase2_completed': a.phase2_completed,
            })

        return Response({
            'game_id': game_id,
            'round_number': round_number,
            'teams': teams_data,
        })


class InstructorReasoningTeamView(APIView):
    """
    GET /instructor/games/{game_id}/teams/{team_id}/reasoning/

    One team, all rounds. Full breakdown + evidence.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id, team_id):
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        analyses = RoundResultReasoningAnalysis.objects.filter(
            game=game, team=team,
        ).order_by('round_number')

        rounds = []
        for a in analyses:
            rounds.append({
                'round_number': a.round_number,
                'reasoning_score_deterministic': float(a.reasoning_score_deterministic),
                'reasoning_score_full': float(a.reasoning_score_full) if a.reasoning_score_full else None,
                'coherence_ext_score': float(a.coherence_ext_score),
                'responsiveness_score': float(a.responsiveness_score),
                'trajectory_score': float(a.trajectory_score),
                'justification_score': float(a.justification_score) if a.justification_score else None,
                'coherence_ext_breakdown': a.coherence_ext_breakdown,
                'responsiveness_breakdown': a.responsiveness_breakdown,
                'trajectory_breakdown': a.trajectory_breakdown,
                'justification_breakdown': a.justification_breakdown,
                'trajectory_pattern': a.trajectory_pattern,
                'overall_band': a.overall_band,
                'feedback_judge': a.feedback_judge,
                'phase2_completed': a.phase2_completed,
            })

        return Response({
            'game_id': game_id,
            'team_id': team_id,
            'team_name': team.name,
            'rounds': rounds,
        })


class InstructorReasoningComparisonView(APIView):
    """
    GET /instructor/games/{game_id}/reasoning/comparison/

    Cross-team radar data for the latest evaluated round.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        round_number = request.query_params.get('round')

        if round_number:
            round_number = int(round_number)
        else:
            round_number = game.current_round

        analyses = RoundResultReasoningAnalysis.objects.filter(
            game=game, round_number=round_number,
        ).select_related('team')

        comparison = []
        for a in analyses:
            comparison.append({
                'team_id': a.team_id,
                'team_name': a.team.name,
                'dimensions': {
                    'coherence_ext': float(a.coherence_ext_score),
                    'responsiveness': float(a.responsiveness_score),
                    'trajectory': float(a.trajectory_score),
                    'justification': float(a.justification_score) if a.justification_score else None,
                },
                'overall': float(a.reasoning_score_deterministic),
            })

        return Response({
            'round_number': round_number,
            'comparison': comparison,
        })


class InstructorReasoningAggregateView(APIView):
    """
    GET /instructor/games/{game_id}/reasoning/aggregate/

    Competition-level aggregate rankings.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)

        aggregates = CompetitionReasoningAggregate.objects.filter(
            game=game,
        ).select_related('team').order_by('-aggregate_reasoning_score')

        data = []
        for agg in aggregates:
            data.append({
                'team_id': agg.team_id,
                'team_name': agg.team.name,
                'aggregate_reasoning_score': float(agg.aggregate_reasoning_score),
                'rounds_evaluated': agg.rounds_evaluated,
                'avg_coherence_ext': float(agg.avg_coherence_ext),
                'avg_responsiveness': float(agg.avg_responsiveness),
                'avg_trajectory': float(agg.avg_trajectory),
                'dominant_pattern': agg.dominant_pattern,
                'pattern_consistency': float(agg.pattern_consistency),
                'score_trend': agg.score_trend,
                'round_by_round': agg.round_by_round,
            })

        return Response({
            'game_id': game_id,
            'aggregates': data,
        })


class InstructorReasoningExportView(APIView):
    """
    GET /instructor/games/{game_id}/reasoning/export/

    CSV export for judges.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        import csv
        from django.http import HttpResponse

        game = get_object_or_404(Game, id=game_id)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="reasoning_scores_game_{game_id}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            'Team', 'Round', 'Deterministic Score', 'Full Score',
            'Coherence Ext', 'Responsiveness', 'Trajectory', 'Justification',
            'Pattern', 'Band', 'Phase 2 Complete',
        ])

        analyses = RoundResultReasoningAnalysis.objects.filter(
            game=game,
        ).select_related('team').order_by('team__name', 'round_number')

        for a in analyses:
            writer.writerow([
                a.team.name,
                a.round_number,
                float(a.reasoning_score_deterministic),
                float(a.reasoning_score_full) if a.reasoning_score_full else '',
                float(a.coherence_ext_score),
                float(a.responsiveness_score),
                float(a.trajectory_score),
                float(a.justification_score) if a.justification_score else '',
                a.trajectory_pattern,
                a.overall_band,
                a.phase2_completed,
            ])

        return response
