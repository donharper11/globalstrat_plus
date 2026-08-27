#!/usr/bin/env python3
"""Scripted volunteer competition-cycle simulation.

Drives one round lifecycle against a running backend, injecting the adversarial
operator/participant events a live competition must survive, and asserts the
system's response to each. Designed to run against an ISOLATED stack (never
production): set DB_* to a disposable database and BASE to its backend.

Usage:
  GS_SIM_BASE=http://127.0.0.1:8056 GS_SIM_GAME=24 \
  PYTHONPATH=<backend> DJANGO_SETTINGS_MODULE=globalstrat.settings \
  python3 volunteer_cycle_sim.py
"""
import os, json, threading, urllib.request, urllib.error, warnings
warnings.filterwarnings('ignore')
import django; django.setup()
from core.models import (User, Team, Round, DecisionSubmission, DecisionAuditEvent,
                         OperatorAuditEvent)
from core.authentication import create_access_token

BASE = os.environ.get('GS_SIM_BASE', 'http://127.0.0.1:8056')
GID  = int(os.environ.get('GS_SIM_GAME', '24'))

def call(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE+path, data=data, method=method,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        b = e.read().decode()
        try: return e.code, json.loads(b)
        except: return e.code, b[:200]

game = __import__('core.models', fromlist=['Game']).Game.objects.get(id=GID)
RN = game.current_round
rnd = Round.objects.get(game=game, round_number=RN)
teams = list(Team.objects.filter(game=game).order_by('id'))
def member_tok(team):
    from core.models import Enrollment
    e = Enrollment.objects.filter(team_id=team.id).first()
    if not e: return None
    return create_access_token(User.objects.get(user_id=e.user_id))

# instructor token
inst = User.objects.filter(role='instructor').filter(
    username__icontains=str(game.name).split('-')[-1] if '-' in str(game.name) else 'instructor').first()
inst = inst or User.objects.filter(role='instructor').first()
itok = create_access_token(inst)

results = []
def record(scenario, passed, detail):
    results.append({'scenario': scenario, 'pass': bool(passed), 'detail': detail})

# Assign teams to scenarios (need >=6 teams)
tL, tM, tD, tC, tX, tI = teams[3], teams[4], teams[5], teams[6], teams[7], teams[8]

# --- Reset to a clean OPEN round with a future deadline ---
call('POST', f'/api/games/{GID}/instructor/extend-deadline/', itok, {'hours': 48})
rnd.refresh_from_db()

# === Scenario 1: deadline extension is honoured (students can still submit) ===
tok = member_tok(tL)
s_ext, _ = call('POST', f'/api/games/{GID}/instructor/extend-deadline/', itok, {'hours': 72})
s_sub, _ = call('POST', f'/api/games/{GID}/teams/{tL.id}/decisions/round/{RN}/', tok, {})
record('deadline_extension', s_ext == 200 and s_sub in (200, 201),
       {'extend_http': s_ext, 'submit_after_extend_http': s_sub})

# === Scenario 2: DUPLICATE submission (two concurrent writers, same team) ===
tok_d = member_tok(tD)
codes = {}
def dup_write(i):
    codes[i] = call('POST', f'/api/games/{GID}/teams/{tD.id}/decisions/round/{RN}/', tok_d, {})[0]
th = [threading.Thread(target=dup_write, args=(i,)) for i in range(2)]
[t.start() for t in th]; [t.join() for t in th]
n_subs = DecisionSubmission.objects.filter(team=tD, round=rnd).count()
record('duplicate_submission', all(c in (200,201,409,429) for c in codes.values()) and n_subs == 1,
       {'concurrent_http': codes, 'submission_rows': n_subs, 'expect': 'exactly one canonical submission row'})

# === Scenario 3: MISSING submission (never submits -> defaulted at close) ===
DecisionSubmission.objects.filter(team=tM, round=rnd).delete()

# === Scenario 4a: CORRECTION setup — team submits a draft (locked at deadline) ===
tok_c = member_tok(tC)
s_cc, _ = call('POST', f'/api/games/{GID}/teams/{tC.id}/decisions/round/{RN}/', tok_c, {})
# (assertion happens after the final close, below, on the deadline-locked submission)

# === Scenario 5: TEAM DEACTIVATION (guards + excluded from resolution) ===
# guard checks first
s_bad, _ = call('POST', f'/api/games/{GID}/instructor/teams/{tX.id}/participation/', itok,
                {'action': 'deactivate', 'reason': 'short', 'confirmation': 'wrong'})
s_ok, d_ok = call('POST', f'/api/games/{GID}/instructor/teams/{tX.id}/participation/', itok,
                  {'action': 'deactivate', 'reason': 'Withdrawn for volunteer-cycle incident drill',
                   'confirmation': f'DEACTIVATE TEAM {tX.id}'})
tX.refresh_from_db()
record('team_deactivation', s_bad == 400 and s_ok == 200 and tX.participation_status == 'withdrawn',
       {'guard_rejected_bad_input_http': s_bad, 'deactivate_http': s_ok,
        'participation_status': tX.participation_status})

# === Scenario 6: INCIDENT DRILL — accidental close then operator reopen ===
s_close1, _ = call('POST', f'/api/games/{GID}/round-control/close/', itok, {'reason': 'manual'})
rnd.refresh_from_db(); closed_status = rnd.status
s_reopen, d_reopen = call('POST', f'/api/games/{GID}/instructor/extend-deadline/', itok, {'hours': 24})
rnd.refresh_from_db()
tok_i = member_tok(tI)
s_resub, _ = call('POST', f'/api/games/{GID}/teams/{tI.id}/decisions/round/{RN}/', tok_i, {})
record('incident_reopen_after_close',
       s_close1 == 200 and closed_status == 'closed'
       and isinstance(d_reopen, dict) and d_reopen.get('reopened') is True
       and rnd.status == 'open' and s_resub in (200, 201),
       {'close_http': s_close1, 'closed_status': closed_status,
        'reopen_reported': (d_reopen.get('reopened') if isinstance(d_reopen, dict) else None),
        'status_after_reopen': rnd.status, 'resubmit_http': s_resub})

# === Scenario 7: LATE submission (after final close -> rejected) ===
call('POST', f'/api/games/{GID}/round-control/close/', itok, {'reason': 'manual'})
rnd.refresh_from_db()
tok_late = member_tok(tL)
s_late, d_late = call('POST', f'/api/games/{GID}/teams/{tL.id}/decisions/round/{RN}/', tok_late, {})
record('late_submission_rejected', s_late in (403, 409, 400),
       {'post_close_submit_http': s_late, 'detail': (d_late if isinstance(d_late, (str,)) else str(d_late)[:120]),
        'expect': 'rejected once the round is closed'})

# === Scenario 4b: CORRECTION — operator unlocks the deadline-locked submission ===
sub_c = DecisionSubmission.objects.filter(team=tC, round=rnd).first()
locked_before = sub_c.status if sub_c else None
n_op_before = OperatorAuditEvent.objects.filter(game=game, round=rnd, action='unlock_submission_for_correction').count()
s_unlock, d_unlock = call('POST', f'/api/games/{GID}/teams/{tC.id}/decisions/round/{RN}/unlock/', itok, {})
n_op_after = OperatorAuditEvent.objects.filter(game=game, round=rnd, action='unlock_submission_for_correction').count()
record('operator_correction',
       locked_before == 'locked' and s_unlock == 200
       and (d_unlock.get('status') if isinstance(d_unlock, dict) else None) == 'draft'
       and n_op_after == n_op_before + 1,
       {'submission_locked_at_deadline': locked_before, 'unlock_http': s_unlock,
        'status_after': d_unlock.get('status') if isinstance(d_unlock, dict) else d_unlock,
        'new_operator_audit_events': n_op_after - n_op_before,
        'note': 'realistic dispute path: a submission locked at the deadline is unlocked by the operator to correct an error, fully audited'})

# === Missing default recorded at close ===
miss_ever = DecisionAuditEvent.objects.filter(
    game=game, team=tM, round=rnd, endpoint='engine:close_round',
    action='missing_submission_defaulted').exists()
miss_actions = list(DecisionAuditEvent.objects.filter(
    game=game, team=tM, round=rnd, endpoint='engine:close_round').order_by('id').values_list('action', flat=True))
record('missing_defaulted_recorded', miss_ever,
       {'defaulted_recorded_at_first_close': miss_ever, 'all_close_actions_for_team': miss_actions,
        'note': 'genuinely-missing team is defaulted at the first close; a later reopen+reclose (incident drill) then deadline_locks the now-existing empty submission'})

# Operator re-locks after the correction: reopen then close so every active team
# is locked again before resolution (process refuses an unlocked team).
call('POST', f'/api/games/{GID}/instructor/extend-deadline/', itok, {'hours': 6})
call('POST', f'/api/games/{GID}/round-control/close/', itok, {'reason': 'manual'})

# === Process the round; deactivated team excluded from leaderboard ===
s_proc, d_proc = call('POST', f'/api/games/{GID}/round-control/process/', itok, {'force': False, 'reason': 'sim process'})
s_lb, d_lb = call('GET', f'/api/games/{GID}/leaderboard/round/{RN}/', itok)
ranked_team_ids = []
if isinstance(d_lb, dict) and isinstance(d_lb.get('rankings'), list):
    ranked_team_ids = [r.get('team_id') for r in d_lb['rankings']]
record('deactivated_excluded_from_resolution',
       s_proc == 200 and tX.id not in ranked_team_ids and len(ranked_team_ids) > 0,
       {'process_http': s_proc, 'deactivated_team': tX.id,
        'in_leaderboard': tX.id in ranked_team_ids, 'ranked_count': len(ranked_team_ids)})

summary = {'base': BASE, 'game_id': GID, 'round': RN,
           'scenarios': results,
           'passed': sum(1 for r in results if r['pass']),
           'failed': sum(1 for r in results if not r['pass']),
           'all_pass': all(r['pass'] for r in results)}
print(json.dumps(summary, indent=2, default=str))
