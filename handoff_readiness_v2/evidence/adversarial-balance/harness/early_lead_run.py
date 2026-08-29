#!/usr/bin/env python3
"""Run the early-lead lock-in probe against a disposable database."""
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
import early_lead_body
report = early_lead_body.run()
print("---EARLY-LEAD-JSON---")
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

    database = f"gsp_lead_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---EARLY-LEAD-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the early-lead probe did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        # The probe's own precondition: without a lead there is no lock-in to
        # test, and a margin series from a strategy that never led says nothing.
        if not report['lead_was_established']:
            raise SystemExit(
                'REFUSED: the front-loaded strategy never established a lead, '
                'so there is no lock-in to test.')

        (EVIDENCE / 'early-lead-probe.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        print(f"\nscenario : {report['scenario']}")
        print(f"subject  : {report['subject_team']}  "
              f"({report['front_load_rounds']} front-loaded rounds of "
              f"{report['total_rounds']})")
        print(f"\n{'round':>6} {'phase':<14}{'index':>9}{'margin':>10}"
              f"{'rank':>7}  cumulative adopters")
        for r in report['series']:
            print(f"{r['round']:>6} {r['phase']:<14}{r['index']:>9.3f}"
                  f"{r['margin']:>10.3f}{r['rank']:>4}/{r['field']}  "
                  f"{r['cumulative_adopters']}")
        print(f"\npeak margin while front-loading : "
              f"{report['peak_margin_while_front_loading']}")
        print(f"final margin after reverting    : "
              f"{report['final_margin_after_reverting']}")
        print(f"margin by round after revert    : "
              f"{report['margin_by_round_after_revert']}")
        print(f"margin erodes after revert      : "
              f"{report['margin_erodes_after_revert']}")
        print(f"margin never decreases after    : "
              f"{report['margin_strictly_non_decreasing_after_revert']}")
        print(f"rank ever lost after revert     : {report['rank_ever_lost']}")
        print(f"\nwrote {EVIDENCE / 'early-lead-probe.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
