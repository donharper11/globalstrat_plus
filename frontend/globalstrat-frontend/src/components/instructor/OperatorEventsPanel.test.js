import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

import { getOperatorEvents } from '../../api/instructor';
import OperatorEventsPanel from './OperatorEventsPanel';
import { changedFields, formatValue } from './operatorChange';

/**
 * W-CE-07 (walkthrough of 2026-09-22). The Operator Log's "Before → after"
 * column was the audit row's JSON, storage names and all:
 * `{"status":"open","round_number":1} → {"round_number":1,"target_market":null,…}`.
 * It now reads as labelled fields in the instructor's language, one line per
 * field that changed, and a refusal shows the reason the server recorded.
 */

jest.mock('../../api/instructor', () => ({
  getOperatorEvents: jest.fn(),
}));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
  }),
}));

const EVENTS = [
  {
    id: 11, server_timestamp: '2026-09-22T16:40:00+00:00', actor: 'Walkthrough Instructor',
    action: 'activate_game', outcome: 'committed', round_number: null, reason: null,
    before: { game_id: 1, name: 'CE 2026 Heat A', status: 'setup', current_round: 0 },
    after: { game_id: 1, name: 'CE 2026 Heat A', status: 'active', current_round: 1 },
    conflict: null, request_id: 'srv-1',
  },
  {
    id: 12, server_timestamp: '2026-09-22T16:44:00+00:00', actor: 'Walkthrough Instructor',
    action: 'inject_event', outcome: 'committed', round_number: 1, reason: null,
    before: { status: 'open', round_number: 1 },
    after: { event_template: 'Major Competitor Product Launch', round_number: 1, target_market: null },
    conflict: null, request_id: 'srv-2',
  },
  {
    id: 13, server_timestamp: '2026-09-22T18:01:00+00:00', actor: 'Walkthrough Instructor',
    action: 'delete_game', outcome: 'rejected', round_number: 4, reason: null,
    before: { game_id: 1, name: 'CE 2026 Heat A', status: 'active', current_round: 4 },
    after: {},
    conflict: { code: 'competition_game_not_deletable', status: 409,
      detail: 'CE 2026 Heat A is a competition game, so it cannot be deleted.' },
    request_id: 'srv-3',
  },
];

// W-CE2-04: the row a failed processing leaves behind. `detail` is the
// server's sentence in the reader's language; `cause` is the technical text it
// quotes, kept so a dispute can read it.
const FAULT_EVENT = {
  id: 14, server_timestamp: '2026-09-22T18:20:00+00:00', actor: 'Walkthrough Instructor',
  action: 'process_round', outcome: 'rejected', round_number: 2, reason: null,
  before: { status: 'closed', round_number: 2 },
  after: {},
  conflict: {
    code: 'processing_failed', status: 500, message_key: 'processing_failed',
    cause: 'Natural key (\'team_id\', \'market_id\') is not unique in section "team_plant".',
    detail: 'Post-round processing failed: Natural key (\'team_id\', \'market_id\') is not unique in section "team_plant".',
  },
  request_id: 'srv-4',
};

afterEach(() => jest.clearAllMocks());

describe('the Operator Log column', () => {
  test('is labelled text, not the audit row’s JSON', async () => {
    getOperatorEvents.mockResolvedValue({ data: { events: EVENTS } });
    render(<OperatorEventsPanel gameId={1} />);
    await screen.findByText(/Major Competitor Product Launch/);

    const table = document.querySelector('.ant-table');
    const text = table.textContent;
    // No raw JSON and no storage names on the screen (a storage name in the
    // JSON travelled quoted; a catalogue key that happens to contain one,
    // such as `instructor.oplog_current_round`, does not).
    expect(text).not.toMatch(/\{"/);
    expect(text).not.toMatch(/"(round_number|target_market|current_round|game_id|status)"/);
    expect(text).not.toMatch(/\bgame_id\b|\btarget_market\b/);

    // The activation: the fields that changed, labelled, before → after.
    expect(text).toContain('instructor.status: instructor.oplog_game_status_setup → instructor.oplog_game_status_active');
    expect(text).toContain('instructor.oplog_current_round: 0 → 1');
    // The unchanged name is not repeated as a change.
    expect(text).not.toContain('instructor.game_name: CE 2026 Heat A → CE 2026 Heat A');

    // The injection: what was added, and no "null".
    expect(text).toContain('instructor.event_template: Major Competitor Product Launch');
    expect(text).not.toMatch(/null/);

    // The refusal: the server's recorded reason and the code.
    expect(text).toContain('instructor.oplog_refused_because CE 2026 Heat A is a competition game, so it cannot be deleted.');
    expect(text).toContain('competition_game_not_deletable');
  });

  test('an engine fault reads as the server\u2019s sentence, not a Python string', async () => {
    // W-CE2-04 (second walkthrough). `record_fault` used to store the raw
    // exception -- storage names, a Python argument, an instruction addressed
    // to a developer -- and this panel printed it verbatim. The server now
    // stores and serves the catalogue sentence, with the technical cause
    // carried inside it; the panel shows exactly what the server wrote, so a
    // Chinese console reads a Chinese sentence.
    getOperatorEvents.mockResolvedValue({ data: { events: [FAULT_EVENT] } });
    render(<OperatorEventsPanel gameId={1} />);
    await screen.findByText(/Post-round processing failed/);
    const text = document.querySelector('.ant-table').textContent;
    expect(text).toContain('instructor.oplog_refused_because Post-round processing failed:');
    // The cause is kept for the operator, inside the server's sentence.
    expect(text).toContain('Natural key');
    // The panel composes no English of its own around it.
    expect(text).not.toMatch(/engine_failure/);
    expect(text).toContain('processing_failed');
  });

  test('the raw record is still one click away for a dispute', async () => {
    getOperatorEvents.mockResolvedValue({ data: { events: EVENTS.slice(0, 1) } });
    render(<OperatorEventsPanel gameId={1} />);
    await waitFor(() => expect(screen.getAllByText('instructor.oplog_copy_record').length).toBe(1));
  });
});

describe('changedFields', () => {
  test('lists a field once, only when it differs, and never a null that was added', () => {
    expect(changedFields(
      { status: 'open', round_number: 1 },
      { event_template: 'X', round_number: 1, target_market: null },
    )).toEqual([{ key: 'event_template', before: undefined, after: 'X' }]);
    expect(changedFields({ a: 1 }, { a: 1 })).toEqual([]);
    expect(changedFields({ a: 1 }, { a: 2 })).toEqual([{ key: 'a', before: 1, after: 2 }]);
  });

  test('a nested list (a schedule, a team table) is compared entry by entry', () => {
    const before = { rounds: [{ round_number: 1, deadline: null }, { round_number: 2, deadline: null }] };
    const after = { rounds: [{ round_number: 1, deadline: '2026-09-25T10:00:00+00:00' }, { round_number: 2, deadline: null }] };
    expect(changedFields(before, after)).toEqual([{
      key: 'rounds',
      before: [{ round_number: 1, deadline: null }],
      after: [{ round_number: 1, deadline: '2026-09-25T10:00:00+00:00' }],
    }]);
  });

  test('console-internal fields are not shown', () => {
    expect(changedFields(
      { status: 'open', seconds_remaining: 100, next_action: 'close', is_overdue: false },
      { status: 'closed', seconds_remaining: 0, next_action: 'process', is_overdue: true },
    )).toEqual([{ key: 'status', before: 'open', after: 'closed' }]);
  });
});

describe('formatValue', () => {
  const t = (key) => key;
  test('speaks the catalogue, not the storage token', () => {
    expect(formatValue('status', 'processed', t)).toBe('instructor.rc_status_processed');
    expect(formatValue('status', 'paused', t)).toBe('instructor.oplog_game_status_paused');
    expect(formatValue('processing_status', 'FULLY_COMPLETE', t)).toBe('instructor.rc_processing_complete');
    expect(formatValue('close_reason', 'deadline', t)).toBe('instructor.rc_closed_by_deadline');
    expect(formatValue('participation_status', 'withdrawn', t)).toBe('instructor.oplog_participation_withdrawn');
    expect(formatValue('reopened', true, t)).toBe('instructor.yes');
    expect(formatValue('deadline', null, t)).toBe('—');
    expect(formatValue('close_reason', '', t)).toBe('—');
    expect(formatValue('deadline', '2026-09-25T10:00:00+00:00', t))
      .toBe(new Date('2026-09-25T10:00:00+00:00').toLocaleString());
  });
});
