"""
CC-32E: State Snapshot Builder — Constructs immutable StateSnapshot for agent evaluation.

Called ONCE at the start of agent processing. All agents evaluate the SAME snapshot.
Optimized with select_related/prefetch to minimize query count.
"""
from decimal import Decimal

from django.db import models

from core.models.core import Team
from core.models.scenario import (
    AICompetitorDefinition, AICompetitorFitByRound, AICompetitorBehavior,
)
from core.models.cc26_models import AIInvestorFund, AIInvestorHolding
from core.models.cc32d_models import AlliancePartnerProfile, TeamAllianceState
from core.models.cc32f_models import GovernmentProfile, GovernmentSatisfaction
from core.models.results_financials import (
    RoundResultFinancials, RoundResultPerformanceIndex,
    RoundResultMarketRevenue,
)
from core.models.results import RoundResultAdoption, ActiveModifier, EventInstance
from core.models.team_state import TeamMarketPresence, TeamPartnership, TeamProduct, TeamPlatform

from .base import StateSnapshot


def build_state_snapshot(game, round_obj):
    """
    Build an immutable snapshot of all game state relevant to agent evaluation.
    Called ONCE at the start of agent processing.
    """
    round_number = round_obj.round_number
    scenario = game.scenario

    teams = _serialize_teams(game, round_number, scenario)
    markets = _serialize_markets(game, round_number, scenario)
    competitors = _serialize_ai_competitors(game, round_number, scenario)
    investors = _serialize_ai_investors(game, round_number, scenario)
    alliances = _serialize_alliances(game)
    governments = _serialize_governments(game, scenario)
    events = _serialize_round_events(game, round_number)
    global_conditions = _serialize_global_conditions(game, round_number, scenario)

    return StateSnapshot(
        round_number=round_number,
        class_id=game.section_id or game.id,  # CC-3.5: seeds deterministic agent RNG
        teams=teams,
        markets=markets,
        competitors=competitors,
        investors=investors,
        alliances=alliances,
        governments=governments,
        events_this_round=events,
        global_conditions=global_conditions,
    )


# ---------------------------------------------------------------------------
# Team serialization
# ---------------------------------------------------------------------------

def _serialize_teams(game, round_number, scenario):
    """Serialize all team state into snapshot dict."""
    teams = {}
    for team in game.teams.select_related('home_market').all():
        financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()

        performance = RoundResultPerformanceIndex.objects.filter(
            game=game, team=team, round_number=round_number,
        ).first()

        market_revenues = {}
        for mr in RoundResultMarketRevenue.objects.filter(
            game=game, team=team, round_number=round_number,
        ).select_related('market'):
            market_revenues[mr.market.code] = {
                'revenue': float(mr.home_revenue or 0),
                'market_share': float(mr.market_share_pct or 0),
            }

        # Market presence
        market_presence = {}
        for mp in TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market', 'entry_mode'):
            market_presence[mp.market.code] = {
                'entry_mode': mp.entry_mode.code if mp.entry_mode else None,
                'established_round': mp.established_round,
                'ip_exposure': float(mp.ip_exposure_cumulative or 0),
            }

        # Products
        products = []
        for product in TeamProduct.objects.filter(team=team, status='active'):
            products.append({
                'id': product.id,
                'name': product.name,
            })

        # Partnerships
        partnerships = []
        for tp in TeamPartnership.objects.filter(
            team=team, status='active',
        ).select_related('market', 'strategy_option'):
            partnerships.append({
                'market': tp.market.code if tp.market else None,
                'type': tp.strategy_option.code if tp.strategy_option else None,
            })

        # Org structure
        org_structure = None
        try:
            from core.models.cc32b_models import TeamOrganizationalStructure
            tos = TeamOrganizationalStructure.objects.filter(
                game=game, team=team,
            ).select_related('current_structure').first()
            if tos and tos.current_structure:
                org_structure = tos.current_structure.code
        except Exception:
            pass

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

        # Governance commitments
        governance_commitments = []
        try:
            from core.models.cc31_models import TeamGovernanceCommitment
            for tgc in TeamGovernanceCommitment.objects.filter(
                game=game, team=team, is_active=True,
            ).select_related('commitment_type'):
                governance_commitments.append({
                    'code': tgc.commitment_type.code,
                    'name': tgc.commitment_type.name,
                    'activated_round': tgc.activated_round,
                    'penalty_rounds_remaining': tgc.penalty_rounds_remaining,
                })
        except Exception:
            pass

        # Compliance
        compliance = {}
        try:
            from core.models.cc31_models import TeamMarketCompliance
            for tmc in TeamMarketCompliance.objects.filter(
                game=game, team=team,
            ).select_related('market'):
                compliance[tmc.market.code] = float(tmc.compliance_level or 0)
        except Exception:
            pass

        # Talent allocation (CC-32F: government evaluates local employment)
        talent_allocation = {}
        try:
            from core.models.cc31_models import TalentAllocation
            from core.models.decisions import DecisionSubmission
            sub = DecisionSubmission.objects.filter(
                team=team, round__game=game,
                round__round_number=round_number,
            ).first()
            if sub:
                for alloc in TalentAllocation.objects.filter(submission=sub):
                    talent_allocation[alloc.talent_pool] = alloc.market_allocation or {}
        except Exception:
            pass

        # Plants (CC-32F: government evaluates local manufacturing)
        plants = {}
        try:
            from core.models.team_state import TeamPlant
            for plant in TeamPlant.objects.filter(
                team=team, status='operational',
            ).select_related('market'):
                plants[plant.market.code] = True
        except Exception:
            pass

        teams[team.id] = {
            'name': team.name,
            'home_market': team.home_market.code if team.home_market else None,
            'shares_outstanding': team.shares_outstanding,
            'share_price': float(team.share_price or 0),
            'cash_on_hand': float(team.cash_on_hand or 0),
            'financials': _serialize_financials(financials),
            'performance_index': float(performance.index_value) if performance else 50.0,
            'market_presence': market_presence,
            'market_revenues': market_revenues,
            'products': products,
            'partnerships': partnerships,
            'org_structure': org_structure,
            'tax_structure': tax_structure,
            'governance_commitments': governance_commitments,
            'licensed_dependency_pct': float(
                TeamPlatform.objects.filter(
                    team=team, status='active',
                ).aggregate(
                    avg=models.Avg('licensed_dependency_pct')
                )['avg'] or 0
            ),
            'compliance': compliance,
            'talent_allocation': talent_allocation,
            'plants': plants,
        }

    return teams


def _serialize_financials(financials):
    """Serialize RoundResultFinancials into dict."""
    if not financials:
        return {}
    return {
        'total_revenue': float(financials.total_revenue or 0),
        'gross_profit': float(financials.gross_profit or 0),
        'operating_income': float(financials.operating_income or 0),
        'net_income': float(financials.net_income or 0),
        'total_equity': float(financials.total_equity or 0),
        'total_debt': float(financials.total_debt or 0),
        'cash_closing': float(financials.cash_closing or 0),
        'share_price': float(financials.share_price or 0),
        'debt_to_equity': float(financials.debt_to_equity or 0),
        'gross_margin_pct': float(financials.gross_margin_pct or 0),
        'net_margin_pct': float(financials.net_margin_pct or 0),
        'rd_expense': float(financials.rd_expense or 0),
        'marketing_expense': float(financials.marketing_expense or 0),
    }


# ---------------------------------------------------------------------------
# Market serialization
# ---------------------------------------------------------------------------

def _serialize_markets(game, round_number, scenario):
    """Serialize all market state into snapshot dict."""
    from core.models.scenario import MarketConditionByRound

    markets = {}
    for market in scenario.markets.all():
        condition = MarketConditionByRound.objects.filter(
            market=market, round_number=round_number,
        ).first()

        # Active teams in this market
        active_teams = list(
            TeamMarketPresence.objects.filter(
                team__game=game, market=market, status='active',
            ).values_list('team_id', flat=True)
        )

        # Active modifiers (market-wide only — no team FK on ActiveModifier)
        modifiers = []
        for mod in ActiveModifier.objects.filter(
            game=game, target_market=market,
        ).filter(started_round__lte=round_number):
            if mod.expires_round is None or mod.expires_round > round_number:
                modifiers.append({
                    'type': mod.modifier_type,
                    'key': mod.target_field or mod.modifier_type,
                    'value': float(mod.modifier_value),
                })

        markets[market.code] = {
            'name': market.name,
            'growth_rate': float(market.base_growth_rate) + float(condition.growth_rate_modifier) if condition else float(market.base_growth_rate),
            'tariff_rate': float(market.tariff_rate or 0),
            'tax_rate': float(market.tax_rate or 0),
            'exchange_rate': float(getattr(market, 'exchange_rate_base', 1.0)),
            'exchange_rate_modifier': float(getattr(condition, 'exchange_rate_modifier', 0.0)) if condition else 0.0,
            'active_teams': active_teams,
            'modifiers': modifiers,
        }

    return markets


# ---------------------------------------------------------------------------
# AI Competitor serialization
# ---------------------------------------------------------------------------

def _serialize_ai_competitors(game, round_number, scenario):
    """Serialize AI competitor state."""
    competitors = {}
    for comp in AICompetitorDefinition.objects.filter(scenario=scenario):
        behavior = AICompetitorBehavior.objects.filter(ai_competitor=comp).first()

        # Get fit scores for this round
        fit_scores = {}
        for fit in AICompetitorFitByRound.objects.filter(
            ai_competitor=comp, round_number=round_number,
        ).select_related('segment', 'market'):
            market_code = fit.market.code if fit.market else 'global'
            seg_name = fit.segment.name if fit.segment else 'unknown'
            key = f"{market_code}_{seg_name}"
            fit_scores[key] = float(fit.fit_score)

        # Market presence (competitors are in all markets by default)
        presence = {}
        for market in scenario.markets.all():
            presence[market.code] = True

        competitors[str(comp.id)] = {
            'name': comp.name,
            'strategy': behavior.strategy_type if behavior else 'moderate',
            'innovation_rate': float(behavior.innovation_rate) if behavior else 0.5,
            'price_sensitivity': float(behavior.price_sensitivity) if behavior else 0.5,
            'primary_segments': behavior.primary_segments if behavior else [],
            'fit_scores': fit_scores,
            'presence': presence,
        }

    return competitors


# ---------------------------------------------------------------------------
# AI Investor serialization
# ---------------------------------------------------------------------------

def _serialize_ai_investors(game, round_number, scenario):
    """Serialize AI investor state."""
    investors = {}
    for fund in AIInvestorFund.objects.filter(scenario=scenario):
        # Holdings per team
        holdings = {}
        for holding in AIInvestorHolding.objects.filter(
            game=game, fund=fund, round_number=round_number,
        ):
            holdings[holding.team_id] = {
                'shares': holding.shares_held,
                'pct': float(holding.holding_pct),
                'satisfaction': float(holding.satisfaction_score),
                'action': holding.action,
            }

        # Previous round holdings (for delta calculation)
        prev_holdings = {}
        if round_number > 0:
            for holding in AIInvestorHolding.objects.filter(
                game=game, fund=fund, round_number=round_number - 1,
            ):
                prev_holdings[holding.team_id] = {
                    'shares': holding.shares_held,
                    'pct': float(holding.holding_pct),
                }

        investors[str(fund.id)] = {
            'name': fund.name,
            'code': fund.code,
            'philosophy': fund.investment_philosophy,
            'initial_holding_pct': float(fund.initial_holding_pct),
            'max_holding_pct': float(fund.max_holding_pct),
            'min_holding_pct': float(fund.min_holding_pct),
            'trade_aggressiveness': float(fund.trade_aggressiveness),
            'holdings_per_team': holdings,
            'prev_holdings': prev_holdings,
        }

    return investors


# ---------------------------------------------------------------------------
# Alliance serialization
# ---------------------------------------------------------------------------

def _serialize_alliances(game):
    """Serialize alliance state."""
    alliances = {}
    for alliance in TeamAllianceState.objects.filter(
        game=game,
    ).select_related('partner_profile', 'team', 'market'):
        key = f"{alliance.team_id}_{alliance.market.code}_{alliance.partner_profile.partnership_code}"
        profile = alliance.partner_profile

        alliances[key] = {
            'team_id': alliance.team_id,
            'market_code': alliance.market.code,
            'partner_name': profile.name,
            'partner_type': profile.partner_type,
            'partnership_code': profile.partnership_code,
            'satisfaction': float(alliance.satisfaction),
            'feature_satisfaction': alliance.feature_satisfaction or {},
            'status': alliance.status,
            'benefit_delivery_pct': float(alliance.benefit_delivery_pct),
            'satisfaction_floor': float(profile.satisfaction_floor),
            'renegotiation_threshold': float(profile.renegotiation_threshold),
            'patience_rounds': profile.patience_rounds,
            'benefit_curve': profile.benefit_curve,
            'established_round': alliance.established_round,
            'rounds_below_renegotiation': alliance.rounds_below_renegotiation,
            'rounds_below_dissolution': alliance.rounds_below_dissolution,
        }

    return alliances


# ---------------------------------------------------------------------------
# Government serialization (CC-32F)
# ---------------------------------------------------------------------------

def _serialize_governments(game, scenario):
    """Serialize government profiles and satisfaction data."""
    governments = {}

    for gp in GovernmentProfile.objects.filter(
        scenario=scenario,
    ).select_related('market'):
        market_code = gp.market.code

        # Per-team satisfaction records
        satisfaction_per_team = {}
        for gs in GovernmentSatisfaction.objects.filter(
            game=game, market=gp.market,
        ):
            satisfaction_per_team[str(gs.team_id)] = {
                'satisfaction': float(gs.satisfaction),
                'objective_scores': gs.objective_scores or {},
                'status': gs.status,
                'rounds_below_warning': gs.rounds_below_warning,
                'rounds_below_restriction': gs.rounds_below_restriction,
                'active_incentive': gs.active_incentive,
                'active_restriction': gs.active_restriction,
            }

        governments[market_code] = {
            'name': gp.name,
            'description': gp.description,
            'policy_priorities': gp.policy_priorities or [],
            'incentive_threshold': float(gp.incentive_threshold),
            'warning_threshold': float(gp.warning_threshold),
            'restriction_threshold': float(gp.restriction_threshold),
            'max_incentive_value_per_round': float(gp.max_incentive_value_per_round),
            'procurement_budget_per_round': float(gp.procurement_budget_per_round),
            'procurement_frequency': gp.procurement_frequency,
            'policy_volatility': float(gp.policy_volatility),
            'patience_rounds': gp.patience_rounds,
            'satisfaction_per_team': satisfaction_per_team,
        }

    return governments


# ---------------------------------------------------------------------------
# Events & global conditions
# ---------------------------------------------------------------------------

def _serialize_round_events(game, round_number):
    """Serialize events triggered this round."""
    events = []
    for event in EventInstance.objects.filter(
        game=game, round_number=round_number,
    ).select_related('event_template'):
        events.append({
            'template_code': event.event_template.name if event.event_template else 'unknown',
            'name': event.event_template.name if event.event_template else '',
            'severity': getattr(event.event_template, 'severity', 'medium'),
        })
    return events


def _serialize_global_conditions(game, round_number, scenario):
    """Serialize global economic conditions."""
    from core.models.scenario import MarketConditionByRound

    conditions = {
        'round_number': round_number,
        'total_rounds': scenario.num_rounds,
    }

    # Aggregate market growth rates
    growth_rates = {}
    for market in scenario.markets.all():
        mc = MarketConditionByRound.objects.filter(
            market=market, round_number=round_number,
        ).first()
        if mc:
            growth_rates[market.code] = float(market.base_growth_rate) + float(mc.growth_rate_modifier)
    conditions['market_growth_rates'] = growth_rates

    return conditions
