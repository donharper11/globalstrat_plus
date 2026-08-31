#!/usr/bin/env python3
"""Read `stage1-probes.json` and print the rows the probe record cites.

Separate from `probe_run.py` on purpose: the run writes what happened, this
reads it. Re-running this changes no state and needs no stack, so a reviewer
can check any number in the record against the captured evidence without
replaying the game.
"""
import json
import pathlib
import sys

EVIDENCE = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((EVIDENCE / 'stage1-probes.json').read_text())


def teams():
    return {t['index']: t for t in DATA['fixture']['teams']}


def state(round_key, team_index):
    t = teams()[team_index]
    return DATA['snapshots'][round_key]['teams'][str(t['id'])]


def authored_feature_cost(generation_order, feature_code, from_level, to_level):
    total = 0.0
    for row in DATA['fixture']['feature_level_costs']:
        if (row['generation_order'] == generation_order
                and row['feature_code'] == feature_code
                and from_level < row['level'] <= to_level):
            total += row['incremental_cost']
    return total


def main():
    print(f"revision {DATA['code_revision']}  database {DATA['database']}  "
          f"port {DATA['backend_port']}")
    print(f"identity {DATA['identity_check']}")
    print()

    last = max(k for k in DATA['snapshots'] if k.startswith('round_'))
    order = sorted(DATA['snapshots'], key=lambda k: int(k.split('_')[1]))
    print('=== probes ===')
    for probe in DATA['probes']:
        print(f"{probe['item']:<4} {probe['surface']:<18} {probe['status']:<4} "
              f"{probe['what'][:110]}")
    print()

    print('=== platforms per team, final snapshot ===')
    for index in sorted(teams()):
        s = state(order[-1], index)
        for p in s['platforms']:
            print(f"T{index} {s['name']:<20} gen{p['generation_order']} "
                  f"{p['name'][:26]:<26} status={p['status']:<15} "
                  f"started={p['development_started_round']} "
                  f"remaining={p['development_rounds_remaining']} "
                  f"activated={p['activated_round']} "
                  f"authored_rounds={p['authored_development_rounds']} "
                  f"authored_dev=${p['authored_development_cost']:,.0f} "
                  f"authored_lic=${p['authored_license_cost']:,.0f} "
                  f"capitalised=${p['capitalized_cost']:,.0f}")
    print()

    print('=== rd_expense and cash by round ===')
    for index in sorted(teams()):
        s = state(order[-1], index)
        line = ' | '.join(
            f"r{f['round']} rd={f['rd_expense']:,.0f} "
            f"amort={f['platform_amortization']:,.0f} "
            f"rev={f['total_revenue']:,.0f}"
            for f in s['financials'])
        print(f"T{index} {s['name']:<20} cash={s['cash_on_hand']:,.2f}")
        print(f"      {line}")
    print()

    print('=== A1b: feature levels bought, and what they were authored at ===')
    for index in (3, 4):
        for key in order:
            s = DATA['snapshots'][key]['teams'][str(teams()[index]['id'])]
            print(f"T{index} {key}: levels="
                  f"{[(l['feature_code'], l['level']) for l in s['feature_levels']]}")
            if s['pending_feature_gains']:
                print(f"      pending={s['pending_feature_gains']}")
    for probe in DATA['probes']:
        if probe['item'] != 'A1b':
            continue
        print(f"  payload: {json.dumps(probe['payload'])[:600]}")
    print()

    print('=== A1b: what the authored level-cost table charges for the same '
          'levels ===')
    codes = {f['id']: f['code'] for f in DATA['fixture']['features']}
    for index in (3, 4):
        snapshot_state = state('round_1', index)
        before = {l['feature_code']: l['level']
                  for l in snapshot_state['feature_levels']}
        owned = {p['id'] for p in snapshot_state['platforms']}
        total = 0.0
        for probe in DATA['probes']:
            if probe['item'] != 'A1b':
                continue
            rows = probe['payload']
            rows = rows.get('rd_investments') if isinstance(rows, dict) else rows
            if not isinstance(rows, list):
                continue
            for row in rows:
                code = codes.get(row['feature'])
                if (code is None or code not in before
                        or row['team_platform'] not in owned):
                    continue
                cost = authored_feature_cost(1, code, before[code],
                                             row['target_level'])
                if cost:
                    print(f"  T{index} {code} {before[code]:.0f}->"
                          f"{row['target_level']}: ${cost:,.0f} authored, "
                          f"amount ${float(row['amount']):,.0f}, "
                          f"calculated_cost ${float(row['calculated_cost']):,.0f}")
                    total += cost
        print(f"  T{index} total authored cost of the levels granted: "
              f"${total:,.0f}")
    print()

    print('=== A4: prices submitted and prices the engine used ===')
    s = state(order[-1], 6)
    for sub in s['submissions']:
        print(f"  submitted r{sub['round']}: "
              f"{[(m['product'], m['retail_price']) for m in sub['marketing']]}")
    for row in s['product_market_results']:
        print(f"  engine    r{row['round']}: {row['product']:<12} "
              f"price={row['retail_price']:,.2f} produced={row['units_produced']} "
              f"sold={row['units_sold']:,.2f} revenue={row['local_revenue']:,.2f}")
    print()

    print('=== D1: retirement and the market links ===')
    s = state(order[-1], 7)
    for product in s['products']:
        print(f"  {product['name']:<16} status={product['status']:<9} "
              f"retired_round={product['retired_round']} "
              f"markets={product['markets']}")
    print()

    print('=== A2: the lock ===')
    for probe in DATA['probes']:
        if probe['item'] == 'A2':
            print(f"  [{probe['surface']}] {probe['status']}: "
                  f"{json.dumps(probe['response'])[:700]}")
    s = state(order[-1], 5)
    print(f"  T5 cash={s['cash_on_hand']:,.2f}")
    for sub in s['submissions']:
        if sub['platform_developments']:
            print(f"  r{sub['round']} status={sub['status']} budget={sub['budget']} "
                  f"platform_developments={sub['platform_developments']}")
    print()

    print('=== A6: cohort ===')
    print(json.dumps(DATA['cohort'], indent=1)[:2500])
    return 0


if __name__ == '__main__':
    sys.exit(main())
