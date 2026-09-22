import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@testing-library/jest-dom';

import client from '../api/client';
// The real catalogue, so the counts are read the way an instructor reads
// them rather than as a key.
import '../i18n';
import InstructorDashboard from './InstructorDashboard';

/**
 * W-CE-05 (walkthrough of 2026-09-22). After a 27-row roster CSV the console
 * announced nothing the walkthrough could find: no modal, no toast, the
 * table had simply grown. The D6 outcome helper WAS wired at both call
 * sites; what it announced for a clean upload was a three-second toast,
 * gone before anyone looked (the harness looked after four). A batch
 * upload's outcome now also stays on the roster panel until dismissed, for
 * a clean upload and a refused one alike, in the instructor's language.
 *
 * The pasted-text control is driven here because jsdom's File has no
 * `.text()`; both controls hand the response to the same reading and the
 * same panel (`rosterUploadCallSites.test.js` keeps it so).
 */

jest.mock('../api/client', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));

jest.mock('../AuthContext', () => ({
  useAuth: () => ({
    user: { user_id: 1, game_id: null, role: 'instructor', username: 'walk_instructor' },
    logout: jest.fn(),
  }),
}));

const respond = (url) => {
  if (url === '/courses/') return { data: [{ course_id: 1, course_code: 'CE26', course_name: 'Global Strategy Practicum' }] };
  if (url === '/sections/') return { data: [{ section_id: 1, section_code: 'CE26-A', section_name: 'Heat A' }] };
  if (url === '/roster/') return { data: [] };
  if (url === '/team-management/') return { data: null };
  if (url === '/games/') return { data: { games: [] } };
  return { data: {} };
};

const CSV = 'student_id,display_name,email\ns2601,Ava Chen,ava.chen@example.invalid';

beforeEach(() => {
  client.get.mockImplementation((url) => Promise.resolve(respond(url)));
  client.post.mockImplementation((url) => {
    if (url === '/roster/') return Promise.resolve({ data: { created: 27, updated: 0, errors: [] } });
    return Promise.resolve({ data: {} });
  });
});

afterEach(() => {
  jest.clearAllMocks();
  document.body.innerHTML = '';
});

const openBulkUpload = async () => {
  render(<MemoryRouter><InstructorDashboard /></MemoryRouter>);
  fireEvent.click(await screen.findByText('CE26'));
  fireEvent.click(await screen.findByText('CE26-A'));
  await screen.findByText('Bulk Upload (CSV)');
  fireEvent.click(screen.getByText('Bulk Upload (CSV)'));
  const textarea = await screen.findByPlaceholderText(/student_id,display_name,email/);
  fireEvent.change(textarea, { target: { value: CSV } });
  fireEvent.click(screen.getByRole('button', { name: 'Upload Pasted Text' }));
  await waitFor(() => expect(client.post).toHaveBeenCalledWith(
    '/roster/', { action: 'upload', section_id: 1, csv: CSV }));
};

describe('a roster upload announces what it did, and the announcement stays', () => {
  test('a clean upload: the count is on the panel four seconds later', async () => {
    await openBulkUpload();

    // The toast the helper has always shown...
    await waitFor(() => expect(document.body.textContent)
      .toContain('Added 27 student(s) to the roster.'));
    // ...and the notice that now stays.
    const outcome = await screen.findByTestId('roster-upload-outcome');
    expect(outcome).toHaveTextContent('Added 27 student(s) to the roster.');

    // The walkthrough looked four seconds after choosing the file. antd's
    // toast lives three seconds (its documented default; jsdom cannot animate
    // it away, so its removal is not asserted here). The panel's outcome is
    // still there.
    await act(() => new Promise((resolve) => setTimeout(resolve, 4000)));
    expect(screen.getByTestId('roster-upload-outcome'))
      .toHaveTextContent('Added 27 student(s) to the roster.');
  }, 15000);

  test('a partly refused upload: the counts stay on the panel beside the modal', async () => {
    client.post.mockImplementation(() => Promise.resolve({
      data: { created: 2, updated: 1, errors: [{ row: 4, error: 'Row 4 refused.', code: 'section_full' }] },
    }));
    await openBulkUpload();

    const outcome = await screen.findByTestId('roster-upload-outcome');
    expect(outcome).toHaveTextContent('3 row(s) accepted, 1 refused');
    expect(outcome).toHaveTextContent('Accepted: 2 student(s) added, 1 already on the roster.');
  }, 15000);
});
