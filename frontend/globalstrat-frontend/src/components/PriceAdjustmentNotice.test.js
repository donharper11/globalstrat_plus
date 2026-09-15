import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import PriceAdjustmentNotice from './PriceAdjustmentNotice';

/**
 * F3. The notice itself was never the defect -- it had no screen a student
 * could reach. These assertions pin the rendering the routes now lead to.
 *
 * i18n is not initialised under test, so the heading is its translation key.
 * The adjustment sentences are the SERVER'S wording and are asserted verbatim,
 * which is the point: the screen must not restate the rule in its own words.
 */

const adjustment = (overrides = {}) => ({
  product_name: 'Nexus One',
  market: 'North America',
  submitted_price: null,
  applied_price: '315.00',
  rule: 'price_band.blank_priced_at_band_floor',
  message: 'Nexus One in North America: no price was entered, so it was priced '
    + 'at $315 when the round closed — the lowest price allowed this round, '
    + 'whose range was $315 to $585.',
  ...overrides,
});

test('every adjustment the round recorded is shown, in the server’s wording', () => {
  const notOffered = adjustment({
    product_name: 'Aurora NX',
    rule: 'price_band.not_offered',
    applied_price: null,
    message: 'Aurora NX in North America: no unit price was set and there was '
      + 'no previous price to fall back on, so it was not offered for sale '
      + 'this round and sold nothing. Set a unit price to put it back on the '
      + 'market.',
  });

  render(<PriceAdjustmentNotice adjustments={[adjustment(), notOffered]} />);

  expect(screen.getByText(/no price was entered, so it was priced at \$315/))
    .toBeInTheDocument();
  expect(screen.getByText(/was not offered for sale this round and sold nothing/))
    .toBeInTheDocument();
  expect(screen.getByText('results_page.price_adjustments')).toBeInTheDocument();
});

test('a round with no adjustments renders nothing at all', () => {
  const { container } = render(<PriceAdjustmentNotice adjustments={[]} />);
  expect(container).toBeEmptyDOMElement();
});

test('a missing adjustments payload is treated as none, not as an error', () => {
  const { container } = render(<PriceAdjustmentNotice adjustments={undefined} />);
  expect(container).toBeEmptyDOMElement();
});
