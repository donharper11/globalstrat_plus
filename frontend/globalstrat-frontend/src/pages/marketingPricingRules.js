/**
 * The two pricing-surface decisions that are rules, not layout.
 *
 * They live in their own module so they can be asserted directly. Both were
 * defects found by the GSP-CRV2-13 browser pass, and both are the kind of rule
 * that is cheap to get wrong again in a re-layout.
 */

/**
 * Whether a marketing row must be included in the PATCH the screen sends.
 *
 * The rule has two halves and the old predicate had only one of them.
 *
 * Send it when the team has engaged with it, even if every number on it is now
 * empty. R15 and R24 require an explicitly blank price on a present row to
 * reach the server: it is filled at the band floor at the deadline when the
 * product sold here last round, and marked not-for-sale when it did not.
 * Dropping such a row instead deleted the decision with no floor, no audit
 * event and no notice -- the silent vanish R24 exists to prevent (F2).
 *
 * Do NOT send a row the team has never engaged with. R15 is explicit that the
 * floor must never reach a product-market the team never marketed: a
 * fabricated floor-priced row would enter the demand denominator at a very
 * competitive price, take share from every rival and then sell nothing,
 * penalising rivals for another team's inaction.
 */
export const isRowEngaged = (d) => !!(
  d.persisted
  || d.touched
  || d.retail_price > 0
  || d.production_volume > 0
  || d.promotion_budget > 0
);

/**
 * Which sentence a blank price gets, decided by the anchor the server supplied.
 *
 * The floor reaches only a product with a real prior-round price
 * (`previous_round`). On any other anchor `price_band.blank_price()` returns
 * None by design and the product is simply not offered for sale, so promising
 * "it will be priced at $X" states the opposite of the rule that will run (F1).
 */
export const blankPriceMessageKey = (band) => (
  band && band.anchor_source === 'previous_round'
    ? 'marketing.price_blank'
    : 'marketing.price_blank_not_for_sale'
);
