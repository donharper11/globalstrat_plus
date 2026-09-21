"""Market research is a paid mechanic.

Research reports were free and unlimited, and `research_expense` was a P&L line
the engine hardcoded to zero. These tests are written against the properties
the mechanic has to hold, one test each.

The load-bearing one is `test_a_purchase_appears_in_both_calculators`: a charge
that reached only the funding rule, or only the engine, is the divergence the
one-calculator rule exists to prevent. It asserts the two agree by running both.
"""
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.engine.utils import _config_cache
from core.models import (DecisionSubmission, Enrollment, Game, Round, Scenario,
                         Team, User)
from core.models.competition_audit import DecisionAuditEvent
from core.models.course import Course, Section
from core.models.research import DecisionResearchPurchase
from core.models.scenario import (FirmStarterProfile, MarketDefinition,
                                  ScenarioConfig)
from core.services import research_catalogue
from core.services.funding_need import decision_outlays

OPENING_CASH = D('1000000')
PRICE = D('50000')


class PaidResearchBase(TestCase):
    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)

        owner = DjangoUser.objects.create(username=f'owner-pr-{id(self)}')
        self.user = User.objects.create(
            username=f'student-pr-{id(self)}', role='student', password_hash='x')
        self.scenario = Scenario.objects.create(
            name=f'Paid research {id(self)}', industry_label='T',
            description='d', starting_cash=OPENING_CASH, num_rounds=4)
        for key in research_catalogue.PRICE_CONFIG_KEYS.values():
            ScenarioConfig.objects.create(
                scenario=self.scenario, config_key=key,
                config_value=str(PRICE), description=key)
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=self.market, starting_cash=OPENING_CASH,
            starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Paid research game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=OPENING_CASH,
            total_equity=OPENING_CASH, shares_outstanding=1000)

        section = Section.objects.create(
            course_id=Course.objects.create(
                course_code=f'PR{id(self) % 100000}', course_name='Research',
                instructor_id=None, is_active=True).course_id,
            section_code='S1', section_name='S1', max_teams=4,
            team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.user.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True, enrolled_at=timezone.now())

        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.user)}')

    def buy_url(self, report_type):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/reports/{report_type}/purchase/')

    def read_url(self, report_type, query=''):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/reports/{report_type}/{query}')

    def submission(self):
        return DecisionSubmission.objects.filter(
            team=self.team, round=self.round).first()


class PurchaseChargeTests(PaidResearchBase):
    def test_a_purchase_appears_in_both_calculators(self):
        """The funding rule and the engine must charge the same outlay."""
        from core.engine.costs import calculate_operating_expenses

        response = self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(response.status_code, 201, response.data)

        submission = self.submission()
        outlays = decision_outlays(self.scenario, self.team, submission, 1)
        self.assertEqual(outlays['research'], PRICE)

        context = _Context(self.scenario, self.game, self.team, 1)
        # Raises AssertionError if the two sides disagree; that guard is the
        # point of the test as much as the equality below.
        calculate_operating_expenses(context)
        self.assertEqual(context.opex[self.team.id]['research_expense'], PRICE)

    def test_a_purchase_is_charged_exactly_once(self):
        self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(
            DecisionResearchPurchase.objects.filter(
                submission=self.submission()).count(), 1)
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE)

    def test_reopening_a_bought_report_charges_nothing(self):
        first = self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(first.status_code, 201)

        # Re-reading it, then asking to buy it again, must not charge twice.
        self.client.get(self.read_url('products'))
        second = self.client.post(self.buy_url('products'), {}, format='json')

        self.assertEqual(second.status_code, 200)
        self.assertIs(second.data['charged'], False)
        self.assertEqual(
            DecisionResearchPurchase.objects.filter(
                submission=self.submission()).count(), 1)
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE)

    def test_a_market_scoped_report_is_bought_per_market(self):
        other = MarketDefinition.objects.create(
            scenario=self.scenario, name='Away', code='AW', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        self.client.post(self.buy_url('segments'), {'market': 'HM'},
                         format='json')
        again = self.client.post(self.buy_url('segments'), {'market': 'HM'},
                                 format='json')
        self.assertIs(again.data['charged'], False)

        second_market = self.client.post(
            self.buy_url('segments'), {'market': other.code}, format='json')
        self.assertEqual(second_market.status_code, 201)
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE * 2)


class AffordabilityTests(PaidResearchBase):
    def test_an_unaffordable_purchase_is_refused_and_delivers_nothing(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        response = self.client.post(self.buy_url('products'), {},
                                    format='json')

        self.assertEqual(response.status_code, 400)
        # Nothing was written: no purchase row, and the report stays locked.
        self.assertFalse(DecisionResearchPurchase.objects.exists())
        report = self.client.get(self.read_url('products'))
        self.assertIs(report.data['purchased'], False)

    def test_the_refusal_is_in_business_language(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        detail = self.client.post(
            self.buy_url('products'), {}, format='json').data['detail']

        self.assertIn('$50,000.00', detail)
        self.assertIn('$1,000.00', detail)
        for leak in ('research_purchases', 'cash_on_hand', 'within_cash',
                     'DecisionResearchPurchase', 'report_type'):
            self.assertNotIn(leak, detail)

    def test_the_refusal_is_localised(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        detail = self.client.post(
            self.buy_url('products'), {}, format='json',
            HTTP_ACCEPT_LANGUAGE='zh-CN').data['detail']

        self.assertIn('承诺支出', detail)
        self.assertIn('可用现金', detail)
        self.assertIn('$50,000.00', detail)
        # The English template must not leak through the Chinese one.
        self.assertNotIn('available cash', detail)


class AuthoredPriceTests(PaidResearchBase):
    def test_the_price_comes_from_the_scenario_not_a_constant(self):
        ScenarioConfig.objects.filter(
            scenario=self.scenario,
            config_key='research_report_price_products',
        ).update(config_value='12345')
        _config_cache.clear()

        self.assertEqual(
            research_catalogue.price_for(self.scenario, 'products'),
            D('12345'))

        response = self.client.post(self.buy_url('products'), {},
                                    format='json')

        self.assertEqual(response.data['price'], '12345')
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), D('12345'))
        self.assertNotEqual(
            D('12345'), research_catalogue.DEFAULT_RESEARCH_PRICE,
            'the test would prove nothing if it used the fallback figure')

    def test_the_price_is_shown_before_buying(self):
        locked = self.client.get(self.read_url('products'))

        self.assertIs(locked.data['purchased'], False)
        self.assertEqual(locked.data['price'], str(PRICE))
        self.assertEqual(locked.data['products'], [])

    def test_the_charged_price_is_frozen_against_later_calibration(self):
        self.client.post(self.buy_url('products'), {}, format='json')
        ScenarioConfig.objects.filter(
            scenario=self.scenario,
            config_key='research_report_price_products',
        ).update(config_value='999999')
        _config_cache.clear()

        # An already-resolved round must not be restated by a price change.
        self.assertEqual(
            research_catalogue.purchase_total(self.submission()), PRICE)


class AnalystQueryPriceTests(PaidResearchBase):
    """V2-094: the analyst query is the one purchase whose price no payload named.

    The reports endpoint names a price per *report type*, and the analyst tab
    never fetches a report, so a team was charged per question without having
    been shown the figure. The tab already loads `research/queries/`; the
    price is published there, from `price_for()` -- the same calculator the
    charge reads -- so the figure shown and the figure charged cannot differ.
    """
    ANALYST_PRICE = D('12345')

    def setUp(self):
        super().setUp()
        ScenarioConfig.objects.filter(
            scenario=self.scenario,
            config_key='research_analyst_query_price',
        ).update(config_value=str(self.ANALYST_PRICE))
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='rag_enabled',
            config_value='true', description='rag')
        ScenarioConfig.objects.create(
            scenario=self.scenario,
            config_key='max_research_queries_per_round',
            config_value='3', description='quota')
        _config_cache.clear()

    def queries_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/queries/')

    def ask_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/research/query/')

    def test_the_analyst_price_is_published_before_any_question_is_asked(self):
        response = self.client.get(self.queries_url())

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['queries'], [])
        offer = response.data['analyst_query']
        self.assertEqual(offer['price'], str(self.ANALYST_PRICE))
        self.assertNotEqual(
            self.ANALYST_PRICE, research_catalogue.DEFAULT_RESEARCH_PRICE,
            'the test would prove nothing if it used the fallback figure')
        # Reading the price is not a purchase.
        self.assertFalse(DecisionResearchPurchase.objects.exists())

    def test_the_quota_published_is_the_quota_enforced(self):
        """The page multiplied a hardcoded 5 by nothing; the rule is authored."""
        offer = self.client.get(self.queries_url()).data['analyst_query']

        self.assertEqual(offer['max_queries_per_round'], 3)
        self.assertEqual(offer['queries_remaining'], 3)

    def test_the_price_shown_is_the_price_charged(self):
        from unittest import mock

        shown = self.client.get(self.queries_url()).data['analyst_query']['price']
        with mock.patch('core.rag.embeddings.get_embedding',
                        return_value=[0.0]), \
                mock.patch('core.rag.embeddings.translate_query_if_needed',
                           side_effect=lambda text, language: text), \
                mock.patch('core.rag.client.search_articles',
                           return_value=[]):
            asked = self.client.post(
                self.ask_url(), {'query': 'How large is the home market?'},
                format='json')

        self.assertEqual(asked.status_code, 200, asked.data)
        charged = DecisionResearchPurchase.objects.get(
            submission=self.submission(),
            report_type=research_catalogue.ANALYST_QUERY)
        self.assertEqual(str(charged.price.normalize()),
                         str(D(shown).normalize()))
        after = self.client.get(self.queries_url()).data['analyst_query']
        self.assertEqual(after['queries_remaining'], 2)


class AuditTests(PaidResearchBase):
    def test_a_purchase_is_audited(self):
        self.client.post(self.buy_url('products'), {}, format='json')

        event = DecisionAuditEvent.objects.filter(
            action='purchase_research_report').first()

        self.assertIsNotNone(event, 'the purchase wrote no audit event')
        self.assertEqual(event.team_id, self.team.id)
        self.assertEqual(event.round_id, self.round.id)
        self.assertEqual(event.payload['report_type'], 'products')
        self.assertTrue(event.payload_sha256)

    def test_a_refused_purchase_writes_no_audit_event(self):
        self.team.cash_on_hand = D('1000')
        self.team.save(update_fields=['cash_on_hand'])

        self.client.post(self.buy_url('products'), {}, format='json')

        self.assertFalse(DecisionAuditEvent.objects.filter(
            action='purchase_research_report').exists())


class PostCloseReadabilityTests(PaidResearchBase):
    def test_a_bought_report_is_still_readable_after_the_round_closes(self):
        self.client.post(self.buy_url('products'), {}, format='json')

        self.round.status = 'processed'
        self.round.closed_at = timezone.now()
        self.round.save(update_fields=['status', 'closed_at'])
        self.game.current_round = 2
        self.game.save(update_fields=['current_round'])
        Round.objects.create(game=self.game, round_number=2, status='open',
                             opened_at=timezone.now())

        # Round 1's report, read back after close, from round 2.
        report = self.client.get(self.read_url('products', '?round=0'))

        self.assertIs(report.data['purchased'], True)

    def test_a_report_bought_in_an_earlier_round_is_not_free_in_a_later_one(self):
        self.client.post(self.buy_url('products'), {}, format='json')

        self.round.status = 'processed'
        self.round.save(update_fields=['status'])
        self.game.current_round = 2
        self.game.save(update_fields=['current_round'])
        Round.objects.create(game=self.game, round_number=2, status='open',
                             opened_at=timezone.now())

        # The current round's edition is a different report and costs again.
        current = self.client.get(self.read_url('products'))

        self.assertIs(current.data['purchased'], False)


class ProfitAndLossTests(PaidResearchBase):
    """`research_expense` was a P&L line the engine hardcoded to zero."""

    def test_the_pnl_and_cash_move_by_the_authored_price(self):
        """Two identical teams; one bought a report. Nothing else differs.

        Asserting against a control team rather than an absolute figure means
        the test measures the charge itself, not the rest of the round.
        """
        from core.engine.costs import calculate_operating_expenses
        from core.engine.financials import generate_financial_statements
        from core.models.results_financials import RoundResultFinancials

        control = Team.objects.create(
            game=self.game, name='Control',
            firm_starter_profile=self.team.firm_starter_profile,
            performance_index=100, cash_on_hand=OPENING_CASH,
            total_equity=OPENING_CASH, shares_outstanding=1000)
        DecisionSubmission.objects.create(
            team=control, round=self.round, status='draft')

        bought = self.client.post(self.buy_url('products'), {}, format='json')
        self.assertEqual(bought.status_code, 201, bought.data)

        context = _Context(self.scenario, self.game, self.team, 1)
        context.teams = [self.team, control]
        calculate_operating_expenses(context)
        generate_financial_statements(context)

        mine = RoundResultFinancials.objects.get(
            game=self.game, team=self.team, round_number=1)
        theirs = RoundResultFinancials.objects.get(
            game=self.game, team=control, round_number=1)

        self.assertEqual(mine.research_expense, PRICE)
        self.assertEqual(theirs.research_expense, D('0'))
        # The report cost the team exactly its authored price, in the P&L...
        self.assertEqual(theirs.operating_income - mine.operating_income, PRICE)
        # ...and in cash, which is the constraint teams actually plan against.
        self.assertEqual(theirs.cash_closing - mine.cash_closing, PRICE)


class RoundGateTests(PaidResearchBase):
    def test_a_closed_round_refuses_the_purchase(self):
        self.round.status = 'closed'
        self.round.save(update_fields=['status'])

        response = self.client.post(self.buy_url('products'), {},
                                    format='json')

        self.assertEqual(response.status_code, 403)
        self.assertFalse(DecisionResearchPurchase.objects.exists())

    def test_an_unknown_report_is_refused(self):
        response = self.client.post(self.buy_url('nonsense'), {},
                                    format='json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(DecisionResearchPurchase.objects.exists())


class _Context:
    """The minimum `calculate_operating_expenses` reads.

    Built by hand rather than by resolving a round, so the test isolates the
    research charge from every other engine input.
    """

    def __init__(self, scenario, game, team, round_number):
        self.scenario = scenario
        self.game = game
        self.teams = [team]
        self.round_number = round_number
        self.market_revenue = {}
        self.opex = {}
        self.log = []
        # What `generate_financial_statements` reads that is not getattr-guarded.
        # Empty: this round has no trading, so the only expense either team
        # carries is admin overhead, and the one difference between them is the
        # report one of them bought.
        self.interest = {}
        self.tax = {}
        self.cogs = {}
        self.logistics = {}
        self.inventory_costs = {}
        self.market_profit = {}
        self.revenue = {}
