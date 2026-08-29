#!/usr/bin/env python3
"""Run the V2-025 attribution set against a disposable database."""
import datetime, json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
import checksums  # noqa: E402
import inventory_run as R  # noqa: E402

BODY = '''
import sys, json
sys.path.insert(0, {harness!r})
import baseline_gate_body
report = baseline_gate_body.run()
print("---BASELINE-GATE-JSON---")
print(json.dumps(report, default=str))
'''

FIELDS = ('strategy_expense', 'total_revenue', 'capability', 'satisfaction',
          'net_income', 'index_value')


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))
    database = f"gsp_bgate_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---BASELINE-GATE-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the baseline gate did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        (EVIDENCE / 'baseline-competency-gate.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        print(f"\nsubject: {report['subject_team']}")
        print(f"\n{'check':<44}{'result':>8}")
        for name, check in report['checks'].items():
            print(f"  {name:<42}{'PASS' if check['pass'] else 'FAIL':>8}")
            for key, value in check.items():
                if key != 'pass':
                    print(f"      {key}: {value}")
        print(f"\nall checks pass: {report['all_pass']}")
        if report['failed']:
            print(f"FAILED: {report['failed']}")
        print(f"\nwrote {EVIDENCE / 'baseline-competency-gate.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        if not report['all_pass']:
            print('\nThe baseline is not competent; no tournament run using it '
                  'may be accepted as evidence.')
            return 1
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
