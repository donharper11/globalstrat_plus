import { isRowEngaged, blankPriceMessageKey } from './marketingPricingRules';

/**
 * Each test names the finding it covers and fails without the repair.
 */

const row = (overrides = {}) => ({
  team_product: 1,
  market: 1,
  retail_price: null,
  promotion_budget: 0,
  production_volume: 0,
  persisted: false,
  touched: false,
  ...overrides,
});

describe('which marketing rows are submitted (F2, F7, R15, R24)', () => {
  test('a row the team never touched is NOT submitted', () => {
    // R15: the floor must never reach a product-market the team never
    // marketed. A fabricated row would take demand from every rival and then
    // sell nothing.
    expect(isRowEngaged(row())).toBe(false);
  });

  test('a row already on the server is submitted even when fully cleared', () => {
    // F2: the defect. Price cleared, no production, no promotion — the old
    // predicate dropped this from the payload, and the PATCH replaces every
    // row, so the decision was deleted with no floor, no audit event and no
    // notice.
    expect(isRowEngaged(row({ persisted: true }))).toBe(true);
  });

  test('a row the team is filling in is submitted before it has any spend', () => {
    // F7: typing a price is the obvious first action, and it must reach the
    // server.
    expect(isRowEngaged(row({ touched: true }))).toBe(true);
  });

  test('a blank price on an engaged row is still submitted as blank', () => {
    // R24: "submitted blank" has to be representable, or the not-for-sale
    // branch has nothing to act on.
    const cleared = row({ persisted: true, retail_price: null });
    expect(isRowEngaged(cleared)).toBe(true);
  });

  test('any priced or funded row is submitted', () => {
    expect(isRowEngaged(row({ retail_price: 400 }))).toBe(true);
    expect(isRowEngaged(row({ production_volume: 5000 }))).toBe(true);
    expect(isRowEngaged(row({ promotion_budget: 10000 }))).toBe(true);
  });
});

describe('what a blank price is promised (F1, R15, R24)', () => {
  test('a product that sold here last round is promised the band floor', () => {
    expect(blankPriceMessageKey({ anchor_source: 'previous_round', min: 315 }))
      .toBe('marketing.price_blank');
  });

  test('a positioning-reference anchor is told it will NOT be sold', () => {
    // F1: the defect. The screen read "it will be priced at $490" while
    // blank_price() returns None for this anchor and the product is not
    // offered for sale at all.
    expect(blankPriceMessageKey({ anchor_source: 'positioning_reference', min: 490 }))
      .toBe('marketing.price_blank_not_for_sale');
  });

  test('an absent or anchorless band never promises a floor', () => {
    expect(blankPriceMessageKey(undefined))
      .toBe('marketing.price_blank_not_for_sale');
    expect(blankPriceMessageKey({ anchor_source: 'none' }))
      .toBe('marketing.price_blank_not_for_sale');
  });
});
