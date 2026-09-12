"""The participant-language static check runs as part of the backend suite.

GSP-CRV2-12 Stage 5's acceptance criterion is that a *build* fails on a new
participant-facing string that is untranslated or names a model field. The
check itself is `backend/scripts/check-participant-strings`; this is one of
the two places it is enforced, the other being `.github/workflows/
player-language.yml`.

Wiring it into the suite matters because GSP-CRV2-09 runs the integrated
backend suite as the release gate, and a control that only exists in a
workflow file is a control that a local `manage.py test` cannot see.

The check needs no database and no network — it parses the tracked source
tree with `ast` and the standard library only — so it is a `SimpleTestCase`
and costs the suite well under a second.
"""
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK = REPO_ROOT / 'backend/scripts/check-participant-strings'
SELFTEST = REPO_ROOT / 'backend/scripts/check-participant-strings-selftest'


class ParticipantStringGuardTests(SimpleTestCase):

    def test_the_check_is_present_and_executable(self):
        self.assertTrue(CHECK.exists(), f'{CHECK} is missing')
        self.assertTrue(SELFTEST.exists(), f'{SELFTEST} is missing')

    def test_no_participant_string_is_untranslated_or_names_a_field(self):
        result = subprocess.run(
            [sys.executable, str(CHECK), '--repo', str(REPO_ROOT)],
            capture_output=True, text=True)
        self.assertEqual(
            result.returncode, 0,
            'backend/scripts/check-participant-strings failed.\n'
            f'{result.stdout}\n{result.stderr}')
        # Exit 0 over zero examined units would be a vacuous pass; the check
        # exits 2 on that, but assert the receipt line here too so a future
        # narrowing of its scope is visible in this suite rather than silent.
        self.assertIn('check-result name=participant-string-hygiene',
                      result.stdout)
        self.assertNotIn('units=0', result.stdout)
