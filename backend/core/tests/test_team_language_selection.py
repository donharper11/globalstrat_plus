"""Which member decides a team's language, pinned — and why it is not a bug.

`get_team_language` reads
``Enrollment.objects.filter(team_id=…, is_active=True).exclude(language='')
.first()``. It looks like the V2-140 defect — a `LIMIT 1` over a queryset with
no `ORDER BY` — and it is not. **Django's `QuerySet.first()` orders by `pk`
when the queryset is unordered** (`django/db/models/query.py`, 5.2.4), so the
answer is the lowest `enrollment_id` that states a language, every time. The
first version of these tests was written to catch a heap-order defect, and the
perturbation that exposes one for the console's course list changed nothing
here; the compiled SQL says why. **Nothing in this module asks for a
production change**, and the reader who comes to this function next should not
spend the hour again.

What IS worth pinning is the rule itself, because nothing tested it and
something real rests on it. In the ten-round browser pass on candidate
`a0631e5d`, a Simplified-Chinese student read an English memo evaluation:
`_fallback_evaluation` asks for the TEAM's language, the team's language is its
first-enrolled member's, and that member states English. `_FALLBACK_TEXT`
carries a complete Chinese block — nothing was missing from the catalogue, and
the team was simply resolved as English.

So the defect is not in how the language is found. It is the open question of
**what language a team-wide artefact should use when the team's members
differ**, which is the owner's and is already recorded as theirs. These tests
state today's answer precisely enough that changing it has to be deliberate.
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.models.course import Course, Enrollment, Section
from core.tests.test_operator_concurrency import build_minimal_game
from core.utils.localization import get_team_language


class TeamLanguageSelectionTests(TestCase):
    """One team, three members, and a stable answer."""

    def setUp(self):
        self.game, self.team = self._game_and_team()
        self.course = Course.objects.create(
            course_code=f'TL{id(self) % 100000}', course_name='Language course',
            instructor_id=None, is_active=True)
        self.section = Section.objects.create(
            course_id=self.course.course_id, section_code='TL1',
            section_name='Section 1', max_teams=4, team_size_min=1,
            team_size_max=4, is_active=True)
        # Enrolled in order, and the FIRST one states Chinese: the fixture is
        # built so that the stated rule and the heap's answer differ once the
        # winning row is rewritten.
        self.first = self._enrol(1001, 'zh-CN')
        self.second = self._enrol(1002, 'en')
        self.third = self._enrol(1003, 'en')
        self.assertLess(self.first.enrollment_id, self.second.enrollment_id)

    def _game_and_team(self):
        game, teams = build_minimal_game(f'lang-{id(self)}')
        return game, teams[0]

    def _enrol(self, user_id, language):
        return Enrollment.objects.create(
            user_id=user_id, section=self.section, team_id=self.team.id,
            is_active=True, language=language)

    # ---- the stated rule ------------------------------------------------
    def test_the_team_language_is_the_first_enrolled_members(self):
        self.assertEqual(get_team_language(self.team), 'zh-CN')

    def test_an_unrelated_write_to_the_deciding_row_changes_nothing(self):
        """Not a heap-order test; the characterisation that replaced one.

        Rewriting the deciding enrolment is what inverts a sequential scan for
        the console's course list (V2-140). Here it changes nothing, because
        `first()` supplies `ORDER BY pk` — asserted directly below, rather
        than inferred from this passing.
        """
        self.assertEqual(get_team_language(self.team), 'zh-CN')
        Enrollment.objects.filter(pk=self.first.pk).update(
            onboarding_completed=True)
        self.assertEqual(get_team_language(self.team), 'zh-CN')

    def test_a_member_who_states_nothing_does_not_decide(self):
        """A blank language is not a vote for English.

        The filter already excluded blanks; ordering must not quietly let one
        win on being enrolled first. So the FIRST member states nothing here,
        and the answer has to come from the next member who did state one.
        """
        Enrollment.objects.filter(pk=self.first.pk).update(language='')
        self.assertEqual(get_team_language(self.team), 'en')

    def test_a_team_nobody_has_stated_a_language_for_reads_english(self):
        Enrollment.objects.filter(team_id=self.team.id).update(language='')
        self.assertEqual(get_team_language(self.team), 'en')

    def test_the_read_is_ordered_so_the_rule_is_stable(self):
        """Where the determinism actually comes from.

        `QuerySet.first()` adds `ORDER BY pk` to an unordered queryset, so the
        enrolment read is ordered even though the call site never says so.
        This asserts that out loud: if a future change gives `Enrollment` a
        `Meta.ordering`, or reaches the row by slicing instead of `first()`,
        the order becomes someone else's choice and this test says so.
        """
        with CaptureQueriesContext(connection) as captured:
            get_team_language(self.team)
        reads = [q['sql'] for q in captured.captured_queries
                 if 'enrollment' in q['sql'].lower()
                 and q['sql'].lstrip().upper().startswith('SELECT')]
        self.assertTrue(reads, 'the function ran no enrolment read to inspect')
        self.assertIn('ORDER BY', reads[-1].upper(),
                      'the enrolment read lost its order: which member decides '
                      "the team's language would become the heap's choice")
