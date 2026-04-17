"""
Three-Layer Scoring Engine
Layer 1: Preference Alignment
Layer 2: Relative Attractiveness (Competitive Share)
Layer 3: Bass Diffusion Adoption
"""
from decimal import Decimal
from django.db.models import Sum

from core.models import (
    ProgramFeature, ProgramPortfolio, Program,
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Removed: Feature, SegmentPreference, Segment, CumulativeSegmentEngagement
    Score, ScoreType,
    Team,
    NewSalesByRound,
)

ZERO = Decimal('0')
ONE = Decimal('1')


def _get_team_feature_values(team_id, round_id):
    """Get aggregated feature values for a team's active programs."""
    active_programs = Program.objects.filter(
        team_id=team_id, status='Active'
    ).values_list('program_id', flat=True)

    portfolios = ProgramPortfolio.objects.filter(
        program_id__in=active_programs, status='Active'
    ).values_list('program_portfolio_id', flat=True)

    features = ProgramFeature.objects.filter(
        program_portfolio_id__in=portfolios
    ).values('feature_id').annotate(
        avg_value=Sum('feature_value') / Decimal(str(max(len(active_programs), 1)))
    )

    return {f['feature_id']: f['avg_value'] or ZERO for f in features}


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def _get_team_media_values(team_id):
#     """Get media allocation values for a team's active programs."""
#     active_programs = Program.objects.filter(
#         team_id=team_id, status='Active'
#     ).values_list('program_id', flat=True)
#
#     media = ProgramMedia.objects.filter(
#         program_id__in=active_programs
#     ).values('media_type_id').annotate(total_budget=Sum('budget_allocated'))
#
#     return {m['media_type_id']: m['total_budget'] or ZERO for m in media}


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def _get_team_geography_values(team_id):
#     """Get geography focus values for a team's active programs."""
#     active_programs = Program.objects.filter(
#         team_id=team_id, status='Active'
#     ).values_list('program_id', flat=True)
#
#     geo = ProgramGeography.objects.filter(
#         program_id__in=active_programs
#     ).values('focus_id').annotate(total_level=Sum('focus_level'))
#
#     return {g['focus_id']: g['total_level'] or ZERO for g in geo}


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def _get_team_resource_values(team_id):
#     """Get resource allocation values for a team's active programs."""
#     active_programs = Program.objects.filter(
#         team_id=team_id, status='Active'
#     ).values_list('program_id', flat=True)
#
#     resources = ProgramResource.objects.filter(
#         program_id__in=active_programs
#     ).values('resource_type_id').annotate(total_value=Sum('resource_value'))
#
#     return {r['resource_type_id']: r['total_value'] or ZERO for r in resources}


def calculate_alignment(team_id, segment_id, round_id):
    """
    Layer 1: Calculate preference alignment between a team and a stakeholder.
    Returns float 0.0-1.0.
    """
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # SegmentPreference and Feature models removed — stub returning 0.0
    return 0.0


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def _calculate_secondary_bonus(team_id, segment_id):
#     """Calculate secondary alignment bonuses from media/geography/resource matches."""
#     bonuses = []
#
#     # Media preferences
#     media_prefs = StakeholderMediaPref.objects.filter(segment_id=segment_id)
#     if media_prefs.exists():
#         team_media = _get_team_media_values(team_id)
#         if team_media:
#             media_match = sum(
#                 1 for mp in media_prefs if mp.media_type_id in team_media
#             ) / media_prefs.count()
#             bonuses.append(media_match)
#
#     # Geography preferences
#     geo_prefs = StakeholderGeographyPref.objects.filter(segment_id=segment_id)
#     if geo_prefs.exists():
#         team_geo = _get_team_geography_values(team_id)
#         if team_geo:
#             geo_match = sum(
#                 1 for gp in geo_prefs if gp.focus_id in team_geo
#             ) / geo_prefs.count()
#             bonuses.append(geo_match)
#
#     # Resource preferences
#     res_prefs = StakeholderResourcePref.objects.filter(segment_id=segment_id)
#     if res_prefs.exists():
#         team_res = _get_team_resource_values(team_id)
#         if team_res:
#             res_match = sum(
#                 1 for rp in res_prefs if rp.resource_type_id in team_res
#             ) / res_prefs.count()
#             bonuses.append(res_match)
#
#     if not bonuses:
#         return 0.0
#     return sum(bonuses) / len(bonuses)


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def apply_benchmark_modifier(team_id, round_id):
#     """
#     Compare team ESG vs competitor industry benchmark.
#     Returns multiplier: 1.1 if above, 0.9 if below, 1.0 if equal.
#     """
#     from core.services.competitor_ai import calculate_industry_benchmark
#
#     scorecard = ESGScorecard.objects.filter(team_id=team_id).order_by('-round_number').first()
#     if not scorecard:
#         return 1.0
#
#     team_total = (
#         (scorecard.environmental_score or 0) +
#         (scorecard.social_score or 0) +
#         (scorecard.governance_score or 0)
#     )
#
#     benchmark = calculate_industry_benchmark(round_id)
#     benchmark_total = sum(benchmark.values())
#
#     if benchmark_total == 0:
#         return 1.0
#     if team_total > benchmark_total:
#         return 1.1
#     if team_total < benchmark_total:
#         return 0.9
#     return 1.0


def apply_benchmark_modifier(team_id, round_id):
    """Stub — benchmark modifier disabled pending new engine logic."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return 1.0


def calculate_relative_attractiveness(segment_id, round_id):
    """
    Layer 2: Calculate each team's share of a stakeholder's attention.
    Returns dict {team_id: share (0-1)}.
    """
    teams = Team.objects.all()
    alignments = {}

    for team in teams:
        alignment = calculate_alignment(team.team_id, segment_id, round_id)
        modifier = apply_benchmark_modifier(team.team_id, round_id)
        alignments[team.team_id] = alignment * modifier

    total = sum(alignments.values())
    if total == 0:
        # Equal share if no alignment data
        n = len(alignments)
        return {tid: 1.0 / n for tid in alignments} if n else {}

    return {tid: v / total for tid, v in alignments.items()}


def calculate_bass_adoption(segment_id, round_id, economy_id):
    """
    Layer 3: Bass diffusion model.
    Returns total new adopters for this round.

    Formula: new_adopters = [p + q * (N/M)] * [M - N]
    """
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Original code used StakeholderEngagementPotential and Customer/CustomerMarketPotentialByRound
    # as fallback. Both StakeholderEngagementPotential and Customer models are deleted.
    # For now, use cumulative stakeholder engagement as a simple proxy.

    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # StakeholderEngagementPotential, CumulativeSegmentEngagement models removed

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Fallback: try customer_market_potential (Customer model deleted)
    # from core.models import Customer
    # customer = Customer.objects.filter(segment_id=segment_id).first()
    # if not customer:
    #     return 0.0
    # cmp = CustomerMarketPotentialByRound.objects.filter(
    #     customer_id=customer.customer_id, round_id=round_id
    # ).first()
    # ...

    return 0.0


def distribute_adoption(segment_id, round_id, economy_id):
    """
    Combine attractiveness shares with total new adopters.
    Returns dict {team_id: captured_adopters (int)}.
    """
    total_new = calculate_bass_adoption(segment_id, round_id, economy_id)
    if total_new <= 0:
        return {}

    shares = calculate_relative_attractiveness(segment_id, round_id)
    return {
        tid: int(round(total_new * share))
        for tid, share in shares.items()
        if share > 0
    }


def rollup_esg_scores(team_id, round_id):
    """
    Map features to ESG pillars via feature_esg_mapping.
    Program types: 1=Environmental, 2=Social, 3=Governance.
    Types 4-9 map through feature_esg_mapping.
    Returns dict {E: score, S: score, G: score}.
    """
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Feature model removed — stub returning zeroes
    return {'E': 0, 'S': 0, 'G': 0}


# ---------------------------------------------------------------------------
# SDG Coverage
# ---------------------------------------------------------------------------

# Segment IDs that receive SDG breadth bonus
# NGOs (2), Local Communities (5), Government (6), Planetary Guardians (7)
SDG_BONUS_STAKEHOLDERS = {2, 5, 6, 7}


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def calculate_sdg_coverage(team_id, instance_id, round_number):
#     """
#     Calculate distinct SDGs covered by a team's active programs.
#     A feature only counts if its normalized value >= 30%.
#     Writes results to team_sdg_coverage table.
#     Returns count of distinct SDGs covered.
#     """
#     active_programs = Program.objects.filter(
#         team_id=team_id, instance_id=instance_id, status='Active',
#     ).values_list('program_id', flat=True)
#
#     portfolios = ProgramPortfolio.objects.filter(
#         program_id__in=active_programs, status='Active',
#     ).values_list('program_portfolio_id', flat=True)
#
#     program_features = ProgramFeature.objects.filter(
#         program_portfolio_id__in=portfolios,
#     )
#
#     all_feature_ids = program_features.values_list('feature_id', flat=True).distinct()
#     feature_ranges = {}
#     for f in Feature.objects.filter(feature_id__in=all_feature_ids):
#         range_f = float(f.max_value - f.min_value) if f.max_value is not None and f.min_value is not None else 0
#         feature_ranges[f.feature_id] = (float(f.min_value if f.min_value is not None else 0), range_f)
#
#     qualifying_ids = set()
#     for pf in program_features:
#         min_val, range_f = feature_ranges.get(pf.feature_id, (0, 0))
#         if range_f <= 0:
#             continue
#         normalized = (float(pf.feature_value or 0) - min_val) / range_f
#         if normalized >= 0.30:
#             qualifying_ids.add(pf.feature_id)
#
#     sdg_coverage = FeatureSdgMapping.objects.filter(
#         feature_id__in=qualifying_ids,
#     ).values('sdg_id').annotate(
#         total_weight=Sum('relevance_weight'),
#     )
#
#     for entry in sdg_coverage:
#         TeamSdgCoverage.objects.update_or_create(
#             team_id=team_id,
#             instance_id=instance_id,
#             round_number=round_number,
#             sdg_id=entry['sdg_id'],
#             defaults={'coverage_score': entry['total_weight']},
#         )
#
#     return sdg_coverage.count()


def calculate_sdg_coverage(team_id, instance_id, round_number):
    """Stub — SDG coverage disabled pending new engine logic."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return 0


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def get_sdg_alignment_bonus(team_id, instance_id, segment_id):
#     ...
def get_sdg_alignment_bonus(team_id, instance_id, segment_id):
    """Stub — SDG alignment bonus disabled pending new engine logic."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return 1.0


# ---------------------------------------------------------------------------
# Scope 1/2/3 Carbon Decomposition
# ---------------------------------------------------------------------------

# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def calculate_scope_scores(team_id, instance_id, round_number):
#     """
#     Decompose environmental score into Scope 1/2/3 sub-scores.
#     Uses the same 30% normalized threshold as SDG coverage.
#     Writes results to team_scope_scores table.
#     Returns dict {scope_number: score}.
#     """
#     active_programs = Program.objects.filter(
#         team_id=team_id, instance_id=instance_id, status='Active',
#     ).values_list('program_id', flat=True)
#
#     portfolios = ProgramPortfolio.objects.filter(
#         program_id__in=active_programs, status='Active',
#     ).values_list('program_portfolio_id', flat=True)
#
#     program_features = ProgramFeature.objects.filter(
#         program_portfolio_id__in=portfolios,
#     )
#
#     all_feature_ids = program_features.values_list('feature_id', flat=True).distinct()
#     feature_ranges = {}
#     for f in Feature.objects.filter(feature_id__in=all_feature_ids):
#         range_f = float(f.max_value - f.min_value) if f.max_value is not None and f.min_value is not None else 0
#         feature_ranges[f.feature_id] = (float(f.min_value if f.min_value is not None else 0), range_f)
#
#     qualifying = {}
#     for pf in program_features:
#         min_val, range_f = feature_ranges.get(pf.feature_id, (0, 0))
#         if range_f <= 0:
#             continue
#         normalized = (float(pf.feature_value or 0) - min_val) / range_f
#         if pf.feature_id not in qualifying or normalized > qualifying[pf.feature_id]:
#             qualifying[pf.feature_id] = normalized
#
#     result = {}
#     for scope in EmissionScope.objects.all():
#         mappings = FeatureScopeMapping.objects.filter(
#             feature_id__in=qualifying.keys(),
#             scope_id=scope.scope_id,
#         )
#         if mappings.exists():
#             total = sum(
#                 qualifying[m.feature_id] * float(m.impact_factor)
#                 for m in mappings
#             )
#             score = total / mappings.count() * 100
#         else:
#             score = 0
#
#         score = round(min(score, 100), 2)
#
#         TeamScopeScore.objects.update_or_create(
#             team_id=team_id,
#             instance_id=instance_id,
#             round_number=round_number,
#             scope_id=scope.scope_id,
#             defaults={'score': score},
#         )
#         result[scope.scope_number] = score
#
#     return result


def calculate_scope_scores(team_id, instance_id, round_number):
    """Stub — scope scores disabled pending new engine logic."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return {}


# ---------------------------------------------------------------------------
# Regulatory Framework Compliance
# ---------------------------------------------------------------------------

# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def check_framework_compliance(team_id, instance_id, round_number):
#     """
#     Check if a team meets their adopted framework's requirements.
#     """
#     ...


def check_framework_compliance(team_id, instance_id, round_number):
    """Stub — framework compliance disabled pending new engine logic."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return None


# ---------------------------------------------------------------------------
# Supply Chain Modifiers
# ---------------------------------------------------------------------------

# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def get_supplier_modifiers(team_id, instance_id):
#     """
#     Calculate supplier-based modifiers for a team's active programs.
#     """
#     active_programs = Program.objects.filter(
#         team_id=team_id, status='Active',
#     ).values_list('program_id', flat=True)
#
#     assignments = ProgramSupplier.objects.filter(
#         program_id__in=active_programs, is_active=True,
#     ).select_related('supplier')
#
#     if instance_id is not None:
#         assignments = assignments.filter(instance_id=instance_id)
#
#     if not assignments.exists():
#         return {
#             'cost_multiplier': 1.0,
#             'scope3_modifier': 1.0,
#             'ethics_modifier': 1.0,
#         }
#
#     multipliers = []
#     env_scores = []
#     eth_scores = []
#     for a in assignments:
#         multipliers.append(float(a.supplier.cost_multiplier))
#         env_scores.append(a.supplier.environmental_score)
#         eth_scores.append(a.supplier.ethics_score)
#
#     avg_cost = sum(multipliers) / len(multipliers)
#     avg_env = sum(env_scores) / len(env_scores) / 100.0
#     avg_eth = sum(eth_scores) / len(eth_scores) / 100.0
#
#     return {
#         'cost_multiplier': round(avg_cost, 4),
#         'scope3_modifier': round(0.5 + 0.5 * avg_env, 4),
#         'ethics_modifier': round(avg_eth, 4),
#     }


def get_supplier_modifiers(team_id, instance_id):
    """Stub — supplier modifiers disabled pending new engine logic."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    return {
        'cost_multiplier': 1.0,
        'scope3_modifier': 1.0,
        'ethics_modifier': 1.0,
    }
