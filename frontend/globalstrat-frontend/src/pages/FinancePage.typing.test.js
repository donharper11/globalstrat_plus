import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import FinancePage from './FinancePage';
import { getFinanceContext, patchDecision, getTaxStructureContext } from '../api/decisions';

/**
 * W-CE-02. Typing `5000000` into Loan Amount stored $5, $0 or $50 depending
 * on cadence; only a pasted value stored 5,000,000.
 *
 * The three tabs were components declared inside FinancePage's render, so
 * every keystroke -- which sets financing state and re-renders the page --
 * produced a NEW component type, and React unmounted the whole tab and
 * mounted it again. The focused InputNumber was destroyed mid-word: the first
 * digit reached the state, the rest went to an input that no longer existed.
 *
 * This drives the real page and the real antd InputNumber one keystroke at a
 * time (keydown, input, keyup -- what a key press is to the component), with
 * the page's own 700 ms autosave timer live, and reads back what was sent.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('../api/decisions', () => ({
  getFinanceContext: jest.fn(),
  patchDecision: jest.fn(),
  getTaxStructureContext: jest.fn(),
  setTaxStructure: jest.fn(),
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
// The provider's `draft` is React state, so its identity is stable between
// renders; the stub must be too, or the page re-reads its context on every
// render and the test would fail for a reason the product does not have.
const mockDraft = {};
jest.mock('../contexts/DecisionContext', () => ({
  useDecisions: () => ({ draft: mockDraft, locked: false }),
}));
jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { user_id: 4, is_instructor: false } }),
}));
jest.mock('../components/TeamActivityBanner', () => () => null);

const financeContext = () => ({
  data: {
    financial: {
      cash_on_hand: 20000000, total_debt: 5000000, total_equity: 30000000,
      shares_outstanding: 1000000,
    },
    capital: {
      financing_draft: {}, interest_rate: 0.06, max_de_ratio: 2.0,
      share_price: 45, last_net_income: 1000000, available_credit: 55000000,
    },
    budget_status: { total_budget_available: 8000000 },
    key_ratios: { debt_to_equity: 0.17 },
  },
});

beforeEach(() => {
  getFinanceContext.mockResolvedValue(financeContext());
  getTaxStructureContext.mockResolvedValue({ data: { current: { code: 'direct' }, structures: [] } });
  patchDecision.mockResolvedValue({ data: {} });
});
afterEach(() => jest.clearAllMocks());

/** The number boxes of the active tab: antd hides the inactive panes. */
const activeInputs = () => screen.getAllByRole('spinbutton');

const openCapitalTab = async () => {
  render(<FinancePage />);
  fireEvent.click(await screen.findByText('finance.capital_management'));
  const loan = activeInputs()[0];
  loan.focus();
  // As the probe did: select the "$ 0" the box starts with and delete it.
  fireEvent.keyDown(loan, { key: 'Backspace' });
  fireEvent.input(loan, { target: { value: '' } });
  fireEvent.keyUp(loan, { key: 'Backspace' });
  return loan;
};

/**
 * Key presses as the component sees them, into `box`, after `already` is in
 * it: keydown, an input event carrying the text so far, keyup.
 */
const pressKeys = (box, text, already = '') => {
  let typed = already;
  text.split('').forEach((ch) => {
    typed += ch;
    fireEvent.keyDown(box, { key: ch });
    fireEvent.input(box, { target: { value: typed } });
    fireEvent.keyUp(box, { key: ch });
  });
};

const lastFinancingSent = () => {
  const calls = patchDecision.mock.calls.filter(c => c[3] === 'financing');
  return calls.length ? calls[calls.length - 1][4].financing : null;
};

test('a loan amount typed key by key is the number typed, in the box and in the save', async () => {
  const loan = await openCapitalTab();

  pressKeys(loan, '5000000');

  // The input the student was typing into is still the one on the page, and
  // still focused: the tab was not torn down under the keyboard.
  expect(document.contains(loan)).toBe(true);
  expect(loan).toHaveFocus();
  expect(activeInputs()[0]).toBe(loan);

  fireEvent.blur(loan);
  expect(activeInputs()[0]).toHaveValue('$ 5,000,000');

  await waitFor(() => expect(lastFinancingSent()).not.toBeNull());
  expect(lastFinancingSent().new_debt).toBe(5000000);
});

test('a slow cadence -- the autosave fires between keystrokes -- still stores the whole number', async () => {
  const loan = await openCapitalTab();

  pressKeys(loan, '6');
  // The page's own autosave timer (700 ms) fires before the next digit.
  await waitFor(() => expect(lastFinancingSent()?.new_debt).toBe(6), { timeout: 2000 });

  pressKeys(loan, '000000', '6');
  expect(loan).toHaveFocus();
  fireEvent.blur(loan);
  expect(activeInputs()[0]).toHaveValue('$ 6,000,000');
  await waitFor(() => expect(lastFinancingSent().new_debt).toBe(6000000), { timeout: 2000 });
});

test('every financing input on the tab keeps its focus across a keystroke', async () => {
  await openCapitalTab();
  const count = activeInputs().length;
  expect(count).toBeGreaterThanOrEqual(3);

  for (let i = 0; i < count; i += 1) {
    const box = activeInputs()[i];
    box.focus();
    pressKeys(box, '1');
    expect(document.contains(box)).toBe(true);
    expect(box).toHaveFocus();
  }
});
