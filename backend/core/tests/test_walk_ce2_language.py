"""The language defects of the second Consumer Electronics walkthrough.

Each class pins one defect id from
`handoff_readiness_v2/completion/WALKTHROUGH_CE_2_2026-09-22.md` (the findings
table). Every test here was red on `48a8a92` and is green after the repair the
completion report `WALK_CE2_LANGUAGE_2026-09-23.md` names for that id.

Fixture: `WalkCEBase` from `test_walk_ce_language`, extended where a defect
needs a second team member or an instructor with a stated language.
"""
from core.models import User
from core.models.course import Enrollment
from core.tests.test_walk_ce_language import (
    LATIN_WORD, WalkCEBase, has_cjk)


# ---------------------------------------------------------------------------
# W-CE2-05 -- a team's language was its FIRST enrolment's, so a Chinese-reading
# student whose team-mate enrolled first was answered in English however often
# they chose 中文.
# ---------------------------------------------------------------------------

class SecondMemberLanguageTests(WalkCEBase):
    """The walkthrough's team 3: member one enrolled in English, member two
    reads Chinese. R43 said the team's language governs; it did not settle
    whose language that is when members differ, and "the first enrolment's"
    left the choice unreachable for every member but one.
    """

    def setUp(self):
        super().setUp()
        from core.models.scenario import ScenarioConfig
        ScenarioConfig.objects.create(
            scenario=self.game.scenario, config_key='rag_enabled',
            config_value='false', description='no analyst in this game')
        # Member one, enrolled first, states English -- this is `self.enrollment`.
        Enrollment.objects.filter(pk=self.enrollment.pk).update(language='en')
        # Member two, enrolled second, states Chinese.
        self.second_student = User.objects.create(
            username=f'walk-student2-{id(self)}', role='student',
            password_hash='x')
        self.second_enrollment = Enrollment.objects.create(
            user_id=self.second_student.user_id,
            section_id=self.section.section_id,
            team_id=self.team.id, is_active=True, language='zh-CN')

    def _ask(self, user, header_language=None):
        return self.client_for(user, header_language).post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/research/query/',
            {'query': 'q'}, format='json')

    def test_the_second_member_is_refused_in_their_own_language(self):
        """The defect: this refusal was English because a team-mate was first."""
        response = self._ask(self.second_student, 'zh-CN')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertTrue(has_cjk(response.data['error']), response.data)
        self.assertIsNone(
            LATIN_WORD.search(response.data['error']), response.data)

    def test_the_first_member_still_reads_english(self):
        """Each member is answered in their own stated language."""
        response = self._ask(self.student, 'zh-CN')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(has_cjk(response.data['error']), response.data)

    def test_the_header_still_does_not_govern(self):
        """R43 rejected the request's language governing; it still does not.

        Member two states Chinese in their enrolment and sends an English
        browser header: the sentence stays Chinese.
        """
        response = self._ask(self.second_student, 'en')
        self.assertTrue(has_cjk(response.data['error']), response.data)

    def test_a_member_stating_nothing_falls_back_to_the_team(self):
        """The safe fallback: no stated language on the asker's own enrolment
        means the team rule (R43) answers, exactly as before.
        """
        Enrollment.objects.filter(pk=self.second_enrollment.pk).update(
            language='')
        Enrollment.objects.filter(pk=self.enrollment.pk).update(
            language='zh-CN')
        response = self._ask(self.second_student)
        self.assertTrue(has_cjk(response.data['error']), response.data)

    def test_an_unsupported_stated_language_falls_back(self):
        """An enrolment language the catalogue has no entry for must never
        raise `KeyError` out of a refusal.
        """
        Enrollment.objects.filter(pk=self.second_enrollment.pk).update(
            language='fr')
        response = self._ask(self.second_student)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(has_cjk(response.data['error']), response.data)


class ParticipantLanguageResolverTests(WalkCEBase):
    """`language_for_participant` itself: the resolver, apart from the route."""

    def setUp(self):
        super().setUp()
        Enrollment.objects.filter(pk=self.enrollment.pk).update(language='en')
        self.second_student = User.objects.create(
            username=f'walk-resolver2-{id(self)}', role='student',
            password_hash='x')
        Enrollment.objects.create(
            user_id=self.second_student.user_id,
            section_id=self.section.section_id,
            team_id=self.team.id, is_active=True, language='zh-CN')

    def _request(self, user):
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        request.user = user
        return request

    def test_it_reads_the_asking_members_own_enrolment(self):
        from core.utils.participant_messages import (
            language_for_participant, language_for_team)
        request = self._request(self.second_student)
        self.assertEqual(language_for_team(self.team, request), 'en')
        self.assertEqual(
            language_for_participant(self.team, request), 'zh-CN')

    def test_no_user_on_the_request_is_the_team_rule(self):
        from core.utils.participant_messages import (
            language_for_participant, language_for_team)
        request = self._request(None)
        self.assertEqual(
            language_for_participant(self.team, request),
            language_for_team(self.team, request))

    def test_a_user_with_no_enrolment_on_this_team_is_the_team_rule(self):
        from core.utils.participant_messages import language_for_participant
        Enrollment.objects.filter(pk=self.enrollment.pk).update(
            language='zh-CN')
        request = self._request(self.instructor)
        self.assertEqual(
            language_for_participant(self.team, request), 'zh-CN')


class TeamWideProseKeepsTheTeamRuleTests(WalkCEBase):
    """The other half of the W-CE2-05 repair: prose written once for the whole
    team is unchanged -- it still follows `get_team_language`, the first active
    enrolment that states one. Recorded so the split is visible in a test, and
    so a later builder cannot move it without this failing.
    """

    def setUp(self):
        super().setUp()
        Enrollment.objects.filter(pk=self.enrollment.pk).update(language='en')
        self.second_student = User.objects.create(
            username=f'walk-prose2-{id(self)}', role='student',
            password_hash='x')
        Enrollment.objects.create(
            user_id=self.second_student.user_id,
            section_id=self.section.section_id,
            team_id=self.team.id, is_active=True, language='zh-CN')

    def test_the_round_briefing_follows_the_team_not_the_second_member(self):
        from core.engine.narratives import _build_briefing_fields
        fields = _build_briefing_fields(self.game, 1, self.team)
        self.assertFalse(has_cjk(fields['executive_summary']), fields)

    def test_the_team_resolver_is_unchanged(self):
        from core.utils.localization import get_team_language
        self.assertEqual(get_team_language(self.team), 'en')
