"""Game ownership is enforced for every game-scoped instructor route.

Three handoffs found the same defect one view at a time: `IsInstructor` checks
the caller's role and nothing else, so any instructor account could read or act
on any cohort by changing the game id in the URL. V2-007's rework fixed one
view, CRV2-07's authorization FAIL fixed another, and CRV2-08's scan found ten
more GETs still open, including the one returning another cohort's submitted
decisions with their payload hashes, actors and request ids.

The repair is a boundary rather than an eleventh view: `GameScopeGuardMiddleware`
refuses by default, and `game_scope` decides which routes it covers by reading
the registered URL patterns. These tests pin the behaviour and the contract
that keeps a new route covered without anyone remembering to add it.
"""
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import OperatorAuditEvent, Round, User
from core.models.course import Course, Section
from core.services.game_scope import EXEMPTIONS, game_scoped_instructor_routes
from core.tests.test_operator_concurrency import build_minimal_game


class GameScopeBoundaryTests(TestCase):

    def setUp(self):
        self.game, _ = build_minimal_game(f'scope-{id(self)}')
        self.other_game, _ = build_minimal_game(f'scope-other-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')

        self.owner = User.objects.create(
            username=f'owner-{id(self)}', role='instructor', password_hash='x')
        self.outsider = User.objects.create(
            username=f'outsider-{id(self)}', role='instructor', password_hash='x')
        self.student = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')

        self.game.section_id = self._own(self.owner, 'OWNED').section_id
        self.game.save(update_fields=['section_id'])
        self.other_game.section_id = self._own(self.outsider, 'OTHER').section_id
        self.other_game.save(update_fields=['section_id'])

        OperatorAuditEvent.objects.create(
            game=self.game, round=self.round, user=self.owner,
            action='close_round', outcome='committed', reason='seed',
            before={'status': 'open'}, after={'status': 'closed'},
            request_id='srv-scope-1')

    def _own(self, user, code):
        course = Course.objects.create(
            course_code=f'{code}{id(self) % 100000}', course_name=code,
            instructor_id=user.user_id, is_active=True)
        return Section.objects.create(
            course_id=course.course_id, section_code='S1', section_name='S1',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)

    def _client(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def _protected_reads(self, game):
        return (f'/api/games/{game.id}/instructor/operator-events/',
                f'/api/games/{game.id}/instructor/dashboard/',
                f'/api/games/{game.id}/instructor/teams/1/decisions/?round=1')

    # -- the boundary ------------------------------------------------------

    def test_the_guard_is_installed(self):
        self.assertIn('core.middleware.GameScopeGuardMiddleware',
                      settings.MIDDLEWARE)

    def test_an_unrelated_instructor_is_refused_every_protected_read(self):
        client = self._client(self.outsider)
        for url in self._protected_reads(self.game):
            response = client.get(url)
            self.assertEqual(response.status_code, 403, url)
            self.assertNotIn('srv-scope-1', str(response.content))

    def test_an_unrelated_instructor_is_refused_a_lifecycle_write(self):
        response = self._client(self.outsider).post(
            f'/api/games/{self.game.id}/round-control/close/',
            {'reason': 'not my cohort'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')

    def test_owning_one_game_grants_no_access_to_another(self):
        # The outsider genuinely owns `other_game`, so this is not "any
        # instructor is refused" -- it is scoped to the game they own.
        client = self._client(self.outsider)
        self.assertEqual(
            client.get(f'/api/games/{self.other_game.id}/instructor/'
                       f'operator-events/').status_code, 200)
        self.assertEqual(
            client.get(f'/api/games/{self.game.id}/instructor/'
                       f'operator-events/').status_code, 403)

    def test_the_owner_reaches_a_normal_outcome(self):
        client = self._client(self.owner)
        self.assertEqual(
            client.get(f'/api/games/{self.game.id}/instructor/'
                       f'operator-events/').status_code, 200)
        # A lifecycle control answers on its own terms, not with 403.
        self.assertNotEqual(
            client.post(f'/api/games/{self.game.id}/round-control/close/',
                        {'reason': 'closing my own round'},
                        format='json').status_code, 403)

    def test_a_student_is_refused(self):
        response = self._client(self.student).get(
            f'/api/games/{self.game.id}/instructor/operator-events/')
        self.assertIn(response.status_code, (401, 403))

    # -- the unowned pilot cohort, pinned on two routes --------------------

    def test_an_unowned_course_is_readable_by_any_instructor_on_two_routes(self):
        """Pinned deliberately, and recorded as V2-033 rather than repaired.

        `instructor_can_access_game` treats a course with no `instructor_id` as
        unowned and visible to any instructor, because the live pilot cohort's
        course row genuinely has NULL there and scoping strictly would hide
        those games from everyone. That is a documented product decision, so it
        is pinned here on more than one route: if it is ever narrowed, both
        assertions fail together and the change is deliberate.
        """
        Course.objects.filter(
            course_id=Section.objects.get(
                section_id=self.game.section_id).course_id
        ).update(instructor_id=None)
        client = self._client(self.outsider)
        self.assertEqual(
            client.get(f'/api/games/{self.game.id}/instructor/'
                       f'operator-events/').status_code, 200)
        self.assertEqual(
            client.get(f'/api/games/{self.game.id}/instructor/'
                       f'dashboard/').status_code, 200)

    # -- the contract that keeps new routes covered ------------------------

    def test_every_game_scoped_instructor_route_is_guarded_or_exempt(self):
        routes = game_scoped_instructor_routes(refresh=True)
        self.assertGreater(len(routes), 20, 'inventory looks empty')
        unjustified = [route for route, meta in routes.items()
                       if meta['exempt'] and not meta['exempt_reason'].strip()]
        self.assertEqual(unjustified, [],
                         'an exemption must carry a reason')
        self.assertEqual(sorted(EXEMPTIONS), sorted(
            r for r, m in routes.items() if m['exempt']))

    def test_the_inventory_includes_the_routes_that_leaked(self):
        # The ten GETs CRV2-08 found open, by route pattern. A repair that
        # dropped one of these out of the inventory would silently reopen it.
        routes = game_scoped_instructor_routes(refresh=True)
        for fragment in ('instructor/teams/<int:team_id>/decisions/',
                         'instructor/dashboard/',
                         'instructor/briefings/',
                         'instructor/team-config/',
                         'instructor/alerts/',
                         'instructor/research-queries/',
                         'instructor/sc-panel/'):
            self.assertTrue(any(fragment in route for route in routes),
                            f'{fragment} is not in the inventory')
