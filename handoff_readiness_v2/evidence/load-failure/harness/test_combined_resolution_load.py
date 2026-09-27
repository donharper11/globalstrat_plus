import importlib.util
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
HARNESS = HERE / 'combined_resolution_load.py'


def load_harness():
    os.environ.setdefault('DB_PASSWORD', 'unit-test-not-used')
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location(
        'combined_resolution_load_under_test', HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SummaryDiagnosticsTests(unittest.TestCase):
    def test_help_does_not_require_database_credentials(self):
        env = dict(os.environ)
        env.pop('DB_PASSWORD', None)
        result = subprocess.run(
            [sys.executable, str(HARNESS), '--help'],
            cwd=HERE, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('{field,margin,smoke}', result.stdout)

    def test_profile_requires_the_disposable_database_runner(self):
        harness = load_harness()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SystemExit, 'run-load-postgres'):
                harness.run('smoke')

    def test_reports_request_classes_phases_and_completion_times(self):
        harness = load_harness()
        shards = [{
            'samples': [
                {'kind': 'refresh', 'status': 200, 'ms': 100.0,
                 'at': 1.0, 'phase': 'steady'},
                {'kind': 'save', 'status': 200, 'ms': 200.0,
                 'at': 2.0, 'phase': 'deadline-burst'},
                {'kind': 'refresh', 'status': 200, 'ms': 300.0,
                 'at': 3.0, 'phase': 'resolution'},
            ],
            'acknowledged': [],
            'refused': [],
            'authenticated': 1,
            'login_failures': [],
        }]

        report = harness.summarize(shards)

        self.assertEqual(
            report['request_class_latency']['refresh']['requests'], 2)
        self.assertEqual(
            report['request_class_latency']['save']['p95_ms'], 200.0)
        self.assertEqual(
            report['phase_latency']['resolution']['request_mix'],
            {'refresh': 1})
        self.assertEqual(
            report['phase_latency']['resolution']['p95_ms'], 300.0)
        self.assertEqual(
            report['slowest_requests'][0]['endpoint_class'],
            'GET decision summary')
        self.assertEqual(
            report['slowest_requests'][0]['completed_at_utc'],
            '1970-01-01T00:00:03+00:00')


if __name__ == '__main__':
    unittest.main()
