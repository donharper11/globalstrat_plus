import React from 'react';
import { Alert, Card, Collapse, Empty, Table, Typography } from 'antd';

const { Text } = Typography;

export const PAGE_SIZE = 8;

/**
 * The per-save audit trail behind one team's round submission.
 *
 * Extracted from InstructorDashboard so it can be tested on its own. It was
 * 15 lines inside a 2,000-line component, reachable only by rendering the whole
 * instructor dashboard with an authenticated session and a mocked API — which
 * is a fair description of why it had no tests.
 *
 * The three states are deliberately distinct. A round with no saves and a round
 * whose audit trail could not be fetched are different facts, and an instructor
 * defending a disputed result needs to know which one they are looking at: one
 * says the team did not submit, the other says we do not currently know what
 * the team did.
 *
 * `collapsed` (W-CE-20): the drill-down opened on this table, whose rows are
 * hundreds of pixels tall, and the team's actual decisions sat below dozens of
 * them. Behind a closed panel the evidence is one click away and nothing is
 * removed: every row, column and payload is still there when it opens.
 */
export default function AuditEvidenceTable({
  events, error, title = 'Submission audit evidence', collapsed = false,
}) {
  let body;
  if (error) {
    body = (
      <Alert
        type="error"
        showIcon
        message="Audit evidence could not be loaded"
        description={
          <>
            <div>{error}</div>
            <div style={{ marginTop: 4 }}>
              This is not the same as an empty audit trail. Retry before
              concluding anything about what this team submitted.
            </div>
          </>
        }
      />
    );
  } else if (!events || events.length === 0) {
    body = <Empty description="No recorded saves for this round" />;
  } else {
    body = (
      <Table
        dataSource={events}
        rowKey="id"
        size="small"
        pagination={{ pageSize: PAGE_SIZE }}
        scroll={{ x: 1000 }}
        columns={[
          {
            title: 'Time (server)',
            dataIndex: 'server_timestamp',
            render: v => (v ? new Date(v).toLocaleString() : '—'),
          },
          { title: 'Actor', dataIndex: 'actor', render: v => v || '—' },
          { title: 'Action', dataIndex: 'action' },
          { title: 'Endpoint', dataIndex: 'endpoint' },
          { title: 'Request ID', dataIndex: 'request_id', render: v => v || '—' },
          {
            title: 'Payload SHA-256',
            dataIndex: 'payload_sha256',
            render: v => <Text code copyable>{v}</Text>,
          },
          {
            title: 'Payload',
            dataIndex: 'payload',
            render: v => <Text code copyable>{JSON.stringify(v)}</Text>,
          },
        ]}
      />
    );
  }

  if (collapsed) {
    return (
      <Collapse
        size="small"
        style={{ marginTop: 12 }}
        items={[{ key: 'audit', label: title, children: body }]}
      />
    );
  }
  return (
    <Card size="small" title={title} style={{ marginTop: 12 }}>
      {body}
    </Card>
  );
}
