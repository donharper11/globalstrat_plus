#!/usr/bin/env python3
"""Run the Stage 3 development smoke against a disposable database.

Writes nothing under `evidence/`. The smoke is development work under the
handoff's verification budget, so it is allowed to run from a dirty tree and
produces no artifact and no checksum.
"""
import datetime, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory_run as R  # noqa: E402

BODY = '''
import sys, json
sys.path.insert(0, {harness!r})
import smoke_body
report = smoke_body.run()
print("---STAGE3-SMOKE-JSON---")
print(json.dumps(report, default=str))
'''


def main():
    database = f"gsp_smoke_{datetime.datetime.now():%Y%m%d%H%M%S}"
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
            raise SystemExit('the smoke did not run')
        marker = '---STAGE3-SMOKE-JSON---'
        if marker not in result.stdout:
            print(result.stdout[-4000:]); print(result.stderr[-4000:])
            raise SystemExit('the smoke produced no report')
        print(result.stdout.split(marker)[0][-3000:])
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])

        print(f"\nsubject           : {report['subject_team']} "
              f"(field of {report['field_size']})")
        print(f"opponents         : {report['opponent_population']}")
        print(f"rounds/candidate  : {report['rounds_per_candidate']}")
        print(f"baseline index    : {report['baseline']['index']} "
              f"(margin {report['baseline']['margin']}, "
              f"rank {report['baseline']['rank']}/{report['baseline']['field']})")
        print(f"baseline repeats  : {report['baseline_is_repeatable']}")
        spread = report['fitness_spread']
        print(f"fitness spread    : {spread['worst']} .. {spread['best']} "
              f"({spread['distinct_values']} distinct, "
              f"all identical: {spread['all_identical']})")
        print(f"beat the baseline : {report['beat_baseline']}/"
              f"{report['candidates_requested']}")
        print(f"evaluations       : {report['evaluations']} in "
              f"{report['elapsed_seconds']}s")
        print('\ntop five candidates:')
        for row in report['candidates'][:5]:
            f = row['fitness']
            print(f"  #{row['n']:>2} index {f['index']:>8.3f}  "
                  f"margin {f['margin']:>9.3f}  rank {f['rank']}/{f['field']}  "
                  f"price x{row['genome']['price_multiplier']} "
                  f"volume x{row['genome']['volume_multiplier']} "
                  f"promo x{row['genome']['promotion_multiplier']}")
        print('\nno evidence written: this is a development smoke')
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
