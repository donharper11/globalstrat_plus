#!/usr/bin/env python3
"""Re-author the unreachable preference rows (owner ruling, 2026-09-12).

The ruling: *re-author the decorative rows.* Do not exclude unreachable weight
from scoring, and do not leave it as authored.  Wanting a better product should
be felt where a team can act on it.

What "unreachable" actually means here, which is what drives the two rules
below: these features are **not permanently dead**.  In all three scenarios two
of the three appear on Gen 2 (unlock round 2) and one only on Gen 3 (unlock
round 5, plus 2 development rounds).  So one class is out of reach for a single
round and the other for four rounds at best.

    Rule A — Gen-3-only feature, out of reach for rounds 1-4.
        A demand no team can act on for the first four rounds is a flat tax,
        not pressure.  The row is REMOVED from segments a Gen-1 team plays in,
        and its weight is MOVED to that segment-market's highest-weighted
        Gen-1-reachable platform feature, so the segment's total weight is
        unchanged and the weight now sits on something a team can move.

    Rule B — Gen-2 feature, out of reach for round 1 only.
        This is the upgrade incentive the scenario intended, but it was
        authored decoratively: a low ideal against a wide tolerance pays
        0.61-0.88 of its value to a team sitting at level 0, so nobody feels
        it.  The weight is KEPT and the demand is made real - the ideal is
        remapped into the band a Gen-2 platform can actually reach and the
        tolerance tightened, so a Gen-1 team scores near zero on the term and a
        team that upgrades and builds the feature scores near one.  Each
        segment's authored ordering is preserved (the segment that asked for
        least still asks for least).

Segments carrying ``min_generation_required`` are **not touched** - a Gen-1
team cannot enter them at all, so their weight is not "early-round" weight.
Whether a segment teams cannot enter should carry upgrade pressure is a
separate design question, reported rather than decided.

Usage:
    reauthor_unreachable_preferences.py --dry-run     # per-row plan
    reauthor_unreachable_preferences.py --apply       # rewrite the YAML
"""
import argparse
import math
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCENARIO_DIR = REPO / 'backend' / 'scenarios'

# Per scenario: the ideal remap for Rule B (authored ideal -> new ideal) and the
# new tolerance.  The remap keeps each segment's relative demand ordering and
# stays at or below the Gen-2 ceiling for the feature, so the target is
# genuinely attainable once a team upgrades.
PLAN = {
    'consumer_electronics_2026.yaml': {
        'gen3_only': ('connectivity',),
        'gen2': ('ai_features', 'iot_integration'),
        'ideal_map': {4.0: 8.0, 6.0: 10.0, 8.0: 12.0},
        'tolerance': 4.0,
        'gen2_ceiling': {'ai_features': 16, 'iot_integration': 16},
    },
    'clean_energy_tech_2026.yaml': {
        'gen3_only': ('sodium_ion',),
        'gen2': ('solid_state', 'smart_bms'),
        'ideal_map': {3.0: 5.0, 4.0: 6.0},
        'tolerance': 2.5,
        'gen2_ceiling': {'solid_state': 7, 'smart_bms': 8},
    },
    'media_entertainment_2026.yaml': {
        'gen3_only': ('creator_economy',),
        'gen2': ('ai_personalization', 'immersive_media'),
        'ideal_map': {3.0: 5.0, 4.0: 6.0, 5.0: 7.0},
        'tolerance': 2.5,
        'gen2_ceiling': {'ai_personalization': 8, 'immersive_media': 7},
    },
}

# Segment-markets whose authored weights sum to 0.99 rather than 1.00.  Nothing
# divides by an assumed 1.00 (every scorer divides by the observed sum), but
# campaign_engine.py:99 adds `weight * strength * multiplier` WITHOUT
# normalising, so a 0.99 vector yields 1% less campaign bonus than an identical
# 1.00 one.  Tidying makes that path more correct, not less.
WEIGHT_TIDY = {
    'media_entertainment_2026.yaml': (
        ('Cultural Enthusiasts', 'eu'),
        ('Gen Z Digital Natives', 'eu'),
    ),
}


def fmt(value):
    """Format a number the way the scenario files already write them."""
    text = f'{value:.6f}'.rstrip('0')
    if text.endswith('.'):
        text += '0'
    return text


def gaussian_at_zero(ideal, tolerance):
    return math.exp(-(ideal ** 2) / (2 * tolerance ** 2)) if tolerance > 0 else 0.0


def index_blocks(lines):
    """Map (segment, market) -> list of {feature, line indices} from raw text."""
    blocks = {}
    segment = market = None
    start = None
    for i, line in enumerate(lines):
        if line.strip() == 'segment_preferences:':
            start = i
            continue
        if start is None or i < start:
            continue
        stripped = line.rstrip()
        if not stripped:
            continue
        indent = len(stripped) - len(stripped.lstrip())
        if indent == 2 and stripped.endswith(':') and not stripped.lstrip().startswith('-'):
            segment = stripped.strip()[:-1]
            market = None
        elif indent == 4 and stripped.endswith(':') and not stripped.lstrip().startswith('-'):
            market = stripped.strip()[:-1]
        elif indent == 4 and stripped.lstrip().startswith('- - '):
            feature = stripped.split('- - ', 1)[1].strip()
            blocks.setdefault((segment, market), []).append({
                'feature': feature, 'head': i,
                'ideal': i + 1, 'weight': i + 2, 'tolerance': i + 3,
            })
        elif indent == 0 and stripped.endswith(':'):
            break  # next top-level section
    return blocks


def value_of(lines, index):
    return float(lines[index].split('- ', 1)[1])


def process(name, apply_changes):
    path = SCENARIO_DIR / name
    text = path.read_text()
    lines = text.split('\n')
    data = yaml.safe_load(text)
    plan = PLAN[name]

    features = {f['code']: f for layer in data['features'].values() for f in layer}
    gated = {s['name'] for s in data['customer_segments']
             if s.get('min_generation_required')}
    customer = {s['name'] for s in data['customer_segments']}
    unreachable = set(plan['gen3_only']) | set(plan['gen2'])

    blocks = index_blocks(lines)
    actions = []
    edits = {}       # line index -> new text
    deletions = []   # head line index of a 4-line block

    for (segment, market), rows in sorted(blocks.items()):
        if segment not in customer:
            continue
        tidy_target = (segment, market) in WEIGHT_TIDY.get(name, ())
        is_gated = segment in gated
        if is_gated and not tidy_target:
            continue

        reachable = [
            (row, value_of(lines, row['weight'])) for row in rows
            if features.get(row['feature'], {}).get('layer') == 'platform'
            and row['feature'] not in unreachable
        ]
        reachable.sort(key=lambda pair: (-pair[1], pair[0]['feature']))
        target = reachable[0][0] if reachable else None
        moved_weight = 0.0

        if not is_gated:
            for row in rows:
                feature = row['feature']
                if feature not in unreachable:
                    continue
                ideal = value_of(lines, row['ideal'])
                weight = value_of(lines, row['weight'])
                tolerance = value_of(lines, row['tolerance'])
                before_fit = gaussian_at_zero(ideal, tolerance)

                if feature in plan['gen3_only']:
                    if target is None:
                        raise SystemExit(
                            f'{name}: {segment}/{market} has no Gen-1-reachable '
                            f'platform feature to move {feature} weight onto')
                    deletions.append(row['head'])
                    moved_weight += weight
                    actions.append({
                        'scenario': name, 'segment': segment, 'market': market,
                        'feature': feature, 'rule': 'A-move',
                        'why': 'Gen-3-only: out of reach rounds 1-4',
                        'weight': weight, 'moved_to': target['feature'],
                        'fit_at_0_before': round(before_fit, 4),
                    })
                else:
                    new_ideal = plan['ideal_map'][ideal]
                    ceiling = plan['gen2_ceiling'][feature]
                    if new_ideal > ceiling:
                        raise SystemExit(
                            f'{name}: {segment}/{market} {feature} new ideal '
                            f'{new_ideal} exceeds Gen-2 ceiling {ceiling}')
                    new_tolerance = plan['tolerance']
                    edits[row['ideal']] = f'      - {fmt(new_ideal)}'
                    edits[row['tolerance']] = f'      - {fmt(new_tolerance)}'
                    actions.append({
                        'scenario': name, 'segment': segment, 'market': market,
                        'feature': feature, 'rule': 'B-sharpen',
                        'why': 'Gen-2: reachable from round 2, was decorative',
                        'weight': weight,
                        'ideal': f'{ideal} -> {new_ideal}',
                        'tolerance': f'{tolerance} -> {new_tolerance}',
                        'fit_at_0_before': round(before_fit, 4),
                        'fit_at_0_after': round(
                            gaussian_at_zero(new_ideal, new_tolerance), 4),
                    })

        tidy_weight = 0.0
        if tidy_target:
            current = sum(value_of(lines, row['weight']) for row in rows)
            tidy_weight = round(1.0 - current, 6)

        if (moved_weight or tidy_weight) and target is not None:
            new_weight = value_of(lines, target['weight']) + moved_weight + tidy_weight
            edits[target['weight']] = f'      - {fmt(new_weight)}'
            if tidy_weight:
                actions.append({
                    'scenario': name, 'segment': segment, 'market': market,
                    'feature': target['feature'], 'rule': 'C-tidy',
                    'why': f'weights summed to {round(1.0 - tidy_weight, 4)}, '
                           f'not 1.00; campaign_engine does not normalise',
                    'weight': f'+{fmt(tidy_weight)}',
                })

    if apply_changes:
        for index, replacement in edits.items():
            lines[index] = replacement
        for head in sorted(deletions, reverse=True):
            del lines[head:head + 4]
        path.write_text('\n'.join(lines))

    return actions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    options = parser.parse_args()
    if not (options.apply or options.dry_run):
        raise SystemExit('pass --dry-run or --apply')

    everything = []
    for name in PLAN:
        everything.extend(process(name, options.apply))

    by_rule = {}
    for action in everything:
        by_rule.setdefault(action['rule'], []).append(action)

    for rule in sorted(by_rule):
        rows = by_rule[rule]
        print(f'\n=== {rule}: {len(rows)} rows ===')
        seen = set()
        for action in rows:
            key = (action['scenario'], action['segment'], action['feature'])
            if key in seen:
                continue
            seen.add(key)
            same = [r for r in rows if (r['scenario'], r['segment'],
                                        r['feature']) == key]
            head = (f"  {action['scenario'][:22]:<22} {action['segment'][:34]:<34} "
                    f"{action['feature']:<19}")
            if rule == 'A-move':
                print(f"{head} w={action['weight']} -> {action['moved_to']}"
                      f"  (fit@0 was {action['fit_at_0_before']})"
                      f"  x{len(same)} markets")
            elif rule == 'B-sharpen':
                print(f"{head} ideal {action['ideal']}, tol {action['tolerance']}"
                      f"  fit@0 {action['fit_at_0_before']} -> "
                      f"{action['fit_at_0_after']}  x{len(same)} markets")
            else:
                print(f"{head} {action['weight']}  ({action['why']})")

    print(f'\ntotal row actions: {len(everything)}'
          f"  {'APPLIED' if options.apply else '(dry run, nothing written)'}")


if __name__ == '__main__':
    main()
