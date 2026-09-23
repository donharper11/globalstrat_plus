import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import CorporateStrategyPage from './CorporateStrategyPage';
import { getStrategyContext, getTalentContext, getTalentAllocationContext,
  getGovernanceContext, getOrgStructureContext, patchDecision } from '../api/decisions';

/**
 * W-CE2-02, the M&A half. A queued acquisition could be added and never
 * taken back: the Acquire button turned into a disabled "Queued" label and
 * no screen offered a cancel. The card also offered "Acquire -- $25.0M" to a
 * team holding $23.4M, and the lock then refused the whole submission for
 * exactly that money -- a blocker the team had no way to clear. All three
 * teams ended rounds 3 and 4 unable to lock.
 *
 * The decision rows are drafts until the lock and the acquisitions save
 * replaces the whole section, so withdrawing is the same save with the
 * target left out; what can be funded is read from the calculator the lock
 * refuses on, published as `affordability` on the strategy context.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('../api/decisions', () => ({
  getStrategyContext: jest.fn(),
  getTalentContext: jest.fn(),
  getTalentAllocationContext: jest.fn(),
  getGovernanceContext: jest.fn(),
  getOrgStructureContext: jest.fn(),
  switchOrgStructure: jest.fn(),
  patchDecision: jest.fn(),
}));
jest.mock('react-router-dom', () => ({ useNavigate: () => jest.fn() }));
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({ gameId: 1, teamId: 1, currentRound: 3, refreshBudgets: jest.fn() }),
}));
jest.mock('../AuthContext', () => ({ useAuth: () => ({ user: { id: 1 } }) }));

const mockDraft = { current: {} };
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: mockDraft.current, locked: false }),
  describeRefusal: () => [],
}));
jest.mock('../components/TeamActivityBanner', () => () => null);

const TARGET = {
  id: 7, target_name: 'AfriConnect Mobile', description: 'd',
  market_id: 2, market_name: 'Africa',
  base_acquisition_cost: 25000000, market_share_gained: 0.05,
  includes_plant: true, plant_capacity: 3000,
  includes_distribution: false, distribution_reach_bonus: 0,
  talent_bonus: null, min_round_available: 1, requires_market_presence: true,
  integration_rounds: 2, integration_cost_per_round: 500000,
  available: true, locked_reasons: [],
  acquired_by_team: null, acquired_by_self: false,
};

const strategyContext = (affordability) => ({
  data: {
    markets: [], partnerships: [], plants: [], entry_modes: [],
    strategy_options: [],
    financial: { cash_on_hand: 23400000, total_debt: 0, total_equity: 1, shares_outstanding: 1 },
    strategy_budget_remaining: 0,
    affordability,
    acquisition_targets: [TARGET],
    team_acquisitions: [],
  },
});

beforeEach(() => {
  mockDraft.current = {};
  getStrategyContext.mockResolvedValue(strategyContext(
    { cash_on_hand: 30000000, committed_total: 0, unallocated: 30000000 }));
  getTalentContext.mockResolvedValue({ data: {} });
  getTalentAllocationContext.mockResolvedValue({ data: {} });
  getGovernanceContext.mockResolvedValue({ data: {} });
  getOrgStructureContext.mockResolvedValue({ data: {} });
  patchDecision.mockResolvedValue({ data: {} });
});
afterEach(() => jest.clearAllMocks());

const openMnA = async () => {
  render(<CorporateStrategyPage />);
  fireEvent.click(await screen.findByText('corporate_strategy.ma'));
  expect(await screen.findByText('AfriConnect Mobile')).toBeInTheDocument();
};

test('a queued acquisition can be withdrawn, and the save drops it', async () => {
  mockDraft.current = { acquisitions: [{ acquisition_target: 7 }] };
  await openMnA();

  const withdraw = screen.getByRole('button', { name: 'corporate_strategy.withdraw' });
  expect(withdraw).toBeEnabled();
  fireEvent.click(withdraw);

  // The section autosave debounces by two seconds.
  await waitFor(() => expect(patchDecision).toHaveBeenCalled(), { timeout: 5000 });
  const [, , , section, body] = patchDecision.mock.calls[0];
  expect(section).toBe('acquisitions');
  expect(body).toEqual({ acquisitions: [] });
});

test('a target the team cannot fund is not offered, and the reason says so', async () => {
  // The walkthrough's figures: $23.4M of cash against a $25.0M target.
  getStrategyContext.mockResolvedValue(strategyContext(
    { cash_on_hand: 23400000, committed_total: 0, unallocated: 23400000 }));
  await openMnA();

  const acquire = screen.getByRole('button', { name: /corporate_strategy.acquire/ });
  expect(acquire).toBeDisabled();
  expect(screen.getByText(/corporate_strategy.not_affordable/)).toBeInTheDocument();
  fireEvent.click(acquire);
  expect(patchDecision).not.toHaveBeenCalled();
});

test('a target the team can fund is still offered and still queues', async () => {
  await openMnA();

  const acquire = screen.getByRole('button', { name: /corporate_strategy.acquire/ });
  expect(acquire).toBeEnabled();
  fireEvent.click(acquire);

  // The section autosave debounces by two seconds.
  await waitFor(() => expect(patchDecision).toHaveBeenCalled(), { timeout: 5000 });
  expect(patchDecision.mock.calls[0][4]).toEqual(
    { acquisitions: [{ acquisition_target: 7 }] });
});
