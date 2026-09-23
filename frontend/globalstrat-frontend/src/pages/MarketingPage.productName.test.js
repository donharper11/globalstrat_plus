import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import MarketingPage from './MarketingPage';
import { getMarketingContext } from '../api/decisions';

/**
 * W-CE3-05 (third Consumer Electronics walkthrough). The page named the
 * product only in the inner product tab label, and that inner `Tabs` is
 * rendered only when a market holds more than one product. A team with one
 * product in each of two markets saw two tabs named only *Africa (1)* and
 * *North America (1)*, and set a price, a production volume, a campaign
 * focus and a channel split without being told which product it was
 * deciding for.
 *
 * The render is the test rather than a source scan, because the defect is
 * which branch draws the name: a card reached with one product has to carry
 * it, and a market with two has to carry it still.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('../api/decisions', () => ({
  getMarketingContext: jest.fn(),
  patchDecision: jest.fn(),
  getTeamChanges: jest.fn(),
}));
jest.mock('../api/saveFailures', () => ({
  reportUnpublishedFailure: jest.fn(),
}));
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({
    gameId: 1, teamId: 1, currentRound: 1, refreshBudgets: jest.fn(),
  }),
}));
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: { marketing_decisions: [] }, locked: false }),
}));
jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { user_id: 4 } }),
}));
jest.mock('../components/TeamActivityBanner', () => () => null);
jest.mock('../hooks/useUnsavedChangesGuard', () => () => {});

const context = (productMarkets) => ({
  data: {
    product_markets: productMarkets,
    production_capacity: [{
      market_id: 1, market_name: 'North America', own_capacity: 10000,
      contract_mfg_capacity: 0, contract_mfg_available: false,
      contract_mfg_cost_multiplier: 1.25,
    }],
    features: [{ feature_id: 1, feature__name: 'Battery' }],
    marketing_budget_remaining: 2500000,
    sales_rep_cost_per_round: 100000,
    prev_round_decisions: {},
    price_bands: {},
  },
});

const product = (id, name, positioning = 'mainstream') => ({
  product_id: id, product_name: name, positioning,
  platform_name: 'Atlas',
  markets: [{ market_id: 1, market__name: 'North America' }],
  feature_levels: [{ feature_id: 1, feature__name: 'Battery', current_level: 3 }],
});

afterEach(() => jest.clearAllMocks());

test('a market holding exactly one product still names it', async () => {
  getMarketingContext.mockResolvedValue(context([product(1, 'Nexus One')]));

  render(<MarketingPage />);
  expect(await screen.findByText('marketing.title')).toBeInTheDocument();

  expect(screen.getByText('Nexus One')).toBeInTheDocument();
});

test('a market holding two products names the one whose card is open', async () => {
  getMarketingContext.mockResolvedValue(context([
    product(1, 'Nexus One'), product(2, 'Nexus Two', 'premium'),
  ]));

  render(<MarketingPage />);
  expect(await screen.findByText('marketing.title')).toBeInTheDocument();

  // Both are reachable: the tab label names each, and the open card names
  // the one being decided.
  expect(screen.getAllByText('Nexus One').length).toBeGreaterThan(1);
});
