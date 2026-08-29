#!/usr/bin/env python3
"""Run the bounded Stage 2 characterisation against a disposable database."""
import datetime, json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
import inventory_run as R  # noqa: E402

BODY = '''
import sys, json
sys.path.insert(0, {harness!r})
import characterise_body
report = characterise_body.run()
print("---CHARACTERISE-JSON---")
print(json.dumps(report, default=str))
'''


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    database = f"gsp_char_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        if result.returncode != 0:
            print(result.stdout[-4000:]); print(result.stderr[-4000:])
            raise SystemExit('characterisation failed')
        report = json.loads(
            result.stdout.split('---CHARACTERISE-JSON---', 1)[1].strip())
        report['code_revision'] = revision
        (EVIDENCE / 'characterisation.json').write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
        print(f"\nbaseline repeatable: {report['baseline_is_repeatable']}")
        print(f"evaluations: {report['evaluations']} in "
              f"{report['elapsed_seconds']}s")
        print(f"wrote {EVIDENCE / 'characterisation.json'}")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
