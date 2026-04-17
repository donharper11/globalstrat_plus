"""
CC-32E: Alliance Agent — Wraps CC-32D alliance satisfaction logic.

Alliance benefit delivery and status updates run at Step 4.7 (before costs/revenue)
via alliance_engine.process_alliances(). This agent participates in the orchestrator's
convergence loop for cross-agent effects (investor pressure, government actions)
and generates narrative about alliance health changes.
"""
import logging

from .base import AgentBase, AgentAction, StateSnapshot

logger = logging.getLogger('agent_orchestrator')


class AllianceAgent(AgentBase):
    agent_class = "alliance"

    def evaluate(self, snapshot):
        """
        Read alliance state from snapshot and propose satisfaction update actions.
        These reflect the current state (already computed at Step 4.7) for
        cross-agent coordination.
        """
        actions = []

        for alliance_key, alliance_data in snapshot.alliances.items():
            if alliance_data['status'] == 'DISSOLVED':
                continue

            satisfaction = alliance_data['satisfaction']
            status = alliance_data['status']

            actions.append(AgentAction(
                agent_class="alliance",
                agent_id=alliance_key,
                action_type="update_satisfaction",
                target_team=alliance_data['team_id'],
                target_market=alliance_data['market_code'],
                parameters={
                    'new_satisfaction': satisfaction,
                    'feature_scores': alliance_data.get('feature_satisfaction', {}),
                    'status_recommendation': status,
                    'partner_name': alliance_data['partner_name'],
                    'partner_type': alliance_data['partner_type'],
                    'benefit_delivery_pct': alliance_data['benefit_delivery_pct'],
                },
                priority=4,
            ))

            # If dissolving, signal potential partner defection
            if status == 'DISSOLVING':
                actions.append(AgentAction(
                    agent_class="alliance",
                    agent_id=alliance_key,
                    action_type="partner_defection",
                    target_team=None,
                    target_market=alliance_data['market_code'],
                    parameters={
                        'partner_name': alliance_data['partner_name'],
                        'partner_type': alliance_data['partner_type'],
                    },
                    priority=7,
                    dependencies=['adjust_fit'],
                ))

        return actions

    def resolve_dependencies(self, own_actions, all_actions):
        """
        Investor sells → partner worried → satisfaction perception drops.
        Government instability signals could also affect alliance confidence.
        """
        investor_sells = [
            a for a in all_actions
            if a.action_type == 'trade_shares'
            and a.parameters.get('direction') == 'SELL'
            and a.parameters.get('shares', 0) > 3000
        ]

        if not investor_sells:
            return own_actions

        teams_under_pressure = set(a.target_team for a in investor_sells)

        revised = []
        for action in own_actions:
            if (action.action_type == 'update_satisfaction'
                    and action.target_team in teams_under_pressure):
                current_sat = action.parameters.get('new_satisfaction', 0.5)
                action.parameters['new_satisfaction'] = current_sat * 0.95
                action.parameters['investor_pressure_applied'] = True
            revised.append(action)

        return revised

    def apply_actions(self, actions, game, round_obj):
        """
        Alliance processing already runs at Step 4.7. This agent's apply
        is a no-op — cross-agent effects are informational for narrative.
        """
        pass

    def get_narrative(self, actions):
        """Generate narrative items about alliance status changes."""
        narratives = []

        for action in actions:
            if action.action_type == 'update_satisfaction':
                status = action.parameters.get('status_recommendation', 'HEALTHY')
                partner_name = action.parameters.get('partner_name', 'Partner')
                satisfaction = action.parameters.get('new_satisfaction', 0.5)
                market = action.target_market

                if status in ('RENEGOTIATING', 'DISSOLVING'):
                    narratives.append({
                        'type': 'alliance',
                        'priority': 'high',
                        'text': (
                            f"{partner_name} partnership {status.lower()} in {market} "
                            f"(satisfaction {satisfaction:.0%})"
                        ),
                        'market': market,
                        'team_id': action.target_team,
                        'agent_class': 'alliance',
                    })
                elif status == 'STRAINED':
                    narratives.append({
                        'type': 'alliance',
                        'priority': 'medium',
                        'text': (
                            f"{partner_name} partnership strained in {market} "
                            f"(satisfaction {satisfaction:.0%})"
                        ),
                        'market': market,
                        'team_id': action.target_team,
                        'agent_class': 'alliance',
                    })

                if action.parameters.get('investor_pressure_applied'):
                    narratives.append({
                        'type': 'alliance',
                        'priority': 'medium',
                        'text': (
                            f"{partner_name} concerned about investor confidence in team"
                        ),
                        'market': market,
                        'team_id': action.target_team,
                        'agent_class': 'alliance',
                    })

            elif action.action_type == 'partner_defection':
                partner_name = action.parameters.get('partner_name', 'Former partner')
                narratives.append({
                    'type': 'competitive',
                    'priority': 'high',
                    'text': (
                        f"{partner_name} may seek new partnerships in {action.target_market}"
                    ),
                    'market': action.target_market,
                    'agent_class': 'alliance',
                })

        return narratives
