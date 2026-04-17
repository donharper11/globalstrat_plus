"""
CC-32E: Investor Agent — Wraps AI capital markets logic (CC-26).

Delegates actual trading and share price calculation to the existing
capital_markets.process_capital_markets() function, but participates in
the convergence loop for cross-agent dependency resolution.
"""
import logging

from .base import AgentBase, AgentAction, StateSnapshot

logger = logging.getLogger('agent_orchestrator')


class InvestorAgent(AgentBase):
    agent_class = "investor"

    def evaluate(self, snapshot):
        """
        Propose trade actions based on investor sentiment from snapshot.
        Uses snapshot data to determine direction without DB access.
        """
        actions = []

        for fund_id, fund_data in snapshot.investors.items():
            for team_id, team_data in snapshot.teams.items():
                # Determine sentiment from available data
                current_holding = fund_data['holdings_per_team'].get(team_id)
                prev_holding = fund_data['prev_holdings'].get(team_id)

                if current_holding:
                    satisfaction = current_holding.get('satisfaction', 0.5)
                    current_pct = current_holding.get('pct', fund_data['initial_holding_pct'])
                    action_taken = current_holding.get('action', 'hold')
                    shares = current_holding.get('shares', 0)
                else:
                    satisfaction = 0.5
                    current_pct = fund_data['initial_holding_pct']
                    action_taken = 'hold'
                    shares = 0

                prev_shares = 0
                if prev_holding:
                    prev_shares = prev_holding.get('shares', 0)

                shares_traded = shares - prev_shares if prev_shares else 0

                if shares_traded != 0 or action_taken != 'hold':
                    direction = 'BUY' if shares_traded > 0 else ('SELL' if shares_traded < 0 else 'HOLD')

                    actions.append(AgentAction(
                        agent_class="investor",
                        agent_id=fund_id,
                        action_type="trade_shares",
                        target_team=team_id,
                        target_market=None,
                        parameters={
                            'direction': direction,
                            'shares': abs(shares_traded),
                            'satisfaction': satisfaction,
                            'fund_name': fund_data['name'],
                            'fund_code': fund_data['code'],
                            'holding_pct': current_pct,
                        },
                        priority=6,
                        dependencies=['tariff_change', 'grant_incentive'],
                    ))

        return actions

    def resolve_dependencies(self, own_actions, all_actions):
        """
        If government granted incentive to a team, moderate selling.
        If alliance dissolving, increase concern about affected team.
        """
        incentives = [
            a for a in all_actions
            if a.action_type == 'grant_incentive'
        ]
        dissolutions = [
            a for a in all_actions
            if a.action_type == 'update_satisfaction'
            and a.parameters.get('status_recommendation') in ('DISSOLVING', 'DISSOLVED')
        ]

        if not incentives and not dissolutions:
            return own_actions

        beneficiary_teams = set(a.target_team for a in incentives)
        troubled_teams = set(a.target_team for a in dissolutions)

        revised = []
        for action in own_actions:
            if action.action_type == 'trade_shares':
                # Government backing moderates selling
                if action.target_team in beneficiary_teams and action.parameters['direction'] == 'SELL':
                    action.parameters['shares'] = int(action.parameters['shares'] * 0.7)
                    action.parameters['govt_incentive_moderated'] = True

                # Alliance dissolution increases selling pressure
                if action.target_team in troubled_teams and action.parameters['direction'] != 'SELL':
                    action.parameters['alliance_pressure'] = True

            revised.append(action)

        return revised

    def apply_actions(self, actions, game, round_obj):
        """
        Actual investor trading is handled by capital_markets.process_capital_markets()
        which runs at Step 12.8 in the pipeline (before the orchestrator).
        The orchestrator's investor agent participates for cross-agent coordination
        and narrative generation only.
        """
        pass

    def get_narrative(self, actions):
        """Generate narrative items about significant investor activity."""
        narratives = []

        for action in actions:
            if action.action_type != 'trade_shares':
                continue

            shares = action.parameters.get('shares', 0)
            direction = action.parameters.get('direction', 'HOLD')
            fund_name = action.parameters.get('fund_name', 'Unknown Fund')
            satisfaction = action.parameters.get('satisfaction', 0.5)

            # Only narrate significant trades
            if shares < 1000 and direction == 'HOLD':
                continue

            if direction == 'BUY':
                text = f"{fund_name} increasing position (satisfaction {satisfaction:.0%})"
                priority = 'medium' if shares > 5000 else 'low'
            elif direction == 'SELL':
                text = f"{fund_name} reducing exposure (satisfaction {satisfaction:.0%})"
                priority = 'high' if shares > 5000 else 'medium'

                if action.parameters.get('govt_incentive_moderated'):
                    text += " — selling moderated by government incentive"
            else:
                text = f"{fund_name} maintaining position"
                priority = 'low'

            narratives.append({
                'type': 'investor',
                'priority': priority,
                'text': text,
                'team_id': action.target_team,
                'agent_class': 'investor',
            })

        return narratives
