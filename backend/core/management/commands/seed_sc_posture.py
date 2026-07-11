"""
Manually seed a starting supply-chain posture for a game's teams (UX #8).

The same seeding runs automatically at game start; this command is for reseeding
or backfilling an existing game. See core.services.sc_posture.seed_starting_posture.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models.core import Game, Round
from core.services.sc_posture import seed_starting_posture


class Command(BaseCommand):
    help = 'Seed a starting supply-chain posture for all teams in a game.'

    def add_arguments(self, parser):
        parser.add_argument('--game', type=int, required=True, help='Game id')
        parser.add_argument('--round', type=int, default=None,
                            help='Round number (default: the open round, else round 1)')

    @transaction.atomic
    def handle(self, *args, **opts):
        game = Game.objects.filter(id=opts['game']).first()
        if not game:
            raise CommandError(f"Game {opts['game']} not found.")
        if opts['round']:
            rnd = Round.objects.filter(game=game, round_number=opts['round']).first()
        else:
            rnd = (Round.objects.filter(game=game, status='open').order_by('round_number').first()
                   or Round.objects.filter(game=game, round_number=1).first())
        if not rnd:
            raise CommandError('No target round found (specify --round).')

        n = seed_starting_posture(game, rnd)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded starting SC posture for {n} team(s) in "{game.name}" at round {rnd.round_number}.'))
