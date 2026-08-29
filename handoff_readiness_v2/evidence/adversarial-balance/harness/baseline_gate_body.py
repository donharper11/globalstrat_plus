"""Baseline-competency gate: is the named competent baseline actually competent?

Every scoring target this handoff changed is checked against the baseline that
every margin is measured from. Three separate defects reached submitted
evidence before this gate existed, each the same shape -- a rule changed, and
the baseline quietly stopped being competent in the terms that rule scores:

  * actual R&D spend sat at a $100,000 placeholder against a $2,000,000 target,
    so the baseline earned five per cent of available capability credit;
  * staffing sat at load_demo's 50/30/40 against authored optima of 60/40/50,
    conceding a 1.2587x capability multiplier;
  * prices ran load_demo's positioning schedule, so premium products at 1.667x
    the scenario reference scored zero price competitiveness and lost 53% of
    their demand.

None was a game exploit. Each invalidated a tournament. The gate exists so the
next rule change cannot do it a fourth time silently.
"""
import time

from decimal import Decimal as D
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE
import counterfactual as CF
import search_body as S

SEED = 'crv2-06-baseline-gate'


def run():
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('baseline-gate', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.engine.performance import (material_revenue_floor,
                                         scenario_rd_spend_target)
    from core.engine.utils import (scenario_optimal_headcounts,
                                   scenario_reference_prices)
    from core.models import DecisionSubmission, Game, Round, Team
    from core.models.decisions import DecisionMarketing, DecisionRDInvestment
    from core.models.talent import DecisionTalent
    from core.serializers.decision_limits import persisted_violations
    from core.services import funding_need

    game = Game.objects.order_by('-id').first()
    game.refresh_from_db()
    rnd = Round.objects.get(game=game, round_number=game.current_round)
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]
    scenario = game.scenario

    target = scenario_rd_spend_target(scenario)
    optima = scenario_optimal_headcounts(scenario)
    references = scenario_reference_prices(scenario)

    started = time.time()
    checks = {}

    def write_baseline():
        for team in teams:
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=rnd, defaults={'status': 'draft'})
            S.write_candidate(submission, team, None)
            submission.status = 'locked'
            submission.locked_at = timezone.now()
            submission.save(update_fields=['status', 'locked_at'])

    def inspect(into):
        submission = DecisionSubmission.objects.get(team=subject, round=rnd)

        spend = sum((r.amount for r in DecisionRDInvestment.objects.filter(
            submission=submission)), D('0'))
        checks['rd_spend_equals_target'] = {
            'spend': str(spend), 'target': str(target),
            'pass': spend == target}

        talent = DecisionTalent.objects.get(submission=submission)
        pools = {p: getattr(talent, f'{p}_headcount')
                 for p in ('rd', 'commercial', 'operations')}
        checks['talent_at_authored_optima'] = {
            'staffed': pools,
            'optima': {p: int(v) for p, v in optima.items()},
            'pass': all(pools[p] == int(optima[p]) for p in pools)}

        # Each product against its own tier's reference, never one global
        # figure: a premium product priced at the mainstream reference is not
        # competent play, it is a premium product sold as mainstream.
        rows = list(DecisionMarketing.objects.filter(submission=submission)
                    .select_related('team_product'))
        priced = [{'product': r.team_product.name,
                   'positioning': r.team_product.positioning,
                   'price': str(r.retail_price),
                   'tier_reference': str(references.get(
                       r.team_product.positioning)),
                   'matches': (r.team_product.positioning in references
                               and D(str(r.retail_price))
                               == D(str(references[r.team_product.positioning])))}
                  for r in rows]
        checks['pricing_uses_each_products_tier_reference'] = {
            'rows': priced, 'references': {k: str(v) for k, v in references.items()},
            'pass': bool(priced) and all(row['matches'] for row in priced)}

        assessment = funding_need.assess_submission(submission)
        checks['financing_legal_under_v2_024'] = {
            'requested': assessment['requested_new_equity'],
            'maximum': assessment['maximum_new_equity'],
            'pass': assessment['within_limit']}

        limit_violations = persisted_violations(game, rnd)
        equity_violations = funding_need.violations(game, rnd)
        checks['all_payloads_pass_final_validation'] = {
            'decision_limit_violations': len(limit_violations),
            'funding_violations': len(equity_violations),
            'pass': not limit_violations and not equity_violations}

        from core.models import RoundResultFinancials
        revenues = [f.total_revenue for f in RoundResultFinancials.objects.filter(
            game=game, round_number=rnd.round_number)]
        floor = material_revenue_floor(revenues)
        mine = next((f.total_revenue for f in RoundResultFinancials.objects.filter(
            game=game, team=subject, round_number=rnd.round_number)), D('0'))
        checks['commercial_activity_above_material_floor'] = {
            'revenue': str(mine), 'floor': str(floor),
            'pass': mine > floor}

    metrics = CF.evaluate(game, rnd, subject, write_baseline, capture=inspect)

    report = {
        'seed': SEED,
        'subject_team': subject.name,
        'baseline_metrics': metrics,
        'checks': checks,
        'all_pass': all(c['pass'] for c in checks.values()),
        'failed': [name for name, c in checks.items() if not c['pass']],
        'elapsed_seconds': round(time.time() - started, 1),
    }
    return report
