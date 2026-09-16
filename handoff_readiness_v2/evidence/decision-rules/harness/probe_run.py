#!/usr/bin/env python3
"""GSP-CRV2-10 Stage 1: confirm or withdraw Part A by probe.

Part A of `RULES_AND_CALIBRATION_ASSESSMENT.md` was written from source reading
only. This run executes each of its seven claims against a running isolated
stack, through **both** supported submission surfaces wherever the field is
exposed on both:

  whole submission   POST /api/games/G/teams/T/decisions/round/R/
  per decision type  PATCH /api/games/G/teams/T/decisions/round/R/<type>/

It writes no runtime code and changes nothing under `backend/core`. Every
payload, response and resulting row is captured into `stage1-probes.json`.

One team carries one probe so that a round's engine consequences can be read
per item without one probe's payload contaminating another's:

  T1  A1   platform priced at 0, whole-submission surface
  T2  A1   platform priced at 0, per-type surface
  T3  A1b  feature levels bought for 0, whole-submission surface
  T4  A1b  feature levels bought for 0, per-type surface
  T5  A2   committed_cost above cash and above rd_budget, then lock
  T6  A4   price at 10x and 0.1x the previous round's price
  T7  D1   end_of_round retirement, with an immediate retirement as control
  T8  A3   a development_rounds:0 generation, and the control baseline
"""
import argparse
import datetime
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
sys.path.insert(0, str(HERE))
import stack as S                    # noqa: E402
import fixture_bodies as F           # noqa: E402

PASSWORD = F.PASSWORD
BASELINE_BUDGET = {'rd_budget': '2000000', 'marketing_budget': '3000000',
                   'strategy_budget': '500000'}


class Recorder:
    """Every probe is a payload, a response, and the rows that resulted."""

    def __init__(self):
        self.items = []

    def add(self, item, surface, what, method, path, payload, code, body,
            note=''):
        entry = {'item': item, 'surface': surface, 'what': what,
                 'method': method, 'path': path, 'payload': payload,
                 'status': code, 'response': _trim(body), 'note': note}
        self.items.append(entry)
        flag = '' if code < 300 else '  <-- refused'
        print(f'  [{item}/{surface}] {what}: {code}{flag}', flush=True)
        return entry


def _trim(body, limit=2500):
    text = json.dumps(body, default=str)
    if len(text) <= limit:
        try:
            return json.loads(text)
        except ValueError:
            return text
    return text[:limit] + f'... (+{len(text) - limit} chars)'


def marketing_row(product_id, market_id, price, volume=20000,
                  promotion='400000'):
    return {'team_product': product_id, 'market': market_id,
            'retail_price': str(price), 'promotion_budget': promotion,
            'campaign_focus_feature_ids': list(_CAMPAIGN_FOCUS),
            'channel_digital_pct': '0.4000',
            'channel_traditional_pct': '0.4000',
            'channel_trade_pct': '0.2000',
            'distribution_strategy': 'mass_retail',
            'distribution_investment': '200000', 'sales_team_count': 2,
            'distribution_channel_detail': {},
            'production_volume': volume,
            'production_source_market': market_id,
            'demand_estimate': volume}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=6,
                        help='how many game rounds to play')
    parser.add_argument('--keep-database', action='store_true')
    options = parser.parse_args()

    revision = S.revision()
    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    database = f'gsp_crv210_stage1_{stamp}'
    started = datetime.datetime.now().isoformat(timespec='seconds')

    print(f'revision   {revision}')
    print(f'database   {database}')
    print(f'started    {started}', flush=True)

    S.create_database(database)
    print('seeding', flush=True)
    seeded = S.shell_json(
        database,
        'import fixture_bodies as F\n'
        'out = F.seed()\n'
        'print("---SEED---")\n'
        'print(json.dumps(out, default=str))\n',
        '---SEED---')
    game = seeded['game_id']
    teams = seeded['teams']
    print(f"game {game}, {len(teams)} teams, scenario {seeded['scenario']}",
          flush=True)

    port = S.free_port()
    process = S.start_gunicorn(database, port, revision)
    print(f'backend pid {process.pid} on port {port}', flush=True)

    record = {
        'handoff': 'GSP-CRV2-10 Stage 1',
        'code_revision': revision,
        'worktree_dirty': bool(S.dirty()),
        'database': database,
        'database_host': S.DB_HOST,
        'backend_port': port,
        'backend_pid': process.pid,
        'environment': 'GLOBALSTRAT_ENV=production, gunicorn, disposable '
                       'database, port claimed at run time',
        'started_at': started,
        'fixture': seeded,
        'identity_check': None,
        'probes': [],
        'rounds': [],
        'snapshots': {},
        'cohort': {},
    }
    recorder = Recorder()

    try:
        record['identity_check'] = S.assert_identity(
            port, database, teams[0]['student'], PASSWORD)
        print(f"identity confirmed: {record['identity_check']}", flush=True)

        code, body = S.api(port, 'POST', '/api/auth/login/',
                           body={'username': seeded['instructor'],
                                 'password': PASSWORD})
        if code != 200:
            raise SystemExit(f'instructor login failed: {code} {body}')
        instructor = body['access']
        tokens = {}
        for team in teams:
            code, body = S.api(port, 'POST', '/api/auth/login/',
                               body={'username': team['student'],
                                     'password': PASSWORD})
            if code != 200:
                raise SystemExit(f"login failed for {team['student']}")
            tokens[team['id']] = body['access']

        install_reference(seeded)
        by_index = {team['index']: team for team in teams}
        gens = {g['generation_order']: g for g in seeded['generations']}
        na = next(m for m in seeded['markets'] if m['code'] == 'NA')

        record['snapshots']['round_0'] = snapshot(database, game)

        for round_number in range(1, options.rounds + 1):
            print(f'\n=== round {round_number} ===', flush=True)
            events = play_round(port, game, round_number, by_index, tokens,
                                instructor, gens, na, recorder,
                                record['snapshots'])
            record['rounds'].append(events)
            record['snapshots'][f'round_{round_number}'] = snapshot(
                database, game)

        # A6 does not depend on the round loop.
        record['cohort'] = probe_cohort_caps(port, database, seeded, instructor,
                                             tokens, recorder)
    finally:
        S.stop_gunicorn(process)
        record['probes'] = recorder.items
        record['finished_at'] = datetime.datetime.now().isoformat(
            timespec='seconds')
        out = EVIDENCE / 'stage1-probes.json'
        out.write_text(json.dumps(record, indent=2, sort_keys=True,
                                  default=str) + '\n')
        print(f'\nwrote {out}')
        if not options.keep_database:
            S.drop_database(database)
            print(f'dropped {database}')
        else:
            print(f'kept {database}')
    return 0


def snapshot(database, game):
    return S.shell_json(
        database,
        'import fixture_bodies as F\n'
        f'out = F.snapshot({game})\n'
        'print("---SNAP---")\n'
        'print(json.dumps(out, default=str))\n',
        '---SNAP---')


def base_path(game, team_id, round_number):
    return f'/api/games/{game}/teams/{team_id}/decisions/round/{round_number}/'


def play_round(port, game, r, by_index, tokens, instructor, gens, na,
               recorder, snapshots):
    events = {'round': r, 'actions': []}

    def note(what, code, detail=''):
        events['actions'].append({'what': what, 'status': code,
                                  'detail': _trim(detail, 400)})
        print(f'  {what}: {code}', flush=True)

    # Every team gets a budget and a marketing mix so the round resolves as a
    # game rather than as eight teams doing nothing.
    for index, team in by_index.items():
        token = tokens[team['id']]
        path = base_path(game, team['id'], r)
        code, body = S.api(port, 'PATCH', path + 'budget/', token,
                           BASELINE_BUDGET)
        if code >= 300:
            note(f"T{index} budget", code, body)
        code, body = S.api(port, 'PATCH', path + 'esg/', token,
                           {'environmental_investment': '0',
                            'social_investment': '0'})
        if code >= 300:
            note(f"T{index} esg", code, body)

    prices = baseline_prices(snapshots, r, by_index)

    for index, team in by_index.items():
        token = tokens[team['id']]
        path = base_path(game, team['id'], r)
        rows = []
        for product in active_products(snapshots, r, team):
            price = prices[(team['id'], product['id'])]
            if index == 6:
                continue        # T6's marketing is the A4 probe below
            rows.append(marketing_row(product['id'], na['id'], price))
        if rows:
            code, body = S.api(port, 'PATCH', path + 'marketing/', token, rows)
            if code >= 300:
                note(f"T{index} marketing", code, body)

    if r == 1:
        probe_a3(port, game, r, by_index, tokens, gens, recorder)
        probe_deadline_bypass(port, game, r, by_index, tokens, gens, recorder)
        probe_a4(port, game, r, by_index, tokens, na, prices, snapshots,
                 recorder, leg='10x')
        probe_d1(port, game, r, by_index, tokens, snapshots, recorder)
    if r == 2:
        probe_rd_context(port, game, r, by_index, tokens, recorder)
        probe_a1(port, game, r, by_index, tokens, gens, recorder)
        probe_a1b(port, game, r, by_index, tokens, snapshots, recorder)
        probe_a4(port, game, r, by_index, tokens, na, prices, snapshots,
                 recorder, leg='0.1x')
    if r == 3:
        # Round 3 and not round 2: rounds 2, 4, 6 and 8 each carry a mandatory
        # communication, and the lock validator refuses on that before it
        # reaches anything this probe is asking about.
        probe_a2(port, game, r, by_index, tokens, instructor, gens, na,
                 snapshots, recorder)
    if r == 5:
        probe_a1_gen3(port, game, r, by_index, tokens, gens, recorder)

    for action, body in (('close', {'reason': 'CRV2-10 Stage 1 probe run'}),
                         ('process', {}), ('advance', {})):
        started = time.time()
        code, response = S.api(
            port, 'POST', f'/api/games/{game}/round-control/{action}/',
            instructor, body)
        note(f'operator {action}', code,
             f'{response} ({time.time() - started:.1f}s)')
        if code >= 300 and action != 'advance':
            raise SystemExit(f'{action} failed in round {r}: {response}')
    return events


def active_products(snapshots, r, team):
    """The team's active products as of the last snapshot taken."""
    previous = snapshots.get(f'round_{r - 1}') or snapshots.get('round_0')
    rows = previous['teams'][str(team['id'])]['products']
    return [p for p in rows if p['status'] == 'active']


def baseline_prices(snapshots, r, by_index):
    """Last round's price per product, which is what a band would anchor on."""
    previous = snapshots.get(f'round_{r - 1}') or snapshots.get('round_0')
    out = {}
    for team in by_index.values():
        state = previous['teams'][str(team['id'])]
        last = {}
        for row in state['product_market_results']:
            last[row['product']] = row['retail_price']
        for product in state['products']:
            out[(team['id'], product['id'])] = last.get(product['name'], 450.0)
    return out


# --------------------------------------------------------------------------
# The authoritative table that exists and is only displayed
# --------------------------------------------------------------------------

def probe_rd_context(port, game, r, by_index, tokens, recorder):
    """What the server tells the student the price is, before they set it.

    `RDContextView` reads `PlatformGenerationDefinition.development_cost` /
    `license_cost` and the `FeatureLevelCost` schedule. Capturing it alongside
    the payloads is what turns A1 from "the client sets the price" into "the
    server already knows the price and does not use it".
    """
    for index in (1, 3):
        team = by_index[index]
        path = f"/api/games/{game}/teams/{team['id']}/context/rd/"
        code, body = S.api(port, 'GET', path, tokens[team['id']])
        summary = body
        if isinstance(body, dict):
            summary = {
                'rd_budget': body.get('rd_budget'),
                'available_generations': body.get('available_generations'),
                'upgrade_options': body.get('upgrade_options'),
                'current_investments': body.get('current_investments'),
            }
        recorder.add('authoritative-table', f'T{index} rd context',
                     'the prices the server itself publishes for the same '
                     'decisions the probes price at zero',
                     'GET', path, None, code, summary)


# --------------------------------------------------------------------------
# A1 — is the platform price client-set?
# --------------------------------------------------------------------------

def probe_a1(port, game, r, by_index, tokens, gens, recorder):
    gen2 = gens[2]
    for index, surface in ((1, 'whole-submission'), (2, 'per-type')):
        team = by_index[index]
        token = tokens[team['id']]
        path = base_path(game, team['id'], r)
        method = 'in_house' if index == 1 else 'license'
        authored = (gen2['development_cost'] if method == 'in_house'
                    else gen2['license_cost'])
        row = {'platform_generation': gen2['id'], 'method': method,
               'committed_cost': '0', 'platform_name': f'T{index} free Gen2',
               'feature_levels': {}}
        if surface == 'whole-submission':
            payload = {'platform_developments': [row]}
            code, body = S.api(port, 'POST', path, token, payload)
            recorder.add('A1', surface,
                         f'Gen 2 ({method}) committed_cost 0 against an '
                         f'authored ${authored:,.0f}',
                         'POST', path, payload, code, body)
        else:
            payload = [row]
            code, body = S.api(port, 'PATCH', path + 'platforms/', token,
                               payload)
            recorder.add('A1', surface,
                         f'Gen 2 ({method}) committed_cost 0 against an '
                         f'authored ${authored:,.0f}',
                         'PATCH', path + 'platforms/', payload, code, body)


def probe_a1_gen3(port, game, r, by_index, tokens, gens, recorder):
    """Round 5: Gen 3 unlocks, so the most expensive generation is reachable."""
    gen3 = gens[3]
    for index, surface in ((1, 'whole-submission'), (2, 'per-type')):
        team = by_index[index]
        token = tokens[team['id']]
        path = base_path(game, team['id'], r)
        method = 'in_house' if index == 1 else 'license'
        authored = (gen3['development_cost'] if method == 'in_house'
                    else gen3['license_cost'])
        row = {'platform_generation': gen3['id'], 'method': method,
               'committed_cost': '0', 'platform_name': f'T{index} free Gen3',
               'feature_levels': {}}
        if surface == 'whole-submission':
            payload = {'platform_developments': [row]}
            code, body = S.api(port, 'POST', path, token, payload)
            recorder.add('A1', surface,
                         f'Gen 3 ({method}) committed_cost 0 against an '
                         f'authored ${authored:,.0f} — the most expensive '
                         f'unlocked generation',
                         'POST', path, payload, code, body)
        else:
            payload = [row]
            code, body = S.api(port, 'PATCH', path + 'platforms/', token,
                               payload)
            recorder.add('A1', surface,
                         f'Gen 3 ({method}) committed_cost 0 against an '
                         f'authored ${authored:,.0f} — the most expensive '
                         f'unlocked generation',
                         'PATCH', path + 'platforms/', payload, code, body)


# --------------------------------------------------------------------------
# A1b — is the feature price client-set?
# --------------------------------------------------------------------------

def probe_a1b(port, game, r, by_index, tokens, snapshots, recorder):
    gen1_ceilings = None
    for index, surface, method in ((3, 'whole-submission', 'in_house'),
                                   (4, 'per-type', 'license')):
        team = by_index[index]
        token = tokens[team['id']]
        path = base_path(game, team['id'], r)
        state = snapshots['round_1']['teams'][str(team['id'])]
        platform = next(p for p in state['platforms'] if p['status'] == 'active')
        gen1_ceilings = ceilings_for(snapshots, platform['generation_order'])
        rows = []
        for level in state['feature_levels']:
            if level['team_platform_id'] != platform['id']:
                continue
            if level['level'] <= 0:
                continue
            ceiling = gen1_ceilings.get(level['feature_code'])
            if not ceiling or ceiling <= level['level']:
                continue
            rows.append({'team_platform': platform['id'],
                         'feature': feature_id(snapshots, level['feature_code']),
                         'method': method, 'amount': '0',
                         'target_level': int(ceiling),
                         'calculated_cost': '0',
                         '_from_level': level['level'],
                         '_feature_code': level['feature_code']})
        rows = rows[:3]
        clean = [{k: v for k, v in row.items() if not k.startswith('_')}
                 for row in rows]
        what = ('target_level at the generation ceiling with amount 0 and '
                'calculated_cost 0 for '
                + ', '.join(f"{row['_feature_code']} "
                            f"{row['_from_level']:.0f}->{row['target_level']}"
                            for row in rows))
        if surface == 'whole-submission':
            payload = {'rd_investments': clean}
            code, body = S.api(port, 'POST', path, token, payload)
            recorder.add('A1b', surface, f'{method}: {what}', 'POST', path,
                         payload, code, body)
        else:
            code, body = S.api(port, 'PATCH', path + 'rd/', token, clean)
            recorder.add('A1b', surface, f'{method}: {what}', 'PATCH',
                         path + 'rd/', clean, code, body)


_CEILINGS = {}
_FEATURES = {}
_CAMPAIGN_FOCUS = []


def install_reference(seeded):
    for gen in seeded['generations']:
        _CEILINGS[gen['generation_order']] = gen['ceilings']
    for feature in seeded['features']:
        _FEATURES[feature['code']] = feature['id']
    # `campaign_focus_feature_ids` must carry 1-3 feature ids; two real
    # platform features keep every marketing payload legal so that a refusal
    # in a probe is the probe's own.
    _CAMPAIGN_FOCUS[:] = [f['id'] for f in seeded['features'][:2]]


def ceilings_for(snapshots, generation_order):
    return _CEILINGS.get(generation_order, {})


def feature_id(snapshots, code):
    return _FEATURES[code]


# --------------------------------------------------------------------------
# A2 — does platform cost reach either budget check?
# --------------------------------------------------------------------------

def probe_a2(port, game, r, by_index, tokens, instructor, gens, na, snapshots,
             recorder):
    team = by_index[5]
    token = tokens[team['id']]
    path = base_path(game, team['id'], r)
    state = snapshots[f'round_{r - 1}']['teams'][str(team['id'])]
    cash = state['cash_on_hand']
    gen2 = gens[2]
    absurd = '999999999999.00'

    row = {'platform_generation': gen2['id'], 'method': 'in_house',
           'committed_cost': absurd, 'platform_name': 'T5 trillion dollar Gen2',
           'feature_levels': {}}

    payload = {'platform_developments': [row]}
    code, body = S.api(port, 'POST', path, token, payload)
    recorder.add('A2', 'whole-submission',
                 f'committed_cost ${float(absurd):,.0f} against '
                 f'${cash:,.0f} cash and a $2,000,000 rd_budget',
                 'POST', path, payload, code, body)

    code, body = S.api(port, 'PATCH', path + 'platforms/', token, [row])
    recorder.add('A2', 'per-type',
                 f'committed_cost ${float(absurd):,.0f} against '
                 f'${cash:,.0f} cash and a $2,000,000 rd_budget',
                 'PATCH', path + 'platforms/', [row], code, body)

    # Complete the submission so the lock validator runs its whole list, then
    # lock: `_full_validate` is the only place the cash and rd_budget checks
    # live, so a lock that succeeds is the finding.
    platform = next(p for p in state['platforms'] if p['status'] == 'active')
    creates = [{'team_platform': platform['id'],
                'product_name': 'T5 Portfolio Probe',
                'positioning': 'mainstream',
                'target_market_ids': [na['id']]}]
    code, body = S.api(port, 'PATCH', path + 'products/', token, creates)
    recorder.add('A2', 'per-type', 'product portfolio, so the lock validator '
                 'reaches its budget checks', 'PATCH', path + 'products/',
                 creates, code, body)

    rows = [marketing_row(p['id'], na['id'], 450)
            for p in state['products'] if p['status'] == 'active']
    S.api(port, 'PATCH', path + 'marketing/', token, rows)

    code, body = S.api(port, 'POST', path + 'lock/', token, {})
    recorder.add('A2', 'lock', 'lock the submission carrying a $1 trillion '
                 'platform commitment', 'POST', path + 'lock/', {}, code, body,
                 note='the cash check is views/decisions.py:548-552 and the '
                      'rd_budget check is :555-561')

    # Positive control. The same validator, the same team, the same round, one
    # field moved: an over-cash figure in `rd_budget` -- which the checks do
    # read -- must be refused. Without this a passing lock could mean the
    # checks are broken rather than blind to `committed_cost`.
    unlock_path = path + 'unlock/'
    code, body = S.api(port, 'POST', unlock_path, instructor,
                       {'reason': 'CRV2-10 Stage 1 A2 positive control'})
    recorder.add('A2', 'control', 'instructor unlock so the same submission '
                 'can be re-locked with one field changed',
                 'POST', unlock_path,
                 {'reason': 'CRV2-10 Stage 1 A2 positive control'}, code, body)

    over_cash = {'rd_budget': absurd, 'marketing_budget': '0',
                 'strategy_budget': '0'}
    code, body = S.api(port, 'PATCH', path + 'budget/', token, over_cash)
    recorder.add('A2', 'control', 'the same figure in rd_budget, a field the '
                 'checks do read', 'PATCH', path + 'budget/', over_cash, code,
                 body)
    code, body = S.api(port, 'POST', path + 'lock/', token, {})
    recorder.add('A2', 'control', 'lock with rd_budget over cash — the check '
                 'firing here is what makes the result above a blind spot '
                 'rather than a broken validator',
                 'POST', path + 'lock/', {}, code, body)

    # Put the round back the way the probe wants it resolved: baseline budget,
    # the trillion-dollar platform still committed, locked.
    S.api(port, 'PATCH', path + 'budget/', token, BASELINE_BUDGET)
    code, body = S.api(port, 'POST', path + 'lock/', token, {})
    recorder.add('A2', 'lock', 're-lock with the baseline budget restored, so '
                 'the round resolves from the $1 trillion commitment',
                 'POST', path + 'lock/', {}, code, body)


# --------------------------------------------------------------------------
# A3 — is a platform ready in the round it was created?
# --------------------------------------------------------------------------

def probe_a3(port, game, r, by_index, tokens, gens, recorder):
    gen1 = gens[1]
    team = by_index[8]
    token = tokens[team['id']]
    path = base_path(game, team['id'], r)
    row = {'platform_generation': gen1['id'], 'method': 'in_house',
           'committed_cost': str(gen1['development_cost']),
           'platform_name': 'T8 Gen1 rebuild', 'feature_levels': {}}

    payload = {'platform_developments': [row]}
    code, body = S.api(port, 'POST', path, token, payload)
    recorder.add('A3', 'whole-submission',
                 f"development_rounds {gen1['development_rounds']} generation "
                 f'at its authored cost', 'POST', path, payload, code, body)

    code, body = S.api(port, 'PATCH', path + 'platforms/', token, [row])
    recorder.add('A3', 'per-type',
                 f"development_rounds {gen1['development_rounds']} generation "
                 f'at its authored cost', 'PATCH', path + 'platforms/', [row],
                 code, body)


# --------------------------------------------------------------------------
# The deadline path, which is where every rule in `_full_validate` stops
# binding. Not in Part A; found while placing the A2 probe.
# --------------------------------------------------------------------------

def probe_deadline_bypass(port, game, r, by_index, tokens, gens, recorder):
    """A payload the lock validator refuses, resolved anyway by the deadline.

    `_full_validate` is reached only when a team presses Lock. Closing the
    round calls `_lock_all_submissions`, which locks every draft as it stands
    and validates nothing. So the question "does the lock validator refuse
    this?" and the question "is this resolved?" have different answers, and a
    team that simply never locks gets the second one.

    Gen 3 is the sharpest case available: `unlock_round` 5, probed in round 1,
    where the validator has an explicit refusal for it.
    """
    gen3 = gens[3]
    team = by_index[5]
    token = tokens[team['id']]
    path = base_path(game, team['id'], r)
    row = {'platform_generation': gen3['id'], 'method': 'in_house',
           'committed_cost': '0', 'platform_name': 'T5 round-1 Gen3',
           'feature_levels': {}}

    payload = {'platform_developments': [row]}
    code, body = S.api(port, 'POST', path, token, payload)
    recorder.add('deadline-bypass', 'whole-submission',
                 f"Gen 3 (unlock_round {gen3['unlock_round']}) submitted in "
                 f'round {r} at committed_cost 0', 'POST', path, payload,
                 code, body)

    code, body = S.api(port, 'PATCH', path + 'platforms/', token, [row])
    recorder.add('deadline-bypass', 'per-type',
                 f"Gen 3 (unlock_round {gen3['unlock_round']}) submitted in "
                 f'round {r} at committed_cost 0', 'PATCH',
                 path + 'platforms/', [row], code, body)

    code, body = S.api(port, 'POST', path + 'lock/', token, {})
    recorder.add('deadline-bypass', 'lock',
                 'the same submission offered to the lock validator, which is '
                 'the only place the unlock-round rule lives',
                 'POST', path + 'lock/', {}, code, body,
                 note='the team now simply does not lock; the round close '
                      'locks the draft as it stands and the engine resolves it')


# --------------------------------------------------------------------------
# A4 — is there a price band?
# --------------------------------------------------------------------------

def probe_a4(port, game, r, by_index, tokens, na, prices, snapshots, recorder,
             leg):
    team = by_index[6]
    token = tokens[team['id']]
    path = base_path(game, team['id'], r)
    multiplier = 10.0 if leg == '10x' else 0.1
    rows = []
    described = []
    for product in active_products(snapshots, r, team):
        previous = prices[(team['id'], product['id'])]
        new_price = round(previous * multiplier, 2)
        rows.append(marketing_row(product['id'], na['id'], new_price))
        described.append(f"{product['name']} {previous:,.2f} -> {new_price:,.2f}")

    payload = {'marketing_decisions': rows}
    code, body = S.api(port, 'POST', path, token, payload)
    recorder.add('A4', 'whole-submission',
                 f'{leg} the previous round price: ' + '; '.join(described),
                 'POST', path, payload, code, body)

    code, body = S.api(port, 'PATCH', path + 'marketing/', token, rows)
    recorder.add('A4', 'per-type',
                 f'{leg} the previous round price: ' + '; '.join(described),
                 'PATCH', path + 'marketing/', rows, code, body)


# --------------------------------------------------------------------------
# D1 — end_of_round retirement and the market links
# --------------------------------------------------------------------------

def probe_d1(port, game, r, by_index, tokens, snapshots, recorder):
    team = by_index[7]
    token = tokens[team['id']]
    path = base_path(game, team['id'], r)
    products = active_products(snapshots, r, team)
    end_of_round, immediate = products[0], products[1]

    rows = [{'team_product': end_of_round['id'], 'timing': 'end_of_round'},
            {'team_product': immediate['id'], 'timing': 'immediate'}]

    payload = {'product_retires': rows}
    code, body = S.api(port, 'POST', path, token, payload)
    recorder.add('D1', 'whole-submission',
                 f"retire {end_of_round['name']} end_of_round and "
                 f"{immediate['name']} immediate as the control",
                 'POST', path, payload, code, body)

    code, body = S.api(port, 'PATCH', path + 'product-retires/', token, rows)
    recorder.add('D1', 'per-type',
                 f"retire {end_of_round['name']} end_of_round and "
                 f"{immediate['name']} immediate as the control",
                 'PATCH', path + 'product-retires/', rows, code, body)


# --------------------------------------------------------------------------
# A6 — cohort caps
# --------------------------------------------------------------------------

def probe_cohort_caps(port, database, seeded, instructor, tokens, recorder):
    caps = seeded['section_caps']
    section = seeded['section_id']
    out = {'authored_caps': caps, 'before': None, 'after': None}

    out['before'] = S.shell_json(
        database,
        'import fixture_bodies as F\n'
        f'out = F.cohort_state({section}, {seeded["game_id"]})\n'
        'print("---COHORT---")\nprint(json.dumps(out, default=str))\n',
        '---COHORT---')

    # 1. A second game in the same section, sized past max_teams.
    payload = {'scenario_id': seeded['scenario_id'], 'num_teams': 16,
               'name': 'CRV2-10 cap probe game', 'section_id': section}
    code, body = S.api(port, 'POST', '/api/games/create/', instructor, payload)
    recorder.add('A6', 'game-create',
                 f"num_teams 16 into a section whose max_teams is "
                 f"{caps['max_teams']}",
                 'POST', '/api/games/create/', payload, code, body,
                 note='a 500 here is not the cap refusing; see the incidental '
                      'finding on GameCreateView.created_by')

    # 2. num_teams past the *other* cap, the one that is enforced.
    payload = {'scenario_id': seeded['scenario_id'], 'num_teams': 17,
               'name': 'CRV2-10 cap probe game 17', 'section_id': section}
    code, body = S.api(port, 'POST', '/api/games/create/', instructor, payload)
    recorder.add('A6', 'game-create',
                 'num_teams 17, past the unrelated 2..16 cap at '
                 'views/scenario_views.py:237',
                 'POST', '/api/games/create/', payload, code, body)

    # 3. A ninth team added straight to the game through the routed endpoint.
    seed_team = seeded['teams'][0]
    payload = {'game': seeded['game_id'], 'name': 'CRV2-10 Ninth Firm',
               'firm_starter_profile': seed_team['firm_starter_profile_id'],
               'performance_index': seed_team['performance_index'],
               'cash_on_hand': seed_team['cash_on_hand'],
               'total_equity': seed_team['total_equity']}
    code, body = S.api(port, 'POST', '/api/teams/', instructor, payload)
    recorder.add('A6', 'team-create',
                 f"a 9th team in a game whose section allows "
                 f"{caps['max_teams']}",
                 'POST', '/api/teams/', payload, code, body)

    # ...and keep going, so "the cap does not bind" is a measured count rather
    # than one team over the line.
    flood = []
    for n in range(10, 18):
        extra = dict(payload, name=f'CRV2-10 Firm {n}')
        fcode, fbody = S.api(port, 'POST', '/api/teams/', instructor, extra)
        flood.append({'n': n, 'status': fcode,
                      'team_id': fbody.get('id') if isinstance(fbody, dict)
                      else None})
    recorder.add('A6', 'team-create',
                 f"teams 10 through 17 in the same game, against max_teams "
                 f"{caps['max_teams']} and the 2..16 game-create cap",
                 'POST', '/api/teams/', {'repeated': len(flood)},
                 max((r['status'] for r in flood), default=0),
                 {'per_team': flood})

    # 4. Enrol past team_size_max onto one team, through both surfaces that
    #    place a student on a team.
    over = caps['team_size_max'] + 2
    enrolled = []
    for n in range(1, over + 1):
        payload = {'action': 'add', 'section_id': section,
                   'student_id': f'CAP{n:03d}',
                   'display_name': f'Cap Probe {n}',
                   'email': f'cap{n:03d}@example.invalid'}
        code, body = S.api(port, 'POST', '/api/roster/', instructor, payload)
        row = {'n': n, 'status': code, 'response': _trim(body, 300)}
        if isinstance(body, dict) and body.get('user_id'):
            row['user_id'] = body['user_id']
        enrolled.append(row)
    recorder.add('A6', 'roster-add',
                 f'enrol {over} students into a section already holding '
                 f"{out['before']['enrollments_in_section']}",
                 'POST', '/api/roster/', {'repeated': over},
                 max((r['status'] for r in enrolled), default=0),
                 {'per_student': enrolled})

    user_ids = [r['user_id'] for r in enrolled if r.get('user_id')]
    assignments = [{'user_id': uid, 'team_id': seed_team['id']}
                   for uid in user_ids]
    payload = {'action': 'assign', 'assignments': assignments}
    code, body = S.api(port, 'PUT', '/api/team-management/', instructor,
                       payload)
    recorder.add('A6', 'team-management',
                 f'assign {len(assignments)} students to one team whose '
                 f"team_size_max is {caps['team_size_max']}",
                 'PUT', '/api/team-management/', payload, code, body)

    per_user = []
    for uid in user_ids:
        acode, abody = S.api(port, 'POST', f'/api/users/{uid}/assign-team/',
                             instructor, {'team_id': seed_team['id']})
        per_user.append({'user_id': uid, 'status': acode,
                         'response': _trim(abody, 200)})
    recorder.add('A6', 'assign-team',
                 f'the same over-cap assignment through the per-user route',
                 'POST', '/api/users/<id>/assign-team/',
                 {'team_id': seed_team['id'], 'repeated': len(user_ids)},
                 max((r['status'] for r in per_user), default=0),
                 {'per_user': per_user})

    out['after'] = S.shell_json(
        database,
        'import fixture_bodies as F\n'
        f'out = F.cohort_state({section}, {seeded["game_id"]})\n'
        f'games = F.games_for_section({section})\n'
        'print("---COHORT---")\n'
        'print(json.dumps({"state": out, "games": games}, default=str))\n',
        '---COHORT---')
    return out


if __name__ == '__main__':
    raise SystemExit(main())
