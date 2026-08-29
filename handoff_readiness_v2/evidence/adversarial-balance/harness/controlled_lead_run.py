#!/usr/bin/env python3
"""Two controlled playthroughs with exogenous shocks silenced in the fixture."""
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
import controlled_lead_body
report = controlled_lead_body.run({arm!r})
print("---CONTROLLED-JSON---")
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

    def play(arm, label=None):
        database = f"gsp_ctrl_{label or arm}_{datetime.datetime.now():%H%M%S}"
        print(f'Creating disposable database {database}')
        if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
            raise SystemExit('could not create the database')
        try:
            R.manage(database, 'migrate', '--noinput')
            R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
            result = R.manage(database, 'shell', '-c',
                              BODY.format(harness=str(HERE), arm=arm),
                              timeout=7200)
            marker = '---CONTROLLED-JSON---'
            if result.returncode != 0 or marker not in result.stdout:
                print(result.stdout[-4000:]); print(result.stderr[-4000:])
                raise SystemExit(f'the controlled probe did not run ({arm})')
            return json.loads(
                result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        finally:
            R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
            print(f'Dropped {database}')

    baseline_a = play('both_baseline', 'baseline_a')
    baseline_b = play('both_baseline', 'baseline_b')
    countered = play('challenger_counters')

    report = {
        'code_revision': revision,
        'baseline': baseline_a,
        'baseline_repeat': baseline_b,
        'challenger_counters': countered,
    }

    def signature(run):
        return [(r['round'], r['index_gap'], r['composite_gap'],
                 r['adopter_gap']) for r in run['series']]

    report['baseline_is_exactly_repeatable'] = (
        signature(baseline_a) == signature(baseline_b))

    for name, run in (('baseline', baseline_a), ('baseline_repeat', baseline_b),
                      ('challenger_counters', countered)):
        if not run['shocks_were_silent']:
            raise SystemExit(
                f"REFUSED: exogenous shocks fired in {name} despite zero "
                f"probability, so this is not a controlled measurement: "
                f"{run['shock_breaches'][:4]}")
    if not report['baseline_is_exactly_repeatable']:
        raise SystemExit(
            'REFUSED: the controlled baseline is not exactly repeatable, so '
            'nothing measured against it can be trusted.')

    (EVIDENCE / 'controlled-early-lead.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    listed = checksums.regenerate(EVIDENCE)
    bad = checksums.verify(EVIDENCE)
    if bad:
        raise SystemExit(f'inventory does not verify: {bad}')

    print(f"\nscenario                 : {baseline_a['scenario']}")
    print(f"shocks silenced          : {baseline_a['exogenous_shocks_silenced']}")
    print(f"method                   : {baseline_a['silencing_method']}")
    print(f"baseline repeats exactly : "
          f"{report['baseline_is_exactly_repeatable']}")
    print(f"any sales stopped        : baseline "
          f"{baseline_a['any_sales_stopped']}, countered "
          f"{countered['any_sales_stopped']}")
    print(f"any inactivity cap       : baseline "
          f"{baseline_a['any_inactivity_cap']}, countered "
          f"{countered['any_inactivity_cap']}")

    for name, run in (('arm 1: both return to baseline', baseline_a),
                      ('arm 2: challenger counters', countered)):
        print(f"\n--- {name} ---")
        print(f"{'r':>3} {'phase':<11}{'idx gap':>10}{'comp gap':>10}"
              f"{'adopter gap':>14}{'L cap':>8}{'C cap':>8}")
        for r in run['series']:
            print(f"{r['round']:>3} {r['phase']:<11}{r['index_gap']:>10}"
                  f"{r['composite_gap']:>10}{r['adopter_gap']:>14}"
                  f"{r['leader']['capability_component']:>8}"
                  f"{r['challenger']['capability_component']:>8}")
        print(f"  gap when front-load ended : {run['gap_when_front_load_ended']}")
        print(f"  gap at end                : {run['gap_at_end']}")
        print(f"  composite gap at end      : {run['composite_gap_at_end']}")
        print(f"  adopter gap at end        : {run['adopter_gap_at_end']}")

    print(f"\nwrote {EVIDENCE / 'controlled-early-lead.json'}")
    print(f"inventory: {len(listed)} artifacts, verified")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
