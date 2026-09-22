"""Two decisions a student could not make, and the saves that said nothing.

Found 2026-09-21 (BOUNDED_NUMBER_INPUTS F1). `CorporateStrategyPage` autosaved
staff allocation to the section `talent_allocations` and `MarketStrategyPage`
autosaved compliance investment to `compliance_investments`. Neither was a key
of `_TYPE_MAP`, so `DecisionPartialUpdateView` answered every one of those
saves with 400 `unknown_decision_type`; both pages ended the call in
`catch { /* ignore */ }`. The tables, the serializers and the engine consumers
all existed, so these were live competitive decisions that no team could make
from the screen, on a screen that showed the number they had typed.

The payloads were wrong as well as the section names: the pages sent a dict
keyed by pool / by market code, the serializers take a list of rows. And the
allocation rules `TalentAllocationSerializer.validate` carries -- the total
must equal the headcount, a fifth stays at headquarters, only active markets
-- had never run on any route, because nothing passed the `submission` they
read from the serializer context.

Every route test here drives the real URL with a JWT student, in both
languages. `ResolvedRoundTests` closes and resolves a round through
`process_round` and reads the engine's own tables.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.models import DecisionSubmission, Round
from core.models.cc31_models import (ComplianceInvestment, TalentAllocation,
                                     TeamMarketCompliance)
from core.models.competition_audit import DecisionAuditEvent
from core.models.scenario import EntryModeDefinition, MarketDefinition
from core.models.talent import DecisionTalent
from core.models.team_state import TeamMarketPresence
from core.tests.test_operator_concurrency import build_minimal_game
from core.utils.participant_messages import participant_message

LANGUAGES = ('en', 'zh-CN')

TALENT = {
    'rd_headcount': 50, 'rd_salary_level': 3, 'rd_training_budget': '0',
    'commercial_headcount': 30, 'commercial_salary_level': 3,
    'commercial_training_budget': '0',
    'operations_headcount': 40, 'operations_salary_level': 3,
    'operations_training_budget': '0',
}


def allocations(rd_eu=10, commercial_eu=5, operations_eu=0):
    """Balanced against TALENT: every pool totals its headcount."""
    return [
        {'talent_pool': 'rd', 'hq_count': 50 - rd_eu,
         'market_allocation': {'EU': rd_eu}},
        {'talent_pool': 'commercial', 'hq_count': 30 - commercial_eu,
         'market_allocation': {'EU': commercial_eu}},
        {'talent_pool': 'operations', 'hq_count': 40 - operations_eu,
         'market_allocation': {'EU': operations_eu}},
    ]


def has_cjk(text):
    return any('一' <= ch <= '鿿' for ch in str(text))


def leaves(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from leaves(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from leaves(value)
    elif node is not None:
        yield str(node)


class SectionSaveBase(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'sss-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        self.eu = MarketDefinition.objects.create(
            scenario=self.scenario, name='Europe', code='EU', description='d',
            currency_code='EUR', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        # A market of the scenario the team has NOT entered.
        self.sa = MarketDefinition.objects.create(
            scenario=self.scenario, name='South America', code='SA',
            description='d', currency_code='BRL', exchange_rate_base=1,
            base_growth_rate=0, entry_cost_base=0, tax_rate=0,
            regulatory_difficulty=1, infrastructure_quality=1)
        mode = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='Export', code='EXPORT',
            description='d', capital_requirement=0, control_level=1,
            risk_level=1, local_presence_score=1)
        for market in (self.home, self.eu):
            TeamMarketPresence.objects.create(
                team=self.team, market=market, entry_mode=mode,
                established_round=0, initial_investment=0, status='active')
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now()})
        self.client = self.client_for(self.team)

    def client_for(self, team):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'sss-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'SSS{id(self) % 10000}{Course.objects.count()}',
            course_name='SSS', instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=team.id, is_active=True, enrolled_at=timezone.now())
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def url(self, decision_type=None):
        base = (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/decisions/round/1/')
        return f'{base}{decision_type}/' if decision_type else base

    def patch(self, decision_type, body, language='en'):
        return self.client.patch(self.url(decision_type), body, format='json',
                                 HTTP_ACCEPT_LANGUAGE=language)

    def submission(self):
        return DecisionSubmission.objects.filter(
            team=self.team, round=self.round).first()

    def stored_compliance(self):
        return {row.market.code: row.investment_amount
                for row in ComplianceInvestment.objects.filter(
                    submission__team=self.team).select_related('market')}

    def stored_allocations(self):
        return {row.talent_pool: (row.hq_count, row.market_allocation)
                for row in TalentAllocation.objects.filter(
                    submission__team=self.team)}

    def assert_refused(self, response, key, language, status=400, **values):
        self.assertEqual(response.status_code, status, response.data)
        expected = participant_message(key, language=language, **values)
        sentences = list(leaves(
            {k: v for k, v in response.data.items() if k != 'code'}))
        self.assertIn(expected, sentences, response.data)
        for sentence in sentences:
            self.assertEqual(has_cjk(sentence), language == 'zh-CN', sentence)


class ComplianceInvestmentRouteTests(SectionSaveBase):

    def body(self, amount='1500000'):
        return {'compliance_investments': [
            {'market': self.eu.id, 'investment_amount': amount}]}

    def test_the_section_is_accepted_and_stored(self):
        response = self.patch('compliance-investments', self.body())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.stored_compliance(), {'EU': D('1500000.00')})

    def test_a_reload_reads_the_saved_rows_back(self):
        self.patch('compliance-investments', self.body())
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(row['market'], D(row['investment_amount']))
             for row in response.data['compliance_investments']],
            [(self.eu.id, D('1500000'))])

    def test_a_second_save_replaces_the_first(self):
        self.patch('compliance-investments', self.body('1500000'))
        self.patch('compliance-investments', self.body('250000'))
        self.assertEqual(self.stored_compliance(), {'EU': D('250000.00')})

    def test_an_empty_list_clears_the_section(self):
        self.patch('compliance-investments', self.body())
        response = self.patch('compliance-investments',
                              {'compliance_investments': []})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.stored_compliance(), {})

    def test_the_save_writes_a_decision_audit_event(self):
        before = DecisionAuditEvent.objects.filter(team=self.team).count()
        self.patch('compliance-investments', self.body())
        events = DecisionAuditEvent.objects.filter(team=self.team)
        self.assertEqual(events.count(), before + 1)
        event = events.order_by('-id').first()
        self.assertEqual(event.action, 'save')
        self.assertTrue(event.endpoint.endswith('/compliance-investments/'))
        self.assertEqual(
            event.payload['compliance_investments'][0]['market'], self.eu.id)

    def test_over_the_per_market_maximum_is_refused_in_both_languages(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch('compliance-investments',
                                      self.body('10000001'), language)
                self.assert_refused(response, 'compliance_maximum', language)
        self.assertEqual(self.stored_compliance(), {})

    def test_a_market_the_team_has_not_entered_is_refused(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch('compliance-investments', {
                    'compliance_investments': [
                        {'market': self.sa.id, 'investment_amount': '1000'}],
                }, language)
                self.assert_refused(
                    response, 'compliance_market_inactive', language)
        self.assertEqual(self.stored_compliance(), {})

    def test_one_market_named_twice_is_refused_not_a_server_error(self):
        row = {'market': self.eu.id, 'investment_amount': '1000'}
        response = self.patch('compliance-investments',
                              {'compliance_investments': [row, row]}, 'zh-CN')
        self.assert_refused(response, 'request_incomplete', 'zh-CN')
        self.assertEqual(self.stored_compliance(), {})

    def test_a_refused_payload_leaves_the_stored_rows_alone(self):
        self.patch('compliance-investments', self.body('1500000'))
        self.patch('compliance-investments', self.body('10000001'))
        self.assertEqual(self.stored_compliance(), {'EU': D('1500000.00')})

    def test_the_old_section_name_is_still_unknown(self):
        """The page's former spelling. Pinned so the two cannot drift apart
        again unnoticed: the frontend test pins the page to the key above."""
        response = self.patch('compliance_investments', self.body())
        self.assert_refused(response, 'unknown_decision_type', 'en')


class TalentAllocationRouteTests(SectionSaveBase):

    def save_talent(self, **overrides):
        response = self.patch('talent', {'talent': {**TALENT, **overrides}})
        self.assertEqual(response.status_code, 200, response.data)

    def test_the_section_is_accepted_and_stored(self):
        self.save_talent()
        response = self.patch('talent-allocations',
                              {'talent_allocations': allocations()})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.stored_allocations(), {
            'rd': (40, {'EU': 10}),
            'commercial': (25, {'EU': 5}),
            'operations': (40, {'EU': 0}),
        })

    def test_a_reload_reads_the_saved_rows_back(self):
        self.save_talent()
        self.patch('talent-allocations', {'talent_allocations': allocations()})
        submission = self.client.get(self.url())
        self.assertEqual(
            {row['talent_pool']: (row['hq_count'], row['market_allocation'])
             for row in submission.data['talent_allocations']},
            self.stored_allocations())
        # The endpoint the page actually loads allocations from.
        context = self.client.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/context/talent-allocation/')
        self.assertEqual(context.status_code, 200)
        self.assertEqual(context.data['draft_allocations']['rd'],
                         {'hq_count': 40, 'market_allocation': {'EU': 10}})

    def test_the_save_writes_a_decision_audit_event(self):
        self.save_talent()
        self.patch('talent-allocations', {'talent_allocations': allocations()})
        event = DecisionAuditEvent.objects.filter(
            team=self.team).order_by('-id').first()
        self.assertEqual(event.action, 'save')
        self.assertTrue(event.endpoint.endswith('/talent-allocations/'))

    def test_allocating_before_staffing_is_refused_in_both_languages(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch(
                    'talent-allocations',
                    {'talent_allocations': allocations()}, language)
                self.assert_refused(
                    response, 'talent_decision_required', language)
        self.assertEqual(self.stored_allocations(), {})

    def test_a_total_that_is_not_the_headcount_is_refused(self):
        self.save_talent()
        rows = allocations()
        rows[0]['hq_count'] = 30        # 30 + 10 = 40, headcount 50
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch('talent-allocations',
                                      {'talent_allocations': rows}, language)
                self.assert_refused(response, 'talent_allocation_total',
                                    language, allocated=40, headcount=50)
        self.assertEqual(self.stored_allocations(), {})

    def test_too_few_staff_at_headquarters_is_refused(self):
        self.save_talent()
        rows = allocations(rd_eu=45)    # 5 at HQ, the minimum is 10
        response = self.patch('talent-allocations',
                              {'talent_allocations': rows}, 'zh-CN')
        self.assert_refused(response, 'talent_hq_minimum', 'zh-CN', minimum=10)

    def test_a_market_the_team_has_not_entered_is_refused(self):
        self.save_talent()
        rows = allocations()
        rows[0] = {'talent_pool': 'rd', 'hq_count': 40,
                   'market_allocation': {'SA': 10}}
        response = self.patch('talent-allocations',
                              {'talent_allocations': rows}, 'zh-CN')
        self.assert_refused(response, 'talent_market_inactive', 'zh-CN')

    def test_a_negative_count_cannot_balance_the_total(self):
        """hq 60 and EU -10 totals the headcount; it is not an allocation."""
        self.save_talent()
        rows = allocations()
        rows[0] = {'talent_pool': 'rd', 'hq_count': 60,
                   'market_allocation': {'EU': -10}}
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch('talent-allocations',
                                      {'talent_allocations': rows}, language)
                self.assertEqual(response.status_code, 400, response.data)
                for sentence in leaves(response.data):
                    self.assertEqual(has_cjk(sentence), language == 'zh-CN',
                                     sentence)
        self.assertEqual(self.stored_allocations(), {})

    def test_malformed_market_counts_are_refused_not_a_server_error(self):
        self.save_talent()
        for bad in ({'EU': 'ten'}, {'EU': 2.5}, ['EU'], 'EU', {'EU': True}):
            with self.subTest(market_allocation=bad):
                rows = allocations()
                rows[0]['market_allocation'] = bad
                response = self.patch('talent-allocations',
                                      {'talent_allocations': rows})
                self.assertEqual(response.status_code, 400, response.data)

    def test_one_pool_named_twice_is_refused_not_a_server_error(self):
        self.save_talent()
        rows = allocations()
        response = self.patch('talent-allocations',
                              {'talent_allocations': rows + [rows[0]]})
        self.assert_refused(response, 'request_incomplete', 'en')
        self.assertEqual(self.stored_allocations(), {})

    def test_the_old_section_name_is_still_unknown(self):
        response = self.patch('talent_allocations',
                              {'talent_allocations': allocations()})
        self.assert_refused(response, 'unknown_decision_type', 'en')


class StaffingAndAllocationStayConsistentTests(SectionSaveBase):
    """The allocation must total the headcount, so neither can change first.

    The page sends both in one request when a headcount changes. A staffing
    save that would strand a stored allocation is refused rather than accepted:
    accepting it would leave ten staff paid for and forty deployed.
    """

    def setUp(self):
        super().setUp()
        self.patch('talent', {'talent': TALENT})
        self.patch('talent-allocations', {'talent_allocations': allocations()})

    def rd_headcount(self):
        return DecisionTalent.objects.get(
            submission=self.submission()).rd_headcount

    def test_staffing_and_allocation_change_together(self):
        rows = allocations()
        rows[0] = {'talent_pool': 'rd', 'hq_count': 50,
                   'market_allocation': {'EU': 10}}
        response = self.patch('talent', {
            'talent': {**TALENT, 'rd_headcount': 60},
            'talent_allocations': rows})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.rd_headcount(), 60)
        self.assertEqual(self.stored_allocations()['rd'], (50, {'EU': 10}))

    def test_a_headcount_change_that_strands_the_allocation_is_refused(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch(
                    'talent', {'talent': {**TALENT, 'rd_headcount': 12}},
                    language)
                self.assert_refused(response, 'talent_allocation_total',
                                    language, allocated=50, headcount=12)
        self.assertEqual(self.rd_headcount(), 50)
        self.assertEqual(self.stored_allocations()['rd'], (40, {'EU': 10}))

    def test_a_refused_pair_changes_neither(self):
        rows = allocations()
        rows[0]['hq_count'] = 1
        response = self.patch('talent', {
            'talent': {**TALENT, 'rd_headcount': 60},
            'talent_allocations': rows})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.rd_headcount(), 50)
        self.assertEqual(self.stored_allocations()['rd'], (40, {'EU': 10}))

    def test_staffing_changes_that_keep_the_headcount_are_unaffected(self):
        response = self.patch(
            'talent', {'talent': {**TALENT, 'rd_salary_level': 4}})
        self.assertEqual(response.status_code, 200, response.data)

    def test_the_whole_submission_route_applies_the_same_rule(self):
        """It accepted any allocation at all: nothing gave the serializer the
        submission its rules read."""
        rows = allocations()
        rows[0]['hq_count'] = 1
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.client.put(
                    self.url(), {'talent_allocations': rows}, format='json',
                    HTTP_ACCEPT_LANGUAGE=language)
                self.assert_refused(response, 'talent_allocation_total',
                                    language, allocated=11, headcount=50)
        self.assertEqual(self.stored_allocations()['rd'], (40, {'EU': 10}))

    def test_the_whole_submission_route_still_accepts_a_balanced_one(self):
        response = self.client.put(
            self.url(), {'talent_allocations': allocations(rd_eu=20)},
            format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.stored_allocations()['rd'], (30, {'EU': 20}))


class WholeSubmissionWithoutStaffingTests(SectionSaveBase):

    def test_a_first_save_cannot_carry_an_unchecked_allocation(self):
        """No submission yet, so no staffing decision to total against."""
        response = self.client.post(
            self.url(), {'talent_allocations': allocations()}, format='json',
            HTTP_ACCEPT_LANGUAGE='zh-CN')
        self.assert_refused(response, 'talent_decision_required', 'zh-CN')
        self.assertEqual(self.stored_allocations(), {})

    def test_compliance_market_rule_holds_on_the_whole_submission_route(self):
        response = self.client.post(self.url(), {'compliance_investments': [
            {'market': self.sa.id, 'investment_amount': '1000'}]},
            format='json')
        self.assert_refused(response, 'compliance_market_inactive', 'en')
        self.assertEqual(self.stored_compliance(), {})


class ExistingGuardTests(SectionSaveBase):
    """Every guard on a decision write, on the two sections that had none
    because they had no route."""

    def bodies(self):
        return (
            ('compliance-investments', {'compliance_investments': [
                {'market': self.eu.id, 'investment_amount': '1500000'}]}),
            ('talent-allocations', {'talent_allocations': allocations()}),
        )

    def test_a_locked_submission_refuses_both(self):
        self.patch('talent', {'talent': TALENT})
        DecisionSubmission.objects.filter(pk=self.submission().pk).update(
            status='locked')
        for decision_type, body in self.bodies():
            for language in LANGUAGES:
                with self.subTest(decision_type=decision_type,
                                  language=language):
                    self.assert_refused(
                        self.patch(decision_type, body, language),
                        'submission_locked', language)
        self.assertEqual(self.stored_compliance(), {})
        self.assertEqual(self.stored_allocations(), {})

    def test_a_closed_round_refuses_both(self):
        self.patch('talent', {'talent': TALENT})
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for decision_type, body in self.bodies():
            for language in LANGUAGES:
                with self.subTest(decision_type=decision_type,
                                  language=language):
                    response = self.patch(decision_type, body, language)
                    self.assertEqual(response.status_code, 403, response.data)
                    for sentence in leaves(response.data):
                        self.assertEqual(has_cjk(sentence),
                                         language == 'zh-CN', sentence)
        self.assertEqual(self.stored_compliance(), {})
        self.assertEqual(self.stored_allocations(), {})

    def test_an_instructor_holding_the_round_refuses_both_with_the_code(self):
        """R17: refused fast, with the code the frontend retries on, and
        before the handler runs -- nothing is stored."""
        from unittest.mock import patch as mock_patch
        self.patch('talent', {'talent': TALENT})
        with mock_patch(
                'core.services.competition_locks'
                '.try_lock_game_for_decision_write', return_value=False):
            for decision_type, body in self.bodies():
                for language in LANGUAGES:
                    with self.subTest(decision_type=decision_type,
                                      language=language):
                        response = self.patch(decision_type, body, language)
                        self.assert_refused(response, 'lifecycle_in_progress',
                                            language, status=409)
                        self.assertEqual(response.data['code'],
                                         'lifecycle_in_progress')
        self.assertEqual(self.stored_compliance(), {})
        self.assertEqual(self.stored_allocations(), {})

    def test_another_teams_student_is_refused(self):
        rival = self.client_for(self.rival)
        for decision_type, body in self.bodies():
            with self.subTest(decision_type=decision_type):
                response = rival.patch(self.url(decision_type), body,
                                       format='json')
                self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(self.stored_compliance(), {})

    def test_an_anonymous_caller_is_refused(self):
        from rest_framework.test import APIClient
        for decision_type, body in self.bodies():
            with self.subTest(decision_type=decision_type):
                response = APIClient().patch(self.url(decision_type), body,
                                             format='json')
                self.assertIn(response.status_code, (401, 403))

    def test_both_carry_the_decision_write_throttle(self):
        from core.views.decisions import DecisionPartialUpdateView
        self.assertEqual(DecisionPartialUpdateView.throttle_scope,
                         'decision_write')


class TeamNotesTests(SectionSaveBase):
    """SummaryPage sent the team's notes to the BUDGET section.

    The budget serializer requires its three budgets, so any team that typed a
    note had its lock refused with three "This field is required." -- and the
    note itself was never a field of that section.
    """

    def test_the_former_payload_is_refused_and_would_block_the_lock(self):
        response = self.patch('budget', {'team_notes': 'Hold price in EU.'})
        self.assertEqual(response.status_code, 400, response.data)

    def test_notes_save_through_the_whole_submission_route(self):
        self.patch('budget', {'budget_allocation': {
            'rd_budget': '1000', 'marketing_budget': '1000',
            'strategy_budget': '1000'}})
        response = self.client.post(
            self.url(), {'team_notes': 'Hold price in EU.'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.submission().team_notes, 'Hold price in EU.')
        # ...and nothing else in the submission was disturbed by it.
        self.assertEqual(self.submission().budget_allocation.rd_budget,
                         D('1000.00'))
        reloaded = self.client.get(self.url())
        self.assertEqual(reloaded.data['team_notes'], 'Hold price in EU.')


class ResolvedRoundTests(SectionSaveBase):
    """The saved values are what the engine reads when the round resolves."""

    def resolve(self):
        from core.engine.advance_round import process_round
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})
        process_round(self.game.id)

    def test_the_engine_consumes_what_the_routes_stored(self):
        self.assertEqual(
            self.patch('talent', {'talent': TALENT}).status_code, 200)
        self.assertEqual(self.patch(
            'talent-allocations', {'talent_allocations': allocations(
                rd_eu=10, commercial_eu=5, operations_eu=0)}).status_code, 200)
        self.assertEqual(self.patch('compliance-investments', {
            'compliance_investments': [
                {'market': self.eu.id, 'investment_amount': '2500000'}],
        }).status_code, 200)

        self.resolve()

        record = TeamMarketCompliance.objects.get(
            game=self.game, team=self.team, market=self.eu)
        # strategy_effects._process_compliance: the saved amount, accumulated,
        # on the diminishing-returns curve (default scale 5,000,000):
        # 1 - exp(-0.5) = 0.39.
        self.assertEqual(record.cumulative_investment, D('2500000.00'))
        self.assertEqual(record.compliance_level, D('0.39'))
        # talent._calculate_market_talent_multipliers: ten R&D staff in the
        # market is the full localisation baseline, five commercial is half of
        # it, no operations staff is none -- so the three multipliers must
        # come out in that order, from the rows the route stored.
        self.assertGreater(record.effective_rd_multiplier,
                           record.effective_commercial_multiplier)
        self.assertGreater(record.effective_commercial_multiplier,
                           record.effective_operations_multiplier)

    def test_the_control_without_the_saves(self):
        """Same round, nothing saved: the engine has nothing to read, so the
        assertions above are about the saves and not about the fixture."""
        self.assertEqual(
            self.patch('talent', {'talent': TALENT}).status_code, 200)
        self.resolve()
        record = TeamMarketCompliance.objects.get(
            game=self.game, team=self.team, market=self.eu)
        self.assertEqual(record.cumulative_investment, D('0'))
        self.assertEqual(record.compliance_level, D('0'))
        self.assertEqual(record.effective_rd_multiplier,
                         record.effective_operations_multiplier)


class ManifestTests(SectionSaveBase):
    """The rows the routes write are the rows the input manifest hashes.

    `manifest_sections` already lists both tables, keyed on their
    `unique_together`. The routes replace rows rather than updating them, so a
    re-save gives every row a new primary key; the manifest must not notice.
    """

    def save(self, amount):
        self.patch('talent', {'talent': TALENT})
        self.patch('talent-allocations', {'talent_allocations': allocations()})
        self.patch('compliance-investments', {'compliance_investments': [
            {'market': self.eu.id, 'investment_amount': amount}]})

    def input_body(self):
        from core.services.resolution_manifest import build_input_manifest
        body, _snapshot = build_input_manifest(self.game, self.round)
        return body

    def test_the_saved_rows_are_in_the_input_envelope(self):
        from core.services.manifest_version import MANIFEST_SCHEMA_VERSION
        empty = self.input_body()
        self.save('1500000')
        body = self.input_body()
        self.assertEqual(MANIFEST_SCHEMA_VERSION, 6)
        # Canonicalised: the envelope carries its numbers as strings.
        self.assertEqual(str(body['schema_version']), '6')
        self.assertEqual(len(body['sections']['talent_allocation']), 3)
        self.assertEqual(len(body['sections']['compliance_investment']), 1)
        self.assertIn('1500000', str(body['sections']['compliance_investment']))
        for section in ('talent_allocation', 'compliance_investment'):
            self.assertNotEqual(body['section_digests'][section],
                                empty['section_digests'][section])

    def test_a_re_save_of_the_same_decision_hashes_the_same(self):
        self.save('1500000')
        first = self.input_body()['section_digests']
        self.save('999')
        self.assertNotEqual(
            self.input_body()['section_digests']['compliance_investment'],
            first['compliance_investment'])
        self.save('1500000')
        second = self.input_body()['section_digests']
        for section in ('talent_allocation', 'compliance_investment'):
            self.assertEqual(first[section], second[section])


class SectionNamesAgreeTests(TestCase):
    """The page-side list of sections is the server's `_TYPE_MAP`, exactly.

    The defect was two names the server had never heard of. The frontend
    holds `DECISION_SECTIONS` (src/api/decisionSections.js) and a Jest test
    refuses any page that names a section outside it; this holds that list
    equal to the route's own map, so a section added on one side and not the
    other fails a build rather than a student.
    """

    def test_the_two_lists_are_identical(self):
        import re
        from pathlib import Path
        from core.views.decisions import _TYPE_MAP
        source = (Path(__file__).resolve().parents[3]
                  / 'frontend/globalstrat-frontend/src/api/decisionSections.js'
                  ).read_text(encoding='utf-8')
        body = source[source.index('DECISION_SECTIONS = ['):]
        body = body[:body.index('];')]
        listed = re.findall(r"'([a-z-]+)'", body)
        self.assertEqual(sorted(listed), sorted(_TYPE_MAP))
