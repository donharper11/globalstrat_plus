import fs from 'fs';
import path from 'path';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import client from '../api/client';
import { resetGame, archiveGame, deleteGame } from '../api/instructor';
import ReasonedAction from '../components/instructor/ReasonedAction';

/**
 * Reset, archive and delete are operator actions that the server refuses
 * without a written reason of at least ten characters
 * (`OperatorAction.require_reason`, code `reason_required`). The console sent
 * none: `resetGame(gameId)` and `archiveGame(gameId)` posted an empty body, so
 * both buttons had answered 400 on every click since the lifecycle boundary
 * was adopted, and delete joined them when it was brought under the same
 * boundary. The backend half is pinned by
 * `test_operator_route_ownership.ConsoleReasonContractTests`.
 */

jest.mock('../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));

afterEach(() => jest.clearAllMocks());

describe('the API wrappers carry the reason', () => {
  test('reset and archive post it in the body', () => {
    resetGame(7, 'wrong scenario was chosen');
    archiveGame(7, 'the course has finished');

    expect(client.post).toHaveBeenCalledWith(
      '/games/7/reset/', { reason: 'wrong scenario was chosen' });
    expect(client.post).toHaveBeenCalledWith(
      '/games/7/archive/', { reason: 'the course has finished' });
  });

  test('delete sends it as the DELETE body', () => {
    deleteGame(7, 'created by mistake');

    expect(client.delete).toHaveBeenCalledWith(
      '/games/7/delete/', { data: { reason: 'created by mistake' } });
  });
});

describe('the dashboard’s call sites', () => {
  const source = fs.readFileSync(
    path.join(__dirname, 'InstructorDashboard.js'), 'utf8');

  test('no reset, archive or delete is sent without a reason', () => {
    const calls = source.match(/await (resetGame|archiveGame|deleteGame)\(/g) || [];
    const reasoned = source.match(
      /await (resetGame|archiveGame|deleteGame)\(gameId, reason\)/g) || [];
    expect(calls.length).toBe(4);
    expect(reasoned.length).toBe(calls.length);
  });
});

describe('ReasonedAction', () => {
  const t = (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key);
  const setup = (onConfirm = jest.fn().mockResolvedValue(undefined)) => {
    render(
      <ReasonedAction t={t} label="do-it" title="why-title"
        description="what-happens" okText="confirm-it" onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole('button', { name: 'do-it' }));
    return onConfirm;
  };

  test('nothing is sent until a reason of ten characters is written', async () => {
    const onConfirm = setup();
    const ok = screen.getByRole('button', { name: 'confirm-it' });
    expect(ok).toBeDisabled();
    expect(screen.getByText('what-happens')).toBeInTheDocument();
    // The instructor is told the reason is kept.
    expect(screen.getByText('instructor.reason_audit_note')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  too short ' } });
    expect(ok).toBeDisabled();

    fireEvent.change(screen.getByRole('textbox'),
      { target: { value: '  created by mistake  ' } });
    expect(ok).toBeEnabled();
    fireEvent.click(ok);

    await waitFor(() => expect(onConfirm).toHaveBeenCalledWith('created by mistake'));
  });
});
