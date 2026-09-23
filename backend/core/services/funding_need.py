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


def org_transition_charge(team, current_round):
    """The organisational-structure switch this team owes for this round.

    R36 / V2-088: the charge used to leave `team.cash_on_hand` in
    `views/cc32b_views.py` at request time, where **no calculator could see
    it** -- not `decision_outlays`, not `rd_costs.budget_assessment`, not the
    engine. The team's committed spend, projected cash and Finance figures all
    ignored money that had already gone, the equity funding rule never counted
    it, and no path gave it back, so reopening a round left the cash spent
    while the decision it paid for could be changed again.

    Derived from the switch the team's stored structure row already records --
    `adopted_round` is this round and `transitioning_from` names the structure
    it left -- rather than from a new field. Three things follow, deliberately:

    * the charge and the decision that caused it cannot disagree, because
      there is only one row and it is the decision;
    * a round with no switch costs nothing, and a switch made in an earlier
      round is not charged again;
    * **no hashed field is added**, so the manifest envelope is unchanged and
      `MANIFEST_SCHEMA_VERSION` stays where it is. R34's principle: the
      explanation belongs in the audit trail, which `cc32b_views` already
      writes, not in a new column inside the certified envelope.

    Re-resolving the round recomputes the same figure from the same row, so
    the charge is idempotent rather than cumulative.
    """
    from core.models.cc32b_models import TeamOrganizationalStructure

    row = (TeamOrganizationalStructure.objects
           .filter(game_id=team.game_id, team=team,
                   adopted_round=current_round,
                   transitioning_from__isnull=False)
           .select_related('current_structure')
           .order_by('id')
           .first())
    if row is None or row.current_structure is None:
        return D('0')
    return D(str(row.current_structure.transition_cost or 0))


def tax_structure_setup_charge(team, current_round):
    """The tax-structure setup cost this team owes for this round.

    W-CE3-01 / decision 15, and it is R36 / V2-088 again in a second place:
    `engine/costs.process_tax_structure_costs` did
    `team.cash_on_hand -= structure.setup_cost` during Phase 1, **before**
    `engine/financials` reads `cash_opening = team.cash_on_hand`. The
    statement's own identity therefore closed perfectly on every team in every
    round while $2,000,000 was simply not there any more: Aurora Devices'
    round-2 statement closed at $13,523,631.84 and its round-3 statement opened
    at $11,523,631.84, and no line, tab or figure on any screen accounted for
    the difference. No calculator could see it either -- not `decision_outlays`,
    not `rd_costs.budget_assessment`, not the engine's own opex.

    Derived from the row the team's own decision already writes --
    `adopted_round` is this round and `current_structure` is what it switched
    to (`views/cc32c_views.py`) -- rather than from a new field, so:

    * the charge and the decision that caused it cannot disagree, because
      there is only one row and it is the decision;
    * a round with no switch costs nothing, and a switch made in an earlier
      round is not charged again;
    * re-resolving the round recomputes the same figure rather than a
      cumulative one, which `setup_cost_paid` alone could not promise;
    * **no hashed field is added**, so the manifest envelope is unchanged and
      `MANIFEST_SCHEMA_VERSION` stays where it is.

    The recurring `annual_maintenance_cost` is deliberately NOT here. It does
    not have this defect: the engine books it inside `operating_income`, so it
    reaches net income, operating cash flow and the closing cash a student
    reads. Moving it into an opex line would also move it inside
    `calculate_tax`'s deduction total, which changes a team's tax and so a
    published result -- calibration, not a bug (R48). What it lacks is a line
    of its own on the served statement, which is W-CE3-04.
    """
    from core.models.cc32c_models import TeamTaxStructure

    row = (TeamTaxStructure.objects
           .filter(game_id=team.game_id, team=team,
                   adopted_round=current_round,
                   current_structure__isnull=False)
           .select_related('current_structure')
           .order_by('id')
           .first())
    if row is None:
        return D('0')
    return D(str(row.current_structure.setup_cost or 0))


def compliance_investment_total(submission):
    """Everything this submission has committed to compliance this round.

    R47: V2-137's repair made `ComplianceInvestment` saveable for the first
    time, and the silent-saves record found the lever was free -- the amount
    raised `TeamMarketCompliance.compliance_level` but appeared in neither
    `decision_outlays` nor `costs.calculate_operating_expenses`. The owner
    ruled that it costs money, charged from cash at resolution.

    This is the one function both calculators read, in the position
    `research_catalogue.purchase_total` (R23) and `org_transition_charge`
    (R36) already occupy: `decision_outlays` totals it, the engine books it,
    `rd_costs.committed_outlay` counts it toward committed spend, and the
    parity assertion in `calculate_operating_expenses` stops the round if the
    two sides ever disagree.

    The figure is the amount the team typed, summed over its market rows. No
    price is invented and no scenario data is read: the row *is* the decision,
    so the charge and the decision that caused it cannot disagree, a round
    with no rows costs nothing, and re-resolving a round recomputes the same
    amount rather than a cumulative one. `ComplianceInvestment` is already a
    hashed input section (`manifest_sections.py`), so nothing new enters the
    envelope.
    """
    from core.models.cc31_models import ComplianceInvestment

    if submission is None:
        return D('0')
    total = D('0')
    for row in (ComplianceInvestment.objects
                .filter(submission=submission).order_by('id')):
        total += D(str(row.investment_amount or 0))
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
             'strategy': D('0'), 'plant_capex': D('0'), 'talent': D('0'),
             'research': D('0'), 'org_structure': D('0'),
             'compliance': D('0'), 'tax_setup': D('0')}
    # R36: computed *before* the submission guard below, because a structure
    # switch writes no decision row of its own -- a team can switch in a round
    # it never otherwise submitted in, and the charge is owed either way.
    # `engine/costs.calculate_operating_expenses` books this same figure from
    # this same function, outside its own submission guard, for exactly that
    # reason; counting it on one side only is the divergence the one-calculator
    # rule exists to prevent (V2-037/V2-038).
    lines['org_structure'] = org_transition_charge(team, current_round)
    # W-CE3-01 / decision 15: the same shape, for the same reason. A tax
    # structure is switched from Finance > Tax Structure and writes no decision
    # row of its own, so the charge is owed in a round the team may never
    # otherwise have submitted in, and it is computed here before the guard.
    lines['tax_setup'] = tax_structure_setup_charge(team, current_round)
    if submission is None:
        return lines

    for investment in submission.rd_investments.order_by('id'):
        lines['rd'] += investment.amount
    # Platform development is charged from the platform's funding round, not
    # from the presence of a decision row in this round's submission. The
    # engine moved to that basis so payment, accounting and the development
    # clock are one exactly-once event; this rule has to read the same basis or
    # the V2-024 invariant -- that the funding rule and the engine charge the
    # same outlays -- fails, which is how this divergence was caught.
    from core.models.team_state import TeamPlatform
    from core.services.rd_costs import (UnauthoredCost,
                                        platform_development_cost)
    for platform in (TeamPlatform.objects
                     .filter(team=team, funded_round=current_round)
                     .exclude(status='unfunded_draft')
                     .select_related('platform_generation')
                     .order_by('id')):
        try:
            price = platform_development_cost(platform.platform_generation,
                                              platform.development_method)
        except UnauthoredCost:
            continue
        if capitalize_platform:
            lines['platform_capex'] += price
        else:
            lines['rd'] += price

    rep_cost = _sales_rep_cost(scenario)
    for marketing in submission.marketing_decisions.order_by('id'):
        lines['marketing'] += (marketing.promotion_budget
                               + rep_cost * marketing.sales_team_count)

    for entry in submission.market_entries.order_by('id'):
        if entry.action == 'enter':
            lines['strategy'] += entry.initial_investment
        elif entry.action == 'exit':
            lines['strategy'] += (
                entry.initial_investment * EXIT_COST_FRACTION).quantize(
                    D('0.01'), rounding=ROUND_HALF_UP)

    for partnership in TeamPartnership.objects.filter(
            team=team, status='active').order_by('id'):
        lines['strategy'] += partnership.annual_investment

    try:
        esg = submission.esg
        if esg:
            lines['strategy'] += (esg.environmental_investment
                                  + esg.social_investment)
    except Exception:
        pass

    for plant in submission.plant_decisions.order_by('id'):
        if plant.action == 'build' and plant.market.plant_build_cost:
            lines['plant_capex'] += plant.market.plant_build_cost

    # Market research is bought during the round and charged at resolution, so
    # the money is committed the moment the report is delivered. It is an
    # outlay the team's own decisions determine, which is what this function
    # totals -- and `costs.calculate_operating_expenses` books the same rows as
    # `research_expense`. Counting it in one place only is the divergence the
    # one-calculator rule exists to prevent.
    from core.services.research_catalogue import purchase_total
    lines['research'] = purchase_total(submission)

    # R47: compliance investment, from the rows the team saved for this
    # round, through the one function the engine also books from. It is an
    # outlay the team's own decision determines -- the amount it typed -- so
    # it belongs here with research and the structure switch, and it is
    # covered by the engine's parity assertion for the same reason they are.
    lines['compliance'] = compliance_investment_total(submission)

    lines['talent'] = talent_cost(team, submission, current_round)
    return lines


def financing_decided(submission, financing_override=None):
    """The financing row this round, as submitted, read in one place.

    Both the equity funding rule (`funding_requirement`) and the affordability
    rule (`rd_costs.budget_assessment`) have to know what a team has decided to
    raise and to pay out. Before W-CE3-02 only the first of them did: the
    affordability check compared committed spend with cash on hand alone, so
    once a team's cash was negative no spend could ever be small enough, and
    raising $30,000,000 of new debt did not move the figure by a cent. One
    reader of the row, so the two cannot answer differently again.

    `financing_override` lets the API judge a financing row it has not written
    yet using this same arithmetic. Without it the API would need its own copy
    of the rule, and a second copy is what the disposition forbids.
    """
    from core.models.decisions import DecisionFinancing

    if financing_override is not None:
        get = financing_override.get
        return {
            'new_debt': D(str(get('new_debt', 0) or 0)),
            'debt_repayment': D(str(get('debt_repayment', 0) or 0)),
            'new_equity': D(str(get('new_equity', 0) or 0)),
            'dividend_per_share': D(str(get('dividend_per_share', 0) or 0)),
        }
    financing = (DecisionFinancing.objects.filter(submission=submission).first()
                 if submission is not None else None)
    if financing is None:
        return {'new_debt': D('0'), 'debt_repayment': D('0'),
                'new_equity': D('0'), 'dividend_per_share': D('0')}
    return {
        'new_debt': D(str(financing.new_debt or 0)),
        'debt_repayment': D(str(financing.debt_repayment or 0)),
        'new_equity': D(str(financing.new_equity or 0)),
        'dividend_per_share': D(str(financing.dividend_per_share or 0)),
    }


def financing_effect(team, submission, financing_override=None,
                     round_number=None):
    """What this round's financing decision will actually do to the cash.

    Decision 13 asks the affordability rule to count "the financing the team
    has already decided this round". *Decided* is not the same as *received*,
    and the difference is the whole reason this function exists rather than a
    sum of four submitted fields:

    * a team already in financial distress **cannot** raise new debt -- the
      engine refuses it at resolution (`engine/financials`), so counting it
      would let a team lock against money it will never see, which is the same
      class of defect as not counting financing at all;
    * an equity raise is **subscribed**, not granted: the engine multiplies it
      by the investor-sentiment subscription rate, which is derived from the
      *previous* round's holdings and is therefore knowable while the round is
      open;
    * a repayment larger than the debt outstanding is capped, and a dividend is
      capped at opening cash and blocked entirely when opening cash is not
      positive.

    So this is the engine's own financing arithmetic, extracted whole.
    `engine/financials.generate_financial_statements` calls it and applies the
    side effects (the log lines, the refusal notice, the share issue) around
    it, so there is one calculator and the lock cannot promise what the round
    then declines. The caller may pass `round_number` when it already knows it;
    otherwise the submission's own round is used.
    """
    from core.engine.financials import subscription_rate

    raw = financing_decided(submission, financing_override)
    cash_opening = D(str(team.cash_on_hand or 0))

    new_debt = raw['new_debt']
    debt_refused_in_distress = bool(
        getattr(team, 'is_in_distress', False) and new_debt > 0)
    if debt_refused_in_distress:
        new_debt = D('0')

    outstanding = D(str(team.total_debt or 0)) + new_debt
    debt_repayment = raw['debt_repayment']
    debt_repayment_capped = debt_repayment > outstanding
    if debt_repayment_capped:
        debt_repayment = max(outstanding, D('0'))

    requested_equity = raw['new_equity']
    rate = D('1')
    new_equity = D('0')
    new_shares = 0
    if requested_equity > 0:
        if round_number is None:
            round_number = submission.round.round_number
        rate = D(str(subscription_rate(team, team.game, round_number)))
        new_equity = (requested_equity * rate).quantize(
            D('0.01'), rounding=ROUND_HALF_UP)
        opening_equity = D(str(team.total_equity or 0))
        share_price_est = (
            opening_equity / max(D(str(team.shares_outstanding)), D('1'))
            if team.shares_outstanding > 0 else D('1'))
        new_shares = int(new_equity / max(share_price_est, D('1')))

    shares_outstanding = team.shares_outstanding + new_shares
    dividends = (raw['dividend_per_share']
                 * D(str(shares_outstanding))).quantize(
        D('0.01'), rounding=ROUND_HALF_UP)
    dividends_requested = dividends
    dividends_capped = False
    dividends_blocked = False
    if dividends > cash_opening and cash_opening > 0:
        dividends_capped = True
        dividends = cash_opening
    elif dividends > 0 and cash_opening <= 0:
        dividends_blocked = True
        dividends = D('0')

    return {
        'cash_opening': cash_opening,
        'requested_new_debt': raw['new_debt'],
        'new_debt': new_debt,
        'debt_refused_in_distress': debt_refused_in_distress,
        'debt_repayment': debt_repayment,
        'requested_debt_repayment': raw['debt_repayment'],
        'debt_repayment_capped': debt_repayment_capped,
        'requested_new_equity': requested_equity,
        'subscription_rate': rate,
        'new_equity': new_equity,
        'new_shares': new_shares,
        'shares_outstanding': shares_outstanding,
        'dividend_per_share': raw['dividend_per_share'],
        'dividends_requested': dividends_requested,
        'dividends': dividends,
        'dividends_capped': dividends_capped,
        'dividends_blocked': dividends_blocked,
        # What the engine will actually move through `financing_cf`.
        'net_financing': new_debt - debt_repayment + new_equity - dividends,
        # What the team has DECIDED, which is what the affordability rule
        # counts. The difference is the equity subscription: an equity raise
        # is not refused, it is subscribed at a rate investor sentiment sets,
        # and netting that haircut here would put a team in distress back in a
        # dead end -- V2-024 caps the raise at the shortfall itself, so a raise
        # that arrives at 80 % can never close the gap it is capped by, and
        # grossing the cap up instead would widen V2-024. A raise refused
        # outright in distress yields nothing and is excluded above; a raise
        # subscribed down yields most of itself and is counted.
        'net_financing_decided': (new_debt - debt_repayment
                                  + requested_equity - dividends),
    }


def available_funds(team, submission, financing_override=None,
                    round_number=None):
    """Cash on hand plus the financing this team has decided this round.

    The figure the affordability rule compares committed spend with. A team
    whose cash is negative can therefore still reach a state the lock accepts,
    by deciding the financing that covers it -- which is what decision 13
    requires and what the sentence beside the blocker has always told the team
    to do.
    """
    effect = financing_effect(team, submission, financing_override,
                              round_number)
    return (effect['cash_opening'] + effect['net_financing_decided']), effect


def funding_requirement(scenario, team, submission, current_round,
                        capitalize_platform=False, financing_override=None):
    """`eligible_uses`, `available_funding` and the resulting maximum.

    Returned whole rather than as a bare number so a refusal can say which
    side of the comparison put it there, and so the manifest can carry the
    inputs the decision was made on.

    Deliberately unchanged by W-CE3-02: `available_funding` here is opening
    cash plus new debt *as submitted*, and equity is the quantity being sized,
    so it cannot appear on the funds side without making the rule circular.
    Widening it would raise every team's maximum raise, which is the opposite
    of what V2-024 exists to do.
    """
    outlays = decision_outlays(scenario, team, submission, current_round,
                               capitalize_platform)
    decided = financing_decided(submission, financing_override)
    new_debt = decided['new_debt']
    debt_repayment = decided['debt_repayment']
    requested = decided['new_equity']

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


def describe(assessment, team_name, language='en'):
    """This refusal, worded once, in the participant's language.

    The sentence moved into the bilingual catalogue in GSP-CRV2-12 so a
    Chinese team is not refused in English on the Decision Summary. `language`
    defaults to English and the English rendering is byte-identical to the
    sentence this function built before, so `advance_round`'s recorded refusal
    — which has no request to read a language from — is unchanged.
    """
    from core.utils.participant_messages import participant_message

    return participant_message(
        'equity_exceeds_funding_need_detail', language=language,
        team=team_name,
        requested=f'${D(assessment["requested_new_equity"]):,.2f}',
        maximum=f'${D(assessment["maximum_new_equity"]):,.2f}',
        eligible=f'${D(assessment["eligible_uses"]):,.2f}',
        available=f'${D(assessment["available_funding"]):,.2f}',
        opening=f'${D(assessment["opening_cash"]):,.2f}',
        debt=f'${D(assessment["new_debt"]):,.2f}',
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
