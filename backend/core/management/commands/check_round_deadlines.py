"""
Management command to check for round deadlines and auto-advance simulations.

Run via cron every 5 minutes:
    */5 * * * * cd /home/ubuntu/projects/globalstrat/backend && python manage.py check_round_deadlines
"""
import datetime
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Round, SimulationState
from core.models.course import SimulationInstance
from core.services.round_engine import advance_round

logger = logging.getLogger('core.round_scheduler')


class Command(BaseCommand):
    help = 'Check active simulations for expired round deadlines and auto-advance.'

    def handle(self, *args, **options):
        now = timezone.now()

        # --- Phase 1: Lock decisions for rounds past deadline ---
        expired_rounds = Round.objects.filter(
            deadline__lte=now,
            decisions_locked=False,
        ).exclude(status='completed')

        for r in expired_rounds:
            r.decisions_locked = True
            r.lock_reason = 'deadline_expired'
            r.save()
            self.stdout.write(
                f'Locked decisions for Round {r.round_number} '
                f'(game {r.game_id}, deadline was {r.deadline.isoformat()})'
            )
            logger.info(
                'Locked round %s (game %s) — deadline expired',
                r.round_number, r.game_id,
            )

        # --- Phase 2: Auto-advance instances whose current round is locked ---
        instances = SimulationInstance.objects.filter(
            status='active',
            auto_advance=True,
        )

        if not instances.exists():
            if not expired_rounds.exists():
                self.stdout.write('No active auto-advance simulations found.')
            return

        advanced_count = 0

        for instance in instances:
            state = SimulationState.objects.filter(
                instance_id=instance.instance_id,
                status='active',
            ).first()

            if not state or not state.current_round_id:
                continue

            current_round = Round.objects.filter(
                round_id=state.current_round_id,
            ).first()

            if not current_round:
                continue

            # Use the new deadline field first, fall back to end_date + end_time
            if current_round.deadline:
                deadline = current_round.deadline
                if timezone.is_naive(deadline):
                    deadline = timezone.make_aware(
                        deadline, timezone.get_current_timezone()
                    )
            elif current_round.end_date:
                end_time = current_round.end_time or datetime.time(23, 59, 59)
                deadline = datetime.datetime.combine(current_round.end_date, end_time)
                if timezone.is_aware(now):
                    deadline = timezone.make_aware(
                        deadline, timezone.get_current_timezone()
                    )
            else:
                continue

            if now < deadline:
                continue

            # Check grace period from instance settings
            settings = instance.settings or {}
            grace_minutes = settings.get('grace_period_minutes', 15)
            grace_deadline = deadline + datetime.timedelta(minutes=grace_minutes)

            # Also check per-round auto_advance flag
            round_auto = current_round.auto_advance

            if not (instance.auto_advance or round_auto):
                continue

            if now < grace_deadline:
                continue

            # Deadline + grace passed — advance the round
            self.stdout.write(
                f'Auto-advancing instance {instance.instance_id} '
                f'(round {current_round.round_number}, '
                f'deadline was {deadline.isoformat()})...'
            )

            try:
                result = advance_round(state.state_id)
                advanced_count += 1

                # Sync instance current_round from the state
                state.refresh_from_db()
                if state.current_round_id:
                    next_round = Round.objects.filter(
                        round_id=state.current_round_id,
                    ).first()
                    if next_round:
                        instance.current_round = next_round.round_number
                        instance.save()

                if state.status == 'completed':
                    instance.status = 'completed'
                    instance.completed_at = timezone.now()
                    instance.save()

                completed_round = result.get('completed_round', '?')
                next_round_num = result.get('next_round')
                self.stdout.write(self.style.SUCCESS(
                    f'  Round {completed_round} completed. '
                    f'{"Next round: " + str(next_round_num) if next_round_num else "Simulation complete."}'
                ))

                logger.info(
                    'Auto-advanced instance %s: round %s -> %s',
                    instance.instance_id, completed_round, next_round_num,
                )

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  Failed to advance instance {instance.instance_id}: {e}'
                ))
                logger.error(
                    'Auto-advance failed for instance %s: %s',
                    instance.instance_id, e,
                )

        self.stdout.write(
            f'Done. {advanced_count} simulation(s) auto-advanced.'
        )
