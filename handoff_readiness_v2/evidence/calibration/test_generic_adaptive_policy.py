import unittest

from generic_adaptive_policy import decide, normalize_policy


PARAMETERS = {
    'initial_production_factor': 1.25,
    'base_buffer': 1.15,
    'stockout_buffer': 1.25,
    'inventory_buffer': 1.02,
    'stockout_sell_through': 0.98,
    'inventory_sell_through': 0.85,
    'max_growth_factor': 1.35,
    'price_up_factor': 1.02,
    'price_down_factor': 0.98,
    'staff_step': 2,
    'max_staff_factor': 1.25,
    'cash_guard_buffer': 1.05,
    'leverage_guard': 3.0,
}


class GenericAdaptivePolicyTests(unittest.TestCase):
    def decision(self, *, prior=None, finances=None):
        return decide(
            baseline_volume=100,
            baseline_price=420,
            baseline_staff=10,
            prior=prior,
            finances=finances or {'cash': 1_000_000, 'debt_to_equity': 1},
            parameters=PARAMETERS,
        )

    def test_policy_schema_is_closed(self):
        self.assertEqual(normalize_policy(PARAMETERS)['base_buffer'], 1.15)
        with self.assertRaisesRegex(ValueError, 'unknown adaptive policy'):
            normalize_policy(dict(PARAMETERS, scenario='media'))
        incomplete = dict(PARAMETERS)
        del incomplete['base_buffer']
        with self.assertRaisesRegex(ValueError, 'missing adaptive policy'):
            normalize_policy(incomplete)

    def test_initial_round_uses_only_baseline_volume(self):
        result = self.decision()
        self.assertEqual(result['production_volume'], 125)
        self.assertEqual(result['price_factor'], 1.0)
        self.assertEqual(result['sales_staff'], 10)
        self.assertEqual(result['signal'], 'initial')

    def test_stockout_uses_lost_demand_and_growth_cap(self):
        result = self.decision(prior={
            'produced': 100, 'sold': 100, 'unsold': 0, 'lost_demand': 500,
        })
        self.assertEqual(result['signal'], 'stockout_with_lost_demand')
        self.assertEqual(result['production_volume'], 125)
        self.assertEqual(result['price_factor'], 1.02)
        self.assertEqual(result['sales_staff'], 10)

    def test_missing_prior_result_keeps_the_baseline_decision(self):
        result = self.decision(prior={'available': False})
        self.assertEqual(result['production_volume'], 100)
        self.assertEqual(result['price_factor'], 1.0)
        self.assertEqual(result['sales_staff'], 10)
        self.assertEqual(result['signal'], 'prior_result_unavailable')

    def test_inventory_response_cuts_output_and_adds_bounded_staff(self):
        result = self.decision(prior={
            'produced': 100, 'sold': 70, 'unsold': 30, 'lost_demand': 10,
        })
        self.assertEqual(result['signal'], 'excess_inventory')
        self.assertEqual(result['production_volume'], 72)
        self.assertEqual(result['price_factor'], 0.98)
        self.assertEqual(result['sales_staff'], 12)

    def test_financial_guard_overrides_growth_and_extra_staff(self):
        result = self.decision(
            prior={'produced': 100, 'sold': 100, 'unsold': 0,
                   'lost_demand': 500},
            finances={'cash': -1, 'debt_to_equity': 1},
        )
        self.assertTrue(result['financial_guard'])
        self.assertEqual(result['production_volume'], 105)
        self.assertEqual(result['sales_staff'], 10)


if __name__ == '__main__':
    unittest.main()
