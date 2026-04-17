"""
CC-32F: Government Agent — Dynamic Regulatory & Industrial Policy.

Governments evaluate all foreign firms in their market against industrial
policy priorities, grant incentives to high-performing firms, issue warnings
and restrictions to low performers, award procurement contracts competitively,
and shift bilateral trade policies based on aggregate firm behavior.

Plugs into CC-32E Agent Orchestrator as a standard AgentBase implementation.
"""
import logging
import random
from decimal import Decimal

from .base import AgentBase, AgentAction, StateSnapshot

logger = logging.getLogger('agent_orchestrator')


class GovernmentAgent(AgentBase):
    agent_class = "government"

    def evaluate(self, snapshot):
        """
        Evaluate every foreign firm in every market against that government's
        policy priorities. Generate incentive, procurement, warning, restriction,
        regulatory, and bilateral shift actions.
        """
        actions = []

        for market_code, govt_data in snapshot.governments.items():
            if not govt_data:
                continue

            # Evaluate each foreign team in this market
            team_scores = {}
            for team_id, team_data in snapshot.teams.items():
                if market_code not in team_data.get('market_presence', {}):
                    continue  # Team not in this market
                if team_data.get('home_market') == market_code:
                    continue  # Don't evaluate domestic firms

                score = self._evaluate_team(
                    govt_data, team_data,
                    snapshot.markets.get(market_code, {}),
                    market_code,
                )
                team_scores[team_id] = score

            if not team_scores:
                continue

            actions.extend(self._generate_incentives(
                govt_data, team_scores, market_code, snapshot,
            ))
            actions.extend(self._generate_procurement(
                govt_data, team_scores, market_code, snapshot,
            ))
            actions.extend(self._generate_warnings_restrictions(
                govt_data, team_scores, market_code, snapshot,
            ))
            actions.extend(self._generate_regulatory_adjustments(
                govt_data, team_scores, market_code, snapshot,
            ))
            actions.extend(self._generate_bilateral_shifts(
                govt_data, market_code, snapshot,
            ))

        return actions

    # ------------------------------------------------------------------
    # B1: Team evaluation against policy priorities
    # ------------------------------------------------------------------

    def _evaluate_team(self, govt_data, team_data, market_data, market_code):
        """Score a team against the government's policy priorities."""
        scores = {}
        priorities = self._normalize_priorities(
            govt_data.get('policy_priorities', []),
        )

        for priority in priorities:
            obj = priority['objective']

            if obj == 'local_employment':
                # Staff allocated to this market across all pools
                talent = team_data.get('talent_allocation', {})
                market_staff = sum(
                    alloc.get(market_code, 0)
                    for alloc in talent.values()
                )
                baseline = 10
                scores[obj] = min(1.0, market_staff / baseline)

            elif obj == 'technology_transfer':
                entry_mode = team_data['market_presence'].get(
                    market_code, {},
                ).get('entry_mode')
                ip_exposure = team_data['market_presence'].get(
                    market_code, {},
                ).get('ip_exposure', 0)

                if entry_mode in ('JV', 'LICENSING'):
                    # JV/licensing transfers technology; scale by IP exposure
                    scores[obj] = min(1.0, max(0.3, ip_exposure / 0.5))
                elif entry_mode == 'SUBSIDIARY':
                    # Subsidiary with R&D staff = moderate transfer
                    rd_staff = team_data.get('talent_allocation', {}).get(
                        'rd', {},
                    ).get(market_code, 0)
                    scores[obj] = min(1.0, rd_staff / 8.0) * 0.6
                else:
                    scores[obj] = 0.1  # Export = minimal transfer

            elif obj == 'tax_revenue':
                market_rev = team_data.get('market_revenues', {}).get(
                    market_code, {},
                ).get('revenue', 0)
                tax_rate = market_data.get('tax_rate', 0.20)
                tax_structure = team_data.get('tax_structure')

                if tax_structure == 'aggressive':
                    effective_rate = max(0.05, tax_rate - 0.08)
                elif tax_structure == 'regional_hub':
                    effective_rate = max(0.05, tax_rate - 0.04)
                else:
                    effective_rate = tax_rate

                tax_paid = market_rev * effective_rate
                scores[obj] = min(1.0, tax_paid / 500000)

            elif obj == 'esg_compliance':
                compliance = team_data.get('compliance', {}).get(
                    market_code, 0,
                )
                gc = team_data.get('governance_commitments', 0)
                governance_count = len(gc) if isinstance(gc, list) else gc
                gov_score = min(1.0, governance_count / 5.0)
                scores[obj] = (compliance + gov_score) / 2

            elif obj == 'local_manufacturing':
                has_plant = team_data.get('plants', {}).get(
                    market_code, False,
                )
                if has_plant:
                    scores[obj] = 1.0
                else:
                    # Check for contract manufacturing via entry mode
                    entry_mode = team_data['market_presence'].get(
                        market_code, {},
                    ).get('entry_mode')
                    if entry_mode in ('CONTRACT_MFG',):
                        scores[obj] = 0.5
                    else:
                        scores[obj] = 0.0

            elif obj == 'export_contribution':
                has_plant = team_data.get('plants', {}).get(
                    market_code, False,
                )
                if has_plant:
                    scores[obj] = 0.6
                else:
                    scores[obj] = 0.0

            else:
                scores[obj] = 0.5

        # Weighted average
        total_weight = sum(p['weight'] for p in priorities)
        weighted = sum(
            scores.get(p['objective'], 0.5) * p['weight']
            for p in priorities
        )
        overall = weighted / total_weight if total_weight > 0 else 0.5

        return {
            'overall': overall,
            'objective_scores': scores,
        }

    # ------------------------------------------------------------------
    # B2: Incentive generation
    # ------------------------------------------------------------------

    def _generate_incentives(self, govt_data, team_scores, market_code, snapshot):
        """Grant incentives to high-scoring firms."""
        actions = []

        threshold = govt_data.get('incentive_threshold', 0.70)
        max_value = govt_data.get('max_incentive_value_per_round', 2000000)

        eligible = [
            (tid, scores) for tid, scores in team_scores.items()
            if scores['overall'] >= threshold
        ]
        eligible.sort(key=lambda x: x[1]['overall'], reverse=True)

        remaining_budget = max_value
        for team_id, scores in eligible:
            if remaining_budget <= 0:
                break

            top_objective = max(
                scores['objective_scores'].items(), key=lambda x: x[1],
            )
            incentive = self._select_incentive(
                top_objective[0], scores['overall'], remaining_budget,
            )
            if incentive:
                actions.append(AgentAction(
                    agent_class="government",
                    agent_id=f"govt_{market_code}",
                    action_type="grant_incentive",
                    target_team=team_id,
                    target_market=market_code,
                    parameters=incentive,
                    priority=3,
                ))
                remaining_budget -= incentive.get('value', 0)

        return actions

    def _select_incentive(self, strength_area, satisfaction, budget):
        """Select appropriate incentive based on the firm's strength."""
        incentive_map = {
            'local_employment': {
                'type': 'tax_holiday',
                'description': 'Tax holiday for significant local employment contribution',
                'value': min(budget, 1000000),
                'effect': {'tax_reduction_pct': 0.03, 'duration_rounds': 2},
            },
            'local_manufacturing': {
                'type': 'land_grant',
                'description': 'Government land grant for manufacturing investment',
                'value': min(budget, 1500000),
                'effect': {'plant_cost_reduction': 0.20, 'duration_rounds': 0},
            },
            'technology_transfer': {
                'type': 'expedited_permits',
                'description': 'Fast-track regulatory approval for technology partnership',
                'value': min(budget, 500000),
                'effect': {'market_entry_speed': 1.5, 'duration_rounds': 2},
            },
            'esg_compliance': {
                'type': 'green_subsidy',
                'description': 'Environmental compliance subsidy',
                'value': min(budget, 800000),
                'effect': {'esg_cost_offset': 0.30, 'duration_rounds': 2},
            },
            'tax_revenue': {
                'type': 'regulatory_fast_track',
                'description': 'Priority processing for a major tax contributor',
                'value': min(budget, 600000),
                'effect': {'compliance_boost': 0.10, 'duration_rounds': 1},
            },
            'export_contribution': {
                'type': 'export_subsidy',
                'description': 'Export promotion subsidy for local production hub',
                'value': min(budget, 700000),
                'effect': {'logistics_cost_reduction': 0.05, 'duration_rounds': 2},
            },
        }
        return incentive_map.get(strength_area)

    # ------------------------------------------------------------------
    # B3: Procurement
    # ------------------------------------------------------------------

    def _generate_procurement(self, govt_data, team_scores, market_code, snapshot):
        """Award government procurement contracts to the highest-scoring firm."""
        actions = []

        frequency = govt_data.get('procurement_frequency', 2)
        current_round = snapshot.round_number

        if current_round % frequency != 0:
            return actions  # Not a procurement round

        budget = govt_data.get('procurement_budget_per_round', 3000000)

        if team_scores:
            winner_id = max(
                team_scores.items(), key=lambda x: x[1]['overall'],
            )[0]
            winner_score = team_scores[winner_id]
            contract_value = float(budget) * winner_score['overall']

            actions.append(AgentAction(
                agent_class="government",
                agent_id=f"govt_{market_code}",
                action_type="procurement_award",
                target_team=winner_id,
                target_market=market_code,
                parameters={
                    'contract_value': contract_value,
                    'satisfaction_score': winner_score['overall'],
                    'primary_reason': max(
                        winner_score['objective_scores'].items(),
                        key=lambda x: x[1],
                    )[0],
                },
                priority=4,
            ))

        return actions

    # ------------------------------------------------------------------
    # B4: Warnings and restrictions
    # ------------------------------------------------------------------

    def _generate_warnings_restrictions(self, govt_data, team_scores,
                                         market_code, snapshot):
        """Issue warnings or restrict access for low-scoring firms."""
        actions = []

        warning_threshold = govt_data.get('warning_threshold', 0.40)
        restriction_threshold = govt_data.get('restriction_threshold', 0.25)
        patience = govt_data.get('patience_rounds', 2)

        sat_per_team = govt_data.get('satisfaction_per_team', {})

        for team_id, scores in team_scores.items():
            satisfaction = scores['overall']

            if satisfaction < restriction_threshold:
                existing = sat_per_team.get(str(team_id), {})
                rounds_below = existing.get('rounds_below_restriction', 0) + 1

                if rounds_below >= patience:
                    actions.append(AgentAction(
                        agent_class="government",
                        agent_id=f"govt_{market_code}",
                        action_type="access_restriction",
                        target_team=team_id,
                        target_market=market_code,
                        parameters={
                            'restriction_type': 'sales_cap',
                            'magnitude': 0.30,
                            'reason': self._get_lowest_objective(scores),
                            'reversible': True,
                            'reverse_condition': (
                                f'Improve satisfaction above {warning_threshold}'
                            ),
                        },
                        priority=2,
                    ))
                else:
                    # Still below restriction but not enough patience exhausted
                    actions.append(AgentAction(
                        agent_class="government",
                        agent_id=f"govt_{market_code}",
                        action_type="warning_issued",
                        target_team=team_id,
                        target_market=market_code,
                        parameters={
                            'reason': self._get_lowest_objective(scores),
                            'threat': 'Severe operating restrictions imminent',
                            'patience_remaining': patience - rounds_below,
                        },
                        priority=4,
                    ))

            elif satisfaction < warning_threshold:
                existing = sat_per_team.get(str(team_id), {})
                rounds_below_w = existing.get('rounds_below_warning', 0) + 1

                actions.append(AgentAction(
                    agent_class="government",
                    agent_id=f"govt_{market_code}",
                    action_type="warning_issued",
                    target_team=team_id,
                    target_market=market_code,
                    parameters={
                        'reason': self._get_lowest_objective(scores),
                        'threat': (
                            "Operating restrictions if conditions don't improve"
                        ),
                        'patience_remaining': max(
                            0, patience - rounds_below_w,
                        ),
                    },
                    priority=4,
                ))

        return actions

    # ------------------------------------------------------------------
    # B5: Regulatory adjustments (market-wide)
    # ------------------------------------------------------------------

    def _generate_regulatory_adjustments(self, govt_data, team_scores,
                                          market_code, snapshot):
        """Tighten or relax regulations based on collective firm behavior."""
        actions = []

        if not team_scores:
            return actions

        avg_satisfaction = (
            sum(s['overall'] for s in team_scores.values()) / len(team_scores)
        )

        if avg_satisfaction > 0.75:
            if random.random() < 0.15:
                actions.append(AgentAction(
                    agent_class="government",
                    agent_id=f"govt_{market_code}",
                    action_type="regulatory_relaxation",
                    target_team=None,
                    target_market=market_code,
                    parameters={
                        'type': 'tariff_reduction',
                        'magnitude': 0.02,
                        'duration_rounds': 3,
                        'reason': (
                            'Government rewarding foreign investment compliance'
                        ),
                    },
                    priority=3,
                ))

        elif avg_satisfaction < 0.35:
            if random.random() < 0.20:
                actions.append(AgentAction(
                    agent_class="government",
                    agent_id=f"govt_{market_code}",
                    action_type="regulatory_tightening",
                    target_team=None,
                    target_market=market_code,
                    parameters={
                        'type': 'compliance_requirement_increase',
                        'magnitude': 0.10,
                        'duration_rounds': 0,
                        'reason': (
                            'Government tightening standards due to poor '
                            'foreign firm compliance'
                        ),
                    },
                    priority=3,
                ))

        return actions

    # ------------------------------------------------------------------
    # B6: Bilateral trade policy shifts
    # ------------------------------------------------------------------

    def _generate_bilateral_shifts(self, govt_data, market_code, snapshot):
        """Generate bilateral trade policy shifts between markets."""
        actions = []

        volatility = govt_data.get('policy_volatility', 0.10)
        if random.random() > volatility:
            return actions

        for origin_code in snapshot.markets:
            if origin_code == market_code:
                continue

            origin_teams = [
                (tid, tdata) for tid, tdata in snapshot.teams.items()
                if tdata.get('home_market') == origin_code
                and market_code in tdata.get('market_presence', {})
            ]

            if not origin_teams:
                continue

            avg_compliance = sum(
                tdata.get('compliance', {}).get(market_code, 0)
                for _, tdata in origin_teams
            ) / len(origin_teams)

            if avg_compliance > 0.60 and random.random() < 0.3:
                actions.append(AgentAction(
                    agent_class="government",
                    agent_id=f"govt_{market_code}",
                    action_type="bilateral_shift",
                    target_team=None,
                    target_market=market_code,
                    parameters={
                        'type': 'trade_facilitation',
                        'origin_market': origin_code,
                        'tariff_reduction': 0.02,
                        'trust_improvement': 0.03,
                        'duration_rounds': 4,
                        'reason': (
                            f'Bilateral trade relations improving between '
                            f'{market_code} and {origin_code}'
                        ),
                    },
                    priority=3,
                    dependencies=['tariff_change'],
                ))

            elif avg_compliance < 0.20 and random.random() < 0.3:
                actions.append(AgentAction(
                    agent_class="government",
                    agent_id=f"govt_{market_code}",
                    action_type="bilateral_shift",
                    target_team=None,
                    target_market=market_code,
                    parameters={
                        'type': 'increased_screening',
                        'origin_market': origin_code,
                        'tariff_increase': 0.03,
                        'trust_penalty': -0.05,
                        'duration_rounds': 3,
                        'reason': (
                            f'Government increasing scrutiny of firms '
                            f'from {origin_code}'
                        ),
                    },
                    priority=3,
                ))

        return actions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_priorities(raw):
        """
        Ensure policy_priorities is a flat list of {objective, weight} dicts
        with numeric weights.  Handles:
        - Double-nested list: [[{...}, ...]]
        - Weight stored as single-element list: {'weight': [0.30]}
        - Dict-style format: {'local_employment': 0.30, ...}
        """
        if not raw:
            return []

        # Unwrap double-nested list
        if (isinstance(raw, list) and len(raw) == 1
                and isinstance(raw[0], list)):
            raw = raw[0]

        # Convert flat dict to list-of-dicts
        if isinstance(raw, dict):
            return [
                {'objective': k, 'weight': float(v)}
                for k, v in raw.items()
            ]

        # Ensure each weight is a plain float
        normalized = []
        for p in raw:
            weight = p.get('weight', 0)
            if isinstance(weight, (list, tuple)):
                weight = weight[0] if weight else 0
            normalized.append({
                **p,
                'weight': float(weight),
            })
        return normalized

    def _get_lowest_objective(self, scores):
        """Find the weakest policy area for a team."""
        obj_scores = scores.get('objective_scores', {})
        if not obj_scores:
            return 'general_compliance'
        return min(obj_scores.items(), key=lambda x: x[1])[0]

    def _generate_action_narrative(self, action):
        """Generate a short narrative string for the action log."""
        params = action.parameters
        if action.action_type == 'grant_incentive':
            return (
                f"Incentive granted: {params.get('description', 'Investment incentive')}"
            )
        elif action.action_type == 'procurement_award':
            return (
                f"Procurement contract worth "
                f"${params.get('contract_value', 0):,.0f} awarded"
            )
        elif action.action_type == 'warning_issued':
            return (
                f"Warning: improve {params.get('reason', 'compliance')}"
            )
        elif action.action_type == 'access_restriction':
            return (
                f"Access restriction: "
                f"{int(params.get('magnitude', 0.3) * 100)}% sales cap"
            )
        elif action.action_type == 'bilateral_shift':
            return params.get('reason', 'Bilateral policy shift')
        elif action.action_type in ('regulatory_tightening', 'regulatory_relaxation'):
            return params.get('reason', 'Regulatory adjustment')
        return action.action_type

    # ------------------------------------------------------------------
    # B7: Cross-agent dependency resolution
    # ------------------------------------------------------------------

    def resolve_dependencies(self, own_actions, all_actions):
        """
        Government adjusts based on:
        - Investor mass sell-off → soften warnings to prevent capital flight
        - Alliance dissolution → concerned about business stability
        """
        investor_sells = [
            a for a in all_actions
            if a.action_type == 'trade_shares'
            and a.parameters.get('direction') == 'SELL'
        ]

        if not investor_sells:
            return own_actions

        # Aggregate sell volume per team
        fleeing_teams = {}
        for sell in investor_sells:
            tid = sell.target_team
            fleeing_teams[tid] = (
                fleeing_teams.get(tid, 0) + sell.parameters.get('shares', 0)
            )

        revised = []
        for action in own_actions:
            if (action.action_type == 'warning_issued'
                    and action.target_team in fleeing_teams
                    and fleeing_teams[action.target_team] > 10000):
                # Government softens warning to prevent exacerbating flight
                action.parameters['softened'] = True
                reason = action.parameters.get('reason', '')
                action.parameters['reason'] = (
                    f'{reason} (moderated to prevent capital flight)'
                )
            revised.append(action)

        return revised

    # ------------------------------------------------------------------
    # B8: Apply actions to database
    # ------------------------------------------------------------------

    def apply_actions(self, actions, game, round_obj):
        """Apply government actions to the database."""
        from core.models.cc32f_models import (
            GovernmentProfile, GovernmentSatisfaction, GovernmentAction,
        )
        from core.models.scenario import MarketDefinition
        from core.models.results import ActiveModifier
        from core.models.team_state import TeamMarketPresence

        market_cache = {}

        def get_market(code):
            if code not in market_cache:
                market_cache[code] = MarketDefinition.objects.filter(
                    scenario=game.scenario, code=code,
                ).first()
            return market_cache[code]

        for action in actions:
            market = get_market(action.target_market)
            if not market:
                continue

            # Log every action
            GovernmentAction.objects.create(
                game=game,
                round=round_obj,
                market=market,
                action_type=action.action_type.upper(),
                target_team_id=action.target_team,
                target_origin=get_market(
                    action.parameters.get('origin_market'),
                ) if action.parameters.get('origin_market') else None,
                parameters=action.parameters,
                narrative=self._generate_action_narrative(action),
            )

            if action.action_type == 'grant_incentive':
                self._apply_incentive(
                    game, round_obj, action, market,
                )

            elif action.action_type == 'procurement_award':
                self._apply_procurement(
                    game, round_obj, action, market,
                )

            elif action.action_type in (
                'bilateral_shift', 'tariff_adjustment',
            ):
                self._apply_tariff_change(
                    game, round_obj, action, market,
                )

            elif action.action_type in (
                'regulatory_tightening', 'regulatory_relaxation',
            ):
                self._apply_regulatory_change(
                    game, round_obj, action, market,
                )

            elif action.action_type == 'access_restriction':
                self._apply_access_restriction(
                    game, round_obj, action, market,
                )

        # Update GovernmentSatisfaction records
        self._update_satisfaction_records(actions, game, round_obj)

    def _apply_incentive(self, game, round_obj, action, market):
        """Record incentive on satisfaction record."""
        from core.models.cc32f_models import GovernmentSatisfaction

        sat, _ = GovernmentSatisfaction.objects.get_or_create(
            game=game, team_id=action.target_team, market=market,
            defaults={'satisfaction': Decimal('0.50')},
        )
        sat.active_incentive = action.parameters
        sat.save(update_fields=['active_incentive'])

    def _apply_procurement(self, game, round_obj, action, market):
        """Procurement recorded via GovernmentAction (already logged above)."""
        pass

    def _apply_tariff_change(self, game, round_obj, action, market):
        """Tariff change recorded via GovernmentAction (already logged above)."""
        pass

    def _apply_regulatory_change(self, game, round_obj, action, market):
        """Regulatory change recorded via GovernmentAction (already logged above)."""
        pass

    def _apply_access_restriction(self, game, round_obj, action, market):
        """Apply operating restrictions — track on GovernmentSatisfaction."""
        from core.models.cc32f_models import GovernmentSatisfaction

        sat, _ = GovernmentSatisfaction.objects.get_or_create(
            game=game, team_id=action.target_team, market=market,
            defaults={'satisfaction': Decimal('0.50')},
        )
        sat.active_restriction = action.parameters
        sat.status = 'RESTRICTED'
        sat.save(update_fields=['active_restriction', 'status'])

    def _update_satisfaction_records(self, actions, game, round_obj):
        """Update persistent GovernmentSatisfaction for all foreign teams."""
        from core.models.cc32f_models import (
            GovernmentProfile, GovernmentSatisfaction,
        )
        from core.models.team_state import TeamMarketPresence

        profiles = {
            gp.market.code: gp
            for gp in GovernmentProfile.objects.filter(
                scenario=game.scenario,
            ).select_related('market')
        }

        for market_code, gp in profiles.items():
            for team in game.teams.select_related('home_market').all():
                if team.home_market and team.home_market.code == market_code:
                    continue  # Skip domestic firms

                has_presence = TeamMarketPresence.objects.filter(
                    team=team, market=gp.market, status='active',
                ).exists()
                if not has_presence:
                    continue

                # Find current scores from the actions we produced
                # (re-derive from snapshot-like data would be circular;
                #  instead use _evaluate_team on fresh data)
                scores = self._evaluate_team_from_db(
                    gp, team, game, market_code, round_obj.round_number,
                )

                record, _ = GovernmentSatisfaction.objects.get_or_create(
                    game=game, team=team, market=gp.market,
                    defaults={'satisfaction': Decimal('0.50')},
                )

                record.satisfaction = Decimal(str(round(scores['overall'], 2)))
                record.objective_scores = scores['objective_scores']

                # Update counters
                if scores['overall'] < float(gp.restriction_threshold):
                    record.rounds_below_restriction += 1
                else:
                    record.rounds_below_restriction = 0

                if scores['overall'] < float(gp.warning_threshold):
                    record.rounds_below_warning += 1
                else:
                    record.rounds_below_warning = 0

                # Update status
                if scores['overall'] >= float(gp.incentive_threshold):
                    record.status = 'WELCOMED'
                elif scores['overall'] >= float(gp.warning_threshold):
                    record.status = 'NEUTRAL'
                elif record.rounds_below_restriction >= gp.patience_rounds:
                    record.status = 'RESTRICTED'
                elif record.rounds_below_warning >= 1:
                    if record.rounds_below_restriction >= 1:
                        record.status = 'WARNING'
                    else:
                        record.status = 'MONITORED'
                else:
                    record.status = 'MONITORED'

                record.save()

    def _evaluate_team_from_db(self, gp, team, game, market_code, round_number):
        """
        Evaluate a team directly from database (for apply_actions phase).
        Used to persist satisfaction records after actions are applied.
        """
        from core.models.results_financials import RoundResultMarketRevenue
        from core.models.team_state import (
            TeamMarketPresence, TeamPlant, TeamPartnership,
        )
        from core.models.cc31_models import (
            TalentAllocation, TeamMarketCompliance, TeamGovernanceCommitment,
        )
        from core.models.decisions import DecisionSubmission

        scores = {}
        priorities = self._normalize_priorities(gp.policy_priorities or [])

        # Get market presence
        presence = TeamMarketPresence.objects.filter(
            team=team, market=gp.market, status='active',
        ).select_related('entry_mode').first()

        entry_mode = (
            presence.entry_mode.code if presence and presence.entry_mode
            else None
        )
        ip_exposure = float(
            presence.ip_exposure_cumulative or 0,
        ) if presence else 0

        # Get talent allocation
        submission = DecisionSubmission.objects.filter(
            team=team, round__game=game,
            round__round_number=round_number,
        ).first()
        talent_in_market = 0
        rd_in_market = 0
        if submission:
            for alloc in TalentAllocation.objects.filter(
                submission=submission,
            ):
                count = alloc.market_allocation.get(market_code, 0)
                talent_in_market += count
                if alloc.talent_pool == 'rd':
                    rd_in_market = count

        # Market revenue
        mr = RoundResultMarketRevenue.objects.filter(
            game=game, team=team, round_number=round_number,
            market=gp.market,
        ).first()
        market_revenue = float(mr.home_revenue or 0) if mr else 0

        # Plant
        has_plant = TeamPlant.objects.filter(
            team=team, market=gp.market, status='operational',
        ).exists()

        # Compliance
        compliance_obj = TeamMarketCompliance.objects.filter(
            game=game, team=team, market=gp.market,
        ).first()
        compliance_level = float(
            compliance_obj.compliance_level or 0,
        ) if compliance_obj else 0

        # Governance
        governance_count = TeamGovernanceCommitment.objects.filter(
            game=game, team=team, is_active=True,
        ).count()

        # Tax structure
        tax_structure = None
        try:
            from core.models.cc32c_models import TeamTaxStructure
            tts = TeamTaxStructure.objects.filter(
                game=game, team=team,
            ).select_related('current_structure').first()
            if tts and tts.current_structure:
                tax_structure = tts.current_structure.code
        except Exception:
            pass

        for priority in priorities:
            obj = priority['objective']

            if obj == 'local_employment':
                scores[obj] = min(1.0, talent_in_market / 10)

            elif obj == 'technology_transfer':
                if entry_mode in ('JV', 'LICENSING'):
                    scores[obj] = min(1.0, max(0.3, ip_exposure / 0.5))
                elif entry_mode == 'SUBSIDIARY':
                    scores[obj] = min(1.0, rd_in_market / 8.0) * 0.6
                else:
                    scores[obj] = 0.1

            elif obj == 'tax_revenue':
                tax_rate = float(gp.market.tax_rate or 0.20)
                if tax_structure == 'aggressive':
                    eff = max(0.05, tax_rate - 0.08)
                elif tax_structure == 'regional_hub':
                    eff = max(0.05, tax_rate - 0.04)
                else:
                    eff = tax_rate
                scores[obj] = min(1.0, (market_revenue * eff) / 500000)

            elif obj == 'esg_compliance':
                gov_score = min(1.0, governance_count / 5.0)
                scores[obj] = (compliance_level + gov_score) / 2

            elif obj == 'local_manufacturing':
                if has_plant:
                    scores[obj] = 1.0
                else:
                    scores[obj] = 0.0

            elif obj == 'export_contribution':
                scores[obj] = 0.6 if has_plant else 0.0

            else:
                scores[obj] = 0.5

        total_weight = sum(p['weight'] for p in priorities)
        weighted = sum(
            scores.get(p['objective'], 0.5) * p['weight']
            for p in priorities
        )
        overall = weighted / total_weight if total_weight > 0 else 0.5

        return {'overall': overall, 'objective_scores': scores}

    # ------------------------------------------------------------------
    # B9: Narrative generation
    # ------------------------------------------------------------------

    def get_narrative(self, actions):
        """Generate human-readable narrative items for briefing/ticker."""
        narratives = []

        for action in actions:
            if action.action_type == 'grant_incentive':
                narratives.append({
                    'type': 'government',
                    'priority': 'medium',
                    'text': (
                        f"Government incentive: "
                        f"{action.parameters.get('description', 'Investment incentive granted')} "
                        f"({action.target_market})"
                    ),
                    'market': action.target_market,
                    'team_id': action.target_team,
                    'agent_class': 'government',
                })

            elif action.action_type == 'procurement_award':
                narratives.append({
                    'type': 'government',
                    'priority': 'high',
                    'text': (
                        f"Government contract worth "
                        f"${action.parameters['contract_value']:,.0f} "
                        f"awarded in {action.target_market}"
                    ),
                    'market': action.target_market,
                    'team_id': action.target_team,
                    'agent_class': 'government',
                })

            elif action.action_type == 'warning_issued':
                narratives.append({
                    'type': 'government',
                    'priority': 'high',
                    'text': (
                        f"Government warning: improve "
                        f"{action.parameters.get('reason', 'compliance')} "
                        f"or face restrictions ({action.target_market})"
                    ),
                    'market': action.target_market,
                    'team_id': action.target_team,
                    'agent_class': 'government',
                })

            elif action.action_type == 'access_restriction':
                mag = action.parameters.get('magnitude', 0.3)
                narratives.append({
                    'type': 'government',
                    'priority': 'high',
                    'text': (
                        f"Operating restrictions imposed: "
                        f"{int(mag * 100)}% sales cap "
                        f"({action.target_market})"
                    ),
                    'market': action.target_market,
                    'team_id': action.target_team,
                    'agent_class': 'government',
                })

            elif action.action_type == 'bilateral_shift':
                shift_type = action.parameters.get('type', '')
                origin = action.parameters.get('origin_market', '?')
                if shift_type == 'trade_facilitation':
                    narratives.append({
                        'type': 'government',
                        'priority': 'medium',
                        'text': (
                            f"Trade relations improving: "
                            f"{action.target_market} - {origin} "
                            f"tariffs reduced"
                        ),
                        'market': action.target_market,
                        'agent_class': 'government',
                    })
                elif shift_type == 'increased_screening':
                    narratives.append({
                        'type': 'government',
                        'priority': 'high',
                        'text': (
                            f"Increased scrutiny: {action.target_market} "
                            f"tightening on firms from {origin}"
                        ),
                        'market': action.target_market,
                        'agent_class': 'government',
                    })

            elif action.action_type in (
                'regulatory_tightening', 'regulatory_relaxation',
            ):
                direction = (
                    'tightening'
                    if action.action_type == 'regulatory_tightening'
                    else 'relaxing'
                )
                narratives.append({
                    'type': 'government',
                    'priority': 'medium',
                    'text': (
                        f"Regulatory environment {direction} in "
                        f"{action.target_market}: "
                        f"{action.parameters.get('reason', '')}"
                    ),
                    'market': action.target_market,
                    'agent_class': 'government',
                })

        return narratives
