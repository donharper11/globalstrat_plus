#!/usr/bin/env python3
"""Run the bounded adversarial tournament against a disposable database."""
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
import tournament_body
report = tournament_body.run()
print("---TOURNAMENT-JSON---")
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

    database = f"gsp_tourn_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=21600)
        marker = '---TOURNAMENT-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the tournament did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        if report['illegal_payloads']:
            raise SystemExit(
                f"REFUSED: these payloads are illegal under the final rules "
                f"and cannot enter a tournament: {report['illegal_payloads']}")

        for label, data in report['discovery'].items():
            if not data['baseline_is_repeatable']:
                raise SystemExit(f'REFUSED: the {label} discovery baseline is '
                                 f'not exactly repeatable')
        advantages = [row['advantage_by_population'][label]
                      for row in report['discovery_summary']
                      for label in row['advantage_by_population']]
        if len(set(advantages)) == 1:
            raise SystemExit('REFUSED: every candidate scored identically; the '
                             'tournament measured nothing')

        (EVIDENCE / 'stage3-tournament.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        ev = report['evaluations']
        print(f"\nsubject            : {report['subject_team']} "
              f"(field of {report['field_size']})")
        print(f"discovery identity : {report['discovery_identity']}")
        print(f"holdout identities : {report['holdout_identities']}")
        print(f"evaluations        : {ev['discovery_candidates']} discovery "
              f"candidates + {ev['discovery_baselines']} baselines, "
              f"{ev['holdout_candidates']} holdout candidates + "
              f"{ev['holdout_baselines']} baselines, in "
              f"{report['elapsed_seconds']}s")
        print(f"incumbent          : {report['incumbent']['name']} "
              f"(legal payload: "
              f"{report['incumbent_contract']['incumbent']['legal']})")
        print(f"payload contract   : "
              f"{len(report['payload_contract'])} payloads checked, "
              f"{len(report['illegal_payloads'])} illegal")

        print('\n--- discovery: advantage over competent play, by population ---')
        print(f"  {'candidate':<24}{'competent':>11}{'diverse':>10}"
              f"{'incumbent':>11}{'worst':>9}{'median':>9}  wins all")
        for row in report['discovery_summary']:
            a = row['advantage_by_population']
            print(f"  {row['name']:<24}{a['competent']:>11.3f}"
                  f"{a['diverse']:>10.3f}{a['incumbent']:>11.3f}"
                  f"{row['worst_case']:>9.3f}{row['median']:>9.3f}"
                  f"  {row['wins_every_population']}")

        print(f"\nfinalists: {report['finalists']}")
        print('\n--- holdout: 3 candidates x 3 populations x 3 identities ---')
        for row in report['holdout_summary']:
            print(f"\n  {row['name']}")
            print(f"    distribution      : {row['distribution']}")
            print(f"    worst-case margin : {row['worst_case_population_margin']}")
            print(f"    median margin     : {row['median_margin']}")
            print(f"    mean / best       : {row['mean_margin']} / {row['best_case']}")
            print(f"    cells won         : {row['cells_won']}/{row['cells_total']}"
                  f"   wins every cell: {row['wins_every_cell']}")

        print(f"\nany candidate wins across every population and holdout "
              f"fixture: {report['any_candidate_wins_everywhere']}")
        print(f"\nwrote {EVIDENCE / 'stage3-tournament.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
