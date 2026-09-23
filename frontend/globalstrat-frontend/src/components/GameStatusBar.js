import React from 'react';
import { Tag, Space, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';

const { Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  // W-CE2-09: magnitude decides the unit, the sign is carried. Testing
  // `n >= 1e6` sent every negative figure to `toFixed(0)`, which is how
  // the Summary printed `$-12553689` beside `$28.5M`.
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const roundStatusLabel = (roundStatus, locked, t) => {
  if (roundStatus === 'processed') return { text: t('game_status.results_available'), color: 'purple' };
  if (locked) return { text: t('game_status.locked'), color: 'green' };
  if (roundStatus === 'open' || roundStatus === 'in_progress') return { text: t('game_status.draft_open'), color: 'blue' };
  if (roundStatus === 'closed') return { text: t('game_status.round_closed'), color: 'orange' };
  if (roundStatus === 'pending') return { text: t('game_status.not_open'), color: 'default' };
  return { text: t('game_status.unknown'), color: 'default' };
};

const GameStatusBar = () => {
  const { t } = useTranslation();
  const { team, currentRound, totalRounds, roundStatus, budgets } = useGame();
  const { locked, saving, lastSaved, saveError } = useDecisions();

  const status = roundStatusLabel(roundStatus, locked, t);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '6px 20px',
      background: '#F8FAFC',
      borderBottom: '1px solid #E2E8F0',
      fontSize: 12,
      flexWrap: 'wrap',
      gap: 8,
    }}>
      <Space size={16}>
        <Text strong>{t('game_status.round_of', { current: currentRound || '—', total: totalRounds || '—' })}</Text>
        <Tag color={status.color}>{status.text}</Tag>
        <Text>{t('game_status.team', { name: team?.name || '—' })}</Text>
      </Space>
      <Space size={16}>
        {budgets && (
          <>
            <Text type="secondary">{t('topbar.rd_label')} {fmt(budgets.rd_spent)}/{fmt(budgets.rd_allocated)}</Text>
            <Text type="secondary">{t('topbar.mktg_label')} {fmt(budgets.marketing_spent)}/{fmt(budgets.marketing_allocated)}</Text>
            <Text type="secondary">{t('topbar.strat_label')} {fmt(budgets.strategy_spent)}/{fmt(budgets.strategy_allocated)}</Text>
          </>
        )}
        {saving && <Text type="warning">{t('game_status.saving')}</Text>}
        {/* R17: `lastSaved` records the last save that SUCCEEDED and is never
            cleared, so after one good save and then a refusal this went on
            reporting "Saved 14:32" while the edit on screen was unsaved. The
            outstanding refusal now takes precedence over the stale timestamp.
            (This component is currently imported by nothing -- see
            DecisionSaveAlert, which is the mounted surface -- but the
            indicator must not be left stating something false.) */}
        {!saving && saveError && (
          <Text type="danger">{t('game_status.not_saved')}</Text>
        )}
        {!saving && !saveError && lastSaved && (
          <Text type="secondary">{t('game_status.saved', { time: lastSaved.toLocaleTimeString() })}</Text>
        )}
      </Space>
    </div>
  );
};

export default GameStatusBar;
