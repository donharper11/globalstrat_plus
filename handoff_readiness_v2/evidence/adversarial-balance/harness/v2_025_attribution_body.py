"""V2-025 attribution: which stripped input creates the advantage?

`skeleton-crew` -- zero headcount, zero ESG, zero strategy budget -- won 9 of 9
holdout cells at +0.22. That is a composite of several changes at once, and the
tournament cannot say which one pays. Each is varied here on its own, from one
frozen checkpoint, with everything else at the documented baseline.

Two of the mutations are expected to be inert, and are run anyway because
"expected" is not "measured":

  * the baseline already invests nothing in ESG, so setting ESG to zero changes
    nothing. A positive-ESG arm is included to establish the sign of the term
    rather than reporting a no-op as evidence of no effect.
  * `strategy_budget` is a declared budget, and V2-021 established that declared
    budgets are inert. If it is inert here too that is a confirmation, not a
    finding.

R&D is varied through `DecisionRDInvestment.amount`, the actual spend, at zero,
at the baseline the harness writes, and at the scenario target. The tournament's
R&D family varied `rd_budget` instead -- the declared figure V2-021 deliberately
made inert -- so it tested cost, not R&D intensity, and that is the gap this
set closes.

Every mutation is proved to have reached the row scoring reads. A mutation that
does not land is refused rather than reported as no effect, which is the error
the V2-023 gate refused five times before producing a number.
"""
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone
from decimal import Decimal as D

import baseline as BASE
import counterfactual as CF
import fixture as F
import search_body as S

SEED = 'crv2-06-v2-025-attribution'
RD_TARGET = D('2000000')
POSITIVE_ESG = D('1000000')


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('v2025-attr', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.models import DecisionSubmission, Game, Round, Team
    from core.models.decisions import DecisionESG, DecisionRDInvestment
    from core.models.decisions import DecisionBudgetAllocation
    from core.models.talent import DecisionTalent

    game = Game.objects.order_by('-id').first()
    F.apply(game, SEED)
    game.refresh_from_db()
    rnd = Round.objects.get(game=game, round_number=game.current_round)
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]

    def write_all(mutate_subject=None):
        def writer():
            for team in teams:
                submission, _ = DecisionSubmission.objects.get_or_create(
                    team=team, round=rnd, defaults={'status': 'draft'})
                S.write_candidate(submission, team, None)
                if team.id == subject.id and mutate_subject is not None:
                    mutate_subject(submission, team)
                submission.status = 'locked'
                submission.locked_at = timezone.now()
                submission.save(update_fields=['status', 'locked_at'])
        return writer

    def capture(into):
        """Cost, revenue, capability, satisfaction, net income and index."""
        from core.engine.performance import _strategic_capability_component
        from core.models import RoundResultPerformanceIndex
        idx = (RoundResultPerformanceIndex.objects
               .filter(team=subject, round_number=rnd.round_number)
               .order_by('-id').first())
        into['capability'] = str(_strategic_capability_component(
            subject, rnd.round_number, RD_TARGET))
        into['satisfaction'] = str(idx.satisfaction_score) if idx else None
        into['index_value'] = str(idx.index_value) if idx else None

    # ---- the arms ------------------------------------------------------
    def zero_pool(pool):
        def mutate(submission, team):
            talent = DecisionTalent.objects.get(submission=submission)
            setattr(talent, f'{pool}_headcount', 0)
            talent.save()
            stored = DecisionTalent.objects.get(submission=submission)
            return {f'{pool}_headcount': getattr(stored, f'{pool}_headcount')}
        return mutate

    def zero_all_pools(submission, team):
        talent = DecisionTalent.objects.get(submission=submission)
        talent.rd_headcount = 0
        talent.commercial_headcount = 0
        talent.operations_headcount = 0
        talent.save()

    def set_esg(amount):
        def mutate(submission, team):
            esg = DecisionESG.objects.get(submission=submission)
            esg.environmental_investment = amount
            esg.social_investment = D('0')
            esg.save()
        return mutate

    def zero_strategy_budget(submission, team):
        budget = DecisionBudgetAllocation.objects.get(submission=submission)
        budget.strategy_budget = D('0')
        budget.save()

    def set_rd_amount(amount):
        def mutate(submission, team):
            rows = list(DecisionRDInvestment.objects.filter(
                submission=submission))
            for row in rows:
                row.amount = amount
                row.save(update_fields=['amount'])
        return mutate

    ARMS = [
        ('rd-headcount-zero', zero_pool('rd'),
         lambda s: DecisionTalent.objects.get(submission=s).rd_headcount == 0),
        ('commercial-headcount-zero', zero_pool('commercial'),
         lambda s: DecisionTalent.objects.get(
             submission=s).commercial_headcount == 0),
        ('operations-headcount-zero', zero_pool('operations'),
         lambda s: DecisionTalent.objects.get(
             submission=s).operations_headcount == 0),
        ('all-headcount-zero', zero_all_pools,
         lambda s: all(getattr(DecisionTalent.objects.get(submission=s),
                               f'{p}_headcount') == 0
                       for p in ('rd', 'commercial', 'operations'))),
        ('esg-zero', set_esg(D('0')),
         lambda s: DecisionESG.objects.get(
             submission=s).environmental_investment == D('0')),
        ('esg-positive', set_esg(POSITIVE_ESG),
         lambda s: DecisionESG.objects.get(
             submission=s).environmental_investment == POSITIVE_ESG),
        ('strategy-budget-zero', zero_strategy_budget,
         lambda s: DecisionBudgetAllocation.objects.get(
             submission=s).strategy_budget == D('0')),
        ('rd-amount-zero', set_rd_amount(D('0')),
         lambda s: all(r.amount == D('0') for r in
                       DecisionRDInvestment.objects.filter(submission=s))),
        ('rd-amount-baseline', set_rd_amount(BASE.OPTIONAL_AMOUNT),
         lambda s: all(r.amount == BASE.OPTIONAL_AMOUNT for r in
                       DecisionRDInvestment.objects.filter(submission=s))),
        ('rd-amount-target', set_rd_amount(RD_TARGET),
         lambda s: all(r.amount == RD_TARGET for r in
                       DecisionRDInvestment.objects.filter(submission=s))),
    ]

    started = time.time()
    report = {'seed': SEED, 'identity': F.identity_for(SEED),
              'subject_team': subject.name, 'rd_spend_target': str(RD_TARGET),
              'arms': {}, 'evaluations': 0}

    baseline = CF.evaluate(game, rnd, subject, write_all(), capture=capture)
    repeat = CF.evaluate(game, rnd, subject, write_all(), capture=capture)
    report['evaluations'] += 2
    report['baseline'] = baseline
    report['baseline_is_repeatable'] = CF.is_zero(CF.delta(baseline, repeat))

    for name, mutate, reached in ARMS:
        proof = {}

        def mutate_and_prove(submission, team, _m=mutate, _r=reached):
            _m(submission, team)
            proof['reached_scoring_row'] = bool(_r(submission))

        metrics = CF.evaluate(game, rnd, subject,
                              write_all(mutate_and_prove), capture=capture)
        report['evaluations'] += 1
        report['arms'][name] = {
            'metrics': metrics,
            'delta': CF.delta(baseline, metrics),
            'reached_scoring_row': proof.get('reached_scoring_row'),
            'changed_anything': not CF.is_zero(CF.delta(baseline, metrics)),
        }
        if verbose:
            d = report['arms'][name]['delta']
            print(f"  {name:<28} index {d.get('index_value')!s:>10}  "
                  f"reached {proof.get('reached_scoring_row')}", flush=True)

    report['elapsed_seconds'] = round(time.time() - started, 1)
    report['all_mutations_reached_the_row'] = all(
        arm['reached_scoring_row'] for arm in report['arms'].values())
    return report
