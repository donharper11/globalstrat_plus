"""Stage 5 — THE price band: one calculator, one rule, three surfaces.

Ruling 2, confirmed by the handoff owner 2026-08-31, including the audit
requirement. The band is +/- ``price_band_pct`` (default 30%) of the price the
product was selling at last round, authored per scenario rather than fixed.

  | Team's input | While the round is open  | At the deadline            |
  |--------------|-------------------------|----------------------------|
  | Out of band  | ALERT naming the legal  | auto-adjusted to the       |
  |              | range; submission is    | NEARER band edge           |
  |              | accepted, number kept   |                            |
  | Blank        | ALERT: will be priced   | set to previous round -30% |
  |              | at the floor            | (the band floor)           |
  | In band      | nothing                 | used as entered            |

WHY THIS SUBSTITUTES WHERE BECSR REFUSES. ``BECSR/services/pricing.py`` RW-52
refuses an out-of-band price with a 400, on the argument that storing 130
against a success response lies to a student who typed 140. That objection is
real and it is answered here by two things the ruling makes mandatory rather
than optional: every adjustment writes a ``DecisionAuditEvent`` with actor
``system`` recording the submitted value, the applied value and the rule, and
the adjustment is shown to the team on its results screen. A substitution the
team can see, with a receipt naming what they submitted, is not the silent
clamp BECSR rejected. An unaudited one would be, which is why the audit event
is part of this module's contract and not a rider on it.

THE SINGLE-CALLER RULE (BECSR RW-50, and the reason this module exists). The
price shown as legal, the price accepted, and the price applied all come from
``price_band`` here:

  * the pricing surface (``MarketingContextView``) renders ``price_band``;
  * the write response (``DecisionMarketingSerializer.get_warnings``) alerts
    from ``evaluate``;
  * the deadline (``close_round`` -> ``apply_band_at_deadline``) applies
    ``adjusted_price``.

Three callers, one function. The rule is never written twice, so the range a
team is told is legal is the range that is enforced, to the cent.

ROUND 1 IS NOT A SPECIAL CASE. The anchor is the most recent
``RoundResultProductMarket.retail_price`` for this (team, product, market) in
an earlier round. ``bootstrap_round_zero`` writes exactly such a row for round
0 from the authored ``FirmStarterProduct.base_price``, so round 1 resolves
through the same lookup every later round uses. Reading the round-0 result row
rather than ``FirmStarterProduct`` is deliberate: ``TeamProduct`` has no
foreign key back to the starter product (bootstrap matches on product name)
and the team's home market may differ from the starter product's market, so
re-deriving that match here would duplicate a fragile join for no gain.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ZERO = Decimal('0')

# --- The authored dial -------------------------------------------------------
# A fraction of last round's price, never absolute money: scenarios price in
# very different ranges and calibration (GSP-CRV2-11) must be able to move the
# band without touching code.
PRICE_BAND_PCT_KEY = 'price_band_pct'
PRICE_BAND_PCT_DEFAULT = 0.30

# --- Anchor sources ----------------------------------------------------------
ANCHOR_PREVIOUS_ROUND = 'previous_round'
ANCHOR_POSITIONING_REFERENCE = 'positioning_reference'
ANCHOR_NONE = 'none'

# --- Evaluation outcomes -----------------------------------------------------
IN_BAND = 'in_band'
ABOVE_BAND = 'above_band'
BELOW_BAND = 'below_band'
NO_ANCHOR = 'no_anchor'

# --- Rule identifiers recorded in the audit payload --------------------------
# Stable strings: they are what a dispute is answered with months later, so
# they are part of the record's meaning and are not reworded casually.
RULE_OUT_OF_BAND = 'price_band.out_of_band_adjusted_to_nearer_edge'
RULE_BLANK = 'price_band.blank_priced_at_band_floor'

ACTION_ADJUSTED = 'price_band_adjusted'
ACTION_BLANK_DEFAULTED = 'price_blank_defaulted'


def money(value):
    """Two decimals, half-up — the same rounding the rest of the engine uses.

    A band edge a team is told is legal has to be legal to the cent, or the
    number on the screen and the number the comparison uses disagree at the
    boundary.
    """
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'),
                                            rounding=ROUND_HALF_UP)
    except (TypeError, ValueError, InvalidOperation):
        return None


def band_pct(scenario):
    """The band half-width as a fraction (0.30 == +/-30%), authored per scenario.

    Defaults rather than refusing, unlike ``scenario_reference_prices``: a
    missing reference price would make price competitiveness meaningless (the
    V2-023 failure), whereas a missing band simply takes the ruling's stated
    default of 30%. A negative authored value is treated as zero — i.e. no
    band — rather than inverting the range.
    """
    from core.engine.utils import get_config
    raw = get_config(scenario, PRICE_BAND_PCT_KEY,
                     default=PRICE_BAND_PCT_DEFAULT)
    try:
        pct = float(raw)
    except (TypeError, ValueError):
        return PRICE_BAND_PCT_DEFAULT
    if pct != pct or pct in (float('inf'), float('-inf')):  # NaN / inf
        return PRICE_BAND_PCT_DEFAULT
    return max(0.0, pct)


def _previous_round_price(team, team_product, market, round_number):
    """What this product was selling at, in this market, most recently.

    Ordered by ``round_number`` descending over rounds strictly earlier than
    the one being priced, so a product that skipped a round is still anchored
    to the last price it actually sold at rather than losing its anchor.
    """
    from core.models.results_financials import RoundResultProductMarket
    row = (RoundResultProductMarket.objects
           .filter(team=team, team_product=team_product, market=market,
                   round_number__lt=round_number)
           .order_by('-round_number')
           .values_list('retail_price', 'round_number')
           .first())
    if not row:
        return None, None
    price, anchor_round = row
    price = money(price)
    if price is None or price <= ZERO:
        return None, None
    return price, anchor_round


def _positioning_reference_price(scenario, team_product):
    """The authored reference price for this product's positioning tier.

    Used only when the product has never sold in this market — a newly
    launched product, or a market the team has just entered. It is authored
    per scenario and per tier (``reference_price_budget`` and siblings), the
    same values the preference engine already scores price competitiveness
    against, so the band a new product gets is the band the scenario author
    set rather than one invented here.

    RULES-OWNER QUESTION — see the completion report. The alternative is to
    leave a product with no prior price unbanded. That was rejected as the
    default because it leaves V2-041's exposure open on exactly the path a
    team would use to exploit it: launch a product, price it at 1.
    """
    from core.engine.utils import (InvalidScenarioConfiguration,
                                   scenario_reference_prices)
    try:
        prices = scenario_reference_prices(scenario)
    except InvalidScenarioConfiguration:
        # No authored reference: no anchor, therefore no band. Refusing here
        # would turn a scenario-authoring gap into a blocked pricing screen.
        return None
    reference = prices.get((team_product.positioning or '').lower())
    return money(reference) if reference else None


def price_anchor(scenario, team, team_product, market, round_number):
    """``(anchor, source, anchor_round)`` — the price the band is measured from.

    ``source`` is one of ``previous_round``, ``positioning_reference`` or
    ``none``. With ``none`` there is no anchor and therefore no band, and any
    price is legal.
    """
    anchor, anchor_round = _previous_round_price(
        team, team_product, market, round_number)
    if anchor is not None:
        return anchor, ANCHOR_PREVIOUS_ROUND, anchor_round

    reference = _positioning_reference_price(scenario, team_product)
    if reference is not None:
        return reference, ANCHOR_POSITIONING_REFERENCE, None

    return None, ANCHOR_NONE, None


def price_band(scenario, team, team_product, market, round_number):
    """The legal range for one product-market this round, as a plain dict.

    ``min``/``max`` are ``None`` when there is no anchor. Everything a surface
    needs to *state* the rule is in here, so no caller recomputes any part of
    it.
    """
    anchor, source, anchor_round = price_anchor(
        scenario, team, team_product, market, round_number)
    pct = band_pct(scenario)
    band = {
        'anchor': anchor,
        'anchor_source': source,
        'anchor_round_number': anchor_round,
        'band_pct': pct,
        'min': None,
        'max': None,
    }
    if anchor is None or pct <= 0:
        return band
    factor = Decimal(str(pct))
    band['min'] = money(anchor * (Decimal('1') - factor))
    band['max'] = money(anchor * (Decimal('1') + factor))
    return band


def evaluate(submitted, band):
    """Where a submitted price sits relative to ``band``.

    Returns ``in_band``, ``above_band``, ``below_band`` or ``no_anchor``. A
    price is never rejected here: while the round is open the team's number is
    kept whatever this says (Ruling 2), and this only decides whether they are
    alerted.
    """
    if band is None or band.get('min') is None:
        return NO_ANCHOR
    price = money(submitted)
    if price is None:
        return NO_ANCHOR
    if price < band['min']:
        return BELOW_BAND
    if price > band['max']:
        return ABOVE_BAND
    return IN_BAND


def adjusted_price(submitted, band):
    """The price the deadline applies: the NEARER band edge, or the value as entered.

    Nearer rather than, say, always the floor: the adjustment exists to bring
    an illegal number back inside the legal range with the smallest change to
    what the team actually decided. A team that priced high keeps pricing as
    high as the rules allow.
    """
    status = evaluate(submitted, band)
    if status == ABOVE_BAND:
        return band['max'], status
    if status == BELOW_BAND:
        return band['min'], status
    return money(submitted), status


def blank_price(band):
    """The price a blank submission is given: the floor, i.e. last round -30%.

    An absent choice cannot be refused the way an illegal one can — there is
    nothing to hand back and nothing the team decided — so the system takes
    the most conservative value the band allows and says so, on the pricing
    screen while the round is open and again on the results screen after. The
    same asymmetry BECSR's RW-53 records, reached from the same argument.

    ``None`` when there is no anchor: with nothing authored and nothing sold,
    there is no floor to fall to and the row is left alone.
    """
    if band is None or band.get('min') is None:
        return None
    return band['min']


# ---------------------------------------------------------------------------
# Participant-facing wording, chosen in ONE place
# ---------------------------------------------------------------------------
#
# The message keys live in the bilingual catalogue
# (``core/utils/participant_messages.py``); which key applies to which state is
# decided here, so a surface cannot describe the band differently by choosing a
# different sentence for the same condition.

def _fmt_money(value):
    return f'${float(value):,.0f}'


def alert_for(submitted, band, *, product_name, market_name, language='en'):
    """The alert a team sees while the round is open, or ``None`` if in band.

    ``submitted`` of ``None`` means no price was entered for a product-market
    the team is active in — the blank case, which warns that the floor will be
    applied.
    """
    from core.utils.participant_messages import participant_message
    if band is None or band.get('min') is None:
        return None

    if submitted is None:
        return participant_message(
            'price_blank_alert', language=language,
            product=product_name, market=market_name,
            floor=_fmt_money(band['min']),
            minimum=_fmt_money(band['min']), maximum=_fmt_money(band['max']))

    status = evaluate(submitted, band)
    if status in (IN_BAND, NO_ANCHOR):
        return None
    return participant_message(
        'price_band_alert', language=language,
        product=product_name, market=market_name,
        submitted=_fmt_money(submitted),
        minimum=_fmt_money(band['min']), maximum=_fmt_money(band['max']))


def adjustment_notice(event_payload, language='en'):
    """How a recorded adjustment reads to the team on its results screen.

    Rendered from the audit payload rather than recomputed, so the sentence a
    team is shown and the row an instructor can produce in a dispute are the
    same fact.
    """
    from core.utils.participant_messages import participant_message
    product = event_payload.get('product_name') or ''
    market = event_payload.get('market_name') or ''
    applied = event_payload.get('applied_price')
    submitted = event_payload.get('submitted_price')
    minimum = event_payload.get('band_min')
    maximum = event_payload.get('band_max')

    if event_payload.get('rule') == RULE_BLANK:
        return participant_message(
            'price_blank_applied', language=language,
            product=product, market=market,
            applied=_fmt_money(applied),
            minimum=_fmt_money(minimum), maximum=_fmt_money(maximum))
    return participant_message(
        'price_band_adjusted', language=language,
        product=product, market=market,
        submitted=_fmt_money(submitted), applied=_fmt_money(applied),
        minimum=_fmt_money(minimum), maximum=_fmt_money(maximum))


def audit_payload(*, team_product, market, band, submitted, applied, rule):
    """The record an adjustment leaves behind.

    Carries the submitted value, the applied value and the rule — the three
    things dispute 2 ("our decision was recorded differently from what we
    entered") has to be answered with — plus the band and the anchor it came
    from, so the answer can be checked rather than merely asserted. Names, not
    ids, because this payload is rendered to the team.
    """
    return {
        'rule': rule,
        'team_product_id': team_product.id,
        'product_name': team_product.name,
        'market_id': market.id,
        'market_name': market.name,
        'submitted_price': None if submitted is None else str(money(submitted)),
        'applied_price': str(money(applied)),
        'band_min': str(band['min']),
        'band_max': str(band['max']),
        'band_pct': band['band_pct'],
        'anchor_price': str(band['anchor']),
        'anchor_source': band['anchor_source'],
        'anchor_round_number': band['anchor_round_number'],
    }
