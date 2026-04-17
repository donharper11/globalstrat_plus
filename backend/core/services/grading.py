"""
Grading service — converts simulation data into academic grades.

Architecture:
  1. Component extractors: each returns a 0-100 score for a (team, instance).
     Extractors bridge CC-1 (instance_id) and CC-06+ (game_id) models.
  2. Category scorer: weighted blend of mapped components.
  3. Overall scorer: weighted blend of categories.
  4. Linear stretch: maps raw composites into a configurable grade range
     (default floor=60, ceiling=90) to spread clustered scores.
  5. Override resolver: COALESCE(override, computed).
"""
from decimal import Decimal
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from core.models import Team
from core.models.course import Enrollment, SimulationInstance
from core.models.grading import (
    GradingRubric, GradingRubricCategory,
    GradingComponentMapping, TeamGrade, StudentGradeAdjustment,
)

ZERO = Decimal('0')
HUNDRED = Decimal('100')

# Default linear-stretch grade range
DEFAULT_GRADE_FLOOR = Decimal('60')
DEFAULT_GRADE_CEILING = Decimal('90')


# ── Default rubric seed data ────────────────────────────────────────

DEFAULT_RUBRIC = [
    {
        'category_name': 'Performance Index',
        'weight': Decimal('100.00'),
        'sort_order': 1,
        'description': 'Cumulative simulation score based on market performance, segment satisfaction, and strategic decisions',
        'components': [
            ('performance_index', Decimal('100.00'), 'linear'),
        ],
    },
]


def seed_default_rubric(course_id, created_by=None):
    """Create the default rubric for a course if none exists."""
    existing = GradingRubric.objects.filter(
        course_id=course_id, is_active=True,
    ).first()
    if existing:
        return existing

    rubric = GradingRubric.objects.create(
        course_id=course_id,
        rubric_name='Default Rubric',
        is_active=True,
        created_by=created_by,
        created_at=timezone.now(),
        updated_at=timezone.now(),
    )
    for cat_def in DEFAULT_RUBRIC:
        cat = GradingRubricCategory.objects.create(
            rubric_id=rubric.rubric_id,
            category_name=cat_def['category_name'],
            weight=cat_def['weight'],
            sort_order=cat_def['sort_order'],
            description=cat_def['description'],
        )
        for comp_key, comp_weight, transform in cat_def['components']:
            GradingComponentMapping.objects.create(
                category_id=cat.category_id,
                component_key=comp_key,
                component_weight=comp_weight,
                score_transform=transform,
            )
    return rubric


# ── Component Extractors ────────────────────────────────────────────
# Each returns a Decimal 0-100 for a given team + instance.

# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# ESGScorecard model deleted — ESG extractors return ZERO
def _extract_esg_environmental(team_id, instance_id):
    # ESGScorecard deleted
    return ZERO


def _extract_esg_social(team_id, instance_id):
    # ESGScorecard deleted
    return ZERO


def _extract_esg_governance(team_id, instance_id):
    # ESGScorecard deleted
    return ZERO


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# ChallengeResponseScore model deleted
def _extract_challenge_responses(team_id, instance_id):
    # ChallengeResponseScore deleted
    # agg = ChallengeResponseScore.objects.filter(
    #     team_id=team_id,
    # ).aggregate(avg=Avg('score'), cnt=Count('response_id'))
    # ...
    return ZERO


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# EthicalDecision model deleted
def _extract_ethical_reasoning(team_id, instance_id):
    # EthicalDecision deleted
    # decisions = EthicalDecision.objects.filter(team_id=team_id)
    # ...
    return ZERO


def _extract_stakeholder_satisfaction(team_id, instance_id):
    """Latest shareholder_return from LeaderboardEntry, scaled to 0-100."""
    from core.models.results_financials import LeaderboardEntry

    game_id = _resolve_game_id(instance_id)
    if not game_id:
        return ZERO
    entry = LeaderboardEntry.objects.filter(
        game_id=game_id, team_id=team_id,
    ).order_by('-round_number').first()
    if not entry:
        return ZERO
    # shareholder_return is a decimal ratio; scale to 0-100
    sr = float(entry.shareholder_return or 0)
    # Clamp: -1.0 → 0, 0 → 50, 1.0+ → 100
    scaled = max(0, min(100, 50 + sr * 50))
    return Decimal(str(round(scaled, 2)))


def _extract_financial_stewardship(team_id, instance_id):
    """Score based on cumulative net income across decision rounds (excludes R0 bootstrap)."""
    from core.models.results_financials import RoundResultFinancials

    game_id = _resolve_game_id(instance_id)
    if not game_id:
        return Decimal('50')  # neutral baseline

    # Exclude round 0 — bootstrap income varies by starter profile, not player decisions
    financials = RoundResultFinancials.objects.filter(
        game_id=game_id, team_id=team_id, round_number__gte=1,
    )
    if not financials.exists():
        return Decimal('50')

    total_net = sum(float(f.net_income or 0) for f in financials)

    # Scale: $0 = 40, $20M+ cumulative = 100, -$2M = 0
    if total_net >= 0:
        scaled = min(total_net / 333333, 60)
        return min(Decimal('40') + Decimal(str(round(scaled, 2))), HUNDRED)
    else:
        scaled = max(total_net / 50000, -40)
        return max(Decimal('40') + Decimal(str(round(scaled, 2))), ZERO)


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# BCorpCertification and BCorpMilestone models deleted
def _extract_bcorp_progress(team_id, instance_id):
    # BCorpCertification / BCorpMilestone / bcorp service deleted
    # cert = BCorpCertification.objects.filter(
    #     team_id=team_id, instance_id=instance_id,
    #     certification_awarded=True,
    # ).first()
    # ...
    return ZERO


def _extract_sdg_coverage(team_id, instance_id):
    return ZERO


def _extract_total_score(team_id, instance_id):
    """Alias for performance_index — total simulation score."""
    return _extract_performance_index(team_id, instance_id)


def _resolve_game_id(instance_id):
    """Bridge legacy instance_id to CC-06+ game_id."""
    sim = SimulationInstance.objects.filter(
        instance_id=instance_id,
    ).first()
    return sim.game_id if sim else None


def _extract_performance_index(team_id, instance_id):
    """Team.performance_index — the cumulative simulation score (0-100)."""
    game_id = _resolve_game_id(instance_id)
    if not game_id:
        return ZERO
    team = Team.objects.filter(game_id=game_id, id=team_id).first()
    if not team or team.performance_index is None:
        return ZERO
    return min(Decimal(str(team.performance_index)), HUNDRED)


def _extract_coherence_score(team_id, instance_id):
    """Average blended coherence score across all rounds for a team."""
    from core.models.results_financials import RoundResultCoherence

    game_id = _resolve_game_id(instance_id)
    if not game_id:
        return ZERO
    agg = RoundResultCoherence.objects.filter(
        game_id=game_id, team_id=team_id,
    ).aggregate(avg=Avg('blended_score'), cnt=Count('id'))
    if not agg['cnt'] or agg['avg'] is None:
        return ZERO
    # blended_score is 0-100
    return min(Decimal(str(round(float(agg['avg']), 2))), HUNDRED)


def _extract_communication_quality(team_id, instance_id):
    """Average overall_score from TeamCommunication evaluations."""
    from core.models.cc32_models import TeamCommunication

    game_id = _resolve_game_id(instance_id)
    if not game_id:
        return ZERO
    comms = TeamCommunication.objects.filter(
        game_id=game_id, team_id=team_id,
    )
    scores = []
    for c in comms:
        if c.evaluation and isinstance(c.evaluation, dict):
            overall = c.evaluation.get('overall_score')
            if overall is not None:
                scores.append(float(overall))
    if not scores:
        return ZERO
    avg = sum(scores) / len(scores)
    # overall_score is 0-100
    return min(Decimal(str(round(avg, 2))), HUNDRED)


# Registry of component extractors
COMPONENT_EXTRACTORS = {
    'performance_index': _extract_performance_index,
    'coherence_score': _extract_coherence_score,
    'communication_quality': _extract_communication_quality,
    'stakeholder_satisfaction': _extract_stakeholder_satisfaction,
    'financial_stewardship': _extract_financial_stewardship,
    'total_score': _extract_total_score,
    # Legacy extractors (return ZERO — kept for backward compat with old rubrics)
    'esg_environmental': _extract_esg_environmental,
    'esg_social': _extract_esg_social,
    'esg_governance': _extract_esg_governance,
    'challenge_responses': _extract_challenge_responses,
    'ethical_reasoning': _extract_ethical_reasoning,
    'bcorp_progress': _extract_bcorp_progress,
    'sdg_coverage': _extract_sdg_coverage,
}

# Human-readable labels for UI
COMPONENT_LABELS = {
    'performance_index': 'Performance Index',
    'coherence_score': 'Strategic Coherence',
    'communication_quality': 'Communication Quality',
    'stakeholder_satisfaction': 'Segment Satisfaction',
    'financial_stewardship': 'Financial Stewardship',
    'total_score': 'Total Performance Score',
    # Legacy labels
    'esg_environmental': 'ESG — Environmental',
    'esg_social': 'ESG — Social',
    'esg_governance': 'ESG — Governance',
    'challenge_responses': 'Challenge Responses',
    'ethical_reasoning': 'Ethical Reasoning',
    'bcorp_progress': 'B-Corp Progress',
    'sdg_coverage': 'SDG Coverage',
}


# ── Normalization helpers ───────────────────────────────────────────

def _normalize_across_teams(component_key, team_ids, instance_id):
    """Min-max normalize a component across all teams -> dict {team_id: 0-100}."""
    extractor = COMPONENT_EXTRACTORS.get(component_key)
    if not extractor:
        return {tid: ZERO for tid in team_ids}

    raw = {tid: extractor(tid, instance_id) for tid in team_ids}
    values = [v for v in raw.values() if v is not None]
    if not values:
        return {tid: ZERO for tid in team_ids}

    mn, mx = min(values), max(values)
    spread = mx - mn
    if spread == 0:
        return {tid: Decimal('50') for tid in team_ids}

    return {
        tid: ((raw[tid] - mn) / spread) * 100
        for tid in team_ids
    }


# ── Linear Stretch ─────────────────────────────────────────────────

def _linear_stretch(scores, floor=None, ceiling=None):
    """
    Map raw composite scores into [floor, ceiling] via linear interpolation.

    scores: dict {team_id: Decimal}
    Returns:  dict {team_id: Decimal} with stretched grades.

    If all scores are identical, everyone gets the midpoint of the range.
    """
    if floor is None:
        floor = DEFAULT_GRADE_FLOOR
    if ceiling is None:
        ceiling = DEFAULT_GRADE_CEILING

    values = list(scores.values())
    if not values:
        return scores

    raw_min = min(values)
    raw_max = max(values)
    spread = raw_max - raw_min

    if spread == 0:
        mid = (floor + ceiling) / 2
        return {tid: mid for tid in scores}

    return {
        tid: floor + (v - raw_min) / spread * (ceiling - floor)
        for tid, v in scores.items()
    }


# ── Grade Calculation ───────────────────────────────────────────────

def calculate_category_score(team_id, instance_id, category_id,
                             all_team_ids=None):
    """Calculate computed score (0-100) for one rubric category."""
    mappings = GradingComponentMapping.objects.filter(
        category_id=category_id,
    )
    if not mappings.exists():
        return ZERO

    weighted_sum = ZERO
    total_weight = ZERO

    for mapping in mappings:
        extractor = COMPONENT_EXTRACTORS.get(mapping.component_key)
        if not extractor:
            continue

        weight = mapping.component_weight or ZERO
        transform = mapping.score_transform or 'linear'

        if transform == 'normalize' and all_team_ids:
            normalized = _normalize_across_teams(
                mapping.component_key, all_team_ids, instance_id,
            )
            raw_score = normalized.get(team_id, ZERO)
        elif transform == 'threshold':
            raw = extractor(team_id, instance_id)
            threshold = mapping.threshold_value or Decimal('50')
            raw_score = HUNDRED if raw >= threshold else ZERO
        else:  # linear
            raw_score = extractor(team_id, instance_id)

        weighted_sum += weight * raw_score
        total_weight += weight

    if total_weight == 0:
        return ZERO

    return weighted_sum / total_weight


def calculate_team_grades(instance_id, course_id, graded_by=None,
                          grade_floor=None, grade_ceiling=None):
    """
    Full grade calculation for all teams in an instance.
    Creates/updates TeamGrade rows for each category + overall.
    Applies linear stretch to overall composites before persisting.
    Returns list of team grade dicts.
    """
    rubric = GradingRubric.objects.filter(
        course_id=course_id, is_active=True,
    ).first()
    if not rubric:
        rubric = seed_default_rubric(course_id, created_by=graded_by)

    categories = GradingRubricCategory.objects.filter(
        rubric_id=rubric.rubric_id,
    ).order_by('sort_order')

    # Resolve instance_id → game_id to find teams in the new engine
    game_id = _resolve_game_id(instance_id)
    if game_id:
        teams = Team.objects.filter(game_id=game_id)
    else:
        # Fallback: no SimulationInstance link yet
        teams = Team.objects.none()

    team_ids = [t.id for t in teams]
    now = timezone.now()

    # Phase 1: compute raw overall composites per team
    team_data = {}  # team_id -> {team, category_scores, raw_overall}

    for team in teams:
        overall_weighted = ZERO
        overall_weight = ZERO
        category_scores = []

        for cat in categories:
            computed = calculate_category_score(
                team.id, instance_id, cat.category_id,
                all_team_ids=team_ids,
            )
            computed = min(max(computed, ZERO), HUNDRED)

            # Upsert the category grade row
            grade, _ = TeamGrade.objects.update_or_create(
                instance_id=instance_id,
                team_id=team.id,
                category_id=cat.category_id,
                defaults={
                    'computed_score': computed,
                    'final_score': computed,
                    'graded_by': graded_by,
                    'graded_at': now,
                    'updated_at': now,
                },
            )
            # Preserve existing override
            if grade.override_score is not None:
                grade.final_score = grade.override_score
                grade.save(update_fields=['final_score'])

            final = grade.final_score or computed
            overall_weighted += (cat.weight or ZERO) * final
            overall_weight += (cat.weight or ZERO)

            category_scores.append({
                'category_id': cat.category_id,
                'category_name': cat.category_name,
                'weight': float(cat.weight),
                'computed_score': float(computed),
                'override_score': (
                    float(grade.override_score)
                    if grade.override_score is not None else None
                ),
                'final_score': float(final),
                'comments': grade.instructor_comments,
            })

        raw_overall = (
            overall_weighted / overall_weight if overall_weight else ZERO
        )
        raw_overall = min(max(raw_overall, ZERO), HUNDRED)

        team_data[team.id] = {
            'team': team,
            'category_scores': category_scores,
            'raw_overall': raw_overall,
        }

    # Phase 2: linear stretch across all teams
    raw_scores = {tid: d['raw_overall'] for tid, d in team_data.items()}
    stretched = _linear_stretch(raw_scores, grade_floor, grade_ceiling)

    # Phase 3: persist overall grades and build results
    results = []
    for tid, data in team_data.items():
        team = data['team']
        raw = data['raw_overall']
        final_overall = stretched.get(tid, raw)

        TeamGrade.objects.update_or_create(
            instance_id=instance_id,
            team_id=team.id,
            category_id=None,
            defaults={
                'computed_score': raw,
                'final_score': final_overall,
                'graded_by': graded_by,
                'graded_at': now,
                'updated_at': now,
            },
        )

        results.append({
            'team_id': team.id,
            'team_name': team.name,
            'categories': data['category_scores'],
            'raw_overall': float(raw),
            'overall': float(final_overall),
        })

    return results


def override_team_category_score(instance_id, team_id, category_id,
                                 override_score, comments=None,
                                 graded_by=None):
    """Instructor manually overrides a category score for a team."""
    grade, _ = TeamGrade.objects.update_or_create(
        instance_id=instance_id,
        team_id=team_id,
        category_id=category_id,
        defaults={
            'override_score': Decimal(str(override_score)),
            'final_score': Decimal(str(override_score)),
            'instructor_comments': comments,
            'graded_by': graded_by,
            'updated_at': timezone.now(),
        },
    )
    return grade


def clear_override(instance_id, team_id, category_id):
    """Remove an instructor override, reverting to computed score."""
    grade = TeamGrade.objects.filter(
        instance_id=instance_id,
        team_id=team_id,
        category_id=category_id,
    ).first()
    if grade:
        grade.override_score = None
        grade.final_score = grade.computed_score
        grade.updated_at = timezone.now()
        grade.save(update_fields=[
            'override_score', 'final_score', 'updated_at',
        ])
    return grade


def get_student_grades(instance_id, team_id=None):
    """
    Get individual student grades: team overall + adjustments.
    Returns list of {user_id, display_name, team_grade, adjustment, final}.
    """
    from core.models import User

    enrollments = Enrollment.objects.filter(
        section__simulation__instance_id=instance_id,
        is_active=True,
    )
    if team_id:
        enrollments = enrollments.filter(team_id=team_id)

    results = []
    for enr in enrollments:
        if not enr.team_id:
            continue

        team_overall = TeamGrade.objects.filter(
            instance_id=instance_id,
            team_id=enr.team_id,
            category_id__isnull=True,
        ).first()
        base = float(
            team_overall.final_score
        ) if team_overall and team_overall.final_score else 0.0

        adjustments = StudentGradeAdjustment.objects.filter(
            instance_id=instance_id, user_id=enr.user_id,
        )
        total_adj = sum(
            float(a.adjustment_value or 0) for a in adjustments
        )
        final = max(0.0, min(100.0, base + total_adj))

        user = User.objects.filter(user_id=enr.user_id).first()

        results.append({
            'user_id': enr.user_id,
            'display_name': user.display_name if user else None,
            'student_id': user.student_id if user else None,
            'team_id': enr.team_id,
            'team_grade': base,
            'adjustment': total_adj,
            'final_grade': final,
            'adjustments': [
                {
                    'adjustment_id': a.adjustment_id,
                    'type': a.adjustment_type,
                    'value': float(a.adjustment_value),
                    'reason': a.reason,
                }
                for a in adjustments
            ],
        })

    return results
