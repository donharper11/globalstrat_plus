"""Return failed narrative jobs to the queue, without re-running scoring.

The point of the split: a narrative that gave up is a presentation problem, and
fixing it must never mean resolving the round again. This resets the job rows
and nothing else.
"""
from django.core.management.base import BaseCommand, CommandError

from core.models.narrative_jobs import NarrativeJob


class Command(BaseCommand):
    help = 'Reset failed narrative jobs to pending so a worker retries them.'

    def add_arguments(self, parser):
        parser.add_argument('--game', type=int, dest='game_id')
        parser.add_argument('--round', type=int, dest='round_number')
        parser.add_argument('--type', dest='narrative_type')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        jobs = NarrativeJob.objects.filter(state=NarrativeJob.FAILED)
        if options['game_id']:
            jobs = jobs.filter(game_id=options['game_id'])
        if options['round_number'] is not None:
            jobs = jobs.filter(round__round_number=options['round_number'])
        if options['narrative_type']:
            jobs = jobs.filter(narrative_type=options['narrative_type'])

        jobs = list(jobs.select_related('round'))
        if not jobs:
            self.stdout.write('No failed narrative jobs match.')
            return

        for job in jobs:
            self.stdout.write(
                f'  round {job.round.round_number} {job.narrative_type}: '
                f'{job.attempts} attempt(s), last error: {job.last_error[:120]}')
        if options['dry_run']:
            self.stdout.write(f'[dry-run] would requeue {len(jobs)} job(s).')
            return

        updated = NarrativeJob.objects.filter(
            pk__in=[job.pk for job in jobs]).update(
            state=NarrativeJob.PENDING, attempts=0, last_error='',
            claimed_by='', claimed_at=None, claim_expires_at=None,
            completed_at=None)
        self.stdout.write(self.style.SUCCESS(
            f'Requeued {updated} narrative job(s). Scoring was not re-run.'))
