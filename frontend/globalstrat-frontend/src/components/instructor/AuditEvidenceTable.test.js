import React from 'react';
import { render, screen, within, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import AuditEvidenceTable, { PAGE_SIZE } from './AuditEvidenceTable';

const event = (overrides = {}) => ({
  id: 1,
  server_timestamp: '2026-03-04T09:15:00Z',
  actor: 'ada.lovelace',
  action: 'save',
  endpoint: '/api/games/1/teams/2/decisions/round/3/',
  request_id: 'srv-11111111-2222-3333-4444-555555555555',
  payload_sha256: 'a'.repeat(64),
  payload: { marketing_budget: 250000 },
  ...overrides,
});

const rowsOf = table => within(table).getAllByRole('row').slice(1);

describe('audit evidence rendering', () => {
  test('shows actor, server time, request id, hash and payload for a save', () => {
    render(<AuditEvidenceTable events={[event()]} />);

    expect(screen.getByText('ada.lovelace')).toBeInTheDocument();
    expect(screen.getByText('save')).toBeInTheDocument();
    expect(screen.getByText('/api/games/1/teams/2/decisions/round/3/'))
      .toBeInTheDocument();
    expect(screen.getByText('srv-11111111-2222-3333-4444-555555555555'))
      .toBeInTheDocument();
    expect(screen.getByText('a'.repeat(64))).toBeInTheDocument();
    // The payload is shown verbatim: a dispute turns on what was submitted,
    // not on a summary of it.
    expect(screen.getByText('{"marketing_budget":250000}')).toBeInTheDocument();
    // Rendered from the server's timestamp, not the browser's clock.
    expect(screen.getByText(new Date('2026-03-04T09:15:00Z').toLocaleString()))
      .toBeInTheDocument();
  });

  test('renders a missing request id and actor as an em dash, not as blank', () => {
    render(<AuditEvidenceTable
      events={[event({ request_id: '', actor: null })]} />);
    const cells = screen.getAllByText('—');
    expect(cells.length).toBeGreaterThanOrEqual(2);
  });

  test('every column an instructor needs is present, in order', () => {
    render(<AuditEvidenceTable events={[event()]} />);
    // Read from the header row rather than by text: antd also renders a hidden
    // measurement row that repeats every heading, so a text query matches twice.
    const headings = screen.getAllByRole('columnheader').map(h => h.textContent);
    expect(headings).toEqual([
      'Time (server)', 'Actor', 'Action', 'Endpoint',
      'Request ID', 'Payload SHA-256', 'Payload',
    ]);
  });
});

describe('empty and failed history', () => {
  test('an empty audit trail says so', () => {
    render(<AuditEvidenceTable events={[]} />);
    expect(screen.getByText('No recorded saves for this round'))
      .toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  test('a missing audit trail is treated the same as an empty one', () => {
    render(<AuditEvidenceTable events={undefined} />);
    expect(screen.getByText('No recorded saves for this round'))
      .toBeInTheDocument();
  });

  test('a failed request is not shown as an empty audit trail', () => {
    // The defect this covers: `catch { setDrillData(null) }` rendered the same
    // "no submission data" as a team that genuinely submitted nothing, so a
    // server error read as evidence about the team.
    render(<AuditEvidenceTable events={undefined} error="503 Service Unavailable" />);

    expect(screen.getByText('Audit evidence could not be loaded'))
      .toBeInTheDocument();
    expect(screen.getByText('503 Service Unavailable')).toBeInTheDocument();
    expect(screen.getByText(/not the same as an empty audit trail/))
      .toBeInTheDocument();
    expect(screen.queryByText('No recorded saves for this round'))
      .not.toBeInTheDocument();
  });

  test('an error wins over rows that are also present', () => {
    render(<AuditEvidenceTable events={[event()]} error="network error" />);
    expect(screen.getByText('Audit evidence could not be loaded'))
      .toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});

describe('pagination', () => {
  const many = count => Array.from({ length: count }, (_, i) =>
    event({ id: i + 1, actor: `actor-${i + 1}`,
            payload_sha256: String(i + 1).padStart(64, '0') }));

  test(`shows at most ${PAGE_SIZE} saves per page`, () => {
    render(<AuditEvidenceTable events={many(PAGE_SIZE + 5)} />);
    expect(rowsOf(screen.getByRole('table'))).toHaveLength(PAGE_SIZE);
    expect(screen.getByText('actor-1')).toBeInTheDocument();
    expect(screen.queryByText(`actor-${PAGE_SIZE + 1}`)).not.toBeInTheDocument();
  });

  test('the remaining saves are reachable on the next page', () => {
    render(<AuditEvidenceTable events={many(PAGE_SIZE + 5)} />);
    fireEvent.click(screen.getByTitle('2'));
    expect(screen.getByText(`actor-${PAGE_SIZE + 1}`)).toBeInTheDocument();
    expect(screen.queryByText('actor-1')).not.toBeInTheDocument();
  });

  test('no pager appears when everything fits on one page', () => {
    render(<AuditEvidenceTable events={many(PAGE_SIZE)} />);
    expect(rowsOf(screen.getByRole('table'))).toHaveLength(PAGE_SIZE);
    expect(screen.queryByTitle('2')).not.toBeInTheDocument();
  });
});
