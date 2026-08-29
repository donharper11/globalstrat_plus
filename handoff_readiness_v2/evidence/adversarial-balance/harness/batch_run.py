#!/usr/bin/env python3
"""Run the pre-freeze 50-candidate discovery batch against a disposable database."""
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
import batch_body
report = batch_body.run()
print("---STAGE3-BATCH-JSON---")
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

    database = f"gsp_batch_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=14400)
        marker = '---STAGE3-BATCH-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-4000:]); print(result.stderr[-4000:])
            raise SystemExit('the batch did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        for label, data in report['populations'].items():
            if not data['baseline_is_repeatable']:
                raise SystemExit(
                    f'REFUSED: the {label} baseline is not exactly repeatable')
            if data['all_identical']:
                raise SystemExit(
                    f'REFUSED: every candidate scored identically against the '
                    f'{label} population; the batch measured nothing')

        (EVIDENCE / 'stage3-discovery-batch.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        print(f"\nsubject          : {report['subject_team']} "
              f"(field of {report['field_size']})")
        print(f"seed             : {report['seed']}")
        print(f"evaluations      : {report['evaluations']} in "
              f"{report['elapsed_seconds']}s")
        for label, data in report['populations'].items():
            print(f"\n--- {label} population ---")
            print(f"  baseline index   : {data['baseline']['index']} "
                  f"(repeatable {data['baseline_is_repeatable']})")
            print(f"  advantage range  : {data['worst_advantage']} .. "
                  f"{data['best_advantage']} "
                  f"({data['distinct_advantages']} distinct)")
            print(f"  beat baseline    : {data['beat_baseline']}/"
                  f"{report['batch_size']}")
            for row in data['candidates'][:3]:
                f = row['fitness']
                print(f"    #{row['n']:>2} advantage {f['advantage']:>8.3f}  "
                      f"index {f['index']:>7.3f}  rank {f['rank']}/{f['field']}")
        print(f"\nrobust winners (beat competent play in every population): "
              f"{report['robust_winners']}")
        for detail in report['robust_winner_detail']:
            print(f"  #{detail['n']}: {detail['advantage_by_population']}")
        print(f"\nwrote {EVIDENCE / 'stage3-discovery-batch.json'}")
        print(f"inventory regenerated and verified: {len(listed)} artifacts")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
