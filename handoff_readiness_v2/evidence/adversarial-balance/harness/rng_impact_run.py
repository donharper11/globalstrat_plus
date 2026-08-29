#!/usr/bin/env python3
"""Run the RNG-impact gate against a disposable database."""
import datetime, json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
import inventory_run as R  # noqa: E402

BODY = '''
import sys, json
sys.path.insert(0, {harness!r})
SCREEN_PATH = {screen!r}
exec(open({body!r}).read())
'''


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))
    database = f"gsp_rnggate_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c', BODY.format(
            harness=str(HERE), screen=str(EVIDENCE / 'screening.json'),
            body=str(HERE / 'rng_impact_body.py')), timeout=3600)
        if result.returncode != 0:
            print(result.stdout[-4000:]); print(result.stderr[-4000:])
            raise SystemExit('gate failed')
        report = json.loads(result.stdout.split('---RNG-GATE-JSON---', 1)[1].strip())
        report['gate_revision'] = revision
        (EVIDENCE / 'rng-impact-gate.json').write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
        print(f"\nrecorded screen revision : {report['recorded_screen_revision']}")
        print(f"baseline unchanged       : {report['baseline_unchanged']}")
        print(f"probes unchanged         : {report['probes_unchanged']}"
              f"/{report['probes_compared']}")
        print(f"screen remains applicable: {report['screen_remains_applicable']}")
        for name, p in report['probes'].items():
            if p.get('comparable') and not p['unchanged']:
                print(f"  drifted: {name} -> {p['drift']}")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
