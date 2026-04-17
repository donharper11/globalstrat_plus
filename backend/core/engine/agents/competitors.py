"""
CC-32E: Competitor Agent — Wraps AI competitor fit score logic (CC-20).

The CompetitorAgent generates narrative about AI competitor movements.
Actual fit score calculation remains in bass_engine (called inline during adoption),
so this agent does NOT recalculate fit scores. Instead, it reads the current
competitor state from the snapshot and generates narrative + cross-agent reactions.
"""
import logging

from .base import AgentBase, AgentAction, StateSnapshot

logger = logging.getLogger('agent_orchestrator')


class CompetitorAgent(AgentBase):
    agent_class = "competitor"

    def evaluate(self, snapshot):
        """
        Propose fit score adjustment actions based on competitor state.
        These are informational — they record what the competitors did this round
        for narrative and cross-agent dependency purposes.
        """
        actions = []

        for comp_id, comp_data in snapshot.competitors.items():
            for market_code in comp_data.get('presence', {}):
                # Examine human team market shares in this market
                teams_in_market = snapshot.markets.get(market_code, {}).get('active_teams', [])

                # Determine competitive pressure level
                team_count = len(teams_in_market)
                strategy = comp_data.get('strategy', 'moderate')

                # Report current fit scores for narrative generation
                market_fits = {
                    k: v for k, v in comp_data.get('fit_scores', {}).items()
                    if k.startswith(market_code + '_')
                }

                if not market_fits:
                    continue

                avg_fit = sum(market_fits.values()) / len(market_fits) if market_fits else 0.4

                actions.append(AgentAction(
                    agent_class="competitor",
                    agent_id=comp_id,
                    action_type="adjust_fit",
                    target_team=None,
                    target_market=market_code,
                    parameters={
                        'avg_fit': round(avg_fit, 3),
                        'strategy': strategy,
                        'team_count': team_count,
                        'market_fits': market_fits,
                    },
                    priority=5,
                ))

        return actions

    def resolve_dependencies(self, own_actions, all_actions):
        """
        React to government tariff changes and alliance dissolutions.
        """
        # Check for government tariff changes
        tariff_changes = [
            a for a in all_actions
            if a.action_type == 'tariff_change'
        ]

        if not tariff_changes:
            return own_actions

        revised = []
        for action in own_actions:
            if action.action_type == 'adjust_fit':
                market = action.target_market
                tariff_delta = sum(
                    tc.parameters.get('delta', 0)
                    for tc in tariff_changes
                    if tc.target_market == market
                )
                if tariff_delta != 0:
                    # Higher tariffs reduce competitor fit in export markets
                    adjusted_fit = action.parameters['avg_fit'] - (tariff_delta * 0.5)
                    action.parameters['avg_fit'] = max(0.1, adjusted_fit)
                    action.parameters['tariff_adjusted'] = True
            revised.append(action)

        return revised

    def apply_actions(self, actions, game, round_obj):
        """
        Competitor fit scores are calculated inline during bass_engine adoption.
        This agent doesn't need to write fit scores — it's for narrative and
        cross-agent coordination only.
        """
        pass

    def get_narrative(self, actions):
        """Generate narrative items about competitor movements."""
        narratives = []

        # Group by competitor
        by_competitor = {}
        for action in actions:
            if action.action_type == 'adjust_fit':
                comp_id = action.agent_id
                if comp_id not in by_competitor:
                    by_competitor[comp_id] = []
                by_competitor[comp_id].append(action)

        for comp_id, comp_actions in by_competitor.items():
            # Find strongest and weakest markets
            best = max(comp_actions, key=lambda a: a.parameters.get('avg_fit', 0))
            worst = min(comp_actions, key=lambda a: a.parameters.get('avg_fit', 0))

            best_fit = best.parameters.get('avg_fit', 0)
            worst_fit = worst.parameters.get('avg_fit', 0)
            strategy = best.parameters.get('strategy', 'moderate')

            if best_fit > 0.6:
                narratives.append({
                    'type': 'competitive',
                    'priority': 'medium',
                    'text': (
                        f"AI competitor is strengthening position in {best.target_market} "
                        f"({strategy} strategy, avg fit {best_fit:.0%})"
                    ),
                    'market': best.target_market,
                    'agent_class': 'competitor',
                })

            if worst_fit < 0.3 and worst.target_market != best.target_market:
                narratives.append({
                    'type': 'competitive',
                    'priority': 'low',
                    'text': (
                        f"AI competitor struggling in {worst.target_market} "
                        f"(avg fit {worst_fit:.0%})"
                    ),
                    'market': worst.target_market,
                    'agent_class': 'competitor',
                })

            # Tariff adjustment narrative
            tariff_adjusted = [
                a for a in comp_actions
                if a.parameters.get('tariff_adjusted')
            ]
            if tariff_adjusted:
                markets = ', '.join(a.target_market for a in tariff_adjusted)
                narratives.append({
                    'type': 'competitive',
                    'priority': 'medium',
                    'text': f"AI competitor adjusting strategy in {markets} due to tariff changes",
                    'agent_class': 'competitor',
                })

        return narratives
