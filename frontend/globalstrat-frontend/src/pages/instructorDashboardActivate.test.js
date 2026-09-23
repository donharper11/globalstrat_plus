import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

// The dashboard reloads several endpoints on activation, so these two drive a
// lot of asynchronous work. Under the full suite's parallel load they exceeded
// Jest's 5 s default and failed while passing alone; the waits themselves are
// bounded by their own `waitFor` timeouts, so this only stops a slow machine
// being read as a broken page.
jest.setTimeout(30000);
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import client from '../api/client';
import InstructorDashboard from './InstructorDashboard';

/**
 * W-CE2-10. The first round-control action after *Activate Game* was always
 * refused -- *The game has moved to round 1; this request was for round 0.
 * Refresh the console and repeat the action if it is still what you want.* --
 * and worked only after a page reload.
 *
 * Cause: `RoundControlCard` reads `/round-control/` once per `gameId` and
 * sends the round it is showing as `expected_round_number`. Activating the
 * game moves it from round 0 to round 1 without changing `gameId`, and since
 * the W-CE-01 repair the console no longer remounts on a reload, so the card
 * kept the pre-activation round and every action it sent named a round that
 * no longer existed.
 *
 * The dashboard now passes what the card cannot see change -- the game's
 * status and round -- as `reloadKey`, so activating re-reads the card.
 */

jest.mock('../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));

jest.mock('../AuthContext', () => ({
  useAuth: () => ({
    user: { user_id: 1, game_id: 1, role: 'instructor', username: 'walk_instructor' },
    logout: jest.fn(),
  }),
}));

/** The server, keyed by URL; state is what the last lifecycle call left. */
const server = { status: 'setup' };

const dashboard = () => ({
  game_id: 1,
  game_name: 'CE 2026 Heat B',
  status: server.status,
  current_round: server.status === 'setup' ? 0 : 1,
  total_rounds: 10,
  teams: [],
  events_this_round: [],
  round_status: {
    round_state: server.status === 'setup' ? 'pending' : 'open',
    total_teams: 2, teams_locked: 0, teams_pending: 2,
  },
});

/** Round control, as the console reads it before and after activation. */
const roundControl = () => ({
  game_name: 'CE 2026 Heat B',
  total_rounds: 10,
  game_status: server.status,
  round: server.status === 'setup'
    ? {
      round_number: 0, status: 'pending', next_action: 'deadline',
      deadline: null, seconds_remaining: null, is_overdue: false,
      teams_locked: 0, teams_total: 2, teams_pending: 2,
      processing_status: 'PENDING', close_reason: '',
    }
    : {
      round_number: 1, status: 'open', next_action: 'deadline',
      deadline: null, seconds_remaining: null, is_overdue: false,
      teams_locked: 0, teams_total: 2, teams_pending: 2,
      processing_status: 'PENDING', close_reason: '',
    },
});

const respond = (url) => {
  if (url === '/games/1/instructor/dashboard/') return { data: dashboard() };
  if (url === '/games/1/round-schedule/') return { data: { game_name: 'CE 2026 Heat B', total_rounds: 10, rounds: [] } };
  if (url === '/games/1/round-control/') return { data: roundControl() };
  if (url.endsWith('/instructor/alerts/')) return { data: { alerts: [] } };
  if (url.endsWith('/instructor/research-queries/')) return { data: { queries: [] } };
  if (url.endsWith('/instructor/event-templates/')) return { data: { event_templates: [], markets: [] } };
  if (url.endsWith('/instructor/briefings/')) return { data: { briefings: [] } };
  if (url.endsWith('/instructor/operator-events/')) return { data: { events: [] } };
  if (url === '/instructor/student-accounts/') return { data: { students: [] } };
  if (url === '/instructor/active-sessions/') return { data: [] };
  if (url === '/courses/') return { data: [] };
  return { data: {} };
};

// A real server answers on a later task, never in the same microtask as the
// click; see instructorDashboardTabs.test.js for why that matters here.
const later = (value) => new Promise((resolve) => setTimeout(() => resolve(value), 5));

beforeEach(() => {
  server.status = 'setup';
  client.get.mockImplementation((url) => (
    url === '/games/1/instructor/dashboard/'
      ? later(respond(url))
      : Promise.resolve(respond(url))));
  client.post.mockImplementation((url) => {
    if (url === '/games/1/activate/') {
      server.status = 'active';
      return Promise.resolve({ data: { game_id: 1, status: 'active', current_round: 1 } });
    }
    return Promise.resolve({ data: { message: 'ok' } });
  });
});

afterEach(() => {
  jest.clearAllMocks();
  document.body.innerHTML = '';
});

const activate = async () => {
  render(<MemoryRouter><InstructorDashboard /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('tab', { name: 'instructor.game_control' }));
  fireEvent.click(await screen.findByRole('button', { name: 'instructor.activate_game' }));
  const popover = await screen.findByRole('tooltip');
  fireEvent.click(within(popover).getByRole('button', { name: 'OK' }));
  await waitFor(() => expect(client.post).toHaveBeenCalledWith('/games/1/activate/'));
  await screen.findByRole('button', { name: 'instructor.pause_game' });
};

test('the round control card re-reads the round after the game is activated', async () => {
  await activate();

  await waitFor(() => expect(
    client.get.mock.calls.filter(([url]) => url === '/games/1/round-control/').length,
  ).toBeGreaterThanOrEqual(2));
  // And it is the round the game actually moved to that is on the card: the
  // pre-activation round 0 was "pending", round 1 is open.
  await waitFor(() => expect(
    document.body.textContent).toContain('instructor.rc_status_open'), { timeout: 5000 });
  expect(document.body.textContent).not.toContain('instructor.rc_status_pending');
});

test('the first round-control action after activation names the round the game is on', async () => {
  await activate();

  // Round 1 is open, so the card offers Close; whichever control is pressed
  // first, it must carry the round the game actually moved to.
  await waitFor(() => expect(
    document.body.textContent).toContain('instructor.rc_status_open'), { timeout: 5000 });
  const close = await screen.findByRole('button', { name: 'instructor.rc_close_now' });
  fireEvent.click(close);
  const popover = await screen.findByRole('tooltip');
  fireEvent.click(within(popover).getByRole('button', { name: 'OK' }));

  await waitFor(() => expect(client.post).toHaveBeenCalledWith(
    '/games/1/round-control/close/',
    expect.objectContaining({ expected_round_number: 1 }),
  ));
  expect(client.post).not.toHaveBeenCalledWith(
    '/games/1/round-control/close/',
    expect.objectContaining({ expected_round_number: 0 }),
  );
});
