"""Prove on the REAL tree that A8 catches the defect that actually shipped.

The selftest proves the assertion can fail against a synthetic fixture. This
proves something narrower and more useful: that it would have caught THIS
defect in THIS repository. `results_page.of_teams` is put back exactly as it
shipped -- referenced by ResultsPage.js, absent from both catalogues -- and the
check must fail naming it, as A8 rather than A9 because the call site passes an
options object and no fallback.

Runs against a temporary COPY of the tree (`--repo`), so the working tree is
never mutated and this can run alongside a build or a jest run. Restoring by
`git checkout` would have been wrong anyway: the fix is not committed yet.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

BASE = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                    '/agent-ad31a78c64885fc47')
CHECKER = BASE / 'backend/scripts/check-participant-strings'
CONFIG = BASE / 'backend/scripts/participant-strings.config.json'

# Everything the config names, and nothing else.
SUBTREES = ('backend/core', 'frontend/globalstrat-frontend/src')


def build_copy(root: pathlib.Path) -> None:
    for subtree in SUBTREES:
        shutil.copytree(BASE / subtree, root / subtree,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def run(root: pathlib.Path):
    proc = subprocess.run(
        [sys.executable, str(CHECKER), '--repo', str(root),
         '--config', str(CONFIG)],
        capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    root = pathlib.Path(tempfile.mkdtemp(prefix='a8-regress-'))
    try:
        build_copy(root)

        code, out = run(root)
        print('1. the tree as it stands, with the fix     -> exit', code)
        for line in out.splitlines():
            if 'check-result' in line or line.startswith('participant') or 'note' in line:
                print('    ', line.strip())
        if code != 0:
            print(out)
            return 1

        # Put the defect back: delete the plural forms just authored.
        loc = root / 'frontend/globalstrat-frontend/src/locales'
        en, zh = loc / 'en.json', loc / 'zh-CN.json'
        en.write_text(
            en.read_text(encoding='utf-8')
            .replace('    "of_teams_one": "of {{count}} team",\n', '')
            .replace('    "of_teams_other": "of {{count}} teams",\n', ''),
            encoding='utf-8')
        zh.write_text(
            zh.read_text(encoding='utf-8')
            .replace('    "of_teams_other": "共 {{count}} 支队伍",\n', ''),
            encoding='utf-8')

        code, out = run(root)
        print('2. with the shipped defect put back        -> exit', code)
        named = [l.strip() for l in out.splitlines() if 'of_teams' in l]
        for line in out.splitlines():
            if 'check-result' in line or 'FAIL' in line:
                print('    ', line.strip())
        for line in named:
            print('    ', line)
        if code != 1:
            print('EXPECTED exit 1 (findings); the check did not catch it')
            return 1
        if not any('A8' in l and 'results_page.of_teams' in l for l in named):
            print('EXPECTED A8 to name results_page.of_teams')
            return 1
        print('')
        print('A8 catches the defect that shipped, and names it.')
        print('The working tree was never modified: this ran on a copy.')
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main())
