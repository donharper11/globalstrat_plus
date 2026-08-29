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
import v2_025_attribution_body
report = v2_025_attribution_body.run()
print("---V2025-ATTRIBUTION-JSON---")
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
    database = f"gsp_v2025_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---V2025-ATTRIBUTION-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the attribution set did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        if not report['baseline_is_repeatable']:
            raise SystemExit('REFUSED: the baseline is not exactly repeatable')
        unreached = [name for name, arm in report['arms'].items()
                     if not arm['reached_scoring_row']]
        if unreached:
            raise SystemExit(
                f'REFUSED: these mutations did not reach the scoring row and '
                f'their results mean nothing: {unreached}')

        (EVIDENCE / 'v2-025-attribution.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        base = report['baseline']
        print(f"\nsubject  : {report['subject_team']}   identity "
              f"{report['identity']}")
        print(f"baseline : " + '  '.join(
            f'{f}={base.get(f)}' for f in FIELDS))
        print(f"evaluations: {report['evaluations']} in "
              f"{report['elapsed_seconds']}s")
        print(f"\n{'arm':<28}" + ''.join(f'{f[:12]:>15}' for f in FIELDS)
              + '  moved')
        for name, arm in report['arms'].items():
            d = arm['delta']
            cells = ''
            for f in FIELDS:
                v = d.get(f)
                cells += f'{(v if v is not None else "-"):>15}'
            print(f'  {name:<26}{cells}  {arm["changed_anything"]}')
        print(f"\nevery mutation reached the scoring row: "
              f"{report['all_mutations_reached_the_row']}")
        print(f"\nwrote {EVIDENCE / 'v2-025-attribution.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
