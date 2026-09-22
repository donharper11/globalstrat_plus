import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import MarketingPage from './MarketingPage';
import { getMarketingContext, patchDecision } from '../api/decisions';

/**
 * W-CE-04. A refused marketing save was announced twice -- once by the
 * shared "Your last change was not saved" notice (DecisionSaveAlert, fed by
 * the axios interceptor for every decision write) and once more by this
 * page's own banner -- and neither named the product or market the server
 * objected to.
 *
 * The server now names the row (core.tests.test_marketing_refusal_names_row)
 * and the page no longer repeats the shared notice: the refusal is shown
 * once, by the surface every decision page shares. The page still reacts to
 * it -- the price hint says the entry is unsaved rather than saved.
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
const mockRefreshBudgets = jest.fn(() => Promise.resolve());
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({
    gameId: 1, teamId: 1, currentRound: 1, refreshBudgets: mockRefreshBudgets,
  }),
}));
const mockDraft = { marketing_decisions: [] };
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: mockDraft, locked: false }),
}));
jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { user_id: 4 } }),
}));
jest.mock('../components/TeamActivityBanner', () => () => null);
jest.mock('../hooks/useUnsavedChangesGuard', () => () => {});

const SENTENCE = 'Nexus One in North America: Choose one to three campaign focus features.';

const marketingContext = () => ({
  data: {
    product_markets: [{
      product_id: 1, product_name: 'Nexus One', positioning: 'mainstream',
      platform_name: 'Atlas',
      markets: [{ market_id: 1, market__name: 'North America' }],
      feature_levels: [{ feature_id: 1, feature__name: 'Battery', current_level: 3 }],
    }],
    production_capacity: [{
      market_id: 1, market_name: 'North America', own_capacity: 10000,
      contract_mfg_capacity: 0, contract_mfg_available: false,
      contract_mfg_cost_multiplier: 1.25,
    }],
    features: [{ feature_id: 1, feature__name: 'Battery' }],
    marketing_budget_remaining: 2500000,
    sales_rep_cost_per_round: 100000,
    prev_round_decisions: {},
    price_bands: { '1_1': { min: 315, max: 585 } },
  },
});

beforeEach(() => {
  getMarketingContext.mockResolvedValue(marketingContext());
});
afterEach(() => jest.clearAllMocks());

const refusal = () => {
  const err = new Error('Request failed with status code 400');
  err.response = { status: 400, data: { marketing_decisions: [SENTENCE] } };
  return err;
};

test('a refused save is left to the shared notice, and the page marks the entry unsaved', async () => {
  patchDecision.mockRejectedValue(refusal());
  render(<MarketingPage />);
  expect(await screen.findByText('marketing.title')).toBeInTheDocument();

  // An out-of-band price, typed: the hint says the entry is saved -- until
  // the server refuses the save.
  const price = screen.getAllByRole('spinbutton')[0];
  fireEvent.change(price, { target: { value: '1755' } });
  expect(screen.getByText('marketing.price_out_of_band')).toBeInTheDocument();

  // The page's own autosave timer (2 s) sends the row; the server refuses.
  await waitFor(() => expect(patchDecision).toHaveBeenCalled(), { timeout: 4000 });
  await screen.findByText('marketing.price_out_of_band_unsaved', {}, { timeout: 2000 });

  // The shared DecisionSaveAlert (mounted in the shell, above every decision
  // page) carries the server's sentence. The page does not repeat it.
  expect(screen.queryByText('marketing.save_failed_title')).not.toBeInTheDocument();
  expect(screen.queryByText(SENTENCE)).not.toBeInTheDocument();
});
