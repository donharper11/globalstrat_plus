"""Regression checks for the CE10 participant correction order."""
import pathlib
import unittest


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


if __name__ == '__main__':
    unittest.main()
