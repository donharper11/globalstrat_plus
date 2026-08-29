"""Stage 3 adversarial search: candidates, evaluation, discovery, improvement.

A candidate is a multi-round strategy -- one policy applied every round, not an
isolated row -- evaluated against an opponent population from a single frozen
checkpoint. Every evaluation runs inside a transaction that is rolled back, so
candidates differ from each other in their decisions and in nothing else: same
game, same roster, same scenario, same starting state, same RNG streams.

Legality is asserted rather than assumed. Every candidate's persisted decisions
are put through the project's own `decision_limits` policy before the round is
resolved, so a candidate that scored well by writing something the API would
reject cannot enter the results.
"""
import random
from decimal import Decimal as D

from django.db import transaction
from django.utils import timezone

import baseline as BASE
import counterfactual as CF


ROUNDS_PER_CANDIDATE = 3

# Every gene is non-negative and inside the column precision the decision
# tables declare, so the whole search space is legal by construction. The
# multipliers scale the documented baseline rather than replacing it, which
# keeps a candidate comparable to competent play instead of to nothing.
GENES = (
    ('price_multiplier',           0.25,   2.50, float),
    ('volume_multiplier',          0.25,   3.00, float),
    ('promotion_multiplier',       0.00,   4.00, float),
    ('rd_budget',                  0.0,    10_000_000.0, float),
    ('marketing_budget',           0.0,    10_000_000.0, float),
    ('strategy_budget',            0.0,     5_000_000.0, float),
    ('research_budget',            0.0,     3_000_000.0, float),
    ('distribution_investment',    0.0,     2_000_000.0, float),
    ('sales_team_count',           0,      40,   int),
    ('rd_headcount',               0,     150,   int),
    ('commercial_headcount',       0,     150,   int),
    ('operations_headcount',       0,     150,   int),
    ('environmental_investment',   0.0,   2_000_000.0, float),
    ('social_investment',          0.0,   2_000_000.0, float),
)


def random_candidate(rng):
    genome = {}
    for name, low, high, kind in GENES:
        genome[name] = (rng.randint(low, high) if kind is int
                        else round(rng.uniform(low, high), 4))
    return genome


def mutate(genome, rng, rate=0.3, scale=0.2):
    """Perturb a few genes, clipped back into the legal range."""
    child = dict(genome)
    for name, low, high, kind in GENES:
        if rng.random() > rate:
            continue
        span = (high - low) * scale
        value = child[name] + rng.uniform(-span, span)
        value = max(low, min(high, value))
        child[name] = int(round(value)) if kind is int else round(value, 4)
    return child


def _money(value):
    return D(str(round(float(value), 2)))


def write_candidate(submission, team, genome):
    """Baseline decisions, then the candidate's policy over the top."""
    from core.models.decisions import (DecisionBudgetAllocation, DecisionESG,
                                       DecisionMarketing)
    from core.models.talent import DecisionTalent

    BASE.build(submission, team)
    BASE.build_optional(submission, team)
    if genome is None:
        return

    budget = DecisionBudgetAllocation.objects.get(submission=submission)
    budget.rd_budget = _money(genome['rd_budget'])
    budget.marketing_budget = _money(genome['marketing_budget'])
    budget.strategy_budget = _money(genome['strategy_budget'])
    budget.research_budget = _money(genome['research_budget'])
    budget.save()

    sales = int(genome['sales_team_count'])
    # The per-channel detail has to add up to the headcount it describes;
    # leaving the baseline's split behind while changing the count would put a
    # candidate outside the space the API accepts.
    online = sales // 2
    selective = sales // 3
    detail = {'direct_online': online, 'selective_retail': selective,
              'mass_retail': sales - online - selective}

    from core.engine.utils import scenario_reference_prices
    reference_prices = scenario_reference_prices(team.game.scenario)
    for row in DecisionMarketing.objects.filter(
            submission=submission).select_related('team_product'):
        positioning = row.team_product.positioning
        # Multipliers scale the baseline, and the baseline prices each product
        # at its own tier reference, so `price_multiplier` is literally the
        # ratio to that tier's reference which V2-023 scores against. The same
        # multiplier therefore means the same thing in every tier.
        base_price = reference_prices[positioning]
        base_volume = BASE.VOLUME_BY_POSITIONING.get(positioning, BASE.DEFAULT_VOLUME)
        base_promo = BASE.PROMO_BY_POSITIONING.get(positioning, BASE.DEFAULT_PROMO)
        row.retail_price = _money(base_price * genome['price_multiplier'])
        row.production_volume = int(base_volume * genome['volume_multiplier'])
        row.demand_estimate = int(row.production_volume * 1.5)
        row.promotion_budget = _money(float(base_promo) * genome['promotion_multiplier'])
        row.distribution_investment = _money(genome['distribution_investment'])
        row.sales_team_count = sales
        row.distribution_channel_detail = detail
        row.save()

    talent = DecisionTalent.objects.get(submission=submission)
    talent.rd_headcount = int(genome['rd_headcount'])
    talent.commercial_headcount = int(genome['commercial_headcount'])
    talent.operations_headcount = int(genome['operations_headcount'])
    talent.save()

    esg = DecisionESG.objects.get(submission=submission)
    esg.environmental_investment = _money(genome['environmental_investment'])
    esg.social_investment = _money(genome['social_investment'])
    esg.save()

    # Financing is optional and absent from GENES on purpose: the preserved
    # discovery batch was drawn without it, and folding it into the random
    # genome would make that evidence describe a space it never sampled.
    # Targeted candidates set these explicitly; everything else leaves the
    # zeros the baseline writes.
    # `_equity_at_max` raises exactly the largest equity the V2-024 funding
    # rule permits for this submission. A fixed figure cannot do that -- the
    # shortfall depends on the team's cash and its own outlays -- and a fixed
    # figure is also how the tournament ended up with two opponent populations
    # whose payloads the final rules reject.
    if genome.get('_equity_at_max'):
        from core.services import funding_need
        from core.models.decisions import DecisionFinancing
        financing = DecisionFinancing.objects.filter(
            submission=submission).first()
        if financing is not None:
            assessment = funding_need.assess_submission(
                submission, financing_override={
                    'new_debt': financing.new_debt,
                    'debt_repayment': financing.debt_repayment,
                    'new_equity': 0})
            financing.new_equity = D(assessment['maximum_new_equity'])
            financing.save(update_fields=['new_equity'])

    financing_keys = ('new_debt', 'new_equity', 'dividend_per_share')
    if any(key in genome for key in financing_keys):
        from core.models.decisions import DecisionFinancing
        financing = DecisionFinancing.objects.filter(
            submission=submission).first()
        if financing is not None:
            for key in financing_keys:
                if key in genome:
                    setattr(financing, key, _money(genome[key]))
            financing.save()


class IllegalCandidate(Exception):
    """A candidate wrote something the decision rules forbid.

    This must never fire: the gene bounds are non-negative and the writer only
    scales the documented baseline. If it does, the search space has drifted
    outside what the API would accept and every result computed from it is
    worthless, so it stops the run rather than filtering the candidate out.
    """


def evaluate(game, subject, genome, opponent_for, rounds=ROUNDS_PER_CANDIDATE):
    """Resolve `rounds` rounds from the checkpoint and roll back.

    `opponent_for(team)` returns the genome each non-subject team plays, or
    None for the documented baseline.
    """
    from core.engine.advance_round import _run_phase_1, advance_to_next_round
    from core.models import DecisionSubmission, Round, Team
    from core.serializers.decision_limits import (describe_violations,
                                                  persisted_violations)

    game.refresh_from_db()
    start_round = game.current_round
    first = Round.objects.get(game=game, round_number=start_round)
    before = CF.fingerprint(game, first)
    teams = list(Team.objects.filter(game=game).order_by('id'))
    captured = {}

    try:
        with transaction.atomic():
            for step in range(rounds):
                game.refresh_from_db()
                rnd = Round.objects.get(game=game,
                                        round_number=game.current_round)
                for team in teams:
                    submission, _ = DecisionSubmission.objects.get_or_create(
                        team=team, round=rnd, defaults={'status': 'draft'})
                    write_candidate(
                        submission, team,
                        genome if team.id == subject.id else opponent_for(team))
                    submission.status = 'locked'
                    submission.locked_at = timezone.now()
                    submission.save(update_fields=['status', 'locked_at'])

                violations = persisted_violations(game, rnd)
                if violations:
                    raise IllegalCandidate(describe_violations(violations))

                _run_phase_1(game.id)
                if step < rounds - 1:
                    advance_to_next_round(game.id)

            final_round = Round.objects.get(
                game=game, round_number=game.current_round).round_number
            captured['final_round'] = final_round
            captured['teams'] = {
                team.id: CF.read_metrics(game, team, final_round)
                for team in teams}
            raise CF._Rollback()
    except CF._Rollback:
        pass

    game.refresh_from_db()
    after = CF.fingerprint(game, first)
    if after != before:
        differences = {k: (before[k], after[k])
                       for k in before if before[k] != after[k]}
        raise AssertionError(
            f'the database did not return to the checkpoint: {differences}')
    return captured


def score(result, subject_id, baseline=None):
    """Fitness is advantage over competent play, not raw index.

    The development smoke showed why. The subject team playing the plain
    baseline scored 57.99 at rank 1 of 4 with a field margin of 2.57: it is
    intrinsically advantaged in this fixture, so a raw index ranks a team
    advantage that no strategy earned. The two measures also disagree -- one
    smoke candidate beat the baseline on field margin (3.46 against 2.57) while
    losing to it on index (57.27 against 57.99) -- so ranking on index would
    have hidden a candidate that did better against the field.

    `advantage` is the number the handoff asks for: how much a legal strategy
    beats competent baseline play, with the fixture's team advantage divided
    out because both terms are the same team in the same game.
    """
    teams = result['teams']
    subject = teams[subject_id]
    index = float(subject['index_value']) if subject['index_value'] else 0.0
    rivals = [float(m['index_value']) for tid, m in teams.items()
              if tid != subject_id and m['index_value'] is not None]
    best_rival = max(rivals) if rivals else 0.0
    margin = index - best_rival
    fitness = {
        'index': round(index, 4),
        'field_margin': round(margin, 4),
        'best_rival_index': round(best_rival, 4),
        'cash_closing': subject['cash_closing'],
        'net_income': subject['net_income'],
        'total_revenue': subject['total_revenue'],
        'rank': 1 + sum(1 for r in rivals if r > index),
        'field': len(teams),
    }
    if baseline is not None:
        fitness['advantage'] = round(index - baseline['index'], 4)
        fitness['field_margin_gain'] = round(
            margin - baseline['field_margin'], 4)
    return fitness


class IllegalPayload(Exception):
    """A baseline, opponent or candidate payload the final rules reject.

    Distinct from `IllegalCandidate`, which guards the non-negative decision
    limits. This one covers every rule a payload must satisfy to be a legal
    entrant -- V2-024 funding need included -- and exists because the first
    tournament ran an opponent population, `equity-raise`, that the adopted
    rules reject outright. A tournament in which one of three populations is
    illegal has measured something the game cannot contain.
    """


def check_payload_contract(game, rnd, teams, payloads):
    """Construct every payload and validate it against the final rules.

    `payloads` maps a label to the genome each team would play. Everything is
    written inside a transaction and rolled back, so this costs one write pass
    and no resolution.
    """
    from django.db import transaction
    from core.models import DecisionSubmission
    from core.serializers.decision_limits import (describe_violations,
                                                  persisted_violations)
    from core.services import funding_need

    report = {}
    for label, genome_for in payloads.items():
        result = {'legal': True, 'problems': []}
        try:
            with transaction.atomic():
                for team in teams:
                    submission, _ = DecisionSubmission.objects.get_or_create(
                        team=team, round=rnd, defaults={'status': 'draft'})
                    write_candidate(submission, team, genome_for(team))
                    submission.status = 'locked'
                    submission.save(update_fields=['status'])
                limit_violations = persisted_violations(game, rnd)
                if limit_violations:
                    result['problems'].append(
                        f'decision limits: {describe_violations(limit_violations)}')
                equity_violations = funding_need.violations(game, rnd)
                if equity_violations:
                    result['problems'].append(
                        'V2-024 funding need: ' + '; '.join(
                            v['team'] for v in equity_violations))
                raise _ContractRollback()
        except _ContractRollback:
            pass
        result['legal'] = not result['problems']
        report[label] = result
    return report


class _ContractRollback(Exception):
    """Unwinds a contract check. Never escapes `check_payload_contract`."""
