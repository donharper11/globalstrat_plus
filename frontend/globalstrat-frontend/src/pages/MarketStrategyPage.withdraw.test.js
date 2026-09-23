import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import MarketStrategyPage from './MarketStrategyPage';
import { getStrategyContext, getComplianceContext, getMarketLocalization,
  getAllianceState, patchDecision } from '../api/decisions';

/**
 * W-CE2-02, the Market Strategy half, and the second half of W-CE2-01.
 *
 * The Production Capacity card read `context.plants` -- plants the team
 * OWNS -- so a plant build queued this round was invisible and the Build
 * Plant button stayed on the card. Pressing it again stored a second
 * `decision_plant` row for the same market, which breaks the round's input
 * snapshot before Phase 1 begins; and nothing anywhere could take the build
 * back. The Partnerships card listed only *active* partnerships, so a
 * partnership just committed to appeared nowhere and was equally permanent.
 *
 * A queued commitment is now shown where it was made, with a withdraw
 * control (the section save replaces the whole section, so withdrawing is
 * the same save with the row left out), and what the team cannot fund is not
 * offered -- read from `affordability`, which the strategy context publishes
 * from the calculator the lock refuses on.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('../api/decisions', () => ({
  getStrategyContext: jest.fn(),
  getComplianceContext: jest.fn(),
  getMarketLocalization: jest.fn(),
  getAllianceState: jest.fn(),
  patchDecision: jest.fn(),
}));
jest.mock('react-router-dom', () => ({ useNavigate: () => jest.fn() }));
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({ gameId: 1, teamId: 1, currentRound: 3, refreshBudgets: jest.fn() }),
}));

const mockDraft = { current: {} };
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: mockDraft.current, locked: false }),
  describeRefusal: () => [],
}));

const MARKET = {
  id: 2, code: 'AFR', name: 'Africa', is_home_market: false,
  entry_status: 'active', entry_mode: 'Export',
  allows_manufacturing: true, contract_mfg_available: false,
  plant_build_cost: 12000000, plant_build_rounds: 2,
  plant_capacity_units: 5000,
};

const OPTION = {
  id: 9, name: 'Local distributor', category: 'c', code: 'LD',
  capital_cost_base: 4000000, is_reversible: true,
};

const strategyContext = (affordability) => ({
  data: {
    markets: [MARKET], partnerships: [], plants: [], entry_modes: [],
    strategy_options: [OPTION],
    financial: { cash_on_hand: 23400000, total_debt: 0, total_equity: 1, shares_outstanding: 1 },
    strategy_budget_remaining: 0,
    affordability,
    acquisition_targets: [], team_acquisitions: [],
  },
});

beforeEach(() => {
  mockDraft.current = {};
  getStrategyContext.mockResolvedValue(strategyContext(
    { cash_on_hand: 23400000, committed_total: 0, unallocated: 23400000 }));
  getComplianceContext.mockResolvedValue(null);
  getAllianceState.mockResolvedValue(null);
  getMarketLocalization.mockResolvedValue({ data: {} });
  patchDecision.mockResolvedValue({ data: {} });
});
afterEach(() => jest.clearAllMocks());

const open = async () => {
  render(<MarketStrategyPage />);
  expect(await screen.findByText('market_strategy.production_capacity')).toBeInTheDocument();
};

test('a queued plant build is shown, and the Build button is not offered again', async () => {
  mockDraft.current = {
    plant_decisions: [{ market: 2, action: 'build', capacity_units: 0, contract_mfg_volume: 0 }],
  };
  await open();

  expect(screen.getByText('market_strategy.plant_queued')).toBeInTheDocument();
  expect(screen.queryByText('market_strategy.no_plant —')).not.toBeInTheDocument();
});

test('a queued plant build can be withdrawn, and the save drops it', async () => {
  mockDraft.current = {
    plant_decisions: [{ market: 2, action: 'build', capacity_units: 0, contract_mfg_volume: 0 }],
  };
  await open();

  fireEvent.click(screen.getByRole('button', { name: 'market_strategy.withdraw' }));

  // The section autosave debounces by two seconds.
  await waitFor(() => expect(patchDecision).toHaveBeenCalled(), { timeout: 5000 });
  const [, , , section, body] = patchDecision.mock.calls[0];
  expect(section).toBe('plants');
  expect(body).toEqual({ plant_decisions: [] });
});

test('a plant the team cannot fund is not offered', async () => {
  getStrategyContext.mockResolvedValue(strategyContext(
    { cash_on_hand: 23400000, committed_total: 20000000, unallocated: 3400000 }));
  await open();

  const build = screen.getByRole(
    'button', { name: /market_strategy.build_plant/ });
  expect(build).toBeDisabled();
  expect(screen.getByText(/market_strategy.not_affordable/)).toBeInTheDocument();
});

test('a queued partnership is shown and can be withdrawn', async () => {
  mockDraft.current = {
    partnerships: [{
      market: 2, strategy_option: 9, annual_investment: 4000000,
      action: 'establish',
    }],
  };
  await open();

  expect(screen.getByText('market_strategy.queued')).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole(
    'button', { name: 'market_strategy.withdraw' })[0]);

  await waitFor(() => expect(patchDecision).toHaveBeenCalled(), { timeout: 5000 });
  const [, , , section, body] = patchDecision.mock.calls[0];
  expect(section).toBe('partnerships');
  expect(body).toEqual({ partnerships: [] });
});
