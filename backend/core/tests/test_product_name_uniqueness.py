"""Product names must be unique per team, refused at the write.

Found by GSP-CRV2-07's failure walkthrough. A student could send two product
creates sharing a name, or one reusing the name of a product the team already
owned, and the API answered 200. The round then could not be resolved: the
resolution manifest keys `decision_product_create` on
(submission_id, product_name) and `team_product` on (team_id, name), and
refuses a duplicate inside the resolution transaction. Nothing was corrupted --
the shared transaction rolled the whole resolution back -- but the round stalled
for the entire cohort and the only way out was editing the database by hand.

These tests cover both supported write surfaces, the controls that say the rule
is not wider than it should be, and the manifest boundary that still refuses
invalid rows introduced outside the API.
"""
from decimal import Decimal as D

from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from django.utils import timezone

from core.models import DecisionSubmission, Enrollment, Round, User
from core.models.course import Course, Section
from core.models.decisions import DecisionProductCreate
from core.models.scenario import PlatformGenerationDefinition
from core.models.team_state import TeamPlatform, TeamProduct
from core.tests.test_operator_concurrency import build_minimal_game


class ProductNameUniquenessTests(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'prodname-{id(self)}')
        self.team, self.other_team = self.teams[0], self.teams[1]
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.game.scenario, name='Gen 1', description='d',
            generation_order=1, development_cost=D('1000'),
            license_cost=D('500'), is_starting_platform=True)
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name='P1',
            status='active')
        self.other_platform = TeamPlatform.objects.create(
            team=self.other_team, platform_generation=generation, name='P2',
            status='active')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')
        # Enrollment rather than TeamMember: TeamMember.user_id is a foreign
        # key to auth_user, while Enrollment.user_id is the plain integer the
        # permission actually compares.
        section = Section.objects.create(
            course_id=Course.objects.create(
                course_code=f'PN{id(self) % 100000}', course_name='Names',
                instructor_id=None, is_active=True).course_id,
            section_code='S1', section_name='S1', max_teams=4,
            team_size_min=1, team_size_max=4, is_active=True)
        self.student = self._enrol(f'student-{id(self)}', section, self.team)
        self.other_student = self._enrol(
            f'student2-{id(self)}', section, self.other_team)

    def _enrol(self, username, section, team):
        user = User.objects.create(
            username=username, role='student', password_hash='x')
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=team.id, is_active=True, enrolled_at=timezone.now())
        return user

    # -- helpers ----------------------------------------------------------

    def _client(self, user=None):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {create_access_token(user or self.student)}'))
        return client

    def _create_row(self, name, platform=None):
        return {'team_platform': (platform or self.platform).id,
                'product_name': name, 'positioning': 'mainstream',
                'target_market_ids': [1]}

    def _per_type_url(self, team=None):
        team = team or self.team
        return (f'/api/games/{self.game.id}/teams/{team.id}/decisions/'
                f'round/{self.round.round_number}/products/')

    def _whole_url(self, team=None):
        team = team or self.team
        return (f'/api/games/{self.game.id}/teams/{team.id}/decisions/'
                f'round/{self.round.round_number}/')

    def _names_on_record(self, team=None):
        return sorted(DecisionProductCreate.objects.filter(
            submission__team=team or self.team,
            submission__round=self.round).values_list('product_name', flat=True))

    def _assert_names_rejection(self, response):
        self.assertEqual(response.status_code, 400, response.content[:300])
        self.assertIn('product_name', str(response.content))

    # -- duplicates inside one payload ------------------------------------

    def test_per_type_endpoint_rejects_two_creates_sharing_a_name(self):
        response = self._client().patch(
            self._per_type_url(),
            [self._create_row('Vanguard One'), self._create_row('Vanguard One')],
            format='json')
        self._assert_names_rejection(response)
        self.assertEqual(self._names_on_record(), [])

    def test_whole_submission_endpoint_rejects_the_same_payload(self):
        response = self._client().post(
            self._whole_url(),
            {'product_creates': [self._create_row('Vanguard One'),
                                 self._create_row('Vanguard One')]},
            format='json')
        self._assert_names_rejection(response)
        self.assertEqual(self._names_on_record(), [])

    # -- collision with a product the team already owns --------------------

    def _own_a_product(self, name='Vanguard One'):
        return TeamProduct.objects.create(
            team=self.team, team_platform=self.platform, name=name,
            positioning='mainstream', status='active', created_round=1)

    def test_per_type_endpoint_rejects_the_name_of_an_existing_product(self):
        self._own_a_product()
        response = self._client().patch(
            self._per_type_url(), [self._create_row('Vanguard One')],
            format='json')
        self._assert_names_rejection(response)
        self.assertEqual(self._names_on_record(), [])

    def test_whole_submission_endpoint_rejects_the_name_of_an_existing_product(self):
        self._own_a_product()
        response = self._client().post(
            self._whole_url(),
            {'product_creates': [self._create_row('Vanguard One')]},
            format='json')
        self._assert_names_rejection(response)
        self.assertEqual(self._names_on_record(), [])

    def test_a_retired_product_does_not_free_its_name(self):
        # The manifest key spans the whole table, so retiring does not release
        # the name. Accepting it here would stall the round exactly as before.
        product = self._own_a_product()
        TeamProduct.objects.filter(pk=product.pk).update(
            status='retired', retired_round=1)
        response = self._client().patch(
            self._per_type_url(), [self._create_row('Vanguard One')],
            format='json')
        self._assert_names_rejection(response)

    # -- controls: the rule is no wider than it should be ------------------

    def test_two_distinct_names_are_accepted(self):
        response = self._client().patch(
            self._per_type_url(),
            [self._create_row('Vanguard One'), self._create_row('Vanguard Two')],
            format='json')
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(self._names_on_record(),
                         ['Vanguard One', 'Vanguard Two'])

    def test_another_team_may_use_the_same_name(self):
        self._own_a_product('Vanguard One')
        response = self._client(self.other_student).patch(
            self._per_type_url(self.other_team),
            [self._create_row('Vanguard One', self.other_platform)],
            format='json')
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(self._names_on_record(self.other_team),
                         ['Vanguard One'])

    # -- a rejection leaves the previous decisions alone -------------------

    def test_a_rejected_payload_leaves_the_persisted_set_unchanged(self):
        client = self._client()
        accepted = client.patch(
            self._per_type_url(),
            [self._create_row('Keeper One'), self._create_row('Keeper Two')],
            format='json')
        self.assertEqual(accepted.status_code, 200)

        rejected = client.patch(
            self._per_type_url(),
            [self._create_row('Clash'), self._create_row('Clash')],
            format='json')
        self._assert_names_rejection(rejected)
        self.assertEqual(self._names_on_record(), ['Keeper One', 'Keeper Two'])

    def test_a_corrected_payload_is_accepted_and_the_round_resolves(self):
        client = self._client()
        self._assert_names_rejection(client.patch(
            self._per_type_url(),
            [self._create_row('Vanguard One'), self._create_row('Vanguard One')],
            format='json'))

        corrected = client.patch(
            self._per_type_url(),
            [self._create_row('Vanguard One'), self._create_row('Vanguard Two')],
            format='json')
        self.assertEqual(corrected.status_code, 200, corrected.content[:300])

        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})
        from core.engine.advance_round import process_round
        process_round(self.game.id)
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')
        self.assertEqual(
            sorted(TeamProduct.objects.filter(team=self.team)
                   .values_list('name', flat=True)),
            ['Vanguard One', 'Vanguard Two'])

    # -- defence in depth --------------------------------------------------

    def test_the_manifest_still_refuses_rows_inserted_outside_the_api(self):
        """The write-path check is the fix; the manifest key is the backstop."""
        from core.services.manifest_snapshot import SnapshotError
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=self.round, defaults={'status': 'draft'})
        for _ in range(2):
            DecisionProductCreate.objects.create(
                submission=submission, team_platform=self.platform,
                product_name='Smuggled In', positioning='mainstream',
                target_market_ids=[1])
        DecisionSubmission.objects.filter(pk=submission.pk).update(status='locked')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})

        from core.engine.advance_round import process_round
        from core.models.results_financials import RoundResultFinancials
        with self.assertRaises(SnapshotError):
            process_round(self.game.id)
        self.round.refresh_from_db()
        self.assertNotEqual(self.round.status, 'processed')
        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)
        self.assertEqual(TeamProduct.objects.filter(team=self.team).count(), 0)
