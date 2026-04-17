import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Card, Typography, Row, Col, Tabs, Tag, Statistic, Table, Collapse, Progress, Empty, Alert,
} from 'antd';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { getRoundResults, getLeaderboard, getCompetitorIntel } from '../api/results';
import CoherenceGauge from '../components/CoherenceGauge';
import RoundSelector from '../components/RoundSelector';
import LoadingSpinner from '../components/LoadingSpinner';
import { PageHeader, PanelCard } from '../components/design-system';
import { getMarketLocalization, getTalentAllocationContext, getComplianceContext } from '../api/decisions';

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

const ResultsPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, game } = useGame();
  const params = useParams();
  const latestProcessed = Math.max((game?.current_round || 1) - 1, 0);
  const [selectedRound, setSelectedRound] = useState(
    params.roundNumber ? Number(params.roundNumber) : latestProcessed
  );
  const [results, setResults] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [competitors, setCompetitors] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async (rnd) => {
    if (!gameId || !teamId || rnd < 0) { setLoading(false); return; }
    setLoading(true);
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
    setLoading(false);
  }, [gameId, teamId]);

  useEffect(() => {
    if (latestProcessed >= 0 && selectedRound < 0) setSelectedRound(latestProcessed);
  }, [latestProcessed, selectedRound]);

  useEffect(() => { loadData(selectedRound); }, [selectedRound, loadData]);

  if (latestProcessed < 0) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Empty description={t("results_page.no_results_yet")} />
      </div>
    );
  }

  if (loading) return <LoadingSpinner />;
  if (!results) return <Alert message={t("results_page.unable_to_load")} type="error" />;

  const perf = results.performance || {};
  const fin = results.financials || {};
  const coherence = results.coherence || {};
  const rankings = leaderboard?.rankings || [];
  const myRank = rankings.find(r => r.team_id === teamId);

  // --- Tab 1: Performance Overview ---
  const PerformanceTab = () => {
    const { t } = useTranslation();
    return (
    <div>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title={t("results_page.performance_index")} value={perf.index_value?.toFixed(2)} />
            <Tag color={perf.index_change >= 0 ? 'green' : 'red'} style={{ marginTop: 8 }}>
              {perf.index_change >= 0 ? '+' : ''}{perf.index_change?.toFixed(2)}
            </Tag>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title={t("results_page.satisfaction_score")} value={pct(perf.satisfaction_score)} />
            <Progress
              percent={Number(perf.satisfaction_score || 0) * 100}
              strokeColor={Number(perf.satisfaction_score) >= 0.5 ? '#52c41a' : '#faad14'}
              showInfo={false} style={{ marginTop: 8 }}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title={t("results_page.leaderboard_position")}
              value={myRank ? `#${myRank.rank}` : '—'}
              suffix={t("results_page.of_teams", { count: rankings.length })}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} md={8}><Card><Statistic title={t("results_page.revenue")} value={fmt(fin.total_revenue)} /></Card></Col>
        <Col xs={12} md={8}>
          <Card>
            <Statistic title={t("results_page.net_income")} value={fmt(fin.net_income)}
              valueStyle={{ color: fin.net_income >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={12} md={8}><Card><Statistic title={t("results_page.cash_position")} value={fmt(fin.cash_closing)} /></Card></Col>
        <Col xs={12} md={8}>
          <Card>
            <Statistic title={t("results_page.gross_margin")} value={pct(fin.gross_margin_pct)}
              valueStyle={{ color: fin.gross_margin_pct >= 0.4 ? '#3f8600' : fin.gross_margin_pct >= 0.2 ? '#d4b106' : '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={12} md={8}>
          <Card>
            <Statistic title={t("results_page.debt_to_equity")} value={Number(fin.debt_to_equity || 0).toFixed(2)}
              valueStyle={{ color: fin.debt_to_equity < 1 ? '#3f8600' : fin.debt_to_equity < 2 ? '#d4b106' : '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={12} md={8}>
          <Card><Statistic title={t("results_page.shareholder_return")} value={pct(fin.shareholder_return_cumulative)} /></Card>
        </Col>
      </Row>

      {rankings.length > 0 && (
        <Card title={t("results_page.leaderboard")} style={{ marginTop: 16 }}>
          <Table
            dataSource={rankings}
            rowKey="team_id"
            pagination={false}
            size="small"
            rowClassName={(r) => r.team_id === teamId ? 'ant-table-row-selected' : ''}
            columns={[
              { title: t('results_page.rank'), dataIndex: 'rank', width: 60 },
              { title: t('results_page.team'), dataIndex: 'team_name' },
              { title: t('results_page.index'), dataIndex: 'performance_index', render: v => v?.toFixed(2) },
              { title: t('results_page.change'), dataIndex: 'index_change', render: v => (
                <Tag color={v >= 0 ? 'green' : 'red'}>{v >= 0 ? '+' : ''}{v?.toFixed(2)}</Tag>
              )},
            ]}
          />
        </Card>
      )}
    </div>
  );
  };

  // --- Tab 2: Market Results ---
  const MarketTab = () => {
    const { t } = useTranslation();
    const marketPanels = (results.markets || []).map(m => ({
      key: m.market_code,
      label: `${m.market_name} — ${fmt(m.home_revenue)} ${t('results_page.revenue')}, ${pct(m.market_share_pct)} ${t('results_page.share')}`,
      children: (
        <div>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Card title={t("results_page.revenue_profitability")} size="small">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={[{
                    name: m.market_name,
                    revenue: m.home_revenue,
                    profit: m.market_profit,
                  }]}>
                    <XAxis dataKey="name" />
                    <YAxis tickFormatter={v => fmt(v)} />
                    <Tooltip formatter={v => fmt(v)} />
                    <Bar dataKey="revenue" fill="#4CAF50" name={t("results_page.revenue")} />
                    <Bar dataKey="profit" fill="#2196F3" name={t("results_page.profit")} />
                    <Legend />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card title={t("results_page.market_share")} size="small">
                <Statistic value={pct(m.market_share_pct)} valueStyle={{ fontSize: 28 }} />
              </Card>
            </Col>
          </Row>

          {(m.segments || []).length > 0 && (
            <Card title={t("results_page.customer_segment_adoption")} size="small" style={{ marginTop: 12 }}>
              <Table
                dataSource={m.segments}
                rowKey="segment_name"
                pagination={false}
                size="small"
                columns={[
                  { title: t('results_page.segment'), dataIndex: 'segment_name' },
                  { title: t('results_page.fit_score'), dataIndex: 'adjusted_fit_score', render: v => (
                    <Progress
                      percent={Number(v * 100).toFixed(0)}
                      strokeColor={fitColor(v)}
                      size="small" style={{ width: 100 }}
                    />
                  )},
                  { title: t('results_page.adoption'), dataIndex: 'new_adopters', render: v => Number(v).toLocaleString() },
                  { title: t('results_page.cumulative'), dataIndex: 'cumulative_adopters', render: v => Number(v).toLocaleString() },
                  { title: t('results_page.share'), dataIndex: 'team_share_pct', render: pct },
                  { title: t('results_page.best_product'), dataIndex: 'best_product' },
                ]}
              />
            </Card>
          )}

          {(m.non_customer_segments || []).length > 0 && (
            <Card title={t("results_page.non_customer_segments")} size="small" style={{ marginTop: 12 }}>
              <Row gutter={[12, 12]}>
                {m.non_customer_segments.map(s => (
                  <Col xs={12} md={8} key={s.segment_name}>
                    <Card size="small">
                      <Text strong>{s.segment_name}</Text>
                      <Progress
                        percent={Number(s.adjusted_fit_score * 100).toFixed(0)}
                        strokeColor={fitColor(s.adjusted_fit_score)}
                        size="small"
                      />
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>
          )}
        </div>
      ),
    }));

    const productCols = [
      { title: t('results_page.product'), dataIndex: 'product_name' },
      { title: t('results_page.market_col'), dataIndex: 'market' },
      { title: t('results_page.units_sold'), dataIndex: 'units_sold', render: v => Number(v).toLocaleString() },
      { title: t('results_page.revenue'), dataIndex: 'home_revenue', render: fmt },
      { title: t('results_page.unit_cost'), dataIndex: 'unit_cost', render: v => `$${Number(v).toFixed(2)}` },
      { title: t('results_page.inventory'), dataIndex: 'units_unsold', render: v => `${Number(v).toLocaleString()} ${t('results_page.units')}` },
    ];

    return (
      <div>
        <Collapse items={marketPanels} defaultActiveKey={marketPanels.map(p => p.key)} />
        <Card title={t("results_page.product_performance")} style={{ marginTop: 16 }}>
          <Table dataSource={results.products || []} rowKey={(r, i) => `${r.product_name}-${r.market}-${i}`}
            columns={productCols} pagination={false} size="small" />
        </Card>
      </div>
    );
  };

  // --- Tab 3: Events & Intelligence ---
  const EventsTab = () => {
    const { t } = useTranslation();
    const sevColor = { low: 'blue', medium: 'orange', high: 'red', critical: '#8B0000' };
    return (
      <div>
        <Card title={t("results_page.events_this_round")}>
          {(results.events || []).length === 0 ? (
            <Empty description={t("results_page.no_events")} />
          ) : (
            (results.events || []).map((ev, i) => (
              <Card key={i} size="small" style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
                  <Text strong>{ev.name}</Text>
                  <span>
                    <Tag color={sevColor[ev.severity] || 'default'}>{ev.severity}</Tag>
                    <Tag>{ev.market}</Tag>
                  </span>
                </div>
                <Text style={{ display: 'block', marginTop: 8 }}>{ev.narrative}</Text>
              </Card>
            ))
          )}
        </Card>

        {competitors && (
          <Card title={t("results_page.competitor_intelligence")} style={{ marginTop: 16 }}>
            {(competitors.competitors || []).map((c, i) => (
              <Card key={i} size="small" style={{ marginBottom: 8 }}>
                <Text strong>{c.team_name}</Text>
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary">{t("results_page.markets_label")}: </Text>
                  {(c.markets_present || []).map(m => <Tag key={m}>{m}</Tag>)}
                </div>
                <div>
                  <Text type="secondary">{t("results_page.products_label")}: {c.product_count} | {t("results_page.positioning_label")}: </Text>
                  {(c.positioning_observed || []).map(p => <Tag key={p}>{p}</Tag>)}
                </div>
              </Card>
            ))}
            {(competitors.ai_competitors || []).map((ai, i) => (
              <Card key={`ai-${i}`} size="small" style={{ marginBottom: 8, borderLeft: '3px solid #722ed1' }}>
                <Text strong>{ai.name}</Text> <Tag color="purple">AI</Tag>
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary">{t("results_page.markets_label")}: </Text>
                  {(ai.markets_present || []).map(m => <Tag key={m}>{m}</Tag>)}
                </div>
              </Card>
            ))}
          </Card>
        )}
      </div>
    );
  };

  // --- Tab 4: Strategic Scorecard ---
  const ScorecardTab = () => {
    const { t } = useTranslation();
    const bd = coherence.breakdown || {};
    const criteria = [
      { key: 'positioning_price', label: t('results_page.positioning_price') },
      { key: 'distribution_positioning', label: t('results_page.distribution_positioning') },
      { key: 'entry_mode_risk', label: t('results_page.entry_mode_risk') },
      { key: 'rd_market_alignment', label: t('results_page.rd_market_alignment') },
      { key: 'financial_prudence', label: t('results_page.financial_prudence') },
    ];

    let strongest = null;
    let weakest = null;
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
            <Card style={{ textAlign: 'center' }}>
              <Title level={5}>{t("results_page.overall_coherence")}</Title>
              <CoherenceGauge score={coherence.blended_score || 0} size={140} />
            </Card>
          </Col>
          <Col xs={24} md={16}>
            <Card>
              {criteria.map(c => {
                const entry = bd[c.key] || {};
                const score = Number(entry.score || 0) * 100;
                return (
                  <div key={c.key} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text strong>{c.label}</Text>
                      <Text>{score.toFixed(0)}%</Text>
                    </div>
                    <Progress
                      percent={score}
                      strokeColor={score >= 70 ? '#52c41a' : score >= 40 ? '#faad14' : '#f5222d'}
                      showInfo={false}
                    />
                    {entry.feedback && <Text type="secondary" style={{ fontSize: 12 }}>{entry.feedback}</Text>}
                  </div>
                );
              })}
            </Card>
          </Col>
        </Row>

        {(strongest || weakest) && (
          <Card title={t("results_page.strengths_improvements")} style={{ marginTop: 16 }}>
            {strongest && (
              <div style={{ marginBottom: 8 }}>
                <Tag color="green">{t("results_page.strength")}</Tag>
                <Text>{strongest.label} ({(strongest.score * 100).toFixed(0)}%)</Text>
              </div>
            )}
            {weakest && weakest.key !== strongest?.key && (
              <div>
                <Tag color="orange">{t("results_page.improve")}</Tag>
                <Text>{weakest.label} ({(weakest.score * 100).toFixed(0)}%)</Text>
              </div>
            )}
          </Card>
        )}
      </div>
    );
  };

  // --- Tab 5: Localization ---
  const locMultColor = (v) => {
    const n = Number(v);
    if (n >= 0.9) return '#4CAF50';
    if (n >= 0.7) return '#FF9800';
    return '#F44336';
  };

  const MARKET_LINE_COLORS = ['#1E3A5F', '#4CAF50', '#FF9800', '#2196F3', '#9C27B0', '#F44336', '#00BCD4', '#795548'];

  const LocalizationTab = () => {
    const { t } = useTranslation();
    const locData = results.localization;
    if (!locData || locData.length === 0) {
      return <Empty description={t("results_page.localization_inactive")} />;
    }

    const columns = [
      { title: t('results_page.market_col'), dataIndex: 'market_name', key: 'market_name',
        render: (v, row) => row.is_home ? <Text strong>{v} <Tag color="blue" style={{ marginLeft: 4 }}>{t('results_page.home_tag')}</Tag></Text> : v,
      },
      {
        title: t('results_page.distance'), dataIndex: 'distance', key: 'distance',
        render: (v, row) => {
          if (row.is_home) return <Tag color="green">{t('results_page.home_tag')}</Tag>;
          const n = Number(v);
          const label = n <= 1 ? t('results_page.low') : n <= 2 ? t('results_page.med') : n <= 3 ? t('results_page.high') : t('results_page.vhigh');
          const color = n <= 1 ? 'green' : n <= 2 ? 'gold' : n <= 3 ? 'orange' : 'red';
          return <Tag color={color}>{label} ({n})</Tag>;
        },
      },
      {
        title: t('results_page.staff_rd_comm_ops'), key: 'staff',
        render: (_, row) => (
          <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            {Number(row.rd_staff || 0)} / {Number(row.commercial_staff || 0)} / {Number(row.ops_staff || 0)}
          </Text>
        ),
      },
      {
        title: t('results_page.rd_mult'), dataIndex: 'rd_multiplier', key: 'rd_multiplier',
        render: (v, row) => row.is_home
          ? <Text style={{ color: '#4CAF50', fontWeight: 600 }}>100%</Text>
          : <Text style={{ color: locMultColor(v), fontWeight: 600 }}>{pct(v)}</Text>,
      },
      {
        title: t('results_page.comm_mult'), dataIndex: 'commercial_multiplier', key: 'commercial_multiplier',
        render: (v, row) => row.is_home
          ? <Text style={{ color: '#4CAF50', fontWeight: 600 }}>100%</Text>
          : <Text style={{ color: locMultColor(v), fontWeight: 600 }}>{pct(v)}</Text>,
      },
      {
        title: t('results_page.ops_mult'), dataIndex: 'ops_multiplier', key: 'ops_multiplier',
        render: (v, row) => row.is_home
          ? <Text style={{ color: '#4CAF50', fontWeight: 600 }}>100%</Text>
          : <Text style={{ color: locMultColor(v), fontWeight: 600 }}>{pct(v)}</Text>,
      },
      {
        title: t('results_page.compliance'), dataIndex: 'compliance_score', key: 'compliance_score',
        render: (v) => {
          const val = Number((v || 0) * 100);
          return <Progress percent={val.toFixed(0)} size="small" style={{ width: 80 }}
            strokeColor={val >= 70 ? '#52c41a' : val >= 40 ? '#faad14' : '#f5222d'} />;
        },
      },
      {
        title: t('results_page.trust'), dataIndex: 'trust_score', key: 'trust_score',
        render: (v) => {
          const val = Number((v || 0) * 100);
          return <Progress percent={val.toFixed(0)} size="small" style={{ width: 80 }}
            strokeColor={val >= 70 ? '#52c41a' : val >= 40 ? '#faad14' : '#f5222d'} />;
        },
      },
      {
        title: t('results_page.repatriation_cost'), dataIndex: 'repatriation_cost_pct', key: 'repatriation_cost',
        render: (v, row) => {
          if (row.is_home) return <Text type="secondary">N/A</Text>;
          const val = Number(v || 0);
          return <Text style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{(val * 100).toFixed(1)}%</Text>;
        },
      },
    ];

    // Build chart data for effective multiplier trends across rounds
    const trendData = [];
    const marketNames = locData.filter(m => !m.is_home).map(m => m.market_name);

    if (results.localization_history && results.localization_history.length > 0) {
      // Use historical data if available from results
      results.localization_history.forEach(entry => {
        const point = { round: `R${entry.round}` };
        (entry.markets || []).forEach(m => {
          if (!m.is_home) {
            const avg = ((Number(m.rd_multiplier) || 0) + (Number(m.commercial_multiplier) || 0) + (Number(m.ops_multiplier) || 0)) / 3;
            point[m.market_name] = Number((avg * 100).toFixed(1));
          }
        });
        trendData.push(point);
      });
    } else {
      // Fallback: show current round data as single point
      const point = { round: `R${selectedRound}` };
      locData.forEach(m => {
        if (!m.is_home) {
          const avg = ((Number(m.rd_multiplier) || 0) + (Number(m.commercial_multiplier) || 0) + (Number(m.ops_multiplier) || 0)) / 3;
          point[m.market_name] = Number((avg * 100).toFixed(1));
        }
      });
      trendData.push(point);
    }

    const lowEffectiveness = locData
      .filter(m => {
        if (m.is_home) return false;
        const avg = ((Number(m.rd_multiplier) || 0) + (Number(m.commercial_multiplier) || 0) + (Number(m.ops_multiplier) || 0)) / 3;
        return avg < 0.7;
      })
      .sort((a, b) => {
        const avgA = ((Number(a.rd_multiplier) || 0) + (Number(a.commercial_multiplier) || 0) + (Number(a.ops_multiplier) || 0)) / 3;
        const avgB = ((Number(b.rd_multiplier) || 0) + (Number(b.commercial_multiplier) || 0) + (Number(b.ops_multiplier) || 0)) / 3;
        return avgA - avgB;
      });

    return (
      <div>
        <PanelCard title={t("results_page.localization_effectiveness")} headerColor="results">
          <Table
            dataSource={locData}
            rowKey="market_name"
            columns={columns}
            pagination={false}
            size="small"
            scroll={{ x: 900 }}
          />
        </PanelCard>

        {marketNames.length > 0 && trendData.length > 0 && (
          <PanelCard title={t("results_page.effective_multiplier_trends")} headerColor="strategic" style={{ marginTop: 16 }}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
              {t("results_page.effective_multiplier_desc")}
            </Text>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <XAxis dataKey="round" />
                <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} />
                <Tooltip formatter={(v) => `${v}%`} />
                <Legend />
                {marketNames.map((name, i) => (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    stroke={MARKET_LINE_COLORS[i % MARKET_LINE_COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    name={name}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </PanelCard>
        )}

        {lowEffectiveness.length > 0 && (
          <PanelCard title={t("results_page.opportunity_highlights")} headerColor="market" style={{ marginTop: 16 }}>
            <Text strong style={{ display: 'block', marginBottom: 12 }}>{t("results_page.markets_lowest_effectiveness")}</Text>
            <Alert
              type="info"
              showIcon
              message={t("results_page.markets_below_70")}
              style={{ marginBottom: 12 }}
            />
            {lowEffectiveness.map(m => {
              const avg = ((Number(m.rd_multiplier) || 0) + (Number(m.commercial_multiplier) || 0) + (Number(m.ops_multiplier) || 0)) / 3;
              return (
                <div key={m.market_name} style={{ marginBottom: 10, padding: '8px 12px', background: '#FFF7E6', borderRadius: 4, border: '1px solid #FFE58F' }}>
                  <Tag color="red">{m.market_name}</Tag>
                  <Text style={{ fontSize: 13 }}>
                    {t("results_page.avg_multiplier")}: <Text strong style={{ color: locMultColor(avg) }}>{pct(avg)}</Text>
                    {' '}({t("results_page.rd_short")}: {pct(m.rd_multiplier)}, {t("results_page.comm_short")}: {pct(m.commercial_multiplier)}, {t("results_page.ops_short")}: {pct(m.ops_multiplier)})
                  </Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {t("results_page.consider_local_staff")}
                  </Text>
                </div>
              );
            })}
          </PanelCard>
        )}
      </div>
    );
  };

  // CSV export
  const exportCSV = () => {
    const rows = [
      ['Metric', 'Value'],
      ['Round', selectedRound],
      ['Performance Index', perf.index_value],
      ['Index Change', perf.index_change],
      ['Revenue', fin.total_revenue],
      ['Net Income', fin.net_income],
      ['Cash', fin.cash_closing],
      ['Gross Margin', fin.gross_margin_pct],
      ['D/E Ratio', fin.debt_to_equity],
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
    a.href = url;
    a.download = `results_round_${selectedRound}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const tabItems = [
    { key: 'performance', label: t('results.performance_overview'), children: <PerformanceTab /> },
    { key: 'markets', label: t('results.market_results'), children: <MarketTab /> },
    { key: 'events', label: t('results.events_intelligence'), children: <EventsTab /> },
    { key: 'scorecard', label: t('results.strategic_scorecard'), children: <ScorecardTab /> },
    { key: 'localization', label: t('results.localization'), children: <LocalizationTab /> },
  ];

  return (
    <div>
      <PageHeader
        title={t("results_page.title", { round: selectedRound })}
        subtitle={t("results_page.subtitle")}
        actions={
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <RoundSelector
              currentRound={selectedRound}
              maxRound={latestProcessed}
              minRound={0}
              onChange={setSelectedRound}
            />
            <button onClick={exportCSV} style={{
              padding: '4px 12px', cursor: 'pointer', border: '1px solid #d9d9d9', borderRadius: 4, background: '#fff',
            }}>{t("results_page.export_csv")}</button>
          </div>
        }
      />
      <Tabs className="ds-colored-tabs" items={tabItems} />
    </div>
  );
};

export default ResultsPage;
