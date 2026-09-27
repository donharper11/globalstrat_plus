import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import LeaderboardPage from './LeaderboardPage';
import { getLeaderboard, getLeaderboardHistory } from '../api/results';

let mockGameState;

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: key => key }),
}));
jest.mock('../contexts/GameContext', () => ({
  useGame: () => mockGameState,
}));
jest.mock('../api/results', () => ({
  getLeaderboard: jest.fn(),
  getLeaderboardHistory: jest.fn(),
}));
jest.mock('../components/LoadingSpinner', () => () => <div>loading</div>);
jest.mock('../components/RoundSelector', () => ({ currentRound, maxRound }) => (
  <div data-testid="round-selector">{currentRound}/{maxRound}</div>
));
jest.mock('../components/design-system', () => ({
  PageHeader: ({ subtitle, actions }) => <header>{subtitle}{actions}</header>,
  PanelCard: ({ children }) => <section>{children}</section>,
}));
jest.mock('recharts', () => ({
  LineChart: ({ children }) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
}));

beforeEach(() => {
  mockGameState = {
    gameId: 7, teamId: 3, currentRound: undefined, roundStatus: undefined,
  };
  getLeaderboard.mockResolvedValue({ data: { rankings: [] } });
  getLeaderboardHistory.mockResolvedValue({ data: { rounds: [], teams: [] } });
});

afterEach(() => jest.clearAllMocks());

test('waits for game state, then opens on the latest processed round', async () => {
  const { rerender } = render(<LeaderboardPage />);

  expect(screen.getByText('loading')).toBeInTheDocument();
  expect(getLeaderboard).not.toHaveBeenCalled();

  mockGameState = {
    gameId: 7, teamId: 3, currentRound: 9, roundStatus: 'open',
  };
  rerender(<LeaderboardPage />);

  await waitFor(() => expect(getLeaderboard).toHaveBeenCalledWith(7, 8));
  expect(await screen.findByTestId('round-selector')).toHaveTextContent('8/8');
  expect(screen.getByText(/common.round 8/)).toBeInTheDocument();
});

test('a processed current round is itself the latest available round', async () => {
  mockGameState = {
    gameId: 7, teamId: 3, currentRound: 9, roundStatus: 'processed',
  };

  render(<LeaderboardPage />);

  await waitFor(() => expect(getLeaderboard).toHaveBeenCalledWith(7, 9));
  expect(await screen.findByTestId('round-selector')).toHaveTextContent('9/9');
});
