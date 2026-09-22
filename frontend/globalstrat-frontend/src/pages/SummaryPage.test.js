import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import SummaryPage from './SummaryPage';
import { getDecisionSummary } from '../api/decisions';

/**
 * The Decision Summary after the 2026-09-22 walkthrough.
 *
 * W-CE-13: Sourcing, Logistics, Trade Finance and Inventory were listed with
 * 'Fix in ...' and 'Open Sourcing to complete this requirement' although the
 * lock never required them. The server now marks them optional and says so;
 * the page shows that sentence and no Fix button for them.
 *
 * `t` is stubbed to print its key, so an assertion names the catalogue key and
 * any English left on the page is English written in the component.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({ useNavigate: () => mockNavigate }));
jest.mock('../api/decisions', () => ({
  getDecisionSummary: jest.fn(),
  lockDecisions: jest.fn(),
  saveDecisions: jest.fn(),
}));
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({ gameId: 1, teamId: 2, currentRound: 3 }),
}));
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: { team_notes: '' }, locked: false, setLocked: jest.fn() }),
}));
jest.mock('../components/BudgetBar', () => () => null);

export const OPTIONAL_SENTENCE = 'Optional this round. Locking your decisions does not require it.';

export const summaryPayload = (overrides = {}) => ({
  data: {
    submission_status: 'draft',
    can_lock: false,
    lock_blockers: [],
    budget_summary: {},
    categories: {
      budget: { status: 'configured', warnings: [] },
      rd: { status: 'empty', warnings: [] },
      products: { status: 'empty', warnings: [] },
      marketing: { status: 'configured', warnings: [] },
      strategy: { status: 'configured', warnings: [] },
      financing: { status: 'configured', warnings: [], optional: true },
      sourcing: { status: 'empty', warnings: [OPTIONAL_SENTENCE], optional: true },
      logistics: { status: 'empty', warnings: [OPTIONAL_SENTENCE], optional: true },
      trade_finance: { status: 'configured', warnings: [], optional: true },
      inventory: { status: 'empty', warnings: [OPTIONAL_SENTENCE], optional: true },
    },
    ...overrides,
  },
});

/** The "Fix in <section>" buttons, however the label is spelled. */
const fixButtons = () => screen.getAllByRole('button')
  .filter((b) => /^Fix in |summary_page\.fix_in/.test(b.textContent));

afterEach(() => jest.clearAllMocks());

describe('W-CE-13: the supply-chain sections are not lock requirements', () => {
  test('an optional section carries the server’s sentence and no Fix button', async () => {
    getDecisionSummary.mockResolvedValue(summaryPayload());
    render(<SummaryPage />);
    await screen.findByText('summary_page.title');

    expect(screen.getAllByText(OPTIONAL_SENTENCE)).toHaveLength(3);
    // Only the two required sections that are not configured: R&D and products.
    expect(fixButtons()).toHaveLength(2);
    expect(fixButtons().map((b) => b.textContent).join(' '))
      .not.toMatch(/sourcing|logistics|trade.?finance|inventory/i);
    expect(screen.queryByText(/Open (Sourcing|Logistics|Trade Finance|Inventory) to complete/))
      .not.toBeInTheDocument();
  });

  test('an optional section that is not started is tagged optional, not "not started"', async () => {
    getDecisionSummary.mockResolvedValue(summaryPayload());
    render(<SummaryPage />);
    await screen.findByText('summary_page.title');
    expect(screen.getAllByText('summary_page.optional')).toHaveLength(3);
  });

  test('a required section that is not started still has its Fix button', async () => {
    getDecisionSummary.mockResolvedValue(summaryPayload());
    render(<SummaryPage />);
    await screen.findByText('summary_page.title');
    expect(fixButtons().some((b) => /product_portfolio|Product Portfolio/.test(b.textContent)))
      .toBe(true);
  });
});
