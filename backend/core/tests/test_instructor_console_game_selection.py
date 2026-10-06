"""Which game an instructor's console opens on must not be the heap's choice.

`_user_payload` resolves an instructor's `game_id` from their first active
section. Both queries behind that were `LIMIT 1` and a bare `values()` over
no `ORDER BY`, so with two active courses the answer was whatever PostgreSQL
returned first -- and an unrelated `UPDATE` to a `section` row rewrites that
tuple, which can change the order a sequential scan produces.

A competition reaches this: Gate 4 runs a rehearsal heat and Gate 5 creates
the real one, and if one account owns both, the console can open the wrong
game, or open a different one after an edit. The repair orders both queries
by primary key.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import User
from core.models.course import Course, Section, SimulationInstance
from core.tests.test_operator_concurrency import build_minimal_game


class InstructorConsoleGameSelectionTests(TestCase):
    """Two active courses, one instructor, and a stable answer."""

    def setUp(self):
        self.instructor = User.objects.create(
            username=f'console-instr-{id(self)}', role='instructor',
            password_hash='x')
        self.first = self._heat('A')
        self.second = self._heat('B')
        # Lowest course_id is the stated winner; assert the fixture really
        # does order that way rather than trusting creation order.
        self.assertLess(self.first['course'].course_id,
                        self.second['course'].course_id)

    def _heat(self, tag):
        game, _teams = build_minimal_game(f'console-{tag}-{id(self)}')
        course = Course.objects.create(
            course_code=f'CS{tag}{id(self) % 100000}',
            course_name=f'Console {tag}',
            instructor_id=self.instructor.user_id, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code=f'S{tag}',
            section_name=f'Section {tag}', max_teams=4, team_size_min=1,
            team_size_max=4, is_active=True)
        game.section_id = section.section_id
        game.save(update_fields=['section_id'])
        instance = SimulationInstance.objects.create(
            section_id=section.section_id, game_id=game.id, total_rounds=10)
        return {'game': game, 'course': course, 'section': section,
                'instance': instance}

    def _console_game_id(self):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.instructor)}')
        response = client.get('/api/auth/me/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_the_console_opens_on_the_lowest_id_active_heat(self):
        payload = self._console_game_id()
        self.assertEqual(payload['game_id'], self.first['game'].id)

    def test_rewriting_the_winning_section_row_does_not_change_the_answer(self):
        """The defect's actual trigger: an UPDATE moves the live tuple.

        PostgreSQL writes a new version of an updated row after the old one,
        and a sequential scan returns tuples in physical order. Rewriting
        ONLY the lower-id section therefore puts it behind the other one in
        the heap, and an unordered `LIMIT 1` hands back the other course's
        section -- the instructor's console silently following an unrelated
        edit to the wrong game.

        Rewriting both rows in id order would *preserve* scan order and prove
        nothing; this test deliberately touches one.
        """
        before = self._console_game_id()['game_id']
        self.assertEqual(before, self.first['game'].id)
        Section.objects.filter(pk=self.first['section'].pk).update(
            section_name='Section A, renamed')
        self.assertEqual(self._console_game_id()['game_id'],
                         self.first['game'].id)

    def test_the_course_list_is_ordered_not_arbitrary(self):
        """The picker's order is served, so it has to be stated too.

        Same perturbation, same reason: rewrite only the first course.
        """
        Course.objects.filter(pk=self.first['course'].course_id).update(
            course_name='Console A, renamed')
        courses = self._console_game_id()['courses']
        self.assertEqual([entry['course_id'] for entry in courses],
                         sorted(entry['course_id'] for entry in courses))
        self.assertEqual(courses[0]['course_id'], self.first['course'].course_id)

    def test_a_deactivated_course_is_skipped_for_the_next_one(self):
        """Closing the rehearsal heat is the supported way to move on."""
        Course.objects.filter(pk=self.first['course'].course_id).update(
            is_active=False)
        self.assertEqual(self._console_game_id()['game_id'],
                         self.second['game'].id)
