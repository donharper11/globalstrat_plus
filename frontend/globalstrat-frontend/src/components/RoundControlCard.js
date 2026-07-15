import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Card, DatePicker, Descriptions, Modal, Popconfirm,
  Progress, Space, Tag, Typography, message,
} from 'antd';
import dayjs from 'dayjs';

import {
  getRoundControl, closeRound, reopenRound, processRound,
  advanceToNextRound, setRoundDeadline,
} from '../api/accounts';

const { Text, Paragraph } = Typography;

const STATUS_COLOUR = {
  open: 'green',
  closed: 'orange',
  processed: 'blue',
  pending: 'default',
};

const PROCESSING_LABEL = {
  PENDING: 'Not yet processed',
  PROCESSING: 'Processing…',
  RESULTS_AVAILABLE: 'Results ready — narratives generating',
  FULLY_COMPLETE: 'Complete',
  FAILED: 'Failed',
};

function formatRemaining(seconds) {
  if (seconds === null || seconds === undefined) return null;
  const overdue = seconds < 0;
  const s = Math.abs(seconds);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const parts = [];
  if (d) parts.push(`${d}d`);
  if (h || d) parts.push(`${h}h`);
  parts.push(`${m}m`);
  const text = parts.join(' ');
  return overdue ? `${text} overdue` : `${text} remaining`;
}

/**
 * Drives the round lifecycle: open -> closed -> processed -> next round open.
 *
 * The backend reports which action comes next, so the console offers exactly
 * one primary button at a time rather than a row of buttons that may not
 * apply.
 */
export default function RoundControlCard({ gameId, onChanged }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(null);
  const [deadlineOpen, setDeadlineOpen] = useState(false);
  const [deadlineValue, setDeadlineValue] = useState(null);
  const [reopenOpen, setReopenOpen] = useState(false);
  const [reopenValue, setReopenValue] = useState(null);

  const load = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    try {
      const res = await getRoundControl(gameId);
      setData(res.data);
    } catch (err) {
      // A game in setup has no round yet; that isn't an error worth shouting about.
      if (err.response?.status !== 404) {
        message.error(err.response?.data?.error || 'Could not load round status');
      }
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while a round is mid-processing so the console reflects progress.
  useEffect(() => {
    const status = data?.round?.processing_status;
    const active = status === 'PROCESSING' || status === 'RESULTS_AVAILABLE';
    if (!active) return undefined;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [data?.round?.processing_status, load]);

  // Keep the countdown honest without hammering the API.
  useEffect(() => {
    if (!data?.round?.deadline) return undefined;
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [data?.round?.deadline, load]);

  const run = async (key, fn, confirmMsg) => {
    setBusy(key);
    try {
      const res = await fn();
      message.success(res.data?.message || 'Done');
      if (res.data?.warning) message.warning(res.data.warning);
      await load();
      onChanged?.();
    } catch (err) {
      message.error(err.response?.data?.error || confirmMsg || 'Action failed');
    } finally {
      setBusy(null);
    }
  };

  if (!data) {
    return <Card title="Round Control" loading style={{ marginTop: 16 }} />;
  }

  const round = data.round;
  if (!round) {
    return (
      <Card title="Round Control" style={{ marginTop: 16 }}>
        <Alert type="info" showIcon
          message="No round yet"
          description="Activate the game to open Round 1." />
      </Card>
    );
  }

  const next = round.next_action;
  const remaining = formatRemaining(round.seconds_remaining);
  const gamePaused = data.game_status === 'paused';

  return (
    <Card
      title={`Round Control — Round ${round.round_number} of ${data.total_rounds ?? '—'}`}
      style={{ marginTop: 16 }}
      extra={<Button size="small" onClick={load} loading={loading}>Refresh</Button>}
    >
      {gamePaused && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message="Game is paused"
          description="Students cannot submit or change anything while the game is paused. The deadline is also on hold — it will not close the round until you resume." />
      )}

      <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }} bordered
        style={{ marginBottom: 16 }}>
        <Descriptions.Item label="Round status">
          <Tag color={STATUS_COLOUR[round.status] || 'default'}>{round.status}</Tag>
          {round.close_reason && (
            <Text type="secondary">
              {round.close_reason === 'deadline' ? 'closed by deadline' : 'closed by instructor'}
            </Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Deadline">
          {round.deadline ? (
            <Space direction="vertical" size={0}>
              <Text>{new Date(round.deadline).toLocaleString()}</Text>
              <Text type={round.is_overdue ? 'danger' : 'secondary'}>{remaining}</Text>
            </Space>
          ) : (
            <Text type="warning">Not set — this round will never close on its own</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Decisions in">
          <Text>{round.teams_locked} / {round.teams_total}</Text>
          {round.teams_pending > 0 && (
            <Text type="secondary"> ({round.teams_pending} still out)</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Processing" span={3}>
          {PROCESSING_LABEL[round.processing_status] || round.processing_status}
          {round.phase_1_duration != null && (
            <Text type="secondary"> — scoring took {round.phase_1_duration.toFixed(1)}s</Text>
          )}
          {round.narrative_error && (
            <Alert type="warning" showIcon style={{ marginTop: 8 }}
              message="Narrative generation failed"
              description={`${round.narrative_error} — the numbers are still valid.`} />
          )}
        </Descriptions.Item>
      </Descriptions>

      {round.processing_status === 'PROCESSING' && (
        <Progress percent={100} status="active" showInfo={false} style={{ marginBottom: 12 }} />
      )}

      <Paragraph type="secondary" style={{ marginBottom: 12 }}>
        A round closes at its deadline (or when you close it), then you run
        post-round processing, then you advance. Processing and advancing are
        separate so you can check the results before the game moves on.
      </Paragraph>

      <Space wrap>
        <Button onClick={() => { setDeadlineValue(round.deadline ? dayjs(round.deadline) : null); setDeadlineOpen(true); }}>
          {round.deadline ? 'Change deadline' : 'Set deadline'}
        </Button>

        {round.status === 'open' && (
          <Popconfirm
            title="Close this round now?"
            description="Students will be locked out immediately and all decisions submitted as they stand."
            onConfirm={() => run('close', () => closeRound(gameId))}
          >
            <Button danger={round.is_overdue} type={next === 'close' ? 'primary' : 'default'}
              loading={busy === 'close'}>
              Close round now
            </Button>
          </Popconfirm>
        )}

        {round.status === 'closed' && (
          <>
            <Popconfirm
              title="Run post-round processing?"
              description="Scores events, R&D, adoption, revenue, costs, financial statements, performance index and the leaderboard. Takes a few seconds."
              onConfirm={() => run('process', () => processRound(gameId))}
            >
              <Button type="primary" loading={busy === 'process'}>
                Run post-round processing
              </Button>
            </Popconfirm>
            <Button onClick={() => { setReopenValue(null); setReopenOpen(true); }}>
              Reopen round
            </Button>
          </>
        )}

        {round.status === 'processed' && (
          <Popconfirm
            title={data.current_round >= data.total_rounds
              ? 'Finish the game?'
              : `Advance to round ${round.round_number + 1}?`}
            description="Students will start the next round."
            onConfirm={() => run('advance', () => advanceToNextRound(gameId))}
          >
            <Button type="primary" loading={busy === 'advance'}>
              {data.current_round >= data.total_rounds
                ? 'Finish game'
                : `Advance to round ${round.round_number + 1}`}
            </Button>
          </Popconfirm>
        )}

        {round.status === 'open' && (
          <Popconfirm
            title="Close and process in one step?"
            description="Skips the review pause. Use when you're sure the round is done."
            onConfirm={() => run('force', () => processRound(gameId, true))}
          >
            <Button loading={busy === 'force'}>Close &amp; process now</Button>
          </Popconfirm>
        )}
      </Space>

      <Modal
        title="Set round deadline"
        open={deadlineOpen}
        onCancel={() => setDeadlineOpen(false)}
        onOk={async () => {
          await run('deadline', () => setRoundDeadline(gameId, {
            deadline: deadlineValue ? deadlineValue.toISOString() : null,
          }));
          setDeadlineOpen(false);
        }}
        okText="Save deadline"
      >
        <Paragraph type="secondary">
          The round closes automatically at this time and students are locked
          out. Clear it to let the round run until you close it by hand.
        </Paragraph>
        <DatePicker showTime style={{ width: '100%' }}
          value={deadlineValue} onChange={setDeadlineValue} />
        <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
          Times are in your local timezone. Server time is currently{' '}
          {new Date(data.server_time).toLocaleString()}.
        </Paragraph>
      </Modal>

      <Modal
        title="Reopen round"
        open={reopenOpen}
        onCancel={() => setReopenOpen(false)}
        onOk={async () => {
          if (!reopenValue) {
            message.error('Pick a new deadline, or the round will close again straight away.');
            return;
          }
          await run('reopen', () => reopenRound(gameId, reopenValue.toISOString()));
          setReopenOpen(false);
        }}
        okText="Reopen round"
      >
        <Paragraph>
          This unlocks every team's decisions and lets students edit again.
        </Paragraph>
        <Paragraph type="secondary">
          Give the round a new deadline in the future — otherwise the old one
          is still in the past and the round would close again within a minute.
        </Paragraph>
        <DatePicker showTime style={{ width: '100%' }}
          value={reopenValue} onChange={setReopenValue} />
      </Modal>
    </Card>
  );
}
