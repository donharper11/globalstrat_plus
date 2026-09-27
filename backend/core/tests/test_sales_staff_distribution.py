"""Regression contracts for sales-staff distribution reach.

The shipped scenarios author a dollar cap for effective distribution
investment.  Staffing must therefore keep affecting demand until that budget
is exhausted or the selected channel reaches full coverage; costs alone must
not continue after an unrelated five-representative ceiling.
"""
from decimal import Decimal as D
from types import SimpleNamespace

from django.test import TestCase

from core.engine.preference_engine import (
    _derive_distribution_coverage,
    distribution_reach,
)
from core.models.scenario import Scenario, ScenarioConfig
from core.services.funding_need import _sales_rep_cost


class SalesStaffDistributionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.scenario = Scenario.objects.create(
            name='Sales staff reach', industry_label='Test',
            description='Distribution reach contract',
            starting_cash=D('1000000'),
        )
        ScenarioConfig.objects.bulk_create([
            ScenarioConfig(
                scenario=cls.scenario,
                config_key='distribution_investment_cap',
                config_value='5000000',
                description='Max effective distribution investment',
            ),
            ScenarioConfig(
                scenario=cls.scenario,
                config_key='sales_rep_cost_per_round',
                config_value='100000',
            ),
        ])

    def test_authored_investment_cap_drives_the_full_staffing_curve(self):
        expected = {
            0: 0.00,
            1: 0.014,
            5: 0.07,
            10: 0.14,
            25: 0.35,
            50: 0.70,
            60: 0.70,
        }
        for count, reach in expected.items():
            with self.subTest(count=count):
                self.assertAlmostEqual(
                    distribution_reach(self.scenario, 'hybrid', count),
                    reach,
                )

    def test_channel_theoretical_reach_is_realised_at_the_authored_cap(self):
        self.assertAlmostEqual(
            distribution_reach(self.scenario, 'mass_retail', 25), 0.45)
        self.assertAlmostEqual(
            distribution_reach(self.scenario, 'mass_retail', 50), 0.9)
        self.assertAlmostEqual(
            distribution_reach(self.scenario, 'selective_retail', 25), 0.3)
        self.assertAlmostEqual(
            distribution_reach(self.scenario, 'selective_retail', 50), 0.6)

    def test_engine_feature_uses_unrounded_reach_deterministically(self):
        decision = SimpleNamespace(
            distribution_strategy='hybrid', sales_team_count=6,
        )
        samples = [
            _derive_distribution_coverage(
                None, None, None, None, decision, self.scenario, 0.0, 10.0,
            )
            for _ in range(20)
        ]
        self.assertTrue(all(sample == samples[0] for sample in samples))
        self.assertAlmostEqual(samples[0], 0.84)

        decision.sales_team_count = 7
        self.assertAlmostEqual(
            _derive_distribution_coverage(
                None, None, None, None, decision, self.scenario, 0.0, 10.0,
            ),
            0.98,
        )

    def test_negative_staffing_cannot_reduce_base_reach(self):
        self.assertEqual(
            distribution_reach(self.scenario, 'hybrid', -10),
            distribution_reach(self.scenario, 'hybrid', 0),
        )

    def test_reach_and_committed_cost_read_the_same_rep_cost(self):
        self.assertEqual(_sales_rep_cost(self.scenario), D('100000'))
        self.assertAlmostEqual(
            distribution_reach(self.scenario, 'hybrid', 10), 0.14)
