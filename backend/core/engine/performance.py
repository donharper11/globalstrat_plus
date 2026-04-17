"""
Engine Step 13: Performance Index Calculation.
From 03-engine-logic.md Section 12.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.scenario import SegmentDefinition, MarketDefinition
from core.models.team_state import TeamMarketPresence
from core.models.results_financials import RoundResultPerformanceIndex
from core.engine.utils import get_config

D = Decimal


def calculate_performance_index(context):
    """
    For each team:
    1. Sum weighted satisfaction across all segments
    2. satisfaction_score = weighted_sum / total_weight (0-1)
    3. index_change = (satisfaction - 0.5) × sensitivity
    4. new_index = previous_index + index_change, clamped >= 0
    """
    scenario = context.scenario
    current_round = context.round_number
    sensitivity = D(str(get_config(scenario, 'performance_index_sensitivity', default=20.0)))

    all_markets = MarketDefinition.objects.filter(scenario=scenario)
    all_segments = SegmentDefinition.objects.filter(scenario=scenario)

    for team in context.teams:
        # Get markets where team has active presence
        active_market_ids = set(
            TeamMarketPresence.objects.filter(
                team=team, status='active',
            ).values_list('market_id', flat=True)
        )

        weighted_satisfaction = D('0')
        total_weight = D('0')

        for segment in all_segments:
            weight = segment.performance_index_weight
            if weight <= 0:
                continue

            market = segment.market
            if market is None:
                # Global segment — use global fit score
                key = (team.id, segment.id, None)
                fit = D(str(context.fit_scores.get(key, 0.0)))
                fit = D(str(context.adjusted_fit_scores.get(key, fit)))
            elif market.id in active_market_ids:
                key = (team.id, segment.id, market.id)
                fit = D(str(context.fit_scores.get(key, 0.0)))
                fit = D(str(context.adjusted_fit_scores.get(key, fit)))
            else:
                # Not present in market — skip customer segments entirely
                # (team isn't competing there, so those segments shouldn't
                # factor into their performance score). Non-customer segments
                # in absent markets get neutral score.
                if segment.segment_type == 'customer':
                    continue
                fit = D('0.5')

            weighted_satisfaction += fit * weight
            total_weight += weight

        if total_weight == 0:
            satisfaction_score = D('0.5')
        else:
            satisfaction_score = (weighted_satisfaction / total_weight).quantize(
                D('0.0001'), rounding=ROUND_HALF_UP,
            )

        index_change = ((satisfaction_score - D('0.5')) * sensitivity).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        previous_index = team.performance_index
        new_index = max(D('0'), previous_index + index_change)

        # Update team
        team.performance_index = new_index
        team.save()

        # Write result
        RoundResultPerformanceIndex.objects.update_or_create(
            game=context.game, round_number=current_round, team=team,
            defaults={
                'satisfaction_score': satisfaction_score,
                'index_change': index_change,
                'index_value': new_index,
            },
        )

        context.log.append(
            f'Performance index: {team.name} '
            f'{previous_index} → {new_index} '
            f'({"+" if index_change >= 0 else ""}{index_change})'
        )
