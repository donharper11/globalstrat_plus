"""
CC-18 — Compliance enforcement.

Before this, compliance regimes were surfaced but never enforced: the
detention → market-freeze → remediation-cost → reputation loop was open. This
closes it for the regimes whose triggers have a real signal in team decisions:

  - UFLPA (`tier_2_3_xinjiang_exposure_above_threshold`): fires when a team's
    allocation to Xinjiang-adjacent suppliers exceeds the regime threshold;
    mitigated by comprehensive tier-2/3 visibility investment.
  - Customs documentation (`incomplete_or_misclassified_customs_documentation`):
    fires when a team ships to a market without a customs classification
    decision on file.

Other regimes whose triggers have no determinable signal (e.g. BIS restricted-
technology, product-safety certification) are **skipped, not faked** — we do not
invent enforcement we cannot ground.

On fire: the remediation/penalty cost is booked to the P&L
(`context.compliance_costs` → financials), the enforcing market is frozen for the
team through `freeze_until_round` (blocking sales in `calculate_revenue` via
`context.compliance_freezes`), and a reputation impact is recorded on a
`ComplianceEnforcementEvent`. Runs before revenue. Deterministic (seeded).
"""
from decimal import Decimal as D

from core.engine.sc_engine import _seed


def _team_xinjiang_exposure_pct(team, rnd):
    """% of the team's sourcing allocation (this round) that sits with
    Xinjiang-adjacent suppliers."""
    from core.models.sc_decisions import SourcingAllocation
    allocs = list(SourcingAllocation.objects.filter(team=team, round=rnd).select_related('supplier'))
    total = sum((a.allocation_pct or 0) for a in allocs)
    if total <= 0:
        return 0.0
    flagged = 0
    for a in allocs:
        flags = ((a.supplier.tier_2_3_profile or {}).get('risk_flags') or {})
        if flags.get('xinjiang_adjacent'):
            flagged += (a.allocation_pct or 0)
    return 100.0 * flagged / total


def _trigger_applies(regime, team, rnd, market):
    """(applies: bool, mitigated: bool, detail: str) for a regime/team/market,
    or None when the trigger has no determinable signal (→ skip, don't fake)."""
    from core.models.sc_decisions import SourcingDecision, CustomsClassificationDecision

    cond = regime.trigger_condition or ''
    if cond == 'tier_2_3_xinjiang_exposure_above_threshold':
        pct = _team_xinjiang_exposure_pct(team, rnd)
        threshold = float(regime.trigger_threshold_pct or 0)
        if pct <= threshold:
            return (False, False, f'xinjiang exposure {pct:.0f}% ≤ {threshold:.0f}%')
        sdec = SourcingDecision.objects.filter(team=team, round=rnd).first()
        mitigated = bool(sdec and sdec.tier_2_3_visibility_investment == 'comprehensive')
        return (True, mitigated, f'xinjiang exposure {pct:.0f}% > {threshold:.0f}%')

    if cond == 'incomplete_or_misclassified_customs_documentation':
        has_docs = CustomsClassificationDecision.objects.filter(
            team=team, round=rnd, destination_market=market).exists()
        if has_docs:
            return (False, True, 'customs classification on file')
        return (True, False, 'no customs classification for this market')

    return None  # trigger not evaluable from available signals — skip


def _mitigation_reduction_pct(regime):
    """First mitigation's `reduces_enforcement_probability_pct` (0 if none)."""
    for spec in (regime.mitigation_investments or {}).values():
        if isinstance(spec, dict) and spec.get('reduces_enforcement_probability_pct'):
            return float(spec['reduces_enforcement_probability_pct'])
    return 0.0


def _detention_cost(regime):
    dc = regime.detention_consequence or {}
    return D(str(sum(float(dc.get(k, 0) or 0) for k in (
        'remediation_cost_usd', 'reclassification_penalty_usd',
        'violation_penalty_usd', 'recertification_cost_usd'))))


def _freeze_rounds(regime):
    dc = regime.detention_consequence or {}
    return int(dc.get('market_access_freeze_rounds', dc.get('shipment_hold_rounds', 0)) or 0)


def enforce_compliance(context):
    """Carry forward active freezes, evaluate + fire new enforcement, book costs
    and freezes for this round. Runs before revenue."""
    from core.models.core import Round
    from core.models.scenario import MarketDefinition
    from core.models.sc_models import ComplianceRegime
    from core.models.sc_state import ComplianceEnforcementEvent
    import random

    context.compliance_costs = {}
    context.compliance_freezes = set()   # (team_id, market_id) frozen THIS round
    context.compliance_lost_revenue = {}

    rnd = Round.objects.filter(game=context.game, round_number=context.round_number).first()
    if rnd is None:
        return
    game = context.game
    round_number = context.round_number

    # 1. Carry forward still-active freezes from prior enforcement events.
    for ev in (ComplianceEnforcementEvent.objects
               .filter(team__game=game, freeze_until_round__gte=round_number, market__isnull=False)
               .select_related('market')):
        context.compliance_freezes.add((ev.team_id, ev.market_id))

    regimes = list(ComplianceRegime.objects.filter(scenario=context.scenario))
    all_markets = list(MarketDefinition.objects.filter(scenario=context.scenario))
    market_by_code = {m.code: m for m in all_markets}
    rng = random.Random(_seed(game.id, round_number, context.scenario.id) ^ 0x0C0FFEE)

    for team in context.teams:
        for regime in regimes:
            if regime.enforcing_market and regime.enforcing_market != 'all':
                targets = [market_by_code[regime.enforcing_market]] if regime.enforcing_market in market_by_code else []
            else:
                targets = all_markets
            for market in targets:
                # Don't re-fire while this team-market is already frozen.
                if (team.id, market.id) in context.compliance_freezes:
                    continue
                verdict = _trigger_applies(regime, team, rnd, market)
                if verdict is None:
                    continue
                applies, mitigated, detail = verdict
                if not applies:
                    continue
                prob = float(regime.baseline_enforcement_probability_per_round or 0)
                if mitigated:
                    prob *= (1 - _mitigation_reduction_pct(regime) / 100.0)
                if rng.random() >= prob:
                    continue

                # Fire.
                cost = _detention_cost(regime)
                freeze_rounds = _freeze_rounds(regime)
                freeze_until = round_number + freeze_rounds - 1 if freeze_rounds > 0 else 0
                dc = regime.detention_consequence or {}
                reputation = D(str(round(float(dc.get('shipment_value_loss_pct', 0) or 0) / 100.0, 3)))

                ComplianceEnforcementEvent.objects.create(
                    team=team, round=rnd, regime=regime, market=market,
                    cost_usd=cost, freeze_until_round=freeze_until,
                    reputation_impact=reputation, triggered_by=detail, mitigated=mitigated)

                context.compliance_costs[team.id] = context.compliance_costs.get(team.id, D('0')) + cost
                if freeze_until >= round_number:
                    context.compliance_freezes.add((team.id, market.id))

    context.log.append(
        f'Compliance: {len(context.compliance_costs)} team(s) hit, '
        f'{len(context.compliance_freezes)} team-market freeze(s) active.')
