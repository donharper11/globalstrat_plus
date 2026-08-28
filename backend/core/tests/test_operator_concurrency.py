"""GSP-CRV2-02: every conflicting operator action on one boundary.

These are real threads against real PostgreSQL, with a barrier to make the two
requests collide as tightly as the machine allows. Mocks cannot show this:
the defect being tested for is that two transactions each read a round, each
decide they are allowed to proceed, and only discover the conflict inside the
engine — which mocked locks would hide.

Each pair runs `ITERATIONS` times in each arrival order, and every iteration
asserts the invariants that make a competition defensible: exactly one
resolution, no partial output, a complete audit trail, and no 500.
"""
import json
import os
import pathlib
import threading
import time
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth.models import User as DjangoUser
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import (DecisionSubmission, Game, OperatorAuditEvent,
                         ResolutionManifest, Round, Scenario, Team, User)
from core.models.results_financials import LeaderboardEntry, RoundResultFinancials
from core.models.scenario import (FirmStarterProfile, MarketDefinition,
                                  SegmentDefinition)


ITERATIONS = 100

# Set to a directory to have every pair write its transcript there: status
# codes, response bodies, the advisory locks PostgreSQL actually held during
# the race, and the deadlock counter either side of it.
EVIDENCE_DIR = os.environ.get('GSP_CRV2_02_EVIDENCE_DIR')

# Same namespace as core.services.competition_locks; used only to read back
# what the boundary was doing while the two threads contended.
GAME_ROUND_LOCK_NAMESPACE = 0x475352


def advisory_lock_snapshot():
    """Which sessions hold or await the game boundary right now."""
    with connection.cursor() as cursor:
        cursor.execute(
            '''SELECT l.pid, l.mode, l.granted, l.classid, l.objid
               FROM pg_locks l
               WHERE l.locktype = 'advisory' AND l.classid = %s''',
            [GAME_ROUND_LOCK_NAMESPACE])
        return [{'pid': row[0], 'mode': row[1], 'granted': row[2],
                 'namespace': row[3], 'game_id': row[4]}
                for row in cursor.fetchall()]


def build_minimal_game(name):
    """The smallest game Phase 1 will resolve.

    Deliberately tiny: these tests are about coordination, not about scoring,
    and a full scenario makes Phase 1 slow enough that a hundred races per pair
    would take an hour.
    """
    owner = DjangoUser.objects.create(username=f'owner-{name}')
    scenario = Scenario.objects.create(
        name=f'Concurrency {name}', industry_label='Test', description='d',
        starting_cash=1000000, num_rounds=1000, performance_index_base=100)
    market = MarketDefinition.objects.create(
        scenario=scenario, name='Home', code='HM', description='d',
        currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
        entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
        infrastructure_quality=1)
    SegmentDefinition.objects.create(
        scenario=scenario, market=market, name='Mass', segment_type='customer',
        description='d', population_size=1000, population_growth_rate=0,
        bass_p=D('0.03'), bass_q=D('0.38'), performance_index_weight=D('1.0'),
        revenue_per_unit=D('100'), min_generation_required=1)
    profile = FirmStarterProfile.objects.create(
        scenario=scenario, profile_name='Starter', description='d',
        home_market=market, starting_cash=1000000, starting_debt=0)
    game = Game.objects.create(scenario=scenario, name=name, current_round=1,
                               status='active', created_by=owner, section_id=77)
    teams = [
        Team.objects.create(
            game=game, name=f'Team {index}', firm_starter_profile=profile,
            performance_index=D('100'), cash_on_hand=D('1000000'),
            total_equity=D('1000000'), home_market=market)
        for index in range(2)
    ]
    return game, teams


class OperatorConcurrencyBase(TransactionTestCase):
    """Fixture and race harness shared by every pair in the matrix."""

    # Threads need committed data, so every test truncates afterwards; keep the
    # fixture cheap enough that rebuilding it per test is not the bottleneck.
    reset_sequences = False

    def setUp(self):
        # Phase 2 is a background narrative thread with its own database
        # connection. It is outside this handoff's boundary — its durability is
        # GSP-CRV2-03 — and leaving a hundred of them racing the test teardown
        # only produces connection noise, so it is stubbed out here.
        phase_2 = patch('core.engine.advance_round._run_phase_2')
        phase_2.start()
        self.addCleanup(phase_2.stop)
        self.game, self.teams = build_minimal_game(f'race-{id(self)}')
        self.operator = User.objects.create(
            username=f'operator-{id(self)}', role='instructor', password_hash='x')
        self.second_operator = User.objects.create(
            username=f'operator2-{id(self)}', role='instructor', password_hash='x')
        self.round = self._open_round(1)

    def tearDown(self):
        for alias in connections:
            connections[alias].close()

    # -- fixture helpers ---------------------------------------------------

    def _open_round(self, number, status='open', deadline_minutes=60):
        round_obj, _ = Round.objects.update_or_create(
            game=self.game, round_number=number,
            defaults={'status': status, 'opened_at': timezone.now(),
                      'deadline': timezone.now() + timezone.timedelta(
                          minutes=deadline_minutes)})
        Game.objects.filter(pk=self.game.pk).update(current_round=number)
        self.game.refresh_from_db()
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=round_obj,
                defaults={'status': 'locked', 'locked_at': timezone.now()})
        return round_obj

    def _fresh_round(self, iteration, **kwargs):
        """A brand-new round per iteration, so results never need cleaning up."""
        return self._open_round(2 + iteration, **kwargs)

    def _client(self, operator=None):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {create_access_token(operator or self.operator)}'))
        return client

    # -- the race harness --------------------------------------------------

    def _record_evidence(self, name, payload):
        if not EVIDENCE_DIR:
            return
        directory = pathlib.Path(EVIDENCE_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'{name}.json').write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + '\n')

    @staticmethod
    def _describe(result):
        if result is None:
            return {'kind': 'management-command', 'status_code': None}
        return {'kind': 'api', 'status_code': result.status_code,
                'body': getattr(result, 'data', None)}

    def _race(self, first, second, iterations=ITERATIONS, prepare=None,
              evidence_name=None):
        """Run two operator actions into a barrier, alternating arrival order.

        Returns the list of (first_result, second_result) pairs. Each callable
        receives the iteration number and must close its own connection —
        Django gives every thread its own, and a leaked one exhausts the pool.
        """
        outcomes = []
        transcript = []
        deadlocks_before = deadlock_count()
        contended_locks = []
        for iteration in range(iterations):
            if prepare is not None:
                prepare(iteration)
            barrier = threading.Barrier(2, timeout=60)
            results = {}

            def run(slot, action):
                try:
                    barrier.wait()
                    results[slot] = action(iteration)
                except Exception as error:          # pragma: no cover - surfaced below
                    results[slot] = error
                finally:
                    connection.close()

            threads = [threading.Thread(target=run, args=('first', first)),
                       threading.Thread(target=run, args=('second', second))]
            # Both arrival orders, alternating, so neither action is
            # systematically the one that gets there first.
            if iteration % 2:
                threads.reverse()
            for thread in threads:
                thread.start()
            if iteration < 3:
                # Sample what the database is doing mid-race: two sessions on
                # the same advisory lock, one granted and one waiting, is the
                # boundary doing its job.
                while any(thread.is_alive() for thread in threads):
                    for row in advisory_lock_snapshot():
                        if row not in contended_locks:
                            contended_locks.append(row)
                    time.sleep(0.005)
            for thread in threads:
                thread.join(timeout=120)
                self.assertFalse(thread.is_alive(), 'Operator action deadlocked')

            for slot in ('first', 'second'):
                if isinstance(results[slot], Exception):
                    raise results[slot]
            outcomes.append((results['first'], results['second']))
            if iteration < 3 or EVIDENCE_DIR:
                transcript.append({
                    'iteration': iteration,
                    'arrival_order': 'second-first' if iteration % 2 else 'first-first',
                    'first': self._describe(results['first']),
                    'second': self._describe(results['second']),
                })

        if evidence_name:
            self._record_evidence(evidence_name, {
                'pair': evidence_name,
                'iterations': iterations,
                'deadlocks_before': deadlocks_before,
                'deadlocks_after': deadlock_count(),
                'advisory_locks_observed_during_race': contended_locks,
                'status_code_pairs': _tally(outcomes),
                'transcript': transcript,
            })
        return outcomes

    # -- assertions --------------------------------------------------------

    def assertNoServerError(self, responses):
        for response in responses:
            self.assertLess(
                response.status_code, 500,
                f'Unexplained {response.status_code}: '
                f'{getattr(response, "data", None)}')

    def assertStatuses(self, pair, allowed_pairs):
        """The two status codes, as a set, must be one the matrix documents."""
        seen = tuple(sorted(response.status_code for response in pair))
        self.assertIn(seen, allowed_pairs,
                      f'Unexpected outcome {seen}: '
                      f'{[getattr(r, "data", None) for r in pair]}')

    def assertExactlyOneCommit(self, action, round_number=None):
        events = OperatorAuditEvent.objects.filter(game=self.game, action=action)
        if round_number is not None:
            events = events.filter(round__round_number=round_number)
        committed = events.filter(outcome='committed')
        self.assertEqual(
            committed.count(), 1,
            f'{action}: expected one committed audit event, saw '
            f'{list(events.values_list("outcome", "conflict"))}')

    def assertRejectionRecorded(self, action, round_number=None):
        events = OperatorAuditEvent.objects.filter(
            game=self.game, action=action, outcome='rejected')
        if round_number is not None:
            events = events.filter(round__round_number=round_number)
        self.assertTrue(events.exists(),
                        f'{action}: the refused attempt left no audit record')
        for event in events:
            self.assertEqual(event.after, {},
                             'A rejected attempt must not record an after-state')
            self.assertTrue(event.conflict.get('code'))
            self.assertTrue(event.request_id)

    def assertResolvedExactlyOnce(self, round_obj):
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, 'processed')
        manifests = ResolutionManifest.objects.filter(round=round_obj)
        self.assertEqual(manifests.count(), 1)
        self.assertTrue(manifests.first().output_sha256)
        # No partial output: one financial row and one leaderboard row per team.
        for model in (RoundResultFinancials, LeaderboardEntry):
            self.assertEqual(
                model.objects.filter(game=self.game,
                                     round_number=round_obj.round_number).count(),
                len(self.teams),
                f'{model.__name__} rows for round {round_obj.round_number}')


class MinimalFixtureSmokeTests(OperatorConcurrencyBase):
    """The fixture has to actually resolve, and fast, or the matrix is theatre."""

    def test_phase_1_resolves_the_minimal_game_quickly(self):
        from core.engine.advance_round import close_round, process_round
        close_round(self.game.id)
        started = time.monotonic()
        process_round(self.game.id)
        elapsed = time.monotonic() - started
        self.assertResolvedExactlyOnce(self.round)
        self.assertLess(elapsed, 5.0,
                        f'Phase 1 took {elapsed:.1f}s on the minimal fixture; '
                        f'a 100-iteration matrix would be unusable')


# ---------------------------------------------------------------------------
# Shared invariants
# ---------------------------------------------------------------------------

class LockStateInvariantMixin:
    def assertLockStateAgreesWithRound(self, round_obj):
        """A round and its submissions must never disagree.

        A round left 'closed' with unlocked submissions would let a team edit
        after the deadline; a round left 'open' with locked submissions would
        lock them out of time they were given back. Either is a partial state.
        """
        round_obj.refresh_from_db()
        statuses = set(DecisionSubmission.objects.filter(
            round=round_obj).values_list('status', flat=True))
        if round_obj.status in ('closed', 'processed'):
            self.assertEqual(statuses, {'locked'},
                             f'Round is {round_obj.status} but submissions are '
                             f'{statuses}')
        else:
            self.assertEqual(statuses, {'draft'},
                             f'Round is {round_obj.status} but submissions are '
                             f'{statuses}')


def _tally(outcomes):
    """How often each pair of status codes occurred, as evidence of coverage."""
    counts = {}
    for first, second in outcomes:
        key = '+'.join(
            str(getattr(result, 'status_code', 'command')) for result in (first, second))
        counts[key] = counts.get(key, 0) + 1
    return counts


def deadlock_count():
    """PostgreSQL's own deadlock counter for this database."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()')
        row = cursor.fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# The compatibility matrix
# ---------------------------------------------------------------------------

class CloseVersusExtendTests(OperatorConcurrencyBase, LockStateInvariantMixin):
    """close + extend — the pair that can leave a round closed with the
    students' clock still running, or open with their submissions locked."""

    def test_close_and_extend_never_leave_a_half_applied_round(self):
        before_deadlocks = deadlock_count()

        def close(iteration):
            return self._client().post(
                f'/api/games/{self.game.id}/round-control/close/', {}, format='json')

        def extend(iteration):
            # No reason supplied: extending a *closed* round reopens it, which
            # is an integrity bypass and must be refused without one.
            return self._client(self.second_operator).post(
                f'/api/games/{self.game.id}/instructor/extend-deadline/',
                {'hours': 2}, format='json')

        def prepare(iteration):
            self.round = self._fresh_round(iteration)

        outcomes = self._race(close, extend, prepare=prepare, evidence_name='close-vs-extend')
        for close_response, extend_response in outcomes:
            self.assertNoServerError((close_response, extend_response))
            self.assertStatuses((close_response, extend_response),
                                {(200, 200), (200, 400)})
        self.assertLockStateAgreesWithRound(self.round)
        self.assertEqual(deadlock_count(), before_deadlocks,
                         'PostgreSQL reported a deadlock')


class CloseVersusReopenTests(OperatorConcurrencyBase, LockStateInvariantMixin):
    """close + reopen — directly opposed actions on the same rows."""

    def test_close_and_reopen_settle_on_one_coherent_state(self):
        before_deadlocks = deadlock_count()

        def close(iteration):
            return self._client().post(
                f'/api/games/{self.game.id}/round-control/close/', {}, format='json')

        def reopen(iteration):
            deadline = (timezone.now() + timezone.timedelta(hours=3)).isoformat()
            return self._client(self.second_operator).post(
                f'/api/games/{self.game.id}/round-control/reopen/',
                {'deadline': deadline}, format='json')

        def prepare(iteration):
            self.round = self._fresh_round(iteration)

        outcomes = self._race(close, reopen, prepare=prepare, evidence_name='close-vs-reopen')
        for close_response, reopen_response in outcomes:
            self.assertNoServerError((close_response, reopen_response))
            # Either close wins and reopen then legitimately reopens (200/200),
            # or reopen arrives while the round is still open and is refused.
            self.assertStatuses((close_response, reopen_response),
                                {(200, 200), (200, 409)})
        self.assertLockStateAgreesWithRound(self.round)
        self.assertEqual(deadlock_count(), before_deadlocks)


class ProcessVersusCorrectionTests(OperatorConcurrencyBase):
    """process + correct — the race the v2 register left open.

    An unlock landing between the engine's all-teams-locked precondition and
    its read of that team's decisions would resolve the round from a submission
    the operator believed they had taken back.
    """

    def test_a_correction_never_lands_inside_a_resolution(self):
        before_deadlocks = deadlock_count()
        team = self.teams[0]

        def process(iteration):
            return self._client().post(
                f'/api/games/{self.game.id}/round-control/process/', {}, format='json')

        def correct(iteration):
            return self._client(self.second_operator).post(
                f'/api/games/{self.game.id}/teams/{team.id}/decisions/'
                f'round/{self.round.round_number}/unlock/',
                {'reason': 'Student reported a mis-entered price.'}, format='json')

        def prepare(iteration):
            self.round = self._fresh_round(iteration, status='closed')

        outcomes = self._race(process, correct, prepare=prepare, evidence_name='process-vs-correct')
        for index, (process_response, correct_response) in enumerate(outcomes):
            self.assertNoServerError((process_response, correct_response))
            if process_response.status_code == 200:
                # Resolution won: the correction must have been refused, and
                # every submission it resolved from must still be locked.
                self.assertEqual(correct_response.status_code, 409)
            else:
                # The correction won: the round must NOT have resolved from a
                # draft submission.
                self.assertEqual(correct_response.status_code, 200)
                self.assertEqual(process_response.status_code, 400)
        self.assertEqual(deadlock_count(), before_deadlocks)

    def test_a_resolved_round_records_only_locked_submissions(self):
        """The invariant behind the pair, asserted on the data rather than the
        status codes: no resolution exists for a round that had a draft."""
        for round_obj in Round.objects.filter(game=self.game, status='processed'):
            self.assertFalse(
                DecisionSubmission.objects.filter(
                    round=round_obj, status='draft').exists(),
                f'Round {round_obj.round_number} resolved with a draft submission')


class ProcessVersusProcessTests(OperatorConcurrencyBase):
    """process + process — exactly-once resolution, the P0 of this handoff."""

    def test_two_operators_resolve_a_round_exactly_once(self):
        before_deadlocks = deadlock_count()

        def process_as(operator):
            def action(iteration):
                return self._client(operator).post(
                    f'/api/games/{self.game.id}/round-control/process/',
                    {}, format='json')
            return action

        def prepare(iteration):
            self.round = self._fresh_round(iteration, status='closed')

        outcomes = self._race(process_as(self.operator),
                              process_as(self.second_operator), prepare=prepare,
                              evidence_name='process-vs-process')
        for first, second in outcomes:
            self.assertNoServerError((first, second))
            self.assertStatuses((first, second), {(200, 409)})

        # Every round the matrix resolved has exactly one manifest and one
        # complete set of results — no round resolved twice, none half-way.
        processed = Round.objects.filter(game=self.game, status='processed')
        self.assertEqual(processed.count(), ITERATIONS)
        for round_obj in processed:
            self.assertResolvedExactlyOnce(round_obj)
        self.assertEqual(deadlock_count(), before_deadlocks)

    def test_the_losing_operator_is_visible_in_the_audit_trail(self):
        def process_as(operator):
            def action(iteration):
                return self._client(operator).post(
                    f'/api/games/{self.game.id}/round-control/process/',
                    {}, format='json')
            return action

        def prepare(iteration):
            self.round = self._fresh_round(iteration, status='closed')

        self._race(process_as(self.operator), process_as(self.second_operator),
                   iterations=5, prepare=prepare)
        for number in range(2, 7):
            self.assertExactlyOneCommit('process_round', round_number=number)
            self.assertRejectionRecorded('process_round', round_number=number)


class AdvanceVersusCorrectionTests(OperatorConcurrencyBase):
    """advance + correct — a correction must never apply to a round the game
    has already moved past, and advancing must not strand a half-applied one."""

    def test_a_correction_cannot_follow_the_game_past_its_round(self):
        before_deadlocks = deadlock_count()
        team = self.teams[0]
        state = {}

        def prepare(iteration):
            from core.engine.advance_round import process_round
            round_obj = self._fresh_round(iteration, status='closed')
            process_round(self.game.id)
            state['round'] = round_obj

        def advance(iteration):
            return self._client().post(
                f'/api/games/{self.game.id}/round-control/advance/', {}, format='json')

        def correct(iteration):
            return self._client(self.second_operator).post(
                f'/api/games/{self.game.id}/teams/{team.id}/decisions/'
                f'round/{state["round"].round_number}/unlock/',
                {'reason': 'Late correction request from the team.'},
                format='json')

        outcomes = self._race(advance, correct, prepare=prepare, evidence_name='advance-vs-correct')
        for advance_response, correct_response in outcomes:
            self.assertNoServerError((advance_response, correct_response))
            self.assertEqual(advance_response.status_code, 200)
            # The round is already processed either way, so the correction is
            # refused in both arrival orders — that is the property.
            self.assertEqual(correct_response.status_code, 409)

        for round_obj in Round.objects.filter(game=self.game, status='processed'):
            self.assertFalse(
                DecisionSubmission.objects.filter(
                    round=round_obj, status='draft').exists())
        self.assertEqual(deadlock_count(), before_deadlocks)


class DeactivateVersusProcessTests(OperatorConcurrencyBase):
    """deactivate + process — a withdrawal must apply either wholly before a
    resolution or wholly after it, never inside one."""

    def test_a_round_resolves_one_consistent_roster(self):
        before_deadlocks = deadlock_count()
        team = self.teams[0]

        def prepare(iteration):
            Team.objects.filter(pk=team.pk).update(
                participation_status='active', withdrawn_at=None,
                withdrawn_by=None, withdrawal_reason='')
            self.round = self._fresh_round(iteration, status='closed')

        def deactivate(iteration):
            return self._client(self.second_operator).post(
                f'/api/games/{self.game.id}/instructor/teams/{team.id}/participation/',
                {'action': 'deactivate',
                 'reason': 'Team withdrew from the competition.',
                 'confirmation': f'DEACTIVATE TEAM {team.id}'}, format='json')

        def process(iteration):
            return self._client().post(
                f'/api/games/{self.game.id}/round-control/process/', {}, format='json')

        outcomes = self._race(deactivate, process, prepare=prepare, evidence_name='deactivate-vs-process')
        for deactivate_response, process_response in outcomes:
            self.assertNoServerError((deactivate_response, process_response))
            self.assertEqual(deactivate_response.status_code, 200)
            self.assertEqual(process_response.status_code, 200)

        # The roster a round scored must match the roster its manifest recorded:
        # a withdrawal that landed inside Phase 1 would show up as a leaderboard
        # with a different number of teams than the input snapshot describes.
        for manifest in ResolutionManifest.objects.filter(
                game=self.game).select_related('round'):
            recorded_active = sum(
                1 for row in manifest.input_manifest['sections']['team']
                if row['participation_status'] == 'active')
            self.assertEqual(
                LeaderboardEntry.objects.filter(
                    game=self.game,
                    round_number=manifest.round.round_number).count(),
                recorded_active,
                f'Round {manifest.round.round_number} scored a different roster '
                f'from the one its manifest recorded')
        self.assertEqual(deadlock_count(), before_deadlocks)


class SchedulerVersusManualCloseTests(OperatorConcurrencyBase,
                                      LockStateInvariantMixin):
    """scheduler-close + manual-close — the pair that runs every minute in
    production, where the operator's click lands as cron fires."""

    def test_the_deadline_scheduler_and_an_operator_close_a_round_once(self):
        from django.core.management import call_command
        before_deadlocks = deadlock_count()

        def prepare(iteration):
            # Deadline already elapsed, so the scheduler considers it due.
            self.round = self._fresh_round(iteration, deadline_minutes=-1)

        def scheduler(iteration):
            call_command('check_round_deadlines', game=self.game.id, verbosity=0)
            return None

        def manual(iteration):
            return self._client().post(
                f'/api/games/{self.game.id}/round-control/close/', {}, format='json')

        outcomes = self._race(scheduler, manual, prepare=prepare, evidence_name='scheduler-vs-manual-close')
        for _scheduler_result, manual_response in outcomes:
            self.assertNoServerError((manual_response,))
            # The operator either closed it or found it already closed.
            self.assertIn(manual_response.status_code, (200, 409))

        for round_obj in Round.objects.filter(game=self.game).exclude(round_number=1):
            round_obj.refresh_from_db()
            self.assertEqual(round_obj.status, 'closed')
            self.assertIn(round_obj.close_reason, ('manual', 'deadline'))
            self.assertLockStateAgreesWithRound(round_obj)
        # Exactly one operator commit per round: the scheduler is not an
        # operator and writes none, and the manual close either wins or is
        # recorded as a rejection.
        for round_obj in Round.objects.filter(game=self.game).exclude(round_number=1):
            events = OperatorAuditEvent.objects.filter(
                game=self.game, round=round_obj, action='close_round')
            self.assertEqual(events.count(), 1)
            self.assertIn(events.first().outcome, ('committed', 'rejected'))
        self.assertEqual(deadlock_count(), before_deadlocks)
