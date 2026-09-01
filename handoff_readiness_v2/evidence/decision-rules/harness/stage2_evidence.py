#!/usr/bin/env python3
"""Stage 2 evidence: the authoritative price, demonstrated end to end.

Four behaviours on **both** supported write surfaces, and one at the engine
boundary:

* a submission naming no cost is filled with the authored figure;
* a submission naming the authored figure is accepted unchanged;
* a submission naming a different figure is refused, and the refusal names the
  authored figure;
* a row written behind the API refuses the round before any competitive
  mutation.

Then the claim the whole stage rests on: display, validation, charging, the
cash check and the R&D budget check all read the same service. That is shown by
asking each for the same platform and comparing the figures, not by asserting
it in prose.

Runs against a disposable database at the freeze revision.
"""
import json, subprocess, sys, pathlib, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage1_probes as P   # noqa: E402

EVIDENCE = P.EVIDENCE
DATABASE = 'gsp_crv210_stage2'

SAME_SOURCE = """
from decimal import Decimal
from core.models import Game, Team
from core.models.decisions import DecisionPlatformDevelopment
from core.models.scenario import PlatformGenerationDefinition
from core.services import rd_costs
from core.views.decisions import RDContextView

game = Game.objects.get(id=%(game)d)
gen = PlatformGenerationDefinition.objects.get(id=%(gen)d)
team = Team.objects.get(id=%(team)d)

# 1. what the service says the platform costs
service = rd_costs.platform_development_cost(gen, 'in_house')

# 2. what the engine precondition compares a stored row against
row = DecisionPlatformDevelopment.objects.filter(
    submission__team=team, platform_generation=gen).order_by('-id').first()
engine_authored = rd_costs.platform_cost_for(row) if row else None

# 3. what the budget rule counts for the same row
assessment = (rd_costs.budget_assessment(row.submission, team)
              if row else None)

# 4. what the display path quotes for a feature, through the view helper that
#    now delegates to the service
from core.models.scenario import FeatureLevelCost, PlatformFeatureCeiling
ceiling = (PlatformFeatureCeiling.objects
           .filter(platform_generation=gen, ceiling_value__gt=0).first())
display = service_schedule = None
if ceiling:
    display = RDContextView._build_cost_schedule(
        ceiling.feature, gen, 0, ceiling.ceiling_value)
    service_schedule = [
        {'level': r['level'],
         'incremental_cost': float(r['incremental_cost']),
         'cumulative_from_current': float(r['cumulative_from_current'])}
        for r in rd_costs.level_cost_schedule(
            ceiling.feature, gen, 0, ceiling.ceiling_value)]

result = {
    'generation': gen.name,
    'authored_development_cost': str(gen.development_cost),
    'service_says': str(service),
    'engine_precondition_compares_against': (str(engine_authored)
                                             if engine_authored else None),
    'stored_committed_cost': str(row.committed_cost) if row else None,
    'budget_counts_platform_development': (
        assessment['lines']['platform_development'] if assessment else None),
    'display_schedule_matches_service': display == service_schedule,
    'display_first_row': display[0] if display else None,
    'all_agree': (
        row is not None
        and Decimal(str(service)) == Decimal(str(engine_authored))
        and Decimal(row.committed_cost) == Decimal(str(service))
        and assessment is not None
        and Decimal(assessment['lines']['platform_development'])
            == Decimal(str(service))
        and display == service_schedule),
}
"""

TAMPER = """
from decimal import Decimal
from core.models import Game, Round, Team
from core.models.decisions import DecisionPlatformDevelopment
from core.services import rd_costs
game = Game.objects.get(id=%(game)d)
rnd = Round.objects.get(game=game, round_number=%(round)d)
row = DecisionPlatformDevelopment.objects.filter(
    submission__round=rnd, submission__team_id=%(team)d).order_by('-id').first()
before = str(row.committed_cost)
# Behind the API, as an admin edit or a restore would.
DecisionPlatformDevelopment.objects.filter(pk=row.pk).update(
    committed_cost=Decimal('0'))
violations = rd_costs.persisted_cost_violations(game, rnd)
result = {'row': row.pk, 'was': before, 'now': '0',
          'violations': violations,
          'described': rd_costs.describe_cost_violations(violations)}
"""

RESULT_ROWS = """
from core.models import Game, Round
from core.models.results_financials import RoundResultFinancials
game = Game.objects.get(id=%(game)d)
result = {
  'financial_rows_for_round': RoundResultFinancials.objects.filter(
      game=game, round_number=%(round)d).count(),
  'round_status': Round.objects.get(game=game, round_number=%(round)d).status,
}
"""


def main():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=P.REPO,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                           cwd=P.REPO, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to record Stage 2 evidence from a dirty tree')

    P.DATABASE = DATABASE
    P.R.psql('postgres', f'DROP DATABASE IF EXISTS {DATABASE} WITH (FORCE)')
    P.R.psql('postgres', f'CREATE DATABASE {DATABASE}')
    P.R.manage(DATABASE, 'migrate', '--noinput')
    P.R.manage(DATABASE, 'shell', '-c', P.R.LEGACY_TABLES)
    seeded = P.shell('import seed_probe_game as SP\nresult = SP.seed()')
    game = seeded['game_id']
    a, b, c = seeded['teams']
    instructor = seeded['instructor']
    state = P.STATE % game

    process, port, api = P.start(revision)
    out = EVIDENCE / 'stage2-authoritative-cost.json'
    record = {'handoff': 'GSP-CRV2-10 Stage 2',
              'freeze_revision': revision, 'database': DATABASE,
              'stack_pid': process.pid, 'port': port,
              'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'demonstrations': {}}

    def save():
        out.write_text(json.dumps(record, indent=2, sort_keys=True,
                                  default=str) + '\n')

    try:
        ctx = P.shell(state)
        gens = {g['generation_order']: g for g in ctx['generations']}
        gen2 = gens[2]
        P.rounds_until = None
        # Reach the generation's unlock round.
        for _ in range(gen2['unlock_round'] + 2):
            if P.shell(state)['current_round'] >= gen2['unlock_round']:
                break
            P.advance(api, game, instructor, 'reach unlock')
        rnd, blocked = P.open_round(api, game, instructor, P.shell, state, 's2')

        def platform_row(name, cost=None):
            row = {'platform_generation': gen2['id'], 'method': 'in_house',
                   'platform_name': name, 'feature_levels': {}}
            if cost is not None:
                row['committed_cost'] = cost
            return row

        authored = gen2['development_cost']

        # 1. omitted cost is filled, both surfaces
        omitted = P.both_surfaces(
            api, game, rnd, 'platforms',
            (a['id'], a['student'], [platform_row('Omitted per-type')]),
            (b['id'], b['student'], [platform_row('Omitted whole')]))
        stored = P.shell("""
from core.models.decisions import DecisionPlatformDevelopment
result = list(DecisionPlatformDevelopment.objects
              .filter(submission__round__round_number=%d)
              .values('submission__team__name', 'platform_name',
                      'committed_cost'))
""" % rnd)
        record['demonstrations']['omitted_cost_is_filled'] = {
            'authored': authored, 'submission': omitted, 'stored': stored}
        save()

        # 2. the authored figure is accepted unchanged, both surfaces
        matching = P.both_surfaces(
            api, game, rnd, 'platforms',
            (a['id'], a['student'], [platform_row('Matching per-type', authored)]),
            (b['id'], b['student'], [platform_row('Matching whole', authored)]))
        record['demonstrations']['matching_cost_is_accepted'] = {
            'authored': authored, 'submission': matching,
            'stored': P.shell("""
from core.models.decisions import DecisionPlatformDevelopment
result = list(DecisionPlatformDevelopment.objects
              .filter(submission__round__round_number=%d)
              .values('submission__team__name', 'platform_name',
                      'committed_cost'))
""" % rnd)}
        save()

        # 3. a different figure is refused, both surfaces, naming the price
        mismatched = P.both_surfaces(
            api, game, rnd, 'platforms',
            (a['id'], a['student'], [platform_row('Free per-type', '0')]),
            (b['id'], b['student'], [platform_row('Free whole', '0')]))
        record['demonstrations']['mismatched_cost_is_refused'] = {
            'authored': authored, 'submission': mismatched,
            'refusal_names_the_authored_figure': all(
                '15,000,000' in str(mismatched[k]['body'])
                for k in ('per_type', 'whole_submission')),
            'nothing_stored_by_the_refusal': P.shell("""
from core.models.decisions import DecisionPlatformDevelopment
result = list(DecisionPlatformDevelopment.objects
              .filter(submission__round__round_number=%d,
                      platform_name__startswith='Free')
              .values('platform_name', 'committed_cost'))
""" % rnd)}
        save()

        # 4. one source, asked five ways
        record['demonstrations']['one_service_five_callers'] = P.shell(
            SAME_SOURCE % {'game': game, 'gen': gen2['id'], 'team': a['id']})
        save()

        # 5. a row tampered with behind the API refuses the round
        tamper = P.shell(TAMPER % {'game': game, 'round': rnd,
                                   'team': a['id']})
        before_rows = P.shell(RESULT_ROWS % {'game': game, 'round': rnd})
        actions = P.advance(api, game, instructor, 'tampered')
        after_rows = P.shell(RESULT_ROWS % {'game': game, 'round': rnd})
        record['demonstrations']['persisted_tampering_refuses_the_round'] = {
            'tamper': tamper,
            'round_control': {k: {'status': v['status'],
                                  'detail': str(v['detail'])[:300]}
                              for k, v in actions.items()},
            'financials_before': before_rows,
            'financials_after': after_rows,
            'no_competitive_mutation': (
                before_rows['financial_rows_for_round']
                == after_rows['financial_rows_for_round'] == 0),
        }
        save()
    except Exception as exc:
        record['aborted'] = {'error': f'{type(exc).__name__}: {exc}'[:400]}
        raise
    finally:
        P.stop(process)
        P.R.psql('postgres', f'DROP DATABASE IF EXISTS {DATABASE} WITH (FORCE)')
        record['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        save()

    d = record['demonstrations']
    print('omitted filled     :', d['omitted_cost_is_filled']['stored'])
    print('matching accepted  :',
          [(r['platform_name'], r['committed_cost'])
           for r in d['matching_cost_is_accepted']['stored']])
    print('mismatch refused   :',
          d['mismatched_cost_is_refused']['submission']['per_type']['status'],
          d['mismatched_cost_is_refused']['submission']['whole_submission']['status'],
          '| names the price:',
          d['mismatched_cost_is_refused']['refusal_names_the_authored_figure'])
    print('one service        : all_agree =',
          d['one_service_five_callers']['all_agree'])
    print('tampering refused  :',
          d['persisted_tampering_refuses_the_round']['round_control']['process']['status'],
          '| no mutation:',
          d['persisted_tampering_refuses_the_round']['no_competitive_mutation'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
