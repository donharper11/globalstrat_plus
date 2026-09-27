#!/usr/bin/env python3
"""Competition-candidate decision sensitivity and starter-profile evidence.

The runner changes decisions, never mechanics or scenario constants.  Every
probe resolves a fresh database through ``stage1_runtime_replay.py`` for the
full ten-round horizon.  One-factor sweeps are deliberately kept separate
from the derived multi-lever policy so flat mechanics, caps and interactions
are visible rather than hidden inside an optimizer.
"""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import statistics
import subprocess
import sys
import tempfile
import time


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPLAY = HERE / 'stage1_runtime_replay.py'
BASELINE = (REPO / 'handoff_readiness_v2' / 'evidence' /
            'adversarial-balance' / 'harness' / 'baseline.py')
DEFAULT_OUTPUT = HERE / 'competition_sensitivity_measurements.json'
CANDIDATE_REVISION = '49b547fd30c954c44049b1f34e79e5e3a0d5dd3e'
SCENARIOS = {
    'consumer_electronics_2026': 'consumer_electronics_2026.yaml',
    'clean_energy_tech_2026': 'clean_energy_tech_2026.yaml',
    'media_entertainment_2026': 'media_entertainment_2026.yaml',
}

# Levels are ordered by the real decision quantity. Baseline is added by the
# analysis at its natural zero/one point, so it does not need a replay.
POLICY_FAMILIES = {
    'price': [
        ('price_x0_70', 0.70, {'price_multiplier': 0.70}),
        ('price_x0_85', 0.85, {'price_multiplier': 0.85}),
        ('price_x1_15', 1.15, {'price_multiplier': 1.15}),
        ('price_x1_30', 1.30, {'price_multiplier': 1.30}),
    ],
    'promotion': [
        ('promotion_x0', 0.0, {'promotion_multiplier': 0.0}),
        ('promotion_x0_50', 0.50, {'promotion_multiplier': 0.50}),
        ('promotion_x1_50', 1.50, {'promotion_multiplier': 1.50}),
        ('promotion_x2', 2.0, {'promotion_multiplier': 2.0}),
    ],
    'production': [
        ('production_x0_50', 0.50, {'production_multiplier': 0.50}),
        ('production_x0_75', 0.75, {'production_multiplier': 0.75}),
        ('production_x1_25', 1.25, {'production_multiplier': 1.25}),
        ('production_x1_50', 1.50, {'production_multiplier': 1.50}),
    ],
    'sales_staff': [
        ('sales_staff_x0', 0.0, {'sales_staff_multiplier': 0.0}),
        ('sales_staff_x0_50', 0.50, {'sales_staff_multiplier': 0.50}),
        ('sales_staff_x1_50', 1.50, {'sales_staff_multiplier': 1.50}),
        ('sales_staff_x2', 2.0, {'sales_staff_multiplier': 2.0}),
    ],
    'financing_net_debt': [
        ('debt_repayment_2m', -2_000_000,
         {'debt_repayment': 2_000_000}),
        ('debt_repayment_1m', -1_000_000,
         {'debt_repayment': 1_000_000}),
        ('new_debt_1m', 1_000_000, {'new_debt': 1_000_000}),
        ('new_debt_2m', 2_000_000, {'new_debt': 2_000_000}),
    ],
    'stakeholder_esg_total': [
        ('esg_total_0_5m', 500_000,
         {'environmental_investment': 250_000,
          'social_investment': 250_000}),
        ('esg_total_1m', 1_000_000,
         {'environmental_investment': 500_000,
          'social_investment': 500_000}),
        ('esg_total_2m', 2_000_000,
         {'environmental_investment': 1_000_000,
          'social_investment': 1_000_000}),
        ('esg_total_4m', 4_000_000,
         {'environmental_investment': 2_000_000,
          'social_investment': 2_000_000}),
        ('esg_total_6m', 6_000_000,
         {'environmental_investment': 3_000_000,
          'social_investment': 3_000_000}),
    ],
}
BASELINE_LEVEL = {
    'price': 1.0,
    'promotion': 1.0,
    'production': 1.0,
    'sales_staff': 1.0,
    'financing_net_debt': 0.0,
    'stakeholder_esg_total': 0.0,
}
METRICS = (
    'cumulative_revenue', 'cumulative_net_income', 'cumulative_units_sold',
    'final_cash', 'final_performance_index', 'final_satisfaction_score',
    'final_total_debt', 'final_total_equity', 'final_debt_to_equity',
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _f(value):
    return float(value or 0)


def _run_replay(output, scenario, *, policy_spec=None, subject=0,
                rounds=10, teams=8, name_seed=20260927):
    command = [
        sys.executable, str(REPLAY), '--output', str(output),
        '--scenario', scenario, '--rounds', str(rounds), '--teams', str(teams),
        '--adaptive-production', '--name-seed', str(name_seed),
        '--subject-team-index', str(subject),
    ]
    if policy_spec:
        command += ['--policy-spec-json', json.dumps(
            policy_spec, sort_keys=True, separators=(',', ':'))]
    started = time.monotonic()
    result = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                            timeout=7200)
    elapsed = round(time.monotonic() - started, 3)
    if result.returncode:
        raise RuntimeError(
            f"{' '.join(command)} failed ({result.returncode}):\n"
            f'{result.stderr[-5000:]}\n{result.stdout[-5000:]}')
    return json.loads(output.read_text()), command, elapsed, _sha256(output)


def _team_rows(payload, team_index):
    name = payload['teams'][team_index]['name']
    return name, sorted(
        (row for row in payload['team_rounds'] if row['team'] == name),
        key=lambda row: row['round'])


def summarise_team(payload, team_index):
    name, rows = _team_rows(payload, team_index)
    final = rows[-1]
    product_rows = [row for row in payload['product_rounds']
                    if row['team'] == name]
    demand_rows = [row for row in payload['product_demand_rounds']
                   if row['team'] == name]
    decision_rows = sorted(
        (row for row in payload['decision_rounds'] if row['team'] == name),
        key=lambda row: row['round'])
    trajectory = []
    for row in rows:
        round_number = row['round']
        products = [item for item in product_rows
                    if item['round'] == round_number]
        demand = [item for item in demand_rows
                  if item['round'] == round_number]
        decision = next(item for item in decision_rows
                        if item['round'] == round_number)
        trajectory.append({
            'round': round_number,
            'revenue': _f(row['total_revenue']),
            'net_income': _f(row['net_income']),
            'cash': _f(row['cash_closing']),
            'performance_index': _f(row['performance_index']),
            'satisfaction_score': _f(row['satisfaction_score']),
            'total_debt': _f(row['total_debt']),
            'total_equity': _f(row['total_equity']),
            'debt_to_equity': _f(row['debt_to_equity']),
            'units_sold': _f(row['units_sold']),
            'units_unsold': sum(_f(item['units_unsold']) for item in products),
            'lost_demand': sum(_f(item['lost_demand']) for item in demand),
            'unconstrained_demand': sum(
                _f(item['unconstrained_demand']) for item in demand),
            'decision': decision,
        })
    return {
        'team': name,
        'starter_profile': payload['teams'][team_index]['starter_profile'],
        'rank': int(final['rank']),
        'cumulative_revenue': round(sum(_f(row['total_revenue']) for row in rows), 2),
        'cumulative_net_income': round(sum(_f(row['net_income']) for row in rows), 2),
        'cumulative_units_sold': round(sum(_f(row['units_sold']) for row in rows), 2),
        'cumulative_strategy_expense': round(sum(
            _f(row['strategy_expense']) for row in rows), 2),
        'cumulative_financing_cash_flow': round(sum(
            _f(row['financing_cash_flow']) for row in rows), 2),
        'final_cash': _f(final['cash_closing']),
        'final_performance_index': _f(final['performance_index']),
        'final_satisfaction_score': _f(final['satisfaction_score']),
        'final_total_debt': _f(final['total_debt']),
        'final_total_equity': _f(final['total_equity']),
        'final_debt_to_equity': _f(final['debt_to_equity']),
        'final_share_price': _f(final['share_price']),
        'trajectory': trajectory,
    }


def _delta(observed, baseline):
    return {key: round(observed[key] - baseline[key], 6) for key in METRICS}


def classify_effect(observed, baseline, tolerance=1e-6):
    deltas = _delta(observed, baseline)
    outcome_changed = any(abs(value) > tolerance for value in deltas.values())
    changed_rounds = []
    supply_capped = []
    demand_capped = []
    commercially_flat = []
    for current, reference in zip(observed['trajectory'], baseline['trajectory']):
        commercial_change = (
            abs(current['revenue'] - reference['revenue']) > tolerance
            or abs(current['units_sold'] - reference['units_sold']) > tolerance)
        full_change = commercial_change or any(
            abs(current[key] - reference[key]) > tolerance
            for key in ('cash', 'performance_index', 'satisfaction_score',
                        'total_debt', 'total_equity', 'debt_to_equity'))
        if full_change:
            changed_rounds.append(current['round'])
        if not commercial_change:
            commercially_flat.append(current['round'])
        if current['lost_demand'] > tolerance or reference['lost_demand'] > tolerance:
            supply_capped.append(current['round'])
        if current['units_unsold'] > tolerance or reference['units_unsold'] > tolerance:
            demand_capped.append(current['round'])
    if not outcome_changed:
        label = ('cap_masked_across_horizon'
                 if supply_capped or demand_capped else 'flat_observed_mechanic')
    elif changed_rounds and changed_rounds[0] > 1:
        label = 'delayed_or_temporarily_capped'
    else:
        label = 'responsive_from_round_1'
    return {
        'label': label,
        'first_changed_round': changed_rounds[0] if changed_rounds else None,
        'changed_rounds': changed_rounds,
        'commercially_flat_rounds': commercially_flat,
        'supply_capped_rounds': supply_capped,
        'demand_capped_rounds': demand_capped,
        'effect': deltas,
    }


def monotonicity(points, metric, tolerance=1e-6):
    ordered = sorted(points, key=lambda point: point['level'])
    values = [point['result'][metric] for point in ordered]
    changes = [right - left for left, right in zip(values, values[1:])]
    if all(abs(change) <= tolerance for change in changes):
        direction = 'flat'
    elif all(change >= -tolerance for change in changes):
        direction = 'nondecreasing'
    elif all(change <= tolerance for change in changes):
        direction = 'nonincreasing'
    else:
        direction = 'nonmonotonic'
    return {'direction': direction, 'levels': [point['level'] for point in ordered],
            'values': values}


def _dominance(result, baseline, tolerance=1e-6):
    keys = ('final_performance_index', 'cumulative_revenue',
            'cumulative_net_income', 'final_cash')
    changes = [result[key] - baseline[key] for key in keys]
    if all(change >= -tolerance for change in changes) and any(
            change > tolerance for change in changes):
        return 'dominates_baseline'
    if all(change <= tolerance for change in changes) and any(
            change < -tolerance for change in changes):
        return 'dominated_by_baseline'
    return 'tradeoff'


def _deterministic_content(payload):
    return {key: payload[key] for key in (
        'scenario', 'home_markets', 'teams_requested', 'policy', 'policy_spec',
        'subject_team_index', 'adaptive_production', 'teams', 'rows',
        'team_rounds', 'product_rounds', 'product_demand_rounds',
        'decision_rounds')}


def _measure_scenario(scenario, *, rounds, teams, seed, smoke, temp_root):
    scenario_dir = temp_root / scenario
    scenario_dir.mkdir(parents=True, exist_ok=True)
    print(f'[{scenario}] baseline', flush=True)
    baseline_payload, command, elapsed, raw_hash = _run_replay(
        scenario_dir / 'baseline.json', scenario, rounds=rounds, teams=teams,
        name_seed=seed)
    repeat_payload, repeat_command, repeat_elapsed, repeat_hash = _run_replay(
        scenario_dir / 'baseline-repeat.json', scenario, rounds=rounds,
        teams=teams, name_seed=seed)
    deterministic = (_deterministic_content(baseline_payload)
                     == _deterministic_content(repeat_payload))
    if not deterministic:
        raise AssertionError(f'{scenario}: seeded baseline replay was not deterministic')
    commands = [command, repeat_command]
    baseline_subject = summarise_team(baseline_payload, 0)
    families = {}
    policy_results = {}
    selected_families = list(POLICY_FAMILIES)
    if smoke:
        selected_families = selected_families[:2]
    for family in selected_families:
        points = [{
            'name': 'baseline', 'level': BASELINE_LEVEL[family], 'spec': {},
            'result': baseline_subject,
        }]
        probes = POLICY_FAMILIES[family]
        if smoke:
            probes = probes[:1]
        for name, level, spec in probes:
            print(f'[{scenario}] {name}', flush=True)
            payload, probe_command, probe_elapsed, probe_hash = _run_replay(
                scenario_dir / f'{name}.json', scenario, policy_spec=spec,
                rounds=rounds, teams=teams, name_seed=seed)
            result = summarise_team(payload, 0)
            classification = classify_effect(result, baseline_subject)
            entry = {
                'name': name, 'level': level, 'spec': spec,
                'elapsed_seconds': probe_elapsed, 'raw_sha256': probe_hash,
                'result': result, 'classification': classification,
                'dominance': _dominance(result, baseline_subject),
            }
            points.append(entry)
            policy_results[name] = entry
            commands.append(probe_command)
        families[family] = {
            'points': points,
            'monotonicity': {metric: monotonicity(points, metric)
                             for metric in METRICS},
        }

    profile_results = [summarise_team(baseline_payload, index)
                       for index in range(teams)]
    profile_results.sort(key=lambda row: (row['final_performance_index'],
                                          -row['rank']))
    worst = profile_results[0]
    best = profile_results[-1]
    worst_index = next(index for index, team in enumerate(baseline_payload['teams'])
                       if team['starter_profile'] == worst['starter_profile'])

    # The adversarial policy is transparent and reproducible: take only a
    # one-factor level whose final PI beats baseline by >0.01, choosing the
    # best PI (then income/cash) within each family, and compose those levels.
    selected = []
    skilled_spec = {}
    for family, family_data in families.items():
        winner = max(family_data['points'], key=lambda point: (
            point['result']['final_performance_index'],
            point['result']['cumulative_net_income'],
            point['result']['final_cash']))
        if (winner['name'] != 'baseline'
                and winner['result']['final_performance_index']
                > baseline_subject['final_performance_index'] + 0.01):
            selected.append({'family': family, 'name': winner['name'],
                             'level': winner['level'], 'spec': winner['spec']})
            skilled_spec.update(winner['spec'])

    adversarial = None
    if skilled_spec:
        print(f'[{scenario}] skilled policy on worst profile '
              f'{worst["starter_profile"]}', flush=True)
        payload, skilled_command, skilled_elapsed, skilled_hash = _run_replay(
            scenario_dir / 'skilled-worst-profile.json', scenario,
            policy_spec=skilled_spec, subject=worst_index, rounds=rounds,
            teams=teams, name_seed=seed)
        commands.append(skilled_command)
        skilled_worst = summarise_team(payload, worst_index)
        best_index = next(index for index, team in enumerate(payload['teams'])
                          if team['starter_profile'] == best['starter_profile'])
        best_opponent = summarise_team(payload, best_index)
        same_field = [summarise_team(payload, index) for index in range(teams)]
        same_field_pis = [row['final_performance_index'] for row in same_field]
        adversarial = {
            'selection_rule': ('per family, compose the level with the highest '
                               'team-0 final PI only when it improves baseline '
                               'by more than 0.01; ties use income then cash'),
            'selected_levels': selected,
            'policy_spec': skilled_spec,
            'baseline_worst_profile': worst,
            'baseline_best_profile': best,
            'skilled_worst_profile_result': skilled_worst,
            'same_field_best_starting_profile_result': best_opponent,
            'overcame_best_starting_profile_in_same_field': (
                skilled_worst['final_performance_index']
                > best_opponent['final_performance_index']
                and skilled_worst['rank'] < best_opponent['rank']),
            'skilled_worst_pi_gain': round(
                skilled_worst['final_performance_index']
                - worst['final_performance_index'], 6),
            'same_field_pi_spread': round(max(same_field_pis) - min(same_field_pis), 6),
            'elapsed_seconds': skilled_elapsed,
            'raw_sha256': skilled_hash,
        }

    baseline_pis = [row['final_performance_index'] for row in profile_results]
    return {
        'scenario': scenario,
        'baseline': {
            'subject': baseline_subject,
            'profiles': profile_results,
            'pi_min': min(baseline_pis),
            'pi_median': statistics.median(baseline_pis),
            'pi_max': max(baseline_pis),
            'pi_spread': round(max(baseline_pis) - min(baseline_pis), 6),
            'raw_sha256': raw_hash,
            'repeat_raw_sha256': repeat_hash,
            'elapsed_seconds': elapsed,
            'repeat_elapsed_seconds': repeat_elapsed,
            'seeded_repeat_is_identical': deterministic,
        },
        'families': families,
        'adversarial_profile_test': adversarial,
        'commands': commands,
    }


def _verify_candidate(candidate):
    resolved = subprocess.run(
        ['git', 'rev-parse', candidate], cwd=REPO, text=True,
        capture_output=True, check=True).stdout.strip()
    if resolved != CANDIDATE_REVISION:
        raise SystemExit(f'candidate must resolve to {CANDIDATE_REVISION}, got {resolved}')
    # Only this evidence directory may differ from the certified mechanics.
    result = subprocess.run([
        'git', 'diff', '--quiet', CANDIDATE_REVISION, '--',
        'backend/core', 'backend/scenarios',
    ], cwd=REPO)
    if result.returncode:
        raise SystemExit('engine or scenario content differs from the certified candidate')
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--candidate', default=CANDIDATE_REVISION)
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--teams', type=int, default=8)
    parser.add_argument('--name-seed', type=int, default=20260927)
    parser.add_argument('--scenarios', nargs='+', choices=tuple(SCENARIOS),
                        default=tuple(SCENARIOS))
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--smoke', action='store_true')
    options = parser.parse_args()
    if options.rounds != 10 and not options.smoke:
        raise SystemExit('certification evidence requires the full 10-round horizon')
    if options.teams != 8 and not options.smoke:
        raise SystemExit('starter-profile evidence requires the full 8-team field')
    if options.jobs < 1:
        raise SystemExit('--jobs must be positive')
    candidate = _verify_candidate(options.candidate)

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='gsp-candidate-sensitivity-') as temp:
        temp_root = pathlib.Path(temp)
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(options.jobs, len(options.scenarios))) as pool:
            futures = {
                scenario: pool.submit(
                    _measure_scenario, scenario, rounds=options.rounds,
                    teams=options.teams, seed=options.name_seed,
                    smoke=options.smoke, temp_root=temp_root)
                for scenario in options.scenarios
            }
            results = {scenario: futures[scenario].result()
                       for scenario in options.scenarios}

    harness_revision = subprocess.run(
        ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True,
        capture_output=True, check=True).stdout.strip()
    report = {
        'method': {
            'design': ('deterministic seeded, full-horizon, 8-profile field; '
                       'one-factor-at-a-time sweeps plus a disclosed composed '
                       'policy applied to the weakest baseline profile'),
            'rounds': options.rounds,
            'teams': options.teams,
            'name_seed': options.name_seed,
            'adaptive_production': '110% of the prior round units sold',
            'decision_policy': 'all non-subject teams retain the competent baseline',
            'limitations': [
                'The engine is deterministic; seeded repeats establish repeatability but do not provide stochastic confidence intervals.',
                'One-factor sweeps describe local policy paths, not every interaction in the combinatorial decision space.',
                'The composed skilled policy is selected in-sample on team 0 and is tested once on the weakest profile; it is not a holdout-trained optimizer.',
                'The replay writes locked decisions directly, as the pre-existing calibration harness does; results measure resolution mechanics, not API usability.',
                'Debt/equity evidence varies legal-sized debt and repayment flows; it does not force surplus equity issuance when no funding shortfall exists.',
            ],
        },
        'provenance': {
            'candidate_mechanics_revision': candidate,
            'harness_revision': harness_revision,
            'stage1_runtime_replay_sha256': _sha256(REPLAY),
            'baseline_policy_sha256': _sha256(BASELINE),
            'scenario_sha256': {
                scenario: _sha256(REPO / 'backend' / 'scenarios' / filename)
                for scenario, filename in SCENARIOS.items()
                if scenario in options.scenarios
            },
            'engine_and_scenarios_match_candidate': True,
            'commands': [command for result in results.values()
                         for command in result.pop('commands')],
        },
        'scenarios': results,
        'wall_seconds': round(time.monotonic() - started, 3),
    }
    options.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(f'wrote {options.output}', flush=True)
    for scenario, result in results.items():
        baseline = result['baseline']
        adversarial = result['adversarial_profile_test']
        print(f'{scenario}: baseline PI spread={baseline["pi_spread"]:.4f}; '
              f'deterministic={baseline["seeded_repeat_is_identical"]}; '
              f'skilled overcame best start='
              f'{adversarial and adversarial["overcame_best_starting_profile_in_same_field"]}',
              flush=True)


if __name__ == '__main__':
    main()
