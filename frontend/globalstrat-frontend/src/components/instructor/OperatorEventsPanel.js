import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Card, Select, Space, Table, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { getOperatorEvents } from '../../api/instructor';
import { changedFields, fieldLabel, formatValue } from './operatorChange';

const { Text } = Typography;

/**
 * What the operators did to this game, in timestamp order.
 *
 * The dispute procedure for "the operator changed something" asks for actor,
 * timestamp, action, before and after, reason and request id, and for refusals
 * to be visible beside the actions that succeeded. That is what this shows.
 * It is read-only: these rows are evidence, and the database enforces that
 * whatever any screen does.
 *
 * Every label here comes from the catalogue, in both shipped languages. They
 * used to be written with a hard-coded English fallback as the second argument
 * to t(), which rendered correctly in English and left a Chinese instructor
 * reading English, because a fallback string satisfies i18next without the key
 * existing anywhere. These are operator words read under time pressure
 * mid-round, so they are translated for precision rather than polish.
 *
 * The old shape is described here rather than quoted. Spelling it out as a
 * literal call left a string in this file that matches a search for the very
 * defect it records, and two separate review passes reported this panel as
 * still carrying a fallback on the strength of this comment alone.
 *
 * "Before → after" was the audit row's JSON until 2026-09-22 (W-CE-07):
 * storage names, `null`, braces. It is now the fields that changed, labelled
 * and valued from the catalogue (`operatorChange.js`); the raw record stays
 * one click away, copyable, because the dispute runbook reads it.
 */
const OperatorChange = ({ row, t }) => {
  const raw = JSON.stringify({ before: row.before, after: row.after, conflict: row.conflict });
  const copy = (
    <Text type="secondary" style={{ fontSize: 11 }}
      copyable={{ text: raw, tooltips: false }}>
      {t('instructor.oplog_copy_record')}
    </Text>
  );
  if (row.outcome === 'rejected') {
    return (
      <div>
        <div>
          <Text type="danger">{t('instructor.oplog_refused_because')}</Text>{' '}
          {row.conflict?.detail || '—'}
        </div>
        {/* W-CE3-18: the code sat inline after the sentence with only a CSS
            margin between them, so the row's own text read
            `…at least 10 characters.reason_required`. It is a separate fact
            about the refusal, on its own line, with a label that says what
            it is. */}
        {row.conflict?.code ? (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {t('instructor.oplog_refusal_code')}
            </Text>{' '}
            <Text code>{row.conflict.code}</Text>
          </div>
        ) : null}
        {copy}
      </div>
    );
  }
  const rows = changedFields(row.before, row.after);
  return (
    <div>
      {rows.length === 0
        ? <Text type="secondary">{t('instructor.oplog_no_change')}</Text>
        : rows.map(({ key, before, after }) => (
          <div key={key}>
            {fieldLabel(key, t)}: {before === undefined
              ? formatValue(key, after, t)
              : `${formatValue(key, before, t)} → ${formatValue(key, after, t)}`}
          </div>
        ))}
      {copy}
    </div>
  );
};

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
      message={t('instructor.operator_events_failed')}
      description={error} />;
  }

  return (
    <Card size="small" title={t('instructor.operator_events')}
      extra={
        <Space>
          <Select size="small" value={outcome} onChange={setOutcome}
            style={{ width: 160 }}
            options={[
              { value: 'all', label: t('instructor.all_outcomes') },
              { value: 'committed', label: t('instructor.committed') },
              { value: 'rejected', label: t('instructor.rejected') },
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
            title: t('instructor.time_server'),
            dataIndex: 'server_timestamp',
            render: v => (v ? new Date(v).toLocaleString() : '—'),
          },
          { title: t('instructor.actor'), dataIndex: 'actor' },
          { title: t('instructor.action'), dataIndex: 'action' },
          {
            title: t('instructor.outcome'),
            dataIndex: 'outcome',
            render: v => <Tag color={v === 'committed' ? 'green' : 'red'}>{v}</Tag>,
          },
          {
            title: t('instructor.round'),
            dataIndex: 'round_number',
            render: v => (v === null || v === undefined ? '—' : v),
          },
          {
            title: t('instructor.reason'),
            dataIndex: 'reason',
            render: v => v || '—',
          },
          {
            title: t('instructor.before_after'),
            key: 'before_after',
            render: (_, row) => <OperatorChange row={row} t={t} />,
          },
          {
            title: t('instructor.request_id'),
            dataIndex: 'request_id',
            render: v => (v ? <Text code copyable>{v}</Text> : '—'),
          },
        ]}
      />
    </Card>
  );
}
