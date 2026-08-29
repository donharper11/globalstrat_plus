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
import value_conservation_body
report = value_conservation_body.run()
print("---VALUE-CONSERVATION-JSON---")
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
    database = f"gsp_valc_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        raise SystemExit('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        result = R.manage(database, 'shell', '-c',
                          BODY.format(harness=str(HERE)), timeout=7200)
        marker = '---VALUE-CONSERVATION-JSON---'
        if result.returncode != 0 or marker not in result.stdout:
            print(result.stdout[-5000:]); print(result.stderr[-5000:])
            raise SystemExit('the value conservation probe did not run')
        report = json.loads(result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        report['code_revision'] = revision

        (EVIDENCE / 'value-conservation-probe.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        if not report['all_mutations_reached_their_row']:
            missed = [n for n, a in report['arms'].items()
                      if 'proof' in a and a['proof']
                      and not a['proof'].get('reached_row')]
            raise SystemExit(
                f"REFUSED: these mutations did not reach their persisted row, "
                f"so their ledgers mean nothing: {missed}")

        (EVIDENCE / 'value-conservation-probe.json').write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
        listed = checksums.regenerate(EVIDENCE)
        bad = checksums.verify(EVIDENCE)
        if bad:
            raise SystemExit(f'inventory does not verify: {bad}')

        contract = report['fixture_contract']
        if not report['fixture_contract_holds']:
            missing = [f for f, v in contract.items() if not v['reachable']]
            raise SystemExit(
                f"REFUSED: the fixture scenario '{report['scenario']}' cannot "
                f"express these decision families, so a probe against it "
                f"would measure the fixture rather than the product: "
                f"{missing}")

        print(f"\nscenario    : {report['scenario']} (id {report['scenario_id']})")
        print("fixture contract:")
        for family, v in contract.items():
            print(f"  {family:<16} {v['model']:<28} rows {v['rows']:>3}  "
                  f"reachable {v['reachable']}")
        print(f"\nsubject     : {report['subject_team']}")
        print(f"scenario    : {report['scenario_supports']}")
        print(f"evaluations : {report['evaluations']} in "
              f"{report['elapsed_seconds']}s")
        print("\ncontrol ledger (production and sales at zero):")
        for rnd_no, row in sorted(report['control']['ledger'].items()):
            print(f"  round {rnd_no}: cash {row['cash_closing']:>18}  "
                  f"inventory {row['inventory_value']:>14}  "
                  f"cash+inv {row['cash_plus_inventory']:>18}")
        print("\narms:")
        for name, a in report['arms'].items():
            if a.get('unexercisable'):
                print(f"  {name}: UNEXERCISABLE — {a['unexercisable']}")
                continue
            print(f"\n  {name}")
            print(f"    why           : {a['why']}")
            print(f"    proof         : {a['proof']}")
            print(f"    creates value : {a['creates_value']}")
            if 'sales_really_are_zero' in a:
                print(f"    sales at zero : {a['sales_really_are_zero']}  "
                      f"suppressed: {a['sales_effectively_suppressed']}")
                print(f"    units sold    : {a['units_sold_by_round']} "
                      f"vs normal {a['units_sold_normally']}")
                print(f"    cash+inv      : {a['cash_plus_inventory_by_round']}")
                print(f"    conserved     : {a['value_conserved']}")
            if a.get('inconclusive'):
                print(f"    INCONCLUSIVE  : {a['inconclusive']}")
            for rnd_no, d in sorted(a['delta_vs_control'].items()):
                print(f"      round {rnd_no} delta: cash "
                      f"{d.get('cash_closing'):>16}  inventory "
                      f"{d.get('inventory_value'):>14}  cash+inv "
                      f"{d.get('cash_plus_inventory'):>16}")
        print(f"\narms creating value : {report['arms_creating_value']}")
        print(f"inconclusive arms   : {report['inconclusive_arms']}")
        print(f"unexercisable arms  : {report['unexercisable_arms']}")
        print(f"\nwrote {EVIDENCE / 'value-conservation-probe.json'}")
        print(f"inventory: {len(listed)} artifacts, verified")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
