"""Drain the durable narrative queue.

Run it as a supervised long-lived process, or once from cron. Either way it
asks the database what is outstanding rather than trusting anything in memory,
so starting it after a crash resumes the work the crash abandoned:

    python3 manage.py run_narrative_worker --loop --interval 10

Several may run at once. Claims use `SELECT … FOR UPDATE SKIP LOCKED`, so two
workers take different jobs instead of queueing behind the same one, and a
worker that dies leaves a lease that the next one reclaims when it expires.
"""
import signal
import time

from django.core.management.base import BaseCommand

from core.services.narrative_jobs import (
    CLAIM_LEASE_SECONDS, backlog, drain, worker_identity)


class Command(BaseCommand):
    help = 'Claim and run outstanding Phase-2 narrative jobs.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true',
                            help='Keep running instead of draining once.')
        parser.add_argument('--interval', type=float, default=10.0,
                            help='Seconds to sleep when the queue is empty.')
        parser.add_argument('--limit', type=int, default=None,
                            help='Stop after this many jobs.')
        parser.add_argument('--game', type=int, default=None, dest='game_id',
                            help='Restrict to one game.')
        parser.add_argument('--lease', type=int, default=CLAIM_LEASE_SECONDS,
                            help='Seconds a claim is held before it may be '
                                 'reclaimed. Must exceed the LLM timeout.')
        parser.add_argument('--status', action='store_true',
                            help='Report the backlog and exit.')

    def handle(self, *args, **options):
        if options['status']:
            for key, value in backlog(options['game_id']).items():
                self.stdout.write(f'{key:>14}: {value}')
            return

        worker = worker_identity()
        self.stdout.write(f'Narrative worker {worker} starting.')

        # A supervised worker must stop *between* jobs, not inside one: killing
        # it mid-call would otherwise leave a claim to expire rather than a
        # clean handover.
        self._stopping = False

        def _stop(signum, _frame):
            self.stdout.write(f'Signal {signum} received; finishing the '
                              f'current job then stopping.')
            self._stopping = True

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _stop)

        total = 0
        while True:
            processed = drain(limit=options['limit'], worker=worker,
                              game_id=options['game_id'],
                              lease_seconds=options['lease'])
            for job in processed:
                total += 1
                style = (self.style.SUCCESS if job.state == 'succeeded'
                         else self.style.WARNING)
                self.stdout.write(style(
                    f'{job.narrative_type} round {job.round.round_number}: '
                    f'{job.state} (attempt {job.attempts}/{job.max_attempts})'
                    + (f' — {job.last_error}' if job.last_error else '')))
                # Keep the console's view of the round in step as we go.
                from core.engine.advance_round import update_round_narrative_status
                update_round_narrative_status(job.round_id)

            if not options['loop'] or self._stopping:
                break
            if options['limit'] and total >= options['limit']:
                break
            if not processed:
                time.sleep(options['interval'])

        self.stdout.write(f'Narrative worker {worker} stopped after {total} job(s).')
