"""Capture finding F7's reproduction: the pricing screen's default row is refused.

The original capture lived in the first walkthrough's JSON, which later clean
runs overwrote. This re-issues exactly the body `MarketingPage` builds for a
fresh row, and the same body with the two fields a student can supply, so the
report cites a file rather than a memory.
"""
import json
import pathlib
import urllib.error
import urllib.request

SCRATCH = pathlib.Path(__file__).resolve().parent
EVIDENCE = pathlib.Path(
    '/home/ubuntu/projects/globalstrat+/.claude/worktrees'
    '/agent-a0ae8bfea94e98414/handoff_readiness_v2/evidence/bug-sweep'
    '/frontend-verification-2026-09-12')
ports = json.loads((SCRATCH / 'runtime' / 'stack.ports').read_text())
fixture = json.loads((SCRATCH / 'fixture.json').read_text())
BASE = f'http://127.0.0.1:{ports["app"]}'
GAME = fixture['game_id']
TEAM = fixture['team_a_id']


def call(method, path, token=None, body=None, headers=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=None if body is None else json.dumps(body).encode())
    req.add_header('Content-Type', 'application/json')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')


def row(**over):
    base = {
        'team_product': 1, 'market': 1, 'retail_price': 400,
        'promotion_budget': 0, 'campaign_focus_feature_ids': [],
        'channel_digital_pct': 0.34, 'channel_traditional_pct': 0.33,
        'channel_trade_pct': 0.33, 'distribution_strategy': 'mass_retail',
        'distribution_investment': 0, 'sales_team_count': 0,
        'distribution_channel_detail': {}, 'production_volume': 0,
        'production_source_market': None, 'demand_estimate': 0,
    }
    base.update(over)
    return base


def main():
    _, tok = call('POST', '/api/auth/login/',
                  body={'username': fixture['instructor'],
                        'password': fixture['password']})
    instructor = json.loads(tok)['access']
    _, rc = call('GET', f'/api/games/{GAME}/round-control/', instructor)
    current = (json.loads(rc).get('round') or {}).get('round_number')

    _, tok = call('POST', '/api/auth/login/',
                  body={'username': fixture['students'][0]['username'],
                        'password': fixture['password']})
    student = json.loads(tok)['access']

    path = f'/api/games/{GAME}/teams/{TEAM}/decisions/round/{current}/marketing/'
    default_body = {'marketing_decisions': [row()]}
    fixed_body = {'marketing_decisions': [
        row(campaign_focus_feature_ids=[1], production_source_market=1,
            production_volume=5000)]}

    s1, b1 = call('PATCH', path, student, default_body)
    s2, b2 = call('PATCH', path, student, fixed_body)

    out = EVIDENCE / 'default-row-refusal.txt'
    out.write_text(f"""GSP-CRV2-13 — reproduction for finding F7
The pricing screen's own default row is refused, and the refusal is silent.

Captured 2026-09-12 against the disposable stack (game {GAME}, team {TEAM},
round {current}).

MarketingPage.js initialises every row with `campaign_focus_feature_ids: []`
and `production_source_market: null` (lines 68-77), and only sends a row once
a price, production volume or promotion budget is non-zero (line 103). So a
student whose first action is to type a price sends exactly REQUEST 1 below.

`autoSave` wraps the call in `catch {{ /* ignore */ }}` (line 123), so the
refusal is never surfaced. Meanwhile the client-side band alert continues to
read "Your entry is saved" / "您的输入已保存", because that text is computed
from local state and not from the response.

REQUEST 1 — the body the screen builds for a fresh row
PATCH {path}
{json.dumps(default_body, indent=2)}

RESPONSE 1
HTTP {s1}
{b1[:1000]}

REQUEST 2 — the same row, with the two fields a student is never prompted for
PATCH {path}
{json.dumps(fixed_body, indent=2)}

RESPONSE 2
HTTP {s2}
{b2[:700]}

The rule itself is sound: response 2 carries the server's own band warning.
The defect is that the screen's default state cannot reach it and says nothing
when it fails.
""", encoding='utf-8')
    print(f'REQUEST 1 -> HTTP {s1}: {b1[:200]}')
    print(f'REQUEST 2 -> HTTP {s2}')
    print(f'written: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
