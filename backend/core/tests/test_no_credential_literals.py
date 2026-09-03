"""No tracked file may carry a credential as a literal fallback.

`no-committed-secrets` runs gitleaks with its default ruleset, and that ruleset
did not flag the one credential in this repository that mattered. The shape it
misses is an environment lookup with a literal default:

    'PASSWORD': os.environ.get('DB_PASSWORD', '<the live password>')

which reads as configuration rather than as an assigned secret. The scanner had
a 100% miss rate on it while reporting four findings that were all benign, and
it is now *blocking* and green -- a stronger claim than the report-only version
made, on the same detection (V2-048).

Upstream `aide-checks` generates its gitleaks config with `useDefault = true`
and a path allowlist, with no extension point for extra rules, so this lives
here rather than as a fork of a rev-pinned vendored tool. Adding the rule
upstream would be better and is recorded as such; this closes the hole in the
meantime, and it is the repository's own claim to keep either way.
"""
import ast
import pathlib
import re
import subprocess

from django.test import SimpleTestCase

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

# Names whose value is a credential. Matched case-insensitively against the
# environment variable being read.
CREDENTIAL_NAMES = re.compile(
    r'(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|CREDENTIAL)',
    re.IGNORECASE)

# A default that is not a secret: empty, a placeholder, or a value the project
# already marks as insecure and refuses to boot with in production.
BENIGN = re.compile(
    r'^$|^(none|null|changeme|placeholder|xxx+|todo|test|dummy|example)$'
    r'|^django-insecure-', re.IGNORECASE)


# Pinned exceptions, each to one file:line:variable, each with a reason.
#
# Pinned rather than path- or name-based, and deliberately brittle: if the line
# moves the exception stops matching and the finding returns to be re-judged.
# An allowlist nobody has to re-justify is how a check stops meaning anything.
ALLOWED = {
    ('handoff_readiness_v2/narrative_restart_drill.py', 116, 'DASHSCOPE_API_KEY'):
        "Fixture value 'drill-key' for the narrative restart drill. The same "
        "dict points DASHSCOPE_COMPATIBLE_URL at a local stall server on "
        "127.0.0.1, so the key is never sent anywhere; a real DashScope key is "
        "'sk-' plus 32 hex and this is nine characters. Read and confirmed "
        "2026-09-03.",
}


def _tracked_python_files():
    out = subprocess.run(['git', '-C', str(REPO_ROOT), 'ls-files', '-z', '*.py'],
                         capture_output=True, text=True).stdout
    return sorted(p for p in out.split('\0') if p)


class CredentialLiteralTests(SimpleTestCase):

    def test_no_environment_lookup_falls_back_to_a_literal_credential(self):
        offenders = []
        for rel in _tracked_python_files():
            path = REPO_ROOT / rel
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                # os.environ.get(NAME, default) / os.getenv(NAME, default)
                if isinstance(func, ast.Attribute) and func.attr in ('get', 'getenv'):
                    if len(node.args) < 2:
                        continue
                    name, default = node.args[0], node.args[1]
                    if not (isinstance(name, ast.Constant)
                            and isinstance(name.value, str)):
                        continue
                    if not CREDENTIAL_NAMES.search(name.value):
                        continue
                    if not (isinstance(default, ast.Constant)
                            and isinstance(default.value, str)):
                        continue
                    if BENIGN.match(default.value):
                        continue
                    if (rel, node.lineno, name.value) in ALLOWED:
                        continue
                    offenders.append(f'{rel}:{node.lineno} '
                                     f'{name.value} has a literal default')
        self.assertFalse(offenders, (
            'A credential must not have a literal fallback in tracked source. '
            'The value is never printed here; look at the line:\n'
            + '\n'.join(offenders)))

    def test_the_check_recognises_the_shape_it_exists_for(self):
        """A control: the detector must fire on the V2-048 line as it was."""
        sample = ("import os\n"
                  "DATABASES = {'default': {'PASSWORD': "
                  "os.environ.get('DB_PASSWORD', 'a-real-looking-password')}}\n")
        tree = ast.parse(sample)
        found = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ('get', 'getenv')
                    and len(node.args) == 2
                    and isinstance(node.args[0], ast.Constant)
                    and CREDENTIAL_NAMES.search(node.args[0].value)
                    and isinstance(node.args[1], ast.Constant)
                    and not BENIGN.match(node.args[1].value)):
                found.append(node.args[0].value)
        self.assertEqual(found, ['DB_PASSWORD'])

    def test_every_pinned_exception_still_points_at_what_it_describes(self):
        """A stale pin is a hole nobody is looking at."""
        stale = []
        for (rel, lineno, var), reason in ALLOWED.items():
            self.assertTrue(reason.strip(), f'{rel}:{lineno} has no reason')
            path = REPO_ROOT / rel
            if not path.exists():
                stale.append(f'{rel} no longer exists')
                continue
            lines = path.read_text(encoding='utf-8').splitlines()
            if lineno > len(lines) or var not in lines[lineno - 1]:
                stale.append(f'{rel}:{lineno} no longer mentions {var}')
        self.assertFalse(stale, (
            'A pinned exception no longer matches the line it was written '
            'for. Re-judge it rather than moving the pin:\n' + '\n'.join(stale)))

    def test_a_benign_default_is_not_reported(self):
        """Empty and explicitly-insecure placeholders must not be findings."""
        sample = ("import os\n"
                  "a = os.environ.get('DB_PASSWORD', '')\n"
                  "b = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-x')\n")
        tree = ast.parse(sample)
        found = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ('get', 'getenv')
                    and len(node.args) == 2
                    and isinstance(node.args[0], ast.Constant)
                    and CREDENTIAL_NAMES.search(node.args[0].value)
                    and isinstance(node.args[1], ast.Constant)
                    and not BENIGN.match(node.args[1].value)):
                found.append(node.args[0].value)
        self.assertEqual(found, [])
