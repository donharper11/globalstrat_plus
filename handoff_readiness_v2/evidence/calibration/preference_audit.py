#!/usr/bin/env python3
"""GSP-CRV2-11 Stage 5 items 1-4: audit the authored segment preferences.

Reads the shipped scenario YAML directly and imports no engine code, so the
report is evidence about the *authored data* rather than about the engine that
consumes it.  Four questions, one per Stage 5 item:

1. ideal-in-range  -- is every ``ideal_value`` inside its own feature's
   ``min_value``..``max_value``?
2. degeneracy      -- does a segment-market spread its weight, or is it a
   single-term score (Herfindahl on the weight vector) or all-zero?
3. dead weight     -- is positive weight spent on a platform feature whose
   ceiling is 0 on *every* generation unlocked by that round?  Reported per
   round 1..10, because a Gen-2 feature is dead only until Gen 2 unlocks.
4. tolerance       -- the Gaussian half-fit distance (``tolerance *
   sqrt(2 ln 2)``) as a fraction of the feature's own range.  Wide enough and
   every team scores alike (decorative); narrow enough and only an exact match
   scores (cliff).

Usage:  python3 preference_audit.py [--json OUT]
"""
import argparse
import json
import math
import pathlib
import statistics

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCENARIO_DIR = REPO / 'backend' / 'scenarios'
SCENARIOS = (
    'consumer_electronics_2026.yaml',
    'clean_energy_tech_2026.yaml',
    'media_entertainment_2026.yaml',
)
ROUNDS = range(1, 11)

# A Gaussian scores 0.5 at this many tolerances from the ideal.
HALF_FIT = math.sqrt(2 * math.log(2))
# Half-fit distance beyond this fraction of the feature range: every reachable
# level scores close to 1.0, so the term cannot discriminate between teams.
DECORATIVE_ABOVE = 1.0
# Half-fit distance below this fraction: only a near-exact match scores.
CLIFF_BELOW = 0.05


def _ceiling(value):
    """Return the ceiling from YAML's ``[ceiling, starting]`` pair."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else 0
    return float(value or 0)


def _feature_defs(data):
    return {
        feature['code']: feature
        for layer in (data.get('features') or {}).values()
        for feature in (layer or [])
        if isinstance(feature, dict) and feature.get('code')
    }


def _generations(data):
    return sorted((data.get('platform_generations') or []),
                  key=lambda gen: gen.get('generation_order', 0))


def _reachable_ceiling(generations, code, round_number):
    """Best ceiling for ``code`` across every generation unlocked by a round."""
    available = [gen for gen in generations
                 if int(gen.get('unlock_round', 0) or 0) <= round_number]
    if not available:
        return 0.0
    return max(_ceiling((gen.get('ceilings') or {}).get(code, 0))
               for gen in available)


def audit(name):
    import yaml
    data = yaml.safe_load((SCENARIO_DIR / name).read_text())
    features = _feature_defs(data)
    generations = _generations(data)
    gen_rounds = {gen.get('generation_order'): int(gen.get('unlock_round', 0) or 0)
                  for gen in generations}

    out_of_range = []
    dead_weight = []
    tolerance_rows = []
    degenerate = []
    prefs_total = 0

    for segment, by_market in sorted((data.get('segment_preferences') or {}).items()):
        for market, prefs in sorted((by_market or {}).items()):
            weights = []
            for pref in prefs or []:
                if not isinstance(pref, (list, tuple)) or len(pref) < 4:
                    continue
                code, ideal, weight, tolerance = pref[:4]
                feature = features.get(code)
                if feature is None:
                    continue
                prefs_total += 1
                ideal, weight, tolerance = float(ideal), float(weight), float(tolerance)
                weights.append(weight)
                low = float(feature.get('min_value', 0))
                high = float(feature.get('max_value', 20))
                span = high - low

                if not low <= ideal <= high:
                    out_of_range.append({
                        'segment': segment, 'market': market, 'feature': code,
                        'ideal': ideal, 'min': low, 'max': high,
                    })

                if feature.get('layer') == 'platform' and weight > 0:
                    dead_rounds = [r for r in ROUNDS
                                   if _reachable_ceiling(generations, code, r) <= 0]
                    if dead_rounds:
                        dead_weight.append({
                            'segment': segment, 'market': market, 'feature': code,
                            'weight': weight, 'ideal': ideal,
                            'dead_rounds': dead_rounds,
                            'unlocks_round': (min(r for r in ROUNDS if r not in dead_rounds)
                                              if len(dead_rounds) < len(list(ROUNDS))
                                              else None),
                        })

                half_fit = tolerance * HALF_FIT
                ratio = (half_fit / span) if span else float('inf')
                verdict = ('decorative' if ratio > DECORATIVE_ABOVE
                           else 'cliff' if ratio < CLIFF_BELOW
                           else 'discriminating')
                tolerance_rows.append({
                    'segment': segment, 'market': market, 'feature': code,
                    'layer': feature.get('layer'), 'tolerance': tolerance,
                    'range': span, 'half_fit_distance': round(half_fit, 3),
                    'half_fit_as_range_fraction': round(ratio, 4),
                    'verdict': verdict,
                    # Worst case a team can be from the ideal inside the range.
                    'worst_case_fit': round(math.exp(
                        -(max(ideal - low, high - ideal) ** 2) / (2 * tolerance ** 2)), 4)
                    if tolerance > 0 else 0.0,
                })

            if weights:
                total = sum(weights)
                share = [w / total for w in weights] if total else []
                degenerate.append({
                    'segment': segment, 'market': market,
                    'terms': len(weights), 'weight_sum': round(total, 4),
                    'zero_weights': sum(1 for w in weights if w == 0),
                    'max_weight_share': round(max(share), 4) if share else None,
                    'herfindahl': round(sum(s * s for s in share), 4) if share else None,
                    'effective_terms': round(1 / sum(s * s for s in share), 2)
                    if share and sum(s * s for s in share) else None,
                })

    verdict_counts = {}
    for row in tolerance_rows:
        verdict_counts[row['verdict']] = verdict_counts.get(row['verdict'], 0) + 1

    return {
        'scenario': name,
        'generation_unlock_rounds': gen_rounds,
        'preferences_audited': prefs_total,
        'segment_markets': len(degenerate),
        'out_of_range_ideals': out_of_range,
        'dead_weight': dead_weight,
        'dead_weight_total': round(sum(row['weight'] for row in dead_weight), 4),
        'tolerance_verdicts': verdict_counts,
        'tolerance_rows': tolerance_rows,
        'tolerance_summary': {
            'min': min((r['half_fit_as_range_fraction'] for r in tolerance_rows),
                       default=None),
            'median': round(statistics.median(
                [r['half_fit_as_range_fraction'] for r in tolerance_rows]), 4)
            if tolerance_rows else None,
            'max': max((r['half_fit_as_range_fraction'] for r in tolerance_rows),
                       default=None),
        },
        'weight_profiles': degenerate,
        'degenerate_segment_markets': [
            row for row in degenerate
            if row['weight_sum'] == 0 or (row['max_weight_share'] or 0) >= 0.90
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', type=pathlib.Path,
                        default=HERE / 'preference_audit.json')
    options = parser.parse_args()

    reports = [audit(name) for name in SCENARIOS]
    options.json.write_text(json.dumps(reports, indent=1, sort_keys=True) + '\n')

    for report in reports:
        print(f"\n=== {report['scenario']} ===")
        print(f"  preferences: {report['preferences_audited']} across "
              f"{report['segment_markets']} segment-markets; "
              f"generation unlock rounds {report['generation_unlock_rounds']}")
        print(f"  out-of-range ideals: {len(report['out_of_range_ideals'])}")
        for row in report['out_of_range_ideals']:
            print(f"    {row['segment']}/{row['market']}/{row['feature']}: "
                  f"{row['ideal']} outside [{row['min']}, {row['max']}]")
        print(f"  dead-weight preferences: {len(report['dead_weight'])} "
              f"(total weight {report['dead_weight_total']})")
        for row in report['dead_weight']:
            print(f"    {row['segment']}/{row['market']}/{row['feature']}: "
                  f"weight {row['weight']} dead in rounds {row['dead_rounds']}"
                  f" (reachable from round {row['unlocks_round']})")
        print(f"  tolerance verdicts: {report['tolerance_verdicts']}; "
              f"half-fit/range {report['tolerance_summary']}")
        print(f"  degenerate segment-markets: "
              f"{len(report['degenerate_segment_markets'])}")
        for row in report['degenerate_segment_markets']:
            print(f"    {row['segment']}/{row['market']}: {row}")
    print(f"\nwrote {options.json}")


if __name__ == '__main__':
    main()
