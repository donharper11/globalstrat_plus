import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Card, Select, Space, Table, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { getOperatorEvents } from '../../api/instructor';

const { Text } = Typography;

/**
 * What the operators did to this game, in timestamp order.
 *
 * The dispute procedure for "the operator changed something" asks for actor,
 * timestamp, action, before and after, reason and request id, and for refusals
 * to be visible beside the actions that succeeded. That is what this shows.
 * It is read-only: these rows are evidence, and the database enforces that
 * whatever any screen does.
 */
export default function OperatorEventsPanel({ gameId }) {
  const { t } = useTranslation();
  const [events, setEvents] = useState([]);
  const [outcome, setOutcome] = useState('all');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const params = outcome === 'all' ? {} : { outcome };
      const res = await getOperatorEvents(gameId, params);
      setEvents(res.data.events || []);
    } catch (e) {
      setError(e.response?.data?.error || e.message);
    } finally {
      setLoading(false);
    }
  }, [gameId, outcome]);

  useEffect(() => { load(); }, [load]);

  if (error) {
    return <Alert type="error" showIcon
      message={t('instructor.operator_events_failed', 'Operator events unavailable')}
      description={error} />;
  }

  return (
    <Card size="small" title={t('instructor.operator_events', 'Operator actions')}
      extra={
        <Space>
          <Select size="small" value={outcome} onChange={setOutcome}
            style={{ width: 160 }}
            options={[
              { value: 'all', label: t('instructor.all_outcomes', 'All outcomes') },
              { value: 'committed', label: t('instructor.committed', 'Committed') },
              { value: 'rejected', label: t('instructor.rejected', 'Refused') },
            ]} />
        </Space>
      }>
      <Table
        dataSource={events}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 1100 }}
        columns={[
          {
            title: t('instructor.time_server', 'Time (server)'),
            dataIndex: 'server_timestamp',
            render: v => (v ? new Date(v).toLocaleString() : '—'),
          },
          { title: t('instructor.actor', 'Actor'), dataIndex: 'actor' },
          { title: t('instructor.action', 'Action'), dataIndex: 'action' },
          {
            title: t('instructor.outcome', 'Outcome'),
            dataIndex: 'outcome',
            render: v => <Tag color={v === 'committed' ? 'green' : 'red'}>{v}</Tag>,
          },
          {
            title: t('instructor.round', 'Round'),
            dataIndex: 'round_number',
            render: v => (v === null || v === undefined ? '—' : v),
          },
          {
            title: t('instructor.reason', 'Reason'),
            dataIndex: 'reason',
            render: v => v || '—',
          },
          {
            title: t('instructor.before_after', 'Before → after'),
            key: 'before_after',
            render: (_, row) => (
              <Text code copyable={{ text: JSON.stringify({ before: row.before, after: row.after, conflict: row.conflict }) }}>
                {JSON.stringify(row.before)} → {JSON.stringify(row.after)}
              </Text>
            ),
          },
          {
            title: t('instructor.request_id', 'Request ID'),
            dataIndex: 'request_id',
            render: v => (v ? <Text code copyable>{v}</Text> : '—'),
          },
        ]}
      />
    </Card>
  );
}
