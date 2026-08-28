#!/usr/bin/env python3
"""Kill a narrative worker for real, then prove nothing was lost.

The unit tests simulate a dead worker by expiring its lease. This does the
thing itself: it resolves a round, starts a worker in a separate OS process,
SIGKILLs it mid-job — no signal handler, no cleanup, no chance to record
anything — and then starts a fresh worker and checks the round completes.

SIGKILL matters. V2-006 was that "an abrupt process death cannot populate
narrative_error", so a drill that lets the worker tidy up on the way out is not
testing the failure that was reported.

ISOLATED USE ONLY. Point DB_* at a disposable stack.

    cd backend && DB_NAME=globalstrat_replay \
      python3 ../handoff_readiness_v2/narrative_restart_drill.py --game <id>
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time

import django

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from django.utils import timezone                                   # noqa: E402

from core.models import Game, Round                                 # noqa: E402
from core.models.narrative_jobs import NarrativeJob                 # noqa: E402
from core.services import narrative_jobs                            # noqa: E402
from core.services.canonical_json import canonical_sha256           # noqa: E402
from core.services.resolution_manifest import build_output_manifest  # noqa: E402


_STALL_SERVER = """
import sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        time.sleep(600)          # accept, then never answer

    def log_message(self, *a):
        pass


HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
"""


def competitive_hash(round_obj):
    competitive, _narrative = build_output_manifest(round_obj)
    return canonical_sha256(competitive)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=int, required=True, dest='game_id')
    parser.add_argument('--round', type=int, default=None, dest='round_number')
    parser.add_argument('--kill-when-claimed', type=float, default=60.0,
                        help='Seconds to wait for the worker to actually claim '
                             'a job before SIGKILLing it. Killing on a timer '
                             'instead can fire before the worker has claimed '
                             'anything, which tests nothing.')
    parser.add_argument('--stall-port', type=int, default=8794,
                        help='Port for the stalling provider that keeps a job '
                             'claimed long enough to interrupt.')
    parser.add_argument('--lease', type=int, default=8,
                        help='Claim lease. Short, so the drill does not have '
                             'to wait five minutes for a dead claim to expire.')
    parser.add_argument('--out', default=None, help='Write a JSON report here.')
    args = parser.parse_args()

    game = Game.objects.get(pk=args.game_id)
    round_obj = (Round.objects.get(game=game, round_number=args.round_number)
                 if args.round_number is not None
                 else Round.objects.filter(game=game, status='processed')
                 .order_by('-round_number').first())
    if round_obj is None:
        raise SystemExit('No processed round to drill against.')

    report = {'game_id': game.id, 'round_number': round_obj.round_number,
              'started_at': timezone.now().isoformat()}

    # Requeue so there is work to interrupt.
    NarrativeJob.objects.filter(round=round_obj).update(
        state=NarrativeJob.PENDING, attempts=0, last_error='',
        claimed_by='', claimed_at=None, claim_expires_at=None,
        completed_at=None)
    narrative_jobs.enqueue_round(game, round_obj)
    report['hash_before'] = competitive_hash(round_obj)
    report['backlog_before'] = narrative_jobs.backlog(game.id)

    manage = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'backend', 'manage.py')

    # A provider that accepts the connection and never answers. Without it the
    # jobs finish in milliseconds and the kill lands between them, which proves
    # only that an idle worker can be killed safely.
    stall = subprocess.Popen(
        [sys.executable, '-c', _STALL_SERVER, str(args.stall_port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    report['stalling_provider_port'] = args.stall_port

    worker_env = {
        **os.environ,
        'DASHSCOPE_API_KEY': os.environ.get('DASHSCOPE_API_KEY', 'drill-key'),
        'DASHSCOPE_COMPATIBLE_URL':
            f'http://127.0.0.1:{args.stall_port}/v1/chat/completions',
    }
    worker = subprocess.Popen(
        [sys.executable, manage, 'run_narrative_worker', '--loop',
         '--game', str(game.id), '--lease', str(args.lease), '--interval', '1'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=worker_env,
    )
    report['worker_pid'] = worker.pid

    # Wait for the worker to actually have a job in hand, then kill it there.
    deadline = time.monotonic() + args.kill_when_claimed
    claimed = None
    while time.monotonic() < deadline:
        claimed = NarrativeJob.objects.filter(
            round=round_obj, state=NarrativeJob.CLAIMED).first()
        if claimed is not None:
            break
        time.sleep(0.05)
    if claimed is None:
        worker.kill()
        stall.kill()
        raise SystemExit('Worker never claimed a job; nothing to interrupt.')
    report['killed_while_holding'] = {
        'narrative_type': claimed.narrative_type,
        'claimed_by': claimed.claimed_by,
        'claim_expires_at': claimed.claim_expires_at.isoformat(),
    }

    # SIGKILL: the process cannot catch it, so nothing is written on the way
    # out. Whatever it had claimed is now a lease with no owner.
    os.kill(worker.pid, signal.SIGKILL)
    worker.wait(timeout=30)
    stall.kill()
    report['worker_killed'] = True
    report['killed_at'] = timezone.now().isoformat()

    mid = list(NarrativeJob.objects.filter(round=round_obj)
               .order_by('narrative_type')
               .values('narrative_type', 'state', 'attempts', 'claimed_by'))
    report['jobs_after_kill'] = mid
    report['orphaned_claims'] = sum(
        1 for job in mid if job['state'] == NarrativeJob.CLAIMED)
    if not report['orphaned_claims']:
        raise SystemExit(
            'The kill left no orphaned claim, so the drill did not interrupt '
            'work in progress. Re-run; do not report this as a pass.')

    # A dead worker's lease has to expire before another may take it — that is
    # the mechanism, so the drill waits for it rather than forcing it.
    time.sleep(args.lease + 1)

    recovered = subprocess.run(
        [sys.executable, manage, 'run_narrative_worker',
         '--game', str(game.id), '--lease', str(args.lease)],
        capture_output=True, text=True, env={**os.environ}, timeout=600)
    report['recovery_worker_output'] = recovered.stdout[-4000:]
    report['recovery_worker_returncode'] = recovered.returncode

    final = list(NarrativeJob.objects.filter(round=round_obj)
                 .order_by('narrative_type')
                 .values('narrative_type', 'state', 'attempts', 'last_error'))
    report['jobs_after_recovery'] = final
    report['backlog_after'] = narrative_jobs.backlog(game.id)
    report['hash_after'] = competitive_hash(round_obj)
    report['competitive_hash_unchanged'] = (
        report['hash_before'] == report['hash_after'])
    report['all_jobs_terminal'] = all(
        job['state'] in (NarrativeJob.SUCCEEDED, NarrativeJob.FAILED)
        for job in final)
    report['no_job_left_claimed'] = not any(
        job['state'] == NarrativeJob.CLAIMED for job in final)

    rendered = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as stream:
            stream.write(rendered + '\n')
    print(rendered)

    ok = (report['competitive_hash_unchanged'] and report['all_jobs_terminal']
          and report['no_job_left_claimed'])
    print('\nDRILL', 'PASSED' if ok else 'FAILED')
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
