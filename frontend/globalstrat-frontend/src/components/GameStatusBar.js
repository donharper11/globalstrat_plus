import React from 'react';
import { Tag, Space, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';

const { Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const GameStatusBar = () => {
  const { t } = useTranslation();
  const { team, currentRound, budgets } = useGame();
  const { locked, saving, lastSaved } = useDecisions();

  const statusColor = locked ? 'green' : 'blue';
  const statusText = locked ? t('game_status.locked') : t('game_status.in_progress');

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
        <Text strong>{t('game_status.round_of', { current: currentRound || '—', total: 8 })}</Text>
        <Tag color={statusColor}>{statusText}</Tag>
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
        {!saving && lastSaved && (
          <Text type="secondary">{t('game_status.saved', { time: lastSaved.toLocaleTimeString() })}</Text>
        )}
      </Space>
    </div>
  );
};

export default GameStatusBar;
