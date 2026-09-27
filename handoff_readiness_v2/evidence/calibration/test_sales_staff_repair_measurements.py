import copy
import unittest

from sales_staff_repair_measurements import (
    INTERACTION_LEVELS,
    SALES_LEVELS,
    _curve,
    no_free_win,
)


def _result(revenue, units, income, cash, pi):
    return {
        'cumulative_revenue': revenue,
        'cumulative_units_sold': units,
        'cumulative_net_income': income,
        'final_cash': cash,
        'final_performance_index': pi,
        'final_satisfaction_score': 50,
        'final_total_debt': 0,
        'final_total_equity': 1,
        'final_debt_to_equity': 0,
        'trajectory': [{
            'round': 1, 'revenue': revenue, 'units_sold': units,
            'cash': cash, 'performance_index': pi,
            'satisfaction_score': 50, 'total_debt': 0,
            'total_equity': 1, 'debt_to_equity': 0,
            'lost_demand': 0, 'units_unsold': 0,
        }],
    }


class SalesStaffRepairEvidenceTests(unittest.TestCase):
    def test_policy_grids_include_zero_baseline_and_upper_range(self):
        self.assertEqual(SALES_LEVELS, (
            0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0))
        self.assertEqual(INTERACTION_LEVELS, (0.0, 0.5, 1.0, 1.5))

    def test_no_free_win_distinguishes_commercial_value_from_cost(self):
        points = [
            {'level': 0.0, 'result': _result(100, 10, 20, 20, 50)},
            {'level': 1.0, 'result': _result(150, 15, 15, 15, 52)},
        ]
        finding = no_free_win(points)
        self.assertTrue(finding['positive_staff_commercially_beats_zero'])
        self.assertTrue(finding['positive_staff_pi_beats_zero'])
        self.assertFalse(finding['positive_staff_income_beats_zero'])
        self.assertFalse(finding['zero_staff_dominates_every_positive_point'])

    def test_curve_orders_points_and_uses_named_reference(self):
        zero = {'name': 'zero', 'level': 0.0, 'result': _result(80, 8, 25, 25, 49)}
        one = {'name': 'one', 'level': 1.0, 'result': _result(100, 10, 20, 20, 50)}
        curve = _curve([copy.deepcopy(one), copy.deepcopy(zero)], one)
        self.assertEqual(curve['reference'], 'one')
        self.assertEqual([point['level'] for point in curve['points']], [0.0, 1.0])
        self.assertEqual(
            curve['monotonicity']['cumulative_revenue']['direction'],
            'nondecreasing')


if __name__ == '__main__':
    unittest.main()
