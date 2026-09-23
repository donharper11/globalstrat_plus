"""Third-walkthrough display and language repairs (W-CE3-*).

One file per walkthrough pass, as `test_walk_ce2_language.py` is for the
second. Each class names the defect it holds closed and fails on the
unmodified tree.
"""
import json
from decimal import Decimal as D

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.tests.test_cohort_caps import CohortCapTestBase
from core.tests.test_demotion_team_notice import DemotionNoticeFixture


# ---------------------------------------------------------------------------
# W-CE3-15 — the standings contradicted the numbers beside them
# ---------------------------------------------------------------------------

class TheLeaderboardSaysWhyTheTopScoreIsNotFirst(DemotionNoticeFixture):
    """R32 places a commercially inactive firm below every firm that competed.

    The team's own results screen explains it (R35). The leaderboard -- the
    screen a competition is read from -- had no field for it and no mention of
    it, so round 6 showed `4 Meridian Tech 60.34` under three lower scores
    with nothing to explain it.
    """

    def setUp(self):
        super().setUp()
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team])

    def board(self, language=None, user=None, round_number=1):
        headers = ({'HTTP_ACCEPT_LANGUAGE': language} if language else {})
        response = self.client_for(user or self.student).get(
            f'/api/games/{self.game.id}/leaderboard/round/{round_number}/',
            **headers)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def row(self, data, team):
        return next(r for r in data['rankings'] if r['team_id'] == team.id)

    def test_the_demoted_row_is_marked(self):
        data = self.board()

        self.assertTrue(self.row(data, self.team)['commercially_inactive'])
        self.assertTrue(self.row(data, self.team)['rank_marker'])

    def test_a_firm_that_competed_is_not_marked(self):
        data = self.board()

        self.assertFalse(self.row(data, self.rival)['commercially_inactive'])
        self.assertIsNone(self.row(data, self.rival)['rank_marker'])

    def test_the_rule_is_stated_under_the_table(self):
        note = self.board()['rank_rule_note']

        self.assertTrue(note)
        self.assertIn('did not compete', note)
        self.assertIn('not reduced', note)

    def test_the_marker_and_the_rule_read_in_chinese(self):
        data = self.board(language='zh-CN')

        self.assertEqual(self.row(data, self.team)['rank_marker'], '未参与竞争')
        self.assertIn('未参与竞争', data['rank_rule_note'])
        self.assertIn('绩效指数本身并未被扣减', data['rank_rule_note'])

    def test_the_marker_is_read_from_the_stored_receipt(self):
        """Not recomputed beside the record: a screen cannot disagree with the
        audit row about who was demoted."""
        from core.engine import leaderboard as rank_rules

        self.assertEqual(
            rank_rules.demoted_team_ids(self.game, 1), {self.team.id})
        self.assertEqual(self.receipt().payload['team_id'], self.team.id)

    def test_a_round_with_no_demotion_states_no_rule(self):
        self.assertTrue(self.board()['rank_rule_note'])

        # Round 2 was never ranked, so it carries no receipts and no rule.
        self.assertIsNone(self.board(round_number=2)['rank_rule_note'])

    def test_no_rival_score_is_published_by_the_marker(self):
        """R35's standard: the record names the firm that was outscored so a
        dispute can be answered; the marker does not republish it."""
        marker = self.row(self.board(), self.team)['rank_marker']

        self.assertNotIn(self.rival.name, marker)
        self.assertNotIn('60', marker)


class TheLeaderboardSentencesAreInTheCatalogue(SimpleTestCase):
    """Both languages, and no storage name in either (A1/A3's property)."""

    def test_both_sentences_carry_both_languages(self):
        from core.utils.participant_messages import MESSAGES

        for key in ('inactivity_rank_marker', 'inactivity_rank_rule'):
            with self.subTest(key=key):
                self.assertEqual(set(MESSAGES[key]), {'en', 'zh-CN'})
                for text in MESSAGES[key].values():
                    self.assertNotIn('_', text)


# ---------------------------------------------------------------------------
# W-CE3-16 — a dividend of $0.00 reported as exceeding projected equity
# ---------------------------------------------------------------------------

class AZeroDividendIsNotADistribution(TestCase):
    """*Total dividends of $0.00 exceed projected equity. Reduce the dividend.*

    It fired for every team whose projected equity was negative, in both
    languages, and it could not be cleared: there is nothing below zero to
    reduce a zero dividend to. It sat in the same blocker list as the cash
    blocker, so a team that had stripped every decision back to nothing still
    could not lock.
    """

    def setUp(self):
        from core.engine.utils import _config_cache
        from core.models import DecisionSubmission, Round
        from core.models.decisions import (DecisionBudgetAllocation,
                                           DecisionFinancing)
        from core.tests.test_operator_concurrency import build_minimal_game

        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, teams = build_minimal_game(f'ce3div-{id(self)}')
        self.team = teams[0]
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now()})
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=self.submission, rd_budget=D('0'),
            marketing_budget=D('0'), strategy_budget=D('0'),
            research_budget=D('0'))
        self.financing = DecisionFinancing.objects.create(
            submission=self.submission)
        # The state the walkthrough reached: equity driven below zero.
        self.team.total_equity = D('-5000000')
        self.team.shares_outstanding = 1000000
        self.team.save(update_fields=['total_equity', 'shares_outstanding'])

    def blockers(self, language='en'):
        from core.views.decisions import lock_blockers_for
        return lock_blockers_for(self.submission, language=language)

    def dividend_blockers(self, language='en'):
        """Blockers that are the dividend sentence, found by its own stem."""
        from core.utils.participant_messages import MESSAGES
        stem = MESSAGES['dividends_exceed_equity'][language].split('{')[0]
        return [b for b in self.blockers(language) if stem and stem in b]

    def test_a_zero_dividend_raises_no_blocker(self):
        self.assertEqual(self.dividend_blockers(), [])

    def test_a_zero_dividend_raises_no_blocker_in_chinese(self):
        self.assertEqual(self.dividend_blockers('zh-CN'), [])

    def test_a_real_dividend_above_equity_is_still_refused(self):
        """The rule itself is unchanged: only the zero case stops firing."""
        self.financing.dividend_per_share = D('1.0000')
        self.financing.save(update_fields=['dividend_per_share'])

        self.assertEqual(len(self.dividend_blockers()), 1)

    def test_a_real_dividend_within_equity_is_allowed(self):
        self.team.total_equity = D('5000000')
        self.team.save(update_fields=['total_equity'])
        self.financing.dividend_per_share = D('1.0000')
        self.financing.save(update_fields=['dividend_per_share'])

        self.assertEqual(self.dividend_blockers(), [])


# ---------------------------------------------------------------------------
# W-CE3-14 — a generation that is not listed and gives no reason
# ---------------------------------------------------------------------------

class ALockedGenerationNamesItsRequirement(TestCase):
    """The scenario's third generation carries `unlock_round: 5`.

    At round 5 it was not listed at all and no reason was given:
    `RDContextView` `continue`d past it unless the team already held an
    active Generation 2 platform. Every other gate on the platform names
    itself; this one was simply absent, and a team could not tell an unbuilt
    offer from one that does not exist.
    """

    def setUp(self):
        from core.engine.utils import _config_cache
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        from core.models.scenario import PlatformGenerationDefinition
        from core.tests.test_operator_concurrency import build_minimal_game

        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, teams = build_minimal_game(f'ce3gen-{id(self)}')
        self.team = teams[0]
        self.scenario = self.game.scenario
        self.game.current_round = 5
        self.game.save(update_fields=['current_round'])

        self.generations = {}
        for order, unlock in ((1, 0), (2, 3), (3, 5)):
            self.generations[order] = (
                PlatformGenerationDefinition.objects.create(
                    scenario=self.scenario, name=f'Generation {order}',
                    name_zh=f'第 {order} 代平台', description='d',
                    generation_order=order, unlock_round=unlock,
                    development_cost=D('1000000'), license_cost=D('2000000'),
                    development_rounds=1))

        course = Course.objects.create(
            course_code=f'CE3G{id(self) % 100000}', course_name='Gen',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.student = User.objects.create(
            username=f'ce3gen-{id(self)}', role='student', password_hash='x')
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)

    def context(self, language=None):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.student)}')
        headers = ({'HTTP_ACCEPT_LANGUAGE': language} if language else {})
        response = client.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/context/rd/',
            **headers)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def generation_row(self, data, order):
        return next((g for g in data['available_generations']
                     if g['generation_order'] == order), None)

    def test_the_third_generation_is_listed_at_its_unlock_round(self):
        row = self.generation_row(self.context(), 3)

        self.assertIsNotNone(
            row, 'the third generation is not listed at all')

    def test_it_is_listed_as_not_yet_buildable(self):
        row = self.generation_row(self.context(), 3)

        self.assertFalse(row['prerequisites_met'])

    def test_the_requirement_it_fails_is_stated(self):
        row = self.generation_row(self.context(), 3)

        unmet = [p for p in row['prerequisites'] if not p['met']]
        self.assertTrue(unmet, 'no requirement is named')
        self.assertIn('Generation 2 must be active',
                      [p['requirement'] for p in unmet])

    def test_the_requirement_reads_in_chinese(self):
        row = self.generation_row(self.context(language='zh-CN'), 3)

        unmet = [p['requirement'] for p in row['prerequisites'] if not p['met']]
        self.assertIn('第 2 代平台必须处于活跃状态', unmet)

    def test_the_round_requirement_is_met_at_round_five(self):
        """No unlock rule and no price changes: round 5 is round 5."""
        row = self.generation_row(self.context(), 3)

        rounds = [p for p in row['prerequisites']
                  if 'Round 5' in p['requirement']]
        self.assertEqual([p['met'] for p in rounds], [True])
        self.assertEqual(row['development_cost'], 1000000.0)

    def test_a_team_holding_generation_two_still_sees_it(self):
        from core.models.team_state import TeamPlatform

        TeamPlatform.objects.create(
            team=self.team, platform_generation=self.generations[2],
            name='Held', status='active', development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=0)

        row = self.generation_row(self.context(), 3)
        self.assertIsNotNone(row)


# ---------------------------------------------------------------------------
# W-CE3-20 — a hand-set score exported with nothing saying so
# ---------------------------------------------------------------------------

class TheGradesExportSaysWhatWasSetByHand(CohortCapTestBase):
    """The grades CSV carried **88.0** beside a real performance index of
    52.86 -- a score overridden from the console before a single round was
    played -- and had no column saying it was an override, though the
    console's own Team Grades table tags the row *Overridden* and shows the
    computed score it replaced.
    """

    def setUp(self):
        super().setUp()
        from django.utils import timezone as tz
        from core.models.course import SimulationInstance
        from core.models.grading import (GradingRubric,
                                         GradingRubricCategory, TeamGrade)

        self.instructor = self._instructor('ce3ex')
        course, section = self._make_section(
            instructor_id=self.instructor.pk, tag='CE3EX')
        self.instance = SimulationInstance.objects.create(
            section_id=section.section_id, current_round=7, total_rounds=10,
            status='active', settings={})
        rubric = GradingRubric.objects.create(
            course_id=course.course_id, rubric_name='CE3', is_active=True,
            created_at=tz.now(), updated_at=tz.now())
        self.category = GradingRubricCategory.objects.create(
            rubric_id=rubric.rubric_id, category_name='Performance Index',
            weight=D('100.00'), sort_order=1)
        self.overridden = TeamGrade.objects.create(
            instance_id=self.instance.instance_id, team_id=1,
            category_id=self.category.category_id,
            computed_score=D('52.86'), override_score=D('88.00'),
            final_score=D('88.00'))
        TeamGrade.objects.create(
            instance_id=self.instance.instance_id, team_id=2,
            category_id=self.category.category_id,
            computed_score=D('61.40'), override_score=None,
            final_score=D('61.40'))

    def rows(self):
        import csv
        import io as _io
        response = self._client(self.instructor).get(
            f'/api/grades/export/teams/?instance_id='
            f'{self.instance.instance_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return list(csv.reader(_io.StringIO(
            response.content.decode('utf-8'))))

    def test_the_file_has_a_column_for_it(self):
        self.assertIn('Overridden Categories', self.rows()[0])

    def test_the_overridden_row_names_the_category_and_the_computed_score(self):
        rows = self.rows()
        column = rows[0].index('Overridden Categories')
        row = next(r for r in rows[1:] if r[0] == '1')

        self.assertIn('Performance Index', row[column])
        self.assertIn('52.9', row[column])

    def test_a_row_nobody_touched_says_nothing(self):
        rows = self.rows()
        column = rows[0].index('Overridden Categories')
        row = next(r for r in rows[1:] if r[0] == '2')

        self.assertEqual(row[column], '')

    def test_the_score_columns_stay_numeric(self):
        """One trailing column, not a companion per category: a spreadsheet
        still sums the scores."""
        rows = self.rows()
        row = next(r for r in rows[1:] if r[0] == '1')

        self.assertEqual(float(row[rows[0].index('Performance Index')]), 88.0)


# ---------------------------------------------------------------------------
# W-CE3-06 / W-CE3-07 — the Strategic Scorecard's last two English leaks
# ---------------------------------------------------------------------------

class TheScorecardReadsWhollyInOneLanguage(SimpleTestCase):
    """W-CE2-07 translated the leverage and budget sentences and left two.

    The governance/tax sentence stayed English on a Chinese screen beside two
    Chinese siblings, and the market's English name stayed inside the
    criterion detail tables while the same market read 非洲 / 北美 everywhere
    else in the same response.

    Both are rendered into a copy for the reader; the stored row -- a hashed
    field of the competitive `coherence` section -- is never written.
    """

    def setUp(self):
        from core.services import coherence_feedback
        self.mod = coherence_feedback

    # -- W-CE3-06 --------------------------------------------------------

    def stored(self):
        """A breakdown shaped exactly as `engine/coherence.py` writes it."""
        return {
            'financial_prudence': {
                'score': 1.0, 'debt_to_equity': 0.4,
                'feedback': 'Conservative leverage. Strong financial position.',
            },
            'governance_tax': {
                'score': 1.0,
                'feedback': 'No governance-tax conflict detected.',
            },
            'entry_mode_risk': {
                'score': 0.8,
                'details': [{'market': 'Africa', 'risk': 5, 'control': 6,
                             'score': 0.8}],
            },
            'positioning_price': {
                'score': 0.5,
                'details': [{'product': 'Nexus One', 'market': 'North America',
                             'price': 400, 'range': '300-500',
                             'aligned': True}],
            },
        }

    def test_the_governance_sentence_follows_the_reader(self):
        rendered = self.mod.localised_breakdown(self.stored(), 'zh-CN')

        self.assertEqual(rendered['governance_tax']['feedback'],
                         '未发现治理与税务之间的冲突。')

    def test_the_governance_sentence_is_placed_under_either_name(self):
        """The scoring function is `_score_governance_tax_consistency`; the
        stored key is `governance_tax`. A row under either is placed."""
        for name in self.mod.GOVERNANCE_TAX_NAMES:
            with self.subTest(name=name):
                rendered = self.mod.localised_breakdown(
                    {name: {'score': 0.0, 'feedback': 'x'}}, 'zh-CN')
                self.assertNotEqual(rendered[name]['feedback'], 'x')

    def test_the_english_reader_still_gets_the_stored_bytes(self):
        stored = self.stored()

        self.assertEqual(self.mod.localised_breakdown(stored, 'en'), stored)

    # -- W-CE3-07 --------------------------------------------------------

    def names(self):
        return {'Africa': '非洲', 'North America': '北美'}

    def test_the_detail_tables_name_the_market_for_the_reader(self):
        rendered = self.mod.localised_breakdown(
            self.stored(), 'zh-CN', market_names=self.names())

        self.assertEqual(
            rendered['entry_mode_risk']['details'][0]['market'], '非洲')
        self.assertEqual(
            rendered['positioning_price']['details'][0]['market'], '北美')

    def test_the_product_name_is_the_team_s_own_and_is_not_translated(self):
        rendered = self.mod.localised_breakdown(
            self.stored(), 'zh-CN', market_names=self.names())

        self.assertEqual(
            rendered['positioning_price']['details'][0]['product'],
            'Nexus One')

    def test_a_market_the_mapping_does_not_hold_keeps_its_stored_name(self):
        rendered = self.mod.localised_breakdown(
            self.stored(), 'zh-CN', market_names={'North America': '北美'})

        self.assertEqual(
            rendered['entry_mode_risk']['details'][0]['market'], 'Africa')

    def test_the_stored_row_is_never_written(self):
        stored = self.stored()
        before = json.dumps(stored, sort_keys=True, ensure_ascii=False)

        self.mod.localised_breakdown(stored, 'zh-CN',
                                     market_names=self.names())

        self.assertEqual(
            json.dumps(stored, sort_keys=True, ensure_ascii=False), before)

    def test_no_mapping_serves_the_details_exactly_as_stored(self):
        rendered = self.mod.localised_breakdown(self.stored(), 'zh-CN')

        self.assertEqual(
            rendered['entry_mode_risk']['details'],
            self.stored()['entry_mode_risk']['details'])


# ---------------------------------------------------------------------------
# W-CE3-09 / W-CE3-10 — the reads W-CE2-06's repair did not cover
# ---------------------------------------------------------------------------

class TheNamesLeftInEnglish(TestCase):
    """Two names that stayed English on a Chinese screen after W-CE2-06.

    The market's name on the supply-chain decision screens, which read
    `MarketDefinition.name` with no `get_localized_field`; and the English
    suffix of the platform name `game_creation` generates, on three reads
    beside the one `platform_display_name` already covered.
    """

    def setUp(self):
        from core.engine.utils import _config_cache
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        from core.models.scenario import (MarketDefinition,
                                          PlatformGenerationDefinition)
        from core.models.team_state import TeamPlatform
        from core.tests.test_operator_concurrency import build_minimal_game

        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, teams = build_minimal_game(f'ce3names-{id(self)}')
        self.team = teams[0]
        self.scenario = self.game.scenario
        MarketDefinition.objects.filter(scenario=self.scenario).update(
            name='North America', name_zh='北美')

        self.generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Generation 1', name_zh='第 1 代平台',
            description='d', generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        # Exactly the name `game_creation` writes for a starting platform.
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=self.generation,
            name=f'{self.team.name} Base Platform', status='active',
            development_method='in_house', development_started_round=0,
            funded_round=0, development_rounds_remaining=0)

        course = Course.objects.create(
            course_code=f'CE3N{id(self) % 100000}', course_name='Names',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.student = User.objects.create(
            username=f'ce3names-{id(self)}', role='student', password_hash='x')
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)

    def get(self, path, language=None):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.student)}')
        headers = ({'HTTP_ACCEPT_LANGUAGE': language} if language else {})
        response = client.get(path, **headers)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    # -- W-CE3-09 --------------------------------------------------------

    def markets(self, language=None):
        return self.get(f'/api/scenarios/{self.scenario.id}/markets/',
                        language)

    def test_the_supply_chain_market_list_names_the_market_for_the_reader(self):
        self.assertEqual([m['name'] for m in self.markets('zh-CN')], ['北美'])

    def test_the_english_reader_is_unchanged(self):
        self.assertEqual([m['name'] for m in self.markets()],
                         ['North America'])

    def test_the_market_code_stays_a_code(self):
        """`NA` / `APAC` are stable identifiers shown in a tag and used as an
        option value; they are codes in both languages."""
        self.assertEqual([m['code'] for m in self.markets('zh-CN')], ['HM'])

    # -- W-CE3-10 --------------------------------------------------------

    def test_the_create_product_platform_selector_renders_the_default(self):
        data = self.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/context/products/', 'zh-CN')

        names = [p['name'] for p in data['active_platforms']]
        self.assertEqual(names, [f'{self.team.name}基础平台'])

    def test_the_dashboard_scorecard_renders_the_default(self):
        data = self.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/dashboard/scorecard/',
            'zh-CN')

        self.assertNotIn('Base Platform', json.dumps(data, ensure_ascii=False))

    def test_a_team_with_no_platform_reads_a_sentence_not_the_literal_None(self):
        from core.models.team_state import TeamPlatform
        TeamPlatform.objects.filter(pk=self.platform.pk).update(
            status='retired')

        data = self.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}/dashboard/scorecard/',
            'zh-CN')

        blob = json.dumps(data, ensure_ascii=False)
        self.assertNotIn('"None"', blob)
        self.assertIn('无', blob)

    def test_a_name_the_team_chose_is_never_translated(self):
        from core.models.team_state import TeamPlatform
        TeamPlatform.objects.filter(pk=self.platform.pk).update(
            name='Aurora Core')

        data = self.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/context/products/', 'zh-CN')

        self.assertEqual([p['name'] for p in data['active_platforms']],
                         ['Aurora Core'])
