import fs from 'fs';
import path from 'path';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import client from '../../api/client';
import { advanceRound } from '../../api/instructor';
import AdvanceRoundControl from './AdvanceRoundControl';

/**
 * W-CE-24 (walkthrough of 2026-09-22). The Game Lifecycle card's "Advance
 * Round" sent `force: true` whenever a team was pending and never a reason,
 * so the legacy advance route refused it with `reason_required` on every
 * click; the modal had no box to write one in. It is now the ReasonedAction
 * pattern with teams pending, and the server's refusal is shown verbatim.
 */

jest.mock('../../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));

afterEach(() => {
  jest.clearAllMocks();
  // Modal.error renders into document.body outside the RTL container.
  document.body.innerHTML = '';
});

const t = (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key);

describe('the API wrapper', () => {
  test('carries the written reason with the force flag', () => {
    advanceRound(7, true, 'two teams never signed in this round');
    expect(client.post).toHaveBeenCalledWith(
      '/games/7/instructor/advance-round/',
      { force: true, reason: 'two teams never signed in this round' });
  });
});

describe('the dashboard’s call site', () => {
  const source = fs.readFileSync(
    path.join(__dirname, '..', '..', 'pages', 'InstructorDashboard.js'), 'utf8');

  test('the lifecycle card uses the reasoned control, not a bare confirm', () => {
    expect(source).toMatch(/<AdvanceRoundControl\b/);
    expect(source).not.toMatch(/advanceModalOpen/);
    expect(source).not.toMatch(/await advanceRound\(gameId, force\)/);
  });
});

describe('with teams pending', () => {
  const setup = () => render(
    <AdvanceRoundControl t={t} gameId={3} gameName="CE 2026 Heat A"
      teamsPending={6} onAdvanced={jest.fn()} />);

  test('nothing is sent until a reason of ten characters is written', async () => {
    client.post.mockResolvedValue({ data: { message: 'CE 2026 Heat A: round 4 is open.' } });
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'instructor.advance_round' }));

    expect(screen.getByText('instructor.advance_pending {"count":6}')).toBeInTheDocument();
    expect(screen.getByText('instructor.advance_round_named {"game":"CE 2026 Heat A"}')).toBeInTheDocument();
    const ok = screen.getByRole('button', { name: 'instructor.advance_now' });
    expect(ok).toBeDisabled();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'short' } });
    expect(ok).toBeDisabled();
    expect(client.post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByRole('textbox'),
      { target: { value: '  two teams withdrew after the deadline  ' } });
    expect(ok).toBeEnabled();
    fireEvent.click(ok);

    await waitFor(() => expect(client.post).toHaveBeenCalledWith(
      '/games/3/instructor/advance-round/',
      { force: true, reason: 'two teams withdrew after the deadline' }));
  });

  test('a refusal is shown in the server’s own words, with its guidance', async () => {
    client.post.mockRejectedValue({
      response: {
        status: 400,
        data: {
          code: 'reason_required',
          error: '此操作会绕过一项完整性检查，因此需要填写至少 10 个字符的书面理由。',
          guidance: '请填写书面理由，说明为何需要此次越权操作，然后重新执行。',
        },
      },
    });
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'instructor.advance_round' }));
    fireEvent.change(screen.getByRole('textbox'),
      { target: { value: 'a reason the server still refuses' } });
    fireEvent.click(screen.getByRole('button', { name: 'instructor.advance_now' }));

    await waitFor(() => expect(document.body.textContent).toContain(
      '此操作会绕过一项完整性检查，因此需要填写至少 10 个字符的书面理由。 '
      + '请填写书面理由，说明为何需要此次越权操作，然后重新执行。'));
    expect(document.body.textContent).not.toContain('instructor.failed_advance_round');
  });
});

describe('with every team locked', () => {
  test('a plain confirmation sends no force flag and no reason', async () => {
    const onAdvanced = jest.fn();
    client.post.mockResolvedValue({ data: { message: 'done' } });
    render(
      <AdvanceRoundControl t={t} gameId={3} gameName="CE 2026 Heat A"
        teamsPending={0} onAdvanced={onAdvanced} />);
    fireEvent.click(screen.getByRole('button', { name: 'instructor.advance_round' }));
    expect(screen.getByText('instructor.advance_ready')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'instructor.advance_now' }));

    await waitFor(() => expect(client.post).toHaveBeenCalledWith(
      '/games/3/instructor/advance-round/', { force: false, reason: '' }));
    await waitFor(() => expect(onAdvanced).toHaveBeenCalled());
  });
});
