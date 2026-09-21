import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Button, Card, DatePicker, Descriptions, Input, Modal, Popconfirm,
  Progress, Space, Tag, Typography, message,
} from 'antd';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';

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

function formatRemaining(seconds, t) {
  if (seconds === null || seconds === undefined) return null;
  const overdue = seconds < 0;
  const s = Math.abs(seconds);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const parts = [];
  if (d) parts.push(t('instructor.rc_unit_days', { n: d }));
  if (h || d) parts.push(t('instructor.rc_unit_hours', { n: h }));
  parts.push(t('instructor.rc_unit_minutes', { n: m }));
  const time = parts.join(' ');
  if (overdue) return t('instructor.rc_time_overdue', { time });
  return t('instructor.rc_time_remaining', { time });
}

/**
 * Drives the round lifecycle: open -> closed -> processed -> next round open.
 *
 * The backend reports which action comes next, so the console offers exactly
 * one primary button at a time rather than a row of buttons that may not
 * apply.
 */
export default function RoundControlCard({ gameId, onChanged }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(null);
  const [deadlineOpen, setDeadlineOpen] = useState(false);
  const [deadlineValue, setDeadlineValue] = useState(null);
  const [reopenOpen, setReopenOpen] = useState(false);
  const [reopenValue, setReopenValue] = useState(null);
  const [forceOpen, setForceOpen] = useState(false);
  const [forceReason, setForceReason] = useState('');

  const load = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    try {
      const res = await getRoundControl(gameId);
      setData(res.data);
    } catch (err) {
      // A game in setup has no round yet; that isn't an error worth shouting about.
      if (err.response?.status !== 404) {
        message.error(err.response?.data?.error || t('instructor.rc_load_failed'));
      }
    } finally {
      setLoading(false);
    }
  }, [gameId, t]);

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
      message.success(res.data?.message || t('instructor.rc_done'));
      if (res.data?.warning) message.warning(res.data.warning);
      await load();
      onChanged?.();
    } catch (err) {
      const body = err.response?.data;
      // A 409 means another operator or the deadline scheduler moved the round
      // under us. Say so, show the guidance the API sent, and refresh — the
      // console is now showing a state that no longer exists.
      const conflict = err.response?.status === 409;
      const text = [body?.error || confirmMsg || t('instructor.rc_action_failed'), body?.guidance]
        .filter(Boolean)
        .join(' ');
      if (conflict) {
        message.warning(text, 6);
        await load();
        onChanged?.();
      } else {
        message.error(text, 6);
      }
    } finally {
      setBusy(null);
    }
  };

  if (!data) {
    return <Card title={t('instructor.rc_title')} loading style={{ marginTop: 16 }} />;
  }

  const round = data.round;
  if (!round) {
    return (
      <Card title={t('instructor.rc_title')} style={{ marginTop: 16 }}>
        <Alert type="info" showIcon
          message={t('instructor.rc_no_round')}
          description={t('instructor.rc_no_round_hint')} />
      </Card>
    );
  }

  const next = round.next_action;
  const remaining = formatRemaining(round.seconds_remaining, t);
  const gamePaused = data.game_status === 'paused';
  // One t() per key: the string gate cannot resolve a key chosen at run time.
  const statusLabel = {
    open: t('instructor.rc_status_open'),
    closed: t('instructor.rc_status_closed'),
    processed: t('instructor.rc_status_processed'),
    pending: t('instructor.rc_status_pending'),
  };
  const processingLabel = {
    PENDING: t('instructor.rc_processing_pending'),
    PROCESSING: t('instructor.rc_processing_running'),
    RESULTS_AVAILABLE: t('instructor.rc_processing_results'),
    FULLY_COMPLETE: t('instructor.rc_processing_complete'),
    FAILED: t('instructor.rc_processing_failed'),
  };

  return (
    <Card
      title={t('instructor.round_control_title', {
        game: data.game_name || t('instructor.game'),
        round: round.round_number,
        total: data.total_rounds ?? '—',
      })}
      style={{ marginTop: 16 }}
      extra={<Button size="small" onClick={load} loading={loading}>{t('instructor.rc_refresh')}</Button>}
    >
      {gamePaused && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message={t('instructor.rc_paused')}
          description={t('instructor.rc_paused_hint')} />
      )}

      <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }} bordered
        style={{ marginBottom: 16 }}>
        <Descriptions.Item label={t('instructor.rc_round_status')}>
          <Tag color={STATUS_COLOUR[round.status] || 'default'}>
            {statusLabel[round.status] || round.status}
          </Tag>
          {round.close_reason && (
            <Text type="secondary">
              {round.close_reason === 'deadline'
                ? t('instructor.rc_closed_by_deadline')
                : t('instructor.rc_closed_by_instructor')}
            </Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t('instructor.rc_deadline')}>
          {round.deadline ? (
            <Space direction="vertical" size={0}>
              <Text>{new Date(round.deadline).toLocaleString()}</Text>
              <Text type={round.is_overdue ? 'danger' : 'secondary'}>{remaining}</Text>
            </Space>
          ) : (
            <Text type="warning">{t('instructor.rc_deadline_not_set')}</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t('instructor.rc_decisions_in')}>
          <Text>{round.teams_locked} / {round.teams_total}</Text>
          {round.teams_pending > 0 && (
            <Text type="secondary">{' '}{t('instructor.rc_still_out', { n: round.teams_pending })}</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t('instructor.rc_processing')} span={3}>
          {processingLabel[round.processing_status] || round.processing_status}
          {round.phase_1_duration != null && (
            <Text type="secondary">{' '}{t('instructor.rc_scoring_took', { seconds: round.phase_1_duration.toFixed(1) })}</Text>
          )}
          {round.narrative_error && (
            <Alert type="warning" showIcon style={{ marginTop: 8 }}
              message={t('instructor.rc_narrative_failed')}
              description={t('instructor.rc_narrative_failed_hint', { error: round.narrative_error })} />
          )}
        </Descriptions.Item>
      </Descriptions>

      {round.processing_status === 'PROCESSING' && (
        <Progress percent={100} status="active" showInfo={false} style={{ marginBottom: 12 }} />
      )}

      <Paragraph type="secondary" style={{ marginBottom: 12 }}>
        {t('instructor.rc_lifecycle_hint')}
      </Paragraph>

      <Space wrap>
        <Button onClick={() => { setDeadlineValue(round.deadline ? dayjs(round.deadline) : null); setDeadlineOpen(true); }}>
          {round.deadline ? t('instructor.rc_change_deadline') : t('instructor.rc_set_deadline')}
        </Button>

        {round.status === 'open' && (
          <Popconfirm
            title={t('instructor.close_round_confirm', {
              game: data.game_name || t('instructor.game'),
              round: round.round_number,
            })}
            description={t('instructor.rc_close_hint')}
            onConfirm={() => run('close', () => closeRound(gameId, round))}
          >
            <Button danger={round.is_overdue} type={next === 'close' ? 'primary' : 'default'}
              loading={busy === 'close'}>
              {t('instructor.rc_close_now')}
            </Button>
          </Popconfirm>
        )}

        {round.status === 'closed' && (
          <>
            <Popconfirm
              title={t('instructor.process_round_confirm', {
                game: data.game_name || t('instructor.game'),
                round: round.round_number,
              })}
              description={t('instructor.rc_process_hint')}
              onConfirm={() => run('process', () => processRound(gameId, false, round))}
            >
              <Button type="primary" loading={busy === 'process'}>
                {t('instructor.rc_process')}
              </Button>
            </Popconfirm>
            <Button onClick={() => { setReopenValue(null); setReopenOpen(true); }}>
              {t('instructor.rc_reopen')}
            </Button>
          </>
        )}

        {round.status === 'processed' && (
          <Popconfirm
            title={data.current_round >= data.total_rounds
              ? t('instructor.finish_game_confirm', {
                game: data.game_name || t('instructor.game'),
              })
              : t('instructor.advance_round_confirm', {
                game: data.game_name || t('instructor.game'),
                round: round.round_number + 1,
              })}
            description={t('instructor.rc_advance_hint')}
            onConfirm={() => run('advance', () => advanceToNextRound(gameId))}
          >
            <Button type="primary" loading={busy === 'advance'}>
              {data.current_round >= data.total_rounds
                ? t('instructor.rc_finish_game')
                : t('instructor.rc_advance_to', { round: round.round_number + 1 })}
            </Button>
          </Popconfirm>
        )}

        {round.status === 'open' && (
          <Button loading={busy === 'force'} onClick={() => setForceOpen(true)}>
            {t('instructor.rc_close_and_process')}
          </Button>
        )}
      </Space>

      <Modal
        title={t('instructor.close_and_process_title', {
          game: data.game_name || t('instructor.game'),
        })}
        open={forceOpen}
        onCancel={() => setForceOpen(false)}
        okText={t('instructor.rc_close_and_process_ok')}
        okButtonProps={{ danger: true, disabled: forceReason.trim().length < 10 }}
        onOk={async () => {
          await run('force',
            () => processRound(gameId, true, round, forceReason.trim()));
          setForceOpen(false);
          setForceReason('');
        }}
      >
        <Paragraph type="secondary">
          {t('instructor.rc_force_hint')}
        </Paragraph>
        <Input.TextArea
          rows={3}
          value={forceReason}
          onChange={(e) => setForceReason(e.target.value)}
          placeholder={t('instructor.rc_force_reason_placeholder')}
        />
      </Modal>

      <Modal
        title={t('instructor.set_deadline_title', {
          game: data.game_name || t('instructor.game'),
        })}
        open={deadlineOpen}
        onCancel={() => setDeadlineOpen(false)}
        onOk={async () => {
          await run('deadline', () => setRoundDeadline(gameId, {
            deadline: deadlineValue ? deadlineValue.toISOString() : null,
          }, round));
          setDeadlineOpen(false);
        }}
        okText={t('instructor.rc_save_deadline')}
      >
        <Paragraph type="secondary">
          {t('instructor.rc_deadline_hint')}
        </Paragraph>
        <DatePicker showTime style={{ width: '100%' }}
          value={deadlineValue} onChange={setDeadlineValue} />
        <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
          {t('instructor.rc_timezone_hint', {
            time: new Date(data.server_time).toLocaleString(),
          })}
        </Paragraph>
      </Modal>

      <Modal
        title={t('instructor.reopen_round_title', {
          game: data.game_name || t('instructor.game'),
          round: round.round_number,
        })}
        open={reopenOpen}
        onCancel={() => setReopenOpen(false)}
        onOk={async () => {
          if (!reopenValue) {
            message.error(t('instructor.rc_reopen_needs_deadline'));
            return;
          }
          await run('reopen', () => reopenRound(gameId, reopenValue.toISOString(), round));
          setReopenOpen(false);
        }}
        okText={t('instructor.rc_reopen')}
      >
        <Paragraph>
          {t('instructor.rc_reopen_hint')}
        </Paragraph>
        <Paragraph type="secondary">
          {t('instructor.rc_reopen_deadline_hint')}
        </Paragraph>
        <DatePicker showTime style={{ width: '100%' }}
          value={reopenValue} onChange={setReopenValue} />
      </Modal>
    </Card>
  );
}
