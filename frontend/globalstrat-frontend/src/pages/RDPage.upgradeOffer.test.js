import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import RDPage from './RDPage';
import { getRDContext, patchDecision } from '../api/decisions';

/**
 * W-CE-03. The R&D page offered "Invest next level" on every feature below
 * its ceiling, and its own guidance said to upgrade a feature when a new
 * platform is over budget -- while the server refuses every feature-level
 * R&D row (R10, `rd_investment_retired`). Five buttons, five refusals.
 *
 * The page offers only what the server will accept: the context endpoint
 * says feature-level investment is unavailable and why, in the reader's
 * language, and the page shows that sentence where the offer used to be.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('../api/decisions', () => ({
  getRDContext: jest.fn(),
  patchDecision: jest.fn(),
}));
const mockRefreshBudgets = jest.fn();
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({
    gameId: 1, teamId: 1, currentRound: 1, refreshBudgets: mockRefreshBudgets,
  }),
}));
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: {}, locked: false }),
  describeRefusal: () => [],
}));

const RETIRED = 'Feature-level R&D investment is no longer available. '
  + 'Develop a new platform and move the product to it to improve the product.';

const rdContext = (overrides = {}) => ({
  data: {
    owned_platforms: [{
      id: 1, platform_name: 'Atlas', generation_name: 'Gen 1', status: 'active',
      generation_order: 1,
      features: [
        { feature_id: 4, name: 'Battery', code: 'battery', current_level: 3, ceiling: 9,
          cost_schedule: [{ level: 4, incremental_cost: 650000, cumulative_cost: 650000 }] },
        { feature_id: 5, name: 'Display', code: 'display', current_level: 2, ceiling: 9,
          cost_schedule: [{ level: 3, incremental_cost: 400000, cumulative_cost: 400000 }] },
      ],
    }],
    locked_features: [],
    upgrade_options: [],
    available_generations: [],
    platform_dev_decisions: [],
    investment_slots: { max: 5, used: 0, remaining: 5 },
    max_platform_features: 5,
    current_investments: [],
    rd_budget: 4000000,
    rd_budget_remaining: 4000000,
    rd_spent: 0,
    budget_source: 'x',
    pending_feature_gains: [],
    feature_investment: { available: false, reason: RETIRED },
    ...overrides,
  },
});

beforeEach(() => {
  getRDContext.mockResolvedValue(rdContext());
  patchDecision.mockResolvedValue({ data: {} });
});
afterEach(() => jest.clearAllMocks());

test('no feature-level upgrade is offered, and the server\'s reason is shown instead', async () => {
  render(<RDPage />);
  expect(await screen.findByText('rd.title')).toBeInTheDocument();

  expect(screen.queryByRole('button', { name: /invest next level/i })).not.toBeInTheDocument();
  expect(screen.queryByText('rd.platform_upgrade')).not.toBeInTheDocument();
  expect(screen.queryByText(/upgrade an existing feature/i)).not.toBeInTheDocument();
  expect(screen.getByText(RETIRED)).toBeInTheDocument();
  expect(patchDecision).not.toHaveBeenCalled();
});

test('a feature row names its level and ceiling but prices no next level', async () => {
  render(<RDPage />);
  expect(await screen.findByText('rd.title')).toBeInTheDocument();
  // Expand the owned platform's row to its feature list.
  fireEvent.click(screen.getByText('Atlas'));
  // The feature is named in the column header and again in the expanded row.
  expect((await screen.findAllByText('Battery')).length).toBeGreaterThanOrEqual(2);
  expect(screen.queryByText(/rd\.next_level/)).not.toBeInTheDocument();
});

test('an older server that says nothing about feature investment still offers no upgrade', async () => {
  getRDContext.mockResolvedValue(rdContext({ feature_investment: undefined }));
  render(<RDPage />);
  expect(await screen.findByText('rd.title')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /invest next level/i })).not.toBeInTheDocument();
});
