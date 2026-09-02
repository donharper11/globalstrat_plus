"""The authoritative price of R&D, computed on the server.

One calculator, two callers. Before this, the scenario authored the prices —
`PlatformGenerationDefinition.development_cost` / `license_cost`, and the
per-level `FeatureLevelCost` table — and nothing compared them to what a team
submitted. `committed_cost`, `amount` and `calculated_cost` were team-supplied
numbers computed in the browser, and the engine charged whatever arrived
(`costs.py:413`). GSP-CRV2-10 Stage 1 measured the consequence: a platform
authored at $15,000,000 taken for `committed_cost: 0`, active, charged $0.00
(V2-037), and a feature raised to its ceiling for `amount: 0`, charged nothing
in any round.

The rule this module exists to make true: **the cost a team is shown is the
cost the server computes, and the cost the server computes is the cost it
charges.** Not two functions kept in step by hand — one function with two
callers. The display path (`_build_cost_schedule`) and the charge path read the
same table through the same code here, so they cannot drift.

Nothing here clamps or reinterprets a submitted value. A disagreement is
refused and named, because a decision quietly replaced with a different one
looks ordinary afterwards.
"""
from decimal import Decimal

from core.models.scenario import (FeatureLevelCost, PlatformFeatureCeiling,
                                  PlatformGenerationDefinition)

ZERO = Decimal('0')

# `method` on a platform development names which authored price applies.
METHOD_COST_FIELD = {
    'in_house': 'development_cost',
    'license': 'license_cost',
}


class UnauthoredCost(Exception):
    """The scenario does not author a price for what was asked.

    Raised rather than defaulted to zero. A missing price is a configuration
    fault, and the failure mode this whole module exists to remove is exactly
    "no authored figure, so nothing was charged".
    """


def platform_development_cost(generation, method):
    """The authored cost of developing or licensing one platform generation.

    `method` selects the price: `in_house` pays `development_cost`, `license`
    pays `license_cost`. Stage 1 recorded that `method` presently changes
    neither the price charged nor the lead time; this makes it change the price.
    """
    if isinstance(generation, int):
        generation = PlatformGenerationDefinition.objects.filter(
            pk=generation).first()
    if generation is None:
        raise UnauthoredCost('No such platform generation.')

    field = METHOD_COST_FIELD.get((method or '').strip().lower())
    if field is None:
        raise UnauthoredCost(
            f'Unknown development method {method!r}; expected one of '
            f'{", ".join(sorted(METHOD_COST_FIELD))}.')

    cost = getattr(generation, field, None)
    if cost is None:
        raise UnauthoredCost(
            f'{generation.name} authors no {field}, so its {method} price is '
            f'undefined. Set it in the scenario rather than charging zero.')
    return Decimal(cost)


def level_cost_schedule(feature, platform_generation, current_level,
                        ceiling_value):
    """Cost of each level above `current_level` up to the ceiling.

    The table the R&D screen already displayed. Lifted out of the view so the
    charge path reads the same rows.
    """
    current = int(float(current_level))
    ceiling = int(float(ceiling_value))
    schedule = []
    cumulative = ZERO
    rows = (FeatureLevelCost.objects
            .filter(feature=feature, platform_generation=platform_generation,
                    level__gt=current, level__lte=ceiling)
            .order_by('level'))
    for row in rows:
        cumulative += row.incremental_cost
        schedule.append({
            'level': row.level,
            'incremental_cost': row.incremental_cost,
            'cumulative_from_current': cumulative,
        })
    return schedule


def feature_upgrade_cost(feature, platform_generation, current_level,
                         target_level):
    """The authored cost of raising one feature from current to target.

    Sums the same `FeatureLevelCost` rows the schedule shows. A target at or
    below the current level costs nothing and is not an error: it asks for
    nothing.
    """
    current = int(float(current_level))
    target = int(float(target_level))
    if target <= current:
        return ZERO

    # The ceiling is asked first, so a feature that is simply unavailable on
    # this generation is refused as unreachable rather than as unpriced. All
    # three shipped scenarios author four ceiling rows at 0.00 -- the feature
    # does not exist on that generation -- and no level prices for them, which
    # is correct authoring. Reporting those as a missing price would refuse a
    # student's submission for a configuration fault that is not one.
    ceiling = feature_ceiling(feature, platform_generation)
    if ceiling is not None and target > int(float(ceiling)):
        raise UnauthoredCost(
            f'{getattr(feature, "code", feature)} has a ceiling of '
            f'{int(float(ceiling))} on '
            f'{getattr(platform_generation, "name", platform_generation)}; '
            f'level {target} cannot be reached on this platform.')

    rows = list(FeatureLevelCost.objects
                .filter(feature=feature,
                        platform_generation=platform_generation,
                        level__gt=current, level__lte=target)
                .order_by('level'))
    if len(rows) != (target - current):
        priced = sorted(row.level for row in rows)
        raise UnauthoredCost(
            f'Levels {current + 1}-{target} of {getattr(feature, "code", feature)} '
            f'on {getattr(platform_generation, "name", platform_generation)} '
            f'are not fully priced (found levels {priced or "none"}). Author '
            f'the missing FeatureLevelCost rows rather than charging for the '
            f'levels that happen to exist.')
    return sum((row.incremental_cost for row in rows), ZERO)


def feature_ceiling(feature, platform_generation):
    """The authored ceiling for one feature on one generation, or None."""
    row = PlatformFeatureCeiling.objects.filter(
        feature=feature, platform_generation=platform_generation).first()
    return row.ceiling_value if row else None


def current_feature_level(team_platform, feature):
    from core.models.team_state import TeamPlatformFeatureLevel
    row = (TeamPlatformFeatureLevel.objects
           .filter(team_platform=team_platform, feature=feature).first())
    return row.current_level if row else ZERO


def rd_investment_cost(investment):
    """The authored cost of one persisted or validated R&D investment.

    Accepts either a model instance or a validated dict, so the write path and
    the engine precondition ask the same question of the same data.
    """
    platform = _get(investment, 'team_platform')
    feature = _get(investment, 'feature')
    target = _get(investment, 'target_level')
    if platform is None or feature is None or target is None:
        raise UnauthoredCost(
            'An R&D investment needs a platform, a feature and a target level '
            'before its cost can be computed.')
    generation = platform.platform_generation
    return feature_upgrade_cost(
        feature, generation, current_feature_level(platform, feature), target)


def platform_cost_for(development):
    """The authored cost of one persisted or validated platform development."""
    return platform_development_cost(_get(development, 'platform_generation'),
                                     _get(development, 'method'))


def _get(item, name):
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


# ---------------------------------------------------------------------------
# The engine precondition
# ---------------------------------------------------------------------------

def persisted_cost_violations(game, round_obj):
    """Stored R&D rows whose cost disagrees with the authored price.

    The same shape as V2-018's negative-value guard: name the model, the row,
    the field, what is stored and what the scenario authors, so a refusal says
    which row to correct rather than that something is wrong.

    This exists because the API is not the only way a row reaches the database.
    An admin edit, a `manage.py shell`, a restore or a future endpoint can all
    write one, and the write-path enforcement cannot see any of them. The
    boundary that has to hold is the one immediately before competitive
    mutation.
    """
    from core.models.decisions import (DecisionPlatformDevelopment,
                                       DecisionRDInvestment)

    violations = []

    developments = (DecisionPlatformDevelopment.objects
                    .filter(submission__round=round_obj,
                            submission__team__game=game)
                    .select_related('platform_generation', 'submission__team')
                    .order_by('pk'))
    for row in developments:
        try:
            authored = platform_development_cost(row.platform_generation,
                                                 row.method)
        except UnauthoredCost as problem:
            violations.append({
                'model': 'DecisionPlatformDevelopment', 'row': row.pk,
                'field': 'committed_cost', 'stored': str(row.committed_cost),
                'authored': None, 'detail': str(problem)})
            continue
        if Decimal(row.committed_cost) != authored:
            violations.append({
                'model': 'DecisionPlatformDevelopment', 'row': row.pk,
                'team': row.submission.team.name,
                'field': 'committed_cost', 'stored': str(row.committed_cost),
                'authored': str(authored),
                'detail': (f'{row.platform_generation.name} by {row.method} is '
                           f'priced at {authored:,.2f}')})

    investments = (DecisionRDInvestment.objects
                   .filter(submission__round=round_obj,
                           submission__team__game=game)
                   .select_related('team_platform__platform_generation',
                                   'feature', 'submission__team')
                   .order_by('pk'))
    for row in investments:
        try:
            authored = rd_investment_cost(row)
        except UnauthoredCost as problem:
            violations.append({
                'model': 'DecisionRDInvestment', 'row': row.pk,
                'field': 'calculated_cost',
                'stored': str(row.calculated_cost),
                'authored': None, 'detail': str(problem)})
            continue
        for field in ('calculated_cost', 'amount'):
            stored = getattr(row, field, None)
            if stored is not None and Decimal(stored) != authored:
                violations.append({
                    'model': 'DecisionRDInvestment', 'row': row.pk,
                    'team': row.submission.team.name,
                    'field': field, 'stored': str(stored),
                    'authored': str(authored),
                    'detail': (f'raising {getattr(row.feature, "code", row.feature_id)} '
                               f'to level {row.target_level} is priced at '
                               f'{authored:,.2f}')})
    return violations


def describe_cost_violations(violations, limit=5):
    """One readable line per offending row, for the refusal message."""
    shown = violations[:limit]
    lines = [
        (f'{item["model"]} #{item["row"]}'
         + (f' ({item["team"]})' if item.get('team') else '')
         + f': {item["field"]} stored {item["stored"]}'
         + (f', authored {item["authored"]}' if item.get('authored') else '')
         + (f' — {item["detail"]}' if item.get('detail') else ''))
        for item in shown]
    if len(violations) > limit:
        lines.append(f'... and {len(violations) - limit} more')
    return ' | '.join(lines)


# ---------------------------------------------------------------------------
# One budget-versus-cash rule
# ---------------------------------------------------------------------------

def committed_outlay(submission):
    """Everything a submission commits, including platform development.

    Platform development was outside every budget check: `total_budget` summed
    the three budget lines and `rd_total` summed `rd_investments.amount`, and
    neither mentioned `platform_developments.committed_cost` (V2-038). A team
    could commit a nine-figure platform against a four-figure R&D budget and
    nothing objected.
    """
    budget = getattr(submission, 'budget_allocation', None)
    lines = {}
    for field in ('rd_budget', 'marketing_budget', 'strategy_budget',
                  'research_budget'):
        lines[field] = Decimal(getattr(budget, field, ZERO) or ZERO)

    platform = sum(
        (Decimal(row.committed_cost or ZERO)
         for row in submission.platform_developments.all()), ZERO)
    rd_rows = sum(
        (Decimal(row.amount or ZERO)
         for row in submission.rd_investments.all()), ZERO)
    lines['platform_development'] = platform
    lines['rd_investments'] = rd_rows
    return lines


def budget_assessment(submission, team=None):
    """The single answer to "can this team afford what it has committed?"

    Written once because it was written three times and the three disagreed:
    `views/decisions.py:548` and `:888` summed three budget lines, `:1015`
    summed four by including `research_budget`, and none of them counted
    platform development at all. Three rules that disagree is one rule that
    does not exist.
    """
    team = team or submission.team
    lines = committed_outlay(submission)
    budget_total = (lines['rd_budget'] + lines['marketing_budget']
                    + lines['strategy_budget'] + lines['research_budget'])
    # Platform development is committed money that the budget lines do not
    # contain, so it is added to the total the cash has to cover.
    committed = budget_total + lines['platform_development']
    cash = Decimal(getattr(team, 'cash_on_hand', ZERO) or ZERO)

    rd_committed = lines['rd_investments'] + lines['platform_development']
    return {
        'lines': {name: str(value) for name, value in lines.items()},
        'budget_total': str(budget_total),
        'committed_total': str(committed),
        'cash_on_hand': str(cash),
        'within_cash': committed <= cash,
        'rd_committed': str(rd_committed),
        'rd_budget': str(lines['rd_budget']),
        'within_rd_budget': rd_committed <= lines['rd_budget'],
    }


def describe_budget_problems(assessment):
    """The errors an operator or student should see, or an empty list."""
    problems = []
    if not assessment['within_cash']:
        problems.append(
            f'Committed spend of ${Decimal(assessment["committed_total"]):,.2f} '
            f'exceeds available cash of '
            f'${Decimal(assessment["cash_on_hand"]):,.2f}. This includes '
            f'${Decimal(assessment["lines"]["platform_development"]):,.2f} of '
            f'platform development.')
    if not assessment['within_rd_budget']:
        problems.append(
            f'R&D commitments of '
            f'${Decimal(assessment["rd_committed"]):,.2f} exceed the R&D '
            f'budget of ${Decimal(assessment["rd_budget"]):,.2f}. Platform '
            f'development counts against the R&D budget.')
    return problems


# ---------------------------------------------------------------------------
# The unlock gate (V2-039)
# ---------------------------------------------------------------------------

def unlock_problem(generation, round_number):
    """Why this generation may not be developed in this round, or None.

    The unlock check lived only in the lock validator. Stage 1 measured the
    consequence: a Gen 3 platform unlocking at round 5 was submitted in round
    3, the team never locked, close defaulted the submission, and the engine
    built it anyway — active two rounds before it existed as an option.

    A gate that binds only the teams who lock does not bind anyone.
    """
    if generation is None:
        return 'No such platform generation.'
    unlock = getattr(generation, 'unlock_round', None)
    if unlock is not None and round_number is not None and round_number < unlock:
        return (f'{generation.name} unlocks in round {unlock}; this is round '
                f'{round_number}.')
    return None


def persisted_unlock_violations(game, round_obj):
    """Stored platform developments for a generation not yet unlocked."""
    from core.models.decisions import DecisionPlatformDevelopment

    violations = []
    rows = (DecisionPlatformDevelopment.objects
            .filter(submission__round=round_obj, submission__team__game=game)
            .select_related('platform_generation', 'submission__team')
            .order_by('pk'))
    for row in rows:
        problem = unlock_problem(row.platform_generation,
                                 getattr(round_obj, 'round_number', None))
        if problem:
            violations.append({
                'model': 'DecisionPlatformDevelopment', 'row': row.pk,
                'team': row.submission.team.name,
                'field': 'platform_generation', 'detail': problem})
    return violations


def describe_unlock_violations(violations, limit=5):
    lines = [f'{item["model"]} #{item["row"]} ({item["team"]}): {item["detail"]}'
             for item in violations[:limit]]
    if len(violations) > limit:
        lines.append(f'... and {len(violations) - limit} more')
    return ' | '.join(lines)


# ---------------------------------------------------------------------------
# Platform ownership (V2-044)
# ---------------------------------------------------------------------------

def ownership_problem(team_platform, team):
    """Why this team may not invest in this platform, or None.

    Stage 1 measured both halves: the write surfaces accepted an R&D
    investment naming another team's platform, and the lock validator's
    ownership check — which is correct — was reached only by teams that
    locked. A team that never locks is defaulted at close, so in the first
    probe run the foreign row reached the engine and wrote duplicate
    PendingFeatureGain rows against the other team's platform, leaving the
    round unprocessable.

    Same shape as V2-039: a gate that binds only the teams who lock does not
    bind anyone.
    """
    if team_platform is None:
        return 'No such platform.'
    owner_id = getattr(team_platform, 'team_id', None)
    if team is None:
        return None
    if owner_id != getattr(team, 'id', team):
        return (f'Platform "{team_platform.name}" belongs to another team. '
                f'R&D can only be invested in your own platforms.')
    return None


def persisted_ownership_violations(game, round_obj):
    """Stored R&D investments naming a platform the submitting team does not own."""
    from core.models.decisions import DecisionRDInvestment

    violations = []
    rows = (DecisionRDInvestment.objects
            .filter(submission__round=round_obj, submission__team__game=game)
            .select_related('team_platform', 'submission__team')
            .order_by('pk'))
    for row in rows:
        problem = ownership_problem(row.team_platform, row.submission.team)
        if problem:
            violations.append({
                'model': 'DecisionRDInvestment', 'row': row.pk,
                'team': row.submission.team.name,
                'field': 'team_platform',
                'platform_owner': getattr(row.team_platform, 'team_id', None),
                'detail': problem})
    return violations


def describe_ownership_violations(violations, limit=5):
    lines = [f'{item["model"]} #{item["row"]} ({item["team"]}): {item["detail"]}'
             for item in violations[:limit]]
    if len(violations) > limit:
        lines.append(f'... and {len(violations) - limit} more')
    return ' | '.join(lines)


# ---------------------------------------------------------------------------
# Paid before ready
# ---------------------------------------------------------------------------

def platform_price(generation, method):
    """The authored price of one candidate, or None if the scenario has none."""
    try:
        return platform_development_cost(generation, method)
    except UnauthoredCost:
        return None


def allocate_platform_funding(team, candidates):
    """Decide which platforms this team can fund **together**, this round.

    V2-045. Affordability used to be a per-row boolean against
    `team.cash_on_hand`, and both lifecycle loops asked it independently: two
    $1,000,000 drafts against $1,500,000 of cash both came back affordable,
    both started their clocks, and the accounting path then booked $2,000,000
    against $1,500,000. A per-item test that never reserves what it has already
    accepted does not compose.

    One allocation, one running balance. Each accepted candidate's authoritative
    cost is reserved before the next is considered, so no set of transitions can
    book more than the funding available to that set.

    `candidates` is an ordered sequence of `(key, generation, method)`. The
    caller fixes the order and the ordering rule is stated there; this function
    keeps it deterministic by walking the sequence as given.

    Returns `{key: Decimal price}` for the funded candidates only. A candidate
    that does not fit the remaining balance is simply absent, and the caller
    leaves it an unfunded draft with no funding round and no running clock.
    """
    remaining = Decimal(getattr(team, 'cash_on_hand', ZERO) or ZERO)
    funded = {}
    for key, generation, method in candidates:
        price = platform_price(generation, method)
        if price is None:
            # Unpriced: refused by the engine precondition before this point.
            # Never funded on a guess.
            continue
        if price <= remaining:
            funded[key] = price
            remaining -= price
    return funded


# ---------------------------------------------------------------------------
# The per-platform feature cap
# ---------------------------------------------------------------------------

def feature_cap(scenario, default=5):
    """The maximum number of features one platform may carry.

    Stated in one place. `max_platform_features` is the scenario value; the
    default matches the constant the engine used.
    """
    from core.engine.utils import get_config
    try:
        return int(get_config(scenario, 'max_platform_features', default))
    except (TypeError, ValueError):
        return default


def feature_count_problem(feature_levels, scenario):
    """Why this platform names too many features, or None."""
    if not feature_levels:
        return None
    chosen = [level for level in feature_levels.values()
              if level and float(level) > 0]
    cap = feature_cap(scenario)
    if len(chosen) > cap:
        return (f'A platform may carry at most {cap} features; this names '
                f'{len(chosen)}.')
    return None


def persisted_feature_cap_violations(game, round_obj):
    """Stored platform developments naming more features than the cap allows.

    Refused rather than truncated. Activation used to slice the decision to
    the cap, so an over-cap row produced a platform carrying an arbitrary
    subset while the stored decision still named the full set: the evidence
    and the platform built from it disagreed, silently.
    """
    from core.models.decisions import DecisionPlatformDevelopment

    violations = []
    rows = (DecisionPlatformDevelopment.objects
            .filter(submission__round=round_obj, submission__team__game=game)
            .select_related('platform_generation__scenario',
                            'submission__team')
            .order_by('pk'))
    for row in rows:
        levels = row.feature_levels or {}
        named = [level for level in levels.values()
                 if level and float(level) > 0]
        cap = feature_cap(getattr(row.platform_generation, 'scenario', None))
        if len(named) > cap:
            violations.append({
                'model': 'DecisionPlatformDevelopment', 'row': row.pk,
                'team': row.submission.team.name,
                'field': 'feature_levels',
                'submitted_count': len(named), 'cap': cap,
                'detail': (f'names {len(named)} features; a platform may carry '
                           f'at most {cap}')})
    return violations


def describe_feature_cap_violations(violations, limit=5):
    lines = [f'{item["model"]} #{item["row"]} ({item["team"]}): '
             f'{item["detail"]}' for item in violations[:limit]]
    if len(violations) > limit:
        lines.append(f'... and {len(violations) - limit} more')
    return ' | '.join(lines)
