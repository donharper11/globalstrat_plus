#!/usr/bin/env python3
"""Full-horizon evidence for the repaired sales-staff reach curve.

This runner varies decisions only.  It measures the staffing range on its own,
then under extra production and promotion, and finally applies a disclosed
combined policy to a holdout team.  Every point is a fresh ten-round replay.
"""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import subprocess
import tempfile
import time

from competition_sensitivity_measurements import (
    SCENARIOS,
    _deterministic_content,
    _dominance,
    _run_replay,
    classify_effect,
    monotonicity,
    summarise_team,
)


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEFAULT_OUTPUT = HERE / 'sales_staff_repair_measurements.json'
CANDIDATE_REVISION = '49b547fd30c954c44049b1f34e79e5e3a0d5dd3e'
MECHANICS_REVISION = 'f2650fb0bd132e42ce29af26b6e9a01217f0a034'
SUBJECT_INDEX = 0
HOLDOUT_INDEX = 6
SALES_LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
INTERACTION_LEVELS = (0.0, 0.5, 1.0, 1.5)
METRICS = (
    'cumulative_revenue', 'cumulative_net_income', 'cumulative_units_sold',
    'final_cash', 'final_performance_index', 'final_satisfaction_score',
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _actual_staff(result):
    return [row['decision']['sales_staff_total']
            for row in result['trajectory']]


def _point(name, level, spec, result, *, elapsed=0.0, raw_hash=None):
    return {
        'name': name,
        'level': level,
        'spec': spec,
        'elapsed_seconds': elapsed,
        'raw_sha256': raw_hash,
        'actual_sales_staff_by_round': _actual_staff(result),
        'result': result,
    }


def _curve(points, reference):
    ordered = sorted(points, key=lambda point: point['level'])
    for point in ordered:
        point['classification_vs_reference'] = classify_effect(
            point['result'], reference['result'])
        point['dominance_vs_reference'] = _dominance(
            point['result'], reference['result'])
    return {
        'reference': reference['name'],
        'points': ordered,
        'monotonicity': {
            metric: monotonicity(ordered, metric) for metric in METRICS
        },
        'no_free_win': no_free_win(ordered),
    }


def no_free_win(points, tolerance=1e-6):
    """State whether positive staffing produces value that zero staff cannot.

    This deliberately reports commercial, PI and income tests separately.
    Staffing can be a legitimate trade-off without every metric rising.
    """
    zero = next(point for point in points if point['level'] == 0.0)['result']
    positive = [point['result'] for point in points if point['level'] > 0.0]
    keys = ('cumulative_revenue', 'cumulative_units_sold',
            'cumulative_net_income', 'final_cash', 'final_performance_index')
    zero_dominates = all(
        all(zero[key] >= result[key] - tolerance for key in keys)
        and any(zero[key] > result[key] + tolerance for key in keys)
        for result in positive
    )
    return {
        'positive_staff_commercially_beats_zero': any(
            result['cumulative_revenue'] > zero['cumulative_revenue'] + tolerance
            or result['cumulative_units_sold']
            > zero['cumulative_units_sold'] + tolerance
            for result in positive
        ),
        'positive_staff_pi_beats_zero': any(
            result['final_performance_index']
            > zero['final_performance_index'] + tolerance
            for result in positive
        ),
        'positive_staff_income_beats_zero': any(
            result['cumulative_net_income']
            > zero['cumulative_net_income'] + tolerance
            for result in positive
        ),
        'zero_staff_dominates_every_positive_point': zero_dominates,
    }


def _run_point(directory, scenario, name, level, spec, subject, options):
    payload, command, elapsed, raw_hash = _run_replay(
        directory / f'{name}.json', scenario, policy_spec=spec,
        subject=subject, rounds=options.rounds, teams=options.teams,
        name_seed=options.name_seed,
    )
    result = summarise_team(payload, subject)
    return (_point(name, level, spec, result, elapsed=elapsed,
                   raw_hash=raw_hash), command)


def _measure_scenario(scenario, options, temp_root):
    directory = temp_root / scenario
    directory.mkdir(parents=True, exist_ok=True)
    print(f'[{scenario}] baseline + deterministic repeat', flush=True)
    baseline_payload, baseline_command, baseline_elapsed, baseline_hash = (
        _run_replay(directory / 'baseline.json', scenario,
                    rounds=options.rounds, teams=options.teams,
                    name_seed=options.name_seed))
    repeat_payload, repeat_command, repeat_elapsed, repeat_hash = _run_replay(
        directory / 'baseline-repeat.json', scenario,
        rounds=options.rounds, teams=options.teams,
        name_seed=options.name_seed)
    deterministic = (_deterministic_content(baseline_payload)
                     == _deterministic_content(repeat_payload))
    if not deterministic:
        raise AssertionError(f'{scenario}: seeded baseline was not deterministic')
    commands = [baseline_command, repeat_command]
    baseline_result = summarise_team(baseline_payload, SUBJECT_INDEX)
    baseline_point = _point('baseline_sales_x1', 1.0, {}, baseline_result,
                            elapsed=baseline_elapsed, raw_hash=baseline_hash)

    sales_levels = SALES_LEVELS if not options.smoke else (0.0, 1.0)
    interaction_levels = (INTERACTION_LEVELS if not options.smoke
                          else (0.0, 1.0))
    sales_points = [baseline_point]
    for level in sales_levels:
        if level == 1.0:
            continue
        name = f'sales_x{str(level).replace(".", "_")}'
        print(f'[{scenario}] {name}', flush=True)
        point, command = _run_point(
            directory, scenario, name, level,
            {'sales_staff_multiplier': level}, SUBJECT_INDEX, options)
        sales_points.append(point)
        commands.append(command)

    interactions = {}
    for family, fixed_spec in (
        ('production_x1_25', {'production_multiplier': 1.25}),
        ('promotion_x1_5', {'promotion_multiplier': 1.5}),
    ):
        points = []
        for level in interaction_levels:
            name = f'{family}_sales_x{str(level).replace(".", "_")}'
            spec = dict(fixed_spec, sales_staff_multiplier=level)
            print(f'[{scenario}] {name}', flush=True)
            point, command = _run_point(
                directory, scenario, name, level, spec, SUBJECT_INDEX,
                options)
            points.append(point)
            commands.append(command)
        reference = next(point for point in points if point['level'] == 1.0)
        interactions[family] = _curve(points, reference)

    holdout_spec = {
        'production_multiplier': 1.25,
        'promotion_multiplier': 1.5,
        'sales_staff_multiplier': 1.0,
    }
    print(f'[{scenario}] combined policy on holdout team {HOLDOUT_INDEX}',
          flush=True)
    holdout_point, holdout_command = _run_point(
        directory, scenario, 'holdout_combined_policy', 1.0,
        holdout_spec, HOLDOUT_INDEX, options)
    commands.append(holdout_command)
    holdout_baseline = summarise_team(baseline_payload, HOLDOUT_INDEX)
    return {
        'baseline_repeat': {
            'identical': deterministic,
            'raw_sha256': baseline_hash,
            'repeat_raw_sha256': repeat_hash,
            'elapsed_seconds': baseline_elapsed,
            'repeat_elapsed_seconds': repeat_elapsed,
        },
        'sales_range': _curve(sales_points, baseline_point),
        'interactions': interactions,
        'holdout_policy': {
            'subject_team_index': HOLDOUT_INDEX,
            'starter_profile': holdout_result_profile(holdout_baseline),
            'spec': holdout_spec,
            'baseline': holdout_baseline,
            'result': holdout_point,
            'classification': classify_effect(
                holdout_point['result'], holdout_baseline),
            'dominance': _dominance(
                holdout_point['result'], holdout_baseline),
        },
        'commands': commands,
    }


def holdout_result_profile(result):
    return result['starter_profile']


def _verify_revisions():
    candidate = subprocess.run(
        ['git', 'rev-parse', CANDIDATE_REVISION], cwd=REPO, text=True,
        capture_output=True, check=True).stdout.strip()
    mechanics = subprocess.run(
        ['git', 'rev-parse', MECHANICS_REVISION], cwd=REPO, text=True,
        capture_output=True, check=True).stdout.strip()
    if candidate != CANDIDATE_REVISION or mechanics != MECHANICS_REVISION:
        raise SystemExit('candidate or mechanics revision does not resolve exactly')
    expected = {
        'backend/core/engine/preference_engine.py',
        'backend/core/views/research_reports.py',
        'backend/core/tests/test_sales_staff_distribution.py',
    }
    changed = set(subprocess.run(
        ['git', 'diff', '--name-only', CANDIDATE_REVISION, '--',
         'backend/core', 'backend/scenarios'], cwd=REPO, text=True,
        capture_output=True, check=True).stdout.splitlines())
    if changed != expected:
        raise SystemExit(f'unexpected mechanics/scenario changes: {sorted(changed)}')
    return candidate, mechanics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--teams', type=int, default=8)
    parser.add_argument('--name-seed', type=int, default=20260927)
    parser.add_argument('--scenarios', nargs='+', choices=tuple(SCENARIOS),
                        default=tuple(SCENARIOS))
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--smoke', action='store_true')
    options = parser.parse_args()
    if not options.smoke and (options.rounds != 10 or options.teams != 8):
        raise SystemExit('evidence requires ten rounds and eight teams')
    if options.jobs < 1:
        raise SystemExit('--jobs must be positive')
    if options.teams <= HOLDOUT_INDEX:
        raise SystemExit(f'holdout requires at least {HOLDOUT_INDEX + 1} teams')
    candidate, mechanics = _verify_revisions()

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='gsp-sales-staff-repair-') as temp:
        temp_root = pathlib.Path(temp)
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(options.jobs, len(options.scenarios))) as pool:
            futures = {
                scenario: pool.submit(
                    _measure_scenario, scenario, options, temp_root)
                for scenario in options.scenarios
            }
            results = {scenario: futures[scenario].result()
                       for scenario in options.scenarios}

    commands = [command for result in results.values()
                for command in result.pop('commands')]
    report = {
        'method': {
            'design': ('deterministic ten-round range sweep; matched staffing '
                       'curves with +25% production and +50% promotion; one '
                       'combined policy applied to a holdout team'),
            'rounds': options.rounds,
            'teams': options.teams,
            'name_seed': options.name_seed,
            'subject_team_index': SUBJECT_INDEX,
            'holdout_team_index': HOLDOUT_INDEX,
            'adaptive_production': '110% of prior-round units sold',
            'limitations': [
                'The engine is deterministic, so repeatability is measured but there are no stochastic confidence intervals.',
                'The grid covers three disclosed policy paths, not the full combinatorial decision space.',
                'The holdout policy is fixed in advance and is not an optimizer.',
                'Locked decisions are written through the established replay harness; this measures mechanics rather than API usability.',
            ],
        },
        'provenance': {
            'candidate_revision': candidate,
            'mechanics_revision': mechanics,
            'harness_revision': subprocess.run(
                ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True,
                capture_output=True, check=True).stdout.strip(),
            'runner_sha256': _sha256(pathlib.Path(__file__)),
            'scenario_sha256': {
                scenario: _sha256(REPO / 'backend' / 'scenarios' / filename)
                for scenario, filename in SCENARIOS.items()
                if scenario in options.scenarios
            },
            'commands': commands,
        },
        'scenarios': results,
        'wall_seconds': round(time.monotonic() - started, 3),
    }
    options.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(f'wrote {options.output}', flush=True)
    for scenario, result in results.items():
        finding = result['sales_range']['no_free_win']
        print(f'{scenario}: deterministic='
              f'{result["baseline_repeat"]["identical"]}; '
              f'commercial-positive={finding["positive_staff_commercially_beats_zero"]}; '
              f'PI-positive={finding["positive_staff_pi_beats_zero"]}; '
              f'zero-dominates={finding["zero_staff_dominates_every_positive_point"]}',
              flush=True)


if __name__ == '__main__':
    main()
