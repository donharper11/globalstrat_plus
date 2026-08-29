#!/usr/bin/env python3
"""Run the pre-freeze fixture-identity checks against a disposable database."""
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
import identity_check_body
report = identity_check_body.run()
print("---IDENTITY-CHECK-JSON---")
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

    database = f"gsp_ident_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---IDENTITY-CHECK-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-4000:]); print(result.stderr[-4000:])
            raise SystemExit('the identity check did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        print(f"\nidentities            : {report['identities']}")
        print(f"distinct              : {report['identities_are_distinct']}")
        print(f"stable across calls   : {report['identity_is_stable']}")
        print(f"streams differ (all)  : "
              f"{report['every_pair_differs_on_every_stream']}")
        for pair, data in report['stream_differences'].items():
            same = [op for op, v in data['per_stream'].items() if not v['differs']]
            print(f"  {pair}: all differ {data['all_differ']}"
                  + (f", identical streams {same}" if same else ''))
        print(f"every identity repeatable: {report['every_identity_is_repeatable']}")
        print(f"outcomes differ       : {report['identities_change_the_outcome']} "
              f"({report['distinct_outcomes']} distinct of {len(report['seeds'])})")
        for seed, sig in report['outcome_signatures'].items():
            print(f"  {seed}: index {sig[0]}  cash {sig[1]}  revenue {sig[2]}")

        blocking = []
        if not report['identities_are_distinct']:
            blocking.append('seeds do not produce distinct identities')
        if not report['identity_is_stable']:
            blocking.append('the same seed produced different identities')
        if not report['every_pair_differs_on_every_stream']:
            blocking.append('some engine streams are identical across identities')
        if not report['every_identity_is_repeatable']:
            blocking.append('an identity did not reproduce exactly')
        report['blocking_failures'] = blocking

        (EVIDENCE / 'fixture-identity-check.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')
        print(f"\nwrote {EVIDENCE / 'fixture-identity-check.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")

        if blocking:
            print('\nNOT FROZEN: ' + '; '.join(blocking))
            return 1
        print('\nchecks pass: the fixture may be frozen')
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
