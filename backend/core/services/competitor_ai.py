"""
Competitor AI: Personality-driven competitors with market-reactive behavior.

Each competitor has a distinct archetype that determines how they grow ESG
scores and react to team performance each round.

TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
The Competitor and ESGScorecard models have been deleted. All function bodies
are commented out but signatures are preserved for callers.
"""
import logging
import random
from decimal import Decimal

from django.db.models import Max

# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# from core.models import Competitor, ESGScorecard, Team
from core.models import Team

logger = logging.getLogger(__name__)

# Map between DB key names and internal short keys
_PILLAR_KEYS = {
    'Environmental': 'E', 'Social': 'S', 'Governance': 'G',
    'E': 'E', 'S': 'S', 'G': 'G',
}
_PILLAR_DB_KEYS = ['Environmental', 'Social', 'Governance']
_SHORT_TO_DB = {'E': 'Environmental', 'S': 'Social', 'G': 'Governance'}
_SHORT_TO_FIELD = {
    'E': 'environmental_score',
    'S': 'social_score',
    'G': 'governance_score',
}

# ---------------------------------------------------------------------------
# Personality definitions keyed by competitor_id
# ---------------------------------------------------------------------------
COMPETITOR_PERSONALITIES = {
    3: {
        'archetype': 'aggressive',
        'name': 'EcoChamp',
        'focus_pillar': 'E',
        'base_growth': (0.02, 0.04),
        'reactive_growth': (0.04, 0.07),
        'description': (
            'Environmental Aggressive — pushes hard on Environmental. '
            'Accelerates if any team leads in Environmental ESG.'
        ),
    },
    4: {
        'archetype': 'cost_minimizer',
        'name': 'ProfitMax Inc.',
        'focus_pillar': 'G',
        'base_growth': (0.01, 0.03),
        'reactive_growth': (0.02, 0.04),
        'description': (
            'Governance Cost-Minimizer — cheap compliance focus. '
            'Shifts weight toward weakest pillar if falling behind industry average.'
        ),
    },
    5: {
        'archetype': 'champion',
        'name': 'PeopleFirst Solutions',
        'focus_pillar': 'S',
        'base_growth': (0.02, 0.05),
        'reactive_growth': (0.04, 0.06),
        'description': (
            'Social Champion — strong Social focus. '
            'Accelerates Social if a team dominates it; slowly improves weakest pillar.'
        ),
    },
    6: {
        'archetype': 'balanced',
        'name': 'SustainBalance Co.',
        'focus_pillar': None,
        'base_growth': (0.02, 0.04),
        'reactive_growth': (0.03, 0.05),
        'description': (
            'Balanced Leader — highest total score, even approach. '
            'Mirrors the leading team by shifting toward their strongest pillar.'
        ),
    },
}


def _normalise_priorities(raw):
    """
    Convert esg_priority JSONB to normalised {E: weight, S: weight, G: weight}.
    """
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    if not raw:
        return {'E': 0.33, 'S': 0.33, 'G': 0.34}

    result = {}
    total = 0
    for key, val in raw.items():
        short = _PILLAR_KEYS.get(key, key)
        fval = float(val)
        result[short] = fval
        total += fval

    if total > 0:
        result = {k: v / total for k, v in result.items()}

    for p in ('E', 'S', 'G'):
        result.setdefault(p, 0.33)

    return result


def _to_db_priorities(normalised, total_score):
    """Convert normalised weights back to DB format (integer percentages)."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return {
        'Environmental': round(normalised.get('E', 0.33) * 100),
        'Social': round(normalised.get('S', 0.33) * 100),
        'Governance': round(normalised.get('G', 0.34) * 100),
    }


def _get_team_esg_leaders(round_number=None):
    """
    Query ESGScorecard to find the maximum team score per pillar.
    """
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # ESGScorecard model deleted — return zeroes
    # qs = ESGScorecard.objects.all()
    # ...
    return {'E': 0, 'S': 0, 'G': 0, 'avg_total': 0}


# ---------------------------------------------------------------------------
# Personality-specific behavior functions
# ---------------------------------------------------------------------------

def _apply_aggressive(competitor, weights, current_total, personality, leaders):
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted
    return 0, weights


def _apply_cost_minimizer(competitor, weights, current_total, personality, leaders):
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted
    return 0, weights


def _apply_champion(competitor, weights, current_total, personality, leaders):
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted
    return 0, weights


def _apply_balanced(competitor, weights, current_total, personality, leaders):
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted
    return 0, weights


# Map archetype names to behavior functions
_ARCHETYPE_HANDLERS = {
    'aggressive': _apply_aggressive,
    'cost_minimizer': _apply_cost_minimizer,
    'champion': _apply_champion,
    'balanced': _apply_balanced,
}


def _apply_default(competitor, weights, current_total, leaders):
    """Fallback: original 2-5% random growth, no personality."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted
    return 0, weights


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate_competitor_round(competitor_id, round_id, team_esg_leaders=None):
    """
    Simulate one round for a competitor using their personality archetype.
    """
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted — no-op
    # try:
    #     competitor = Competitor.objects.get(pk=competitor_id)
    # except Competitor.DoesNotExist:
    #     return
    # ...
    pass


def simulate_all_competitors(round_id):
    """
    Run AI simulation for all competitors.
    """
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted — no-op
    # team_esg_leaders = _get_team_esg_leaders()
    # for competitor in Competitor.objects.all():
    #     simulate_competitor_round(...)
    pass


def calculate_industry_benchmark(round_id):
    """
    Average all competitors' ESG scores to produce industry benchmark.
    Returns dict {E: avg, S: avg, G: avg}.
    """
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Competitor model deleted — return zeroes
    # competitors = Competitor.objects.all()
    # ...
    return {'E': 0, 'S': 0, 'G': 0}
