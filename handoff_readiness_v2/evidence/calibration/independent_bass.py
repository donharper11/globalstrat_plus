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

  flat        M_r = pop * (1 + g)          -- what events.py computes today:
                                              growth applied once to the static
                                              authored population, every round.
  compounding M_r = pop * (1 + g) ** r     -- growth that accumulates, which is
                                              what a ten-round market needs.
"""
import argparse
import json
import pathlib
import sys

import yaml


def load_scenario(path):
    return yaml.safe_load(pathlib.Path(path).read_text())


def segment_rows(scenario):
    """(market, segment, population, p, q, growth, revenue_per_unit) tuples."""
    rows = []
    for seg in scenario['customer_segments']:
        pops = seg.get('populations') or {}
        growths = seg.get('growth_rates') or {}
        for market_code, population in sorted(pops.items()):
            rows.append({
                'market': market_code,
                'segment': seg['name'],
                'population': float(population),
                'p': float(seg['bass_p']),
                'q': float(seg['bass_q']),
                'growth': float(growths.get(market_code, 0) or 0),
                'revenue_per_unit': float(seg.get('revenue_per_unit') or 0),
            })
    return rows


def trajectory(row, rounds, regime):
    """Adoption pool, cumulative adopters and remaining pool, per round.

    No team behaviour and no AI: this is the pool the field competes over, so
    it is the quantity the calibration target is stated in.
    """
    p, q, pop, g = row['p'], row['q'], row['population'], row['growth']
    out, cumulative = [], 0.0
    for r in range(1, rounds + 1):
        if regime == 'flat':
            M = pop + pop * g              # events.py: applied once, per round
        elif regime == 'compounding':
            M = pop * ((1 + g) ** r)
        elif regime == 'static':
            M = pop                        # no growth at all, for reference
        else:
            raise ValueError(regime)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario',
                    default='backend/scenarios/consumer_electronics_2026.yaml')
    ap.add_argument('--rounds', type=int, default=10)
    ap.add_argument('--json', help='write full results here')
    args = ap.parse_args()

    scenario = load_scenario(args.scenario)
    rows = segment_rows(scenario)
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
    print(f"  {'round':>5}  {'flat (today)':>16}  {'compounding':>16}  {'ratio':>7}")
    flat, comp = totals('flat', 'pool'), totals('compounding', 'pool')
    for i in range(args.rounds):
        ratio = (comp[i] / flat[i]) if flat[i] else float('nan')
        print(f'  {i+1:>5}  {flat[i]:>16,.0f}  {comp[i]:>16,.0f}  {ratio:>7.2f}x')
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
