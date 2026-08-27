#!/usr/bin/env python3
"""Full multi-round competition playthrough with bot teams.

Drives a complete N-round game against a running backend: every team is a bot
that makes strategy-differentiated decisions (budget + marketing per product-
market) each round, with adversarial operator/participant events injected per
round, then the operator closes -> processes -> advances. After each round it
asserts the system stayed healthy (resolution succeeded, a leaderboard was
produced, the resolution manifest completed) so engine/lifecycle defects that
only appear over a real multi-round game with diverse data surface here — before
scarce human volunteers are spent on them.

ISOLATED USE ONLY. Point DB_* and GS_SIM_BASE at a disposable stack.
  GS_SIM_BASE=http://127.0.0.1:8058 GS_SIM_GAME=24 GS_SIM_ROUNDS=6 \
  PYTHONPATH=<backend> DJANGO_SETTINGS_MODULE=globalstrat.settings \
  python3 full_playthrough_sim.py
"""
import os, json, urllib.request, urllib.error, warnings
warnings.filterwarnings('ignore')
import django; django.setup()
from core.models import (User, Team, Round, Enrollment, DecisionSubmission,
                         ResolutionManifest)
from core.authentication import create_access_token
import core.models as _m
Game = _m.Game

BASE = os.environ.get('GS_SIM_BASE', 'http://127.0.0.1:8058')
GID = int(os.environ.get('GS_SIM_GAME', '24'))
ROUNDS = int(os.environ.get('GS_SIM_ROUNDS', '6'))

# Strategy profiles: (rd, marketing, strategy) budget in millions, price factor, volume factor.
PROFILES = [
    ('aggressive_rd',   (8, 2, 1), 1.05, 1.2),
    ('marketing_heavy', (2, 8, 1), 0.95, 1.4),
    ('balanced',        (4, 4, 2), 1.00, 1.0),
    ('conservative',    (1, 1, 1), 1.10, 0.7),
]

def call(method, path, token, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE+path, data=data, method=method,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        b = e.read().decode()
        try: return e.code, json.loads(b)
        except: return e.code, b[:200]
    except Exception as e:
        return 0, str(e)[:200]

game = Game.objects.get(id=GID)
teams = list(Team.objects.filter(game=game).order_by('id'))
def tok_for_team(team):
    e = Enrollment.objects.filter(team_id=team.id).first()
    return create_access_token(User.objects.get(user_id=e.user_id)) if e else None
inst = User.objects.filter(role='instructor', username__icontains=str(game.name).split('-')[-1]).first() \
       or User.objects.filter(role='instructor').first()
itok = create_access_token(inst)

team_profiles = {t.id: PROFILES[i % len(PROFILES)] for i, t in enumerate(teams)}
report = {'base': BASE, 'game_id': GID, 'rounds': [], 'issues': []}

def issue(msg):
    report['issues'].append(msg)

def play_round(rn):
    rec = {'round': rn, 'decisions_submitted': 0, 'marketing_ok': 0, 'events': []}
    rnd = Round.objects.get(game=game, round_number=rn)
    # open a generous window
    call('POST', f'/api/games/{GID}/instructor/extend-deadline/', itok, {'hours': 72})

    # rotating adversarial events for this round
    missing_team = teams[rn % len(teams)]
    correct_team = teams[(rn + 1) % len(teams)]
    deactivate_team = teams[(rn + 2) % len(teams)] if rn == 2 else None

    for t in teams:
        if t.id == missing_team.id:
            continue  # missing: this team never submits this round
        prof_name, (rd_b, mk_b, st_b), pricef, volf = team_profiles[t.id]
        tok = tok_for_team(t)
        if not tok:
            continue
        # ensure a submission exists
        call('POST', f'/api/games/{GID}/teams/{t.id}/decisions/round/{rn}/', tok, {})
        # budget (varied by profile)
        call('PATCH', f'/api/games/{GID}/teams/{t.id}/decisions/round/{rn}/budget/', tok,
             {'rd_budget': rd_b*1_000_000, 'marketing_budget': mk_b*1_000_000,
              'strategy_budget': st_b*1_000_000})
        rec['decisions_submitted'] += 1
        # marketing per product-market (best effort — diverse price/volume)
        s_ctx, ctx = call('GET', f'/api/games/{GID}/teams/{t.id}/context/marketing/', tok)
        if s_ctx == 200 and isinstance(ctx, dict):
            md = []
            for pm in ctx.get('product_markets', []):
                feats = [f['feature_id'] for f in pm.get('feature_levels', [])][:1] or [1]
                for mk in pm.get('markets', []):
                    vol = int(10000 * volf)
                    md.append({
                        'team_product': pm['product_id'], 'market': mk['market_id'],
                        'retail_price': round(500 * pricef, 2),
                        'production_volume': vol,
                        'promotion_budget': mk_b * 100_000,
                        'sales_team_count': 2,
                        'campaign_focus_feature_ids': feats,
                        'channel_digital_pct': 1.0, 'channel_traditional_pct': 0.0,
                        'channel_trade_pct': 0.0,
                        'distribution_strategy': 'hybrid',
                        'distribution_investment': 0,
                        'production_source_market': mk['market_id'],
                        'demand_estimate': vol,
                    })
            if md:
                s_mk, _ = call('PATCH', f'/api/games/{GID}/teams/{t.id}/decisions/round/{rn}/marketing/', tok,
                               {'marketing_decisions': md})
                if s_mk in (200, 201):
                    rec['marketing_ok'] += 1

    # deactivate a team mid-game (round 2)
    if deactivate_team is not None:
        s_d, _ = call('POST', f'/api/games/{GID}/instructor/teams/{deactivate_team.id}/participation/', itok,
                      {'action': 'deactivate', 'reason': f'Playthrough incident drill round {rn}',
                       'confirmation': f'DEACTIVATE TEAM {deactivate_team.id}'})
        rec['events'].append({'deactivate_team': deactivate_team.id, 'http': s_d})

    # close (deadline-locks all remaining teams; missing team defaulted)
    s_close, _ = call('POST', f'/api/games/{GID}/round-control/close/', itok, {'reason': 'manual'})
    rec['events'].append({'close': s_close})

    # operator correction on correct_team, then re-lock via reopen+close
    s_unlock, _ = call('POST', f'/api/games/{GID}/teams/{correct_team.id}/decisions/round/{rn}/unlock/', itok, {})
    rec['events'].append({'correction_unlock_team': correct_team.id, 'http': s_unlock})
    if s_unlock == 200:
        call('POST', f'/api/games/{GID}/instructor/extend-deadline/', itok, {'hours': 2})
        call('POST', f'/api/games/{GID}/round-control/close/', itok, {'reason': 'manual'})

    # process
    s_proc, d_proc = call('POST', f'/api/games/{GID}/round-control/process/', itok,
                          {'force': False, 'reason': f'playthrough round {rn}'}, timeout=120)
    rec['process_http'] = s_proc
    if s_proc != 200:
        issue(f'round {rn}: process returned {s_proc}: {str(d_proc)[:120]}')

    # leaderboard produced?
    s_lb, d_lb = call('GET', f'/api/games/{GID}/leaderboard/round/{rn}/', itok)
    rankings = d_lb.get('rankings', []) if isinstance(d_lb, dict) else []
    rec['leaderboard_count'] = len(rankings)
    if s_proc == 200 and not rankings:
        issue(f'round {rn}: processed but leaderboard empty')

    # manifest completed (output hash set)?
    man = ResolutionManifest.objects.filter(game=game, round=rnd).first()
    rec['manifest_complete'] = bool(man and man.output_sha256)
    if s_proc == 200 and not rec['manifest_complete']:
        issue(f'round {rn}: processed but resolution manifest incomplete')

    # deactivated team excluded?
    if deactivate_team is not None:
        rec['deactivated_excluded'] = deactivate_team.id not in [r.get('team_id') for r in rankings]
        if not rec['deactivated_excluded']:
            issue(f'round {rn}: deactivated team {deactivate_team.id} still in leaderboard')

    # advance (except final round)
    if rn < ROUNDS:
        s_adv, d_adv = call('POST', f'/api/games/{GID}/round-control/advance/', itok,
                            {'force': False, 'reason': f'playthrough advance {rn}'})
        rec['advance_http'] = s_adv
        if s_adv != 200:
            issue(f'round {rn}: advance returned {s_adv}: {str(d_adv)[:120]}')
        # reactivate the team we withdrew, so later rounds are clean
        if deactivate_team is not None:
            call('POST', f'/api/games/{GID}/instructor/teams/{deactivate_team.id}/participation/', itok,
                 {'action': 'reactivate', 'reason': f'Playthrough restore after round {rn}',
                  'confirmation': f'REACTIVATE TEAM {deactivate_team.id}'})
    report['rounds'].append(rec)
    print(f"round {rn}: process={rec['process_http']} leaderboard={rec['leaderboard_count']} "
          f"manifest={'ok' if rec['manifest_complete'] else 'INCOMPLETE'} "
          f"decisions={rec['decisions_submitted']} marketing_ok={rec['marketing_ok']} "
          f"advance={rec.get('advance_http','-')}")

start = game.current_round
for rn in range(start, start + ROUNDS):
    game.refresh_from_db()
    play_round(rn)

report['all_rounds_healthy'] = all(
    r.get('process_http') == 200 and r.get('leaderboard_count', 0) > 0 and r.get('manifest_complete')
    for r in report['rounds'])
report['issue_count'] = len(report['issues'])
print(json.dumps(report, indent=2, default=str))
