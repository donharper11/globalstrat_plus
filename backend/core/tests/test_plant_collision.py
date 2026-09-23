"""W-CE2-01: a plant built where an acquisition also brings one stops the game.

The second walkthrough's round 2 could not be processed at all. Aurora
Devices built a plant in AFR and completed the acquisition of *AfriConnect
Mobile*, an AFR target with `includes_plant`. `strategy_effects._process_plants`
created a `TeamPlant` for the build and `acquisitions.process_acquisitions`
created a second one for the target, both with the same
(team, market, construction_started_round); the competition manifest declares
that triple the natural key of the hashed `team_plant` section, so the output
snapshot refused the round with

    SnapshotError: Natural key ('team_id', 'market_id',
    'construction_started_round') is not unique in section "team_plant"

Post-round processing answered 500, the round stayed `closed` with
`processing_status = 'FAILED'`, and no screen could withdraw either decision,
so the game could not advance. The walkthrough went on only after an auditor
deleted the plant decision straight out of the database
(`harness/unstick_plant_collision.py`, disclosed in the record).

Two repairs, because a game that already carries the collision still has to
be finishable:

* **The decision boundary refuses it.** A plant build and an acquisition
  whose target brings a plant in the same market cannot both be queued --
  refused at the save that would create the second one, in the reader's
  language, naming the market, and listed by the lock validator so a draft
  assembled before this change is refused too.
* **The engine reconciles rather than crashes.** Two plants started by one
  team in one market in one round are one plant: the capacities add, the
  earlier completion wins, and an operational plant stays operational. This
  is the only path a stuck game can be resolved by, and it un-sticks a round
  already sitting at `closed / FAILED` -- the operator presses *Run
  post-round processing* again.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.decisions import (DecisionAcquisition,
                                   DecisionBudgetAllocation, DecisionPlant)
from core.models.scenario import AcquisitionTarget, MarketDefinition
from core.models.team_state import TeamMarketPresence, TeamPlant
from core.tests.test_operator_concurrency import build_minimal_game

PLANT_CAPACITY = 5000        # what the market's own plant builds
TARGET_CAPACITY = 3000       # what the acquired target brings
BUILD_ROUNDS = 2


class PlantCollisionBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'pc-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        MarketDefinition.objects.filter(pk=self.home.pk).update(
            allows_manufacturing=True, plant_build_cost=D('0'),
            plant_build_rounds=BUILD_ROUNDS,
            plant_capacity_units=PLANT_CAPACITY)
        self.home.refresh_from_db()
        from core.models.scenario import EntryModeDefinition
        self.mode = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='Export', code='EXPORT',
            description='d', capital_requirement=0, control_level=1,
            risk_level=1, local_presence_score=1)
        for team in self.teams:
            TeamMarketPresence.objects.create(
                team=team, market=self.home, entry_mode=self.mode,
                established_round=0, initial_investment=0, status='active')
        self.target = AcquisitionTarget.objects.create(
            scenario=self.scenario, market=self.home,
            target_name='AfriConnect Mobile', description='d',
            base_acquisition_cost=D('0'), market_share_gained=D('0.05'),
            includes_plant=True, plant_capacity=TARGET_CAPACITY,
            min_round_available=1, integration_rounds=1)
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'closed', 'opened_at': timezone.now(),
                      'deadline': timezone.now()})
        self.submissions = {}
        for team in self.teams:
            submission = DecisionSubmission.objects.create(
                team=team, round=self.round, status='locked')
            DecisionBudgetAllocation.objects.create(
                submission=submission, rd_budget=D('0'),
                marketing_budget=D('0'), strategy_budget=D('0'),
                research_budget=D('0'))
            self.submissions[team.id] = submission

    # -- fixture helpers ---------------------------------------------------

    def queue_build(self, team=None, market=None):
        return DecisionPlant.objects.create(
            submission=self.submissions[(team or self.team).id],
            market=market or self.home, action='build',
            capacity_units=0, contract_mfg_volume=0)

    def queue_acquisition(self, team=None):
        return DecisionAcquisition.objects.create(
            submission=self.submissions[(team or self.team).id],
            acquisition_target=self.target)

    def resolve(self):
        from core.engine.advance_round import process_round
        return process_round(self.game.id)

    def plants(self, team=None):
        return list(TeamPlant.objects.filter(
            team=team or self.team).order_by('id'))


class RoundAlwaysProcessesTests(PlantCollisionBase):
    """The P0: the round has to resolve, and the two rows have to be one."""

    def test_a_build_beside_an_acquired_plant_does_not_stop_the_round(self):
        self.queue_build()
        self.queue_acquisition()

        self.resolve()

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')
        self.assertNotEqual(self.round.processing_status, 'FAILED')

    def test_the_two_plants_are_one_row_carrying_both_capacities(self):
        self.queue_build()
        self.queue_acquisition()

        self.resolve()

        rows = self.plants()
        self.assertEqual(len(rows), 1, f'expected one plant row, got {rows}')
        plant = rows[0]
        self.assertEqual(plant.market_id, self.home.id)
        self.assertEqual(plant.construction_started_round, 1)
        # Both capacities: the team paid for the build and bought the target.
        self.assertEqual(plant.capacity_units,
                         PLANT_CAPACITY + TARGET_CAPACITY)
        # The acquired plant runs from the round it is bought, so the
        # reconciled row is operational and completes this round.
        self.assertEqual(plant.status, 'operational')
        self.assertEqual(plant.completion_round, 1)

    def test_two_build_rows_in_one_market_are_one_plant(self):
        """The same collision without an acquisition: two appended builds.

        Driven through the engine step rather than `process_round`, because
        two `decision_plant` rows with the same (submission, market, action)
        break the *input* snapshot before Phase 1 runs at all -- a second,
        independent game-stopper on the same screen, refused at the save now
        and cleared for an existing game by `manage.py reconcile_plant_rows`.
        """
        from core.engine.strategy_effects import _process_plants
        self.queue_build()
        self.queue_build()

        _process_plants(self.team, self.submissions[self.team.id], 1)

        rows = self.plants()
        self.assertEqual(len(rows), 1, f'expected one plant row, got {rows}')
        self.assertEqual(rows[0].capacity_units, PLANT_CAPACITY * 2)
        self.assertEqual(rows[0].status, 'under_construction')
        self.assertEqual(rows[0].completion_round, 1 + BUILD_ROUNDS)

    def test_a_build_alone_is_unchanged(self):
        self.queue_build()

        self.resolve()

        rows = self.plants()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].capacity_units, PLANT_CAPACITY)
        self.assertEqual(rows[0].status, 'under_construction')
        self.assertEqual(rows[0].completion_round, 1 + BUILD_ROUNDS)

    def test_an_acquired_plant_alone_is_unchanged(self):
        self.queue_acquisition()

        self.resolve()

        rows = self.plants()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].capacity_units, TARGET_CAPACITY)
        self.assertEqual(rows[0].status, 'operational')

    def test_a_plant_from_an_earlier_round_is_a_separate_row(self):
        """The natural key is per start round: last round's plant is not merged."""
        TeamPlant.objects.create(
            team=self.team, market=self.home, status='operational',
            capacity_units=PLANT_CAPACITY, construction_started_round=0,
            completion_round=0)
        self.queue_build()

        self.resolve()

        self.assertEqual(len(self.plants()), 2)


class StuckRoundRecoveryTests(PlantCollisionBase):
    """A round already sitting at `closed / FAILED` must be finishable."""

    def test_a_failed_round_processes_on_the_next_attempt(self):
        self.queue_build()
        self.queue_acquisition()
        # Exactly the state the walkthrough was left in.
        Round.objects.filter(pk=self.round.pk).update(
            status='closed', processing_status='FAILED')

        self.resolve()

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')
        self.assertEqual(len(self.plants()), 1)


class DecisionBoundaryTests(PlantCollisionBase):
    """The collision cannot be created through the routes a student uses."""

    def setUp(self):
        super().setUp()
        Round.objects.filter(pk=self.round.pk).update(
            status='open', decisions_locked=False,
            deadline=timezone.now() + timezone.timedelta(hours=4))
        self.round.refresh_from_db()
        DecisionSubmission.objects.filter(
            round=self.round).update(status='draft')
        self.client = self.client_for(self.team)

    def client_for(self, team, language='en'):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'pc-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'PC{id(self) % 10000}{Course.objects.count()}',
            course_name='PC', instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=team.id, is_active=True, enrolled_at=timezone.now())
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}',
            HTTP_ACCEPT_LANGUAGE=language)
        return client

    def url(self, section):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}/'
                f'decisions/round/{self.round.round_number}/{section}/')

    def save_plants(self, rows, client=None):
        return (client or self.client).patch(
            self.url('plants'), {'plant_decisions': rows}, format='json')

    def save_acquisitions(self, rows, client=None):
        return (client or self.client).patch(
            self.url('acquisitions'), {'acquisitions': rows}, format='json')

    def build_row(self):
        return {'market': self.home.id, 'action': 'build',
                'capacity_units': 0, 'contract_mfg_volume': 0}

    # -- the two orders the two pages can be used in ----------------------

    def test_a_build_is_refused_when_the_acquisition_already_brings_one(self):
        self.assertEqual(
            self.save_acquisitions(
                [{'acquisition_target': self.target.id}]).status_code, 200)

        response = self.save_plants([self.build_row()])

        self.assertEqual(response.status_code, 400)
        sentence = str(response.data)
        self.assertIn('AfriConnect Mobile', sentence)
        self.assertIn(self.home.name, sentence)
        self.assertEqual(DecisionPlant.objects.filter(
            submission=self.submissions[self.team.id]).count(), 0)

    def test_the_acquisition_is_refused_when_a_build_is_already_queued(self):
        self.assertEqual(self.save_plants([self.build_row()]).status_code, 200)

        response = self.save_acquisitions(
            [{'acquisition_target': self.target.id}])

        self.assertEqual(response.status_code, 400)
        self.assertIn(self.home.name, str(response.data))
        # The refused save leaves the team's decisions as they were.
        self.assertEqual(DecisionAcquisition.objects.filter(
            submission=self.submissions[self.team.id]).count(), 0)
        self.assertEqual(DecisionPlant.objects.filter(
            submission=self.submissions[self.team.id]).count(), 1)

    def test_the_same_market_cannot_be_built_in_twice(self):
        response = self.save_plants([self.build_row(), self.build_row()])

        self.assertEqual(response.status_code, 400)
        self.assertIn(self.home.name, str(response.data))
        self.assertEqual(DecisionPlant.objects.filter(
            submission=self.submissions[self.team.id]).count(), 0)

    def test_the_refusal_is_in_the_readers_language(self):
        zh = self.client_for(self.team, language='zh-CN')
        self.assertEqual(
            self.save_acquisitions(
                [{'acquisition_target': self.target.id}], client=zh
            ).status_code, 200)

        response = self.save_plants([self.build_row()], client=zh)

        self.assertEqual(response.status_code, 400)
        sentence = str(response.data)
        self.assertIn('收购', sentence)
        self.assertIn('撤回', sentence)

    def test_a_build_on_its_own_is_still_accepted(self):
        self.assertEqual(self.save_plants([self.build_row()]).status_code, 200)
        self.assertEqual(DecisionPlant.objects.filter(
            submission=self.submissions[self.team.id]).count(), 1)

    def test_a_target_a_rival_already_owns_does_not_block_a_build(self):
        from core.models.team_state import TeamAcquisition
        TeamAcquisition.objects.create(
            team=self.rival, acquisition_target=self.target, acquired_round=1,
            integration_complete=True, integration_rounds_remaining=0,
            total_cost_paid=D('0'))
        self.queue_acquisition()

        self.assertEqual(self.save_plants([self.build_row()]).status_code, 200)

    def test_the_lock_refuses_a_draft_that_already_carries_both(self):
        """A draft assembled before this rule existed still cannot be locked."""
        from core.views.decisions import lock_blockers_for
        self.queue_build()
        self.queue_acquisition()

        blockers = lock_blockers_for(
            self.submissions[self.team.id], language='en')

        self.assertTrue(any('AfriConnect Mobile' in b for b in blockers),
                        blockers)


class ReconcileCommandTests(PlantCollisionBase):
    """The operator path for a round already stuck on duplicate decisions."""

    def run_command(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('reconcile_plant_rows', '--game-id', str(self.game.id),
                     '--round', '1', *args, stdout=out)
        return out.getvalue()

    def test_a_duplicate_decision_stops_the_round_before_phase_one(self):
        from core.services.manifest_snapshot import SnapshotError
        self.queue_build()
        self.queue_build()

        with self.assertRaises(SnapshotError) as caught:
            self.resolve()

        self.assertIn('decision_plant', str(caught.exception))
        self.round.refresh_from_db()
        self.assertEqual(self.round.processing_status, 'FAILED')

    def test_the_command_reports_without_writing(self):
        self.queue_build()
        self.queue_build()

        output = self.run_command()

        self.assertIn('duplicate plant decision', output)
        self.assertEqual(DecisionPlant.objects.count(), 2)

    def test_apply_removes_the_duplicate_and_the_round_processes(self):
        self.queue_build()
        self.queue_build()

        self.run_command('--apply')

        self.assertEqual(DecisionPlant.objects.count(), 1)
        from core.models import DecisionAuditEvent
        self.assertTrue(DecisionAuditEvent.objects.filter(
            action='duplicate_plant_decision_removed').exists())

        self.resolve()
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')

    def test_a_clean_round_is_reported_as_clean(self):
        self.queue_build()

        output = self.run_command()

        self.assertIn('no duplicate plant decisions', output)
