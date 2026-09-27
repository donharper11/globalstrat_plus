import copy
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import competition_sensitivity_measurements as measurement
import stage1_runtime_replay as replay


def payload(*, lost=0, revenue=(100, 120), pi=(55, 56)):
    team = {'name': 'A', 'starter_profile': 'Profile A'}
    team_rounds = []
    product_rounds = []
    demand_rounds = []
    decisions = []
    for index, round_number in enumerate((1, 2)):
        team_rounds.append({
            'round': round_number, 'team': 'A',
            'total_revenue': str(revenue[index]),
            'net_income': '10', 'cash_closing': str(1000 + index),
            'total_debt': '100', 'total_equity': '900',
            'debt_to_equity': '0.1111', 'financing_cash_flow': '0',
            'strategy_expense': '0', 'share_price': '10',
            'performance_index': str(pi[index]), 'satisfaction_score': '0.5',
            'rank': 1, 'units_produced': '10', 'units_sold': '10',
            'units_unsold': '0',
        })
        product_rounds.append({
            'round': round_number, 'team': 'A', 'units_unsold': '0',
        })
        demand_rounds.append({
            'round': round_number, 'team': 'A',
            'lost_demand': str(lost), 'unconstrained_demand': str(10 + lost),
        })
        decisions.append({
            'round': round_number, 'team': 'A',
            'average_retail_price': '100', 'promotion_budget_total': '20',
            'production_volume_total': 10, 'sales_staff_total': 10,
            'new_debt': '0', 'debt_repayment': '0', 'new_equity': '0',
            'environmental_investment': '0', 'social_investment': '0',
        })
    return {
        'scenario': 'Synthetic', 'home_markets': '', 'teams_requested': 1,
        'policy': 'baseline', 'policy_spec': {}, 'subject_team_index': 0,
        'adaptive_production': True, 'teams': [team], 'rows': [],
        'team_rounds': team_rounds, 'product_rounds': product_rounds,
        'product_demand_rounds': demand_rounds, 'decision_rounds': decisions,
    }


class PolicySpecTests(unittest.TestCase):
    def test_every_authored_probe_uses_supported_nonnegative_fields(self):
        for probes in measurement.POLICY_FAMILIES.values():
            for _name, _level, spec in probes:
                parsed = replay.parse_policy_spec(json.dumps(spec))
                self.assertEqual(set(parsed), set(spec))

    def test_unknown_negative_and_boolean_values_are_rejected(self):
        for raw in ('{"typo": 1}', '{"new_debt": -1}',
                    '{"price_multiplier": true}', '[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                replay.parse_policy_spec(raw)

    def test_required_families_are_bidirectional_or_span_zero_to_cap(self):
        self.assertEqual(set(measurement.POLICY_FAMILIES), {
            'price', 'promotion', 'production', 'sales_staff',
            'financing_net_debt', 'stakeholder_esg_total',
        })
        for family in ('price', 'promotion', 'production', 'sales_staff'):
            levels = [probe[1] for probe in measurement.POLICY_FAMILIES[family]]
            self.assertLess(min(levels), 1)
            self.assertGreater(max(levels), 1)
        financing = [probe[1] for probe in
                     measurement.POLICY_FAMILIES['financing_net_debt']]
        self.assertLess(min(financing), 0)
        self.assertGreater(max(financing), 0)
        esg = [probe[1] for probe in
               measurement.POLICY_FAMILIES['stakeholder_esg_total']]
        self.assertEqual((min(esg), max(esg)), (500_000, 6_000_000))


class AnalysisTests(unittest.TestCase):
    def test_summary_uses_the_whole_horizon_and_final_balance_sheet(self):
        summary = measurement.summarise_team(payload(), 0)
        self.assertEqual(summary['cumulative_revenue'], 220)
        self.assertEqual(summary['cumulative_net_income'], 20)
        self.assertEqual(summary['cumulative_units_sold'], 20)
        self.assertEqual(summary['final_performance_index'], 56)
        self.assertEqual(summary['final_total_debt'], 100)

    def test_identical_output_with_lost_demand_is_cap_masked_not_flat(self):
        baseline = measurement.summarise_team(payload(lost=5), 0)
        observed = measurement.summarise_team(payload(lost=5), 0)
        classified = measurement.classify_effect(observed, baseline)
        self.assertEqual(classified['label'], 'cap_masked_across_horizon')
        self.assertEqual(classified['supply_capped_rounds'], [1, 2])

    def test_changed_first_round_is_responsive(self):
        baseline = measurement.summarise_team(payload(), 0)
        observed_payload = payload(revenue=(110, 130), pi=(56, 57))
        observed = measurement.summarise_team(observed_payload, 0)
        classified = measurement.classify_effect(observed, baseline)
        self.assertEqual(classified['label'], 'responsive_from_round_1')
        self.assertEqual(classified['first_changed_round'], 1)

    def test_monotonicity_reports_nonmonotonic_paths(self):
        points = []
        for level, value in ((0, 1), (1, 3), (2, 2)):
            result = {metric: 0 for metric in measurement.METRICS}
            result['final_performance_index'] = value
            points.append({'level': level, 'result': result})
        self.assertEqual(
            measurement.monotonicity(
                points, 'final_performance_index')['direction'],
            'nonmonotonic')

    def test_determinism_comparison_ignores_database_and_timestamp_only(self):
        first = payload()
        second = copy.deepcopy(first)
        first.update(database='one', generated_at='a')
        second.update(database='two', generated_at='b')
        self.assertEqual(measurement._deterministic_content(first),
                         measurement._deterministic_content(second))


if __name__ == '__main__':
    unittest.main()
