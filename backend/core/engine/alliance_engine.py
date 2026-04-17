"""
CC-32D: AI Alliance Partners — Satisfaction Engine (Step 5.5)

Evaluates each active alliance partner's satisfaction based on weighted
feature preferences, updates partnership status, and calculates benefit
delivery percentage. Integrated into advance_round.py between strategy
effects (Step 4) and fit scores (Step 5).

CC-3.5: post-dissolution partner-defection roll uses seeded RNG.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.engine.rng import get_rng
from core.models.cc32d_models import AlliancePartnerProfile, TeamAllianceState
from core.models.cc31_models import TeamMarketCompliance, TalentAllocation
from core.models.team_state import TeamPartnership, TeamMarketPresence
from core.models.decisions import DecisionSubmission, DecisionMarketing
from core.models.results_financials import RoundResultMarketRevenue, RoundResultFinancials


# ---------------------------------------------------------------------------
# Main entry point — called from advance_round.py
# ---------------------------------------------------------------------------

def process_alliances(context):
    """
    Step 5.5: Evaluate each active alliance and update satisfaction/status.
    Also creates TeamAllianceState for newly established partnerships.
    """
    game = context.game
    round_number = context.round_number

    # Create alliance states for new partnerships that have profiles
    _initialize_new_alliance_states(game, round_number)

    # Process each active alliance
    for alliance in TeamAllianceState.objects.filter(game=game).exclude(status='DISSOLVED'):
        partner = alliance.partner_profile
        team = alliance.team
        market = alliance.market

        # B1: Calculate satisfaction
        feature_scores = {}
        for pref in partner.preferences:
            feature = pref['feature']
            score = _evaluate_feature(feature, team, game, market, round_number, context)
            feature_scores[feature] = round(score, 2)

        total_weight = sum(p['weight'] for p in partner.preferences)
        if total_weight > 0:
            weighted_sum = sum(
                feature_scores.get(p['feature'], 0.5) * p['weight']
                for p in partner.preferences
            )
            satisfaction = Decimal(str(round(weighted_sum / total_weight, 2)))
        else:
            satisfaction = Decimal('0.50')

        alliance.satisfaction = satisfaction
        alliance.feature_satisfaction = feature_scores

        # B2: Update status
        _update_status(alliance, partner, game, round_number, context)

        # B3: Update benefit delivery
        _update_benefit_delivery(alliance, partner)

        # B5: Process dissolution consequences
        if alliance.status == 'DISSOLVING' and alliance.dissolved_round == round_number:
            _process_dissolution(alliance, team, game, round_number, context)

        alliance.save()

    context.log.append(f'CC-32D: Alliance satisfaction processed')


# ---------------------------------------------------------------------------
# B1: Feature evaluation
# ---------------------------------------------------------------------------

def _evaluate_feature(feature, team, game, market, round_number, context):
    """Evaluate a single alliance satisfaction feature. Returns 0.0-1.0."""

    if feature == 'market_investment':
        return _eval_market_investment(team, game, market, round_number, context)

    elif feature == 'revenue_share':
        return _eval_revenue_share(team, game, market, round_number)

    elif feature == 'governance_quality':
        return _eval_governance(team, game)

    elif feature == 'localization_commitment':
        return _eval_localization(team, game, market, round_number, context)

    elif feature == 'technology_sharing':
        return _eval_technology_sharing(team, game, market)

    elif feature == 'exclusivity_respect':
        return _eval_exclusivity(team, game, market)

    elif feature == 'communication_quality':
        return _eval_communication(team, game, round_number)

    return 0.5  # Unknown feature — neutral


def _eval_market_investment(team, game, market, round_number, context):
    """How much is the team investing in this market vs total?"""
    submission = DecisionSubmission.objects.filter(
        team=team, round__round_number=round_number, round__game=game,
    ).first()
    if not submission:
        return 0.3

    # Market-specific spend: marketing + compliance
    market_spend = Decimal('0')
    for md in submission.marketing_decisions.filter(market=market):
        market_spend += md.promotion_budget

    from core.models.cc31_models import ComplianceInvestment
    ci = ComplianceInvestment.objects.filter(submission=submission, market=market).first()
    if ci:
        market_spend += ci.investment_amount

    # Total spend across all markets
    total_spend = Decimal('0')
    for md in submission.marketing_decisions.all():
        total_spend += md.promotion_budget
    for ci_all in ComplianceInvestment.objects.filter(submission=submission):
        total_spend += ci_all.investment_amount

    if total_spend <= 0:
        return 0.3

    ratio = float(market_spend / total_spend)
    # Partner expects ~20-30% of investment in their market
    return min(1.0, ratio / 0.25)


def _eval_revenue_share(team, game, market, round_number):
    """Is the partnership generating growing revenue?"""
    current = RoundResultMarketRevenue.objects.filter(
        team=team, round_number=round_number, market=market,
    ).first()
    prev = RoundResultMarketRevenue.objects.filter(
        team=team, round_number=round_number - 1, market=market,
    ).first()

    if not current:
        return 0.4  # No revenue yet — slightly below neutral

    current_rev = float(current.market_revenue) if current else 0
    if prev and float(prev.market_revenue) > 0:
        prev_rev = float(prev.market_revenue)
        growth = (current_rev - prev_rev) / prev_rev
        return min(1.0, max(0.0, 0.5 + growth * 2))

    return 0.5  # First round in market — neutral


def _eval_governance(team, game):
    """Team's governance quality based on active commitments."""
    from core.models.cc31_models import TeamGovernanceCommitment
    active_count = TeamGovernanceCommitment.objects.filter(
        game=game, team=team, is_active=True,
    ).count()
    # Scale: 0 commitments = 0.3, 1 = 0.5, 2 = 0.7, 3+ = 0.9+
    return min(1.0, 0.3 + active_count * 0.2)


def _eval_localization(team, game, market, round_number, context):
    """Talent allocation + compliance in this market."""
    # Compliance level
    compliance = TeamMarketCompliance.objects.filter(
        game=game, team=team, market=market,
    ).first()
    compliance_score = float(compliance.compliance_level) if compliance else 0.0

    # Local staff count from talent allocation
    from core.engine.utils import get_config
    baseline = int(get_config(game.scenario, 'localization_staff_baseline', default=10))

    submission = DecisionSubmission.objects.filter(
        team=team, round__round_number=round_number, round__game=game,
    ).first()
    local_staff = 0
    if submission:
        for alloc in TalentAllocation.objects.filter(submission=submission):
            local_staff += alloc.market_allocation.get(market.code, 0)

    staffing_score = min(1.0, local_staff / baseline) if baseline > 0 else 0.5

    return (staffing_score + compliance_score) / 2


def _eval_technology_sharing(team, game, market):
    """For tech/JV partners: IP exposure indicates sharing."""
    presence = TeamMarketPresence.objects.filter(
        team=team, market=market, status='active',
    ).first()
    if presence and presence.ip_exposure_cumulative:
        # Higher IP exposure = more sharing = partner happier
        return min(1.0, 0.4 + float(presence.ip_exposure_cumulative) * 0.6)
    return 0.5  # Default moderate


def _eval_exclusivity(team, game, market):
    """Is the team working with competing partners in this market?"""
    partner_count = TeamPartnership.objects.filter(
        team=team, market=market, status='active',
    ).count()
    # 1 partner = fine, each additional = -0.2
    if partner_count <= 1:
        return 1.0
    return max(0.3, 1.0 - (partner_count - 1) * 0.2)


def _eval_communication(team, game, round_number):
    """Check if CC-32A communication scores exist."""
    try:
        from core.models.cc32_models import TeamCommunication
        comms = TeamCommunication.objects.filter(
            game=game, team=team, is_draft=False,
        )
        if comms.exists():
            scores = [
                c.evaluation.get('overall_score', 50) / 100
                for c in comms
                if c.evaluation
            ]
            if scores:
                return sum(scores) / len(scores)
    except Exception:
        pass
    return 0.5  # No communication data — neutral


# ---------------------------------------------------------------------------
# B2: Status updates
# ---------------------------------------------------------------------------

def _update_status(alliance, partner, game, round_number, context):
    """Update partnership status based on satisfaction history."""
    if alliance.status == 'DISSOLVED':
        return

    satisfaction = float(alliance.satisfaction)
    reneg_threshold = float(partner.renegotiation_threshold)
    floor = float(partner.satisfaction_floor)

    if satisfaction >= reneg_threshold:
        # Healthy — reset counters
        alliance.status = 'HEALTHY'
        alliance.rounds_below_renegotiation = 0
        alliance.rounds_below_dissolution = 0
        alliance.renegotiation_demands = None

    elif satisfaction >= floor:
        # Strained — below renegotiation threshold
        alliance.rounds_below_renegotiation += 1
        alliance.rounds_below_dissolution = 0

        if alliance.rounds_below_renegotiation >= partner.patience_rounds:
            alliance.status = 'RENEGOTIATING'
            alliance.renegotiation_demands = _generate_demands(alliance, partner)
            context.log.append(
                f'CC-32D: {partner.name} demanding renegotiation with {alliance.team.name} in {alliance.market.code}'
            )
        else:
            alliance.status = 'STRAINED'

    else:
        # Below dissolution threshold
        alliance.rounds_below_dissolution += 1

        if alliance.rounds_below_dissolution >= partner.patience_rounds:
            alliance.status = 'DISSOLVING'
            alliance.dissolved_round = round_number
            context.log.append(
                f'CC-32D: {partner.name} terminating partnership with {alliance.team.name} in {alliance.market.code}'
            )
        else:
            alliance.status = 'STRAINED'
            alliance.rounds_below_renegotiation += 1


def _generate_demands(alliance, partner):
    """Generate specific demands based on weakest features."""
    demands = []
    feature_scores = alliance.feature_satisfaction or {}
    sorted_features = sorted(feature_scores.items(), key=lambda x: x[1])

    demand_templates = {
        'market_investment': {
            'type': 'increase_investment',
            'description': f'{partner.name} demands increased investment in {alliance.market.name}',
            'requirement': 'Increase compliance + marketing investment by 50% in this market',
        },
        'localization_commitment': {
            'type': 'increase_local_staff',
            'description': f'{partner.name} wants to see more local hiring',
            'requirement': 'Allocate at least 8 staff to this market',
        },
        'governance_quality': {
            'type': 'governance_improvement',
            'description': f'{partner.name} concerned about governance standards',
            'requirement': 'Adopt at least 2 governance commitments',
        },
        'revenue_share': {
            'type': 'revenue_growth',
            'description': f'{partner.name} wants to see market revenue growth',
            'requirement': 'Increase marketing spend or launch new product in this market',
        },
        'technology_sharing': {
            'type': 'technology_sharing',
            'description': f'{partner.name} wants deeper technology collaboration',
            'requirement': 'Increase R&D investment through this partnership',
        },
        'exclusivity_respect': {
            'type': 'reduce_competing_partners',
            'description': f'{partner.name} unhappy about competing partnerships',
            'requirement': 'Reduce number of active partnerships in this market',
        },
    }

    for feature, score in sorted_features[:2]:
        if feature in demand_templates:
            demands.append(demand_templates[feature])

    return demands


# ---------------------------------------------------------------------------
# B3: Benefit delivery calculation
# ---------------------------------------------------------------------------

def _update_benefit_delivery(alliance, partner):
    """Calculate benefit delivery percentage from satisfaction and curve."""
    if alliance.status in ('DISSOLVED', 'DISSOLVING'):
        alliance.benefit_delivery_pct = Decimal('0')
        return

    satisfaction = float(alliance.satisfaction)
    curve = partner.benefit_curve

    if curve == 'LINEAR':
        alliance.benefit_delivery_pct = Decimal(str(max(0.20, satisfaction))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP,
        )
    elif curve == 'THRESHOLD':
        if satisfaction >= 0.7:
            alliance.benefit_delivery_pct = Decimal('1.00')
        elif satisfaction >= 0.4:
            alliance.benefit_delivery_pct = Decimal('0.60')
        else:
            alliance.benefit_delivery_pct = Decimal('0.30')
    elif curve == 'BINARY':
        if satisfaction >= float(partner.satisfaction_floor):
            alliance.benefit_delivery_pct = Decimal('1.00')
        else:
            alliance.benefit_delivery_pct = Decimal('0')

    # Renegotiation caps at 50%
    if alliance.status == 'RENEGOTIATING':
        alliance.benefit_delivery_pct = min(
            alliance.benefit_delivery_pct, Decimal('0.50'),
        )


# ---------------------------------------------------------------------------
# B5: Dissolution consequences
# ---------------------------------------------------------------------------

def _process_dissolution(alliance, team, game, round_number, context):
    """Handle partnership dissolution — benefits lost, penalties applied."""
    alliance.benefit_delivery_pct = Decimal('0')

    # Terminate the underlying TeamPartnership
    profile = alliance.partner_profile
    TeamPartnership.objects.filter(
        team=team, market=alliance.market, status='active',
        strategy_option__code__icontains=_code_fragment(profile.partnership_code),
    ).update(status='terminated', terminated_round=round_number)

    # Channel penalty: apply via ActiveModifier
    from core.models.results import ActiveModifier
    ActiveModifier.objects.create(
        game=game,
        team=team,
        modifier_type='cost',
        modifier_key='channel_penalty_dissolution',
        modifier_value=Decimal('-0.15'),
        source=f'CC-32D: {profile.name} dissolution',
        round_applied=round_number,
        expires_round=round_number + 2,
    )

    # Regulator penalty
    ActiveModifier.objects.create(
        game=game,
        team=team,
        modifier_type='preference',
        modifier_key='regulator_penalty_dissolution',
        modifier_value=Decimal('-0.05'),
        source=f'CC-32D: {profile.name} dissolution',
        round_applied=round_number,
        expires_round=round_number + 1,
    )

    # 40% chance dissolved partner joins AI competitor
    class_id = game.section_id or game.id
    defection_rng = get_rng(
        class_id, round_number, f"alliance_partner_defection:{alliance.id}",
    )
    if defection_rng.random() < 0.4:
        from core.models.scenario import AICompetitorDefinition
        ai_comp = AICompetitorDefinition.objects.filter(
            scenario=game.scenario,
        ).first()
        if ai_comp:
            context.log.append(
                f'CC-32D: {profile.name} now partnering with {ai_comp.name} in {alliance.market.code}'
            )

    context.log.append(
        f'CC-32D: Partnership dissolved — {profile.name} in {alliance.market.code}'
    )


def _code_fragment(partnership_code):
    """Extract a useful fragment for matching strategy_option codes."""
    # partnership_code like 'local_strategic_na' or 'distribution_partner'
    # strategy_option.code might be 'local_strategic_na' or 'distribution_partner'
    return partnership_code.split('_')[0]  # 'local', 'distribution', etc.


# ---------------------------------------------------------------------------
# Alliance state initialization
# ---------------------------------------------------------------------------

def _initialize_new_alliance_states(game, round_number):
    """Create TeamAllianceState for partnerships that have profiles but no state."""
    scenario = game.scenario

    for team in game.teams.all():
        active_partnerships = TeamPartnership.objects.filter(
            team=team, status='active',
        ).select_related('strategy_option', 'market')

        for tp in active_partnerships:
            code = tp.strategy_option.code if tp.strategy_option else ''

            # Find matching profile
            profile = AlliancePartnerProfile.objects.filter(
                scenario=scenario,
                partnership_code=code,
                market=tp.market,
            ).first()

            if not profile:
                continue

            # Create if doesn't exist
            TeamAllianceState.objects.get_or_create(
                game=game,
                team=team,
                partner_profile=profile,
                defaults={
                    'market': tp.market,
                    'satisfaction': Decimal('0.70'),
                    'status': 'HEALTHY',
                    'benefit_delivery_pct': Decimal('1.00'),
                    'established_round': tp.established_round or round_number,
                },
            )
