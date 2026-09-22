import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import client from '../api/client';
import InstructorDashboard from './InstructorDashboard';

/**
 * W-CE-01 (walkthrough of 2026-09-22). Every Game Control action that
 * reloaded the dashboard -- activate, set deadline, extend, process -- threw
 * the console back to the Courses & Sections tab.
 *
 * Cause: `loadData()` sets `loading`, and the dashboard returned a bare
 * spinner while loading, unmounting the whole `<Tabs>`; the Tabs were
 * uncontrolled (`defaultActiveKey="courses"`), so the remount forgot which tab
 * the instructor was on. This drives the real component through the real
 * activate control and asserts the tab survives the reload.
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

const dashboard = (status) => ({
  game_id: 1,
  game_name: 'CE 2026 Heat A',
  status,
  current_round: status === 'setup' ? 0 : 1,
  total_rounds: 10,
  teams: [],
  events_this_round: [],
  round_status: {
    round_state: status === 'setup' ? 'pending' : 'open',
    total_teams: 8, teams_locked: 0, teams_pending: 8,
  },
});

/** The server, keyed by URL; state is what the last lifecycle call left. */
const server = { status: 'setup' };

const respond = (url) => {
  if (url === '/games/1/instructor/dashboard/') return { data: dashboard(server.status) };
  if (url === '/games/1/round-schedule/') return { data: { game_name: 'CE 2026 Heat A', total_rounds: 10, rounds: [] } };
  if (url === '/games/1/round-control/') return { data: { game_name: 'CE 2026 Heat A', total_rounds: 10, round: null, game_status: server.status } };
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

// A real server answers on a later task, never in the same microtask as
// the click. React 18 batches everything that happens before the next task,
// so an instantly-resolved mock would hide the loading render (and the
// unmount) that the browser shows. The dashboard fetch takes a tick.
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
    return Promise.resolve({ data: {} });
  });
});

afterEach(() => {
  jest.clearAllMocks();
  document.body.innerHTML = '';
});

const activeTab = () => document.querySelector('.ant-tabs-tab-active')?.textContent;

describe('the console stays on the tab an action was taken from', () => {
  test('Activate Game reloads the dashboard without leaving Game Control', async () => {
    render(<MemoryRouter><InstructorDashboard /></MemoryRouter>);

    const gameControl = await screen.findByRole('tab', { name: 'instructor.game_control' });
    fireEvent.click(gameControl);
    await waitFor(() => expect(activeTab()).toBe('instructor.game_control'));

    fireEvent.click(await screen.findByRole('button', { name: 'instructor.activate_game' }));
    // The Popconfirm's own OK.
    const popover = await screen.findByRole('tooltip');
    fireEvent.click(within(popover).getByRole('button', { name: 'OK' }));

    await waitFor(() => expect(client.post).toHaveBeenCalledWith('/games/1/activate/'));
    // The reload that follows the action: the dashboard is fetched again and
    // the game is now active.
    await waitFor(() => expect(
      client.get.mock.calls.filter(([url]) => url === '/games/1/instructor/dashboard/').length,
    ).toBeGreaterThanOrEqual(2));
    await screen.findByRole('button', { name: 'instructor.pause_game' });

    expect(activeTab()).toBe('instructor.game_control');
  });
});
