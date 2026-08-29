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
import disclosure_probe_body
report = disclosure_probe_body.run()
print("---DISCLOSURE-JSON---")
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
    database = f"gsp_disc_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---DISCLOSURE-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the disclosure probe did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        (EVIDENCE / 'progressive-disclosure-probe.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        control = report['positive_control']
        if not report['probe_is_valid']:
            raise SystemExit(
                f"REFUSED: the probe did not reach the application. Positive "
                f"control {control['url']} returned {control['status']}, and "
                f"the permitted write returned "
                f"{report['steps'][1].get('status')}. Absence of a value in a "
                f"failed request is not evidence of protection.")

        print(f"\nfield              : {report['field_path']}")
        print(f"positive control   : {control['status']} "
              f"(reached app: {control['reached_the_application']})")
        print(f"authored unlock    : round {report['authored_unlock_round']}, "
              f"probed at round {report['current_round']}")
        print(f"write gate holds   : {report['write_gate_holds']}")
        print(f"class isolation    : {report['class_isolation_holds']}")
        print(f"readable at unlock : {report['readable_after_unlock']}")
        print(f"\nread surfaces before unlock:")
        for name, e in report['read_surfaces_before_unlock'].items():
            print(f"  {name:<38} status {e['status']:>3}  "
                  f"leaks value: {e['sentinel_in_body']}")
        print(f"\nread gate holds    : {report['read_gate_holds']}")
        if report['leaking_surfaces']:
            print(f"LEAKING SURFACES   : {report['leaking_surfaces']}")
        print(f"\nwrote {EVIDENCE / 'progressive-disclosure-probe.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
