"""GSP-CRV2-12 — participant-facing language: the four V2-069 defects, and parity.

Every test here fails without the CRV2-12 change.

V2-069 recorded four residual defects after the CRV2-12 sweep landed
(`51d6616`, "route decision refusals through the bilingual catalogue"). This
module pins all four, plus the EN/ZH parity property that Stage 3 requires to
be demonstrated rather than asserted:

  1. `round_not_accepting` interpolated the raw English status token into the
     Chinese sentence, so a zh-CN participant read 第 N 回合状态为"closed".
  2. `IsTeamMember` said "change this team's decisions" on all of its routes,
     including the seven that are read-only.
  3. `DecisionSummaryView` returned storage names ("`rd_budget` is 0.") and
     English-only advice, which is the exact class of string F-PL-01 was
     raised about.
  4. `get_user_language` ran an `Enrollment` query on every permission check
     when no `Accept-Language` header was sent.

The static check `backend/scripts/check-participant-strings` is exercised by
`test_player_language_guard.py`, which is what stops a *new* string
regressing any of this.
"""
import ast
import re
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient, APIRequestFactory

from core.authentication import create_access_token
from core.models import DecisionSubmission, Round, User
from core.models.course import Course, Enrollment, Section
from core.models.decisions import DecisionBudgetAllocation
from core.models.scenario import EntryModeDefinition, MarketDefinition
from core.models.team_state import TeamMarketPresence
from core.services import funding_need
from core.tests.test_operator_concurrency import build_minimal_game
from core.utils.participant_messages import (
    FIELD_LABELS, MESSAGES, ROUND_STATUS_LABELS, participant_message,
    round_status_label,
)
from core.views.decisions import IsTeamMember

REPO_ROOT = Path(__file__).resolve().parents[3]
PLACEHOLDER = re.compile(r'\{(\w+)\}')


# ---------------------------------------------------------------------------
# V2-069.1 — the round status reaches a Chinese participant in Chinese
# ---------------------------------------------------------------------------

class RoundStatusLanguageTests(SimpleTestCase):

    def test_every_authored_round_status_has_a_participant_label(self):
        """A status the catalogue has not been taught would leak as English."""
        from core.models.core import Round as RoundModel
        authored = {value for value, _label in RoundModel.STATUS_CHOICES}
        self.assertEqual(authored - set(ROUND_STATUS_LABELS), set())

    def test_chinese_refusal_carries_no_english_status_token(self):
        """The defect verbatim: 第 3 回合状态为“closed”."""
        for status in ('pending', 'closed', 'processed'):
            message = participant_message(
                'round_not_accepting', language='zh-CN',
                round=3, status=round_status_label(status, 'zh-CN'))
            self.assertNotIn(status, message)
            self.assertNotRegex(
                message, r'[A-Za-z]{3,}',
                f'{status!r} left Latin text in a Chinese refusal: {message}')

    def test_english_refusal_is_unchanged(self):
        """The English sentence CRV2-12 already shipped must not move."""
        self.assertEqual(
            participant_message(
                'round_not_accepting', language='en',
                round=3, status=round_status_label('closed', 'en')),
            'Round 3 is closed and no longer accepts decisions.')

    def test_an_unknown_status_falls_back_rather_than_raising(self):
        self.assertEqual(round_status_label('archived', 'zh-CN'), 'archived')


# ---------------------------------------------------------------------------
# V2-069.2 — a refused read is not told it may not write
# ---------------------------------------------------------------------------

class TeamMemberPermissionWordingTests(SimpleTestCase):
    """No database: `self.message` is set before any lookup, and an
    unauthenticated request returns False before `_get_user_from_header`
    reaches the ORM."""

    def setUp(self):
        self.factory = APIRequestFactory()

    class _View:
        kwargs = {'team_id': 1}

    def _message_for(self, request):
        guard = IsTeamMember()
        guard.has_permission(request, self._View())
        return guard.message

    def test_a_refused_read_names_viewing(self):
        for method in ('get', 'head', 'options'):
            request = getattr(self.factory, method)('/')
            self.assertEqual(
                self._message_for(request),
                'You do not have permission to view this team’s decisions.',
                f'{method.upper()} was told it may not *change* decisions')

    def test_a_refused_write_still_names_changing(self):
        for method in ('post', 'put', 'patch', 'delete'):
            request = getattr(self.factory, method)('/')
            self.assertEqual(
                self._message_for(request),
                'You do not have permission to change this team’s decisions.')

    def test_a_refused_read_is_localised(self):
        request = self.factory.get('/', HTTP_ACCEPT_LANGUAGE='zh-CN')
        self.assertEqual(self._message_for(request), '您无权查看该团队的决策。')

    def test_the_seven_read_only_routes_are_still_seven(self):
        """The finding counted seven. If a write lands on one of these classes
        the count changes and this wording decision needs revisiting."""
        source = (REPO_ROOT / 'backend/core/views/decisions.py').read_text(
            encoding='utf-8')
        read_only = []
        for node in ast.parse(source).body:
            if not isinstance(node, ast.ClassDef):
                continue
            perms = []
            for body in node.body:
                if (isinstance(body, ast.Assign)
                        and getattr(body.targets[0], 'id', '') == 'permission_classes'):
                    perms = [getattr(e, 'id', getattr(e, 'attr', ''))
                             for e in body.value.elts]
            if 'IsTeamMember' not in perms:
                continue
            methods = {b.name for b in node.body
                       if isinstance(b, ast.FunctionDef)
                       and b.name in ('get', 'post', 'put', 'patch', 'delete')}
            if methods <= {'get'}:
                read_only.append(node.name)
        self.assertEqual(len(read_only), 7, read_only)


# ---------------------------------------------------------------------------
# Stage 3 — EN/ZH parity, demonstrated by rendering
# ---------------------------------------------------------------------------

class BilingualParityTests(SimpleTestCase):

    def test_every_message_renders_in_both_languages_with_its_values(self):
        """Interpolation order is where translated strings break: a value
        present in one language and absent in the other raises KeyError at the
        moment a team is already being refused."""
        for key, entry in MESSAGES.items():
            english = set(PLACEHOLDER.findall(entry['en']))
            chinese = set(PLACEHOLDER.findall(entry['zh-CN']))
            self.assertEqual(
                english, chinese,
                f'{key} interpolates {english} in EN but {chinese} in ZH')
            values = {name: f'<{name}>' for name in english}
            for language in ('en', 'zh-CN'):
                rendered = participant_message(key, language=language, **values)
                for name in english:
                    self.assertIn(
                        f'<{name}>', rendered,
                        f'{key} ({language}) dropped {name} when rendered')

    def test_every_message_and_label_carries_both_languages(self):
        for name, catalogue in (('MESSAGES', MESSAGES),
                                ('FIELD_LABELS', FIELD_LABELS),
                                ('ROUND_STATUS_LABELS', ROUND_STATUS_LABELS)):
            for key, entry in catalogue.items():
                self.assertTrue(entry.get('en', '').strip(), f'{name}[{key}] en')
                self.assertTrue(entry.get('zh-CN', '').strip(),
                                f'{name}[{key}] zh-CN')


class FundingNeedWordingTests(SimpleTestCase):
    """The equity refusal moved into the catalogue. The engine records the
    English sentence and has no request to read a language from, so English
    must be byte-identical to what `advance_round` recorded before."""

    ASSESSMENT = {
        'requested_new_equity': '20000000', 'maximum_new_equity': '0',
        'eligible_uses': '1000', 'available_funding': '1000',
        'opening_cash': '1000', 'new_debt': '0',
    }

    def test_english_is_byte_identical_to_the_pre_crv2_12_sentence(self):
        self.assertEqual(
            funding_need.describe(self.ASSESSMENT, 'Team 1'),
            'Team 1: equity raise of $20,000,000.00 exceeds the funding '
            'shortfall of $0.00 (eligible uses $1,000.00 less available '
            'funding $1,000.00: opening cash $1,000.00 plus new debt $0.00). '
            'Equity may finance a genuine current-round shortfall; it may not '
            'create surplus cash or fund dividends.')

    def test_chinese_is_available_and_keeps_every_figure(self):
        chinese = funding_need.describe(
            self.ASSESSMENT, 'Team 1', language='zh-CN')
        for figure in ('$20,000,000.00', '$0.00', '$1,000.00'):
            self.assertIn(figure, chinese)
        self.assertIn('股权融资', chinese)


# ---------------------------------------------------------------------------
# V2-069.3 and V2-069.4 — the Decision Summary, and what it costs to build
# ---------------------------------------------------------------------------

def _uncached_get_user_language(request):
    """`get_user_language` exactly as it read before CRV2-12's memoisation.

    Used to measure the defect rather than assert it.
    """
    from core.utils.localization import _lang_from_header
    from core.models.course import Enrollment
    header_lang = _lang_from_header(request)
    if header_lang:
        return header_lang
    try:
        enrollment = Enrollment.objects.filter(
            user_id=request.user.id, is_active=True).first()
        return enrollment.language if enrollment and enrollment.language else 'en'
    except Exception:
        return 'en'


class DecisionSummaryLanguageTests(TestCase):

    # Storage names the Summary used to return, and the model fields that must
    # never appear in a participant payload.
    STORAGE_NAMES = ('rd_budget', 'marketing_budget', 'strategy_budget',
                     'retail_price', 'promotion_budget', 'target_market_ids')

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'crv212-{id(self)}')
        self.team = self.teams[0]
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')
        self.student = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'L{id(self) % 100000}', course_name='Lang',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)

    def _client(self, language=None):
        client = APIClient()
        credentials = {
            'HTTP_AUTHORIZATION': f'Bearer {create_access_token(self.student)}'}
        if language:
            credentials['HTTP_ACCEPT_LANGUAGE'] = language
        client.credentials(**credentials)
        return client

    def _url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
                f'round/{self.round.round_number}/summary/')

    def _with_zero_budget(self):
        submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=submission, rd_budget=D('0'),
            marketing_budget=D('0'), strategy_budget=D('0'))
        return submission

    @staticmethod
    def _all_text(payload):
        text = list(payload.get('lock_blockers') or [])
        for category in (payload.get('categories') or {}).values():
            text.extend(category.get('warnings') or [])
            text.extend(category.get('errors') or [])
        return text

    def _active_presence_without_products(self):
        """A market the team operates in but sells nothing in.

        The Summary's strategy warning names that market, so whichever
        language the name is in becomes visible in the response.
        """
        market = MarketDefinition.objects.filter(
            scenario=self.game.scenario).first()
        market.name_zh = '本土市场'
        market.save(update_fields=['name_zh'])
        entry_mode = EntryModeDefinition.objects.create(
            scenario=self.game.scenario, name='Wholly owned', code='WOS',
            description='d', capital_requirement=D('0'),
            control_level=D('1'), risk_level=D('1'),
            local_presence_score=D('1'))
        TeamMarketPresence.objects.create(
            team=self.team, market=market, entry_mode=entry_mode,
            established_round=0, initial_investment=D('0'), status='active')
        return market

    def test_a_market_name_reaches_a_chinese_participant_in_chinese(self):
        """The market name was interpolated raw, so a Chinese sentence
        carried an English market name."""
        market = self._active_presence_without_products()
        self._with_zero_budget()
        warnings = self._client('zh-CN').get(
            self._url()).data['categories']['strategy']['warnings']
        self.assertTrue(warnings, 'expected a strategy warning naming the market')
        joined = ' '.join(warnings)
        self.assertIn('本土市场', joined)
        self.assertNotIn(market.name, joined)

    def test_the_same_market_still_reads_in_english_for_an_english_request(self):
        market = self._active_presence_without_products()
        self._with_zero_budget()
        warnings = self._client('en').get(
            self._url()).data['categories']['strategy']['warnings']
        self.assertIn(market.name, ' '.join(warnings))

    def test_summary_returns_no_storage_name_in_either_language(self):
        self._with_zero_budget()
        for language in ('en', 'zh-CN'):
            response = self._client(language).get(self._url())
            self.assertEqual(response.status_code, 200, response.data)
            blob = ' '.join(self._all_text(response.data))
            for name in self.STORAGE_NAMES:
                self.assertNotIn(
                    name, blob,
                    f'{language}: storage name {name!r} reached a participant')

    def test_zero_budget_warning_names_the_business_object(self):
        self._with_zero_budget()
        warnings = self._client('en').get(
            self._url()).data['categories']['budget']['warnings']
        self.assertIn(
            'R&D budget is set to zero. Review this before locking.', warnings)

    def test_zero_budget_warning_is_localised(self):
        self._with_zero_budget()
        warnings = self._client('zh-CN').get(
            self._url()).data['categories']['budget']['warnings']
        self.assertIn('研发预算 已设为零。锁定前请确认。', warnings)

    def test_missing_submission_advice_is_localised(self):
        english = self._client('en').get(self._url()).data['lock_blockers']
        chinese = self._client('zh-CN').get(self._url()).data['lock_blockers']
        self.assertEqual(english, [
            'No decisions have been started for this round. '
            'Open any decision area to begin.'])
        self.assertEqual(chinese, [
            '本回合尚未开始任何决策。请打开任一决策页面开始填写。'])

    def test_lock_blockers_are_localised_not_english_only(self):
        self._with_zero_budget()
        chinese = self._client('zh-CN').get(self._url()).data['lock_blockers']
        self.assertTrue(chinese)
        for blocker in chinese:
            self.assertRegex(
                blocker, r'[一-鿿]',
                f'a zh-CN participant was refused in English: {blocker}')

    # -- V2-069.4: the cost of resolving the language ----------------------

    def _enrollment_queries(self, uncached):
        client = self._client()          # deliberately no Accept-Language
        target = 'core.views.decisions.get_user_language'
        with CaptureQueriesContext(connection) as captured:
            if uncached:
                with patch(target, _uncached_get_user_language):
                    response = client.get(self._url())
            else:
                response = client.get(self._url())
        self.assertEqual(response.status_code, 200)
        # Only the language lookup, which is the one query that reads the
        # `language` column. `IsTeamMember`'s own membership check hits the
        # same table (`SELECT 1 AS "a" ... team_id AND user_id`) and the
        # supply-chain categories touch `sc_sinosure_enrollment`; counting
        # every statement whose text contains "enrollment" conflates all
        # three and measures nothing.
        return [query['sql'] for query in captured.captured_queries
                if '"enrollment"."language"' in query['sql']]

    def test_language_is_resolved_once_per_request(self):
        """The measurement, and the repair, on a representative request.

        A GET of the Decision Summary with no `Accept-Language` header. The
        permission check and the view body each resolve the caller's language,
        and before the memoisation each resolution was its own `Enrollment`
        query. Two is what this one endpoint costs; `views/decisions.py` calls
        the resolver from twenty-four places, so a request that crosses more
        of them paid more.
        """
        self._with_zero_budget()
        before = self._enrollment_queries(uncached=True)
        after = self._enrollment_queries(uncached=False)
        self.assertEqual(
            len(before), 2,
            f'expected the pre-CRV2-12 helper to resolve the language twice, '
            f'got {len(before)}: {before}')
        self.assertEqual(
            len(after), 1,
            f'language resolution should cost one query, not {len(after)}: '
            f'{after}')
