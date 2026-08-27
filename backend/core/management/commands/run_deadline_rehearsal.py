"""Run an isolated, authenticated deadline-write rehearsal against Gunicorn."""
import concurrent.futures
import hashlib
import json
import statistics
import time
import urllib.error
import urllib.request
import uuid

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.engine.advance_round import close_round
from core.models import (DecisionAuditEvent, DecisionSubmission, Enrollment,
                         Game, Round, Scenario, Section, SimulationInstance,
                         Team, User)
from core.models.course import Course


class Command(BaseCommand):
    help = 'Create an evidence game and rehearse concurrent writes at deadline.'

    def add_arguments(self, parser):
        parser.add_argument('--requests', type=int, choices=[96, 288], required=True)
        parser.add_argument('--concurrency', type=int, required=True)
        parser.add_argument('--identities', type=int, default=24)
        parser.add_argument('--base-url', default='http://127.0.0.1:8002/api')
        parser.add_argument('--confirm', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, *args, **opts):
        expected = f'CREATE-REHEARSAL-{opts["requests"]}'
        if opts['confirm'] != expected:
            raise CommandError(f'Confirmation mismatch; expected {expected}.')
        if opts['identities'] < 4 or opts['requests'] % opts['identities']:
            raise CommandError('identities must be >=4 and divide requests evenly.')
        scenario = Scenario.objects.filter(name__icontains='Consumer Electronics').first()
        if not scenario:
            raise CommandError('Consumer Electronics scenario not found.')
        owner = DjangoUser.objects.filter(is_superuser=True).first()
        if not owner:
            raise CommandError('A Django superuser is required to own the evidence game.')

        run_id = uuid.uuid4().hex[:10]
        name = f'REHEARSAL-{opts["requests"]}-{run_id}'
        call_command('initialize_game', scenario=scenario.id,
                     teams=opts['identities'], name=name, verbosity=0)
        game = Game.objects.get(name=name)
        game.current_round = 1
        game.status = 'active'
        game.save(update_fields=['current_round', 'status'])
        round_obj, _ = Round.objects.update_or_create(
            game=game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now() + timezone.timedelta(minutes=5)})

        instructor, _ = User.objects.get_or_create(
            username=f'rehearsal-instructor-{run_id}',
            defaults={'password_hash': 'disabled', 'role': 'instructor'})
        course = Course.objects.create(
            course_code=f'REH-{run_id}', course_name=name,
            instructor_id=instructor.user_id, academic_year='2026',
            semester='Rehearsal', is_active=True, created_at=timezone.now())
        section = Section.objects.create(
            course=course, section_code='LOAD', section_name='Load rehearsal',
            is_active=True, created_at=timezone.now())
        SimulationInstance.objects.create(
            section=section, game_id=game.id, current_round=1,
            total_rounds=scenario.num_rounds, status='active',
            started_at=timezone.now(), created_at=timezone.now())

        actors = []
        password = f'rehearsal-{run_id}'
        for index, team in enumerate(game.teams.order_by('id')):
            username = f'rehearsal-{run_id}-{index:03d}'
            user = User.objects.create(
                username=username, password_hash=hashlib.sha256(password.encode()).hexdigest(),
                role='student', display_name=f'Rehearsal {index + 1}')
            Enrollment.objects.create(
                user_id=user.user_id, section=section, team_id=team.id,
                enrolled_at=timezone.now(), is_active=True)
            login_request = urllib.request.Request(
                f'{opts["base_url"]}/auth/login/', method='POST',
                data=json.dumps({'username': username, 'password': password}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(login_request, timeout=10) as login_response:
                token = json.loads(login_response.read())['access']
            actors.append((team.id, token))

        per_identity = opts['requests'] // len(actors)
        jobs = [(team_id, token, seq) for team_id, token in actors
                for seq in range(per_identity)]
        cutoff = int(len(jobs) * .9)
        fast, delayed = jobs[:cutoff], jobs[cutoff:]

        def write(job, delay=0):
            team_id, token, seq = job
            if delay: time.sleep(delay)
            url = (f'{opts["base_url"]}/games/{game.id}/teams/{team_id}/'
                   f'decisions/round/1/')
            request = urllib.request.Request(
                url, data=b'{}', method='POST',
                headers={'Content-Type': 'application/json',
                         'Authorization': f'Bearer {token}',
                         'X-Request-ID': f'{run_id}-{team_id}-{seq}'})
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    body = response.read().decode(errors='replace')[:300]
            except urllib.error.HTTPError as error:
                status = error.code
                body = error.read().decode(errors='replace')[:300]
            return {'team_id': team_id, 'sequence': seq, 'status': status,
                    'body': body,
                    'ms': round((time.perf_counter() - started) * 1000, 2)}

        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=opts['concurrency']) as pool:
            fast_futures = [pool.submit(write, job) for job in fast]
            # Keep the final cohort pending beyond observed saturated response
            # latency; 750ms was insufficient at the 3x profile and let some
            # nominally-late jobs arrive before the deadline transaction.
            delayed_futures = [pool.submit(write, job, 5.0) for job in delayed]
            while sum(f.done() for f in fast_futures) < len(fast_futures):
                if time.perf_counter() - started > 30:
                    raise CommandError('Fast writes did not finish within 30 seconds.')
                time.sleep(.01)
            close_result = close_round(game.id, reason='deadline')
            results = [f.result() for f in fast_futures + delayed_futures]

        accepted = [r for r in results if r['status'] in (200, 201)]
        rejected = [r for r in results if r['status'] == 403]
        other = [r for r in results if r['status'] not in (200, 201, 403)]
        latencies = sorted(r['ms'] for r in results)
        percentile = lambda p: latencies[min(len(latencies) - 1, int(len(latencies) * p))]
        audit_count = DecisionAuditEvent.objects.filter(
            game=game, round=round_obj, action='save').count()
        locked_count = DecisionSubmission.objects.filter(
            round=round_obj, status='locked').count()
        report = {
            'run_id': run_id, 'game_id': game.id, 'game_name': name,
            'requests': len(results), 'identities': len(actors),
            'concurrency': opts['concurrency'], 'in_flight_at_close': len(delayed),
            'accepted': len(accepted), 'late_rejected': len(rejected),
            'response_samples': list({r['body'] for r in results})[:5],
            'other_statuses': other, 'audit_save_events': audit_count,
            'locked_submissions': locked_count, 'teams': len(actors),
            'close_result': close_result,
            'elapsed_seconds': round(time.perf_counter() - started, 3),
            'latency_ms': {'p50': statistics.median(latencies),
                           'p95': percentile(.95), 'p99': percentile(.99),
                           'max': max(latencies)},
            'invariants': {
                'every_request_accounted_for': len(accepted) + len(rejected) == len(results),
                'accepted_writes_audited': audit_count == len(accepted),
                'every_team_locked': locked_count == len(actors),
                'all_in_flight_uniformly_rejected': len(rejected) == len(delayed),
            },
        }
        with open(opts['output'], 'w', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        if not all(report['invariants'].values()):
            raise CommandError('One or more rehearsal invariants failed.')
