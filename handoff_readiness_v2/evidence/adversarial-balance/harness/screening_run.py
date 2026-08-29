#!/usr/bin/env python3
"""Run Stage 2 screening against a disposable database.

`--smoke N` is the cheap development loop: N probes, no evidence written.
Without it the full plan runs and the results are stored.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
import inventory_run as R  # noqa: E402


BODY = '''
import json, sys
sys.path.insert(0, {harness!r})
import screening_body
inventory = json.loads(open({inventory!r}).read())
report = screening_body.run(inventory, max_probes={max_probes})
print("---SCREENING-JSON---")
print(json.dumps(report, default=str))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', type=int, default=None,
                        help='development only: screen this many probes and '
                             'write no evidence')
    parser.add_argument('--keep', action='store_true')
    options = parser.parse_args()

    dirty = subprocess.run(['git', 'status', '--porcelain',
                            '--untracked-files=no'], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if options.smoke is None and dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    database = f'gsp_screen_{stamp}'
    body = BODY.format(harness=str(HERE),
                       inventory=str(EVIDENCE / 'dimension-inventory.json'),
                       max_probes=options.smoke)

    print(f'Creating disposable database {database}')
    created = R.psql('postgres', f'CREATE DATABASE {database}')
    if created.returncode != 0:
        raise SystemExit(created.stderr)
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c', body, timeout=7200)
        if result.returncode != 0:
            print(result.stdout[-4000:])
            print(result.stderr[-4000:])
            raise SystemExit('screening failed')
        print(result.stdout.split('---SCREENING-JSON---')[0][-2000:])
        report = json.loads(
            result.stdout.split('---SCREENING-JSON---', 1)[1].strip())
        report['code_revision'] = revision
        report['working_tree_clean'] = dirty == ''

        if report.get('aborted'):
            print(f"\nABORTED: {report['aborted']}")
            for name, check in report['self_tests'].items():
                if isinstance(check, dict):
                    print(f"  {'ok ' if check['passed'] else 'BAD'} {name}: "
                          f"{check.get('delta')}")
            raise SystemExit(1)

        print(f"\nplanned {report['planned']} | screened {report['screened']} "
              f"| moved {report['moved']} | flat {report['flat']} "
              f"| unreachable {report['unreachable']} "
              f"| {report['elapsed_seconds']}s")
        for decision_type, state in sorted(
                report.get('decision_type_availability', {}).items()):
            if not state['built']:
                print(f"  unreachable: {decision_type} — {state['rule']}")

        if not report['coverage_complete']:
            print(f"REFUSED: {report['not_applied']} dimension(s) were neither "
                  f"screened nor unreachable-with-a-rule, and {report['errors']} "
                  f"errored. A dimension nobody looked at is not a screening "
                  f"result. No evidence written.")
            raise SystemExit(1)
        if not report['discriminating']:
            print('REFUSED: the screen is entirely flat or entirely responsive. '
                  'Either shape means the instrument is not discriminating, so '
                  'no evidence is written.')
            raise SystemExit(1)

        if options.smoke is None:
            (EVIDENCE / 'screening.json').write_text(
                json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
            print(f"wrote {EVIDENCE / 'screening.json'}")
        else:
            print('(smoke run — no evidence written)')
        return 0
    finally:
        if not options.keep:
            R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
            print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
