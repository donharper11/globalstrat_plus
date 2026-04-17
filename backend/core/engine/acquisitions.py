"""
Engine Step 4.6: Acquisition Processing (CC-20).

Process M&A decisions: create TeamAcquisition records, grant immediate
benefits (plant, distribution, talent), and advance integration for
in-progress acquisitions.
"""
import logging
from decimal import Decimal

from core.models.decisions import DecisionSubmission, DecisionAcquisition
from core.models.team_state import (
    TeamAcquisition, TeamPlant, TeamMarketModifier,
)

logger = logging.getLogger(__name__)


def process_acquisitions(context):
    """
    Process M&A decisions for all teams, then advance integration
    for previously acquired targets.
    """
    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team,
            round__round_number=context.round_number,
            round__game=context.game,
            status='locked',
        ).first()
        if not submission:
            continue

        for decision in DecisionAcquisition.objects.filter(
            submission=submission,
        ).select_related('acquisition_target__market'):
            target = decision.acquisition_target

            # Already acquired by this or another team — skip
            if TeamAcquisition.objects.filter(acquisition_target=target).exists():
                _notify_rejected_bid(context, team, target)
                continue

            # Create acquisition record
            TeamAcquisition.objects.create(
                team=team,
                acquisition_target=target,
                acquired_round=context.round_number,
                integration_complete=False,
                integration_rounds_remaining=target.integration_rounds,
                total_cost_paid=target.base_acquisition_cost,
            )

            # Immediate benefit: plant (operational immediately)
            if target.includes_plant and target.plant_capacity > 0:
                TeamPlant.objects.create(
                    team=team,
                    market=target.market,
                    capacity_units=target.plant_capacity,
                    status='operational',
                    construction_started_round=context.round_number,
                    completion_round=context.round_number,
                )

            # Immediate benefit: distribution reach modifier
            if target.includes_distribution and target.distribution_reach_bonus > 0:
                TeamMarketModifier.objects.create(
                    team=team,
                    market=target.market,
                    modifier_type='distribution_reach',
                    value=float(target.distribution_reach_bonus),
                    source=f'Acquisition of {target.target_name}',
                    expires_round=None,
                )

            # Immediate benefit: talent bonuses
            if target.talent_bonus:
                from core.models.talent import TeamTalentState
                for pool, bonus in target.talent_bonus.items():
                    state = TeamTalentState.objects.filter(
                        team=team,
                        talent_pool=pool,
                        round_number=context.round_number,
                    ).first()
                    if state:
                        state.talent_level = min(
                            state.talent_level + Decimal(str(bonus)),
                            Decimal('10'),
                        )
                        state.save()

    # Advance integration for all in-progress acquisitions
    for acq in TeamAcquisition.objects.filter(integration_complete=False):
        if acq.acquired_round == context.round_number:
            continue  # Just acquired this round — don't count down yet
        acq.integration_rounds_remaining -= 1
        if acq.integration_rounds_remaining <= 0:
            acq.integration_complete = True
        acq.save()

    context.log.append('Acquisitions processed')


def _notify_rejected_bid(context, team, target):
    """Create a TeamNotification when a competing bid is rejected."""
    message = (
        f"{target.target_name} was acquired by another team. "
        f"Your acquisition bid was not fulfilled. No cost has been charged."
    )
    context.log.append(
        f"Acquisition bid rejected for {team.name}: {target.target_name} already acquired"
    )
    try:
        from core.models.messaging import TeamNotification
        from core.models.course import SimulationInstance
        instance = SimulationInstance.objects.filter(game_id=context.game.id).first()
        TeamNotification.objects.create(
            team_id=team.id,
            round_id=context.round_number,
            instance_id=instance.instance_id if instance else None,
            notification_text=message,
            is_read=False,
        )
    except Exception as exc:
        logger.warning("Failed to create rejected-bid notification: %s", exc)
