import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AskAnalystTab } from './MarketResearchPage';
import client from '../api/client';

/**
 * V2-094. An analyst question is charged per question, and the tab asked for
 * the money without ever naming the figure: no payload it loaded carried a
 * price. `research/queries/` now publishes `analyst_query` from the same
 * calculator the charge reads, and these tests pin what the tab does with it.
 *
 * The rule under test is "price shown before buying", so it has a second half:
 * when the price is NOT known the tab must not sell. A page that falls back to
 * an unpriced Ask button has restored the defect on the first failed fetch.
 *
 * `t` is stubbed to print its key and its interpolation values, so a test can
 * see that the server's figure -- not a constant -- reached the sentence.
 */

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));
jest.mock('../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn() },
}));
jest.mock('../api/decisions', () => ({
  getResearchReport: jest.fn(),
  purchaseResearchReport: jest.fn(),
}));
const mockRefreshBudgets = jest.fn();
jest.mock('../contexts/GameContext', () => ({
  useGame: () => ({ gameId: 1, teamId: 2, refreshBudgets: mockRefreshBudgets }),
}));

const props = { gameId: 1, teamId: 2, currentRound: 3 };

const queriesPayload = (overrides = {}) => ({
  data: {
    round_number: 3,
    queries: [],
    query_count: 0,
    analyst_query: {
      price: '12345', max_queries_per_round: 3, queries_remaining: 3,
    },
    ...overrides,
  },
});

afterEach(() => jest.clearAllMocks());

test('the server’s price is on the screen before anything is asked', async () => {
  client.get.mockResolvedValue(queriesPayload());
  render(<AskAnalystTab {...props} />);

  // The sentence carries the server's figure...
  expect(await screen.findByText(/market_research\.price_per_query.*\$12,345/))
    .toBeInTheDocument();
  // ...and so does the button that spends it.
  expect(screen.getByRole('button', { name: /\$12,345/ })).toBeInTheDocument();
  expect(client.post).not.toHaveBeenCalled();
});

test('the quota shown is the server’s, not a constant', async () => {
  client.get.mockResolvedValue(queriesPayload());
  render(<AskAnalystTab {...props} />);

  expect(await screen.findByText(/ai_analyst_desc.*"max":3/)).toBeInTheDocument();
  expect(screen.getByText(/0 \/ 3/)).toBeInTheDocument();
});

test('with no price from the server, the tab says so and does not sell', async () => {
  // An older backend, or a payload that lost the block.
  client.get.mockResolvedValue(queriesPayload({ analyst_query: undefined }));
  render(<AskAnalystTab {...props} />);

  expect(await screen.findByText('market_research.price_unavailable'))
    .toBeInTheDocument();
  const textarea = screen.getByRole('textbox');
  expect(textarea).toBeDisabled();
  expect(screen.getByRole('button', { name: /market_research\.ask/ }))
    .toBeDisabled();
  expect(client.post).not.toHaveBeenCalled();
});

test('a failed load does not leave an unpriced Ask button behind', async () => {
  client.get.mockRejectedValue(new Error('network'));
  render(<AskAnalystTab {...props} />);

  expect(await screen.findByText('market_research.price_unavailable'))
    .toBeInTheDocument();
  expect(screen.getByRole('button', { name: /market_research\.ask/ }))
    .toBeDisabled();
});

test('asking spends money, so the committed-spend figures are refreshed', async () => {
  client.get.mockResolvedValue(queriesPayload());
  client.post.mockResolvedValue({ data: { response: 'An answer.' } });
  render(<AskAnalystTab {...props} />);

  const textarea = await screen.findByRole('textbox');
  fireEvent.change(textarea, { target: { value: 'How large is the market?' } });
  fireEvent.click(screen.getByRole('button', { name: /\$12,345/ }));

  await waitFor(() => expect(client.post).toHaveBeenCalledTimes(1));
  // The server reads `query` (rag/views.py). The tab used to send
  // `query_text`, so every question was refused 400 "Query text is required"
  // and the analyst could not be asked from the screen at all.
  expect(client.post.mock.calls[0][1]).toEqual({ query: 'How large is the market?' });
  await waitFor(() => expect(mockRefreshBudgets).toHaveBeenCalled());
  expect(await screen.findByText(/1 \/ 3/)).toBeInTheDocument();
});
