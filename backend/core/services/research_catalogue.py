"""What a research report costs, and what a team has already bought.

One calculator, in the shape V2-037 adopted for R&D cost: *the price a team is
shown is the price the server computes, and the price the server computes is
the price it charges*. Every surface -- the catalogue the UI renders, the
affordability check, the purchase write, the outlay the funding rule totals and
the expense the engine books -- reads `price_for()` and nothing else. A second
approximate copy is what makes a validator and an engine disagree.

Prices are authored per scenario (R3: a fixed constant would make research
equally costly in every scenario and leave calibration nothing to move). They
are read through `core.engine.utils.get_config`, following the
`reference_price_*` precedent adopted for V2-023.

`DEFAULT_RESEARCH_PRICE` is a fallback, not the rule. Every scenario YAML and
the accompanying data migration author all six keys, so a real database always
answers from its own scenario. The fallback exists because `reference_price_*`
is fail-closed and raises when unauthored, and a report priced by raising would
turn an unrelated test fixture -- one that builds a `Scenario` inline without
config rows -- into a failure in someone else's suite. See the completion
report: whether this should instead be fail-closed is a rules-owner question.
"""
from decimal import Decimal


SEGMENTS = 'segments'
PRODUCTS = 'products'
MARKETS = 'markets'
CHANNELS = 'channels'
STAKEHOLDERS = 'stakeholders'
ANALYST_QUERY = 'analyst_query'

# The five report types `ResearchReportsView` dispatches (research_reports.py).
REPORT_TYPES = (SEGMENTS, PRODUCTS, MARKETS, CHANNELS, STAKEHOLDERS)

# Everything that costs money, reports plus the analyst query.
PURCHASABLE = REPORT_TYPES + (ANALYST_QUERY,)

# Reports that are bought per market. The other three are whole-game reports,
# which is why a purchase is not keyed on a market foreign key.
MARKET_SCOPED = frozenset({SEGMENTS, CHANNELS})

PRICE_CONFIG_KEYS = {
    SEGMENTS: 'research_report_price_segments',
    PRODUCTS: 'research_report_price_products',
    MARKETS: 'research_report_price_markets',
    CHANNELS: 'research_report_price_channels',
    STAKEHOLDERS: 'research_report_price_stakeholders',
    # Its own key because it has a real marginal cost: it is charged per
    # question asked, not bought once for the round.
    ANALYST_QUERY: 'research_analyst_query_price',
}

# A uniform placeholder. Calibration is a later, data-only change.
DEFAULT_RESEARCH_PRICE = Decimal('50000')


class UnknownReportType(ValueError):
    """A report type that is not in the catalogue."""


def price_for(scenario, report_type):
    """The authored price of one report type, as a Decimal."""
    from core.engine.utils import get_config

    if report_type not in PRICE_CONFIG_KEYS:
        raise UnknownReportType(report_type)
    raw = get_config(scenario, PRICE_CONFIG_KEYS[report_type], default=None,
                     cast_type=str)
    if raw is None:
        return DEFAULT_RESEARCH_PRICE
    # Authored as a string, like every other ScenarioConfig value. Decimal is
    # taken over the string rather than a float so an authored price is charged
    # to the cent exactly as written.
    try:
        return Decimal(str(raw))
    except (ArithmeticError, ValueError):
        return DEFAULT_RESEARCH_PRICE


def scope_key_for(report_type, market_code=None):
    """The discriminator that makes "bought once this round" a database rule."""
    if report_type in MARKET_SCOPED and market_code:
        return str(market_code)
    return ''


def is_purchased(submission, report_type, market_code=None):
    """Has this submission already bought this report?"""
    from core.models.research import DecisionResearchPurchase

    if submission is None:
        return False
    return DecisionResearchPurchase.objects.filter(
        submission=submission, report_type=report_type,
        scope_key=scope_key_for(report_type, market_code),
    ).exists()


def is_readable(team, report_type, market_code, round_numbers):
    """Can this team read this report, for any of these rounds?

    A purchase belongs to the round it was made in. Access is granted by a
    purchase in the round being *viewed* as well as the current one, so a
    report bought in round 3 stays readable when round 3 is re-opened after
    close and after the game completes -- post-close retrieval and disputes
    depend on it (CRV2-08). It is not granted across every round, because the
    report's content changes each round and a single purchase must not buy
    every future edition.
    """
    from core.models.research import DecisionResearchPurchase

    rounds = [r for r in round_numbers if r is not None]
    if not rounds:
        return False
    return DecisionResearchPurchase.objects.filter(
        submission__team=team, report_type=report_type,
        scope_key=scope_key_for(report_type, market_code),
        submission__round__round_number__in=rounds,
    ).exists()


def purchase_total(submission):
    """Everything this submission has committed to research this round.

    The figure `funding_need.decision_outlays` totals and `engine/costs.py`
    books, so the funding rule and the engine cannot charge different amounts.
    """
    from core.models.research import DecisionResearchPurchase

    if submission is None:
        return Decimal('0')
    total = Decimal('0')
    for row in (DecisionResearchPurchase.objects
                .filter(submission=submission).order_by('id')):
        total += row.price
    return total


def catalogue(scenario, submission=None, market_code=None):
    """Every purchasable item, its price, and whether it is already bought."""
    entries = []
    for report_type in PURCHASABLE:
        scoped = report_type in MARKET_SCOPED
        entries.append({
            'report_type': report_type,
            'price': str(price_for(scenario, report_type)),
            'market_scoped': scoped,
            'purchased': (False if report_type == ANALYST_QUERY
                          else is_purchased(submission, report_type,
                                            market_code if scoped else None)),
        })
    return entries
