"""The Strategic Scorecard's sentences, chosen once (W-CE2-07).

The engine wrote these as English f-strings with no catalogue entry, so a
Chinese team read *Conservative leverage. Strong financial position.* on an
otherwise Chinese Round Results tab.

What the engine **stores** cannot follow the reader: `RoundResultCoherence
.breakdown` is a hashed field of the `coherence` manifest section, and a
scoring artefact in the competitive hash may not depend on who opens the
screen. So the stored sentence stays English, byte-identical to what shipped,
and the reader re-derives the same key from the same stored numbers.

There is one rule, not two: the engine picks the key with the functions below
and stores their English rendering; `feedback_for_reader` calls the same
functions on the numbers the engine stored beside the sentence. A breakdown
this module cannot place -- an older row, or a criterion with no rule here --
keeps the sentence it already has.
"""
from core.utils.participant_messages import participant_message


# Criterion name in `breakdown` -> the numbers its key is derived from.
#
# W-CE3-06: the governance/tax sentence stayed English on a Chinese screen
# while its two siblings were translated, because the name written here was
# the scoring function's (`_score_governance_tax_consistency`) and not the
# key the engine stores the entry under (`breakdown['governance_tax']`).
# `_key_and_values` therefore never matched it and every read fell through to
# "keep the stored sentence". Both names are accepted, so a row written under
# either is placed.
FINANCIAL_PRUDENCE = 'financial_prudence'
BUDGET_DISCIPLINE = 'budget_discipline'
GOVERNANCE_TAX = 'governance_tax'
GOVERNANCE_TAX_NAMES = ('governance_tax', 'governance_tax_consistency')

ALL_KEYS = (
    'coherence_leverage_conservative',
    'coherence_leverage_moderate',
    'coherence_leverage_high',
    'coherence_budget_no_baseline',
    'coherence_budget_within',
    'coherence_budget_slightly_over',
    'coherence_budget_over',
    'coherence_budget_significantly_over',
    'coherence_budget_massively_over',
    'coherence_governance_tax_clear',
    'coherence_governance_tax_conflict',
    'coherence_governance_tax_aggressive',
)

# The budget sentences that name the overspend as a percentage.
KEYS_TAKING_OVER_PCT = (
    'coherence_budget_slightly_over',
    'coherence_budget_over',
    'coherence_budget_significantly_over',
    'coherence_budget_massively_over',
)


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def financial_prudence_key(debt_to_equity):
    """The leverage sentence, by the same thresholds the score uses."""
    d2e = _f(debt_to_equity)
    if d2e < 1.0:
        return 'coherence_leverage_conservative'
    if d2e < 2.0:
        return 'coherence_leverage_moderate'
    return 'coherence_leverage_high'


def budget_discipline_key(over_pct, operating_budget):
    """The budget sentence, by the same thresholds the score uses.

    An operating budget of zero or less is the first round, where there is no
    prior profit to compute a baseline from.
    """
    if _f(operating_budget) <= 0:
        return 'coherence_budget_no_baseline'
    over = _f(over_pct)
    if over <= 0:
        return 'coherence_budget_within'
    if over <= 0.10:
        return 'coherence_budget_slightly_over'
    if over <= 0.25:
        return 'coherence_budget_over'
    if over <= 0.50:
        return 'coherence_budget_significantly_over'
    return 'coherence_budget_massively_over'


def governance_tax_key(score):
    """The governance/tax sentence.

    Placed by the score the same branch set, because that branch stores no
    other number: 1.0 no conflict, 0.0 the anti-corruption contradiction,
    anything between them the aggressive structure with no commitment.
    """
    value = _f(score)
    if value >= 1.0:
        return 'coherence_governance_tax_clear'
    if value <= 0.0:
        return 'coherence_governance_tax_conflict'
    return 'coherence_governance_tax_aggressive'


def over_pct_text(over_pct):
    """The percentage exactly as the engine's f-string formatted it."""
    return f'{_f(over_pct):.0%}'


def feedback_text(key, language='en', **values):
    """One scorecard sentence, rendered."""
    return participant_message(key, language=language, **values)


def _key_and_values(criterion, entry):
    """The key and format values for a stored breakdown entry, or (None, {})."""
    if criterion == FINANCIAL_PRUDENCE:
        if 'debt_to_equity' not in entry:
            return None, {}
        return financial_prudence_key(entry.get('debt_to_equity')), {}
    if criterion == BUDGET_DISCIPLINE:
        if 'operating_budget' not in entry:
            return None, {}
        key = budget_discipline_key(
            entry.get('over_pct'), entry.get('operating_budget'))
        values = ({'over': over_pct_text(entry.get('over_pct'))}
                  if key in KEYS_TAKING_OVER_PCT else {})
        return key, values
    if criterion in GOVERNANCE_TAX_NAMES:
        if 'score' not in entry:
            return None, {}
        return governance_tax_key(entry.get('score')), {}
    return None, {}


def feedback_for_reader(criterion, entry, language='en'):
    """The stored sentence for `criterion`, in this reader's language.

    Falls back to the stored English sentence whenever the entry cannot be
    placed -- a criterion with no rule here, a row written before the numbers
    were stored, or a rendering that raises. A screen never loses a sentence
    to this.
    """
    stored = (entry or {}).get('feedback', '')
    if language == 'en':
        return stored
    try:
        key, values = _key_and_values(criterion, entry or {})
        if key is None:
            return stored
        return feedback_text(key, language, **values)
    except Exception:
        return stored


def _localised_details(details, market_names):
    """A copy of one criterion's detail rows with the market named for the
    reader (W-CE3-07).

    `entry_mode_risk`, `positioning_price` and `distribution_positioning`
    each store `market` as the stored English `MarketDefinition.name`, so a
    Chinese read of Round Results carried *Africa*, *North America*, *East
    Asia* inside the scorecard's own tables while the same market was 非洲 /
    北美 everywhere else in the same response.

    The stored row cannot carry the reader's language -- `breakdown` is a
    hashed field of the competitive `coherence` section -- and it carries no
    market id to look up, so the English name it does carry is the key. A
    name the mapping does not hold keeps the stored value: a market renamed
    or removed since the round was resolved loses nothing.

    The product name is deliberately left alone. It is the team's own name,
    as `platform_display_name` treats a platform the team named.
    """
    if not market_names:
        return details
    rendered = []
    for row in details:
        name = row.get('market') if isinstance(row, dict) else None
        if name in market_names:
            rendered.append(dict(row, market=market_names[name]))
        else:
            rendered.append(row)
    return rendered


def localised_breakdown(breakdown, language='en', market_names=None):
    """A copy of a stored breakdown with every sentence in `language`.

    The stored row is never written: this builds a new dict for the response.

    `market_names` maps a stored English market name to the name this reader
    should see; the caller builds it because it is the caller that holds the
    scenario. Omitted, the detail tables are served exactly as stored.
    """
    if language == 'en' or not isinstance(breakdown, dict):
        return breakdown or {}
    rendered = {}
    for criterion, entry in breakdown.items():
        if not isinstance(entry, dict):
            rendered[criterion] = entry
            continue
        row = dict(entry)
        if 'feedback' in row:
            row['feedback'] = feedback_for_reader(criterion, entry, language)
        if isinstance(row.get('details'), list):
            row['details'] = _localised_details(row['details'], market_names)
        rendered[criterion] = row
    return rendered
