"""
Tests for the 2026-07-15 auth + round-lifecycle work.

Covers the five reported defects:
  1. students could log in with no password
  2. no way for an instructor to set/reset a student password
  3. no visibility of who is logged in
  4. round deadlines were recorded but never enforced
  5. pause set a flag that nothing read

Plus the deeper hole found while fixing (1): an unsigned X-User-Id header /
?user_id= param was accepted as proof of identity on every endpoint.
"""
from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User, Game, Round, Team
from core.models.auth_models import UserSession
from core.models.course import Course, Section, Enrollment
from core.models.scenario import Scenario, MarketDefinition
from core.utils.passwords import (
    hash_password, verify_password, is_legacy_hash, default_password_for,
)
import hashlib


def _legacy_sha256(plain):
    return hashlib.sha256(plain.encode()).hexdigest()


class PasswordUtilTests(TestCase):
    """core.utils.passwords — hashing, legacy fallback, upgrade."""

    def test_new_hashes_are_pbkdf2_not_sha256(self):
        h = hash_password('hunter2')
        self.assertTrue(h.startswith('pbkdf2_'))
        self.assertFalse(is_legacy_hash(h))

    def test_pbkdf2_roundtrip(self):
        h = hash_password('hunter2')
        ok, upgrade = verify_password('hunter2', h)
        self.assertTrue(ok)
        self.assertFalse(upgrade)

    def test_pbkdf2_rejects_wrong_password(self):
        h = hash_password('hunter2')
        ok, _ = verify_password('wrong', h)
        self.assertFalse(ok)

    def test_legacy_sha256_still_verifies_and_flags_upgrade(self):
        """Existing instructor hashes must not be locked out."""
        h = _legacy_sha256('oldpass')
        ok, upgrade = verify_password('oldpass', h)
        self.assertTrue(ok)
        self.assertTrue(upgrade)

    def test_legacy_sha256_rejects_wrong_password(self):
        h = _legacy_sha256('oldpass')
        ok, _ = verify_password('nope', h)
        self.assertFalse(ok)

    def test_blank_hash_never_verifies(self):
        """An account with no password set must not be loginable."""
        for candidate in ('', 'anything', None):
            ok, _ = verify_password(candidate, '')
            self.assertFalse(ok)

    def test_blank_password_never_verifies(self):
        ok, _ = verify_password('', hash_password('x'))
        self.assertFalse(ok)

    def test_default_password_prefers_student_id(self):
        u = User(username='alice', student_id='S123')
        self.assertEqual(default_password_for(u), 'S123')

    def test_default_password_falls_back_to_username(self):
        u = User(username='alice', student_id='')
        self.assertEqual(default_password_for(u), 'alice')


class _BaseFixture(TestCase):
    """A game with one team, one enrolled student, and an instructor."""

    def setUp(self):
        self.client = APIClient()

        self.django_user = DjangoUser.objects.create(username='owner')
        self.scenario = Scenario.objects.create(
            name='S', industry_label='Test', description='d',
            starting_cash=1000, num_rounds=3,
        )
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1,
        )
        self.game = Game.objects.create(
            scenario=self.scenario, name='G', status='active',
            current_round=1, created_by=self.django_user,
        )
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now(),
        )

        self.instructor = User.objects.create(
            username='prof', role='instructor',
            password_hash=hash_password('profpass'),
        )
        self.course = Course.objects.create(
            course_code='C1', course_name='Course',
            instructor_id=self.instructor.user_id, is_active=True,
        )
        self.section = Section.objects.create(
            course=self.course, section_code='S1', is_active=True,
        )
        self.game.section_id = self.section.section_id
        self.game.save()

        self.student = User.objects.create(
            username='2330024103', student_id='2330024103',
            display_name='Student One', role='Student', password_hash='',
        )

    def _make_team(self):
        from core.models.scenario import FirmStarterProfile
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='P', description='d',
            home_market=self.market,
        )
        return Team.objects.create(
            game=self.game, name='T1', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000,
            home_market=self.market,
        )

    def _enroll(self, team=None):
        return Enrollment.objects.create(
            user_id=self.student.user_id, section=self.section,
            team_id=team.id if team else None, is_active=True,
        )

    def _auth(self, user):
        from core.authentication import create_access_token
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')


class LoginPasswordTests(_BaseFixture):
    """Defect 1: students could log in without a password."""

    def setUp(self):
        super().setUp()
        self.team = self._make_team()
        self._enroll(self.team)
        self.url = reverse('auth-login')

    def test_student_cannot_log_in_without_password(self):
        """The original bug: username alone was enough."""
        r = self.client.post(self.url, {'username': '2330024103'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('access', r.data)

    def test_student_with_no_password_set_is_refused(self):
        """Blank password_hash must not mean 'anything works'."""
        r = self.client.post(
            self.url, {'username': '2330024103', 'password': 'guess'},
            format='json')
        self.assertEqual(r.status_code, 403)
        self.assertNotIn('access', r.data)

    def test_student_logs_in_with_default_student_id_password(self):
        self.student.password_hash = hash_password('2330024103')
        self.student.save()
        r = self.client.post(
            self.url, {'username': '2330024103', 'password': '2330024103'},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)

    def test_student_rejected_with_wrong_password(self):
        self.student.password_hash = hash_password('2330024103')
        self.student.save()
        r = self.client.post(
            self.url, {'username': '2330024103', 'password': 'wrong'},
            format='json')
        self.assertEqual(r.status_code, 401)
        self.assertNotIn('access', r.data)

    def test_login_does_not_leak_whether_a_username_exists(self):
        """Same status and message for unknown user and wrong password."""
        self.student.password_hash = hash_password('pw')
        self.student.save()
        unknown = self.client.post(
            self.url, {'username': 'nobody', 'password': 'x'}, format='json')
        wrong = self.client.post(
            self.url, {'username': '2330024103', 'password': 'x'}, format='json')
        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(str(unknown.data['error']), str(wrong.data['error']))

    def test_legacy_instructor_hash_logs_in_and_is_upgraded(self):
        self.instructor.password_hash = _legacy_sha256('legacy1')
        self.instructor.save()
        r = self.client.post(
            self.url, {'username': 'prof', 'password': 'legacy1'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.instructor.refresh_from_db()
        self.assertTrue(self.instructor.password_hash.startswith('pbkdf2_'))

    def test_login_creates_a_session_row(self):
        self.student.password_hash = hash_password('2330024103')
        self.student.save()
        r = self.client.post(
            self.url, {'username': '2330024103', 'password': '2330024103'},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('session_id', r.data)
        self.assertTrue(
            UserSession.objects.filter(user_id=self.student.user_id).exists())


class ImpersonationTests(_BaseFixture):
    """The deeper hole: unsigned X-User-Id / ?user_id= was trusted as identity."""

    def test_x_user_id_header_no_longer_grants_instructor_access(self):
        url = reverse('instructor-student-accounts')
        r = self.client.get(url, HTTP_X_USER_ID=str(self.instructor.user_id))
        self.assertIn(r.status_code, (401, 403))

    def test_user_id_query_param_no_longer_grants_instructor_access(self):
        url = reverse('instructor-student-accounts')
        r = self.client.get(url, {'user_id': self.instructor.user_id})
        self.assertIn(r.status_code, (401, 403))

    def test_auth_me_requires_a_token(self):
        r = self.client.get(reverse('auth-me'), {'user_id': self.instructor.user_id})
        self.assertIn(r.status_code, (401, 403))

    def test_auth_me_describes_the_caller_not_the_requested_user_id(self):
        """Passing someone else's user_id must not return their profile."""
        self._auth(self.student)
        r = self.client.get(reverse('auth-me'),
                            {'user_id': self.instructor.user_id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['user_id'], self.student.user_id)

    def test_jwt_still_grants_instructor_access(self):
        self._auth(self.instructor)
        r = self.client.get(reverse('instructor-student-accounts'))
        self.assertEqual(r.status_code, 200)


class PasswordManagementTests(_BaseFixture):
    """Defect 2: instructor can set/reset student passwords."""

    def setUp(self):
        super().setUp()
        self._enroll()
        self._auth(self.instructor)

    def test_reset_to_default_sets_student_id_and_enables_login(self):
        url = reverse('instructor-student-password',
                      args=[self.student.user_id])
        r = self.client.post(url, {'reset_to_default': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['password'], '2330024103')

        self.client.credentials()
        login = self.client.post(
            reverse('auth-login'),
            {'username': '2330024103', 'password': '2330024103'}, format='json')
        # 403 = password is right but no team yet; the password itself worked.
        self.assertNotEqual(login.status_code, 401)

    def test_set_explicit_password(self):
        url = reverse('instructor-student-password', args=[self.student.user_id])
        r = self.client.post(url, {'password': 'newpass123'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.student.refresh_from_db()
        ok, _ = verify_password('newpass123', self.student.password_hash)
        self.assertTrue(ok)

    def test_short_password_rejected(self):
        url = reverse('instructor-student-password', args=[self.student.user_id])
        r = self.client.post(url, {'password': 'ab'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_student_cannot_reset_anyones_password(self):
        self._auth(self.student)
        url = reverse('instructor-student-password', args=[self.student.user_id])
        r = self.client.post(url, {'password': 'newpass123'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_instructor_cannot_reset_a_student_in_another_course(self):
        other = User.objects.create(
            username='other', student_id='S999', role='Student',
            password_hash='')
        url = reverse('instructor-student-password', args=[other.user_id])
        r = self.client.post(url, {'reset_to_default': True}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_bulk_reset_only_missing(self):
        url = reverse('instructor-bulk-password-reset')
        r = self.client.post(url, {'only_missing': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['updated_count'], 1)
        self.student.refresh_from_db()
        self.assertTrue(self.student.password_hash.startswith('pbkdf2_'))

    def test_account_list_reports_password_status(self):
        r = self.client.get(reverse('instructor-student-accounts'))
        self.assertEqual(r.status_code, 200)
        row = next(s for s in r.data['students']
                   if s['user_id'] == self.student.user_id)
        self.assertFalse(row['has_password'])
        self.assertTrue(row['needs_password'])
        self.assertEqual(row['default_password'], '2330024103')


class SessionVisibilityTests(_BaseFixture):
    """Defect 3: who is logged in, and for how long."""

    def setUp(self):
        super().setUp()
        self._enroll()

    def test_active_sessions_lists_a_logged_in_student(self):
        UserSession.objects.create(
            user_id=self.student.user_id, username=self.student.username,
            role='Student', game_id=self.game.id,
        )
        self._auth(self.instructor)
        r = self.client.get(reverse('instructor-active-sessions'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['active_count'], 1)
        self.assertEqual(r.data['active'][0]['username'], '2330024103')

    def test_duration_minutes_reflects_time_since_login(self):
        now = timezone.now()
        s = UserSession.objects.create(
            user_id=self.student.user_id, username='u',
            login_at=now - timezone.timedelta(minutes=42), last_seen_at=now,
        )
        self.assertEqual(s.duration_minutes, 42)

    def test_idle_session_drops_off_the_active_list(self):
        old = timezone.now() - timezone.timedelta(
            minutes=UserSession.IDLE_TIMEOUT_MINUTES + 5)
        UserSession.objects.create(
            user_id=self.student.user_id, username='u',
            login_at=old, last_seen_at=old,
        )
        self.assertEqual(UserSession.active_qs().count(), 0)

    def test_logout_ends_the_session(self):
        s = UserSession.objects.create(
            user_id=self.student.user_id, username='u')
        self._auth(self.student)
        r = self.client.post(reverse('auth-logout'),
                             {'session_id': s.id}, format='json')
        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.assertIsNotNone(s.logout_at)
        self.assertFalse(s.is_active)

    def test_students_cannot_see_the_session_list(self):
        self._auth(self.student)
        r = self.client.get(reverse('instructor-active-sessions'))
        self.assertEqual(r.status_code, 403)


class DeadlineEnforcementTests(_BaseFixture):
    """Defect 4: deadlines were recorded but never enforced."""

    def setUp(self):
        super().setUp()
        self.team = self._make_team()
        self._enroll(self.team)
        self.submit_url = reverse(
            'decision-submission',
            args=[self.game.id, self.team.id, 1],
        ) if self._has_route() else None

    def _has_route(self):
        try:
            reverse('decision-submission', args=[1, 1, 1])
            return True
        except Exception:
            return False

    def test_command_runs_without_crashing(self):
        """It used to raise FieldError on Round.decisions_locked."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('check_round_deadlines', stdout=out)
        self.assertIn('no rounds due', out.getvalue())

    def test_past_deadline_closes_the_round(self):
        from django.core.management import call_command
        from io import StringIO
        self.round.deadline = timezone.now() - timezone.timedelta(minutes=1)
        self.round.save()

        call_command('check_round_deadlines', stdout=StringIO())

        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'closed')
        self.assertEqual(self.round.close_reason, 'deadline')
        self.assertIsNotNone(self.round.closed_at)

    def test_future_deadline_leaves_the_round_open(self):
        from django.core.management import call_command
        from io import StringIO
        self.round.deadline = timezone.now() + timezone.timedelta(hours=1)
        self.round.save()
        call_command('check_round_deadlines', stdout=StringIO())
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')

    def test_closing_locks_every_team_submission(self):
        from core.engine.advance_round import close_round
        from core.models.decisions import DecisionSubmission
        close_round(self.game.id, reason='deadline')
        sub = DecisionSubmission.objects.get(team=self.team, round=self.round)
        self.assertEqual(sub.status, 'locked')

    def test_paused_game_deadline_does_not_run_down(self):
        """A paused game must not burn the students' remaining time."""
        from django.core.management import call_command
        from io import StringIO
        self.game.status = 'paused'
        self.game.save()
        self.round.deadline = timezone.now() - timezone.timedelta(minutes=1)
        self.round.save()
        call_command('check_round_deadlines', stdout=StringIO())
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')

    def test_dry_run_changes_nothing(self):
        from django.core.management import call_command
        from io import StringIO
        self.round.deadline = timezone.now() - timezone.timedelta(minutes=1)
        self.round.save()
        call_command('check_round_deadlines', '--dry-run', stdout=StringIO())
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')

    def test_close_is_idempotent(self):
        from core.engine.advance_round import close_round
        first = close_round(self.game.id, reason='deadline')
        second = close_round(self.game.id, reason='deadline')
        self.assertTrue(first['changed'])
        self.assertFalse(second['changed'])


class RoundLifecycleTests(_BaseFixture):
    """Defect 4b: process and advance are separate, ordered steps."""

    def setUp(self):
        super().setUp()
        self.team = self._make_team()
        self._auth(self.instructor)

    def test_control_endpoint_reports_next_action(self):
        r = self.client.get(reverse('round-control', args=[self.game.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['round']['status'], 'open')
        self.assertEqual(r.data['round']['next_action'], 'await_deadline')

    def test_manual_close_then_next_action_is_process(self):
        r = self.client.post(reverse('round-control-close', args=[self.game.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['round']['status'], 'closed')
        self.assertEqual(r.data['round']['next_action'], 'process')
        self.round.refresh_from_db()
        self.assertEqual(self.round.close_reason, 'manual')

    def test_cannot_advance_before_processing(self):
        from core.engine.advance_round import close_round
        close_round(self.game.id)
        r = self.client.post(reverse('round-control-advance', args=[self.game.id]),
                             {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('processed', str(r.data['error']).lower())
        self.game.refresh_from_db()
        self.assertEqual(self.game.current_round, 1)

    def test_cannot_process_an_open_round_without_force(self):
        r = self.client.post(reverse('round-control-process', args=[self.game.id]),
                             {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_advance_after_processing_opens_next_round(self):
        """The processed round stays put until advance is called."""
        self.round.status = 'processed'
        self.round.processed_at = timezone.now()
        self.round.save()

        r = self.client.post(reverse('round-control-advance', args=[self.game.id]),
                             {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['next_round'], 2)

        self.game.refresh_from_db()
        self.assertEqual(self.game.current_round, 2)
        nxt = Round.objects.get(game=self.game, round_number=2)
        self.assertEqual(nxt.status, 'open')

    def test_advance_past_final_round_completes_the_game(self):
        self.game.current_round = 3
        self.game.save()
        Round.objects.create(game=self.game, round_number=3, status='processed')
        r = self.client.post(reverse('round-control-advance', args=[self.game.id]),
                             {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['next_round'])
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, 'completed')

    def test_reopen_requires_a_future_deadline(self):
        self.round.deadline = timezone.now() - timezone.timedelta(minutes=5)
        self.round.status = 'closed'
        self.round.save()
        r = self.client.post(reverse('round-control-reopen', args=[self.game.id]),
                             {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_reopen_with_new_deadline_unlocks_submissions(self):
        from core.engine.advance_round import close_round
        from core.models.decisions import DecisionSubmission
        close_round(self.game.id)
        new_deadline = (timezone.now() + timezone.timedelta(hours=2)).isoformat()
        r = self.client.post(reverse('round-control-reopen', args=[self.game.id]),
                             {'deadline': new_deadline}, format='json')
        self.assertEqual(r.status_code, 200)
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')
        sub = DecisionSubmission.objects.get(team=self.team, round=self.round)
        self.assertEqual(sub.status, 'draft')

    def test_cannot_reopen_a_processed_round(self):
        self.round.status = 'processed'
        self.round.save()
        r = self.client.post(reverse('round-control-reopen', args=[self.game.id]),
                             {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_set_deadline_minutes_from_now(self):
        r = self.client.post(reverse('round-control-deadline', args=[self.game.id]),
                             {'minutes_from_now': 90}, format='json')
        self.assertEqual(r.status_code, 200)
        self.round.refresh_from_db()
        self.assertIsNotNone(self.round.deadline)
        self.assertGreater(self.round.deadline, timezone.now())

    def test_setting_a_past_deadline_warns(self):
        past = (timezone.now() - timezone.timedelta(hours=1)).isoformat()
        r = self.client.post(reverse('round-control-deadline', args=[self.game.id]),
                             {'deadline': past}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data['warning'])

    def test_students_cannot_drive_the_round_lifecycle(self):
        self._auth(self.student)
        for route in ('round-control-close', 'round-control-process',
                      'round-control-advance', 'round-control-deadline'):
            r = self.client.post(reverse(route, args=[self.game.id]),
                                 {}, format='json')
            self.assertEqual(r.status_code, 403, f'{route} was not protected')


class PauseEnforcementTests(_BaseFixture):
    """Defect 5: pause set a flag that nothing read."""

    def setUp(self):
        super().setUp()
        self.team = self._make_team()
        self._enroll(self.team)
        self.url = reverse('decision-lock', args=[self.game.id, self.team.id, 1])

    def test_student_can_write_while_game_is_active(self):
        self._auth(self.student)
        r = self.client.post(self.url, {}, format='json')
        self.assertNotEqual(r.status_code, 403)

    def test_pause_blocks_student_writes(self):
        """The original bug: this used to succeed."""
        self.game.status = 'paused'
        self.game.save()
        self._auth(self.student)
        r = self.client.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_pause_still_allows_student_reads(self):
        self.game.status = 'paused'
        self.game.save()
        self._auth(self.student)
        r = self.client.get(reverse('decision-summary',
                                    args=[self.game.id, self.team.id, 1]))
        self.assertNotEqual(r.status_code, 403)

    def test_pause_does_not_block_the_instructor(self):
        self.game.status = 'paused'
        self.game.save()
        self._auth(self.instructor)
        r = self.client.get(reverse('round-control', args=[self.game.id]))
        self.assertEqual(r.status_code, 200)

    def test_archived_game_blocks_student_writes(self):
        self.game.status = 'archived'
        self.game.save()
        self._auth(self.student)
        r = self.client.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_resume_restores_student_writes(self):
        self.game.status = 'paused'
        self.game.save()
        self._auth(self.instructor)
        self.client.post(reverse('game-resume', args=[self.game.id]))
        self.game.refresh_from_db()
        self.assertEqual(self.game.status, 'active')

        self._auth(self.student)
        r = self.client.post(self.url, {}, format='json')
        self.assertNotEqual(r.status_code, 403)


class ClosedRoundBlocksSubmissionTests(_BaseFixture):
    """A closed or overdue round must reject student writes."""

    def setUp(self):
        super().setUp()
        self.team = self._make_team()
        self._enroll(self.team)
        self.url = reverse('decision-lock', args=[self.game.id, self.team.id, 1])
        self._auth(self.student)

    def test_closed_round_rejects_writes(self):
        self.round.status = 'closed'
        self.round.save()
        r = self.client.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_overdue_round_rejects_writes_even_if_still_marked_open(self):
        """Belt and braces: enforced live, not only by cron."""
        self.round.deadline = timezone.now() - timezone.timedelta(minutes=1)
        self.round.save()
        self.assertEqual(self.round.status, 'open')
        r = self.client.post(self.url, {}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_round_within_deadline_accepts_writes(self):
        self.round.deadline = timezone.now() + timezone.timedelta(hours=1)
        self.round.save()
        r = self.client.post(self.url, {}, format='json')
        self.assertNotEqual(r.status_code, 403)
