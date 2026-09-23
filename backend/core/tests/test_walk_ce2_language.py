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


# ---------------------------------------------------------------------------
# W-CE2-08 -- the AI Coach alerts were always English, whatever the console's
# language. Two causes: a game created from the console is recorded against the
# first superuser, not the instructor, and an instructor created from the
# console has no `Enrollment`, so `PUT /api/user/preferences/` had nothing to
# write to and `get_instructor_language` could only answer 'en'.
# ---------------------------------------------------------------------------

class InstructorLanguagePreferenceTests(WalkCEBase):
    """The console's language switch must reach the coach."""

    def test_the_preference_route_stores_a_language_for_an_unenrolled_user(self):
        from core.models.preferences import UserLanguagePreference
        self.assertFalse(
            Enrollment.objects.filter(
                user_id=self.instructor.user_id).exists())
        response = self.client_for(self.instructor).put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            UserLanguagePreference.objects.get(
                user_id=self.instructor.user_id).language, 'zh-CN')

    def test_the_route_reads_back_what_it_stored(self):
        self.client_for(self.instructor).put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        read = self.client_for(self.instructor).get('/api/user/preferences/')
        self.assertEqual(read.data['language'], 'zh-CN')

    def test_an_unsupported_language_is_still_refused_and_stores_nothing(self):
        from core.models.preferences import UserLanguagePreference
        response = self.client_for(self.instructor).put(
            '/api/user/preferences/', {'language': 'fr'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(UserLanguagePreference.objects.filter(
            user_id=self.instructor.user_id).exists())

    def test_a_students_enrolment_is_still_written(self):
        """The existing behaviour the analyst repair depends on (W-CE-11)."""
        response = self.client_for(self.student).put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.language, 'zh-CN')


class InstructorOwnerLanguageTests(WalkCEBase):
    """`get_instructor_language` must find the instructor who owns the game.

    `Game.created_by` is a Django auth user, and `GameCreateView` records the
    first superuser whenever the caller is a `JWTUser` -- which is every
    console instructor. The owner in practice is the course instructor, found
    through the game's section.
    """

    def test_it_follows_the_course_instructors_stored_preference(self):
        from core.utils.localization import get_instructor_language
        self.assertEqual(get_instructor_language(self.game), 'en')
        self.client_for(self.instructor).put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        self.assertEqual(get_instructor_language(self.game), 'zh-CN')

    def test_the_created_by_enrolment_still_answers_when_there_is_no_course(self):
        """The path every existing caller used, unchanged."""
        from core.models import Game
        from core.utils.localization import get_instructor_language
        Game.objects.filter(pk=self.game.pk).update(section_id=None)
        self.game.refresh_from_db()
        Enrollment.objects.update_or_create(
            user_id=self.game.created_by_id,
            section_id=self.section.section_id,
            defaults={'is_active': True, 'language': 'zh-CN'})
        self.assertEqual(get_instructor_language(self.game), 'zh-CN')

    def test_an_unsupported_stored_language_reads_as_english(self):
        from core.models.preferences import UserLanguagePreference
        from core.utils.localization import get_instructor_language
        UserLanguagePreference.objects.create(
            user_id=self.instructor.user_id, language='fr')
        self.assertEqual(get_instructor_language(self.game), 'en')


class CoachAlertLanguageTests(WalkCEBase):
    """The panel the walkthrough could not read in Chinese."""

    def setUp(self):
        super().setUp()
        from core.models.results_financials import RoundResultFinancials
        RoundResultFinancials.objects.create(
            game=self.game, team=self.team, round_number=1)

    def _alerts(self):
        from core.engine.instructor_alerts import generate_post_round_alerts
        from core.models.cc21_models import InstructorAlert
        InstructorAlert.objects.filter(game=self.game).delete()
        generate_post_round_alerts(self.game, 1)
        return list(InstructorAlert.objects.filter(game=self.game))

    def test_the_alerts_are_english_for_an_english_console(self):
        alerts = self._alerts()
        self.assertTrue(alerts)
        self.assertFalse(any(has_cjk(a.title) for a in alerts), alerts)

    def test_the_alerts_follow_the_consoles_recorded_language(self):
        self.client_for(self.instructor).put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        alerts = self._alerts()
        self.assertTrue(alerts)
        for alert in alerts:
            self.assertTrue(has_cjk(alert.title), alert.title)
            self.assertTrue(has_cjk(alert.detail), alert.detail)

    def test_the_alerts_a_view_serves_are_the_stored_ones(self):
        """Read time changes nothing: the stored row is what the panel shows,
        so the language is the one fixed when the alert was written.
        """
        self.client_for(self.instructor).put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        self._alerts()
        response = self.client_for(self.instructor).get(
            f'/api/games/{self.game.id}/instructor/alerts/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['alerts'])
        for served in response.data['alerts']:
            self.assertTrue(has_cjk(served['title']), served)


# ---------------------------------------------------------------------------
# W-CE2-06 -- the market's English name on an otherwise Chinese screen.
# The CE scenario authors `name_zh` for every market (西欧 for Western Europe),
# so nothing here needs authored content: these are reads that skipped
# `get_localized_field`.
# ---------------------------------------------------------------------------

class MarketNameOnChineseScreensTests(WalkCEBase):

    def setUp(self):
        super().setUp()
        self.market.name = 'Western Europe'
        self.market.name_zh = '西欧'
        self.market.save(update_fields=['name', 'name_zh'])
        # `build_minimal_game` stops short of a platform; the Products screen
        # needs one, named the way `game_creation` names a starting platform.
        from core.models.scenario import PlatformGenerationDefinition
        from core.models.team_state import TeamPlatform
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.game.scenario, name='Gen 1', name_zh='第一代',
            description='d', generation_order=1, development_cost=0,
            license_cost=0, is_starting_platform=True)
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation,
            name=f'{self.team.name} Base Platform', status='active',
            activated_round=0)

    def test_the_scenario_authors_a_chinese_name_for_every_ce_market(self):
        """Stated precisely, because the repair depends on it."""
        from core.models.scenario import MarketDefinition
        missing = [m.name for m in MarketDefinition.objects.filter(
            scenario=self.game.scenario) if not m.name_zh]
        self.assertEqual(missing, [])

    def _products_context(self):
        return self.client_for(self.student, 'zh-CN').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/context/products/')

    def test_the_products_active_markets_column_is_chinese(self):
        from core.models.team_state import TeamProduct, TeamProductMarket
        product = TeamProduct.objects.create(
            team=self.team, team_platform=self.platform, name='IronClad Field',
            positioning='mainstream', status='active', created_round=1)
        TeamProductMarket.objects.create(
            team_product=product, market=self.market, is_active=True,
            first_offered_round=1)
        response = self._products_context()
        self.assertEqual(response.status_code, 200, response.data)
        rows = [p for p in response.data['products'] if p['id'] == product.id]
        self.assertTrue(rows)
        for entry in rows[0]['markets']:
            self.assertEqual(entry['market__name'], '西欧')

    def test_the_starting_platform_name_has_no_english_suffix(self):
        from core.utils.participant_messages import platform_display_name
        self.assertEqual(
            self.platform.name, f'{self.team.name} Base Platform')
        chinese = platform_display_name(
            self.platform, 'zh-CN', team_name=self.team.name)
        self.assertIsNone(
            LATIN_WORD.search(chinese.replace(self.team.name, '')), chinese)
        self.assertEqual(
            platform_display_name(self.platform, 'en',
                                  team_name=self.team.name),
            f'{self.team.name} Base Platform')

    def test_a_name_the_team_chose_is_left_alone(self):
        from core.utils.participant_messages import platform_display_name
        self.platform.name = 'Helios'
        self.platform.save(update_fields=['name'])
        self.assertEqual(
            platform_display_name(self.platform, 'zh-CN',
                                  team_name=self.team.name), 'Helios')

    def test_the_price_notice_names_the_market_in_chinese(self):
        from core.services import price_band
        payload = {
            'rule': price_band.RULE_BLANK,
            'product_name': 'IronClad Field',
            'market_id': self.market.id, 'market_name': 'Western Europe',
            'applied_price': '100', 'band_min': '90', 'band_max': '110',
        }
        notice = price_band.adjustment_notice(payload, 'zh-CN')
        self.assertIn('西欧', notice)
        self.assertNotIn('Western Europe', notice)
        self.assertEqual(
            price_band.market_name_for_reader(payload, 'zh-CN'), '西欧')
        self.assertEqual(
            price_band.market_name_for_reader(payload, 'en'), 'Western Europe')

    def test_a_payload_without_a_market_id_still_reads(self):
        """An adjustment recorded before the id was stored must not break."""
        from core.services import price_band
        payload = {
            'rule': price_band.RULE_BLANK, 'product_name': 'P',
            'market_name': 'Western Europe', 'applied_price': '100',
            'band_min': '90', 'band_max': '110',
        }
        self.assertIn(
            'Western Europe', price_band.adjustment_notice(payload, 'zh-CN'))

    def test_an_all_markets_event_is_not_the_english_word_global(self):
        """`results_api` printed the literal 'Global' for an event with no
        target market, on a Chinese screen as well as an English one.
        """
        from core.utils.participant_messages import market_label
        self.assertEqual(market_label(self.market, 'zh-CN'), '西欧')
        self.assertEqual(market_label(self.market, 'en'), 'Western Europe')
        self.assertEqual(market_label(None, 'en'), 'Global')
        self.assertEqual(market_label(None, 'zh-CN'), '全球')


# ---------------------------------------------------------------------------
# W-CE2-07 -- the Strategic Scorecard's sentences were English f-strings in
# `engine/coherence.py` with no catalogue entry. What the engine STORES may
# not change: `breakdown` is a hashed field of the `coherence` manifest
# section. The stored sentence stays English and the reader re-derives the
# same key from the same stored numbers, through the same function.
# ---------------------------------------------------------------------------

class ScorecardSentenceTests(WalkCEBase):

    def test_the_english_stored_by_the_engine_is_byte_identical(self):
        from core.services import coherence_feedback as fb
        self.assertEqual(
            fb.feedback_text(fb.financial_prudence_key(0.5), 'en'),
            'Conservative leverage. Strong financial position.')
        self.assertEqual(
            fb.feedback_text(fb.financial_prudence_key(1.5), 'en'),
            'Moderate leverage. Manageable but watch debt growth.')
        self.assertEqual(
            fb.feedback_text(fb.financial_prudence_key(3.0), 'en'),
            'High leverage. Risk of financial distress.')
        self.assertEqual(
            fb.feedback_text(fb.budget_discipline_key(0, 5000000), 'en'),
            'Spending within operating budget. Good fiscal discipline.')
        self.assertEqual(
            fb.feedback_text(fb.budget_discipline_key(0.12, 5000000), 'en',
                             over='12%'),
            'Over budget by 12%. Spending discipline is weak.')
        self.assertEqual(
            fb.feedback_text(fb.budget_discipline_key(0, 0), 'en'),
            'No operating budget baseline (first round).')

    def test_every_key_has_both_languages(self):
        from core.services import coherence_feedback as fb
        from core.utils.participant_messages import MESSAGES
        for key in fb.ALL_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, MESSAGES)
                self.assertTrue(MESSAGES[key]['zh-CN'])
                self.assertTrue(has_cjk(MESSAGES[key]['zh-CN']))

    def test_the_reader_renders_a_stored_entry_in_chinese(self):
        from core.services import coherence_feedback as fb
        entry = {'score': 1.0, 'debt_to_equity': 0.4,
                 'feedback': 'Conservative leverage. Strong financial position.'}
        rendered = fb.feedback_for_reader('financial_prudence', entry, 'zh-CN')
        self.assertTrue(has_cjk(rendered), rendered)
        self.assertIsNone(LATIN_WORD.search(rendered), rendered)
        self.assertEqual(
            fb.feedback_for_reader('financial_prudence', entry, 'en'),
            entry['feedback'])

    def test_a_percentage_is_kept_in_the_translated_sentence(self):
        from core.services import coherence_feedback as fb
        entry = {'score': 0.5, 'over_pct': 0.12, 'operating_budget': 5000000,
                 'feedback': 'Over budget by 12%. Spending discipline is weak.'}
        rendered = fb.feedback_for_reader('budget_discipline', entry, 'zh-CN')
        self.assertIn('12%', rendered)
        self.assertTrue(has_cjk(rendered), rendered)

    def test_an_entry_the_reader_cannot_place_keeps_its_stored_sentence(self):
        """A breakdown written by an older engine, or a criterion with no
        rule here, must not lose the sentence it already has.
        """
        from core.services import coherence_feedback as fb
        entry = {'score': 0.5, 'feedback': 'Something older.'}
        self.assertEqual(
            fb.feedback_for_reader('rd_market_alignment', entry, 'zh-CN'),
            'Something older.')
        self.assertEqual(
            fb.feedback_for_reader('financial_prudence', {}, 'zh-CN'), '')

    def test_the_governance_sentence_is_placed_by_its_score(self):
        from core.services import coherence_feedback as fb
        for score, fragment in ((1.0, '未发现'), (0.0, '反腐败'), (0.7, '激进')):
            entry = {'score': score, 'feedback': 'x'}
            rendered = fb.feedback_for_reader(
                'governance_tax_consistency', entry, 'zh-CN')
            self.assertIn(fragment, rendered)

    def test_the_results_route_serves_the_scorecard_in_chinese(self):
        from core.models.results_financials import RoundResultCoherence
        Enrollment.objects.filter(pk=self.enrollment.pk).update(
            language='zh-CN')
        RoundResultCoherence.objects.create(
            game=self.game, team=self.team, round_number=1,
            formula_score=80, blended_score=80,
            breakdown={'financial_prudence': {
                'score': 1.0, 'debt_to_equity': 0.4,
                'feedback': 'Conservative leverage. Strong financial position.'}})
        response = self.client_for(self.student, 'zh-CN').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/results/round/1/')
        self.assertEqual(response.status_code, 200, response.data)
        served = (response.data['coherence']['breakdown']
                  ['financial_prudence']['feedback'])
        self.assertTrue(has_cjk(served), served)
        self.assertNotIn('Conservative leverage', served)

    def test_the_stored_row_is_untouched_by_a_chinese_read(self):
        from core.models.results_financials import RoundResultCoherence
        row = RoundResultCoherence.objects.create(
            game=self.game, team=self.team, round_number=1,
            formula_score=80, blended_score=80,
            breakdown={'financial_prudence': {
                'score': 1.0, 'debt_to_equity': 0.4,
                'feedback': 'Conservative leverage. Strong financial position.'}})
        self.client_for(self.student, 'zh-CN').get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/results/round/1/')
        row.refresh_from_db()
        self.assertEqual(
            row.breakdown['financial_prudence']['feedback'],
            'Conservative leverage. Strong financial position.')


# ---------------------------------------------------------------------------
# W-CE2-04 -- the Operator Log printed the server's internal error verbatim.
# ---------------------------------------------------------------------------

SNAPSHOT_ERROR = (
    "Natural key ('team_id', 'market_id', 'construction_started_round') is "
    'not unique in section "team_plant": team_plant(team(game("CE 2026 Heat A")'
    '|"Aurora Devices")|…)|"2") appears twice. Declare a key that identifies '
    'a row, or set key=None to use a content key.')


class OperatorLogFaultSentenceTests(WalkCEBase):

    def _fault_conflict(self, message_key='processing_failed'):
        from core.authentication import JWTUser
        from core.services.lifecycle import operator_action
        from django.test import RequestFactory
        request = RequestFactory().post('/')
        request.user = JWTUser(self.instructor)
        request.data = {}
        with operator_action(request, self.game.id, 'process_round') as action:
            action.require_round()
            event = action.record_fault(
                SNAPSHOT_ERROR, message_key=message_key)
        return event.conflict

    def test_the_stored_row_carries_a_sentence_not_a_python_string(self):
        conflict = self._fault_conflict()
        self.assertEqual(conflict['cause'], SNAPSHOT_ERROR)
        self.assertTrue(conflict['detail'].startswith(
            'Post-round processing failed:'), conflict['detail'])
        self.assertEqual(conflict['message_key'], 'processing_failed')
        self.assertEqual(conflict['code'], 'processing_failed')

    def test_the_stored_sentence_is_english_r44(self):
        conflict = self._fault_conflict()
        self.assertFalse(has_cjk(conflict['detail']), conflict)

    def test_the_log_serves_the_sentence_in_the_operators_language(self):
        self._fault_conflict()
        self.client_for(self.instructor).put(
            '/api/user/preferences/', {'language': 'zh-CN'}, format='json')
        response = self.client_for(self.instructor, 'zh-CN').get(
            f'/api/games/{self.game.id}/instructor/operator-events/')
        self.assertEqual(response.status_code, 200, response.data)
        rejected = [e for e in response.data['events']
                    if e['outcome'] == 'rejected']
        self.assertTrue(rejected, response.data)
        detail = rejected[0]['conflict']['detail']
        self.assertTrue(has_cjk(detail), detail)
        # The technical cause is kept for the operator, labelled as English by
        # the sentence itself.
        self.assertIn('Natural key', detail)
        self.assertIn('（英文）', detail)
        self.assertEqual(rejected[0]['conflict']['cause'], SNAPSHOT_ERROR)

    def test_the_english_log_reads_exactly_what_is_stored(self):
        conflict = self._fault_conflict()
        response = self.client_for(self.instructor, 'en').get(
            f'/api/games/{self.game.id}/instructor/operator-events/')
        rejected = [e for e in response.data['events']
                    if e['outcome'] == 'rejected']
        self.assertEqual(rejected[0]['conflict']['detail'],
                         conflict['detail'])

    def test_a_conflict_with_no_message_key_is_served_unchanged(self):
        """A lifecycle refusal's row keeps the English sentence it stored."""
        from core.utils.operator_messages import localise_conflict
        stored = {'code': 'round_not_open', 'detail': 'Round 1 is closed.',
                  'status': 409}
        self.assertEqual(localise_conflict(stored, 'zh-CN'), stored)
        self.assertEqual(localise_conflict(None, 'zh-CN'), None)

    def test_every_fault_key_a_call_site_uses_is_bilingual(self):
        from core.utils.operator_messages import MESSAGES
        for key in ('processing_failed', 'advance_failed',
                    'legacy_advance_failed'):
            with self.subTest(key=key):
                self.assertTrue(has_cjk(MESSAGES[key]['zh-CN']))
                self.assertIn('{detail}', MESSAGES[key]['zh-CN'])
