"""V2-076 — `reset_simulation` is withheld from competition deployments.

Its TRUNCATE/UPDATE statements are not scoped to an instance and it swallows
its own failures. The SQL is deliberately unchanged; what these tests pin is
that the command refuses before it touches anything when the process is a
production/competition one or any instance is flagged as a competition heat,
and that no command-line option talks it out of refusing.

"Did not touch anything" is proven, not inferred: the command's own database
handle is replaced with a recorder for the duration of each refusal, and the
recorder must see no statement except the guard's single SELECT.
"""
import io
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings

from core.management.commands import reset_simulation
from core.models.course import Course, Section, SimulationInstance

NOT_COMPETITION = dict(IS_PRODUCTION=False, COMPETITION_REQUIRE_CLEAN_BUILD=False)


class StatementRecorder:
    """Stands in for the command's `connection`; records every statement."""

    def __init__(self):
        self.statements = []

    def cursor(self):
        recorder = self
        real = connection.cursor()

        class Cursor:
            def __enter__(self):
                real.__enter__()
                return self

            def __exit__(self, *exc):
                return real.__exit__(*exc)

            def execute(self, sql, params=None):
                recorder.statements.append(' '.join(sql.split()))
                return real.execute(sql, params)

            def fetchall(self):
                return real.fetchall()

            def fetchone(self):
                return real.fetchone()

        return Cursor()

    def ensure_connection(self):
        return connection.ensure_connection()

    def mutations(self):
        return [s for s in self.statements
                if s.split()[0].upper() in
                ('TRUNCATE', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'DROP')]


class ResetSimulationIsWithheld(TestCase):

    def run_command(self, *args):
        recorder = StatementRecorder()
        with mock.patch.object(reset_simulation, 'connection', recorder):
            try:
                call_command('reset_simulation', *args,
                             stdout=io.StringIO(), stderr=io.StringIO())
                error = None
            except CommandError as caught:
                error = caught
        return error, recorder

    def assert_refused(self, error, recorder, because):
        self.assertIsNotNone(error, 'the command ran instead of refusing')
        message = str(error)
        self.assertIn('REFUSED', message)
        self.assertIn('V2-076', message)
        self.assertIn(because, message)
        self.assertIn('no override', message)
        self.assertEqual(recorder.mutations(), [])
        # Nothing but (at most) the guard's own read of the competition flag.
        for statement in recorder.statements:
            self.assertTrue(
                statement.startswith('SELECT instance_id, settings FROM '
                                     'simulation_instance'), statement)

    def flag_a_heat(self, flagged=True):
        course = Course.objects.create(
            course_code=f'V76{id(self) % 100000}', course_name='V2-076',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S-V76',
            section_name='Section V2-076', max_teams=8, team_size_min=3,
            team_size_max=5, is_active=True)
        return SimulationInstance.objects.create(
            section_id=section.section_id, game_id=None, current_round=1,
            total_rounds=5,
            status='active',
            settings={'is_competition': True} if flagged else {})

    # -- the environment ----------------------------------------------------

    @override_settings(IS_PRODUCTION=True, ENVIRONMENT='production',
                       COMPETITION_REQUIRE_CLEAN_BUILD=False)
    def test_refuses_in_production(self):
        error, recorder = self.run_command('--confirm')
        self.assert_refused(error, recorder, 'production environment')
        self.assertEqual(recorder.statements, [])

    @override_settings(IS_PRODUCTION=False, COMPETITION_REQUIRE_CLEAN_BUILD=True)
    def test_refuses_on_a_competition_stack(self):
        error, recorder = self.run_command('--confirm')
        self.assert_refused(error, recorder, 'COMPETITION_REQUIRE_CLEAN_BUILD')
        self.assertEqual(recorder.statements, [])

    @override_settings(IS_PRODUCTION=True, ENVIRONMENT='production')
    def test_the_dry_run_is_refused_too(self):
        error, recorder = self.run_command()
        self.assert_refused(error, recorder, 'production environment')

    # -- the competition flag ------------------------------------------------

    @override_settings(**NOT_COMPETITION)
    def test_refuses_while_any_instance_is_a_competition_heat(self):
        heat = self.flag_a_heat()
        # A different instance is named: the SQL is not scoped to it, so which
        # instance the operator meant is beside the point.
        error, recorder = self.run_command(
            '--confirm', '--instance-id', str(heat.instance_id + 1000))
        self.assert_refused(error, recorder, "settings['is_competition']")
        self.assertIn(str(heat.instance_id), str(error))

    @override_settings(**NOT_COMPETITION)
    def test_refuses_when_the_flag_cannot_be_read(self):
        """Fail closed: an unreadable flag is treated as set."""
        recorder = StatementRecorder()

        def broken_cursor():
            raise RuntimeError('simulation_instance is unreachable')
        recorder.cursor = broken_cursor
        with mock.patch.object(reset_simulation, 'connection', recorder):
            with self.assertRaises(CommandError) as caught:
                call_command('reset_simulation', '--confirm',
                             stdout=io.StringIO(), stderr=io.StringIO())
        self.assertIn('could not be read', str(caught.exception))
        self.assertIn('REFUSED', str(caught.exception))

    # -- no way round it ----------------------------------------------------

    def test_there_is_no_override_option(self):
        parser = reset_simulation.Command().create_parser(
            'manage.py', 'reset_simulation')
        options = {option for action in parser._actions
                   for option in action.option_strings}
        self.assertEqual(
            {o for o in options if o.startswith('--')} - {
                '--help', '--version', '--verbosity', '--settings',
                '--pythonpath', '--traceback', '--no-color', '--force-color',
                '--skip-checks'},
            {'--confirm', '--instance-id', '--reset-competitors'})

    @override_settings(IS_PRODUCTION=True, ENVIRONMENT='production')
    def test_no_environment_variable_lifts_the_refusal(self):
        with mock.patch.dict('os.environ', {
                'RESET_SIMULATION_ALLOW': 'true',
                'ALLOW_RESET_SIMULATION': 'true',
                'RESET_SIMULATION_OVERRIDE': 'true'}):
            error, recorder = self.run_command('--confirm')
        self.assert_refused(error, recorder, 'production environment')

    # -- and it is a guard, not a deletion ------------------------------------

    @override_settings(**NOT_COMPETITION)
    def test_a_development_database_with_no_heat_is_not_refused(self):
        self.flag_a_heat(flagged=False)
        self.assertIsNone(reset_simulation.Command()._competition_refusal())
