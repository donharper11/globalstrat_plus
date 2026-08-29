"""V2-024: equity may finance a funding shortfall, and nothing else.

The Stage 3 tournament demonstrated an opponent-independent dominant strategy:
the documented baseline plus an unused $20,000,000 equity raise beat competent
play in 9 of 9 holdout cells, with near-identical advantage against every
opponent population. `_financial_component` scores
`1 - clamp01(debt_to_equity / 2)`, so equity lowers leverage and lifts the
index, while the index never reads `shares_outstanding` -- dilution and the
cost of equity appear nowhere in scoring. Raising equity and paying it straight
back out as dividends won all nine cells too, which is the shape of a risk-free
loop rather than a balance preference.

The adopted rule::

    eligible_uses      = current-round operating and strategic cash outlays
                         + debt repayment
    available_funding  = opening cash + new debt
    maximum_new_equity = max(0, eligible_uses - available_funding)

Dividends are excluded from eligible uses, so equity cannot fund a payout. A
request above the maximum is **rejected, not clamped**: clamping would silently
replace a team's financing decision with a different one and the result would
look ordinary, which is the failure mode this handoff has repaired twice.

One calculator, not two. Every outlay line below is the expression the engine
itself charges, and `costs.calculate_operating_expenses` calls
`decision_outlays` rather than repeating them, so a validator and an engine
cannot drift apart. That is a requirement of the disposition, not a
convenience: a second approximate calculator would let a raise be accepted
against costs the engine never charges, or rejected against costs it does.
"""
from decimal import ROUND_HALF_UP, Decimal as D


SALARY_BASE_BY_LEVEL = {1: 15000, 2: 22500, 3: 30000, 4: 40000, 5: 55000}
RECRUITMENT_COST_PER_HIRE = D('10000')
LAYOFF_COST_PER_HEAD = D('20000')
DEFAULT_SALES_REP_COST = D('100000')
EXIT_COST_FRACTION = D('0.20')


def _sales_rep_cost(scenario):
    from core.models.scenario import ScenarioConfig
    try:
        return D(ScenarioConfig.objects.get(
            scenario=scenario, config_key='sales_rep_cost_per_round',
        ).config_value)
    except ScenarioConfig.DoesNotExist:
        return DEFAULT_SALES_REP_COST


def talent_cost(team, submission, current_round):
    """Payroll, training, recruitment and severance for one round."""
    from core.models.talent import DecisionTalent, TeamTalentState
    try:
        talent = submission.talent
    except DecisionTalent.DoesNotExist:
        return D('0')
    if talent is None:
        return D('0')

    total = D('0')
    for prefix in ('rd', 'commercial', 'operations'):
        headcount = getattr(talent, f'{prefix}_headcount')
        salary_level = getattr(talent, f'{prefix}_salary_level')
        training = D(str(getattr(talent, f'{prefix}_training_budget')))
        pool_salary = D(str(headcount * SALARY_BASE_BY_LEVEL[salary_level]))
        previous = TeamTalentState.objects.filter(
            team=team, talent_pool=prefix, round_number=current_round - 1,
        ).first()
        previous_headcount = previous.headcount if previous else 0
        new_hires = max(headcount - previous_headcount, 0)
        layoffs = max(previous_headcount - headcount, 0)
        total += (pool_salary + training
                  + D(str(new_hires)) * RECRUITMENT_COST_PER_HIRE
                  + D(str(layoffs)) * LAYOFF_COST_PER_HEAD)
    return total


def decision_outlays(scenario, team, submission, current_round,
                     capitalize_platform=False):
    """Every cash outlay this round that the team's own decisions determine.

    Returned as separate lines so the engine can book them where it books them
    and the funding rule can total them. Deliberately excludes anything that
    depends on how the round resolves -- revenue-scaled admin overhead, COGS,
    tariffs, tax, interest, disruption and compliance costs -- because a rule
    that runs before the first competitive write cannot know them. Excluding
    real outlays makes the rule stricter, never more permissive: it lowers the
    funding requirement and so lowers the equity a team may raise.
    """
    from core.models.team_state import TeamPartnership

    lines = {'rd': D('0'), 'platform_capex': D('0'), 'marketing': D('0'),
             'strategy': D('0'), 'plant_capex': D('0'), 'talent': D('0')}
    if submission is None:
        return lines

    for investment in submission.rd_investments.all():
        lines['rd'] += investment.amount
    for development in submission.platform_developments.all():
        if capitalize_platform:
            lines['platform_capex'] += development.committed_cost
        else:
            lines['rd'] += development.committed_cost

    rep_cost = _sales_rep_cost(scenario)
    for marketing in submission.marketing_decisions.all():
        lines['marketing'] += (marketing.promotion_budget
                               + rep_cost * marketing.sales_team_count)

    for entry in submission.market_entries.all():
        if entry.action == 'enter':
            lines['strategy'] += entry.initial_investment
        elif entry.action == 'exit':
            lines['strategy'] += (
                entry.initial_investment * EXIT_COST_FRACTION).quantize(
                    D('0.01'), rounding=ROUND_HALF_UP)

    for partnership in TeamPartnership.objects.filter(
            team=team, status='active'):
        lines['strategy'] += partnership.annual_investment

    try:
        esg = submission.esg
        if esg:
            lines['strategy'] += (esg.environmental_investment
                                  + esg.social_investment)
    except Exception:
        pass

    for plant in submission.plant_decisions.all():
        if plant.action == 'build' and plant.market.plant_build_cost:
            lines['plant_capex'] += plant.market.plant_build_cost

    lines['talent'] = talent_cost(team, submission, current_round)
    return lines


def funding_requirement(scenario, team, submission, current_round,
                        capitalize_platform=False, financing_override=None):
    """`eligible_uses`, `available_funding` and the resulting maximum.

    Returned whole rather than as a bare number so a refusal can say which
    side of the comparison put it there, and so the manifest can carry the
    inputs the decision was made on.
    """
    from core.models.decisions import DecisionFinancing

    outlays = decision_outlays(scenario, team, submission, current_round,
                               capitalize_platform)
    # `financing_override` lets the API judge a financing row it has not
    # written yet, against the outlays already persisted, using this same
    # arithmetic. Without it the API would need its own copy of the rule, and a
    # second copy is what the disposition forbids.
    if financing_override is not None:
        new_debt = D(str(financing_override.get('new_debt', 0) or 0))
        debt_repayment = D(str(financing_override.get('debt_repayment', 0) or 0))
        requested = D(str(financing_override.get('new_equity', 0) or 0))
    else:
        financing = (DecisionFinancing.objects.filter(submission=submission)
                     .first() if submission is not None else None)
        new_debt = D(str(financing.new_debt)) if financing else D('0')
        debt_repayment = D(str(financing.debt_repayment)) if financing else D('0')
        requested = D(str(financing.new_equity)) if financing else D('0')

    eligible_uses = sum(outlays.values(), D('0')) + debt_repayment
    available_funding = D(str(team.cash_on_hand)) + new_debt
    maximum = max(D('0'), eligible_uses - available_funding)
    return {
        'outlays': {k: str(v) for k, v in outlays.items()},
        'debt_repayment': str(debt_repayment),
        'eligible_uses': str(eligible_uses),
        'opening_cash': str(team.cash_on_hand),
        'new_debt': str(new_debt),
        'available_funding': str(available_funding),
        'maximum_new_equity': str(maximum),
        'requested_new_equity': str(requested),
        'within_limit': requested <= maximum,
    }


class EquityExceedsFundingNeed(ValueError):
    """A requested raise is larger than the shortfall it claims to finance."""


def describe(assessment, team_name):
    return (
        f'{team_name}: equity raise of ${D(assessment["requested_new_equity"]):,.2f} '
        f'exceeds the funding shortfall of '
        f'${D(assessment["maximum_new_equity"]):,.2f} '
        f'(eligible uses ${D(assessment["eligible_uses"]):,.2f} '
        f'less available funding ${D(assessment["available_funding"]):,.2f}: '
        f'opening cash ${D(assessment["opening_cash"]):,.2f} '
        f'plus new debt ${D(assessment["new_debt"]):,.2f}). '
        f'Equity may finance a genuine current-round shortfall; it may not '
        f'create surplus cash or fund dividends.'
    )


def violations(game, round_obj):
    """Every team in this round whose raise exceeds its funding need."""
    from core.engine.utils import get_config
    from core.models import DecisionSubmission, Team

    scenario = game.scenario
    capitalize_platform = get_config(
        scenario, 'capitalize_platform_development', default=False,
        cast_type=bool)
    found = []
    for team in Team.objects.filter(
            game=game, participation_status='active').order_by('id'):
        submission = DecisionSubmission.objects.filter(
            team=team, round=round_obj).first()
        if submission is None:
            continue
        assessment = funding_requirement(
            scenario, team, submission, round_obj.round_number,
            capitalize_platform)
        if not assessment['within_limit']:
            found.append({'team': team.name, 'team_id': team.id,
                          'assessment': assessment})
    return found


def assess_submission(submission, financing_override=None):
    """The funding assessment for one submission, for the API boundary.

    The same call the engine precondition makes, so the two paths cannot
    enforce different formulas. The API check is necessary but not sufficient
    on its own: a team may write a large raise while its outlays are large and
    then cut the outlays, so the round-level precondition has to re-check at
    resolution regardless of what the API accepted earlier.
    """
    from core.engine.utils import get_config
    team = submission.team
    scenario = team.game.scenario
    return funding_requirement(
        scenario, team, submission, submission.round.round_number,
        get_config(scenario, 'capitalize_platform_development', default=False,
                   cast_type=bool),
        financing_override)
