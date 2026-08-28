import React from 'react';
import { Alert, Card, Empty, Table, Typography } from 'antd';

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
 */
export default function AuditEvidenceTable({ events, error, title = 'Submission audit evidence' }) {
  if (error) {
    return (
      <Card size="small" title={title} style={{ marginTop: 12 }}>
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
      </Card>
    );
  }

  if (!events || events.length === 0) {
    return (
      <Card size="small" title={title} style={{ marginTop: 12 }}>
        <Empty description="No recorded saves for this round" />
      </Card>
    );
  }

  return (
    <Card size="small" title={title} style={{ marginTop: 12 }}>
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
    </Card>
  );
}
