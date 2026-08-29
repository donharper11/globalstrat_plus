"""The screening analysis must fail loudly when it stops measuring.

Three times in GSP-CRV2-06 an analysis produced confident output while
measuring nothing:

* the first screen compared a probe team against a *different* control team and
  reported all 40 of 40 probes responsive;
* the escalation report kept reading `control` and `probe` keys after the
  result format changed, so every fraction came out `None` and only the
  hard-coded entries escalated;
* the index criterion had no threshold, so arithmetic noise counted as balance.

Each was caught by reading output rather than by a test. These tests use a tiny
synthetic report with known flat, material and below-threshold rows, so the
analysis is checked against answers known in advance — and they fail if it
reads an absent or obsolete key.
"""
import importlib.util
import pathlib
import sys

from django.test import SimpleTestCase

HARNESS = (pathlib.Path(__file__).resolve().parents[3]
           / 'handoff_readiness_v2' / 'evidence' / 'adversarial-balance'
           / 'harness')


def load_report_module():
    spec = importlib.util.spec_from_file_location(
        'screening_report', HARNESS / 'screening_report.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['screening_report'] = module
    spec.loader.exec_module(module)
    return module


def synthetic_report():
    """Known answers: one flat, one material, one below threshold."""
    return {
        'baseline_metrics': {
            'net_income': '-1000000', 'total_revenue': '500000',
            'cash_closing': '2000000', 'index_value': '50.00',
            'satisfaction_score': '0.5000',
        },
        'results': [
            # Flat: identical to baseline in every metric.
            {'applied': True, 'decision_type': 'demo', 'field': 'flat_field',
             'kind': 'numeric', 'label': 'legal_minimum', 'value': '0',
             'moved': False,
             'delta': {'net_income': '0', 'total_revenue': '0',
                       'cash_closing': '0', 'index_value': '0.00'}},
            # Material: 50% of baseline net income.
            {'applied': True, 'decision_type': 'demo', 'field': 'material_field',
             'kind': 'numeric', 'label': 'funded_maximum', 'value': '999',
             'moved': True,
             'delta': {'net_income': '-500000', 'total_revenue': '0',
                       'cash_closing': '0', 'index_value': '0.00'}},
            # Below threshold: 1% of net income, 0.1% of the index — moved, but
            # not material on either scale.
            {'applied': True, 'decision_type': 'demo', 'field': 'tiny_field',
             'kind': 'numeric', 'label': 'funded_maximum', 'value': '1',
             'moved': True,
             'delta': {'net_income': '-10000', 'total_revenue': '0',
                       'cash_closing': '0', 'index_value': '0.05'}},
        ],
    }


class ScreeningAnalysisContractTests(SimpleTestCase):

    def setUp(self):
        self.report = load_report_module()

    def verdicts(self, payload):
        table, _escalate = self.report.classify(payload)
        return {f"{e['decision_type']}.{e['field']}": e for e in table}

    def test_the_known_flat_row_is_flat(self):
        verdicts = self.verdicts(synthetic_report())
        self.assertEqual(verdicts['demo.flat_field']['verdict'],
                         'flat in screening')

    def test_the_known_material_row_escalates(self):
        verdicts = self.verdicts(synthetic_report())
        entry = verdicts['demo.material_field']
        self.assertEqual(entry['verdict'], 'escalate')
        self.assertIn('material response against the subject baseline',
                      entry['escalation_reasons'])

    def test_the_below_threshold_row_does_not_escalate(self):
        """It moved. Moving is not the same as mattering."""
        verdicts = self.verdicts(synthetic_report())
        entry = verdicts['demo.tiny_field']
        self.assertEqual(entry['verdict'], 'flat in screening',
                         f'escalated on {entry["escalation_reasons"]}')

    def test_an_obsolete_key_layout_cannot_pass_silently(self):
        """The exact failure that produced "41 flat, 3 escalate".

        A report in the previous shape — `control` and `probe` blocks, no
        `delta`, no `baseline_metrics` — must not come back all-flat as though
        it had been measured.
        """
        obsolete = {
            'results': [
                {'applied': True, 'decision_type': 'demo', 'field': 'x',
                 'kind': 'numeric', 'label': 'legal_minimum', 'value': '0',
                 'control': {'net_income': '-1000000', 'index_value': '50.00'},
                 'probe': {'net_income': '-2000000', 'index_value': '60.00'}},
            ],
        }
        # The row doubled net income and moved the index ten points. Calling
        # that flat is the one answer certainly wrong, so the analysis must
        # refuse rather than answer.
        with self.assertRaises(self.report.UnreadableScreeningReport):
            self.report.classify(obsolete)

    def test_a_missing_baseline_cannot_be_read_as_no_response(self):
        payload = synthetic_report()
        payload.pop('baseline_metrics')
        with self.assertRaises(self.report.UnreadableScreeningReport):
            self.report.classify(payload)


class AuditGuardRunnerRegressionTests(SimpleTestCase):
    """The test runner must only touch databases it actually created.

    GSP-CRV2-04 made the runner install the append-only audit guards into the
    test database, because migrations are disabled there and a guard that lives
    only in a migration is one no test can observe. It iterated every
    *configured* connection rather than the ones Django built, so a suite of
    nothing but `SimpleTestCase` — which needs no database — died on
    "relation competition_sensitive_read_event does not exist" before a single
    test ran.

    This module is that suite. Its existence is most of the regression; the
    assertions below pin the shape so the loop cannot quietly go back to
    iterating aliases.
    """

    def test_the_runner_installs_only_into_created_connections(self):
        import inspect
        from globalstrat.test_runner import GlobalStratTestRunner
        source = inspect.getsource(GlobalStratTestRunner.setup_databases)
        self.assertIn('created = [entry[0] for entry in config]', source)
        self.assertNotIn('for alias in connections:', source,
                         'the runner is iterating configured aliases again, '
                         'which breaks any suite that needs no database')

    def test_this_suite_needs_no_database(self):
        """If it ever does, the regression above stops being exercised."""
        self.assertEqual(self.databases, set())
