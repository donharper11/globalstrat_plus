"""W-CE3-04: the served income statement did not add up either.

The page's own gap was W-CE3-03 and is repaired in `incomeStatementRows.js`.
This is the harder half: `operating_income` also subtracts depreciation at 10 %
of plant book value, the tax structure's `annual_maintenance_cost`,
product-retirement cost, and the supply-chain disruption and compliance
enforcement costs -- **none of which is a field of `RoundResultFinancials`**.
So even `gross_profit` minus every expense field the API served differed from
the served `operating_income` by $0.58M to $2.40M for a playing team, and a
team that built a plant could not find its depreciation anywhere.

Two things are served now. `platform_amortization` and
`platform_switch_write_off` are stored columns that nothing published, so they
become lines outright. The five charges with no column are published as one
residual, `other_operating_expense`, computed from the served figures, plus
`other_non_operating_expense` for the tax audit penalty and the realised FX
hedge result below operating income.

Naming the five individually needs five columns on `financials`, which is a
hashed section with no exclusions: that moves `MANIFEST_SCHEMA_VERSION` from 7
to 8 and is a decision for the owner, not a side effect of a presentation
repair. It is stopped here and recorded in the completion report.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models.results_financials import RoundResultFinancials
from core.tests.test_operator_concurrency import build_minimal_game
from core.views.cc15_views import STORED_OPERATING_EXPENSE_FIELDS


class ServedStatementBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'sis-{id(self)}')
        self.team = self.teams[0]
        self.client = self.client_for(self.team)

    def client_for(self, team):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'sis-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'SIS{id(self) % 10000}{Course.objects.count()}',
            course_name='SIS', instructor_id=None, is_active=True)
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

    def write_statement(self, **overrides):
        """A round result carrying every charge, including the unstored ones.

        `operating_income` is written the way `engine/financials` computes it:
        gross profit less every stored expense AND less the charges that have
        no column. That difference is exactly what the served statement had no
        way to show.
        """
        fields = dict(
            gross_revenue=D('20000000'), total_revenue=D('20000000'),
            total_cogs=D('12000000'), gross_profit=D('8000000'),
            rd_expense=D('1000000'), marketing_expense=D('1500000'),
            strategy_expense=D('900000'), research_expense=D('100000'),
            compliance_expense=D('400000'), admin_overhead=D('700000'),
            logistics_tariff_expense=D('350000'),
            inventory_expense=D('250000'),
            platform_amortization=D('200000'),
            platform_switch_write_off=D('50000'),
            interest_expense=D('300000'), tax_expense=D('250000'),
        )
        unstored = overrides.pop('_unstored', D('615289'))
        audit_penalty = overrides.pop('_audit_penalty', D('84711'))
        fields.update(overrides)
        stored = sum(fields[name] for name in STORED_OPERATING_EXPENSE_FIELDS)
        operating_income = fields['gross_profit'] - stored - unstored
        pre_tax = operating_income - fields['interest_expense']
        net_income = pre_tax - fields['tax_expense'] - audit_penalty
        return RoundResultFinancials.objects.create(
            game=self.game, team=self.team, round_number=1,
            operating_income=operating_income, pre_tax_income=pre_tax,
            net_income=net_income, **fields)

    def served(self):
        response = self.client.get(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/financial-reports/history/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['rounds'][0]


class TheServedStatementIsCompleteTests(ServedStatementBase):

    def test_the_stored_columns_nothing_published_are_published(self):
        self.write_statement()

        row = self.served()

        self.assertEqual(row['platform_amortization'], 200000.0)
        self.assertEqual(row['platform_switch_write_off'], 50000.0)

    def test_gross_profit_less_every_served_line_is_operating_income(self):
        self.write_statement()

        row = self.served()
        served = sum(D(str(row[name]))
                     for name in STORED_OPERATING_EXPENSE_FIELDS)
        served += D(str(row['other_operating_expense']))

        self.assertEqual(D(str(row['gross_profit'])) - served,
                         D(str(row['operating_income'])))

    def test_the_residual_is_exactly_the_charge_with_no_column(self):
        self.write_statement()

        row = self.served()

        self.assertEqual(row['other_operating_expense'], 615289.0)

    def test_operating_income_less_every_served_line_is_net_income(self):
        self.write_statement()

        row = self.served()

        self.assertEqual(
            D(str(row['operating_income']))
            - D(str(row['interest_expense']))
            - D(str(row['tax_expense']))
            - D(str(row['other_non_operating_expense'])),
            D(str(row['net_income'])))

    def test_the_below_the_line_residual_is_the_audit_penalty(self):
        self.write_statement()

        self.assertEqual(self.served()['other_non_operating_expense'],
                         84711.0)

    def test_a_round_with_no_unstored_charge_shows_a_zero_residual(self):
        self.write_statement(_unstored=D('0'), _audit_penalty=D('0'))

        row = self.served()

        self.assertEqual(row['other_operating_expense'], 0.0)
        self.assertEqual(row['other_non_operating_expense'], 0.0)

    def test_a_hedge_gain_reads_as_a_negative_charge_rather_than_vanishing(self):
        """`fx_hedge_pnl` lifts pre-tax income; the residual must carry it."""
        self.write_statement(_audit_penalty=D('-120000'))

        self.assertEqual(self.served()['other_non_operating_expense'],
                         -120000.0)


class TheHashedSectionIsUnchangedTests(ServedStatementBase):
    """The repair is served-only. It must not have grown a column.

    Naming depreciation, tax-structure maintenance, product retirement,
    supply-chain disruption and compliance enforcement individually would
    require five, and `financials` is hashed field-for-field.
    """

    def test_no_new_column_on_the_hashed_financials_section(self):
        from core.services.manifest_version import MANIFEST_SCHEMA_VERSION

        names = {f.name for f in RoundResultFinancials._meta.get_fields()}

        self.assertNotIn('depreciation', names)
        self.assertNotIn('other_operating_expense', names)
        self.assertEqual(MANIFEST_SCHEMA_VERSION, 7)
