#!/usr/bin/env python3
"""Stage 1 rework: the probes the first pass did not actually measure.

Four gaps, each measured rather than argued:

1. `development_rounds: 0` activation timing, on a team that does not already
   own that generation. The first pass recorded a 200 and identical platform
   rows, because creation is skipped when a non-retired platform of the
   generation exists -- a response code is not evidence of activation.
2. The second write surface for A1c, A3 and D1. The first pass claimed both
   surfaces throughout and its artifacts carried one write each for those three.
3. A complete lock attempt for the cross-team platform reference, so the
   ownership check is reached instead of masked by an earlier error.
4. The free ceiling-level initialisation, measured on its own rather than
   noticed inside another probe.
"""
import json, subprocess, sys, pathlib, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage1_probes as P   # noqa: E402

EVIDENCE = P.EVIDENCE

PLATFORM_ROWS = """
from core.models.team_state import TeamPlatform, TeamPlatformFeatureLevel
result = {
  'platforms': list(TeamPlatform.objects.filter(team_id=%(team)d)
                    .values('id', 'platform_generation_id', 'status',
                            'development_rounds_remaining', 'name')
                    .order_by('id')),
  'feature_levels': list(TeamPlatformFeatureLevel.objects
                         .filter(team_platform__team_id=%(team)d)
                         .values('team_platform_id', 'feature_id',
                                 'current_level').order_by('team_platform_id')),
}
"""

STRIP = """
from core.models.team_state import TeamPlatform
qs = TeamPlatform.objects.filter(team_id=%(team)d, platform_generation_id=%(gen)d)
before = list(qs.values('id', 'status'))
qs.update(status='retired')
result = {'retired': before,
          'remaining_non_retired': list(
              TeamPlatform.objects.filter(team_id=%(team)d)
              .exclude(status='retired').values('id', 'platform_generation_id'))}
"""

FILL = """
import seed_probe_game as SP
import baseline as BASE
from decimal import Decimal as D
from django.utils import timezone
from core.models import DecisionSubmission, Round, Team
from core.models.cc32_models import CommunicationAssignment, TeamCommunication
from core.models.decisions import DecisionESG, DecisionProductCreate
from core.models.team_state import TeamMarketPresence, TeamPlatform
team = Team.objects.get(id=%(team)d)
rnd = Round.objects.get(game_id=%(game)d, round_number=%(round)d)
sub, _ = DecisionSubmission.objects.get_or_create(
    team=team, round=rnd, defaults={'status': 'draft'})
BASE.build(sub, team)
platform = TeamPlatform.objects.filter(team=team).exclude(status='retired').first()
markets = list(TeamMarketPresence.objects.filter(team=team, status='active')
               .values_list('market_id', flat=True))
DecisionProductCreate.objects.filter(submission=sub).delete()
if platform and markets:
    DecisionProductCreate.objects.create(
        submission=sub, team_platform=platform,
        product_name='Rework R%(round)d ' + team.name,
        positioning='mainstream', target_market_ids=markets[:1])
DecisionESG.objects.update_or_create(
    submission=sub, defaults={'environmental_investment': D('50000'),
                              'social_investment': D('25000')})
for ca in CommunicationAssignment.objects.filter(scenario=team.game.scenario):
    TeamCommunication.objects.update_or_create(
        game=team.game, team=team, round=rnd, assignment=ca,
        defaults={'content': 'Stage 1 rework fixture.', 'word_count': 4,
                  'is_draft': False, 'submitted_at': timezone.now()})
result = {'submission': sub.id, 'filled': True}
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
    a, b, c = seeded['teams']
    instructor = seeded['instructor']
    state = P.STATE % game

    process, port, api = P.start(revision)
    out = EVIDENCE / 'stage1-rework-probes.json'
    record = {'handoff': 'GSP-CRV2-10 Stage 1 rework',
              'baseline_revision': revision, 'database': P.DATABASE,
              'stack_pid': process.pid, 'port': port,
              'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'probes': {}}

    def save():
        out.write_text(json.dumps(record, indent=2, sort_keys=True,
                                  default=str) + '\n')

    try:
        ctx = P.shell(state)
        gens = {g['generation_order']: g for g in ctx['generations']}
        gen0 = gens[1]      # development_rounds 0, the starting generation
        gen2 = gens[2]      # development_rounds 2, the control

        # -- 1. development_rounds 0, on teams that do not own it ------------
        stripped = {t['name']: P.shell(STRIP % {'team': t['id'],
                                                'gen': gen0['id']})
                    for t in (a, b)}
        rnd, blocked = P.open_round(api, game, instructor, P.shell, state, 'dr0')
        before = {t['id']: P.shell(PLATFORM_ROWS % {'team': t['id']})
                  for t in (a, b)}
        rows = lambda name: [{'platform_generation': gen0['id'],
                              'method': 'in_house',
                              'committed_cost': str(gen0['development_cost']),
                              'platform_name': name, 'feature_levels': {}}]
        submitted = P.both_surfaces(
            api, game, rnd, 'platforms',
            (a['id'], a['student'], rows('Rework dr0 per-type')),
            (b['id'], b['student'], rows('Rework dr0 whole')))
        timeline = []
        for step in range(3):
            actions = P.advance(api, game, instructor, f'dr0 step {step}')
            now = P.shell(state)['current_round']
            timeline.append({
                'advance': {k: v['status'] for k, v in actions.items()},
                'round_now': now,
                'team_a': P.shell(PLATFORM_ROWS % {'team': a['id']}),
                'team_b': P.shell(PLATFORM_ROWS % {'team': b['id']})})
        record['probes']['A3_development_rounds_0'] = {
            'claim': ('a generation authored development_rounds 0 is active in '
                      'the round it was created'),
            'why_the_first_pass_could_not_measure_it': (
                'every team owns the starting generation and creation is '
                'skipped when a non-retired platform of it exists, so the '
                'probe recorded a 200 and unchanged rows -- the skip, not the '
                'timing'),
            'fixture': {'starting_platforms_retired': stripped},
            'generation': gen0,
            'submitted_in_round': rnd,
            'round_precondition': blocked or 'round open',
            'submission': submitted,
            'platforms_before': before,
            'timeline': timeline,
        }
        save()

        # -- 2. development_rounds 2 control, both surfaces -------------------
        rnd, blocked = P.open_round(api, game, instructor, P.shell, state, 'dr2')
        rows2 = lambda name: [{'platform_generation': gen2['id'],
                               'method': 'in_house',
                               'committed_cost': str(gen2['development_cost']),
                               'platform_name': name, 'feature_levels': {}}]
        submitted2 = P.both_surfaces(
            api, game, rnd, 'platforms',
            (a['id'], a['student'], rows2('Rework dr2 per-type')),
            (b['id'], b['student'], rows2('Rework dr2 whole')))
        timeline2 = []
        for step in range(3):
            actions = P.advance(api, game, instructor, f'dr2 step {step}')
            timeline2.append({
                'advance': {k: v['status'] for k, v in actions.items()},
                'round_now': P.shell(state)['current_round'],
                'team_a': P.shell(PLATFORM_ROWS % {'team': a['id']}),
                'team_b': P.shell(PLATFORM_ROWS % {'team': b['id']})})
        record['probes']['A3_development_rounds_2_control'] = {
            'claim': 'an authored development_rounds of 2 behaves as 1',
            'generation': gen2,
            'submitted_in_round': rnd,
            'round_precondition': blocked or 'round open',
            'submission': submitted2,
            'timeline': timeline2,
        }
        save()

        # -- 3. free ceiling initialisation, measured on its own --------------
        # A platform created with feature_levels {} -- no feature named -- and
        # what its levels are afterwards.
        created = [pl for pl in timeline2[-1]['team_a']['platforms']
                   if pl['platform_generation_id'] == gen2['id']]
        levels = [row for row in timeline2[-1]['team_a']['feature_levels']
                  if created and row['team_platform_id'] == created[0]['id']]
        ceilings = P.shell("""
from core.models.scenario import PlatformFeatureCeiling
result = list(PlatformFeatureCeiling.objects
              .filter(platform_generation_id=%d)
              .values('feature_id', 'ceiling_value').order_by('feature_id'))
""" % gen2['id'])
        record['probes']['free_ceiling_initialisation'] = {
            'claim': ('a newly created platform has its features initialised '
                      'without any decision naming them'),
            'payload_feature_levels': {},
            'platform_created': created,
            'levels_after': levels,
            'authored_ceilings': ceilings,
            'levels_at_or_above_ceiling': [
                row for row in levels
                for c in ceilings
                if c['feature_id'] == row['feature_id']
                and float(row['current_level']) >= float(c['ceiling_value'])],
        }
        save()

        # -- 4. A1c on both surfaces, and a complete lock ---------------------
        rnd, blocked = P.open_round(api, game, instructor, P.shell, state, 'A1c')
        ta = P.shell(state)['teams']
        own_a = (ta.get(str(a['id'])) or ta.get(a['id']))['team_platform_id']
        ceiling = ((ta.get(str(a['id'])) or ta.get(a['id']))['ceilings'] or [{}])[0]
        foreign = [{'team_platform': own_a, 'feature': ceiling.get('feature_id'),
                    'method': 'in_house', 'amount': '0',
                    'target_level': ceiling.get('ceiling_value') or 10,
                    'calculated_cost': '0'}]
        cross = P.both_surfaces(
            api, game, rnd, 'rd',
            (b['id'], b['student'], foreign),
            (c['id'], c['student'], foreign))
        # Fill everything else the lock validator needs, so the ownership check
        # is reached rather than masked by an earlier error.
        filled = P.shell(FILL % {'team': b['id'], 'game': game, 'round': rnd})
        refresh = api.call(
            'PATCH', f'/api/games/{game}/teams/{b["id"]}/decisions/round/{rnd}/rd/',
            b['student'], foreign)
        lock = api.call(
            'POST', f'/api/games/{game}/teams/{b["id"]}/decisions/round/{rnd}/lock/',
            b['student'])
        record['probes']['A1c_foreign_platform_both_surfaces'] = {
            'claim': ("the write path accepts an R&D investment naming another "
                      "team's platform, and whether a complete lock refuses it"),
            'platform_named': own_a,
            'submitting_teams': {'per_type': b['id'], 'whole_submission': c['id']},
            'submitted_in_round': rnd,
            'round_precondition': blocked or 'round open',
            'submission': cross,
            'fixture_filled_for_lock': filled,
            're_added_after_fill': {'status': refresh[0],
                                    'body': str(refresh[1])[:200]},
            'complete_lock_attempt': {'status': lock[0],
                                      'body': str(lock[1])[:600]},
        }
        save()

        # -- 5. D1 on both surfaces -------------------------------------------
        rnd, blocked = P.open_round(api, game, instructor, P.shell, state, 'D1')
        fresh = P.shell(state)['teams']
        pairs = []
        for team in (a, b):
            tctx = fresh.get(str(team['id'])) or fresh.get(team['id'])
            active = [pr for pr in tctx['products'] if pr['status'] == 'active']
            if active:
                pairs.append((team, active[0]))
        if len(pairs) == 2:
            (ta_, pa_), (tb_, pb_) = pairs
            rows_sql = """
from core.models.team_state import TeamProduct, TeamProductMarket
result = {
  'products': list(TeamProduct.objects.filter(id__in=[%d, %d])
                   .values('id','name','status')),
  'markets': list(TeamProductMarket.objects.filter(team_product_id__in=[%d, %d])
                  .values('id','team_product_id','market_id','is_active')),
}
""" % (pa_['id'], pb_['id'], pa_['id'], pb_['id'])
            before_rows = P.shell(rows_sql)
            retire = P.both_surfaces(
                api, game, rnd, 'product-retires',
                (ta_['id'], ta_['student'],
                 [{'team_product': pa_['id'], 'timing': 'end_of_round'}]),
                (tb_['id'], tb_['student'],
                 [{'team_product': pb_['id'], 'timing': 'end_of_round'}]))
            actions = P.advance(api, game, instructor, 'D1')
            record['probes']['D1_both_surfaces'] = {
                'claim': ("end_of_round retirement sets status retired and "
                          'leaves TeamProductMarket active, on both surfaces'),
                'submitted_in_round': rnd,
                'round_precondition': blocked or 'round open',
                'products': {'per_type': pa_, 'whole_submission': pb_},
                'submission': retire,
                'before': before_rows,
                'round_advance': {k: v['status'] for k, v in actions.items()},
                'after': P.shell(rows_sql),
            }
        else:
            record['probes']['D1_both_surfaces'] = {
                'skipped': 'fewer than two teams hold an active product'}
        save()
    except Exception as exc:
        record['aborted'] = {'after': sorted(record['probes']),
                             'error': f'{type(exc).__name__}: {exc}'[:400]}
        raise
    finally:
        P.stop(process)
        record['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        save()

    print(f"wrote stage1-rework-probes.json with {len(record['probes'])} probes")
    for name in sorted(record['probes']):
        print(' ', name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
