"""
Gamification Engine
Evaluates achievements and badges, computes QICOIN totals.
"""
from django.utils import timezone
from django.db import connection

from core.models import (
    Achievement, GamificationBadge, TeamAchievement, TeamBadge,
    TeamIncomeStatement,
    TeamPerformance,
    Program,
)
# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# Removed: ESGScorecard, TeamCodeOfEthics

# QICOIN reward values — must match seed_gamification data
ACHIEVEMENT_COINS = {
    'First Revenue': 50,
    'Revenue Milestone: $100K': 200,
    'Revenue Milestone: $500K': 500,
    'Triple Crown': 150,
    'ESG Leader': 300,
    'Segment Champion': 250,
    'Ethical Compass': 200,
    'Ethics Architect': 500,
    'B-Corp Certified': 1000,
    'Market Mover': 200,
    'Program Diversifier': 150,
}

BADGE_COINS = {
    'ESG Champion': 100,
    'Revenue Growth': 75,
    'Environmental Excellence': 50,
    'Social Excellence': 50,
    'Governance Excellence': 50,
}


def _get_cumulative_revenue(team_id):
    """Sum all revenue from team_income_statements."""
    from django.db.models import Sum
    result = TeamIncomeStatement.objects.filter(
        team_id=team_id
    ).aggregate(total=Sum('revenue'))
    return float(result['total'] or 0)


def _get_distinct_program_type_count(team_id):
    """Count distinct active program types for a team."""
    return Program.objects.filter(
        team_id=team_id, status='Active'
    ).values('program_type_id').distinct().count()


def _check_achievement(name, team_id, team_result, bcorp_summary, ethics_summary):
    """Check if a single achievement criteria is met. Returns bool."""
    esg = team_result.get('esg', {})
    e_score = esg.get('E', 0)
    s_score = esg.get('S', 0)
    g_score = esg.get('G', 0)

    if name == 'First Revenue':
        return team_result.get('revenue', 0) > 0

    elif name == 'Revenue Milestone: $100K':
        return _get_cumulative_revenue(team_id) >= 100_000

    elif name == 'Revenue Milestone: $500K':
        return _get_cumulative_revenue(team_id) >= 500_000

    elif name == 'Triple Crown':
        return e_score > 0 and s_score > 0 and g_score > 0

    elif name == 'ESG Leader':
        return (e_score + s_score + g_score) >= 150

    elif name == 'Segment Champion':
        perf = TeamPerformance.objects.filter(team_id=team_id).first()
        if perf and perf.average_stakeholder_satisfaction is not None:
            return float(perf.average_stakeholder_satisfaction) >= 0.60
        return False

    elif name == 'Ethical Compass':
        team_ethics = ethics_summary.get(team_id, {})
        alignment = team_ethics.get('ethical_alignment')
        if alignment is not None:
            return alignment >= 70
        return False

    elif name == 'Ethics Architect':
        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        return False

    elif name == 'B-Corp Certified':
        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        return False

    elif name == 'Market Mover':
        return team_result.get('total_units', 0) >= 500

    elif name == 'Program Diversifier':
        return _get_distinct_program_type_count(team_id) >= 3

    return False


def _check_badge(name, team_id, round_id, team_result, all_team_results):
    """Check if a single badge criteria is met for this round. Returns bool."""
    esg = team_result.get('esg', {})
    e_score = esg.get('E', 0)
    s_score = esg.get('S', 0)
    g_score = esg.get('G', 0)
    esg_total = e_score + s_score + g_score

    if name == 'ESG Champion':
        # Highest ESG total among all teams this round
        for other_tid, other_result in all_team_results.items():
            if other_tid == team_id:
                continue
            other_esg = other_result.get('esg', {})
            other_total = sum(other_esg.values())
            if other_total > esg_total:
                return False
        # Must have at least some ESG score
        return esg_total > 0

    elif name == 'Revenue Growth':
        current_rev = team_result.get('revenue', 0)
        # Get previous round revenue
        prev_income = TeamIncomeStatement.objects.filter(
            team_id=team_id
        ).exclude(round_id=round_id).order_by('-statement_id').first()
        prev_rev = float(prev_income.revenue or 0) if prev_income else 0
        return current_rev > prev_rev and current_rev > 0

    elif name == 'Environmental Excellence':
        return e_score >= 80

    elif name == 'Social Excellence':
        return s_score >= 80

    elif name == 'Governance Excellence':
        return g_score >= 80

    return False


def evaluate_achievements(team_id, round_id, team_result, bcorp_summary, ethics_summary):
    """
    Check each achievement for the team, skip already-earned,
    create TeamAchievement rows for newly earned ones.
    Returns list of newly awarded achievement names.
    """
    achievements = Achievement.objects.all()
    already_earned = set(
        TeamAchievement.objects.filter(team_id=team_id)
        .values_list('achievement_id', flat=True)
    )

    newly_awarded = []
    now = timezone.now()

    for ach in achievements:
        if ach.achievement_id in already_earned:
            continue

        if _check_achievement(ach.achievement_name, team_id, team_result, bcorp_summary, ethics_summary):
            TeamAchievement.objects.create(
                team_id=team_id,
                achievement_id=ach.achievement_id,
                round_id=round_id,
                created_at=now,
            )
            newly_awarded.append(ach.achievement_name)

    return newly_awarded


def evaluate_badges(team_id, round_id, team_result, all_team_results):
    """
    Check each badge for the team this round, skip same badge+team+round duplicates,
    create TeamBadge rows for newly earned ones.
    Returns list of newly awarded badge names.
    """
    badges = GamificationBadge.objects.all()
    already_this_round = set(
        TeamBadge.objects.filter(team_id=team_id, round_id=round_id)
        .values_list('badge_id', flat=True)
    )

    newly_awarded = []
    now = timezone.now()

    for badge in badges:
        if badge.badge_id in already_this_round:
            continue

        if _check_badge(badge.badge_name, team_id, round_id, team_result, all_team_results):
            TeamBadge.objects.create(
                team_id=team_id,
                badge_id=badge.badge_id,
                round_id=round_id,
                created_at=now,
            )
            newly_awarded.append(badge.badge_name)

    return newly_awarded


def calculate_qicoin(team_id):
    """
    Compute QICOIN total by summing rewards from earned achievements + badges.
    QICOIN is computed (not stored) — no DB column needed.
    Returns dict with qicoin_total and breakdown list.
    """
    breakdown = []

    # Achievement rewards
    team_achievements = TeamAchievement.objects.filter(team_id=team_id)
    achievement_ids = [ta.achievement_id for ta in team_achievements]
    achievements = {
        a.achievement_id: a.achievement_name
        for a in Achievement.objects.filter(achievement_id__in=achievement_ids)
    }

    for ta in team_achievements:
        name = achievements.get(ta.achievement_id, 'Unknown')
        coins = ACHIEVEMENT_COINS.get(name, 0)
        breakdown.append({
            'type': 'achievement',
            'name': name,
            'coins': coins,
            'round_id': ta.round_id,
        })

    # Badge rewards (badges can be earned multiple times across rounds)
    team_badges = TeamBadge.objects.filter(team_id=team_id)
    badge_ids = set(tb.badge_id for tb in team_badges)
    badge_names = {
        b.badge_id: b.badge_name
        for b in GamificationBadge.objects.filter(badge_id__in=badge_ids)
    }

    for tb in team_badges:
        name = badge_names.get(tb.badge_id, 'Unknown')
        coins = BADGE_COINS.get(name, 0)
        breakdown.append({
            'type': 'badge',
            'name': name,
            'coins': coins,
            'round_id': tb.round_id,
        })

    qicoin_total = sum(item['coins'] for item in breakdown)

    return {
        'qicoin_total': qicoin_total,
        'breakdown': breakdown,
    }


def process_gamification(teams, round_id, round_number, team_results, bcorp_summary, ethics_summary):
    """
    Top-level orchestrator called by round_engine after leaderboard step.
    Evaluates achievements and badges for all teams.
    Returns summary dict.
    """
    summary = {}

    for team in teams:
        tid = team.team_id
        team_result = team_results.get(tid, {})

        new_achievements = evaluate_achievements(
            tid, round_id, team_result, bcorp_summary, ethics_summary
        )
        new_badges = evaluate_badges(
            tid, round_id, team_result, team_results
        )

        qicoin = calculate_qicoin(tid)

        summary[tid] = {
            'new_achievements': new_achievements,
            'new_badges': new_badges,
            'qicoin_total': qicoin['qicoin_total'],
        }

    return summary
