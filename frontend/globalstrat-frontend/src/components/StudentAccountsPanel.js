import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Badge, Button, Card, Input, Modal, Popconfirm, Space, Switch,
  Table, Tag, Tooltip, Typography, message,
} from 'antd';

import {
  getStudentAccounts, setStudentPassword, bulkResetPasswords,
  getActiveSessions,
} from '../api/accounts';

const { Text, Paragraph } = Typography;

function formatMinutes(mins) {
  if (mins === null || mins === undefined) return '—';
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

/**
 * Student account administration: who can log in, who is logged in, and
 * password resets.
 */
export default function StudentAccountsPanel({ gameId }) {
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
      message.error(err.response?.data?.error || 'Could not load student accounts');
    } finally {
      setLoading(false);
    }
  }, [search, thisGameOnly, gameId]);

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
      message.error(err.response?.data?.error || 'Could not set the password');
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
        <Tooltip title={onlineIds.has(r.user_id) ? 'Logged in now' : 'Not logged in'}>
          <Badge status={onlineIds.has(r.user_id) ? 'success' : 'default'} />
        </Tooltip>
      ),
    },
    {
      title: 'Student', key: 'name',
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.display_name || r.username}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{r.username}</Text>
        </Space>
      ),
    },
    { title: 'Student ID', dataIndex: 'student_id', render: v => v || <Text type="secondary">—</Text> },
    {
      title: 'Logged in for', key: 'online_minutes',
      render: (_, r) => {
        const s = (sessions?.active || []).find(x => x.user_id === r.user_id);
        return s
          ? <Text>{formatMinutes(s.duration_minutes)}</Text>
          : <Text type="secondary">—</Text>;
      },
    },
    {
      title: 'Password', key: 'has_password', width: 150,
      render: (_, r) => (r.needs_password
        ? <Tag color="red">Not set — cannot log in</Tag>
        : <Tag color="green">Set</Tag>),
    },
    {
      title: 'Actions', key: 'actions', width: 220,
      render: (_, r) => (
        <Space>
          <Popconfirm
            title="Reset to default?"
            description={`Their password becomes their student ID (${r.default_password || '—'}).`}
            onConfirm={() => doReset(r, { reset_to_default: true }, 'Password reset to the student ID')}
            disabled={!r.default_password}
          >
            <Button size="small" disabled={!r.default_password}>Reset to ID</Button>
          </Popconfirm>
          <Button size="small" onClick={() => { setPwModal(r); setPwValue(''); }}>
            Set password
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Card
        title="Who's logged in"
        style={{ marginBottom: 16 }}
        extra={<Button size="small" onClick={load} loading={loading}>Refresh</Button>}
      >
        {sessions && (
          <>
            <Space size="large" wrap style={{ marginBottom: 12 }}>
              <Text strong style={{ fontSize: 20 }}>
                {sessions.active_count} online
              </Text>
              <Text type="secondary">
                Counted as online if active in the last {sessions.idle_timeout_minutes} minutes.
                Auto-refreshes every 30s.
              </Text>
            </Space>
            <Table
              size="small" rowKey="session_id" pagination={false}
              dataSource={sessions.active || []}
              locale={{ emptyText: 'Nobody is logged in right now.' }}
              columns={[
                {
                  title: 'Student', key: 'who',
                  render: (_, r) => (
                    <Space direction="vertical" size={0}>
                      <Text strong>{r.display_name || r.username}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>{r.username}</Text>
                    </Space>
                  ),
                },
                { title: 'Team', dataIndex: 'team_name', render: v => v || <Text type="secondary">—</Text> },
                {
                  title: 'Logged in for', dataIndex: 'duration_minutes',
                  sorter: (a, b) => a.duration_minutes - b.duration_minutes,
                  defaultSortOrder: 'descend',
                  render: v => formatMinutes(v),
                },
                {
                  title: 'Last active', dataIndex: 'idle_minutes',
                  render: v => (v <= 1
                    ? <Tag color="green">now</Tag>
                    : <Text type="secondary">{formatMinutes(v)} ago</Text>),
                },
                { title: 'Since', dataIndex: 'login_at', render: v => new Date(v).toLocaleTimeString() },
              ]}
            />
          </>
        )}
      </Card>

      <Card
        title="Student accounts &amp; passwords"
        extra={
          <Space>
            <Switch size="small" checked={thisGameOnly} onChange={setThisGameOnly} />
            <Text type="secondary">This game only</Text>
          </Space>
        }
      >
        {missingCount > 0 && (
          <Alert
            type="warning" showIcon style={{ marginBottom: 12 }}
            message={`${missingCount} student${missingCount === 1 ? '' : 's'} cannot log in`}
            description="These accounts have no password set. Give each one their student ID as a password so they can sign in."
            action={
              <Popconfirm
                title={`Set ${missingCount} password${missingCount === 1 ? '' : 's'}?`}
                description="Each student's password becomes their own student ID. Existing passwords are left alone."
                onConfirm={async () => {
                  try {
                    const res = await bulkResetPasswords({ only_missing: true });
                    message.success(res.data.message);
                    if (res.data.skipped_count) {
                      message.warning(`${res.data.skipped_count} skipped — no student ID on file.`);
                    }
                    load();
                  } catch (err) {
                    message.error(err.response?.data?.error || 'Bulk reset failed');
                  }
                }}
              >
                <Button size="small" type="primary">Set all to student ID</Button>
              </Popconfirm>
            }
          />
        )}

        <Input.Search
          allowClear placeholder="Search by name, username or student ID"
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
        title={pwModal ? `Set password for ${pwModal.display_name || pwModal.username}` : ''}
        open={!!pwModal}
        onCancel={() => { setPwModal(null); setPwValue(''); }}
        confirmLoading={pwSaving}
        onOk={() => {
          if (pwValue.length < 6) {
            message.error('Password must be at least 6 characters.');
            return;
          }
          doReset(pwModal, { password: pwValue }, 'Password updated');
        }}
        okText="Set password"
      >
        <Paragraph type="secondary">
          The student can log in with this immediately. You'll see it once
          after saving — it isn't recoverable later, only resettable.
        </Paragraph>
        <Input.Password
          placeholder="New password (at least 6 characters)"
          value={pwValue} onChange={(e) => setPwValue(e.target.value)}
          onPressEnter={() => pwValue.length >= 6 && doReset(pwModal, { password: pwValue }, 'Password updated')}
        />
      </Modal>

      <Modal
        title="Password set"
        open={!!revealed}
        onCancel={() => setRevealed(null)}
        footer={[<Button key="ok" type="primary" onClick={() => setRevealed(null)}>Done</Button>]}
      >
        {revealed && (
          <>
            <Paragraph>Give these to the student:</Paragraph>
            <Card size="small">
              <Paragraph style={{ marginBottom: 4 }}>
                <Text type="secondary">Username: </Text>
                <Text strong copyable code>{revealed.username}</Text>
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                <Text type="secondary">Password: </Text>
                <Text strong copyable code>{revealed.password}</Text>
              </Paragraph>
            </Card>
            <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              This is the only time the password is shown. If it's lost, reset it again.
            </Paragraph>
          </>
        )}
      </Modal>
    </>
  );
}
