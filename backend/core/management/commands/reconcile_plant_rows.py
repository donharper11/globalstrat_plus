"""Operator recovery for W-CE2-01: a round stuck on colliding plant rows.

A team that queued the same plant build twice in one market stores two
`decision_plant` rows with the same (submission, market, action). That triple
is the hashed `decision_plant` section's natural key, so `prepare_manifest`
refuses the round *before* Phase 1 begins and no engine repair can reach it:
post-round processing answers 500 and the round sits at
`closed / processing_status = FAILED`. No student or instructor screen can
withdraw a queued plant on a closed round, which is why this exists.

This command is the supported alternative to editing the database by hand
(the walkthrough had to do exactly that; `harness/unstick_plant_collision.py`
is the disclosed intervention). It reports what collides, and with `--apply`
removes the *duplicate* rows only -- the first row for each
(submission, market, action) is kept, so the team's decision survives and
only the repetition of it goes. Every removal is recorded as a
`DecisionAuditEvent` against the team and round, so the change is as
answerable as any other correction to a round's inputs.

It does not touch the acquisition-plus-build collision: the engine reconciles
that one itself (`core/engine/plants.record_plant`), so such a round is
un-stuck simply by running post-round processing again.

    python manage.py reconcile_plant_rows --game-id 1
    python manage.py reconcile_plant_rows --game-id 1 --round 2 --apply
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import DecisionAuditEvent, Game, Round
from core.models.decisions import DecisionPlant, DecisionSubmission


class Command(BaseCommand):
    help = ('Report, and with --apply remove, duplicate plant decisions that '
            'stop a round from being processed (W-CE2-01).')

    def add_arguments(self, parser):
        parser.add_argument('--game-id', type=int, required=True)
        parser.add_argument('--round', type=int, dest='round_number',
                            help='Round number; default is the round the game '
                                 'is currently sitting on.')
        parser.add_argument('--apply', action='store_true',
                            help='Remove the duplicates. Without it, nothing '
                                 'is written.')

    def handle(self, *args, **options):
        game = Game.objects.filter(id=options['game_id']).first()
        if not game:
            raise CommandError(f'No game with id {options["game_id"]}.')
        round_number = options['round_number']
        if round_number is None:
            round_number = game.current_round
        round_obj = Round.objects.filter(
            game=game, round_number=round_number).first()
        if not round_obj:
            raise CommandError(
                f'Game "{game.name}" has no round {round_number}.')

        duplicates = []
        for submission in (DecisionSubmission.objects
                           .filter(round=round_obj)
                           .select_related('team')
                           .order_by('team_id')):
            seen = set()
            for row in (DecisionPlant.objects
                        .filter(submission=submission)
                        .select_related('market')
                        .order_by('id')):
                key = (row.market_id, row.action)
                if key in seen:
                    duplicates.append((submission, row))
                seen.add(key)

        if not duplicates:
            self.stdout.write(
                f'Game "{game.name}" round {round_number}: no duplicate plant '
                f'decisions. If processing still fails, the round is not stuck '
                f'on this defect.')
            return

        for submission, row in duplicates:
            self.stdout.write(
                f'{submission.team.name}: duplicate plant decision '
                f'"{row.action}" in {row.market.name} '
                f'(decision_plant id {row.id})')

        if not options['apply']:
            self.stdout.write(
                f'{len(duplicates)} duplicate row(s). Re-run with --apply to '
                f'remove them, then run post-round processing again.')
            return

        with transaction.atomic():
            for submission, row in duplicates:
                DecisionAuditEvent.objects.create(
                    game=game, team=submission.team, round=round_obj,
                    user=None, action='duplicate_plant_decision_removed',
                    endpoint='manage.py:reconcile_plant_rows',
                    payload={'decision_plant_id': row.id,
                             'market': row.market.code,
                             'plant_action': row.action,
                             'finding': 'W-CE2-01'})
                row.delete()

        self.stdout.write(
            f'Removed {len(duplicates)} duplicate plant decision(s) from game '
            f'"{game.name}" round {round_number}. Run post-round processing '
            f'again.')
