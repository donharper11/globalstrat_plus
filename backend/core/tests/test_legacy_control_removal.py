"""The legacy simulation-control surface is gone, and the detector that hid it
can no longer certify a route by name collision.

`POST /api/simulation-control/` and the `advance` action on
`SimulationStateViewSet` both drove `core.services.round_engine`, a second
engine that is not `core.engine.advance_round`. Neither checked that the
instructor owned the game it was handed, and the control view's `_reset` issued
unscoped `TRUNCATE`/`UPDATE`/`DELETE` across every instance on the deployment.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

from core.authentication import create_access_token
from core.models import User


class LegacyControlSurfaceIsUnregistered(SimpleTestCase):
    def test_the_legacy_route_names_no_longer_reverse(self):
        for name in ('simulation-control', 'simulation-state-advance'):
            with self.assertRaises(NoReverseMatch, msg=f'{name} still registered'):
                reverse(name)

    def test_the_legacy_paths_no_longer_resolve(self):
        for path in ('/api/simulation-control/',
                     '/api/simulation-state/1/advance/'):
            with self.assertRaises(Resolver404, msg=f'{path} still resolves'):
                resolve(path)

    def test_the_legacy_engine_module_is_gone(self):
        with self.assertRaises(ModuleNotFoundError):
            __import__('core.services.round_engine')

    def test_the_read_only_state_viewset_survives_without_advance(self):
        """Only the action was legacy; the read surface is still served."""
        from core.views.core import SimulationStateViewSet
        self.assertFalse(hasattr(SimulationStateViewSet, 'advance'))
        self.assertTrue(SimulationStateViewSet.queryset.model.__name__,
                        'SimulationState')


class LegacyControlRefusesInstructors(TestCase):
    """An instructor account is exactly who used to be allowed through."""

    def setUp(self):
        self.instructor = User.objects.create(
            username='legacy-removal-instructor', role='instructor',
            password_hash='x',
        )
        DjangoUser.objects.create(
            id=self.instructor.user_id, username='legacy-removal-instructor-auth',
        )
        self.client_ = APIClient()
        self.client_.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.instructor)}')

    def test_simulation_control_is_404_for_every_action(self):
        for action in ('start', 'advance', 'pause', 'resume', 'reset'):
            response = self.client_.post(
                '/api/simulation-control/',
                {'action': action, 'instance_id': 1, 'confirm': True},
                format='json')
            self.assertEqual(response.status_code, 404,
                             f'{action} still reachable')

    def test_legacy_state_advance_is_404(self):
        response = self.client_.post(
            '/api/simulation-state/1/advance/', {}, format='json')
        self.assertEqual(response.status_code, 404)


# --------------------------------------------------------------------------
# The per-round checklist and reminder routes (R48 item 8)
# --------------------------------------------------------------------------

class DeadRoundStatusRoutesAreGone(SimpleTestCase):
    """`rounds/<id>/decision-status/`, `rounds/<id>/send-reminder/` and
    `rounds/current/my-status/` looked a round up by `round_id`, a column the
    model does not have, and answered 500 on every call. No console control
    and no student page called them (the frontend has no caller of any of the
    three paths). Integrator decision under R48: remove them, as R16 removed
    the legacy control surface."""

    def test_the_route_names_no_longer_reverse(self):
        for name, args in (('round-decision-status', [1]),
                           ('round-send-reminder', [1]),
                           ('my-decision-status', [])):
            with self.assertRaises(NoReverseMatch, msg=f'{name} still registered'):
                reverse(name, args=args)

    def test_the_paths_no_longer_resolve(self):
        for path in ('/api/rounds/1/decision-status/',
                     '/api/rounds/1/send-reminder/',
                     '/api/rounds/current/my-status/'):
            with self.assertRaises(Resolver404, msg=f'{path} still resolves'):
                resolve(path)

    def test_the_views_are_gone_with_their_routes(self):
        import core.views
        import core.views.course
        for module in (core.views, core.views.course):
            for name in ('DecisionStatusView', 'SendReminderView'):
                self.assertFalse(hasattr(module, name),
                                 f'{module.__name__}.{name} survives its route')

    def test_the_sentences_only_they_spoke_are_gone_from_the_catalogues(self):
        """A catalogue entry no route can reach is dead wording that the
        string inventory would keep listing as reachable."""
        from core.utils.operator_messages import MESSAGES as OPERATOR
        from core.utils.participant_messages import MESSAGES as PARTICIPANT
        self.assertNotIn('reminder_game_required', OPERATOR)
        for key in ('round_not_found', 'status_item_programs',
                    'status_item_challenges', 'status_item_dilemma',
                    'status_detail_modified', 'status_detail_no_changes',
                    'status_detail_submitted_count', 'status_detail_submitted',
                    'status_detail_pending'):
            self.assertNotIn(key, PARTICIPANT, key)
        # The operator sentence of the same name is still spoken by the
        # instructor's round-results route and stays.
        self.assertIn('round_not_found', OPERATOR)


# --------------------------------------------------------------------------
# The detector that recorded the removed route as guarded
# --------------------------------------------------------------------------

class _ViewGuardedByTheCompetitionEngine(APIView):
    def post(self, request):
        from core.engine.advance_round import advance_round
        advance_round(1)
        return Response({})


class _ViewCallingSomethingElseCalledAdvanceRound(APIView):
    """Shape of the deleted `SimulationControlView._advance`: the marker name,
    bound to a module that does not take the lifecycle lock."""

    def post(self, request):
        from core.services.budget import process_loans as advance_round
        advance_round(1)
        return Response({})


class _ViewThatOnlyMentionsTheMarker(APIView):
    def post(self, request):
        # advance_round( is named here and nowhere else — a comment is not a call.
        return Response({'note': 'operator_action( process_round('})


class BoundaryMarkersResolveToSymbols(SimpleTestCase):
    def test_a_marker_bound_to_the_competition_engine_counts(self):
        from core.services.route_inventory import uses_boundary
        self.assertTrue(uses_boundary(_ViewGuardedByTheCompetitionEngine))

    def test_a_marker_bound_to_another_module_does_not_count(self):
        """The false positive that certified `POST /api/simulation-control/`."""
        from core.services.route_inventory import uses_boundary
        self.assertFalse(
            uses_boundary(_ViewCallingSomethingElseCalledAdvanceRound))

    def test_a_marker_in_a_comment_or_string_does_not_count(self):
        from core.services.route_inventory import uses_boundary
        self.assertFalse(uses_boundary(_ViewThatOnlyMentionsTheMarker))

    def test_the_decision_write_mixin_still_counts_through_the_mro(self):
        from core.services.route_inventory import uses_boundary
        from core.views.decisions import DecisionSubmissionView
        self.assertTrue(uses_boundary(DecisionSubmissionView))

    def test_the_real_operator_routes_are_still_guarded(self):
        """The repair must not turn genuinely guarded routes unguarded."""
        from core.services.route_inventory import uses_boundary
        from core.views.round_control import (
            RoundCloseView, RoundProcessView, RoundAdvanceView)
        from core.views.scenario_views import GameResetView
        for view in (RoundCloseView, RoundProcessView, RoundAdvanceView,
                     GameResetView):
            self.assertTrue(uses_boundary(view), f'{view.__name__} lost its guard')

    def test_no_registered_route_is_unguarded_under_the_repaired_detector(self):
        from core.services.route_inventory import unguarded_routes
        offenders = unguarded_routes()
        self.assertFalse(offenders, 'Unguarded mutating routes:\n' + '\n'.join(
            f'  {e["route"]} {e["view"]}' for e in offenders.values()))
