import React from 'react';
import { render, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TeamActivityBanner from './TeamActivityBanner';
import { getTeamChanges } from '../api/decisions';
import { useAuth } from '../AuthContext';

jest.mock('../api/decisions', () => ({
  getTeamChanges: jest.fn(() => Promise.resolve({ data: { changes: [] } })),
}));
jest.mock('../AuthContext', () => ({ useAuth: jest.fn() }));

/**
 * F6. The team-changes endpoint is `IsInstructor` since the V2-035 hardening,
 * so polling it from a student's decision screen every 30s could only ever
 * produce a 403 — a permanent stream of console and network errors on the
 * three pages a team spends the round on, which is exactly the noise that
 * hides a real failure on launch day.
 */

const props = {
  gameId: 1, teamId: 1, currentRound: 1, currentUserId: 2,
};

afterEach(() => jest.clearAllMocks());

test('a student never calls the instructor-only team-changes endpoint', () => {
  useAuth.mockReturnValue({ user: { user_id: 2, role: 'student' } });
  render(<TeamActivityBanner {...props} />);
  expect(getTeamChanges).not.toHaveBeenCalled();
});

test('an instructor still gets the teammate activity poll', async () => {
  useAuth.mockReturnValue({ user: { user_id: 9, role: 'instructor' } });
  render(<TeamActivityBanner {...props} />);
  await waitFor(() => expect(getTeamChanges).toHaveBeenCalled());
});

test('a missing or unknown role is treated as not entitled', () => {
  useAuth.mockReturnValue({ user: null });
  render(<TeamActivityBanner {...props} />);
  expect(getTeamChanges).not.toHaveBeenCalled();
});
