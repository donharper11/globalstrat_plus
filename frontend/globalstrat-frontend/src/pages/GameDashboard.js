import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Typography, Row, Col, Tag, Space, Statistic, Button, Progress, Alert,
  Tabs, Table, Collapse, Empty, Modal,
} from 'antd';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Area, AreaChart,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useAuth } from '../AuthContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getDecisionSummary } from '../api/decisions';
import { getBalancedScorecard, getRoundResults, getLeaderboard, getCompetitorIntel, getLatestBriefing, getRoundBriefing, markBriefingRead } from '../api/results';
import { getFinancialHistory } from '../api/cc15';
import { PanelCard, MetricRow, PageHeader, StatusBadge } from '../components/design-system';
import BudgetBar from '../components/BudgetBar';
import CoherenceGauge from '../components/CoherenceGauge';
import RoundSelector from '../components/RoundSelector';
import LoadingSpinner from '../components/LoadingSpinner';
import InvestorProfilePopover, { InvestorNameLink, InvestorSummaryCard } from '../components/InvestorProfilePopover';
import OnboardingModal from '../components/OnboardingModal';
import { getInvestorRelations } from '../api/results';
import SupplyChainPanel from '../components/sc/SupplyChainPanel';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`;

const fitColor = (v) => {
  const n = Number(v);
  if (n >= 0.6) return '#4CAF50';
  if (n >= 0.3) return '#FF9800';
  return '#F44336';
};

const MetricBox = ({ title, value, bar, barColor, hint, valueStyle, sparkData, sparkColor }) => (
  <div style={{ textAlign: 'center' }}>
    <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>{title}</Text>
    <Text strong style={{ fontSize: 20, lineHeight: 1.1, ...valueStyle }}>{value}</Text>
    {bar != null && (
      <div style={{ margin: '6px auto 2px', width: '80%', height: 8, background: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{
          width: `${Math.min(Math.max(bar, 0), 100)}%`,
          height: '100%',
          background: barColor || '#1677ff',
          borderRadius: 4,
          transition: 'width 0.5s ease',
        }} />
      </div>
    )}
    {sparkData && sparkData.length > 1 && (
      <div style={{ margin: '4px auto 0', width: '90%', height: 30 }}>
        <ResponsiveContainer width="100%" height={30}>
          <AreaChart data={sparkData}>
            <defs>
              <linearGradient id={`spark-${title}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={sparkColor || '#1677ff'} stopOpacity={0.3} />
                <stop offset="100%" stopColor={sparkColor || '#1677ff'} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="v" stroke={sparkColor || '#1677ff'} strokeWidth={1.5} fill={`url(#spark-${title})`} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    )}
    {hint && <Text type="secondary" style={{ fontSize: 10, display: 'block' }}>{hint}</Text>}
  </div>
);

const SHARE_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

const HeroGauge = ({ value, label }) => {
  const numVal = Number(value) || 0;
  const angle = Math.min(numVal / 100, 1) * 180;
  const gaugeColor = numVal >= 60 ? '#10B981' : numVal >= 40 ? '#F59E0B' : '#EF4444';
  return (
    <div style={{ textAlign: 'center' }}>
      <svg viewBox="0 0 200 120" width="180" height="108">
        <defs>
          <linearGradient id="gauge-bg" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#f0f0f0" />
            <stop offset="100%" stopColor="#e8e8e8" />
          </linearGradient>
          <linearGradient id="gauge-fill" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={gaugeColor} stopOpacity="0.7" />
            <stop offset="100%" stopColor={gaugeColor} />
          </linearGradient>
        </defs>
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#gauge-bg)" strokeWidth="16" strokeLinecap="round" />
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#gauge-fill)" strokeWidth="16" strokeLinecap="round"
          strokeDasharray={`${(angle / 180) * 251.3} 251.3`} />
        <text x="100" y="90" textAnchor="middle" fontFamily="Rajdhani, sans-serif" fontWeight="700" fontSize="36" fill="var(--color-text-primary, #1a1a1a)">
          {numVal.toFixed(1)}
        </text>
        <text x="100" y="112" textAnchor="middle" fontSize="12" fill="#888">{label}</text>
      </svg>
    </div>
  );
};

const SignalItem = ({ signal }) => {
  const color = signal.type === 'alert' ? '#ff4d4f' : signal.type === 'warning' ? '#faad14' : '#1677ff';
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'flex-start' }}>
      <Tag color={color} style={{ minWidth: 22, textAlign: 'center', flexShrink: 0 }}>!</Tag>
      <Text style={{ fontSize: 12 }}>{signal.text}</Text>
    </div>
  );
};

const GameDashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { game, team, currentRound, budgets, gameId, teamId, loading } = useGame();
  const { user } = useAuth();
  const { locked } = useDecisions();
  const [summary, setSummary] = useState(null);
  const [scorecard, setScorecard] = useState(null);
  const [results, setResults] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [competitors, setCompetitors] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [finHistory, setFinHistory] = useState([]);
  const [briefing, setBriefing] = useState(null);
  const [briefingRead, setBriefingRead] = useState(true);
  const [showBriefingSplash, setShowBriefingSplash] = useState(false);
  const [investorData, setInvestorData] = useState(null);
  const [activeFund, setActiveFund] = useState(null);
  const [showInvestorSummary, setShowInvestorSummary] = useState(false);

  const base = gameId && teamId ? `/games/${gameId}/teams/${teamId}` : '';
  const latestProcessed = Math.max((currentRound || 1) - 1, 0);
  const [selectedRound, setSelectedRound] = useState(null);

  useEffect(() => {
    if (currentRound != null && selectedRound === null) {
      setSelectedRound(latestProcessed);
    }
  }, [currentRound, latestProcessed, selectedRound]);

  // Fetch briefing + per-user read status
  useEffect(() => {
    if (!gameId || !teamId || !user?.user_id) return;
    getLatestBriefing(gameId, teamId, user.user_id)
      .then(res => {
        const b = res.data?.briefing;
        const isRead = res.data?.is_read;
        setBriefing(b);
        setBriefingRead(isRead);
        if (b && !isRead) {
          setShowBriefingSplash(true);
        }
      })
      .catch(() => {});
  }, [gameId, teamId, user?.user_id]);

  const handleDismissBriefing = useCallback(() => {
    setShowBriefingSplash(false);
    if (briefing && user?.user_id) {
      markBriefingRead(gameId, teamId, briefing.id, user.user_id).catch(() => {});
      setBriefingRead(true);
    }
  }, [briefing, gameId, teamId, user?.user_id]);

  useEffect(() => {
    if (!gameId || !teamId || !currentRound) return;
    getDecisionSummary(gameId, teamId, currentRound)
      .then(res => setSummary(res.data))
      .catch(() => {});
    getBalancedScorecard(gameId, teamId)
      .then(res => setScorecard(res.data))
      .catch(() => {});
    getFinancialHistory(gameId, teamId)
      .then(res => setFinHistory(res.data?.rounds || []))
      .catch(() => {});
    getInvestorRelations(gameId, teamId, {})
      .then(res => setInvestorData(res.data))
      .catch(() => {});
  }, [gameId, teamId, currentRound]);

  const loadRoundResults = useCallback(async (rnd) => {
    if (!gameId || !teamId || rnd == null || rnd < 0) return;
    setResultsLoading(true);
    try {
      const [resR, resL, resC] = await Promise.all([
        getRoundResults(gameId, teamId, rnd),
        getLeaderboard(gameId, rnd),
        getCompetitorIntel(gameId, teamId, rnd),
      ]);
      setResults(resR.data);
      setLeaderboard(resL.data);
      setCompetitors(resC.data);
    } catch { /* empty */ }
    setResultsLoading(false);
  }, [gameId, teamId]);

  useEffect(() => { loadRoundResults(selectedRound); }, [selectedRound, loadRoundResults]);

  if (loading) return <LoadingSpinner />;

  const categories = summary?.categories || {};
  const statusColor = (s) => {
    if (s === 'configured') return 'green';
    if (s === 'partial') return 'orange';
    if (s === 'error') return 'red';
    return 'default';
  };

  const decisionPages = [
    { key: 'rd', label: t('dashboard.step_rd'), path: `${base}/decisions/rd` },
    { key: 'products', label: t('dashboard.step_products'), path: `${base}/decisions/products` },
    { key: 'marketing', label: t('dashboard.step_marketing'), path: `${base}/decisions/marketing` },
    { key: 'strategy', label: t('dashboard.step_strategy'), path: `${base}/decisions/corporate-strategy` },
    { key: 'finance', label: t('dashboard.step_finance'), path: `${base}/decisions/finance`, altKey: 'budget' },
    { key: 'summary', label: t('dashboard.step_review'), path: `${base}/decisions/summary` },
  ];

  // === Scorecard data ===
  const fin = scorecard?.financial || {};
  const cust = scorecard?.customer || {};
  const cap = scorecard?.capability || {};
  const grw = scorecard?.growth || {};
  const signals = scorecard?.signals || [];
  const talent = cap.talent || {};

  const marginColor = fin.net_margin >= 0.1 ? '#52c41a' : fin.net_margin >= 0 ? '#faad14' : '#ff4d4f';
  const deColor = fin.debt_to_equity < 1 ? '#52c41a' : fin.debt_to_equity < 2 ? '#faad14' : '#ff4d4f';

  // === Results data ===
  const perf = results?.performance || {};
  const resFin = results?.financials || {};
  const coherence = results?.coherence || {};
  const rankings = leaderboard?.rankings || [];
  const myRank = rankings.find(r => r.team_id === teamId);

  // Build sparkline data from financial history
  const revenueSpark = finHistory.map(r => ({ r: `R${r.round_number}`, v: Number(r.total_revenue || 0) }));
  const cashSpark = finHistory.map(r => ({ r: `R${r.round_number}`, v: Number(r.cash_closing || 0) }));
  const marginSpark = finHistory.map(r => ({ r: `R${r.round_number}`, v: Number(r.net_margin_pct || 0) * 100 }));

  // Market share data for pie chart
  const marketShareData = (results?.markets || [])
    .filter(m => m.market_share_pct > 0)
    .map(m => ({ name: m.market_name, value: Math.round(Number(m.market_share_pct) * 100) }));

  // Revenue by market for bar chart
  const revenueByMarket = (results?.markets || [])
    .filter(m => m.home_revenue > 0)
    .map(m => ({ name: m.market_name, revenue: Number(m.home_revenue), profit: Number(m.market_profit || 0) }));

  // ─── Tab: Balanced Scorecard ───
  const ScorecardOverview = () => {
    const { t } = useTranslation();
    return (
    <div>
      {/* Hero row — Performance Index gauge + key metrics */}
      {scorecard && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={24} md={8}>
            <PanelCard title={t('dashboard.performance_index')} headerColor="strategic">
              <HeroGauge
                value={perf.index_value || fin.share_price || 55}
                label={myRank ? `#${myRank.rank} ${t('dashboard.of')} ${rankings.length}` : t('dashboard.leaderboard')}
              />
            </PanelCard>
          </Col>
          <Col xs={24} md={8}>
            <PanelCard title={t('dashboard.revenue')} headerColor="financial">
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <Text strong style={{ fontSize: 28, display: 'block' }}>{fmt(fin.revenue)}</Text>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('dashboard.net_margin')}: {pct(fin.net_margin)}</Text>
              </div>
              {revenueSpark.length > 1 && (
                <div style={{ height: 50, marginTop: 4 }}>
                  <ResponsiveContainer width="100%" height={50}>
                    <AreaChart data={revenueSpark}>
                      <defs>
                        <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10B981" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="#10B981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area type="monotone" dataKey="v" stroke="#10B981" strokeWidth={2} fill="url(#revGrad)" dot={false} />
                      <Tooltip formatter={v => fmt(v)} labelFormatter={l => l} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </PanelCard>
          </Col>
          <Col xs={24} md={8}>
            <PanelCard title={t('dashboard.cash_position')} headerColor="financial">
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <Text strong style={{ fontSize: 28, display: 'block', color: fin.cash_position > 20000000 ? undefined : '#cf1322' }}>{fmt(fin.cash_position)}</Text>
                <Text type="secondary" style={{ fontSize: 11 }}>D/E: {fin.debt_to_equity?.toFixed(2) || '0'}</Text>
              </div>
              {cashSpark.length > 1 && (
                <div style={{ height: 50, marginTop: 4 }}>
                  <ResponsiveContainer width="100%" height={50}>
                    <AreaChart data={cashSpark}>
                      <defs>
                        <linearGradient id="cashGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area type="monotone" dataKey="v" stroke="#3B82F6" strokeWidth={2} fill="url(#cashGrad)" dot={false} />
                      <Tooltip formatter={v => fmt(v)} labelFormatter={l => l} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </PanelCard>
          </Col>
        </Row>
      )}

      <div className="panel-grid">
        <PanelCard title={t('dashboard.financial_perspective')} headerColor="financial">
          {scorecard ? (
            <>
              <Row gutter={[16, 16]}>
                <Col xs={6}>
                  <MetricBox title={t('dashboard.revenue')} value={fmt(fin.revenue)}
                    sparkData={revenueSpark} sparkColor="#10B981" />
                </Col>
                <Col xs={6}>
                  <MetricBox title={t('dashboard.net_margin')} value={pct(fin.net_margin)}
                    bar={Math.abs(fin.net_margin) * 100} barColor={marginColor}
                    hint={fin.net_margin >= 0.1 ? t('dashboard.healthy') : fin.net_margin >= 0 ? t('dashboard.thin') : t('dashboard.loss')} />
                </Col>
                <Col xs={6}>
                  <MetricBox title={t('dashboard.cash')} value={fmt(fin.cash_position)}
                    bar={Math.min(fin.cash_position / 100000000 * 100, 100)} barColor="#52c41a"
                    hint={fin.cash_position > 20000000 ? t('dashboard.strong') : t('dashboard.limited')} />
                </Col>
                <Col xs={6}>
                  <MetricBox title={t('dashboard.debt_to_equity')} value={fin.debt_to_equity?.toFixed(2) || '0'}
                    bar={Math.min(fin.debt_to_equity / 3 * 100, 100)} barColor={deColor}
                    hint={fin.debt_to_equity < 1 ? t('dashboard.low') : fin.debt_to_equity < 2 ? t('dashboard.moderate') : t('dashboard.high')} />
                </Col>
              </Row>
              <Row gutter={[16, 8]} style={{ marginTop: 8 }}>
                <Col xs={12}>
                  <div style={{ textAlign: 'center' }}>
                    <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>{t('dashboard.share_price')}</Text>
                    <Text strong style={{ fontSize: 20, lineHeight: 1.1 }}>
                      ${fin.share_price?.toFixed(2) || '0.00'}
                    </Text>
                    {fin.share_price_change_pct != null && (
                      <Text style={{
                        fontSize: 12, marginLeft: 4,
                        color: fin.share_price_change_pct >= 0 ? '#52c41a' : '#ff4d4f',
                      }}>
                        {fin.share_price_change_pct >= 0 ? '▲' : '▼'} {fin.share_price_change_pct >= 0 ? '+' : ''}{fin.share_price_change_pct.toFixed(1)}%
                      </Text>
                    )}
                  </div>
                </Col>
                <Col xs={12}>
                  <div style={{ textAlign: 'center', position: 'relative' }}>
                    <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>
                      {t('dashboard.investor_sentiment')}{' '}
                      <span
                        style={{ cursor: 'pointer', fontSize: 13 }}
                        onClick={() => setShowInvestorSummary(v => !v)}
                        title={t('dashboard.view_ai_summary')}
                      >
                        &#x2139;&#xFE0F;
                      </span>
                    </Text>
                    <Text strong style={{
                      fontSize: 14,
                      color: fin.sentiment_direction === 'buying' ? '#52c41a' : fin.sentiment_direction === 'selling' ? '#ff4d4f' : '#faad14',
                    }}>
                      {fin.sentiment_direction === 'buying' ? `▲ ${t('dashboard.investors_buying')}` : fin.sentiment_direction === 'selling' ? `▼ ${t('dashboard.investors_selling')}` : `— ${t('dashboard.investors_holding')}`}
                    </Text>
                    {showInvestorSummary && investorData?.fund_profiles && (
                      <InvestorSummaryCard
                        fundProfiles={investorData.fund_profiles}
                        onFundClick={(f, e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setShowInvestorSummary(false);
                          setActiveFund({ ...f, _anchorRect: rect });
                        }}
                        onClose={() => setShowInvestorSummary(false)}
                      />
                    )}
                  </div>
                </Col>
              </Row>
              {revenueByMarket.length > 0 && (
                <div style={{ marginTop: 12, height: 120 }}>
                  <ResponsiveContainer width="100%" height={120}>
                    <BarChart data={revenueByMarket} barSize={20}>
                      <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                      <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 10 }} width={50} />
                      <Tooltip formatter={v => fmt(v)} />
                      <Bar dataKey="revenue" fill="#3B82F6" name={t('dashboard.revenue')} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="profit" fill="#10B981" name={t('dashboard.profit')} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          ) : <Text type="secondary">{t('common.loading')}</Text>}
        </PanelCard>

        <PanelCard title={t('dashboard.customer_perspective')} headerColor="market">
          {scorecard ? (
            <>
              <Row gutter={[16, 16]}>
                <Col xs={12}>
                  <MetricBox title={t('dashboard.satisfaction')}
                    value={cust.satisfaction >= 0.7 ? t('dashboard.strong') : cust.satisfaction >= 0.5 ? t('dashboard.moderate') : cust.satisfaction >= 0.3 ? t('dashboard.weak') : t('dashboard.low')}
                    bar={(cust.satisfaction || 0.5) * 100}
                    barColor={cust.satisfaction >= 0.7 ? '#52c41a' : cust.satisfaction >= 0.5 ? '#faad14' : '#ff4d4f'} />
                  <div style={{ marginTop: 8, textAlign: 'center' }}>
                    {cust.top_segment && <Text style={{ fontSize: 11, display: 'block' }}>{t('dashboard.top_segment')}: {cust.top_segment.segment} ({(cust.top_segment.share_pct * 100).toFixed(0)}%)</Text>}
                    {cust.weakest_segment && <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{t('dashboard.weakest_segment')}: {cust.weakest_segment.segment} ({(cust.weakest_segment.share_pct * 100).toFixed(0)}%)</Text>}
                  </div>
                </Col>
                <Col xs={12}>
                  {marketShareData.length > 0 ? (
                    <div style={{ height: 120 }}>
                      <ResponsiveContainer width="100%" height={120}>
                        <PieChart>
                          <Pie data={marketShareData} dataKey="value" cx="50%" cy="50%" innerRadius={25} outerRadius={45} paddingAngle={2}>
                            {marketShareData.map((_, i) => <Cell key={i} fill={SHARE_COLORS[i % SHARE_COLORS.length]} />)}
                          </Pie>
                          <Tooltip formatter={v => `${v}%`} />
                          <Legend wrapperStyle={{ fontSize: 10 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <MetricBox title={t('dashboard.market_share')} value={`${cust.total_market_share || 0}%`} bar={cust.total_market_share || 0} />
                  )}
                </Col>
              </Row>
            </>
          ) : <Text type="secondary">{t('common.loading')}</Text>}
        </PanelCard>

        <PanelCard title={t('dashboard.stakeholder_perspective')} headerColor="strategic">
          {scorecard ? (
            scorecard.stakeholders && scorecard.stakeholders.length > 0 ? (
              <div>
                {scorecard.stakeholders.map(grp => (
                  <div key={grp.type} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <Text strong style={{ fontSize: 12 }}>{grp.label}</Text>
                      <Tag color={grp.avg_satisfaction >= 0.7 ? 'green' : grp.avg_satisfaction >= 0.5 ? 'gold' : 'red'}>
                        {grp.avg_satisfaction >= 0.7 ? t('dashboard.strong') : grp.avg_satisfaction >= 0.5 ? t('dashboard.moderate') : t('dashboard.weak')}
                      </Tag>
                    </div>
                    <div style={{ width: '100%', height: 6, background: '#f0f0f0', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{
                        width: `${(grp.avg_satisfaction || 0) * 100}%`,
                        height: '100%',
                        background: grp.avg_satisfaction >= 0.7 ? '#52c41a' : grp.avg_satisfaction >= 0.5 ? '#faad14' : '#ff4d4f',
                        borderRadius: 3,
                        transition: 'width 0.5s ease',
                      }} />
                    </div>
                    {grp.segments.length > 1 && (
                      <div style={{ marginTop: 4 }}>
                        {grp.segments.map(s => (
                          <Text key={s.name} type="secondary" style={{ fontSize: 10, display: 'block' }}>
                            {s.name} ({s.market}): {(s.satisfaction * 100).toFixed(0)}%
                          </Text>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>{t('dashboard.no_stakeholder_data')}</Text>
            )
          ) : <Text type="secondary">{t('common.loading')}</Text>}
        </PanelCard>

        <PanelCard title={t('dashboard.capability_perspective')} headerColor="strategic">
          {scorecard ? (
            <Row gutter={[16, 16]}>
              <Col xs={6}><MetricBox title={t('dashboard.tech_rating')} value={`${cap.technology_rating_pct}%`} bar={cap.technology_rating_pct} hint={cap.platform_generation} /></Col>
              <Col xs={6}><MetricBox title={t('dashboard.talent_rd')} value={(talent.rd?.level || 3).toFixed(1)} bar={(talent.rd?.level || 3) * 10} barColor={talent.rd?.level >= 5 ? '#52c41a' : '#1677ff'} /></Col>
              <Col xs={6}><MetricBox title={t('dashboard.talent_commercial')} value={(talent.commercial?.level || 3).toFixed(1)} bar={(talent.commercial?.level || 3) * 10} barColor={talent.commercial?.level >= 5 ? '#52c41a' : '#1677ff'} /></Col>
              <Col xs={6}><MetricBox title={t('dashboard.talent_operations')} value={(talent.operations?.level || 3).toFixed(1)} bar={(talent.operations?.level || 3) * 10} barColor={talent.operations?.level >= 5 ? '#52c41a' : '#1677ff'} /></Col>
            </Row>
          ) : <Text type="secondary">{t('common.loading')}</Text>}
        </PanelCard>

        <PanelCard title={t('dashboard.growth_innovation')} headerColor="results">
          {scorecard ? (
            <>
              <Row gutter={[16, 16]}>
                <Col xs={6}><MetricBox title={t('dashboard.rd_pct_revenue')} value={`${grw.rd_as_pct_of_revenue}%`} bar={Math.min(grw.rd_as_pct_of_revenue * 5, 100)} barColor={grw.rd_as_pct_of_revenue >= 5 ? '#52c41a' : '#faad14'} /></Col>
                <Col xs={6}><MetricBox title={t('dashboard.markets_entered')} value={`${grw.markets_entered} / ${grw.total_markets}`} bar={(grw.markets_entered / Math.max(grw.total_markets, 1)) * 100} /></Col>
                <Col xs={6}><MetricBox title={t('dashboard.platform_generation')} value={`Gen ${grw.platform_generation}`} bar={(grw.platform_generation / Math.max(grw.max_generation, 1)) * 100} /></Col>
                <Col xs={6}><MetricBox title={t('dashboard.product_count')} value={grw.product_count} bar={Math.min(grw.product_count * 20, 100)} /></Col>
              </Row>
              {finHistory.length > 1 && (
                <div style={{ marginTop: 12, height: 80 }}>
                  <Text type="secondary" style={{ fontSize: 10, marginBottom: 4, display: 'block' }}>{t('dashboard.net_margin_trend')}</Text>
                  <ResponsiveContainer width="100%" height={60}>
                    <LineChart data={marginSpark}>
                      <XAxis dataKey="r" tick={{ fontSize: 9 }} />
                      <YAxis tick={{ fontSize: 9 }} width={30} tickFormatter={v => `${v}%`} />
                      <Tooltip formatter={v => `${Number(v).toFixed(1)}%`} />
                      <Line type="monotone" dataKey="v" stroke="#8B5CF6" strokeWidth={2} dot={{ r: 3, fill: '#8B5CF6' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          ) : <Text type="secondary">{t('common.loading')}</Text>}
        </PanelCard>
      </div>

      {signals.length > 0 && (
        <PanelCard title={t('dashboard.strategic_signals')} headerColor="neutral">
          {signals.map((s, i) => <SignalItem key={i} signal={s} />)}
        </PanelCard>
      )}

      <div className="panel-grid">
        <PanelCard title={t('dashboard.budget_overview')} headerColor="financial">
          <BudgetBar budgets={budgets} />
        </PanelCard>
        <PanelCard title={t('dashboard.decision_checklist')} headerColor="neutral">
          <Space direction="vertical" style={{ width: '100%' }}>
            {decisionPages.map(p => {
              const cat = categories[p.key] || categories[p.altKey] || {};
              return (
                <div key={p.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Button type="link" onClick={() => navigate(p.path)} style={{ padding: 0, fontSize: 13 }}>{p.label}</Button>
                  <StatusBadge status={cat.status || 'pending'} label={cat.status || 'empty'} />
                </div>
              );
            })}
          </Space>
        </PanelCard>
      </div>
    </div>
  );
  };

  // ─── Tab: Performance Overview ───
  const PerformanceTab = () => {
    const { t } = useTranslation();
    if (resultsLoading) return <LoadingSpinner />;
    if (!results) return <Empty description={t('dashboard.no_results')} />;
    return (
      <div>
        <MetricRow metrics={[
          { label: t('dashboard.performance_index_label'), value: perf.index_value?.toFixed(2) || '—', status: perf.index_change >= 0 ? 'positive' : 'negative' },
          { label: t('dashboard.satisfaction_score'), value: pct(perf.satisfaction_score), status: Number(perf.satisfaction_score) >= 0.5 ? 'positive' : 'warning' },
          { label: t('dashboard.leaderboard_position'), value: myRank ? `#${myRank.rank} ${t('dashboard.of')} ${rankings.length}` : '—', status: 'neutral' },
        ]} />
        <MetricRow metrics={[
          { label: t('dashboard.revenue'), value: fmt(resFin.total_revenue), status: 'neutral' },
          { label: t('dashboard.net_income'), value: fmt(resFin.net_income), status: resFin.net_income >= 0 ? 'positive' : 'negative' },
          { label: t('dashboard.cash_position'), value: fmt(resFin.cash_closing), status: 'neutral' },
          { label: t('dashboard.gross_margin'), value: pct(resFin.gross_margin_pct), status: resFin.gross_margin_pct >= 0.4 ? 'positive' : resFin.gross_margin_pct >= 0.2 ? 'warning' : 'negative' },
          { label: t('dashboard.debt_to_equity'), value: Number(resFin.debt_to_equity || 0).toFixed(2), status: resFin.debt_to_equity < 1 ? 'positive' : resFin.debt_to_equity < 2 ? 'warning' : 'negative' },
          { label: t('dashboard.shareholder_return'), value: pct(resFin.shareholder_return_cumulative), status: 'neutral' },
        ]} />
        {rankings.length > 0 && (
          <PanelCard headerColor="results" title={t('dashboard.leaderboard')}>
            <Table dataSource={rankings} rowKey="team_id" pagination={false} size="small"
              rowClassName={(r) => r.team_id === teamId ? 'ant-table-row-selected' : ''}
              columns={[
                { title: t('dashboard.rank'), dataIndex: 'rank', width: 60 },
                { title: t('dashboard.team'), dataIndex: 'team_name' },
                { title: t('dashboard.index'), dataIndex: 'performance_index', render: v => v?.toFixed(2) },
                { title: t('dashboard.change'), dataIndex: 'index_change', render: v => (
                  <Tag color={v >= 0 ? 'green' : 'red'}>{v >= 0 ? '+' : ''}{v?.toFixed(2)}</Tag>
                )},
                { title: t('dashboard.share_price'), dataIndex: 'share_price', render: v => v != null ? `$${v.toFixed(2)}` : '—' },
                { title: t('dashboard.investor_confidence'), dataIndex: 'investor_confidence', render: v => {
                  if (v == null) return '—';
                  const pctVal = (v * 100).toFixed(0);
                  const color = v >= 0.7 ? '#52c41a' : v >= 0.4 ? '#faad14' : '#ff4d4f';
                  return <Tag color={color === '#52c41a' ? 'green' : color === '#faad14' ? 'gold' : 'red'}>{pctVal}%</Tag>;
                }},
              ]} />
          </PanelCard>
        )}
      </div>
    );
  };

  // ─── Tab: Market Results ───
  const MarketTab = () => {
    const { t } = useTranslation();
    if (resultsLoading) return <LoadingSpinner />;
    if (!results) return <Empty description={t('dashboard.no_results')} />;

    const marketPanels = (results.markets || []).map(m => ({
      key: m.market_code,
      label: `${m.market_name} — ${fmt(m.home_revenue)} ${t('dashboard.revenue')}, ${pct(m.market_share_pct)} ${t('dashboard.share')}`,
      children: (
        <div>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Card title={t('dashboard.revenue_profitability')} size="small">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={[{ name: m.market_name, revenue: m.home_revenue, profit: m.market_profit }]}>
                    <XAxis dataKey="name" /><YAxis tickFormatter={v => fmt(v)} />
                    <Tooltip formatter={v => fmt(v)} />
                    <Bar dataKey="revenue" fill="#4CAF50" name={t('dashboard.revenue')} />
                    <Bar dataKey="profit" fill="#2196F3" name={t('dashboard.profit')} />
                    <Legend />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card title={t('dashboard.market_share')} size="small">
                <Statistic value={pct(m.market_share_pct)} valueStyle={{ fontSize: 28 }} />
              </Card>
            </Col>
          </Row>
          {(m.segments || []).length > 0 && (
            <Card title={t('dashboard.customer_segment_adoption')} size="small" style={{ marginTop: 12 }}>
              <Table dataSource={m.segments} rowKey="segment_name" pagination={false} size="small"
                columns={[
                  { title: t('dashboard.segment'), dataIndex: 'segment_name' },
                  { title: t('dashboard.fit_score'), dataIndex: 'adjusted_fit_score', render: v => (
                    <Progress percent={Number(v * 100).toFixed(0)} strokeColor={fitColor(v)} size="small" style={{ width: 100 }} />
                  )},
                  { title: t('dashboard.adoption'), dataIndex: 'new_adopters', render: v => Number(v).toLocaleString() },
                  { title: t('corporate_strategy.cumulative'), dataIndex: 'cumulative_adopters', render: v => Number(v).toLocaleString() },
                  { title: t('dashboard.share'), dataIndex: 'team_share_pct', render: pct },
                  { title: t('dashboard.best_product'), dataIndex: 'best_product' },
                ]} />
            </Card>
          )}
          {(m.non_customer_segments || []).length > 0 && (
            <Card title={t('dashboard.non_customer_segments')} size="small" style={{ marginTop: 12 }}>
              <Row gutter={[12, 12]}>
                {m.non_customer_segments.map(s => (
                  <Col xs={12} md={8} key={s.segment_name}>
                    <Card size="small">
                      <Text strong>{s.segment_name}</Text>
                      <Progress percent={Number(s.adjusted_fit_score * 100).toFixed(0)} strokeColor={fitColor(s.adjusted_fit_score)} size="small" />
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>
          )}
        </div>
      ),
    }));

    return (
      <div>
        <Collapse items={marketPanels} defaultActiveKey={marketPanels.map(p => p.key)} />
        <PanelCard headerColor="market" title={t('dashboard.product_performance')}>
          <Table dataSource={results.products || []} rowKey={(r, i) => `${r.product_name}-${r.market}-${i}`}
            pagination={false} size="small"
            columns={[
              { title: t('dashboard.product'), dataIndex: 'product_name' },
              { title: t('dashboard.market'), dataIndex: 'market' },
              { title: t('dashboard.units_sold'), dataIndex: 'units_sold', render: v => Number(v).toLocaleString() },
              { title: t('dashboard.revenue'), dataIndex: 'home_revenue', render: fmt },
              { title: t('dashboard.unit_cost'), dataIndex: 'unit_cost', render: v => `$${Number(v).toFixed(2)}` },
              { title: t('dashboard.inventory'), dataIndex: 'units_unsold', render: v => `${Number(v).toLocaleString()} ${t('dashboard.units_label')}` },
            ]} />
        </PanelCard>
      </div>
    );
  };

  // ─── Tab: Events & Intelligence ───
  const EventsTab = () => {
    const { t } = useTranslation();
    if (resultsLoading) return <LoadingSpinner />;
    if (!results) return <Empty description={t('dashboard.no_results')} />;
    const sevColor = { low: 'blue', medium: 'orange', high: 'red', critical: '#8B0000' };
    return (
      <div>
        <PanelCard headerColor="market" title={t('dashboard.events_this_round')}>
          {(results.events || []).length === 0 ? (
            <Empty description={t('dashboard.no_events')} />
          ) : (
            (results.events || []).map((ev, i) => (
              <Card key={i} size="small" style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
                  <Text strong>{ev.name}</Text>
                  <span><Tag color={sevColor[ev.severity] || 'default'}>{ev.severity}</Tag><Tag>{ev.market}</Tag></span>
                </div>
                <Text style={{ display: 'block', marginTop: 8 }}>{ev.narrative}</Text>
              </Card>
            ))
          )}
        </PanelCard>
        {competitors && (
          <PanelCard headerColor="strategic" title={t('dashboard.competitor_intelligence')}>
            {(competitors.competitors || []).map((c, i) => (
              <Card key={i} size="small" style={{ marginBottom: 8 }}>
                <Text strong>{c.team_name}</Text>
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary">{t('dashboard.markets')}: </Text>
                  {(c.markets_present || []).map(m => <Tag key={m}>{m}</Tag>)}
                </div>
                <div>
                  <Text type="secondary">{t('dashboard.products')}: {c.product_count} | {t('dashboard.positioning')}: </Text>
                  {(c.positioning_observed || []).map(p => <Tag key={p}>{p}</Tag>)}
                </div>
              </Card>
            ))}
            {(competitors.ai_competitors || []).map((ai, i) => (
              <Card key={`ai-${i}`} size="small" style={{ marginBottom: 8, borderLeft: '3px solid #722ed1' }}>
                <Text strong>{ai.name}</Text> <Tag color="purple">AI</Tag>
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary">{t('dashboard.markets')}: </Text>
                  {(ai.markets_present || []).map(m => <Tag key={m}>{m}</Tag>)}
                </div>
              </Card>
            ))}
          </PanelCard>
        )}
      </div>
    );
  };

  // ─── Tab: Strategic Scorecard ───
  const StrategicScorecardTab = () => {
    const { t } = useTranslation();
    if (resultsLoading) return <LoadingSpinner />;
    if (!results) return <Empty description={t('dashboard.no_results')} />;

    const bd = coherence.breakdown || {};
    const criteria = [
      { key: 'positioning_price', label: t('dashboard.positioning_price') },
      { key: 'distribution_positioning', label: t('dashboard.distribution_positioning') },
      { key: 'entry_mode_risk', label: t('dashboard.entry_mode_risk') },
      { key: 'rd_market_alignment', label: t('dashboard.rd_market_alignment') },
      { key: 'financial_prudence', label: t('dashboard.financial_prudence') },
    ];
    let strongest = null, weakest = null;
    criteria.forEach(c => {
      const sc = bd[c.key]?.score;
      if (sc != null) {
        if (!strongest || sc > strongest.score) strongest = { ...c, score: sc };
        if (!weakest || sc < weakest.score) weakest = { ...c, score: sc };
      }
    });

    return (
      <div>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <PanelCard headerColor="strategic" title={t('dashboard.overall_coherence')}>
              <div style={{ textAlign: 'center' }}>
                <CoherenceGauge score={coherence.blended_score || 0} size={140} />
              </div>
            </PanelCard>
          </Col>
          <Col xs={24} md={16}>
            <PanelCard headerColor="strategic" title={t('dashboard.coherence_breakdown')}>
              {criteria.map(c => {
                const entry = bd[c.key] || {};
                const score = Number(entry.score || 0) * 100;
                return (
                  <div key={c.key} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text strong>{c.label}</Text><Text>{score.toFixed(0)}%</Text>
                    </div>
                    <Progress percent={score}
                      strokeColor={score >= 70 ? '#52c41a' : score >= 40 ? '#faad14' : '#f5222d'}
                      showInfo={false} />
                    {entry.feedback && <Text type="secondary" style={{ fontSize: 12 }}>{entry.feedback}</Text>}
                  </div>
                );
              })}
            </PanelCard>
          </Col>
        </Row>
        {(strongest || weakest) && (
          <PanelCard headerColor="neutral" title={t('dashboard.strengths_improvements')}>
            {strongest && (
              <div style={{ marginBottom: 8 }}>
                <Tag color="green">{t('dashboard.strength')}</Tag>
                <Text>{strongest.label} ({(strongest.score * 100).toFixed(0)}%)</Text>
              </div>
            )}
            {weakest && weakest.key !== strongest?.key && (
              <div><Tag color="orange">{t('dashboard.improve')}</Tag><Text>{weakest.label} ({(weakest.score * 100).toFixed(0)}%)</Text></div>
            )}
          </PanelCard>
        )}
      </div>
    );
  };

  // CSV export
  const exportCSV = () => {
    if (!results) return;
    const rows = [
      ['Metric', 'Value'],
      ['Round', selectedRound],
      ['Performance Index', perf.index_value],
      ['Index Change', perf.index_change],
      ['Revenue', resFin.total_revenue],
      ['Net Income', resFin.net_income],
      ['Cash', resFin.cash_closing],
      ['Gross Margin', resFin.gross_margin_pct],
      ['D/E Ratio', resFin.debt_to_equity],
      ['Coherence', coherence.blended_score],
    ];
    (results.markets || []).forEach(m => {
      rows.push([`${m.market_name} Revenue`, m.home_revenue]);
      rows.push([`${m.market_name} Share`, m.market_share_pct]);
    });
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `results_round_${selectedRound}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  // ─── Strategic Briefing Tab ─────────────────────────────────────────
  const StrategicBriefingTab = () => {
    const { t } = useTranslation();
    if (!briefing) return <Empty description={t('dashboard.no_briefing')} />;
    const b = briefing;
    const pa = b.performance_analysis || {};
    const ir = b.investment_returns || {};
    const is_ = b.investor_sentiment || {};
    const cl = b.competitive_landscape || {};
    const recs = b.strategic_recommendations || [];
    const risks = b.risk_alerts || [];

    const sevColor = (s) => s === 'critical' ? '#F44336' : s === 'warning' ? '#FF9800' : '#2196F3';
    const priColor = (p) => p === 'high' ? 'red' : p === 'medium' ? 'orange' : 'blue';

    // CC-31G: Build fund name → profile lookup for clickable names in briefing
    const investorFundProfileMap = {};
    (investorData?.fund_profiles || []).forEach(fp => { investorFundProfileMap[fp.name] = fp; });
    const FUND_NAMES = Object.keys(investorFundProfileMap);

    // Replace fund name occurrences in text with clickable spans
    const _renderBriefingText = (text) => {
      if (!text || FUND_NAMES.length === 0) return text;
      const regex = new RegExp(`(${FUND_NAMES.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'g');
      const parts = text.split(regex);
      return parts.map((part, i) => {
        const fp = investorFundProfileMap[part];
        if (fp) {
          return (
            <InvestorNameLink key={i} fund={fp} activeFund={activeFund} setActiveFund={setActiveFund}>
              {part}
            </InvestorNameLink>
          );
        }
        return part;
      });
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Card size="small" title={t('dashboard.round_strategic_briefing', { round: b.round_number })}>
          <Text style={{ fontSize: 15, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{_renderBriefingText(b.executive_summary)}</Text>
          <div style={{ marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 11 }}>
              Generated {b.generated_at ? new Date(b.generated_at).toLocaleString() : ''}
            </Text>
          </div>
        </Card>

        {/* Risk Alerts */}
        {risks.length > 0 && (
          <Card size="small" title={t('dashboard.risk_alerts')}>
            {risks.map((r, i) => (
              <Alert
                key={i}
                type={r.severity === 'critical' ? 'error' : r.severity === 'warning' ? 'warning' : 'info'}
                message={r.title}
                description={r.detail}
                showIcon
                style={{ marginBottom: i < risks.length - 1 ? 8 : 0 }}
              />
            ))}
          </Card>
        )}

        {/* Performance Analysis */}
        <Card size="small" title={t('dashboard.performance_analysis')}>
          {(pa.revenue_drivers || []).length > 0 && (
            <>
              <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('dashboard.revenue_by_market')}</Text>
              <Table
                size="small"
                pagination={false}
                dataSource={(pa.revenue_drivers || []).map((d, i) => ({ ...d, key: i }))}
                columns={[
                  { title: t('dashboard.market'), dataIndex: 'market' },
                  { title: t('dashboard.revenue'), dataIndex: 'revenue', render: v => fmt(v) },
                  { title: t('dashboard.change'), dataIndex: 'change', render: v => <span style={{ color: v >= 0 ? '#4CAF50' : '#F44336' }}>{fmt(v)}</span> },
                  { title: t('dashboard.share'), dataIndex: 'share', render: v => `${(v * 100).toFixed(1)}%` },
                ]}
                style={{ marginBottom: 16 }}
              />
            </>
          )}
          {(pa.segment_performance || []).length > 0 && (
            <>
              <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('dashboard.segment_performance')}</Text>
              {(pa.segment_performance || []).map((s, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <span>{s.segment} ({s.market})</span>
                  <span>
                    <Tag color={s.position === 'strong' ? 'green' : 'orange'}>{s.fit}</Tag>
                    Share: {(s.share * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </>
          )}
          {(pa.stakeholder_satisfaction || []).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('dashboard.stakeholder_satisfaction')}</Text>
              {(pa.stakeholder_satisfaction || []).map((s, i) => (
                <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{s.segment}</span>
                    <span><Tag color={fitColor(s.satisfaction_score)}>{s.satisfaction}</Tag> {s.trend}</span>
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>{s.narrative}</Text>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Investment Returns */}
        <Card size="small" title={t('dashboard.strategic_investment_returns')}>
          <Text style={{ display: 'block', marginBottom: 8 }}>{ir.overall_narrative}</Text>
          <Row gutter={16}>
            {[
              { label: 'ESG', data: ir.esg },
              { label: t('dashboard.talent'), data: ir.talent },
              { label: t('dashboard.partnerships'), data: ir.partnerships },
              { label: t('dashboard.plants'), data: ir.plants },
            ].map(({ label, data }) => data && (
              <Col span={12} key={label} style={{ marginBottom: 8 }}>
                <Card size="small" type="inner" title={label}>
                  <Text style={{ fontSize: 12 }}>{data.narrative}</Text>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        {/* Investor Sentiment */}
        <Card size="small" title={t('dashboard.investor_sentiment_section')}>
          <Text style={{ display: 'block', marginBottom: 8 }}>{_renderBriefingText(is_.narrative)}</Text>
          {(is_.investors || []).map((inv, i) => {
            const fp = investorFundProfileMap[inv.name];
            return (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                  {fp ? (
                    <InvestorNameLink fund={fp} activeFund={activeFund} setActiveFund={setActiveFund}>
                      <Text strong>{inv.name}</Text>
                    </InvestorNameLink>
                  ) : (
                    <Text strong>{inv.name}</Text>
                  )}
                  <Tag color={inv.action === 'bought' ? 'green' : inv.action === 'sold' ? 'red' : 'default'}>
                    {inv.action.toUpperCase()} {inv.change !== 0 && `${Math.abs(inv.change).toLocaleString()} shares`}
                  </Tag>
                </div>
                <Text style={{ fontSize: 12 }}>{inv.narrative}</Text>
              </div>
            );
          })}
        </Card>

        {/* Competitive Landscape */}
        <Card size="small" title={t('dashboard.competitive_landscape')}>
          <Text style={{ display: 'block', marginBottom: 8 }}>{cl.narrative}</Text>
          {(cl.competitor_moves || []).length > 0 && (
            <div>
              <Text strong style={{ fontSize: 12 }}>{t('dashboard.notable_competitor_moves')}:</Text>
              {(cl.competitor_moves || []).map((cm, i) => (
                <div key={i} style={{ padding: '4px 0' }}>
                  <Text>{cm.team}: {cm.moves.join('; ')}</Text>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Strategic Recommendations */}
        {recs.length > 0 && (
          <Card size="small" title={t('dashboard.strategic_recommendations')}>
            {recs.map((r, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: i < recs.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <Tag color={priColor(r.priority)}>{r.priority}</Tag>
                  <Tag>{r.category}</Tag>
                  <Text strong>{r.title}</Text>
                </div>
                <Text style={{ fontSize: 13 }}>{r.detail}</Text>
                {r.framework_reference && (
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" italic style={{ fontSize: 12 }}>{r.framework_reference}</Text>
                  </div>
                )}
                {r.action_page && (
                  <div style={{ marginTop: 2 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>Go to: {r.action_page}</Text>
                  </div>
                )}
              </div>
            ))}
          </Card>
        )}
      </div>
    );
  };

  const tabItems = [
    { key: 'scorecard', label: t('dashboard.balanced_scorecard'), children: <ScorecardOverview /> },
    { key: 'performance', label: t('dashboard.performance'), children: <PerformanceTab /> },
    { key: 'markets', label: t('dashboard.market_results'), children: <MarketTab /> },
    { key: 'events', label: t('dashboard.events_intelligence'), children: <EventsTab /> },
    { key: 'strategic', label: t('dashboard.strategic_scorecard'), children: <StrategicScorecardTab /> },
    { key: 'supply_chain', label: 'Supply Chain', children: <SupplyChainPanel /> },
    ...(briefing ? [{ key: 'briefing', label: t('dashboard.strategic_briefing_tab', { round: briefing.round_number }), children: <StrategicBriefingTab /> }] : []),
  ];

  return (
    <div>
      {/* First-login onboarding */}
      <OnboardingModal />

      {/* Briefing Splash Overlay */}
      <Modal
        open={showBriefingSplash}
        title={null}
        footer={null}
        closable={false}
        width={720}
        centered
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto', padding: '24px' } }}
      >
        {briefing && (
          <div>
            <img
              src="/images/strategy-brief.png"
              alt={t('dashboard.strategic_briefing_alt')}
              loading="lazy"
              style={{
                width: '100%', height: 220, objectFit: 'cover',
                display: 'block', marginBottom: 16, borderRadius: 2,
              }}
            />
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <Title level={3} style={{ margin: 0 }}>{t('dashboard.round_strategic_briefing', { round: briefing.round_number })}</Title>
              <Text type="secondary">{t('dashboard.team_performance_summary')}</Text>
            </div>

            <Card size="small" style={{ marginBottom: 16, background: '#f6ffed', border: '1px solid #b7eb8f' }}>
              <Text style={{ fontSize: 14, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>{briefing.executive_summary}</Text>
            </Card>

            {(briefing.risk_alerts || []).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                {briefing.risk_alerts.map((r, i) => (
                  <Alert
                    key={i}
                    type={r.severity === 'critical' ? 'error' : r.severity === 'warning' ? 'warning' : 'info'}
                    message={r.title}
                    description={r.detail}
                    showIcon
                    style={{ marginBottom: 8 }}
                  />
                ))}
              </div>
            )}

            {(briefing.strategic_recommendations || []).length > 0 && (
              <Card size="small" title={t('dashboard.top_recommendations')} style={{ marginBottom: 16 }}>
                {(briefing.strategic_recommendations || []).slice(0, 3).map((r, i) => (
                  <div key={i} style={{ padding: '6px 0', borderBottom: i < 2 ? '1px solid #f0f0f0' : 'none' }}>
                    <Tag color={r.priority === 'high' ? 'red' : 'orange'}>{r.priority}</Tag>
                    <Text strong>{r.title}</Text>
                    <div><Text style={{ fontSize: 12 }}>{r.detail}</Text></div>
                  </div>
                ))}
              </Card>
            )}

            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Button type="primary" size="large" onClick={handleDismissBriefing}>
                {t('dashboard.continue_to_dashboard')}
              </Button>
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {t('dashboard.full_briefing_available')}
                </Text>
              </div>
            </div>
          </div>
        )}
      </Modal>

      <PageHeader title={t('dashboard.title')} />
      <Tabs
        className="ds-colored-tabs"
        items={tabItems}
        defaultActiveKey="scorecard"
        tabBarExtraContent={
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <RoundSelector currentRound={selectedRound} maxRound={latestProcessed} minRound={0} onChange={setSelectedRound} />
            <button onClick={exportCSV} style={{ padding: '2px 8px', cursor: 'pointer', border: '1px solid #d9d9d9', borderRadius: 4, background: '#fff', fontSize: 12 }}>CSV</button>
          </div>
        }
      />

      {/* CC-31G: Investor Profile Popover (shared across all tabs) */}
      {activeFund && (
        <InvestorProfilePopover
          fund={activeFund}
          onClose={() => setActiveFund(null)}
          anchorRect={activeFund._anchorRect}
        />
      )}
    </div>
  );
};

export default GameDashboard;
