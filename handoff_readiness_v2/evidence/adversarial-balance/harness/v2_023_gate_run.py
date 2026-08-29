#!/usr/bin/env python3
"""Run the V2-023 confirmation gate. Refuses evidence on any missing diagnostic."""
import datetime, json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
import inventory_run as R  # noqa: E402

REQUIRED_PROOF = ('reached_intended_row', 'market_average_price',
                  'price_fit_score', 'rival_rows_at_this_positioning',
                  'stored_price')
REQUIRED_OUTCOMES = ('units_sold', 'adoption_pool', 'fit_score',
                     'total_revenue', 'net_income', 'cash_closing',
                     'index_value')

BODY = '''
import sys
sys.path.insert(0, {harness!r})
exec(open({body!r}).read())
'''


def refuse(message):
    print(f'REFUSED: {message}')
    raise SystemExit(1)


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        refuse('the tree is dirty:\n  ' + '\n  '.join(dirty.splitlines()))

    database = f"gsp_v2023_{datetime.datetime.now():%Y%m%d%H%M%S}"
    print(f'Creating disposable database {database}')
    if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
        refuse('could not create the database')
    try:
        R.manage(database, 'migrate', '--noinput')
        R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
        out = R.manage(database, 'shell', '-c', BODY.format(
            harness=str(HERE), body=str(HERE / 'v2_023_gate_body.py')),
            timeout=3600)
        if out.returncode != 0:
            print(out.stdout[-4000:]); print(out.stderr[-4000:])
            refuse('the gate did not run')
        report = json.loads(out.stdout.split('---V2023-GATE-JSON---', 1)[1].strip())
        report['gate_revision'] = revision

        if not report.get('positioning_membership'):
            refuse('positioning membership is missing; the gate cannot say '
                   'which group a team was in, which is the whole question')
        if not report.get('gate_usable'):
            refuse(report.get('why', 'the fixture cannot test the hypothesis'))
        if not report.get('baseline_is_repeatable'):
            refuse(f"the baseline is not exactly repeatable: "
                   f"{report['baseline_repeat_delta']}")

        for label, subject in report['subjects'].items():
            for price, cell in subject['by_price'].items():
                proof, outcomes = cell['proof'], cell['outcomes']
                missing = [k for k in REQUIRED_PROOF if proof.get(k) is None]
                missing += [k for k in REQUIRED_OUTCOMES
                            if outcomes.get(k) is None]
                if missing:
                    refuse(f'{label} @ {price}: missing diagnostics {missing}')
                if not proof['reached_intended_row']:
                    refuse(f'{label} @ {price}: the mutation did not reach the '
                           f'intended product/market row')

        (EVIDENCE / 'v2-023-gate.json').write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')

        print(f"\nbaseline repeatable: {report['baseline_is_repeatable']}")
        print('\npositioning groups:')
        for key, g in report['positioning_membership'].items():
            print(f"  {key:22} teams={g['teams']}")
        for label in ('alone', 'shared'):
            s = report['subjects'][label]
            print(f"\n--- {label}: {s['team']} / {s['product']} in {s['group']} "
                  f"({s['rival_rows']} rival row(s)) ---")
            print(f"  {'price':>8} {'avg price':>12} {'price fit':>10} "
                  f"{'units sold':>12} {'revenue':>14} {'index':>8}")
            for price, cell in s['by_price'].items():
                p, o = cell['proof'], cell['outcomes']
                print(f"  {price:>8} {p['market_average_price']:>12.2f} "
                      f"{p['price_fit_score']:>10.4f} {o['units_sold']:>12} "
                      f"{o['total_revenue']:>14} {o['index_value']:>8}")
            print(f"  units constant across prices: "
                  f"{s['units_constant_across_prices']}")
        print(f"\nhypothesis supported: {report['hypothesis_supported']}")
        print(f"wrote {EVIDENCE / 'v2-023-gate.json'}")
        return 0
    finally:
        R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        print(f'Dropped {database}')


if __name__ == '__main__':
    raise SystemExit(main())
