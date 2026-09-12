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


def _run_replay(output, *, teams, rounds, policy='baseline', name_seed=None,
                home_markets='NA'):
    command = [
        sys.executable, str(RUNTIME_REPLAY), '--output', str(output),
        '--teams', str(teams), '--rounds', str(rounds),
        '--home-markets', home_markets,
        '--adaptive-production', '--policy', policy,
    ]
    if name_seed is not None:
        command += ['--name-seed', str(name_seed)]
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


def _per_profile_final(payload, rounds):
    """Every team's final-round outcome, keyed by the starter profile it ran.

    R28 asks whether any authored starting position carries an advantage that
    play cannot overcome.  Answering that needs the whole field, not the single
    subject team ``_team_final`` reports, and it must be keyed by profile
    rather than by team name -- the name is a shuffled label, the profile is
    the thing under test.
    """
    rows = []
    for row in payload['team_rounds']:
        if row['round'] != rounds:
            continue
        rows.append({
            'starter_profile': row['starter_profile'],
            'team': row['team'],
            'units_sold': round(_float(row['units_sold']), 2),
            'total_revenue': round(_float(row['total_revenue']), 2),
            'net_income': round(_float(row['net_income']), 2),
            'cash_closing': round(_float(row['cash_closing']), 2),
            'performance_index': round(_float(row['performance_index']), 4),
            'rank': int(row['rank']),
        })
    rows.sort(key=lambda entry: (entry['rank'], entry['starter_profile']))
    return rows


def _profile_trajectory(payload, rounds):
    """Per-profile performance index at every round, for the same question."""
    series = {}
    for row in payload['team_rounds']:
        series.setdefault(row['starter_profile'], {})[row['round']] = round(
            _float(row['performance_index']), 4)
    return {profile: [values[r] for r in range(1, rounds + 1) if r in values]
            for profile, values in sorted(series.items())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--field-sizes', type=int, nargs='+', default=FIELD_SIZES)
    parser.add_argument('--output', type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--smoke', action='store_true',
                        help='run only the 4-team baseline and one price probe')
    parser.add_argument('--name-seed', type=int, default=None,
                        help='pin the shuffled company names so the run is '
                             'reproducible')
    parser.add_argument('--baseline-only', action='store_true',
                        help='run only the field-size baselines, no policy '
                             'variations (used for the R28 per-profile table)')
    parser.add_argument('--home-markets', default='NA',
                        help='comma-separated home-market assignment for the '
                             'teams, in order (default: NA for every team, '
                             'which is the measured baseline). Use it to '
                             'measure what spreading home markets does.')
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
    if options.baseline_only:
        policies = ()
    elif options.smoke:
        policies = ('price_plus_10',)
    else:
        policies = POLICIES
    baseline_size = 8 if 8 in field_sizes else field_sizes[0]
    commands = []
    field_runs = {}
    sensitivity_runs = {}
    with tempfile.TemporaryDirectory(prefix='gsp-crv211-calibration-') as temp:
        tempdir = pathlib.Path(temp)
        for size in field_sizes:
            print(f'running {size}-team baseline ({options.rounds} rounds)', flush=True)
            payload, command = _run_replay(tempdir / f'field-{size}.json', teams=size,
                                           rounds=options.rounds,
                                           name_seed=options.name_seed,
                                           home_markets=options.home_markets)
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
                                           rounds=options.rounds, policy=policy,
                                           name_seed=options.name_seed,
                                           home_markets=options.home_markets)
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

        per_profile = _per_profile_final(baseline, options.rounds)
        profile_trajectory = _profile_trajectory(baseline, options.rounds)
        baseline_roster = [
            {'name': team['name'], 'starter_profile': team['starter_profile']}
            for team in baseline['teams']
        ]

    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True,
                              capture_output=True, check=True).stdout.strip()
    report = {
        'method': {
            'scenario': 'Consumer Electronics 2026',
            'rounds': options.rounds,
            'home_market_assignment': options.home_markets,
            'baseline_policy': 'documented competent baseline with 10% adaptive production',
            'ai_diffusion_rule': 'Fix A only: AI take is recorded but is excluded from Bass N',
            'measurement_rule': 'No scenario, profile, market, AI, price, production, or scoring dial is retuned.',
            'sensitivity_rule': 'One decision field changes for team 0; every other team retains baseline policy.',
            'name_seed': options.name_seed,
            'per_profile_rule': 'Every team plays the identical competent baseline policy, so a difference in outcome is attributable to the authored starting position and to nothing else.',
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
        'per_profile_final': {
            'field_size': baseline_size,
            'round': options.rounds,
            'roster': baseline_roster,
            'rows': per_profile,
            'performance_index_by_round': profile_trajectory,
            # The per-round detail behind the trajectory.  Without it the
            # aggregated report can show that a profile's index fell without
            # showing why, and a single-round fall of 13-17 points is exactly
            # the thing a starting-position audit has to be able to explain.
            'team_rounds': baseline['team_rounds'],
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
            'distinct_starter_profiles_in_baseline': len(
                {team['starter_profile'] for team in baseline['teams']}),
            'baseline_team_count': len(baseline['teams']),
        },
    }
    options.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(f'wrote {options.output}')
    print('field sizes:', ', '.join(str(size) for size in field_sizes))
    print('sensitivity dimensions:', ', '.join(policies) or '(none)')
    for size, payload in field_runs.items():
        row = _by_round(payload, options.rounds)[-1]
        print('field {size:>2}: round {round} human={human_adopters:,.2f} '
              'AI={ai_adopters:,.2f} unserved={unserved_adopters:,.2f} '
              'HHI={team_sales_hhi:.6f}'.format(size=size, **row))
    print()
    print(f'per-profile round-{options.rounds} outcome at {baseline_size} teams '
          f'({report["checks"]["distinct_starter_profiles_in_baseline"]} distinct '
          f'profiles across {report["checks"]["baseline_team_count"]} teams):')
    print('%-28s %6s %12s %14s %14s %10s' % (
        'starter profile', 'rank', 'units', 'revenue', 'net income', 'index'))
    for row in per_profile:
        print('%-28s %6d %12.0f %14.0f %14.0f %10.4f' % (
            row['starter_profile'][:28], row['rank'], row['units_sold'],
            row['total_revenue'], row['net_income'], row['performance_index']))
    if per_profile:
        indexes = [row['performance_index'] for row in per_profile]
        print('index spread: %.4f (min %.4f, max %.4f)' % (
            max(indexes) - min(indexes), min(indexes), max(indexes)))
    for policy, result in sensitivity_runs.items():
        delta = result['delta_from_baseline']
        print(f'{policy}: PI delta={delta["performance_index"]:+.4f}, '
              f'units delta={delta["units_sold"]:+,.2f}, '
              f'net income delta={delta["net_income"]:+,.2f}')


if __name__ == '__main__':
    main()
