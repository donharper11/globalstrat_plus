#!/usr/bin/env python3
"""An independent Bass/adoption simulator for GSP-CRV2-11 Stage 1.

Imports no engine code, on purpose. The point is to reproduce what the authored
parameters *specify* and compare that against what the engine *delivers*; a
simulator that shared a helper with the engine would agree with it about a
shared mistake.

Everything here is read from the scenario YAML and the arithmetic is written
out longhand from the Bass model:

    pool_r = (p + q * N_{r-1} / M_r) * (M_r - N_{r-1})

BECSR's demand diagnostic established the method and the expectation: the
engine was faithful to 0.2% and the defect was in the seeded market, not the
code. This is the same test asked of this engine.

Two population regimes are modelled, because Stage 1 item 3 turns on the
difference:

  flat        M_r = pop * (1 + g)          -- the pre-CRV2-11 historical
                                              runtime: growth applied once to
                                              the static authored population.
  compounding M_r = pop * (1 + g) ** r     -- the current shipped runtime:
                                              growth accumulates each round.
"""
import argparse
import json
import pathlib
import sys

import yaml


def load_scenario(path):
    return yaml.safe_load(pathlib.Path(path).read_text())


def _market_paths(scenario, rounds):
    """Independent replay of the authored market growth/demand schedule.

    ``events.update_market_conditions`` grows a customer segment from its
    market's base growth rate plus the scheduled round modifier.  The YAML also
    contains informational segment ``growth_rates`` fields, but the engine does
    not read them; using those here would make a tidy but unfaithful replay.
    """
    paths = {}
    condition_rows = scenario.get('market_conditions') or {}
    for market in scenario['markets']:
        code = market['code']
        base_growth = float(market.get('base_growth_rate') or 0)
        scheduled = {
            int(row[0]): row
            for row in condition_rows.get(code, [])
        }
        paths[code] = [
            {
                'growth': base_growth + float(scheduled.get(r, [r, 0])[1] or 0),
                # Demand multipliers are one-round demand shocks, not a
                # population-growth rate, and therefore do not compound.
                'demand_multiplier': float(scheduled.get(r, [r, 0, 0, 0, 1])[4] or 1),
            }
            for r in range(1, rounds + 1)
        ]
    return paths


def segment_rows(scenario, rounds):
    """(market, segment, population, p, q, market path, revenue) tuples."""
    rows = []
    paths = _market_paths(scenario, rounds)
    for seg in scenario['customer_segments']:
        pops = seg.get('populations') or {}
        for market_code, population in sorted(pops.items()):
            rows.append({
                'market': market_code,
                'segment': seg['name'],
                'population': float(population),
                'p': float(seg['bass_p']),
                'q': float(seg['bass_q']),
                'market_path': paths[market_code],
                'revenue_per_unit': float(seg.get('revenue_per_unit') or 0),
            })
    return rows


def trajectory(row, rounds, regime):
    """Adoption pool, cumulative adopters and remaining pool, per round.

    No team behaviour and no AI: this is the pool the field competes over, so
    it is the quantity the calibration target is stated in.
    """
    p, q, pop = row['p'], row['q'], row['population']
    out, cumulative = [], 0.0
    for r in range(1, rounds + 1):
        market_state = row['market_path'][r - 1]
        if regime == 'flat':
            # Pre-CRV2-11 engine: current period's growth applied once to the
            # authored population. Conditions can vary M, but no prior growth
            # carries forward.
            M = pop * (1 + market_state['growth'])
        elif regime == 'compounding':
            M = pop
            for prior in row['market_path'][:r]:
                M *= 1 + prior['growth']
        elif regime == 'static':
            M = pop                        # no growth at all, for reference
        else:
            raise ValueError(regime)
        M *= market_state['demand_multiplier']
        remaining = max(M - cumulative, 0.0)
        pool = (p + q * cumulative / max(M, 1)) * remaining if M > 0 else 0.0
        pool = max(pool, 0.0)
        cumulative += pool
        out.append({
            'round': r,
            'M': M,
            'N_prev': cumulative - pool,
            'pool': pool,
            'N': cumulative,
            'remaining': max(M - cumulative, 0.0),
            'penetration': (cumulative / M) if M > 0 else 0.0,
            'industry_revenue': pool * row['revenue_per_unit'],
        })
    return out


def compare_runtime(path, scenario):
    """Replay delivered pools from exported runtime state without engine code.

    The runtime harness records its effective population and the published
    human allocation for every segment-market-round.  This function uses only
    those observations plus YAML Bass parameters.  It therefore independently
    checks the one thing the field configuration must not change: whether the
    engine's published adoption pool equals the authored Bass equation when
    supplied the same ``M`` and prior *human* ``N`` (Fix A deliberately keeps
    AI take out of N).
    """
    delivered = json.loads(pathlib.Path(path).read_text())
    params = {
        (row['market'], row['segment']): row
        for row in segment_rows(scenario, rounds=1)
    }
    cumulative_human = {}
    comparisons = []
    for observed in sorted(delivered['rows'],
                           key=lambda row: (row['market'], row['segment'], row['round'])):
        key = (observed['market'], observed['segment'])
        source = params[key]
        M = float(observed['population'])
        N_prev = cumulative_human.get(key, 0.0)
        expected = (source['p'] + source['q'] * N_prev / max(M, 1)) * max(M - N_prev, 0)
        expected = max(expected, 0.0)
        actual = float(observed['adoption_pool'])
        comparisons.append({
            'round': observed['round'], 'market': key[0], 'segment': key[1],
            'effective_population': M, 'human_n_prev': N_prev,
            'independent_pool': expected, 'engine_pool': actual,
            'absolute_divergence': abs(expected - actual),
            'relative_divergence': (abs(expected - actual) / expected
                                    if expected else 0.0),
            'ai_adopters': float(observed['ai_adopters']),
            'human_adopters': float(observed['human_adopters']),
            'unserved_adopters': float(observed['unserved_adopters']),
        })
        cumulative_human[key] = N_prev + float(observed['human_adopters'])
    return {
        'scenario': delivered['scenario'],
        'runtime_code_revision': delivered.get('code_revision'),
        'observations': comparisons,
        'max_absolute_divergence': max(row['absolute_divergence'] for row in comparisons),
        'max_relative_divergence': max(row['relative_divergence'] for row in comparisons),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario',
                    default='backend/scenarios/consumer_electronics_2026.yaml')
    ap.add_argument('--rounds', type=int, default=10)
    ap.add_argument('--json', help='write full results here')
    ap.add_argument('--runtime-input',
                    help='Stage 1 runtime export to independently compare')
    ap.add_argument('--comparison-json',
                    help='where to write the runtime comparison JSON')
    args = ap.parse_args()

    scenario = load_scenario(args.scenario)
    if args.runtime_input:
        comparison = compare_runtime(args.runtime_input, scenario)
        rendered = json.dumps(comparison, indent=2, sort_keys=True)
        if args.comparison_json:
            pathlib.Path(args.comparison_json).write_text(rendered + '\n')
        print(f"runtime observations : {len(comparison['observations'])}")
        print(f"max absolute divergence: {comparison['max_absolute_divergence']:.6f}")
        print(f"max relative divergence: {comparison['max_relative_divergence']:.9%}")
        return
    rows = segment_rows(scenario, args.rounds)
    results = {}
    for regime in ('flat', 'compounding', 'static'):
        results[regime] = {
            f"{r['market']}|{r['segment']}": trajectory(r, args.rounds, regime)
            for r in rows
        }

    def totals(regime, field):
        return [sum(results[regime][k][i][field] for k in results[regime])
                for i in range(args.rounds)]

    print(f'scenario : {args.scenario}')
    print(f'segments : {len(rows)} (segment x market pairs)')
    print(f'rounds   : {args.rounds}')
    print()
    print('Adoption pool per round, whole economy (units):')
    print(f"  {'round':>5}  {'flat (pre-CRV2-11)':>20}  {'compounding (current)':>22}  {'ratio':>7}")
    flat, comp = totals('flat', 'pool'), totals('compounding', 'pool')
    for i in range(args.rounds):
        ratio = (comp[i] / flat[i]) if flat[i] else float('nan')
        print(f'  {i+1:>5}  {flat[i]:>20,.0f}  {comp[i]:>22,.0f}  {ratio:>7.2f}x')
    print()
    print(f'  round 10 / round 1, flat        : {flat[-1] / flat[0]:.3f}')
    print(f'  round 10 / round 1, compounding : {comp[-1] / comp[0]:.3f}')
    print()
    print('Market size M per round, whole economy (people):')
    fM, cM = totals('flat', 'M'), totals('compounding', 'M')
    for i in (0, 4, 9):
        print(f'  round {i+1:>2}: flat {fM[i]:>15,.0f}   compounding {cM[i]:>15,.0f}')
    print()
    pen_f = [sum(results['flat'][k][i]['N'] for k in results['flat'])
             / sum(results['flat'][k][i]['M'] for k in results['flat'])
             for i in range(args.rounds)]
    print('Penetration N/M, flat regime:')
    for i in (0, 4, 9):
        print(f'  round {i+1:>2}: {pen_f[i]:.1%}')

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(results, indent=2))
        print(f'\nwrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
