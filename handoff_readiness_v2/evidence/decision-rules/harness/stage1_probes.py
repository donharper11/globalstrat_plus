#!/usr/bin/env python3
"""GSP-CRV2-10 Stage 1 — confirm or withdraw, before any repair is designed.

Part A was written from source reading and none of it has been executed. Each
probe here submits a real payload through **both** supported submission APIs,
advances the round where the claim is about what the engine does, and records
what actually happened: the payload, the response, and the rows afterwards.

Writes no runtime code and commits nothing to the candidate. The database is
named for this handoff, the stack claims its ports at run time, and it refuses
to start unless a fixture identity authenticates through the app origin --
CRV2-08's stack was configured on a fixed 8002 that already carried a gunicorn
serving the live database, and only a login failure exposed that its requests
were landing on production.
"""
import contextlib, json, os, pathlib, signal, subprocess, sys, time
import urllib.error, urllib.request

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BACKEND = REPO / 'backend'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EVIDENCE.parent / 'load-failure' / 'harness'))
sys.path.insert(0, str(EVIDENCE.parent / 'adversarial-balance' / 'harness'))
import inventory_run as R      # noqa: E402
import stack as S              # noqa: E402

DATABASE = 'gsp_crv210_probe'
PASSWORD = 'crv210-probe'
BACKUPS = pathlib.Path('/tmp/crv210-backups')


def shell(code, marker='---OUT---', timeout=1800):
    body = (f'import sys\nsys.path.insert(0, {str(HERE)!r})\n'
            f'sys.path.insert(0, {str(EVIDENCE.parent / "adversarial-balance" / "harness")!r})\n'
            f'import json\n{code}\nprint("{marker}")\n'
            'print(json.dumps(result, default=str))\n')
    out = R.manage(DATABASE, 'shell', '-c', body, timeout=timeout)
    if marker not in out.stdout:
        raise SystemExit(f'shell failed:\n{out.stdout[-2500:]}\n{out.stderr[-1500:]}')
    return json.loads(out.stdout.split(marker, 1)[1].strip().splitlines()[0])


class Api:
    def __init__(self, port):
        self.port = port
        self.tokens = {}

    def login(self, username):
        if username in self.tokens:
            return self.tokens[username]
        req = urllib.request.Request(
            f'http://127.0.0.1:{self.port}/api/auth/login/', method='POST',
            data=json.dumps({'username': username,
                             'password': PASSWORD}).encode())
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=60) as r:
            self.tokens[username] = json.loads(r.read())['access']
        return self.tokens[username]

    def call(self, method, path, username, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            f'http://127.0.0.1:{self.port}{path}', method=method, data=data)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {self.login(username)}')
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = (e.read() or b'')[:400].decode('utf-8', 'replace')
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, raw


def start(revision):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    port = S.free_port()
    env = dict(os.environ, DB_NAME=DATABASE, PYTHONUNBUFFERED='1',
               GLOBALSTRAT_ENV='production', GIT_REVISION=revision,
               COMPETITION_BACKUP_DIR=str(BACKUPS),
               DJANGO_SECRET_KEY='crv210-probe-stack',
               DB_PASSWORD=os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***'))
    log = open('/tmp/crv210-stack.log', 'w')
    process = subprocess.Popen(
        ['gunicorn', '-c', 'gunicorn.conf.py', '-b', f'127.0.0.1:{port}',
         'globalstrat.wsgi:application'],
        cwd=str(BACKEND), env=env, stdout=log, stderr=subprocess.STDOUT,
        preexec_fn=os.setsid)
    S.wait_for(f'http://127.0.0.1:{port}/api/auth/login/')
    api = Api(port)
    api.login('crv210_student_1')     # refuse to proceed unless it is ours
    return process, port, api


def stop(process):
    with contextlib.suppress(Exception):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=30)


# ---------------------------------------------------------------------------
# Probe bodies. Each returns the payload sent, the response, and the rows that
# resulted -- never a verdict inferred from the response alone.
# ---------------------------------------------------------------------------

STATE = '''
import seed_probe_game as SP
result = SP.context(%d)
'''

TEAM_STATE = '''
from core.models import Team
from core.models.team_state import TeamPlatform, TeamPlatformFeatureLevel
from core.models.results_financials import RoundResultFinancials
team = Team.objects.get(id=%(team)d)
result = {
    'cash_on_hand': str(team.cash_on_hand),
    'platforms': list(TeamPlatform.objects.filter(team=team)
                      .values('id', 'platform_generation_id', 'status',
                              'development_rounds_remaining', 'name')),
    'feature_levels': list(TeamPlatformFeatureLevel.objects
                           .filter(team_platform__team=team)
                           .values('team_platform_id', 'feature_id',
                                   'current_level')),
    'financials': list(RoundResultFinancials.objects
                       .filter(team=team).order_by('round_number')
                       .values('round_number', 'rd_expense', 'net_income',
                               'cash_closing', 'platform_amortization')),
}
'''


def advance(api, game_id, instructor, note=''):
    """Close, process and advance one round through the supported controls."""
    steps = {}
    for action in ('close', 'process', 'advance'):
        body = {'reason': f'Stage 1 probe {note}'} if action == 'close' else {}
        status, payload = api.call(
            'POST', f'/api/games/{game_id}/round-control/{action}/',
            instructor, body)
        steps[action] = {'status': status,
                         'detail': str(payload)[:200] if status >= 300 else 'ok'}
    return steps


def both_surfaces(api, game_id, round_number, decision_type,
                  first, second):
    """Submit through the per-type and whole-submission APIs.

    `first` and `second` are `(team_id, student, rows)`. They carry separate
    row lists on purpose: the first run reused one team's `team_platform` id
    for both teams, the API accepted the cross-team reference, and the engine
    then wrote duplicate PendingFeatureGain rows that made the round
    unprocessable -- which invalidated every probe that followed.
    """
    team_a, student_a, rows_a = first
    team_b, student_b, rows_b = second
    per_type = api.call(
        'PATCH',
        f'/api/games/{game_id}/teams/{team_a}/decisions/round/{round_number}/'
        f'{decision_type}/', student_a, rows_a)
    key = {'platforms': 'platform_developments', 'rd': 'rd_investments',
           'marketing': 'marketing_decisions',
           'product-retires': 'product_retires'}[decision_type]
    whole = api.call(
        'POST',
        f'/api/games/{game_id}/teams/{team_b}/decisions/round/{round_number}/',
        student_b, {key: rows_b})
    return {
        'per_type_endpoint': (f'PATCH .../decisions/round/{round_number}/'
                              f'{decision_type}/'),
        'per_type': {'team': team_a, 'payload': rows_a,
                     'status': per_type[0], 'body': str(per_type[1])[:300]},
        'whole_submission_endpoint': f'POST .../decisions/round/{round_number}/',
        'whole_submission': {'team': team_b, 'payload': rows_b,
                             'status': whole[0], 'body': str(whole[1])[:300]},
    }


def open_round(api, game_id, instructor, shell_fn, state_sql, note=''):
    """The number of a round that is open, driving the lifecycle if it is not.

    A probe that submits into a closed round measures the deadline gate, not
    the rule it was written for. The first run lost four probes that way after
    one round refused to process.
    """
    for _ in range(4):
        ctx = shell_fn(state_sql)
        if ctx['round_status'] == 'open':
            return ctx['current_round'], None
        steps = advance(api, game_id, instructor, note)
        failed = {k: v for k, v in steps.items() if v['status'] >= 300}
        if failed and ctx['round_status'] != 'open':
            after = shell_fn(state_sql)
            if after['round_status'] != 'open':
                return after['current_round'], {
                    'could_not_open_a_round': steps,
                    'round_status': after['round_status']}
    ctx = shell_fn(state_sql)
    return ctx['current_round'], {'round_status': ctx['round_status']}



PRICE_BASELINE = """
from core.models.decisions import DecisionMarketing
result = {'previous_prices': list(DecisionMarketing.objects
          .filter(team_product_id__in=[%d, %d])
          .order_by('-id').values('team_product_id', 'retail_price')[:4])}
"""

PRICE_STORED = """
from core.models.decisions import DecisionMarketing
result = list(DecisionMarketing.objects
              .filter(submission__round__round_number=%d)
              .values('submission__team__name', 'team_product_id',
                      'retail_price'))
"""

SECTION_CAPS = """
from core.models.course import Enrollment, Section
section = Section.objects.get(section_id=%d)
result = {'section_id': section.section_id, 'max_teams': section.max_teams,
          'team_size_min': section.team_size_min,
          'team_size_max': section.team_size_max,
          'enrolments_before': Enrollment.objects.filter(
              section=section, is_active=True).count()}
"""

ROSTER_ROWS = """
from core.models.course import Enrollment
rows = list(Enrollment.objects.filter(section_id=%d, is_active=True)
            .values('enrollment_id', 'user_id', 'team_id'))
result = {'active_enrolments': len(rows),
          'unassigned_user_ids': [r['user_id'] for r in rows
                                  if r['team_id'] is None]}
"""

AFTER_CAPS = """
from core.models import Team
from core.models.course import Enrollment
result = {
  'active_enrolments': Enrollment.objects.filter(section_id=%d, is_active=True).count(),
  'members_on_probe_team': Enrollment.objects.filter(team_id=%d, is_active=True).count(),
  'teams_in_game': Team.objects.filter(game_id=%d).count(),
}
"""

PRODUCT_ROWS = """
from core.models.team_state import TeamProduct, TeamProductMarket
result = {
  'product': list(TeamProduct.objects.filter(id=%d).values('id','name','status')),
  'markets': list(TeamProductMarket.objects.filter(team_product_id=%d)
                  .values('id','market_id','is_active')),
}
"""

def main():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                            cwd=REPO, capture_output=True,
                            text=True).stdout.strip()
    print(f'Rebuilding {DATABASE}', flush=True)
    R.psql('postgres', f'DROP DATABASE IF EXISTS {DATABASE} WITH (FORCE)')
    if R.psql('postgres', f'CREATE DATABASE {DATABASE}').returncode != 0:
        raise SystemExit('could not create the probe database')
    R.manage(DATABASE, 'migrate', '--noinput')
    R.manage(DATABASE, 'shell', '-c', R.LEGACY_TABLES)

    seeded = shell('import seed_probe_game as SP\nresult = SP.seed()')
    game = seeded['game_id']
    a, b, c = seeded['teams']
    instructor = seeded['instructor']
    print(f"game {game}, teams {[t['name'] for t in seeded['teams']]}", flush=True)

    process, port, api = start(revision)
    output = EVIDENCE / 'stage1-probe-record.json'
    record = {
        'handoff': 'GSP-CRV2-10 Stage 1',
        'stage': ('probe only - no runtime code changed, nothing committed to '
                  'the candidate'),
        'baseline_revision': revision, 'branch': branch,
        'database': DATABASE, 'stack_pid': process.pid, 'port': port,
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'fixture': seeded, 'probes': {},
    }

    def save():
        output.write_text(
            json.dumps(record, indent=2, sort_keys=True, default=str) + '\n')

    state = STATE % game

    def team_ctx(team_id):
        fresh = shell(state)['teams']
        return fresh.get(str(team_id)) or fresh.get(team_id)

    def rounds_until(target):
        steps = []
        for _ in range(target + 2):
            now = shell(state)
            if now['current_round'] >= target:
                return steps
            steps.append({'from_round': now['current_round'],
                          'actions': advance(api, game, instructor,
                                             f'reach round {target}')})
        return steps

    try:
        ctx = shell(state)
        record['context'] = ctx
        gens = ctx['generations']
        record['probe_targets'] = {
            'generations': {g['name']: {
                'unlock_round': g['unlock_round'],
                'development_cost': g['development_cost'],
                'development_rounds': g['development_rounds'],
                'is_starting_platform': g['is_starting_platform']} for g in gens},
            'note': ('Every team starts owning the Gen 1 platform, and '
                     '_process_platform_development skips creation when a '
                     'non-retired platform of that generation exists. A probe '
                     'targeting Gen 1 measures that skip, not the cost rule.'),
        }

        # -- A1 ---------------------------------------------------------------
        gen2 = next(g for g in gens if g['generation_order'] == 2)
        reach = rounds_until(gen2['unlock_round'])
        rnd, blocked = open_round(api, game, instructor, shell, state, 'A1')
        before_a = shell(TEAM_STATE % {'team': a['id']})
        before_b = shell(TEAM_STATE % {'team': b['id']})
        submitted = both_surfaces(
            api, game, rnd, 'platforms',
            (a['id'], a['student'], [{'platform_generation': gen2['id'],
                                      'method': 'in_house',
                                      'committed_cost': '0',
                                      'platform_name': 'Probe A1 free',
                                      'feature_levels': {}}]),
            (b['id'], b['student'], [{'platform_generation': gen2['id'],
                                      'method': 'license',
                                      'committed_cost': '0',
                                      'platform_name': 'Probe A1 licensed',
                                      'feature_levels': {}}]))
        steps = advance(api, game, instructor, 'A1')
        record['probes']['A1_platform_committed_cost_zero'] = {
            'claim': ('a platform development with committed_cost 0 yields the '
                      'platform and charges nothing'),
            'target_generation': gen2,
            'authored_cost': {'in_house': gen2['development_cost'],
                              'license': gen2['license_cost']},
            'submitted_in_round': rnd,
            'round_precondition': blocked or 'round open',
            'rounds_advanced_to_unlock': reach,
            'submission': submitted, 'round_advance': steps,
            'team_a_before': before_a,
            'team_a_after': shell(TEAM_STATE % {'team': a['id']}),
            'team_b_before': before_b,
            'team_b_after': shell(TEAM_STATE % {'team': b['id']}),
        }
        save()

        # -- A2 ---------------------------------------------------------------
        gen3 = next((g for g in gens if g['generation_order'] == 3), gen2)
        rnd, blocked = open_round(api, game, instructor, shell, state, 'A2')
        huge = '999999999'
        submitted = both_surfaces(
            api, game, rnd, 'platforms',
            (a['id'], a['student'], [{'platform_generation': gen3['id'],
                                      'method': 'in_house',
                                      'committed_cost': huge,
                                      'platform_name': 'Probe A2',
                                      'feature_levels': {}}]),
            (b['id'], b['student'], [{'platform_generation': gen3['id'],
                                      'method': 'in_house',
                                      'committed_cost': huge,
                                      'platform_name': 'Probe A2',
                                      'feature_levels': {}}]))
        budget = api.call(
            'PATCH',
            f'/api/games/{game}/teams/{a["id"]}/decisions/round/{rnd}/budget/',
            a['student'], {'rd_budget': '1000', 'marketing_budget': '1000',
                           'strategy_budget': '1000'})
        lock = api.call(
            'POST',
            f'/api/games/{game}/teams/{a["id"]}/decisions/round/{rnd}/lock/',
            a['student'])
        record['probes']['A2_cost_above_cash_and_budget'] = {
            'claim': ('platform development cost is checked against neither the '
                      "team's cash nor its R&D budget"),
            'team_cash_on_hand': team_ctx(a['id'])['cash_on_hand'],
            'committed_cost_submitted': huge, 'rd_budget_set_to': '1000',
            'submitted_in_round': rnd,
            'round_precondition': blocked or 'round open',
            'submission': submitted,
            'budget_write': {'status': budget[0], 'body': str(budget[1])[:200]},
            'lock_attempt': {'status': lock[0], 'body': str(lock[1])[:400]},
        }
        save()

        # -- A1c: another team's platform (found by accident) ------------------
        rnd, blocked = open_round(api, game, instructor, shell, state, 'A1c')
        own_a = team_ctx(a['id'])['team_platform_id']
        own_b = team_ctx(b['id'])['team_platform_id']
        ceiling = (team_ctx(a['id'])['ceilings'] or [{}])[0]
        cross = api.call(
            'PATCH',
            f'/api/games/{game}/teams/{b["id"]}/decisions/round/{rnd}/rd/',
            b['student'],
            [{'team_platform': own_a, 'feature': ceiling.get('feature_id'),
              'method': 'in_house', 'amount': '0',
              'target_level': ceiling.get('ceiling_value') or 10,
              'calculated_cost': '0'}])
        cross_lock = api.call(
            'POST',
            f'/api/games/{game}/teams/{b["id"]}/decisions/round/{rnd}/lock/',
            b['student'])
        record['probes']['A1c_rd_against_another_teams_platform'] = {
            'claim': ('not in Part A: does the write path accept an R&D '
                      "investment naming another team's platform?"),
            'found_how': ("the first probe run sent one team's platform id to "
                          'both teams; the API accepted it and the engine then '
                          'wrote duplicate PendingFeatureGain rows, which made '
                          'the round unprocessable and invalidated four later '
                          'probes'),
            'submitting_team': b['id'], 'its_own_platform': own_b,
            'platform_named_in_payload': own_a,
            'submitted_in_round': rnd,
            'round_precondition': blocked or 'round open',
            'write': {'status': cross[0], 'body': str(cross[1])[:300]},
            'lock_attempt': {'status': cross_lock[0],
                             'body': str(cross_lock[1])[:400]},
        }
        api.call('PATCH',
                 f'/api/games/{game}/teams/{b["id"]}/decisions/round/{rnd}/rd/',
                 b['student'], [])
        save()

        # -- A1b ---------------------------------------------------------------
        rnd, blocked = open_round(api, game, instructor, shell, state, 'A1b')
        ceil_a = (team_ctx(a['id'])['ceilings'] or [{}])[0]
        ceil_b = (team_ctx(b['id'])['ceilings'] or [{}])[0]
        before_a = shell(TEAM_STATE % {'team': a['id']})
        submitted = both_surfaces(
            api, game, rnd, 'rd',
            (a['id'], a['student'],
             [{'team_platform': team_ctx(a['id'])['team_platform_id'],
               'feature': ceil_a.get('feature_id'), 'method': 'in_house',
               'amount': '0', 'target_level': ceil_a.get('ceiling_value') or 10,
               'calculated_cost': '0'}]),
            (b['id'], b['student'],
             [{'team_platform': team_ctx(b['id'])['team_platform_id'],
               'feature': ceil_b.get('feature_id'), 'method': 'in_house',
               'amount': '0', 'target_level': ceil_b.get('ceiling_value') or 10,
               'calculated_cost': '0'}]))
        steps = advance(api, game, instructor, 'A1b')
        record['probes']['A1b_rd_target_level_free'] = {
            'claim': ('target_level with amount 0 and calculated_cost 0 grants '
                      'the level outright and charges nothing'),
            'ceilings_targeted': {'team_a': ceil_a, 'team_b': ceil_b},
            'submitted_in_round': rnd,
            'round_precondition': blocked or 'round open',
            'submission': submitted, 'round_advance': steps,
            'team_a_before': before_a,
            'team_a_after': shell(TEAM_STATE % {'team': a['id']}),
        }
        save()

        # -- A3 ---------------------------------------------------------------
        timing = {}
        for label, order in (('development_rounds_0', 1),
                             ('development_rounds_2', 2)):
            gen = next((g for g in gens if g['generation_order'] == order), None)
            if gen is None:
                timing[label] = {'skipped': 'no such generation'}
                continue
            rnd, blocked = open_round(api, game, instructor, shell, state,
                                      f'A3 {label}')
            before = shell(TEAM_STATE % {'team': c['id']})
            owns = [pl for pl in before['platforms']
                    if pl['platform_generation_id'] == gen['id']]
            sent = api.call(
                'PATCH',
                f'/api/games/{game}/teams/{c["id"]}/decisions/round/{rnd}/platforms/',
                c['student'],
                [{'platform_generation': gen['id'], 'method': 'in_house',
                  'committed_cost': str(gen['development_cost']),
                  'platform_name': f'Probe A3 {label}', 'feature_levels': {}}])
            steps = advance(api, game, instructor, f'A3 {label}')
            after = shell(TEAM_STATE % {'team': c['id']})
            timing[label] = {
                'authored_development_rounds': gen['development_rounds'],
                'unlock_round': gen['unlock_round'],
                'team_already_owned_this_generation': bool(owns),
                'submitted_in_round': rnd,
                'round_precondition': blocked or 'round open',
                'submit_status': sent[0], 'submit_body': str(sent[1])[:250],
                'round_advance': steps,
                'platforms_before': before['platforms'],
                'platforms_after': after['platforms'],
                'round_now': shell(state)['current_round'],
            }
        record['probes']['A3_platform_ready_timing'] = {
            'claim': ('a platform is ready in the round it was created, and an '
                      'authored development_rounds of 2 behaves as 1'),
            'observations': timing,
        }
        save()

        # -- A4 ---------------------------------------------------------------
        rnd, blocked = open_round(api, game, instructor, shell, state, 'A4')
        ta, tb = team_ctx(a['id']), team_ctx(b['id'])
        pa = (ta['products'] or [None])[0]
        pb = (tb['products'] or [None])[0]
        ma = (ta['markets'] or [None])[0]
        mb = (tb['markets'] or [None])[0]
        if pa and pb and ma and mb:
            baseline = shell(PRICE_BASELINE % (pa['id'], pb['id']))

            focus_a = [f['feature_id'] for f in (ta['ceilings'] or [])][:1]
            focus_b = [f['feature_id'] for f in (tb['ceilings'] or [])][:1]

            def price_rows(product, market, price, focus):
                # The full marketing contract. The first attempt sent only the
                # price fields and every write came back 400 on missing
                # required fields, which would have read as "a band refused it"
                # if the response body had not been recorded.
                return [{'team_product': product['id'], 'market': market,
                         'retail_price': price, 'promotion_budget': '1000',
                         'campaign_focus_feature_ids': focus,
                         'channel_digital_pct': '0.4000',
                         'channel_traditional_pct': '0.4000',
                         'channel_trade_pct': '0.2000',
                         'distribution_strategy': 'mass_retail',
                         'distribution_investment': '1000',
                         'sales_team_count': 1,
                         'distribution_channel_detail': {},
                         'production_volume': 10,
                         'production_source_market': market,
                         'demand_estimate': 10}]

            high = both_surfaces(
                api, game, rnd, 'marketing',
                (a['id'], a['student'], price_rows(pa, ma, '99999', focus_a)),
                (b['id'], b['student'], price_rows(pb, mb, '99999', focus_b)))
            low = both_surfaces(
                api, game, rnd, 'marketing',
                (a['id'], a['student'], price_rows(pa, ma, '1', focus_a)),
                (b['id'], b['student'], price_rows(pb, mb, '1', focus_b)))
            price_probe = {
                'baseline': baseline, 'ten_times_and_more': high,
                'one_tenth_and_less': low,
                'stored_after_both': shell(PRICE_STORED % rnd),
                'submitted_in_round': rnd,
                'round_precondition': blocked or 'round open'}
        else:
            price_probe = {'skipped': 'no active product or market on a team'}
        record['probes']['A4_price_band'] = {
            'claim': ('retail_price is validated > 0 and nothing else: no band, '
                      'no alert, no anchor, no rule for a blank price'),
            'observations': price_probe,
        }
        save()

        # -- A6 ---------------------------------------------------------------
        caps = shell(SECTION_CAPS % seeded['section_id'])
        added = []
        for n in range(caps['team_size_max'] + 3):
            status, body = api.call('POST', '/api/roster/', instructor, {
                'action': 'add', 'section_id': caps['section_id'],
                'student_id': f'crv210-overflow-{n}',
                'display_name': f'Overflow {n}',
                'email': f'crv210_overflow_{n}@example.invalid'})
            added.append({'n': n, 'status': status, 'body': str(body)[:140]})
        roster = shell(ROSTER_ROWS % caps['section_id'])
        assignments = [{'user_id': uid, 'team_id': a['id']}
                       for uid in roster['unassigned_user_ids']]
        assign = api.call(
            'PUT', f"/api/team-management/?section_id={caps['section_id']}",
            instructor, {'action': 'assign', 'assignments': assignments})
        record['probes']['A6_cohort_caps'] = {
            'claim': ('max_teams, team_size_min and team_size_max are defined '
                      'and nothing enforces them at enrolment or assignment'),
            'section': caps,
            'enrolment_attempts_via_roster_add': added,
            'assignment_attempt_via_team_management': {
                'assigned': len(assignments), 'status': assign[0],
                'body': str(assign[1])[:300]},
            'after': shell(AFTER_CAPS % (caps['section_id'], a['id'], game)),
        }
        save()

        # -- D1 ---------------------------------------------------------------
        rnd, blocked = open_round(api, game, instructor, shell, state, 'D1')
        tb = team_ctx(b['id'])
        product = (tb['products'] or [None])[0]
        if product:
            rows_sql = PRODUCT_ROWS % (product['id'], product['id'])
            before_rows = shell(rows_sql)
            sent = api.call(
                'PATCH',
                f'/api/games/{game}/teams/{b["id"]}/decisions/round/{rnd}/product-retires/',
                b['student'],
                [{'team_product': product['id'], 'timing': 'end_of_round'}])
            steps = advance(api, game, instructor, 'D1')
            retire_probe = {'product': product, 'submitted_in_round': rnd,
                            'round_precondition': blocked or 'round open',
                            'before': before_rows,
                            'submit_status': sent[0],
                            'submit_body': str(sent[1])[:250],
                            'round_advance': steps, 'after': shell(rows_sql)}
        else:
            retire_probe = {'skipped': 'no product on the team'}
        record['probes']['D1_end_of_round_retirement'] = {
            'claim': ("end_of_round retirement sets status='retired' but never "
                      'deactivates TeamProductMarket rows'),
            'observations': retire_probe,
        }
        save()
    except Exception as exc:
        record['aborted'] = {'after_probes': sorted(record.get('probes', {})),
                             'error': f'{type(exc).__name__}: {exc}'[:400]}
        raise
    finally:
        stop(process)
        record['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        output.write_text(
            json.dumps(record, indent=2, sort_keys=True, default=str) + '\n')

    print(f"\nwrote stage1-probe-record.json with {len(record['probes'])} probes")
    for name in sorted(record['probes']):
        print(f'  {name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
