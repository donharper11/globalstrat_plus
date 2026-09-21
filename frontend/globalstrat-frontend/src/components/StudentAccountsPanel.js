import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Badge, Button, Card, Input, Modal, Popconfirm, Space, Switch,
  Table, Tag, Tooltip, Typography, message,
} from 'antd';
import { useTranslation } from 'react-i18next';

import {
  getStudentAccounts, setStudentPassword, bulkResetPasswords,
  getActiveSessions,
} from '../api/accounts';

const { Text, Paragraph } = Typography;

function formatMinutes(mins, t) {
  if (mins === null || mins === undefined) return '—';
  if (mins < 60) return t('instructor.sa_minutes', { m: mins });
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  if (m) return t('instructor.sa_hours_minutes', { h, m });
  return t('instructor.sa_hours', { h });
}

/**
 * Student account administration: who can log in, who is logged in, and
 * password resets.
 */
export default function StudentAccountsPanel({ gameId }) {
  const { t } = useTranslation();
  const [students, setStudents] = useState([]);
  const [sessions, setSessions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [thisGameOnly, setThisGameOnly] = useState(true);

  const [pwModal, setPwModal] = useState(null); // the student being edited
  const [pwValue, setPwValue] = useState('');
  const [pwSaving, setPwSaving] = useState(false);
  const [revealed, setRevealed] = useState(null); // {username, password}

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      if (thisGameOnly && gameId) params.game_id = gameId;
      const [accRes, sessRes] = await Promise.all([
        getStudentAccounts(params),
        getActiveSessions(thisGameOnly && gameId ? { game_id: gameId } : {}),
      ]);
      setStudents(accRes.data.students || []);
      setSessions(sessRes.data);
    } catch (err) {
      message.error(err.response?.data?.error || t('instructor.sa_load_failed'));
    } finally {
      setLoading(false);
    }
  }, [search, thisGameOnly, gameId, t]);

  useEffect(() => { load(); }, [load]);

  // Refresh the online list regularly — it's the point of the panel.
  useEffect(() => {
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [load]);

  const doReset = async (student, payload, label) => {
    setPwSaving(true);
    try {
      const res = await setStudentPassword(student.user_id, payload);
      setRevealed({ username: res.data.username, password: res.data.password });
      message.success(label);
      setPwModal(null);
      setPwValue('');
      load();
    } catch (err) {
      message.error(err.response?.data?.error || t('instructor.sa_set_failed'));
    } finally {
      setPwSaving(false);
    }
  };

  const missingCount = students.filter(s => s.needs_password).length;
  const onlineIds = new Set((sessions?.active || []).map(s => s.user_id));

  const columns = [
    {
      title: '', key: 'online', width: 40,
      render: (_, r) => (
        <Tooltip title={onlineIds.has(r.user_id) ? t('instructor.sa_online') : t('instructor.sa_offline')}>
          <Badge status={onlineIds.has(r.user_id) ? 'success' : 'default'} />
        </Tooltip>
      ),
    },
    {
      title: t('instructor.sa_student'), key: 'name',
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.display_name || r.username}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{r.username}</Text>
        </Space>
      ),
    },
    { title: t('instructor.sa_student_id'), dataIndex: 'student_id', render: v => v || <Text type="secondary">—</Text> },
    {
      title: t('instructor.sa_logged_in_for'), key: 'online_minutes',
      render: (_, r) => {
        const s = (sessions?.active || []).find(x => x.user_id === r.user_id);
        return s
          ? <Text>{formatMinutes(s.duration_minutes, t)}</Text>
          : <Text type="secondary">—</Text>;
      },
    },
    {
      title: t('instructor.sa_password'), key: 'has_password', width: 150,
      render: (_, r) => (r.needs_password
        ? <Tag color="red">{t('instructor.sa_password_missing')}</Tag>
        : <Tag color="green">{t('instructor.sa_password_set')}</Tag>),
    },
    {
      title: t('instructor.sa_actions'), key: 'actions', width: 220,
      render: (_, r) => (
        <Space>
          <Popconfirm
            title={t('instructor.sa_reset_confirm')}
            description={t('instructor.sa_reset_confirm_hint', { password: r.default_password || '—' })}
            onConfirm={() => doReset(r, { reset_to_default: true }, t('instructor.sa_reset_done'))}
            disabled={!r.default_password}
          >
            <Button size="small" disabled={!r.default_password}>{t('instructor.sa_reset_to_id')}</Button>
          </Popconfirm>
          <Button size="small" onClick={() => { setPwModal(r); setPwValue(''); }}>
            {t('instructor.sa_set_password')}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title={t('instructor.sa_whos_logged_in')}
        style={{ marginBottom: 16 }}
        extra={<Button size="small" onClick={load} loading={loading}>{t('instructor.rc_refresh')}</Button>}
      >
        {sessions && (
          <>
            <Space size="large" wrap style={{ marginBottom: 12 }}>
              <Text strong style={{ fontSize: 20 }}>
                {t('instructor.sa_active_sessions', { count: sessions.active_count })}
              </Text>
              <Text type="secondary">
                {t('instructor.sa_sessions_hint', { minutes: sessions.idle_timeout_minutes })}
              </Text>
            </Space>
            <Table
              size="small" rowKey="session_id" pagination={false}
              dataSource={sessions.active || []}
              locale={{ emptyText: t('instructor.sa_nobody_online') }}
              columns={[
                {
                  title: t('instructor.sa_student'), key: 'who',
                  render: (_, r) => (
                    <Space direction="vertical" size={0}>
                      <Text strong>{r.display_name || r.username}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>{r.username}</Text>
                    </Space>
                  ),
                },
                { title: t('instructor.sa_team'), dataIndex: 'team_name', render: v => v || <Text type="secondary">—</Text> },
                {
                  title: t('instructor.sa_logged_in_for'), dataIndex: 'duration_minutes',
                  sorter: (a, b) => a.duration_minutes - b.duration_minutes,
                  defaultSortOrder: 'descend',
                  render: v => formatMinutes(v, t),
                },
                {
                  title: t('instructor.sa_last_active'), dataIndex: 'idle_minutes',
                  render: v => (v <= 1
                    ? <Tag color="green">{t('instructor.sa_active_now')}</Tag>
                    : <Text type="secondary">{t('instructor.sa_time_ago', { time: formatMinutes(v, t) })}</Text>),
                },
                { title: t('instructor.sa_since'), dataIndex: 'login_at', render: v => new Date(v).toLocaleTimeString() },
              ]}
            />
          </>
        )}
      </Card>

      <Card
        title={t('instructor.sa_accounts_title')}
        extra={
          <Space>
            <Switch size="small" checked={thisGameOnly} onChange={setThisGameOnly} />
            <Text type="secondary">{t('instructor.sa_this_game_only')}</Text>
          </Space>
        }
      >
        {missingCount > 0 && (
          <Alert
            type="warning" showIcon style={{ marginBottom: 12 }}
            message={t('instructor.sa_cannot_log_in', { count: missingCount })}
            description={t('instructor.sa_cannot_log_in_hint')}
            action={
              <Popconfirm
                title={t('instructor.sa_bulk_confirm', { count: missingCount })}
                description={t('instructor.sa_bulk_confirm_hint')}
                onConfirm={async () => {
                  try {
                    const res = await bulkResetPasswords({ only_missing: true });
                    message.success(res.data.message);
                    if (res.data.skipped_count) {
                      message.warning(t('instructor.sa_bulk_skipped', { count: res.data.skipped_count }));
                    }
                    load();
                  } catch (err) {
                    message.error(err.response?.data?.error || t('instructor.sa_bulk_failed'));
                  }
                }}
              >
                <Button size="small" type="primary">{t('instructor.sa_bulk_button')}</Button>
              </Popconfirm>
            }
          />
        )}

        <Input.Search
          allowClear placeholder={t('instructor.sa_search_placeholder')}
          style={{ maxWidth: 380, marginBottom: 12 }}
          onSearch={setSearch}
          onChange={(e) => { if (!e.target.value) setSearch(''); }}
        />

        <Table
          size="small" rowKey="user_id" loading={loading}
          dataSource={students} columns={columns}
          pagination={{ pageSize: 25, showSizeChanger: true }}
        />
      </Card>

      <Modal
        title={pwModal ? t('instructor.sa_set_password_for', { name: pwModal.display_name || pwModal.username }) : ''}
        open={!!pwModal}
        onCancel={() => { setPwModal(null); setPwValue(''); }}
        confirmLoading={pwSaving}
        onOk={() => {
          if (pwValue.length < 6) {
            message.error(t('instructor.sa_password_too_short'));
            return;
          }
          doReset(pwModal, { password: pwValue }, t('instructor.sa_password_updated'));
        }}
        okText={t('instructor.sa_set_password')}
      >
        <Paragraph type="secondary">
          {t('instructor.sa_set_password_hint')}
        </Paragraph>
        <Input.Password
          placeholder={t('instructor.sa_new_password_placeholder')}
          value={pwValue} onChange={(e) => setPwValue(e.target.value)}
          onPressEnter={() => pwValue.length >= 6 && doReset(pwModal, { password: pwValue }, t('instructor.sa_password_updated'))}
        />
      </Modal>

      <Modal
        title={t('instructor.sa_password_set_title')}
        open={!!revealed}
        onCancel={() => setRevealed(null)}
        footer={[<Button key="ok" type="primary" onClick={() => setRevealed(null)}>{t('instructor.sa_done')}</Button>]}
      >
        {revealed && (
          <>
            <Paragraph>{t('instructor.sa_give_to_student')}</Paragraph>
            <Card size="small">
              <Paragraph style={{ marginBottom: 4 }}>
                <Text type="secondary">{t('instructor.sa_username_label')}{' '}</Text>
                <Text strong copyable code>{revealed.username}</Text>
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                <Text type="secondary">{t('instructor.sa_password_label')}{' '}</Text>
                <Text strong copyable code>{revealed.password}</Text>
              </Paragraph>
            </Card>
            <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              {t('instructor.sa_shown_once')}
            </Paragraph>
          </>
        )}
      </Modal>
    </>
  );
}
