import React from 'react';
import { Alert, Card, Collapse, Empty, Table, Typography } from 'antd';
import { useTranslation } from 'react-i18next';

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
 *
 * Its headings and notices come from the catalogue (W-CE-17): the table was
 * English on a Chinese console. The rows themselves -- actor, action,
 * endpoint, request id, hash, payload -- are the record and are shown as
 * stored.
 */
export default function AuditEvidenceTable({ events, error, title, collapsed = false }) {
  const { t } = useTranslation();
  const heading = title || t('instructor.audit_evidence_title');
  let body;
  if (error) {
    body = (
      <Alert
        type="error"
        showIcon
        message={t('instructor.audit_load_failed')}
        description={
          <>
            <div>{error}</div>
            <div style={{ marginTop: 4 }}>{t('instructor.audit_not_empty_note')}</div>
          </>
        }
      />
    );
  } else if (!events || events.length === 0) {
    body = <Empty description={t('instructor.audit_no_saves')} />;
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
            title: t('instructor.time_server'),
            dataIndex: 'server_timestamp',
            render: v => (v ? new Date(v).toLocaleString() : '—'),
          },
          { title: t('instructor.actor'), dataIndex: 'actor', render: v => v || '—' },
          { title: t('instructor.action'), dataIndex: 'action' },
          { title: t('instructor.endpoint'), dataIndex: 'endpoint' },
          { title: t('instructor.request_id'), dataIndex: 'request_id', render: v => v || '—' },
          {
            title: t('instructor.payload_sha256'),
            dataIndex: 'payload_sha256',
            render: v => <Text code copyable>{v}</Text>,
          },
          {
            title: t('instructor.payload'),
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
        items={[{ key: 'audit', label: heading, children: body }]}
      />
    );
  }
  return (
    <Card size="small" title={heading} style={{ marginTop: 12 }}>
      {body}
    </Card>
  );
}
