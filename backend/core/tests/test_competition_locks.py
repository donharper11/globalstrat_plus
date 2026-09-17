"""Focused PostgreSQL proof for the decision/lifecycle advisory boundary."""
import threading
import time

from django.db import connection, connections, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from core.services.competition_locks import lock_game_for_lifecycle
from core.views.decisions import CompetitionDecisionWriteMixin


class _MutationProbe(CompetitionDecisionWriteMixin, APIView):
    """A route-shaped handler whose call count proves whether it ran."""

    calls = 0
    permission_classes = [permissions.AllowAny]

    def post(self, request, game_id, team_id, round_number):
        type(self).calls += 1
        return Response({'executed': True})


@skipUnlessDBFeature('supports_transactions')
class DecisionLifecycleLockTests(TransactionTestCase):
    """Late writes must not occupy sync workers behind a long resolution."""

    def setUp(self):
        super().setUp()
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL advisory locks are the production boundary')
        _MutationProbe.calls = 0
        self.factory = APIRequestFactory()

    def test_lifecycle_conflict_refuses_mutation_without_waiting_or_executing(self):
        game_id = 987654321
        held = threading.Event()
        release = threading.Event()
        failure = []

        def hold_exclusive_boundary():
            try:
                with transaction.atomic():
                    lock_game_for_lifecycle(game_id)
                    held.set()
                    release.wait(timeout=10)
            except Exception as exc:  # surfaced in the test thread below
                failure.append(exc)
            finally:
                connections.close_all()

        holder = threading.Thread(target=hold_exclusive_boundary, daemon=True)
        holder.start()
        self.assertTrue(held.wait(timeout=5), 'exclusive lifecycle lock not held')
        try:
            request = self.factory.post('/decision-write/', {}, format='json')
            started = time.monotonic()
            response = _MutationProbe.as_view()(
                request, game_id=game_id, team_id=42, round_number=3)
            elapsed = time.monotonic() - started

            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data['code'], 'lifecycle_in_progress')
            # R17: the refusal must carry a message, and the message must
            # describe what actually happened. This boundary fires for EVERY
            # exclusive operator action -- a deadline change, an event
            # injection, a team edit -- not only Phase-1 resolution, so a
            # sentence claiming the round is being processed is false for most
            # of them. Asserted by meaning rather than by exact text: the
            # wording is participant copy and may be retuned, while "names an
            # instructor action, and says nothing was saved" is the ruling.
            detail = response.data['detail']
            self.assertTrue(
                detail.strip(), 'a refused write must tell the student why')
            self.assertIn('instructor', detail.lower(),
                          'the refusal must name the instructor action that '
                          'caused it')
            self.assertIn('nothing was saved', detail.lower(),
                          'a refusal must say the edit was not saved')
            self.assertNotIn('being processed', detail.lower(),
                             'the round is not being processed for a deadline '
                             'change, an event injection or a team edit')
            self.assertEqual(_MutationProbe.calls, 0,
                             'a refused request must not execute its mutation handler')
            self.assertLess(elapsed, 0.5,
                            'the refusal waited behind the lifecycle holder')
        finally:
            release.set()
            holder.join(timeout=10)
        self.assertFalse(holder.is_alive())
        self.assertEqual(failure, [])

        response = _MutationProbe.as_view()(
            self.factory.post('/decision-write/', {}, format='json'),
            game_id=game_id, team_id=42, round_number=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_MutationProbe.calls, 1,
                         'uncontended writes still execute exactly once')
