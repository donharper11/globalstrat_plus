"""
Engine Step 6: Campaign Focus Multiplier.
From 03-engine-logic.md Section 6.

When a team selects 2-3 features to emphasize in their marketing campaign,
those features get a perception boost in the preference matching. The bonus
is proportional to the feature's weight AND the team's actual strength on
that feature — you can't fake quality with marketing alone.
"""
from core.models.decisions import DecisionMarketing, DecisionSubmission
from core.models.team_state import (
    TeamPlatformFeatureLevel, TeamProductMarket,
    TeamMarketPresence,
)
from core.models.scenario import SegmentPreference, FeatureDefinition
from core.engine.utils import get_config


def apply_campaign_multipliers(context):
    """
    Engine Step 6: Apply campaign focus multiplier to fit scores.
    For each team's product in each market, boost fit scores based on
    campaign feature selection.
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number

    campaign_multiplier = get_config(
        scenario, 'campaign_focus_multiplier', default=0.15,
    )

    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()
        if not submission:
            continue

        mkt_decisions = DecisionMarketing.objects.filter(
            submission=submission,
        ).select_related('team_product', 'market')

        for mkt_dec in mkt_decisions:
            product = mkt_dec.team_product
            market = mkt_dec.market
            campaign_feature_ids = mkt_dec.campaign_focus_feature_ids or []

            if not campaign_feature_ids:
                continue

            # Get segments in this market
            seg_ids = [
                seg_id for (t_id, seg_id, m_id), _ in context.fit_scores.items()
                if t_id == team.id and m_id == market.id
            ]

            for seg_id in seg_ids:
                key = (team.id, seg_id, market.id)
                fit_score = context.fit_scores.get(key, 0.0)
                best_product = context.best_products.get(key)

                # Only apply campaign bonus if this product is the best one
                if best_product is None or best_product.id != product.id:
                    continue

                # CC-16: Commercial talent amplifier
                from core.engine.talent import get_talent_level
                from decimal import Decimal as _D
                from core.engine.utils import clamp as _clamp
                commercial_talent = get_talent_level(team, 'commercial', context.round_number)
                talent_amplifier = float(_clamp(
                    _D('1.0') + (commercial_talent - _D('3')) * _D('0.08'),
                    _D('0.70'), _D('1.50'),
                ))

                # Calculate campaign bonus
                campaign_bonus = 0.0
                for feature_id in campaign_feature_ids:
                    try:
                        pref = SegmentPreference.objects.get(
                            segment_id=seg_id, feature_id=feature_id,
                        )
                    except SegmentPreference.DoesNotExist:
                        continue

                    # Get actual level for this feature
                    actual_level = _get_actual_level(
                        team, product, feature_id, context, market,
                    )
                    feature = pref.feature
                    ceiling = float(feature.max_value)

                    if ceiling <= 0:
                        continue

                    feature_strength = actual_level / ceiling  # 0.0 to 1.0

                    # Bonus = weight × strength × multiplier
                    campaign_bonus += (
                        float(pref.weight) * feature_strength * campaign_multiplier
                    )

                # CC-16: Apply commercial talent amplifier
                campaign_bonus *= talent_amplifier

                # CC-32B: Apply org coordination modifier
                org_mods = getattr(context, 'org_modifiers', {}).get(team.id, {})
                coordination_mod = float(org_mods.get('coordination_modifier', 1.0))
                campaign_bonus *= coordination_mod

                adjusted_fit = min(fit_score + campaign_bonus, 1.0)
                context.fit_scores[key] = adjusted_fit
                context.adjusted_fit_scores[key] = adjusted_fit

    context.log.append('Campaign focus multipliers applied')


def _get_actual_level(team, product, feature_id, context, market):
    """Get the actual level of a feature for a product."""
    try:
        feature = FeatureDefinition.objects.get(id=feature_id)
    except FeatureDefinition.DoesNotExist:
        return 0.0

    if feature.layer == 'platform':
        try:
            fl = TeamPlatformFeatureLevel.objects.get(
                team_platform=product.team_platform,
                feature_id=feature_id,
            )
            return float(fl.current_level)
        except TeamPlatformFeatureLevel.DoesNotExist:
            return float(feature.default_value)

    elif feature.layer == 'strategy':
        from core.models.team_state import TeamStrategyFeatureLevel
        try:
            sl = TeamStrategyFeatureLevel.objects.get(
                team=team, feature_id=feature_id, market=market,
                round_number=context.round_number,
            )
            return float(sl.current_level)
        except TeamStrategyFeatureLevel.DoesNotExist:
            return float(feature.default_value)

    elif feature.layer == 'marketing':
        # Marketing features are derived — use the already-calculated value
        # from the fit score computation. For campaign purposes, use default.
        return float(feature.default_value)

    return 0.0
