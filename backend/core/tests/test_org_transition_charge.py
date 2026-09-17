"""R36 / V2-088: the organisational-structure charge is booked by the engine.

`cc32b_views` used to do `team.cash_on_hand -= transition_cost; team.save()` at
request time. The money left the business at click time and **existed in no
calculator**: not `funding_need.decision_outlays`, not
`rd_costs.budget_assessment`, not the engine. So a team's own committed-spend,
projected-cash and Finance figures ignored money that had already gone, the
equity funding rule never counted it, and no path restored it -- reopening a
round left the cash spent while the decision it paid for could be changed
again.

R36 moves the charge into resolution, where it is booked with every other
outlay. These tests are written against the properties that move has to hold,
one test each.

The load-bearing one is `test_the_charge_appears_in_both_calculators`. A charge
that reaches only the funding rule, or only the engine, is precisely the
divergence V2-037/V2-038 consolidated the budget rule to end; it asserts the
two agree by running both, and the parity assertion inside
`calculate_operating_expenses` is as much the point as the equality itself.

Every test here fails against the pre-R36 tree: there, the switch moved cash
immediately and `decision_outlays` had no `org_structure` line at all.
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
from core.models.cc32b_models import (OrganizationalStructureType,
                                      TeamOrganizationalStructure)
from core.models.course import Course, Section
from core.models.scenario import FirmStarterProfile, MarketDefinition
from core.services.funding_need import decision_outlays, org_transition_charge
from core.services.rd_costs import budget_assessment

OPENING_CASH = D('10000000')
TRANSITION_COST = D('2500000')


class _Context:
    """The minimum the cost and financial steps read.

    Built by hand rather than by resolving a round, so these tests isolate the
    structure charge from every other engine input. Modelled on the harness
    `test_paid_research` uses for the same reason.
    """

    def __init__(self, scenario, game, teams, round_number):
        self.scenario = scenario
        self.game = game
        self.teams = list(teams)
        self.round_number = round_number
        self.market_revenue = {}
        self.opex = {}
        self.log = []
        self.interest = {}
        self.tax = {}
        self.cogs = {}
        self.logistics = {}
        self.inventory_costs = {}
        self.market_profit = {}
        self.revenue = {}


class OrgTransitionBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)

        owner = DjangoUser.objects.create(username=f'owner-org-{id(self)}')
        self.user = User.objects.create(
            username=f'student-org-{id(self)}', role='student',
            password_hash='x')
        self.scenario = Scenario.objects.create(
            name=f'Org transition {id(self)}', industry_label='T',
            description='d', starting_cash=OPENING_CASH, num_rounds=4)
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
            scenario=self.scenario, name='Org transition game',
            current_round=1, status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now(),
            deadline=timezone.now() + timezone.timedelta(hours=4))
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=OPENING_CASH,
            total_equity=OPENING_CASH, shares_outstanding=1000)
        self.control = Team.objects.create(
            game=self.game, name='Control', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=OPENING_CASH,
            total_equity=OPENING_CASH, shares_outstanding=1000)

        self.centralized = OrganizationalStructureType.objects.create(
            scenario=self.scenario, code='centralized', name='Centralized',
            description='d', base_overhead_per_round=D('0'),
            per_market_coordination_cost=D('0'), transition_cost=D('0'),
            transition_disruption_rounds=0, display_order=1)
        self.matrix = OrganizationalStructureType.objects.create(
            scenario=self.scenario, code='matrix', name='Matrix',
            description='d', base_overhead_per_round=D('0'),
            per_market_coordination_cost=D('0'),
            transition_cost=TRANSITION_COST,
            transition_disruption_rounds=0, display_order=2)

        section = Section.objects.create(
            course_id=Course.objects.create(
                course_code=f'OT{id(self) % 100000}', course_name='Org',
                instructor_id=None, is_active=True).course_id,
            section_code='S1', section_name='S1', max_teams=4,
            team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.user.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True, enrolled_at=timezone.now())

        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.user)}')

    # -- helpers ------------------------------------------------------------

    @property
    def url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/context/org-structure/')

    def switch_to(self, structure):
        return self.client.post(
            self.url, {'structure_id': structure.id}, format='json')

    def switch_via_api(self):
        """Put the team on `centralized`, then switch it to `matrix`."""
        TeamOrganizationalStructure.objects.update_or_create(
            game=self.game, team=self.team,
            defaults={'current_structure': self.centralized,
                      'adopted_round': 0})
        response = self.switch_to(self.matrix)
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def submission(self, team=None):
        return DecisionSubmission.objects.filter(
            team=team or self.team, round=self.round).first()

    def cash(self, team):
        team.refresh_from_db()
        return team.cash_on_hand


class ChargeTimingTests(OrgTransitionBase):

    def test_switching_moves_no_cash_at_request_time(self):
        """The defect itself: cash used to leave the business on the click."""
        self.switch_via_api()

        self.assertEqual(self.cash(self.team), OPENING_CASH)

    def test_the_switch_itself_is_recorded(self):
        """Moving the charge must not lose the decision that earns it."""
        self.switch_via_api()

        org = TeamOrganizationalStructure.objects.get(
            game=self.game, team=self.team)
        self.assertEqual(org.current_structure_id, self.matrix.id)
        self.assertEqual(org.transitioning_from_id, self.centralized.id)
        self.assertEqual(org.adopted_round, 1)

    def test_the_audit_record_stays_as_it_was(self):
        """R34: the explanation lives in the audit trail, unchanged by R36."""
        from core.models.competition_audit import DecisionAuditEvent

        self.switch_via_api()

        self.assertTrue(DecisionAuditEvent.objects.filter(
            team=self.team, action='change_org_structure').exists())

    def test_it_moves_cash_only_at_resolution(self):
        """Against a control team that did not switch, in cash and in the P&L."""
        from core.engine.costs import calculate_operating_expenses
        from core.engine.financials import generate_financial_statements
        from core.models.results_financials import RoundResultFinancials

        self.switch_via_api()

        context = _Context(self.scenario, self.game,
                           [self.team, self.control], 1)
        calculate_operating_expenses(context)
        generate_financial_statements(context)

        mine = RoundResultFinancials.objects.get(
            game=self.game, team=self.team, round_number=1)
        theirs = RoundResultFinancials.objects.get(
            game=self.game, team=self.control, round_number=1)

        self.assertEqual(theirs.operating_income - mine.operating_income,
                         TRANSITION_COST)
        self.assertEqual(theirs.cash_closing - mine.cash_closing,
                         TRANSITION_COST)

    def test_a_switch_made_in_an_earlier_round_is_not_charged_again(self):
        """The charge belongs to the round the switch was made in."""
        self.switch_via_api()

        self.assertEqual(org_transition_charge(self.team, 1), TRANSITION_COST)
        self.assertEqual(org_transition_charge(self.team, 2), D('0'))

    def test_resolving_the_same_round_twice_charges_the_same_amount(self):
        """Derived from the stored switch, so it is idempotent, not cumulative."""
        self.switch_via_api()

        first = org_transition_charge(self.team, 1)
        second = org_transition_charge(self.team, 1)
        self.assertEqual(first, TRANSITION_COST)
        self.assertEqual(second, TRANSITION_COST)

    def test_a_round_with_no_switch_costs_nothing(self):
        self.assertEqual(org_transition_charge(self.team, 1), D('0'))
        self.assertEqual(org_transition_charge(self.control, 1), D('0'))


class OneCalculatorTests(OrgTransitionBase):

    def test_the_charge_appears_in_both_calculators(self):
        """The funding rule and the engine must charge the same outlay.

        `calculate_operating_expenses` raises `AssertionError` if
        `decision_outlays` and the engine's own lines disagree, and R36 widened
        that assertion to cover this line. The guard firing is as much the
        point of this test as the equality below.
        """
        from core.engine.costs import calculate_operating_expenses

        self.switch_via_api()
        submission = self.submission()
        self.assertIsNotNone(submission)

        outlays = decision_outlays(self.scenario, self.team, submission, 1)
        self.assertEqual(outlays['org_structure'], TRANSITION_COST)

        context = _Context(self.scenario, self.game, [self.team], 1)
        calculate_operating_expenses(context)
        self.assertEqual(
            context.opex[self.team.id]['strategy_expense'], TRANSITION_COST)

    def test_the_parity_assertion_covers_the_new_line(self):
        """Enforced, not merely satisfied.

        If the engine booked the switch and `decision_outlays` did not, the
        round has to stop rather than resolve with the two sides pricing
        different things. Patching the shared calculator to forget the line is
        how that is demonstrated without waiting for a future edit to make the
        mistake for real.
        """
        from unittest.mock import patch

        from core.engine.costs import calculate_operating_expenses

        self.switch_via_api()
        context = _Context(self.scenario, self.game, [self.team], 1)

        def forgetful(*args, **kwargs):
            lines = decision_outlays(*args, **kwargs)
            lines['org_structure'] = D('0')
            return lines

        with patch('core.services.funding_need.decision_outlays', forgetful):
            with self.assertRaisesRegex(AssertionError, 'decision_outlays'):
                calculate_operating_expenses(context)

    def test_committed_spend_includes_it(self):
        """The team's own spending figure must show money it has committed."""
        self.switch_via_api()

        assessment = budget_assessment(self.submission(), self.team)
        self.assertEqual(D(assessment['lines']['org_transition']),
                         TRANSITION_COST)
        self.assertEqual(D(assessment['committed_total']), TRANSITION_COST)

    def test_the_equity_funding_rule_counts_it(self):
        """V2-024's eligible uses include every decision-driven outlay."""
        from core.services import funding_need

        self.switch_via_api()
        assessment = funding_need.funding_requirement(
            self.scenario, self.team, self.submission(), 1)

        self.assertEqual(D(assessment['outlays']['org_structure']),
                         TRANSITION_COST)
        self.assertEqual(D(assessment['eligible_uses']), TRANSITION_COST)


class AffordabilityTests(OrgTransitionBase):

    def test_an_unaffordable_switch_is_refused(self):
        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=D('1000'))
        self.team.refresh_from_db()
        TeamOrganizationalStructure.objects.update_or_create(
            game=self.game, team=self.team,
            defaults={'current_structure': self.centralized,
                      'adopted_round': 0})

        response = self.switch_to(self.matrix)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('Insufficient cash', response.data['error'])

    def test_a_refused_switch_leaves_no_switch_behind(self):
        """The refusal rolls the structure change back with it."""
        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=D('1000'))
        self.team.refresh_from_db()
        TeamOrganizationalStructure.objects.update_or_create(
            game=self.game, team=self.team,
            defaults={'current_structure': self.centralized,
                      'adopted_round': 0})

        self.switch_to(self.matrix)

        org = TeamOrganizationalStructure.objects.get(
            game=self.game, team=self.team)
        self.assertEqual(org.current_structure_id, self.centralized.id)
        self.assertIsNone(org.transitioning_from_id)
        self.assertEqual(self.cash(self.team), D('1000'))
        self.assertEqual(org_transition_charge(self.team, 1), D('0'))


class ReopenTests(OrgTransitionBase):

    def test_reopening_the_round_has_nothing_to_unwind(self):
        """The money never moved, so there is nothing to give back.

        This is the shape of the repair rather than an extra mechanism: the
        old path took cash at click time and no reopen path restored it --
        `round_control.py`, `advance_round.py` and `lifecycle.py` contain no
        `cash_on_hand` write at all. Charging at resolution makes an unresolved
        round cost nothing by construction.
        """
        self.switch_via_api()
        self.assertEqual(self.cash(self.team), OPENING_CASH)

        self.round.status = 'closed'
        self.round.save(update_fields=['status'])
        self.round.status = 'open'
        self.round.save(update_fields=['status'])

        self.assertEqual(self.cash(self.team), OPENING_CASH)

    def test_undoing_the_decision_removes_the_charge(self):
        """It unwinds as any other decision-driven outlay does: with the row."""
        self.switch_via_api()
        self.assertEqual(
            decision_outlays(self.scenario, self.team, self.submission(),
                             1)['org_structure'], TRANSITION_COST)

        org = TeamOrganizationalStructure.objects.get(
            game=self.game, team=self.team)
        org.current_structure = self.centralized
        org.transitioning_from = None
        org.adopted_round = 0
        org.save()

        self.assertEqual(
            decision_outlays(self.scenario, self.team, self.submission(),
                             1)['org_structure'], D('0'))
