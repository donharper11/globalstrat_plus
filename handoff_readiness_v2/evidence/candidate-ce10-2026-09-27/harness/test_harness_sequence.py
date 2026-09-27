"""Regression checks for the CE10 participant correction order."""
import pathlib
import unittest

from leaderboard_contract import validate_leaderboard


HERE = pathlib.Path(__file__).resolve().parent


class CorrectionOrderTests(unittest.TestCase):
    def test_marketing_precedes_summary_affordability_and_lock(self):
        script = (HERE / 'run_round.sh').read_text()
        prepare = script.index('lock_round.py "$1" "$2" "$ROUND" prepare')
        affordability = script.index('follow_the_blocker.py "$1" "$2" "$ROUND"')
        withdrawal = script.index('withdraw_acquisition.py "$1" "$2" "$ROUND"')
        refreshed_affordability = script.index(
            'follow_the_blocker.py "$1" "$2" "$ROUND"', affordability + 1)
        final_lock = script.index(
            'lock_round.py "$1" "$2" "$ROUND" \\\n', refreshed_affordability)
        self.assertLess(prepare, affordability)
        self.assertLess(affordability, withdrawal)
        self.assertLess(withdrawal, refreshed_affordability)
        self.assertLess(refreshed_affordability, final_lock)

    def test_prepare_mode_reads_summary_without_trying_to_lock(self):
        driver = (HERE / 'lock_round.py').read_text()
        prepare = driver.index("if MODE == 'prepare':")
        summary = driver.index("DEC + 'summary/'", prepare)
        stop = driver.index('return R.finish()', summary)
        lock_button = driver.index("page.locator('button'", stop)
        self.assertLess(prepare, summary)
        self.assertLess(summary, stop)
        self.assertLess(stop, lock_button)

    def test_fresh_shortfall_is_added_to_existing_equity(self):
        driver = (HERE / 'follow_the_blocker.py').read_text()
        self.assertIn('equity_target = existing_equity + shortfall', driver)
        self.assertIn("'budget' in blocker.lower()", driver)


class LeaderboardContractTests(unittest.TestCase):
    def test_r32_inactivity_demotion_is_a_valid_published_order(self):
        rows = [
            {'rank': 1, 'performance_index': 64.77,
             'commercially_inactive': False, 'rank_marker': None},
            {'rank': 2, 'performance_index': 52.82,
             'commercially_inactive': False, 'rank_marker': None},
            {'rank': 3, 'performance_index': 47.59,
             'commercially_inactive': False, 'rank_marker': None},
            {'rank': 4, 'performance_index': 53.24,
             'commercially_inactive': True,
             'rank_marker': 'Did not compete'},
        ]
        result = validate_leaderboard(rows, 'Inactive firms rank last.')
        self.assertTrue(all(result.values()), result)

    def test_unmarked_or_unexplained_demotion_is_rejected(self):
        rows = [
            {'rank': 1, 'performance_index': 50,
             'commercially_inactive': False, 'rank_marker': None},
            {'rank': 2, 'performance_index': 60,
             'commercially_inactive': True, 'rank_marker': None},
        ]
        result = validate_leaderboard(rows, None)
        self.assertFalse(result['inactivity_markers_correct'])
        self.assertFalse(result['rank_rule_explained'])

    def test_an_inactive_row_cannot_precede_an_active_row(self):
        rows = [
            {'rank': 1, 'performance_index': 60,
             'commercially_inactive': True,
             'rank_marker': 'Did not compete'},
            {'rank': 2, 'performance_index': 50,
             'commercially_inactive': False, 'rank_marker': None},
        ]
        result = validate_leaderboard(rows, 'Inactive firms rank last.')
        self.assertFalse(result['active_then_inactive'])


class AntdTabTraversalTests(unittest.TestCase):
    def test_overproduction_uses_direct_tabs_and_the_normal_overflow_menu(self):
        driver = (HERE / 'drive_overproduction.py').read_text()
        self.assertIn(':scope > .ant-tabs-nav [role="tab"]', driver)
        self.assertIn('.ant-tabs-nav-more:visible', driver)
        self.assertIn('.ant-tabs-dropdown:visible', driver)
        self.assertIn('if tab.is_visible():', driver)
        self.assertNotIn(
            "page.locator('.ant-tabs > .ant-tabs-nav .ant-tabs-tab')",
            driver)


if __name__ == '__main__':
    unittest.main()
