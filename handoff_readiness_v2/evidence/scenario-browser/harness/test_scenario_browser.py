import pathlib
import tempfile
import unittest

import scenario_browser as harness


class ScenarioBrowserCliTests(unittest.TestCase):
    def test_consumer_electronics_remains_the_default(self):
        options = harness.build_parser().parse_args([])
        self.assertEqual(options.scenario, 'consumer_electronics_2026')

    def test_media_and_clean_energy_accept_explicit_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for slug in ('media_entertainment_2026',
                         'clean_energy_tech_2026'):
                options = harness.build_parser().parse_args([
                    '--scenario', slug,
                    '--worktree', str(root / 'candidate'),
                    '--runtime', str(root / slug),
                    '--candidate-revision', '49b547fd',
                    '--dry-run',
                ])
                config = harness.resolved_config(options)
                self.assertEqual(config['scenario'], slug)
                self.assertEqual(config['languages'], ['en', 'zh-CN'])
                self.assertEqual(config['candidate_revision'], '49b547fd')
                self.assertTrue(config['runtime'].endswith(slug))

    def test_scenario_files_are_explicit_and_distinct(self):
        files = [row['file'] for row in harness.SCENARIOS.values()]
        self.assertEqual(len(files), len(set(files)))
        self.assertTrue(all(path.startswith('scenarios/') for path in files))


if __name__ == '__main__':
    unittest.main()
