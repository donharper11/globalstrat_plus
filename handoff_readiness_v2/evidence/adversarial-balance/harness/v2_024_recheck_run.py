#!/usr/bin/env python3
"""Re-run only the V2-024 tournament candidates and controls."""
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
import v2_024_recheck_body
report = v2_024_recheck_body.run()
print("---V2024-RECHECK-JSON---")
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
    database = f"gsp_v2024_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---V2024-RECHECK-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the recheck did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        (EVIDENCE / 'v2-024-recheck.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        print(f"\nsubject   : {report['subject_team']}")
        print(f"identity  : {report['identity']}")
        print(f"evaluations: {report['evaluations']} in {report['elapsed_seconds']}s")
        for label, cell in report['results'].items():
            print(f"\n--- {label} ---")
            if not cell.get('baseline_resolvable'):
                print(f"  baseline REFUSED: {cell.get('baseline_refusal','')[:200]}")
                continue
            print(f"  baseline index {cell['baseline']['index']}")
            for name, row in cell['candidates'].items():
                if row['resolved']:
                    print(f"  {name:<22} advantage "
                          f"{row['fitness']['advantage']:>8.3f}")
                else:
                    print(f"  {name:<22} REFUSED: {row['refusal'][:140]}")
        print(f"\nboth equity candidates refused everywhere: "
              f"{report['equity_candidates_refused']}")
        print(f"\nwrote {EVIDENCE / 'v2-024-recheck.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
