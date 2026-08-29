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
import v2_025_recheck_body
report = v2_025_recheck_body.run()
print("---V2025-RECHECK-JSON---")
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
    database = f"gsp_v25rc_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---V2025-RECHECK-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the recheck did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        (EVIDENCE / 'v2-025-recheck.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        print(f"\nsubject   : {report['subject_team']}")
        print(f"incumbent : {report['incumbent_population']} "
              f"({report['incumbent_note']})")
        print(f"evaluations: {report['evaluations']} in "
              f"{report['elapsed_seconds']}s")
        print(f"\n{'candidate':<20}{'worst':>9}{'median':>9}{'best':>9}"
              f"{'won':>8}  wins every cell")
        for name, data in report['summary'].items():
            print(f"  {name:<18}{data['worst_case']:>9.3f}"
                  f"{data['median']:>9.3f}{data['best_case']:>9.3f}"
                  f"{data['cells_won']:>5}/{data['cells_total']}"
                  f"   {data['wins_every_cell']}")
        for name, data in report['summary'].items():
            print(f"\n  {name} distribution: {data['distribution']}")
        print(f"\nskeleton-crew still wins every cell: "
              f"{report['skeleton_still_wins_every_cell']}")
        print(f"zero-headcount opponent-independent advantage: "
              f"{report['zero_headcount_has_opponent_independent_advantage']}")
        print(f"\nwrote {EVIDENCE / 'v2-025-recheck.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
