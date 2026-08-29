#!/usr/bin/env python3
"""Run the two candidate rule probes against a disposable database.

Measurement only. Neither probe changes a scoring formula: a confirmed
rules-sensitive finding earns a disposition request, not a quiet edit.
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
import inventory_run as R  # noqa: E402

BODY = '''
import sys
sys.path.insert(0, {harness!r})
exec(open({body!r}).read())
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep', action='store_true')
    options = parser.parse_args()

    dirty = subprocess.run(['git', 'status', '--porcelain',
                            '--untracked-files=no'], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    database = f"gsp_rules_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    created = R.psql('postgres', f'CREATE DATABASE {database}')
    if created.returncode != 0:
        raise SystemExit(created.stderr)
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c', BODY.format(
            harness=str(HERE), body=str(HERE / 'rule_probe_body.py')),
            timeout=3600)
        if result.returncode != 0:
            print(result.stdout[-4000:])
            print(result.stderr[-4000:])
            raise SystemExit('rule probes failed')
        report = json.loads(
            result.stdout.split('---RULE-PROBE-JSON---', 1)[1].strip())
        report['code_revision'] = revision
        (EVIDENCE / 'rule-probes.json').write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')

        cap = report['capability_ratio']
        one = report['one_unit_bypass']
        print(f"\nbaseline repeatable: {report['baseline_is_repeatable']}")
        print('\n--- A. $1 R&D budget / $1 R&D spend ---')
        print(f"  {cap['question']}")
        print(f"  baseline index {cap['baseline']['index_value']} "
              f"score {cap['baseline']['satisfaction_score']} "
              f"net {cap['baseline']['net_income']}")
        print(f"  probe    index {cap['probe']['index_value']} "
              f"score {cap['probe']['satisfaction_score']} "
              f"net {cap['probe']['net_income']}")
        print(f"  delta    index {cap['delta']['index_value']} "
              f"score {cap['delta']['satisfaction_score']} "
              f"net {cap['delta']['net_income']}")
        print('\n--- B. one unit of revenue ---')
        print(f"  {one['question']}")
        for label in ('silent', 'one_unit'):
            row = one[label]
            print(f"  {label:9} revenue {row['total_revenue']} "
                  f"index {row['index_value']} score {row['satisfaction_score']}")
        print(f"  delta     index {one['delta_one_unit_vs_silent']['index_value']} "
              f"score {one['delta_one_unit_vs_silent']['satisfaction_score']}")
        print(f"\nwrote {EVIDENCE / 'rule-probes.json'}")
        return 0
    finally:
        if not options.keep:
            R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
            print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
