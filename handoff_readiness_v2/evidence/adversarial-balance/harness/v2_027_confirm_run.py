#!/usr/bin/env python3
"""Run the V2-027 confirmation: bounds, four counter-strategies, decomposition."""
import datetime, json, pathlib, subprocess, sys
from decimal import Decimal as D

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
sys.path.insert(0, str(HERE))
import checksums  # noqa: E402
import inventory_run as R  # noqa: E402

BODY = '''
import sys, json
sys.path.insert(0, {harness!r})
import v2_027_confirm_body
report = v2_027_confirm_body.run({strategy!r})
print("---V2027-JSON---")
print(json.dumps(report, default=str))
'''

STRATEGIES = ('none', 'max_capability', 'price_volume_capture',
              'financing_funded_scale', 'combined_best')
SENSITIVITY = D('20')
WEIGHTS = {'market': D('0.30'), 'capability': D('0.25'), 'financial': D('0.15'),
           'stakeholder': D('0.15'), 'resilience': D('0.15')}


def main():
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=REPO, capture_output=True, text=True).stdout.strip()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record evidence from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))

    def play(strategy):
        database = f"gsp_v2027_{strategy}_{datetime.datetime.now():%H%M%S}"
        print(f'Creating disposable database {database}')
        if R.psql('postgres', f'CREATE DATABASE {database}').returncode != 0:
            raise SystemExit('could not create the database')
        try:
            R.manage(database, 'migrate', '--noinput')
            R.manage(database, 'shell', '-c', R.LEGACY_TABLES)
            result = R.manage(database, 'shell', '-c',
                              BODY.format(harness=str(HERE), strategy=strategy),
                              timeout=7200)
            marker = '---V2027-JSON---'
            if result.returncode != 0 or marker not in result.stdout:
                print(result.stdout[-4000:]); print(result.stderr[-4000:])
                raise SystemExit(f'the confirmation did not run ({strategy})')
            return json.loads(
                result.stdout.split(marker, 1)[1].strip().splitlines()[0])
        finally:
            R.psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
            print(f'Dropped {database}')

    runs = {s: play(s) for s in STRATEGIES}
    for strategy, run in runs.items():
        if run['identity_failures']:
            raise SystemExit(
                f"REFUSED: composite and index_change disagree in {strategy}, "
                f"so the decomposition rests on nothing: "
                f"{run['identity_failures'][:3]}")

    control = runs['none']
    gap = D(control['gap_at_end'])
    leader_composite = D(control['series'][-1]['leader']['composite'])

    # Absolute bound: composite 1.0 in one round, every component maxed at
    # once. Reported because it is the formula's true ceiling, and immediately
    # qualified because those maxima are not jointly reachable.
    absolute_per_round = (D('1') - D('0.5')) * SENSITIVITY
    absolute_advantage = (D('1') - leader_composite) * SENSITIVITY
    absolute_rounds = (gap / absolute_advantage
                       if absolute_advantage > 0 else None)

    # Attainable bound: the best per-round composite advantage any of the four
    # legal plans actually reached.
    attained = {s: D(r['best_composite_advantage_per_round'])
                for s, r in runs.items() if s != 'none'}
    best_attained = max(attained.values()) if attained else D('0')
    attainable_advantage = best_attained * SENSITIVITY
    attainable_rounds = (gap / attainable_advantage
                         if attainable_advantage > 0 else None)

    report = {
        'code_revision': revision,
        'sensitivity': str(SENSITIVITY),
        'component_weights': {k: str(v) for k, v in WEIGHTS.items()},
        'index_rule': ('index_change = (composite - 0.5) * sensitivity; '
                       'new_index = max(0, previous_index + index_change). '
                       'The index integrates with no decay term, so a gap '
                       'persists unless the trailing team scores a higher '
                       'composite than the leader.'),
        'measured_gap_at_end_of_control': str(gap),
        'leader_composite_while_baseline': str(leader_composite),
        'absolute_bound': {
            'max_index_change_per_round': str(absolute_per_round),
            'max_advantage_per_round_over_this_leader': str(absolute_advantage),
            'rounds_to_close': (str(absolute_rounds.quantize(D('0.01')))
                                if absolute_rounds else None),
            'caveat': ('assumes composite 1.0 -- market, capability, '
                       'financial, stakeholder and resilience all at maximum '
                       'in the same round. Market and financial are scored '
                       'relative to the highest revenue in the field, so '
                       'maximising them requires already out-earning the '
                       'leader. This is the formula ceiling, not a plan.'),
        },
        'attainable_bound': {
            'best_composite_advantage_per_round': str(best_attained),
            'index_advantage_per_round': str(attainable_advantage),
            'rounds_to_close': (str(attainable_rounds.quantize(D('0.01')))
                                if attainable_rounds else None),
            'by_strategy': {s: str(v) for s, v in attained.items()},
        },
        'runs': runs,
    }

    closers = [s for s, r in runs.items()
               if s != 'none' and r['closed_materially']]
    report['strategies_closing_materially'] = closers
    report['any_strategy_closed_the_gap'] = [
        s for s, r in runs.items() if s != 'none' and r['gap_closed']]

    # The decomposition the disposition asks for.
    last = control['series'][-1]
    report['persistence_decomposition'] = {
        'accumulated_index_gap': last['index_gap'],
        'current_round_composite_gap': last['composite_gap'],
        'current_round_index_effect': str(
            D(last['composite_gap']) * SENSITIVITY),
        'leader_adopters': last['leader']['cumulative_adopters'],
        'challenger_adopters': last['challenger']['cumulative_adopters'],
        'reading': ('the share of the standing gap explained by current-round '
                    'performance is the composite gap times sensitivity; the '
                    'remainder is carried by the accumulated index, which has '
                    'no decay term, and by the adopter stock bought earlier.'),
    }

    (EVIDENCE / 'v2-027-confirmation.json').write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + '\n')
    listed = checksums.regenerate(EVIDENCE)
    bad = checksums.verify(EVIDENCE)
    if bad:
        raise SystemExit(f'inventory does not verify: {bad}')

    print(f"\n=== bounds ===")
    print(f"measured gap                     : {gap}")
    print(f"leader composite while baseline  : {leader_composite}")
    ab = report['absolute_bound']
    print(f"\nabsolute formula bound:")
    print(f"  max index change per round     : {ab['max_index_change_per_round']}")
    print(f"  max advantage over this leader : {ab['max_advantage_per_round_over_this_leader']}")
    print(f"  rounds to close                : {ab['rounds_to_close']}")
    print(f"  caveat                         : {ab['caveat']}")
    at = report['attainable_bound']
    print(f"\nattainable bound, from the four legal plans:")
    print(f"  best composite advantage/round : {at['best_composite_advantage_per_round']}")
    print(f"  index advantage per round      : {at['index_advantage_per_round']}")
    print(f"  rounds to close                : {at['rounds_to_close']}")
    for s, v in at['by_strategy'].items():
        print(f"    {s:<26} {v}")

    print(f"\n=== counter-strategies ===")
    for s in STRATEGIES:
        r = runs[s]
        print(f"  {s:<26} gap {r['gap_when_countering_began']:>8} -> "
              f"{r['gap_at_end']:>8}  change {r['gap_change']:>8}  "
              f"closed materially: {r['closed_materially']}")

    pd = report['persistence_decomposition']
    print(f"\n=== persistence decomposition (control) ===")
    print(f"  standing index gap             : {pd['accumulated_index_gap']}")
    print(f"  current-round composite gap    : {pd['current_round_composite_gap']}")
    print(f"  that gap as index effect       : {pd['current_round_index_effect']}")
    print(f"  adopters leader / challenger   : {pd['leader_adopters']} / "
          f"{pd['challenger_adopters']}")
    print(f"\nstrategies closing materially   : {closers}")
    print(f"\nwrote {EVIDENCE / 'v2-027-confirmation.json'}")
    print(f"inventory: {len(listed)} artifacts, verified")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
