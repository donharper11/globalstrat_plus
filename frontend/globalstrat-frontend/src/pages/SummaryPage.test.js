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
  initReactI18next: { type: '3rdParty', init: () => {} },
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

describe('queued-acquisition affordability guidance', () => {
  const guidance = {
    en: 'Committed spend of $29,820,000.00 exceeds available funds of $28,994,307.21 — $28,994,307.21 of cash plus $0.00 of financing decided this round. Cut $825,692.79: your largest reducible commitment is the queued acquisition (withdraw it in Corporate Strategy → M&A) at $18,000,000.00. A queued acquisition is not eligible for financing before it is fulfilled.',
    zh: '承诺支出 $29,820,000.00 超过可用资金 $28,994,307.21——现金 $28,994,307.21 加上本回合已决定的融资 $0.00。需要削减 $825,692.79：目前可削减的最大承诺是已排队的收购（前往“公司战略”→“并购”撤回），金额 $18,000,000.00。排队中的收购在完成前不属于可融资用途。',
  };

  test.each(Object.values(guidance))(
    'renders the bilingual server guidance verbatim: %s',
    async (message) => {
      getDecisionSummary.mockResolvedValue(summaryPayload({
        lock_blockers: [message],
        categories: {
          ...summaryPayload().data.categories,
          budget: { status: 'error', errors: [message], warnings: [] },
        },
      }));
      render(<SummaryPage />);
      await screen.findByText('summary_page.title');
      expect(screen.getAllByText(message).length).toBeGreaterThan(0);
      expect(screen.queryByText(/strategy budget at \$23,250,000\.00/))
        .not.toBeInTheDocument();
      expect(screen.queryByText(/战略预算，金额 \$23,250,000\.00/))
        .not.toBeInTheDocument();
    },
  );
});
