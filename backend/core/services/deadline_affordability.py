"""Decision 14: the deadline may not spend what the lock would refuse.

W-CE2-03 repaired half of this. `_lock_all_submissions` froze a team's draft at
the deadline exactly as it stood, so a submission the lock had refused --
*Committed spend of $38,000,000.00 exceeds available cash of $25,446,310.88* --
was resolved anyway, and the engine charged it in full. The acquisition half was
closed by teaching `acquisitions.process_acquisitions` to read the lock's own
affordability answer. The rest was disclosed as a residue in that repair's §7.1
and became W-CE3-02: teams closed at -$6,468,269.34 and -$7,431,324.09 on plant
builds and marketing, and from there could never lock again.

Decision 13 has now made the affordability rule satisfiable -- a team can always
reach it by deciding financing -- so decision 14 applies the same rule here.
One rule, two paths, the same arithmetic: this module evaluates
`rd_costs.budget_assessment`, the function the lock refuses on, and nothing
else.

**What a deadline-closed unaffordable draft now does.** The deadline withdraws
the team's own discretionary commitments, largest first within each step, in
this fixed order, re-asking the same question after every withdrawal and
stopping the moment the draft fits:

    1. plant builds
    2. platform development requests
    3. compliance investments
    4. the ESG investment
    5. market entries
    6. promotion and distribution budgets
    7. the declared budget lines, reduced to the decisions actually made
       under them

Every one of these is a row the team could itself have withdrawn from a screen
before the lock (W-CE2-02 gave it the controls), which is why withdrawing them
introduces no rule a player could not have applied themselves. Queued
acquisitions are deliberately NOT withdrawn: the engine already declines an
unaffordable one, uncharged and with a notification, and the decision row is
kept as the team's record -- so this module asks its question with the
acquisition excluded, because withdrawing a plant to pay for a bid that will
not happen would be the wrong trade.

If the draft still does not fit once everything discretionary is gone -- a team
whose available funds are simply negative and which raised nothing -- it is
closed with nothing discretionary in it. That is the honest terminal state: the
lock would have refused, the deadline cannot refuse without stalling the round
for everyone (rejected in W-CE2-03 §7.1(c)), so it spends nothing.

A team that locked its own submission is never touched: it passed this check at
the lock, so the gate can only fire on a draft the lock would have refused.

Every withdrawal writes a `DecisionAuditEvent` with `user=None` -- actor
`system` on the instructor drill-down -- and the team is told, in its own
language, what was withdrawn and that nothing was charged for it.

**Hashed values.** This changes decision rows before the round's input snapshot
is taken, so a round carrying a team whose draft the lock would have refused
hashes differently than it did. No section gains or loses a field and
`MANIFEST_SCHEMA_VERSION` does not move.
"""
from decimal import Decimal as D

# The order the deadline withdraws in. Stated here, once, because it is a rule
# a player can feel and R48 requires every such rule to be traceable in plain
# language in one place.
WITHDRAWAL_ORDER = (
    'plant_builds',
    'platform_developments',
    'compliance_investments',
    'esg',
    'market_entries',
    'promotion_budgets',
    'declared_budgets',
)


def _fits(submission, team):
    """Does this draft fit the lock's own affordability rule?

    Asked with queued acquisitions excluded: `acquisitions.process_acquisitions`
    withholds an unaffordable bid and charges nothing for it, so the deadline
    does not withdraw a plant to pay for a purchase that will not happen. Every
    other figure is `budget_assessment`'s, untouched.
    """
    from core.services.rd_costs import budget_assessment

    assessment = budget_assessment(submission, team)
    if assessment['within_cash']:
        return True, assessment
    committed = (D(assessment['committed_total'])
                 - D(assessment['lines'].get('acquisitions', '0')))
    return committed <= D(assessment['available_funds']), assessment


def _withdraw_plant_builds(submission):
    rows = list(submission.plant_decisions.filter(action='build')
                .select_related('market').order_by('id'))
    if not rows:
        return None
    names = [row.market.code for row in rows]
    for row in rows:
        row.delete()
    return ('plant_builds', names)


def _withdraw_platform_developments(submission):
    """The request, and the draft platform the request created.

    A platform whose funding round is this round has been paid for; one that is
    still `unfunded_draft` has not, and is exactly what an unfunded request
    leaves behind (`rd_costs.allocate_platform_funding`). Only the unpaid draft
    is withdrawn, so nothing already charged is taken back.
    """
    from core.models.team_state import TeamPlatform

    rows = list(submission.platform_developments
                .select_related('platform_generation').order_by('id'))
    if not rows:
        return None
    names = [row.platform_generation.name for row in rows]
    generation_ids = [row.platform_generation_id for row in rows]
    for row in rows:
        row.delete()
    TeamPlatform.objects.filter(
        team=submission.team, status='unfunded_draft',
        platform_generation_id__in=generation_ids).delete()
    return ('platform_developments', names)


def _withdraw_compliance_investments(submission):
    from core.models.cc31_models import ComplianceInvestment

    rows = list(ComplianceInvestment.objects.filter(submission=submission)
                .select_related('market').order_by('id'))
    if not rows:
        return None
    names = [row.market.code for row in rows]
    ComplianceInvestment.objects.filter(submission=submission).delete()
    return ('compliance_investments', names)


def _withdraw_esg(submission):
    from core.models.decisions import DecisionESG

    try:
        esg = submission.esg
    except DecisionESG.DoesNotExist:
        return None
    if esg is None:
        return None
    if esg.environmental_investment == 0 and esg.social_investment == 0:
        return None
    esg.environmental_investment = D('0')
    esg.social_investment = D('0')
    esg.save(update_fields=['environmental_investment', 'social_investment'])
    return ('esg', [])


def _withdraw_market_entries(submission):
    rows = list(submission.market_entries.filter(action='enter')
                .select_related('market').order_by('id'))
    if not rows:
        return None
    names = [row.market.code for row in rows]
    for row in rows:
        row.delete()
    return ('market_entries', names)


def _withdraw_promotion_budgets(submission):
    rows = [row for row in submission.marketing_decisions.order_by('id')
            if row.promotion_budget or row.distribution_investment
            or row.sales_team_count]
    if not rows:
        return None
    for row in rows:
        row.promotion_budget = D('0')
        row.distribution_investment = D('0')
        row.sales_team_count = 0
        row.save(update_fields=['promotion_budget', 'distribution_investment',
                                'sales_team_count'])
    return ('promotion_budgets', [])


def _withdraw_declared_budgets(submission, team):
    """Reduce each declared line to the decisions actually made under it.

    A declared budget is a floor the affordability rule counts (V2-057) and the
    engine never charges on its own -- the engine charges the decisions. So
    this step gives back the headroom a team declared and did not use, and it
    cannot reduce a charge.
    """
    from core.models.decisions import DecisionBudgetAllocation
    from core.services.rd_costs import budget_assessment

    try:
        budget = submission.budget_allocation
    except DecisionBudgetAllocation.DoesNotExist:
        return None
    assessment = budget_assessment(submission, team)
    targets = {
        'rd_budget': D(assessment['rd_spent']),
        'marketing_budget': D(assessment['marketing_spent']),
        'strategy_budget': D(assessment['strategy_spent'])
        - D(assessment['lines'].get('acquisitions', '0')),
        'research_budget': D(assessment['lines']['research_purchases']),
    }
    changed = []
    for field, target in targets.items():
        target = max(target, D('0'))
        if getattr(budget, field) > target:
            setattr(budget, field, target)
            changed.append(field)
    if not changed:
        return None
    budget.save(update_fields=changed)
    return ('declared_budgets', [])


def _resize_equity_to_funding_need(submission):
    """W-CE4-02: the raise must be sized against what is left, not what was.

    A withdrawal above lowers `funding_need.decision_outlays`, which lowers
    `eligible_uses`, which lowers `maximum_new_equity`. The equity raise on the
    submission was sized against the commitments this close has just removed,
    so leaving it alone produces a draft that fits the affordability rule and
    breaks V2-024 -- and `advance_round` then refuses to score the round:

        Round 6 cannot be scored: 4 equity raise(s) exceed the funding
        shortfall they claim to finance ... Aurora Devices: equity raise of
        $23,433,933.40 exceeds the funding shortfall of $23,283,933.40

    Six team-rounds of the fourth walkthrough ended that way, for teams that
    did nothing between the two measurements: immediately before the close
    every team was inside the cap by $100,000, immediately after all four were
    outside it by $150,000. The operator's only way out was a hand-written
    reopen, resize, re-lock, re-close loop.

    The raise is resized **down to the maximum the reduced draft justifies**,
    from `funding_need` -- the same calculator that produced the reduction, so
    the two cannot answer differently -- and never up. That is exactly the
    figure the Decision Summary quotes to a team standing at this draft, and
    exactly what the team would have had to type to lock that draft itself:
    V2-024 rejects rather than clamps, so a student with the reduced draft in
    front of them could have locked at this number and at no higher one.

    Nothing else about the raise changes. It is still *requested*, not
    received: `financing_effect` still subscribes it at investor sentiment and
    still refuses it in distress, so the close cannot promise money the round
    then declines.

    Returns `(before, after)` when the raise moved, otherwise `None`.
    """
    from core.models.decisions import DecisionFinancing
    from core.services.funding_need import assess_submission

    assessment = assess_submission(submission)
    if assessment['within_limit']:
        return None
    financing = DecisionFinancing.objects.filter(submission=submission).first()
    if financing is None:
        # No row means nothing was requested, so the rule cannot be broken.
        return None
    before = D(str(financing.new_equity or 0))
    after = D(assessment['maximum_new_equity'])
    if after >= before:
        return None
    financing.new_equity = after
    financing.save(update_fields=['new_equity'])
    return (before, after)


def _resize_debt_to_ceiling(submission, team):
    """W-CE4-10: a deadline cannot make an invalid debt request legal.

    The ordinary lock refuses unsupported new borrowing, but deadline close
    freezes a draft without running the full lock validator. Resize only the
    incremental debt that the shared ceiling assessment rejects, before the
    affordability pass decides how much of the draft can remain. The change
    is audited and announced just like the deadline's other substitutions.
    """
    from core.models.decisions import DecisionFinancing
    from core.services.debt_ceiling import assess as assess_debt_ceiling

    financing = DecisionFinancing.objects.filter(
        submission=submission).first()
    if financing is None or not financing.new_debt:
        return None
    assessment = assess_debt_ceiling(team, financing)
    if not assessment['blocks_new_debt']:
        return None
    before = D(str(financing.new_debt))
    after = min(before, assessment['maximum_new_debt'])
    if after >= before:
        return None
    financing.new_debt = after
    financing.save(update_fields=['new_debt'])
    return (before, after)


_STEPS = {
    'plant_builds': lambda s, t: _withdraw_plant_builds(s),
    'platform_developments': lambda s, t: _withdraw_platform_developments(s),
    'compliance_investments': lambda s, t: _withdraw_compliance_investments(s),
    'esg': lambda s, t: _withdraw_esg(s),
    'market_entries': lambda s, t: _withdraw_market_entries(s),
    'promotion_budgets': lambda s, t: _withdraw_promotion_budgets(s),
    'declared_budgets': _withdraw_declared_budgets,
}


def bring_draft_within_available_funds(game, round_obj):
    """Apply the lock's affordability rule to every draft the deadline closes.

    Runs before `_lock_all_submissions` freezes anything, so the submission
    each lock event records is already the one that will be resolved. Returns
    a list of per-team records for the caller's log.
    """
    from core.models import DecisionSubmission, Team

    applied = []
    for team in Team.objects.filter(
            game=game, participation_status='active').order_by('id'):
        submission = DecisionSubmission.objects.filter(
            team=team, round=round_obj).first()
        if submission is None or submission.status == 'locked':
            # A team that locked its own submission passed this check at the
            # lock; a team with no submission has committed nothing.
            continue

        fits, assessment = _fits(submission, team)
        debt = _resize_debt_to_ceiling(submission, team)
        if debt is not None:
            # Re-read the one affordability answer after removing money the
            # ceiling will not let this draft borrow.
            fits, assessment = _fits(submission, team)
        if fits and debt is None:
            continue

        before = {
            'committed_total': assessment['committed_total'],
            'available_funds': assessment['available_funds'],
        }
        withdrawn = []
        equity = None
        for name in WITHDRAWAL_ORDER:
            result = _STEPS[name](submission, team)
            if result is None:
                continue
            withdrawn.append(result)
            # W-CE4-02: before asking whether the draft fits again. The raise
            # is part of available funds, so resizing it changes the answer,
            # and asking first would stop the loop on a draft the round then
            # refuses to score. Re-asked after every step because a later
            # withdrawal can lower the maximum again.
            moved = _resize_equity_to_funding_need(submission)
            if moved is not None:
                equity = (equity[0] if equity else moved[0], moved[1])
            fits, assessment = _fits(submission, team)
            if fits:
                break

        if not withdrawn and debt is None:
            continue

        record = {
            'team': team.name, 'team_id': team.id,
            'withdrawn': [{'step': step, 'items': items}
                          for step, items in withdrawn],
            'before': before,
            'after': {'committed_total': assessment['committed_total'],
                      'available_funds': assessment['available_funds']},
            'within_available_funds': fits,
        }
        if equity is not None:
            record['equity_resized'] = {'from': str(equity[0]),
                                        'to': str(equity[1])}
        if debt is not None:
            record['new_debt_resized'] = {'from': str(debt[0]),
                                          'to': str(debt[1])}
        applied.append(record)
        _record(game, team, round_obj, submission, record)
        _notify(game, team, round_obj, record)
    return applied


def _record(game, team, round_obj, submission, record):
    from core.models import DecisionAuditEvent

    action = ('deadline_withdrew_commitments' if record['withdrawn']
              else 'deadline_adjusted_financing')
    DecisionAuditEvent.objects.create(
        game=game, team=team, round=round_obj, user=None,
        action=action,
        endpoint='engine:close_round', payload=record)


# The steps, named for a student. One key per step so the sentence reads the
# same way in both languages and no key is assembled at run time.
_STEP_MESSAGE_KEY = {
    'plant_builds': 'withdrawn_plant_builds',
    'platform_developments': 'withdrawn_platform_developments',
    'compliance_investments': 'withdrawn_compliance_investments',
    'esg': 'withdrawn_esg',
    'market_entries': 'withdrawn_market_entries',
    'promotion_budgets': 'withdrawn_promotion_budgets',
    'declared_budgets': 'withdrawn_declared_budgets',
}


def _notify(game, team, round_obj, record):
    from core.engine.utils import notify_team
    from core.utils.localization import get_team_language
    from core.utils.participant_messages import participant_message

    language = get_team_language(team)
    if record['withdrawn']:
        steps = '; '.join(
            participant_message(
                _STEP_MESSAGE_KEY[entry['step']], language=language)
            for entry in record['withdrawn'])
        notify_team(
            game.id, team, round_obj.round_number,
            participant_message(
                'deadline_withdrew_commitments', language=language,
                committed=f'${D(record["before"]["committed_total"]):,.2f}',
                available=f'${D(record["before"]["available_funds"]):,.2f}',
                withdrawn=steps))
    if record.get('new_debt_resized'):
        notify_team(
            game.id, team, round_obj.round_number,
            participant_message(
                'deadline_resized_debt', language=language,
                requested=f'${D(record["new_debt_resized"]["from"]):,.2f}',
                allowed=f'${D(record["new_debt_resized"]["to"]):,.2f}'))
    # W-CE4-02: a resized raise is a change to the team's own financing
    # decision, so it is said separately rather than folded into the list of
    # things that were withdrawn -- the money was not withdrawn, the request
    # was reduced to what the smaller draft can justify.
    if record.get('equity_resized'):
        notify_team(
            game.id, team, round_obj.round_number,
            participant_message(
                'deadline_resized_equity', language=language,
                requested=f'${D(record["equity_resized"]["from"]):,.2f}',
                allowed=f'${D(record["equity_resized"]["to"]):,.2f}'))
