#!/usr/bin/env python3
"""Measure CRV2-11's adopted, fixed Fix-A policy on disposable PostgreSQL.

This runner does not tune a scenario.  It replays the existing competent
baseline policy with all teams assigned to NA, then makes one transparent,
measurement-only decision change to the first team.  It measures the same
policy at the five intended heat sizes (4, 6, 8, 10 and 12 teams).

``backend/scripts/run-calibration-postgres`` supplies a temporary PostgreSQL
container and generated credential.  The per-run replay then creates and
forces-drops its own database, so no production database or credential is in
scope for this evidence.
"""
import argparse
import hashlib
import json
import os
import pathlib
import statistics
import subprocess
import sys
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNTIME_REPLAY = HERE / 'stage1_runtime_replay.py'
DEFAULT_OUTPUT = HERE / 'fixed_policy_measurements.json'
FIELD_SIZES = (4, 6, 8, 10, 12)
POLICIES = (
    'price_plus_10',
    'promotion_plus_50',
    'production_plus_25',
    'sales_team_plus_50',
)


def _float(value):
    return float(value)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_replay(output, *, teams, rounds, policy='baseline'):
    command = [
        sys.executable, str(RUNTIME_REPLAY), '--output', str(output),
        '--teams', str(teams), '--rounds', str(rounds), '--home-markets', 'NA',
        '--adaptive-production', '--policy', policy,
    ]
    result = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                            env=os.environ.copy(), timeout=7200)
    if result.returncode:
        raise RuntimeError(
            f"{' '.join(command)} failed ({result.returncode}):\n"
            f'{result.stderr[-4000:]}\n{result.stdout[-4000:]}')
    return json.loads(output.read_text()), command


def _by_round(payload, rounds):
    rows = []
    for round_number in range(1, rounds + 1):
        recs = [row for row in payload['rows'] if row['round'] == round_number]
        team_rows = [row for row in payload['team_rounds']
                     if row['round'] == round_number]
        product_rows = [row for row in payload['product_rounds']
                        if row['round'] == round_number]
        pool = sum(_float(row['adoption_pool']) for row in recs)
        human = sum(_float(row['human_adopters']) for row in recs)
        ai = sum(_float(row['ai_adopters']) for row in recs)
        unserved = sum(_float(row['unserved_adopters']) for row in recs)
        sales = {}
        for product in product_rows:
            sales[product['team']] = sales.get(product['team'], 0.0) + _float(product['units_sold'])
        total_sales = sum(sales.values())
        shares = [(value / total_sales) for value in sales.values()] if total_sales else []
        indexes = sorted(_float(row['performance_index']) for row in team_rows)
        rows.append({
            'round': round_number,
            'adoption_pool': round(pool, 2),
            'human_adopters': round(human, 2),
            'ai_adopters': round(ai, 2),
            'unserved_adopters': round(unserved, 2),
            'human_share': round(human / pool, 8) if pool else 0.0,
            'ai_share': round(ai / pool, 8) if pool else 0.0,
            'unserved_share': round(unserved / pool, 8) if pool else 0.0,
            'team_units_sold': round(total_sales, 2),
            'team_sales_hhi': round(sum(share * share for share in shares), 8),
            'team_count': len(team_rows),
            'performance_index_min': round(indexes[0], 4),
            'performance_index_median': round(statistics.median(indexes), 4),
            'performance_index_max': round(indexes[-1], 4),
        })
    return rows


def _assert_integrity(payload, *, teams, rounds):
    if len(payload['teams']) != teams:
        raise AssertionError(f'expected {teams} teams, got {len(payload["teams"])}')
    for row in _by_round(payload, rounds):
        if row['team_count'] != teams:
            raise AssertionError(f'round {row["round"]}: missing team result')
        if abs(row['adoption_pool'] - row['human_adopters'] - row['ai_adopters']
               - row['unserved_adopters']) > 0.02:
            raise AssertionError(f'round {row["round"]}: adoption pool does not reconcile')


def _team_final(payload, team_index, rounds):
    team_name = payload['teams'][team_index]['name']
    row = next(row for row in payload['team_rounds']
               if row['round'] == rounds and row['team'] == team_name)
    return {
        'total_revenue': round(_float(row['total_revenue']), 2),
        'net_income': round(_float(row['net_income']), 2),
        'cash_closing': round(_float(row['cash_closing']), 2),
        'performance_index': round(_float(row['performance_index']), 4),
        'rank': row['rank'],
        'units_sold': round(_float(row['units_sold']), 2),
    }


def _delta(observed, baseline):
    return {key: round(observed[key] - baseline[key], 4)
            for key in ('total_revenue', 'net_income', 'cash_closing',
                        'performance_index', 'units_sold')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--field-sizes', type=int, nargs='+', default=FIELD_SIZES)
    parser.add_argument('--output', type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--smoke', action='store_true',
                        help='run only the 4-team baseline and one price probe')
    options = parser.parse_args()
    if not 1 <= options.rounds <= 10:
        raise SystemExit('--rounds must be between 1 and 10')
    if not options.field_sizes or any(size < 1 for size in options.field_sizes):
        raise SystemExit('--field-sizes must contain positive team counts')

    required = ('DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD')
    absent = [key for key in required if not os.environ.get(key)]
    if absent:
        raise SystemExit('This runner requires disposable DB_* environment from '
                         'backend/scripts/run-calibration-postgres: ' + ', '.join(absent))

    field_sizes = tuple(dict.fromkeys(options.field_sizes))
    if options.smoke:
        field_sizes = (4,)
    policies = ('price_plus_10',) if options.smoke else POLICIES
    baseline_size = 8 if 8 in field_sizes else field_sizes[0]
    commands = []
    field_runs = {}
    sensitivity_runs = {}
    with tempfile.TemporaryDirectory(prefix='gsp-crv211-calibration-') as temp:
        tempdir = pathlib.Path(temp)
        for size in field_sizes:
            print(f'running {size}-team baseline ({options.rounds} rounds)', flush=True)
            payload, command = _run_replay(tempdir / f'field-{size}.json', teams=size,
                                           rounds=options.rounds)
            _assert_integrity(payload, teams=size, rounds=options.rounds)
            field_runs[size] = payload
            commands.append(command)

        baseline = field_runs[baseline_size]
        subject = {
            'team_index': 0,
            'baseline_name': baseline['teams'][0]['name'],
            'starter_profile': baseline['teams'][0]['starter_profile'],
        }
        baseline_subject = _team_final(baseline, 0, options.rounds)
        for policy in policies:
            print(f'running {baseline_size}-team {policy} ({options.rounds} rounds)',
                  flush=True)
            payload, command = _run_replay(tempdir / f'{policy}.json', teams=baseline_size,
                                           rounds=options.rounds, policy=policy)
            _assert_integrity(payload, teams=baseline_size, rounds=options.rounds)
            observed = _team_final(payload, 0, options.rounds)
            sensitivity_runs[policy] = {
                'subject_team': subject,
                'variation_name': payload['teams'][0]['name'],
                'final_subject_result': observed,
                'delta_from_baseline': _delta(observed, baseline_subject),
                'rounds': _by_round(payload, options.rounds),
            }
            commands.append(command)

    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True,
                              capture_output=True, check=True).stdout.strip()
    report = {
        'method': {
            'scenario': 'Consumer Electronics 2026',
            'rounds': options.rounds,
            'home_market_assignment': 'NA for every team',
            'baseline_policy': 'documented competent baseline with 10% adaptive production',
            'ai_diffusion_rule': 'Fix A only: AI take is recorded but is excluded from Bass N',
            'measurement_rule': 'No scenario, profile, market, AI, price, production, or scoring dial is retuned.',
            'sensitivity_rule': 'One decision field changes for team 0; every other team retains baseline policy.',
        },
        'provenance': {
            'code_revision': revision,
            'runtime_replay_sha256': _sha256(RUNTIME_REPLAY),
            'scenario_sha256': _sha256(REPO / 'backend/scenarios/consumer_electronics_2026.yaml'),
            'commands': commands,
        },
        'field_size_saturation': {
            str(size): {'rounds': _by_round(payload, options.rounds)}
            for size, payload in field_runs.items()
        },
        'fixed_policy_sensitivity': {
            'baseline_field_size': baseline_size,
            'baseline_subject_final': baseline_subject,
            'variations': sensitivity_runs,
        },
        'checks': {
            'all_field_sizes_reconciled': True,
            'all_requested_runs_completed': True,
            'policy_variations': list(policies),
        },
    }
    options.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(f'wrote {options.output}')
    print('field sizes:', ', '.join(str(size) for size in field_sizes))
    print('sensitivity dimensions:', ', '.join(policies))
    for size, payload in field_runs.items():
        row = _by_round(payload, options.rounds)[-1]
        print('field {size:>2}: round {round} human={human_adopters:,.2f} '
              'AI={ai_adopters:,.2f} unserved={unserved_adopters:,.2f} '
              'HHI={team_sales_hhi:.6f}'.format(size=size, **row))
    for policy, result in sensitivity_runs.items():
        delta = result['delta_from_baseline']
        print(f'{policy}: PI delta={delta["performance_index"]:+.4f}, '
              f'units delta={delta["units_sold"]:+,.2f}, '
              f'net income delta={delta["net_income"]:+,.2f}')


if __name__ == '__main__':
    main()
