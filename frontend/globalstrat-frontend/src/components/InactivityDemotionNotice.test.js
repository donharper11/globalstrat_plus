import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import InactivityDemotionNotice from './InactivityDemotionNotice';

/**
 * R35. The demoted team is told on its own results screen.
 *
 * The same shape as `PriceAdjustmentNotice.test.js`, and for the same reason:
 * the sentence is the SERVER'S and is asserted verbatim. A screen that
 * restated the ranking rule in its own words would be a second place the rule
 * is worded, which is the defect CRV2-12's standard exists to prevent.
 *
 * i18n is not initialised under test, so the heading is its translation key.
 */

const demotion = (overrides = {}) => ({
  rule: 'inactivity.ranked_below_every_active_firm',
  rank: 4,
  performance_index: '89.96',
  outscored_a_firm_ranked_above: true,
  message: 'Your firm sold nothing in round 1, so it did not compete this '
    + 'round. A firm that does not compete is placed below every firm that '
    + 'did, whatever its score — so your firm was ranked 4 in this round’s '
    + 'standings with a performance index of 89.96, below firms whose index '
    + 'was lower than yours. The index itself was not reduced; only the '
    + 'placing. Sell in at least one market next round to be ranked on your '
    + 'score again.',
  ...overrides,
});

test('the demotion the round recorded is shown, in the server’s wording', () => {
  render(<InactivityDemotionNotice notices={[demotion()]} />);

  expect(screen.getByText(/placed below every firm that did/))
    .toBeInTheDocument();
  expect(screen.getByText(/below firms whose index was lower than yours/))
    .toBeInTheDocument();
  expect(screen.getByText('results_page.inactivity_demotion'))
    .toBeInTheDocument();
});

test('a round with no demotion renders nothing at all', () => {
  const { container } = render(<InactivityDemotionNotice notices={[]} />);
  expect(container).toBeEmptyDOMElement();
});

test('a missing notices payload is treated as none, not as an error', () => {
  const { container } = render(<InactivityDemotionNotice notices={undefined} />);
  expect(container).toBeEmptyDOMElement();
});
