import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import SummaryPage from './SummaryPage';
import { getDecisionSummary } from '../api/decisions';
import { OPTIONAL_SENTENCE, summaryPayload } from './SummaryPage.test';

/**
 * W-CE-16 (the Summary checklist): with `t` printing its key, any run of
 * English words left on the rendered page was written in the component.
 * The server's own sentence is the one thing allowed through.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('react-router-dom', () => ({ useNavigate: () => jest.fn() }));
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

test('a Chinese reader is shown nothing written in English in the component', async () => {
  getDecisionSummary.mockResolvedValue(summaryPayload());
  const { container } = render(<SummaryPage />);
  await screen.findByText('summary_page.title');
  const text = container.textContent.split(OPTIONAL_SENTENCE).join(' ');
  // Three or more English words in a row: a sentence, not a key or a number.
  expect(text.match(/\b[A-Za-z]+(?: [A-Za-z]+){2,}\b/g) || []).toEqual([]);
  ['Sourcing', 'Logistics', 'Trade Finance', 'Inventory', 'Not started',
    'Complete', 'Fix in', 'to complete this requirement', 'draft work saved',
    'Finish the blocked items'].forEach((literal) => {
    expect(text).not.toContain(literal);
  });
});
