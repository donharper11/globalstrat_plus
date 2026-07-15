"""
Close rounds whose deadline has elapsed.

Run from cron every minute:
    * * * * * cd /home/ubuntu/projects/globalstrat/backend && \
        /usr/bin/python3 manage.py check_round_deadlines >> /tmp/globalstrat-deadlines.log 2>&1

History: this command previously queried Round.decisions_locked / auto_advance
/ end_date — fields that exist on BECSR's Round model but not GlobalStrat's.
It was a copy of BECSR's command and raised FieldError on the first query, so
deadlines were never enforced. Rewritten against the real model.

Policy (chosen 2026-07-15): the deadline only CLOSES the round. Scoring and
advancing stay manual, so an instructor can inspect a round before the game
moves on. Pass --auto-process / --auto-advance to opt a run into more.
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models.core import Game, Round

logger = logging.getLogger('core.round_scheduler')


class Command(BaseCommand):
    help = 'Close any open round whose deadline has passed.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would close without changing anything.',
        )
        parser.add_argument(
            '--auto-process', action='store_true',
            help='Also run post-round processing on each round that closes.',
        )
        parser.add_argument(
            '--auto-advance', action='store_true',
            help='Also open the next round after processing. Implies --auto-process.',
        )
        parser.add_argument(
            '--game', type=int, default=None,
            help='Restrict to a single game id.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = options['dry_run']
        auto_advance = options['auto_advance']
        auto_process = options['auto_process'] or auto_advance

        # Only games actually in play. A paused game's deadline does not run
        # down — pausing would otherwise silently burn the students' time.
        games = Game.objects.filter(status='active')
        if options['game']:
            games = games.filter(id=options['game'])

        due = []
        for game in games:
            round_obj = Round.objects.filter(
                game=game, round_number=game.current_round,
            ).first()
            if not round_obj:
                continue
            if round_obj.status != 'open':
                continue
            if not round_obj.deadline:
                continue
            if now < round_obj.deadline:
                continue
            due.append((game, round_obj))

        if not due:
            self.stdout.write(f'{now:%Y-%m-%d %H:%M:%S} — no rounds due to close.')
            return

        from core.engine.advance_round import (
            close_round, process_round, advance_to_next_round,
        )

        for game, round_obj in due:
            label = f'game {game.id} ("{game.name}") round {round_obj.round_number}'

            if dry_run:
                self.stdout.write(
                    f'[dry-run] would close {label} '
                    f'(deadline {round_obj.deadline:%Y-%m-%d %H:%M})'
                )
                continue

            try:
                result = close_round(game.id, reason='deadline')
                self.stdout.write(self.style.SUCCESS(
                    f'Closed {label} — deadline was '
                    f'{round_obj.deadline:%Y-%m-%d %H:%M}, '
                    f'{result.get("submissions_locked", 0)} submission(s) locked.'
                ))
                logger.info('Deadline closed %s', label)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to close {label}: {e}'))
                logger.exception('Failed to close %s', label)
                continue

            if not auto_process:
                continue

            try:
                process_round(game.id)
                self.stdout.write(self.style.SUCCESS(f'  Processed {label}.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Processing failed for {label}: {e}'))
                logger.exception('Auto-process failed for %s', label)
                continue

            if not auto_advance:
                continue

            try:
                adv = advance_to_next_round(game.id)
                nxt = adv.get('next_round')
                self.stdout.write(self.style.SUCCESS(
                    f'  Advanced to round {nxt}.' if nxt else '  Game complete.'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Advance failed for {label}: {e}'))
                logger.exception('Auto-advance failed for %s', label)

        self.stdout.write(f'Done. {len(due)} round(s) due.')
