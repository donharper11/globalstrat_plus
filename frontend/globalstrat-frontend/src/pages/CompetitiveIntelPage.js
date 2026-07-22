import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Select, Typography, Tag, Row, Col, Empty, Tabs, Table } from 'antd';
import { useGame } from '../contexts/GameContext';
import { getCompetitorIntel } from '../api/results';
import LoadingSpinner from '../components/LoadingSpinner';
import { PageHeader, PanelCard } from '../components/design-system';

const { Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const pct = (v) => `${(Number(v || 0) * 100).toFixed(1)}%`;

const CompetitiveIntelPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, roundStatus } = useGame();
  const [selectedRound, setSelectedRound] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const latestProcessed = roundStatus === 'processed' ? currentRound : Math.max((currentRound || 1) - 1, 0);

  const roundOptions = [];
  for (let i = latestProcessed; i >= 0; i--) {
    roundOptions.push({ value: i, label: `${t('common.round')} ${i}` });
  }

  const fetchData = useCallback(async (rnd) => {
    if (!gameId || !teamId) return;
    setLoading(true);
    try {
      const res = await getCompetitorIntel(gameId, teamId, rnd);
      setData(res.data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [gameId, teamId]);

  useEffect(() => {
    if (currentRound != null && selectedRound == null) {
      setSelectedRound(latestProcessed);
    }
  }, [currentRound, latestProcessed, selectedRound]);

  useEffect(() => {
    if (selectedRound != null) fetchData(selectedRound);
  }, [selectedRound, fetchData]);

  if (loading) return <LoadingSpinner message={t("common.loading")} />;

  const competitors = data?.competitors || [];
  const aiCompetitors = data?.ai_competitors || [];
  const marketReport = data?.market_report || [];
  const financialSummary = data?.financial_summary || [];

  // ─── Tab 1: Competitor Overview (original) ───
  const OverviewTab = () => {
    const { t } = useTranslation();
    return (
    <div>
      {competitors.length > 0 ? (
        <PanelCard headerColor="strategic" title={t("competitive_intel.human_competitors").toUpperCase()}>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            {competitors.map((c, i) => (
              <Col xs={24} md={12} key={i}>
                <Card size="small" title={c.team_name}>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">{t("competitive_intel.markets")}: </Text>
                    {c.markets_present?.length > 0 ? (
                      c.markets_present.map(m => <Tag key={m} color="green">{m}</Tag>)
                    ) : (
                      <Text type="secondary">{t("competitive_intel.none_observed")}</Text>
                    )}
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">{t("competitive_intel.products")}: </Text>
                    <Text>{c.product_count} {t('competitive_intel.observed')}</Text>
                    {c.positioning_observed?.length > 0 && (
                      <span> | {t('competitive_intel.col_positioning')}: {c.positioning_observed.map(p => {
                        const key = p === 'ultra_premium' ? 'common.ultra_premium' : `common.${p}`;
                        return t(key, p);
                      }).join(', ')}</span>
                    )}
                  </div>
                  {Object.keys(c.approximate_market_share || {}).length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary">{t("competitive_intel.market_share")}: </Text>
                      {Object.entries(c.approximate_market_share).map(([mkt, share]) => (
                        <Tag key={mkt}>{mkt} {(share * 100).toFixed(1)}%</Tag>
                      ))}
                    </div>
                  )}
                  {Object.keys(c.approximate_price_range || {}).length > 0 && (
                    <div>
                      <Text type="secondary">{t("competitive_intel.price_range")}: </Text>
                      {Object.entries(c.approximate_price_range).map(([mkt, range]) => (
                        <Tag key={mkt}>{mkt}: ${range}</Tag>
                      ))}
                    </div>
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        </PanelCard>
      ) : (
        <Empty description={t("competitive_intel.no_competitor_data")} style={{ marginBottom: 24 }} />
      )}
      {aiCompetitors.length > 0 && (
        <PanelCard headerColor="strategic" title={t("competitive_intel.ai_competitors").toUpperCase()}>
          <Row gutter={[16, 16]}>
            {aiCompetitors.map((ai, i) => (
              <Col xs={24} md={12} key={i}>
                <Card size="small" title={ai.name}>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">{t("competitive_intel.markets")}: </Text>
                    {ai.markets_present?.map(m => <Tag key={m} color="blue">{m}</Tag>)}
                  </div>
                  {Object.keys(ai.approximate_market_share || {}).length > 0 && (
                    <div>
                      <Text type="secondary">{t("competitive_intel.market_share")}: </Text>
                      {Object.entries(ai.approximate_market_share).map(([mkt, share]) => (
                        <Tag key={mkt}>{mkt} {(share * 100).toFixed(1)}%</Tag>
                      ))}
                    </div>
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        </PanelCard>
      )}
    </div>
  );
  };

  // ─── Tab 2: Market Report (products, features, prices, positions) ───
  const MarketReportTab = () => {
    const { t } = useTranslation();
    // Collect all feature names across all products
    const featureSet = new Set();
    marketReport.forEach(p => {
      Object.keys(p.features || {}).forEach(f => featureSet.add(f));
    });
    const featureNames = [...featureSet].sort();

    const columns = [
      {
        title: t('competitive_intel.col_team'), dataIndex: 'team_name', width: 120, fixed: 'left',
        render: (v, r) => <Text strong={r.is_own_team} style={r.is_own_team ? { color: '#1677ff' } : {}}>{v}</Text>,
      },
      { title: t('competitive_intel.col_product'), dataIndex: 'product_name', width: 130 },
      { title: t('competitive_intel.col_market'), dataIndex: 'market', width: 70 },
      { title: t('competitive_intel.col_positioning'), dataIndex: 'positioning', width: 100, render: v => <Tag>{v || '—'}</Tag> },
      { title: t('competitive_intel.col_price'), dataIndex: 'price', width: 80, render: v => `$${Number(v).toFixed(0)}`, sorter: (a, b) => a.price - b.price },
      { title: t('competitive_intel.col_units_sold'), dataIndex: 'units_sold', width: 90, render: v => Number(v).toLocaleString() },
      ...featureNames.map(f => ({
        title: f.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        dataIndex: ['features', f],
        width: 80,
        render: (_, r) => {
          const val = r.features?.[f];
          return val != null ? val.toFixed(1) : '—';
        },
      })),
    ];

    // Expand segment positions into a nested row
    const expandedRowRender = (record) => {
      if (!record.segment_positions?.length) return <Text type="secondary">{t("competitive_intel.no_market_data")}</Text>;
      return (
        <Table
          dataSource={record.segment_positions}
          rowKey="segment"
          pagination={false}
          size="small"
          columns={[
            { title: t('competitive_intel.col_segment'), dataIndex: 'segment' },
            { title: t('competitive_intel.col_fit_score'), dataIndex: 'fit_score', render: v => (
              <span>
                {(v * 100).toFixed(0)}%
                <span style={{
                  display: 'inline-block', width: 50, height: 6, background: '#f0f0f0',
                  borderRadius: 3, marginLeft: 8, verticalAlign: 'middle',
                }}>
                  <span style={{
                    display: 'block', width: `${v * 100}%`, height: '100%',
                    background: v >= 0.6 ? '#52c41a' : v >= 0.3 ? '#faad14' : '#ff4d4f',
                    borderRadius: 3,
                  }} />
                </span>
              </span>
            )},
            { title: t('competitive_intel.col_share'), dataIndex: 'share_pct', render: v => pct(v) },
          ]}
        />
      );
    };

    return (
      <PanelCard headerColor="market" title={t("competitive_intel.products_features_position").toUpperCase()}>
        {marketReport.length > 0 ? (
          <Table
            dataSource={marketReport}
            rowKey={(r, i) => `${r.team_name}-${r.product_name}-${r.market}-${i}`}
            pagination={false}
            size="small"
            scroll={{ x: 'max-content' }}
            expandable={{
              expandedRowRender,
              rowExpandable: r => (r.segment_positions || []).length > 0,
            }}
            columns={columns}
          />
        ) : (
          <Empty description={t("competitive_intel.no_market_data")} />
        )}
      </PanelCard>
    );
  };

  // ─── Tab 3: Financial Performance ───
  const FinancialTab = () => {
    const { t } = useTranslation();
    const columns = [
      {
        title: t('competitive_intel.col_team'), dataIndex: 'team_name', fixed: 'left', width: 130,
        render: (v, r) => <Text strong={r.is_own_team} style={r.is_own_team ? { color: '#1677ff' } : {}}>{v}</Text>,
      },
      { title: t('competitive_intel.col_revenue'), dataIndex: 'revenue', render: fmt, sorter: (a, b) => a.revenue - b.revenue },
      {
        title: t('competitive_intel.col_net_income'), dataIndex: 'net_income', render: v => (
          <Text style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>{fmt(v)}</Text>
        ), sorter: (a, b) => a.net_income - b.net_income,
      },
      { title: t('competitive_intel.col_gross_margin'), dataIndex: 'gross_margin_pct', render: pct, sorter: (a, b) => a.gross_margin_pct - b.gross_margin_pct },
      { title: t('competitive_intel.col_net_margin'), dataIndex: 'net_margin_pct', render: pct },
      { title: t('competitive_intel.col_cash'), dataIndex: 'cash', render: fmt },
      {
        title: t('competitive_intel.col_de_ratio'), dataIndex: 'debt_to_equity', render: v => (
          <Text style={{ color: v < 1 ? '#3f8600' : v < 2 ? '#d4b106' : '#cf1322' }}>{v.toFixed(2)}</Text>
        ),
      },
      { title: t('competitive_intel.col_share_price'), dataIndex: 'share_price', render: v => `$${v.toFixed(2)}` },
      { title: t('competitive_intel.col_perf_index'), dataIndex: 'performance_index', render: v => v.toFixed(2), sorter: (a, b) => a.performance_index - b.performance_index },
      { title: t('competitive_intel.col_rd_spend'), dataIndex: 'rd_expense', render: fmt },
      { title: t('competitive_intel.col_mktg_spend'), dataIndex: 'marketing_expense', render: fmt },
    ];

    return (
      <PanelCard headerColor="financial" title={t("competitive_intel.financial_performance_comparison").toUpperCase()}>
        {financialSummary.length > 0 ? (
          <Table
            dataSource={financialSummary}
            rowKey="team_name"
            pagination={false}
            size="small"
            scroll={{ x: 'max-content' }}
            rowClassName={r => r.is_own_team ? 'ant-table-row-selected' : ''}
            columns={columns}
          />
        ) : (
          <Empty description={t("competitive_intel.no_financial_data")} />
        )}
      </PanelCard>
    );
  };

  const tabItems = [
    { key: 'overview', label: t('competitive_intel.competitor_overview'), children: <OverviewTab /> },
    { key: 'market-report', label: t('competitive_intel.market_report'), children: <MarketReportTab /> },
    { key: 'financials', label: t('competitive_intel.financial_performance'), children: <FinancialTab /> },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      <PageHeader
        title={t("nav.competitive_intelligence")}
        subtitle={`${t('common.round')} ${selectedRound} · ${t('competitive_intel.competitor_analysis')}`}
        actions={<Select value={selectedRound} onChange={setSelectedRound} options={roundOptions} style={{ width: 140 }} />}
      />
      <Tabs className="ds-colored-tabs" items={tabItems} defaultActiveKey="overview" />
    </div>
  );
};

export default CompetitiveIntelPage;
