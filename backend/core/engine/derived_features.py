"""
CC-25: Derived Feature Calculation Engine.

Calculate derived feature levels from game state each round.
Called AFTER financials but BEFORE performance index, so the
preference engine sees the latest financial-driven feature levels.
"""
from decimal import Decimal

from core.models.scenario import FeatureDefinition, MarketDefinition
from core.models.results_financials import RoundResultFinancials
from core.models.team_state import (
    TeamStrategyFeatureLevel,
    TeamMarketPresence,
    TeamPlant,
    TeamPartnership,
)
from core.models.decisions import DecisionMarketing, DecisionESG, DecisionSubmission


def calculate_derived_features(context):
    """
    Calculate all derived feature levels from game state.
    Called in the engine pipeline after financials (Step 12)
    but before performance index (Step 13).
    """
    for team in context.teams:
        financials = RoundResultFinancials.objects.filter(
            game=context.game, team=team, round_number=context.round_number,
        ).first()
        prev_financials = RoundResultFinancials.objects.filter(
            game=context.game, team=team, round_number=context.round_number - 1,
        ).first()

        if not financials:
            continue

        # === FINANCIAL STABILITY ===
        d_e = float(financials.debt_to_equity or 0)
        if d_e <= 0.3:
            de_score = 10
        elif d_e <= 0.5:
            de_score = 8
        elif d_e <= 1.0:
            de_score = 6
        elif d_e <= 1.5:
            de_score = 4
        elif d_e <= 2.0:
            de_score = 2
        else:
            de_score = 1

        cash = float(financials.cash_closing or 0)
        if cash > 40_000_000:
            cash_score = 9
        elif cash > 20_000_000:
            cash_score = 7
        elif cash > 10_000_000:
            cash_score = 5
        elif cash > 5_000_000:
            cash_score = 3
        else:
            cash_score = 1

        interest = float(financials.interest_expense or 0)
        oi = float(financials.operating_income or 0)
        if interest > 0 and oi > 0:
            coverage = oi / interest
            coverage_score = min(int(coverage), 10)
        else:
            coverage_score = 10  # No debt = no risk

        stability = round(de_score * 0.4 + cash_score * 0.3 + coverage_score * 0.3, 1)
        _update(team, 'financial_stability', context, stability)

        # === DIVIDEND & SHAREHOLDER RETURNS ===
        dividend_yield = 0
        share_price = float(financials.share_price or 0)
        dividends_paid = float(financials.dividends_paid or 0)
        if share_price > 0 and dividends_paid > 0:
            shares = 1_000_000  # Default shares outstanding
            div_per_share = dividends_paid / shares
            dividend_yield = div_per_share / share_price

        cum_return = float(financials.shareholder_return_cumulative or 0)

        if dividend_yield >= 0.05:
            div_score = 9
        elif dividend_yield >= 0.03:
            div_score = 7
        elif dividend_yield >= 0.01:
            div_score = 5
        elif dividend_yield > 0:
            div_score = 3
        else:
            div_score = 1

        if cum_return >= 0.20:
            return_score = 10
        elif cum_return >= 0.10:
            return_score = 8
        elif cum_return >= 0:
            return_score = 5
        elif cum_return >= -0.10:
            return_score = 3
        else:
            return_score = 1

        dividend_level = round(div_score * 0.5 + return_score * 0.5, 1)
        _update(team, 'dividend_consistency', context, dividend_level)

        # === REVENUE MOMENTUM ===
        total_rev = float(financials.total_revenue or 0)
        prev_rev = float(prev_financials.total_revenue or 0) if prev_financials else 0
        if prev_rev > 0:
            growth = (total_rev - prev_rev) / prev_rev
            if growth >= 0.20:
                momentum = 10
            elif growth >= 0.10:
                momentum = 8
            elif growth >= 0.05:
                momentum = 6
            elif growth >= 0:
                momentum = 5
            elif growth >= -0.05:
                momentum = 4
            elif growth >= -0.10:
                momentum = 2
            else:
                momentum = 1
        else:
            momentum = 5  # Baseline for round with no prior revenue

        _update(team, 'revenue_momentum', context, momentum)

        # === PROFITABILITY ===
        net_margin = float(financials.net_margin_pct or 0)
        roe = float(financials.roe or 0)

        if net_margin >= 0.20:
            margin_score = 10
        elif net_margin >= 0.10:
            margin_score = 7
        elif net_margin >= 0.05:
            margin_score = 5
        elif net_margin >= 0:
            margin_score = 3
        else:
            margin_score = 1

        if roe >= 0.20:
            roe_score = 10
        elif roe >= 0.10:
            roe_score = 7
        elif roe >= 0.05:
            roe_score = 5
        elif roe >= 0:
            roe_score = 3
        else:
            roe_score = 1

        profit_level = round(margin_score * 0.5 + roe_score * 0.5, 1)
        _update(team, 'profitability', context, profit_level)

        # === INNOVATION INTENSITY ===
        rd_expense = float(financials.rd_expense or 0)
        rd_pct = rd_expense / total_rev if total_rev > 0 else 0

        if rd_pct >= 0.15:
            rd_score = 9
        elif rd_pct >= 0.10:
            rd_score = 7
        elif rd_pct >= 0.05:
            rd_score = 5
        elif rd_pct > 0:
            rd_score = 3
        else:
            rd_score = 1

        gen_score = min(_get_highest_platform_gen(team) * 3, 10)
        innovation = round(rd_score * 0.6 + gen_score * 0.4, 1)
        _update(team, 'innovation_intensity', context, innovation)

        # === MARKET EXPANSION (global) ===
        market_count = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).count()
        total_markets = MarketDefinition.objects.filter(
            scenario=context.scenario,
        ).count()

        expansion_ratio = market_count / max(total_markets, 1)
        if expansion_ratio >= 1.0:
            expansion = 10
        elif expansion_ratio >= 0.66:
            expansion = 7
        elif expansion_ratio >= 0.33:
            expansion = 4
        else:
            expansion = 2

        _update(team, 'market_expansion', context, expansion)

        # === ESG SUB-FEATURES ===
        _calculate_esg_features(team, context)

        # === PER-MARKET FEATURES ===
        for market in MarketDefinition.objects.filter(scenario=context.scenario):
            _calculate_market_features(team, market, context)

    context.log.append('CC-25: Derived features calculated')


def _calculate_esg_features(team, context):
    """Calculate sustainability, governance, and social responsibility features from ESG decisions."""
    # Get latest ESG decision
    submission = DecisionSubmission.objects.filter(
        team=team, round__round_number=context.round_number,
    ).first()

    env_investment = 0
    social_investment = 0
    gov_commitment_count = 0

    if submission:
        esg = DecisionESG.objects.filter(submission=submission).first()
        if esg:
            env_investment = float(esg.environmental_investment or 0)
            social_investment = float(esg.social_investment or 0)
            gov_val = esg.governance_commitments or 0
            if isinstance(gov_val, (list, dict)):
                gov_commitment_count = len(gov_val)
            else:
                gov_commitment_count = int(gov_val)

    # Sustainability — based on environmental investment
    if env_investment >= 3_000_000:
        sus_level = 9
    elif env_investment >= 2_000_000:
        sus_level = 7
    elif env_investment >= 1_000_000:
        sus_level = 5
    elif env_investment >= 500_000:
        sus_level = 3
    elif env_investment > 0:
        sus_level = 2
    else:
        sus_level = 0

    _update(team, 'sustainability_commitment', context, sus_level)

    # Governance — CC-31J: sum of active commitment boosts, or legacy count-based
    from core.models.cc31_models import GovernanceCommitmentType, TeamGovernanceCommitment
    game = context.game
    scenario = game.scenario if game else None
    commitment_types = GovernanceCommitmentType.objects.filter(
        scenario=scenario,
    ) if scenario else GovernanceCommitmentType.objects.none()

    if commitment_types.exists():
        # NEW: Sum governance_quality boosts from active commitments
        active_tgcs = TeamGovernanceCommitment.objects.filter(
            game=game, team=team, is_active=True,
        ).select_related('commitment_type')
        gov_boost_sum = 0.0
        for tgc in active_tgcs:
            for benefit in (tgc.commitment_type.benefits or []):
                if benefit.get('target') == 'governance_quality':
                    gov_boost_sum += float(benefit.get('boost', 0))
        # Scale: boost sum of ~0.85 (all 5) maps to 0-10 feature level
        # 0.85 total boost → level 9 (leading governance)
        gov_level = min(round(gov_boost_sum * 10.6), 10)

        # Apply revocation penalty: drop governance_quality during penalty period
        penalty_tgcs = TeamGovernanceCommitment.objects.filter(
            game=game, team=team, penalty_rounds_remaining__gt=0,
        ).select_related('commitment_type')
        for tgc in penalty_tgcs:
            penalty = tgc.commitment_type.revocation_penalty or {}
            reg_penalty = float(penalty.get('regulator_penalty', 0))
            gov_level = max(gov_level + int(reg_penalty * 10), 0)
    else:
        # LEGACY fallback
        commitment_count = gov_commitment_count
        if commitment_count >= 4:
            gov_level = 9
        elif commitment_count >= 3:
            gov_level = 7
        elif commitment_count >= 2:
            gov_level = 5
        elif commitment_count >= 1:
            gov_level = 3
        else:
            gov_level = 0

    _update(team, 'governance_quality', context, gov_level)

    # Social responsibility — based on social investment
    if social_investment >= 3_000_000:
        social_level = 9
    elif social_investment >= 2_000_000:
        social_level = 7
    elif social_investment >= 1_000_000:
        social_level = 5
    elif social_investment >= 500_000:
        social_level = 3
    elif social_investment > 0:
        social_level = 2
    else:
        social_level = 0

    _update(team, 'social_responsibility', context, social_level)


def _calculate_market_features(team, market, context):
    """Calculate per-market derived features: local_manufacturing, distribution, tenure."""
    presence = TeamMarketPresence.objects.filter(
        team=team, market=market, status='active',
    ).first()

    # LOCAL MANUFACTURING
    has_plant = TeamPlant.objects.filter(
        team=team, market=market, status='operational',
    ).exists()

    if has_plant:
        mfg_level = 8  # Strong local commitment
    elif presence:
        mfg_level = 2  # Present but no local production
    else:
        mfg_level = 0  # Not in market

    _update(team, 'local_manufacturing', context, mfg_level, market=market)

    # DISTRIBUTION COMMITMENT
    if presence:
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=context.round_number,
        ).first()

        dist_investment = 0
        sales_reps = 0
        if submission:
            for dm in DecisionMarketing.objects.filter(
                submission=submission, market=market,
            ):
                dist_investment += float(dm.distribution_investment or 0)
                sales_reps += dm.sales_team_count or 0

        has_dist_partner = TeamPartnership.objects.filter(
            team=team, market=market, status='active',
        ).exists()

        # Acquisition distribution reach bonus
        from core.models.team_state import TeamMarketModifier
        acq_dist_bonus = sum(
            m.value for m in TeamMarketModifier.objects.filter(
                team=team, market=market, modifier_type='distribution_reach',
            )
        )

        dist_score = 1
        if dist_investment > 500_000:
            dist_score += 3
        elif dist_investment > 200_000:
            dist_score += 2
        elif dist_investment > 0:
            dist_score += 1

        dist_score += min(sales_reps, 5)
        if has_dist_partner:
            dist_score += 2
        # Acquisition distribution reach: 0.08 bonus → +2 points (scaled ×25)
        dist_score += int(acq_dist_bonus * 25)

        dist_level = min(dist_score, 10)
    else:
        dist_level = 0

    _update(team, 'distribution_commitment', context, dist_level, market=market)

    # MARKET TENURE
    if presence:
        entry_round = presence.established_round or 0
        tenure_rounds = context.round_number - entry_round
        tenure_level = min(tenure_rounds + 2, 10)  # Start at 2, grow by 1 per round
    else:
        tenure_level = 0

    _update(team, 'market_tenure', context, tenure_level, market=market)


def _update(team, feature_code, context, level, market=None):
    """Update a derived strategy feature level."""
    feature = FeatureDefinition.objects.filter(
        scenario=context.scenario, code=feature_code,
    ).first()
    if not feature:
        return

    clamped = min(max(level, 0), 10)
    TeamStrategyFeatureLevel.objects.update_or_create(
        team=team,
        feature=feature,
        market=market,
        round_number=context.round_number,
        defaults={'current_level': Decimal(str(clamped))},
    )


def _get_highest_platform_gen(team):
    """Get the highest platform generation order the team has access to."""
    from core.models.team_state import TeamPlatform
    platforms = TeamPlatform.objects.filter(team=team).select_related('platform_generation')
    if not platforms.exists():
        return 1
    return max(p.platform_generation.generation_order for p in platforms)
