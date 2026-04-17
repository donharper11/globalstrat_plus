import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Typography, Table, Tag, Empty } from 'antd';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { useGame } from '../contexts/GameContext';
import { getLeaderboard, getLeaderboardHistory } from '../api/results';
import RoundSelector from '../components/RoundSelector';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Title } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const COLORS = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16'];

const LeaderboardPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, game } = useGame();
  const latestProcessed = Math.max((game?.current_round || 1) - 1, 0);
  const [selectedRound, setSelectedRound] = useState(latestProcessed);
  const [leaderboard, setLeaderboard] = useState(null);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async (rnd) => {
    if (!gameId || rnd < 0) { setLoading(false); return; }
    setLoading(true);
    try {
      const [resL, resH] = await Promise.all([
        getLeaderboard(gameId, rnd),
        getLeaderboardHistory(gameId),
      ]);
      setLeaderboard(resL.data);
      setHistory(resH.data);
    } catch { /* empty */ }
    setLoading(false);
  }, [gameId]);

  useEffect(() => {
    if (latestProcessed >= 0 && selectedRound < 0) setSelectedRound(latestProcessed);
  }, [latestProcessed, selectedRound]);

  useEffect(() => { loadData(selectedRound); }, [selectedRound, loadData]);

  if (loading) return <LoadingSpinner />;

  if (latestProcessed < 0) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Empty description={t("leaderboard_page.no_rankings")} />
      </div>
    );
  }

  const rankings = leaderboard?.rankings || [];
  const markets = rankings.length > 0 ? Object.keys(rankings[0]?.market_share || {}) : [];

  const columns = [
    { title: t('leaderboard_page.rank'), dataIndex: 'rank', width: 60, sorter: (a, b) => a.rank - b.rank },
    {
      title: t('leaderboard_page.team'), dataIndex: 'team_name',
      render: (v, r) => r.team_id === teamId ? <strong>{v}</strong> : v,
    },
    { title: t('leaderboard_page.index'), dataIndex: 'performance_index', sorter: (a, b) => a.performance_index - b.performance_index,
      render: v => v?.toFixed(2) },
    { title: t('leaderboard_page.change'), dataIndex: 'index_change', sorter: (a, b) => a.index_change - b.index_change,
      render: v => <Tag color={v >= 0 ? 'green' : 'red'}>{v >= 0 ? '+' : ''}{v?.toFixed(2)}</Tag> },
    { title: t('leaderboard_page.revenue'), dataIndex: 'total_revenue', sorter: (a, b) => a.total_revenue - b.total_revenue,
      render: fmt },
    { title: t('leaderboard_page.net_income'), dataIndex: 'net_income', sorter: (a, b) => a.net_income - b.net_income,
      render: v => <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>{fmt(v)}</span> },
    { title: t('leaderboard_page.return'), dataIndex: 'shareholder_return', sorter: (a, b) => a.shareholder_return - b.shareholder_return,
      render: v => `${(Number(v || 0) * 100).toFixed(1)}%` },
    ...markets.map(m => ({
      title: `${m} ${t('leaderboard_page.share')}`,
      dataIndex: ['market_share', m],
      render: v => v != null ? `${(Number(v) * 100).toFixed(0)}%` : '—',
    })),
  ];

  // Build trend chart data
  const buildTrendData = (field) => {
    if (!history) return [];
    return (history.rounds || []).map((rnd, i) => {
      const point = { round: `R${rnd}` };
      (history.teams || []).forEach(t => {
        point[t.team_name] = t[field]?.[i] ?? null;
      });
      return point;
    });
  };

  const teamNames = (history?.teams || []).map(t => t.team_name);

  const TrendChart = ({ data, title, formatter }) => {
    const { t } = useTranslation();
    return (
    <PanelCard headerColor="results" title={title.toUpperCase()} style={{ marginTop: 16 }}>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="round" />
          <YAxis tickFormatter={formatter || (v => v)} />
          <Tooltip formatter={formatter || (v => v)} />
          <Legend />
          {teamNames.map((name, i) => (
            <Line
              key={name}
              dataKey={name}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={history?.teams?.[i]?.team_id === teamId ? 3 : 1.5}
              dot={history?.teams?.[i]?.team_id === teamId}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </PanelCard>
  );
  };

  return (
    <div>
      <PageHeader
        title={t("leaderboard_page.title")}
        subtitle={`${t("common.round")} ${selectedRound} · ${t("leaderboard_page.team_rankings")}`}
        actions={
          <RoundSelector
            currentRound={selectedRound}
            maxRound={latestProcessed}
            minRound={0}
            onChange={setSelectedRound}
          />
        }
      />

      <PanelCard headerColor="results" title={t("leaderboard_page.rankings").toUpperCase()}>
        <Table
          dataSource={rankings}
          rowKey="team_id"
          columns={columns}
          pagination={false}
          rowClassName={(r) => r.team_id === teamId ? 'ant-table-row-selected' : ''}
        />
      </PanelCard>

      <TrendChart
        data={buildTrendData('index_history')}
        title={t("leaderboard_page.performance_index_trend")}
      />
      <TrendChart
        data={buildTrendData('revenue_history')}
        title={t("leaderboard_page.revenue_trend")}
        formatter={fmt}
      />
      <TrendChart
        data={buildTrendData('share_price_history')}
        title={t("leaderboard_page.share_price_trend")}
        formatter={v => `$${Number(v).toFixed(2)}`}
      />
    </div>
  );
};

export default LeaderboardPage;
