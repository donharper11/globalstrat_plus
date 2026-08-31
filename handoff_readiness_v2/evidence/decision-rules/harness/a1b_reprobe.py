#!/usr/bin/env python3
"""A1b, probed for what it actually claims.

The first attempt read the feature level one round after submitting and found
it unchanged. That settles nothing: feature gains are lagged through
`PendingFeatureGain`, so one advance cannot distinguish "the grant never
happened" from "the grant has not landed yet".

This submits target_level R&D on the team's own active platform with amount 0
and calculated_cost 0, then advances three rounds, reading the level and the
R&D charge after each. It also records what a brand-new platform's features are
initialised to, which is where the first run's only level movement came from.
"""
import json, subprocess, sys, pathlib, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage1_probes as P   # noqa: E402

EVIDENCE = P.EVIDENCE
LEVELS = """
from core.models import Team
from core.models.team_state import (PendingFeatureGain, TeamPlatform,
                                    TeamPlatformFeatureLevel)
from core.models.results_financials import RoundResultFinancials
team = Team.objects.get(id=%(team)d)
result = {
  'levels': list(TeamPlatformFeatureLevel.objects.filter(team_platform_id=%(platform)d)
                 .values('feature_id', 'current_level').order_by('feature_id')),
  'pending': list(PendingFeatureGain.objects
                  .filter(team_platform_id=%(platform)d)
                  .values('feature_id', 'applies_round', 'gain_amount',
                          'applied')),
  'rd_expense': list(RoundResultFinancials.objects.filter(team=team)
                     .order_by('round_number')
                     .values('round_number', 'rd_expense')),
}
"""


def main():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=P.REPO,
                              capture_output=True, text=True).stdout.strip()
    P.R.psql('postgres', f'DROP DATABASE IF EXISTS {P.DATABASE} WITH (FORCE)')
    P.R.psql('postgres', f'CREATE DATABASE {P.DATABASE}')
    P.R.manage(P.DATABASE, 'migrate', '--noinput')
    P.R.manage(P.DATABASE, 'shell', '-c', P.R.LEGACY_TABLES)
    seeded = P.shell('import seed_probe_game as SP\nresult = SP.seed()')
    game = seeded['game_id']
    a = seeded['teams'][0]
    instructor = seeded['instructor']
    state = P.STATE % game

    process, port, api = P.start(revision)
    record = {'handoff': 'GSP-CRV2-10 Stage 1 — A1b re-probe',
              'baseline_revision': revision, 'database': P.DATABASE,
              'stack_pid': process.pid, 'port': port,
              'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'why': ('the first attempt read the level one round after '
                      'submitting; PendingFeatureGain lags the grant, so one '
                      'advance could not tell "never happened" from "not yet"'),
              'steps': []}
    try:
        ctx = P.shell(state)
        team = ctx['teams'].get(str(a['id'])) or ctx['teams'].get(a['id'])
        platform = team['team_platform_id']
        ceiling = (team['ceilings'] or [{}])[0]
        record['target'] = {'team': a['id'], 'platform': platform,
                            'ceiling': ceiling}
        sql = LEVELS % {'team': a['id'], 'platform': platform}
        record['before'] = P.shell(sql)

        rnd, blocked = P.open_round(api, game, instructor, P.shell, state, 'A1b')
        payload = [{'team_platform': platform,
                    'feature': ceiling.get('feature_id'),
                    'method': 'in_house', 'amount': '0',
                    'target_level': ceiling.get('ceiling_value') or 10,
                    'calculated_cost': '0'}]
        sent = api.call(
            'PATCH',
            f'/api/games/{game}/teams/{a["id"]}/decisions/round/{rnd}/rd/',
            a['student'], payload)
        record['submission'] = {'round': rnd, 'payload': payload,
                                'round_precondition': blocked or 'round open',
                                'status': sent[0], 'body': str(sent[1])[:300]}

        for step in range(3):
            actions = P.advance(api, game, instructor, f'A1b step {step}')
            record['steps'].append({
                'advance': {k: v['status'] for k, v in actions.items()},
                'round_now': P.shell(state)['current_round'],
                'state': P.shell(sql)})
    finally:
        P.stop(process)
        record['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        (EVIDENCE / 'stage1-a1b-reprobe.json').write_text(
            json.dumps(record, indent=2, sort_keys=True, default=str) + '\n')

    target_feature = record['target']['ceiling'].get('feature_id')
    def level_of(state):
        for row in state['levels']:
            if row['feature_id'] == target_feature:
                return row['current_level']
        return None
    print('target feature', target_feature,
          '| ceiling', record['target']['ceiling'].get('ceiling_value'))
    print('before:', level_of(record['before']))
    for i, step in enumerate(record['steps']):
        print(f"after advance {i+1} (round {step['round_now']}):",
              level_of(step['state']),
              '| pending', step['state']['pending'],
              '| rd_expense', [(r['round_number'], r['rd_expense'])
                               for r in step['state']['rd_expense']][-2:])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
