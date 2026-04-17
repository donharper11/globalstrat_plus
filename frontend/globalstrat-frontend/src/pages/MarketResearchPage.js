import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Tabs, Select, Tag, Progress, Table, Row, Col,
  Typography, Space, Empty, Alert, Input, Button, message,
} from 'antd';
import { useGame } from '../contexts/GameContext';
import { getResearchReport } from '../api/decisions';
import client from '../api/client';
import LoadingSpinner from '../components/LoadingSpinner';
import { PageHeader, PanelCard } from '../components/design-system';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const MAX_QUERIES = 5;

// --------------- helpers ---------------

const fitColor = (label) => {
  if (!label) return undefined;
  const l = label.toLowerCase();
  if (l === 'strong' || l === 'excellent') return 'green';
  if (l === 'moderate' || l === 'good') return 'gold';
  if (l === 'weak' || l === 'fair') return 'orange';
  if (l === 'very weak' || l === 'poor') return 'red';
  return undefined;
};

const importancePct = (label) => {
  if (!label) return 0;
  const l = label.toLowerCase();
  if (l === 'critical') return 100;
  if (l === 'high') return 80;
  if (l === 'moderate') return 60;
  if (l === 'low') return 40;
  return 30;
};

const money = (n) => {
  if (n == null) return '--';
  return `$${Number(n).toLocaleString()}`;
};

const pct = (n, decimals = 1) => {
  if (n == null) return '--';
  return `${(n * 100).toFixed(decimals)}%`;
};

// --------------- Expandable Row Toggle ---------------

const ExpandToggle = ({ expanded, onClick }) => (
  <span
    onClick={onClick}
    style={{
      cursor: 'pointer',
      display: 'inline-block',
      width: 20,
      fontSize: 12,
      color: 'var(--color-text-secondary)',
      userSelect: 'none',
    }}
  >
    {expanded ? '▼' : '▶'}
  </span>
);

// --------------- Tab 1: Segments ---------------

const SegmentDetail = ({ seg }) => {
  const { t } = useTranslation();
  return (
  <div style={{ padding: '12px 16px 12px 36px', background: 'var(--color-surface-50)', borderBottom: '1px solid var(--color-surface-200)' }}>
    <Row gutter={[24, 12]}>
      {/* Your position */}
      <Col xs={24} md={8}>
        <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>{t("market_research.your_position")}</Text>
        <Row gutter={16}>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.share')}</Text>
            <div><Text strong>{pct(seg.your_share)}</Text></div>
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.rank')}</Text>
            <div><Text strong>#{seg.your_rank ?? '--'}</Text></div>
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.fit')}</Text>
            <div><Tag color={fitColor(seg.your_fit_score_label)}>{seg.your_fit_score_label || '--'}</Tag></div>
          </Col>
        </Row>
      </Col>

      {/* Market leader */}
      <Col xs={24} md={8}>
        <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>{t("market_research.market_leader")}</Text>
        <Row gutter={16}>
          <Col span={12}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.competitor')}</Text>
            <div><Text strong>{seg.top_competitor || '--'}</Text></div>
          </Col>
          <Col span={12}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.share')}</Text>
            <div><Text strong>{pct(seg.top_competitor_share)}</Text></div>
          </Col>
        </Row>
      </Col>

      {/* Top valued features */}
      <Col xs={24} md={8}>
        {seg.top_valued_features && seg.top_valued_features.length > 0 && (
          <>
            <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>{t("market_research.top_valued_features")}</Text>
            {seg.top_valued_features.slice(0, 3).map((f) => (
              <div key={f.name} style={{ marginBottom: 4 }}>
                <Row align="middle">
                  <Col span={10}><Text style={{ fontSize: 12 }}>{f.name}</Text></Col>
                  <Col span={14}>
                    <Progress
                      percent={importancePct(f.importance)}
                      size="small"
                      format={() => f.importance}
                      strokeColor={f.importance === 'Critical' ? '#f5222d' : f.importance === 'High' ? '#fa8c16' : '#1890ff'}
                    />
                  </Col>
                </Row>
              </div>
            ))}
          </>
        )}
      </Col>
    </Row>

    {/* Price sensitivity & opportunity */}
    <Row gutter={[24, 8]} style={{ marginTop: 8 }}>
      {seg.price_sensitivity && (
        <Col>
          <Text type="secondary" style={{ fontSize: 12 }}>{t("market_research.price_sensitivity")}: </Text>
          <Tag>{seg.price_sensitivity}</Tag>
        </Col>
      )}
      {seg.opportunity_signal && (
        <Col xs={24}>
          <Alert type="info" message={t('market_research.opportunity')} description={seg.opportunity_signal} showIcon={false} style={{ marginTop: 4 }} />
        </Col>
      )}
    </Row>
  </div>
  );
};

const SegmentsTab = ({ gameId, teamId, round }) => {
  const { t } = useTranslation();
  const [market, setMarket] = useState('NA');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [markets, setMarkets] = useState([]);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    if (!gameId || !teamId) return;
    getResearchReport(gameId, teamId, 'markets')
      .then((res) => {
        const list = res.data?.markets || [];
        setMarkets(list.map((m) => ({ label: m.name, value: m.code })));
        if (list.length > 0 && !list.find((m) => m.code === market)) {
          setMarket(list[0].code);
        }
      })
      .catch(() => {});
  }, [gameId, teamId]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = useCallback(async () => {
    if (!gameId || !teamId || !market) return;
    setLoading(true);
    setError(null);
    try {
      const params = { market };
      if (round != null) params.round = round;
      const res = await getResearchReport(gameId, teamId, 'segments', params);
      setData(res.data);
      setExpanded({});
    } catch (err) {
      setError(err.response?.data?.detail || t('market_research.failed_load_segments'));
    } finally {
      setLoading(false);
    }
  }, [gameId, teamId, market, round]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const toggle = (name) => setExpanded(prev => ({ ...prev, [name]: !prev[name] }));

  const segments = data?.segments || [];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ marginRight: 8 }}>{t("market_research.market_label")}:</Text>
        <Select
          value={market}
          onChange={setMarket}
          options={markets.length > 0 ? markets : []}
          style={{ width: '100%', maxWidth: 220 }}
        />
      </div>

      {loading && <LoadingSpinner tip={t("market_research.loading_segments")} />}
      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

      {!loading && data && (
        segments.length === 0 ? (
          <Empty description={t("market_research.no_segment_data")} />
        ) : (
          <PanelCard headerColor="market" title={t("market_research.customer_segments").toUpperCase()}>
            <div className="ds-data-table-wrapper">
              <table className="ds-data-table">
                <thead>
                  <tr>
                    <th style={{ width: 28 }}></th>
                    <th>{t('market_research.segment')}</th>
                    <th>{t('market_research.type')}</th>
                    <th className="text-right">{t('market_research.population')}</th>
                    <th className="text-right">{t('market_research.growth')}</th>
                    <th className="text-right">{t('market_research.your_share')}</th>
                    <th>{t('market_research.your_rank')}</th>
                    <th>{t('market_research.fit')}</th>
                    <th>{t('market_research.leader')}</th>
                    <th>{t('market_research.signals')}</th>
                  </tr>
                </thead>
                <tbody>
                  {segments.map((seg) => (
                    <React.Fragment key={seg.name}>
                      <tr
                        onClick={() => toggle(seg.name)}
                        style={{ cursor: 'pointer' }}
                      >
                        <td><ExpandToggle expanded={!!expanded[seg.name]} onClick={() => {}} /></td>
                        <td><Text strong>{seg.name}</Text></td>
                        <td>
                          <Space size={4}>
                            <Tag style={{ margin: 0 }}>{seg.type || t('market_research.customer')}</Tag>
                            {seg.underserved && <Tag color="blue" style={{ margin: 0 }}>{t('market_research.underserved')}</Tag>}
                          </Space>
                        </td>
                        <td className="text-right">{seg.population?.toLocaleString() ?? '--'}</td>
                        <td className="text-right">{seg.growth_label || pct(seg.growth_rate)}</td>
                        <td className="text-right">{pct(seg.your_share)}</td>
                        <td>#{seg.your_rank ?? '--'}</td>
                        <td><Tag color={fitColor(seg.your_fit_score_label)} style={{ margin: 0 }}>{seg.your_fit_score_label || '--'}</Tag></td>
                        <td>{seg.top_competitor || '--'}</td>
                        <td>
                          {seg.opportunity_signal && <Tag color="blue" style={{ margin: 0 }}>{t('market_research.opportunity')}</Tag>}
                          {seg.price_sensitivity && <Tag style={{ margin: 0 }}>{seg.price_sensitivity}</Tag>}
                        </td>
                      </tr>
                      {expanded[seg.name] && (
                        <tr>
                          <td colSpan={10} style={{ padding: 0 }}>
                            <SegmentDetail seg={seg} />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </PanelCard>
        )
      )}
    </div>
  );
};

// --------------- Tab 2: Products ---------------

const getSegFitColumns = (t) => [
  { title: t('market_research.segment'), dataIndex: 'segment', key: 'segment' },
  { title: t('market_research.fit'), dataIndex: 'fit_label', key: 'fit_label', render: (v) => <Tag color={fitColor(v)}>{v}</Tag> },
  { title: t('market_research.adoption'), dataIndex: 'adoption', key: 'adoption', render: (v) => (v != null ? v.toLocaleString() : '--') },
];

const ProductDetail = ({ prod }) => {
  const { t } = useTranslation();
  return (
  <div style={{ padding: '12px 16px 12px 36px', background: 'var(--color-surface-50)', borderBottom: '1px solid var(--color-surface-200)' }}>
    {/* Feature levels */}
    {prod.features && prod.features.length > 0 && (
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>{t("market_research.feature_levels")}</Text>
        <Row gutter={[16, 4]}>
          {prod.features.map((f) => (
            <Col xs={12} sm={8} md={6} key={f.name}>
              <Text style={{ fontSize: 12 }}>{f.name}</Text>
              <Progress percent={Math.round((f.level / 10) * 100)} size="small" format={() => f.level} />
            </Col>
          ))}
        </Row>
      </div>
    )}

    {/* Market performance */}
    {prod.markets && prod.markets.map((mkt) => (
      <div key={mkt.market} style={{ marginBottom: 16, padding: 12, background: '#fff', borderRadius: 4, border: '1px solid var(--color-surface-200)' }}>
        <Text strong style={{ display: 'block', marginBottom: 8 }}>{mkt.market}</Text>
        <Row gutter={16} style={{ marginBottom: 8 }}>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.units_sold')}</Text>
            <div><Text strong>{mkt.units_sold?.toLocaleString() ?? '--'}</Text></div>
          </Col>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.revenue')}</Text>
            <div><Text strong>{money(mkt.revenue)}</Text></div>
          </Col>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.margin')}</Text>
            <div><Text strong>{pct(mkt.margin_pct)}</Text></div>
          </Col>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.rank')}</Text>
            <div><Text strong>#{mkt.market_rank ?? '--'}</Text></div>
          </Col>
        </Row>

        {mkt.segment_fit && mkt.segment_fit.length > 0 && (
          <Table
            dataSource={mkt.segment_fit.map((s, i) => ({ ...s, key: i }))}
            columns={getSegFitColumns(t)}
            pagination={false}
            size="small"
            style={{ marginBottom: 8 }}
          />
        )}

        <Row gutter={16}>
          {mkt.strongest_segment && (
            <Col span={12}><Text type="secondary">{t('market_research.strongest')}: </Text><Tag color="green">{mkt.strongest_segment}</Tag></Col>
          )}
          {mkt.weakest_segment && (
            <Col span={12}><Text type="secondary">{t('market_research.weakest')}: </Text><Tag color="red">{mkt.weakest_segment}</Tag></Col>
          )}
        </Row>

        {mkt.recommendation && (
          <Alert type="info" message={t("market_research.recommendation")} description={mkt.recommendation} showIcon={false} style={{ marginTop: 8 }} />
        )}
      </div>
    ))}
  </div>
  );
};

const ProductsTab = ({ gameId, teamId, round }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    if (!gameId || !teamId) return;
    setLoading(true);
    const params = round != null ? { round } : {};
    getResearchReport(gameId, teamId, 'products', params)
      .then((res) => setData(res.data))
      .catch((err) => setError(err.response?.data?.detail || t('market_research.failed_load_products')))
      .finally(() => setLoading(false));
  }, [gameId, teamId, round]);

  if (loading) return <LoadingSpinner tip={t("market_research.loading_products")} />;
  if (error) return <Alert type="error" message={error} />;
  if (!data || !data.products || data.products.length === 0) {
    return <Empty description={t("market_research.no_product_data")} />;
  }

  const toggle = (name) => setExpanded(prev => ({ ...prev, [name]: !prev[name] }));

  // Compute summary metrics for each product
  const products = data.products;

  return (
    <PanelCard headerColor="market" title={t("market_research.product_analysis").toUpperCase()}>
      <div className="ds-data-table-wrapper">
        <table className="ds-data-table">
          <thead>
            <tr>
              <th style={{ width: 28 }}></th>
              <th>{t('market_research.product')}</th>
              <th>{t('market_research.platform')}</th>
              <th>{t('market_research.positioning')}</th>
              <th className="text-right">{t('market_research.markets')}</th>
              <th className="text-right">{t('market_research.total_revenue')}</th>
              <th className="text-right">{t('market_research.avg_margin')}</th>
              <th>{t('market_research.best_rank')}</th>
            </tr>
          </thead>
          <tbody>
            {products.map((prod) => {
              const totalRev = (prod.markets || []).reduce((s, m) => s + (m.revenue || 0), 0);
              const margins = (prod.markets || []).filter(m => m.margin_pct != null);
              const avgMargin = margins.length > 0 ? margins.reduce((s, m) => s + m.margin_pct, 0) / margins.length : null;
              const bestRank = (prod.markets || []).reduce((best, m) => {
                if (m.market_rank == null) return best;
                return best == null ? m.market_rank : Math.min(best, m.market_rank);
              }, null);

              return (
                <React.Fragment key={prod.name}>
                  <tr onClick={() => toggle(prod.name)} style={{ cursor: 'pointer' }}>
                    <td><ExpandToggle expanded={!!expanded[prod.name]} onClick={() => {}} /></td>
                    <td><Text strong>{prod.name}</Text></td>
                    <td>{prod.platform ? <Tag style={{ margin: 0 }}>{prod.platform}</Tag> : '--'}</td>
                    <td>
                      {prod.positioning ? (
                        <Tag color={prod.positioning === 'premium' ? 'purple' : 'blue'} style={{ margin: 0 }}>{prod.positioning}</Tag>
                      ) : '--'}
                    </td>
                    <td className="text-right">{(prod.markets || []).length}</td>
                    <td className="text-right">{money(totalRev)}</td>
                    <td className="text-right">{pct(avgMargin)}</td>
                    <td>{bestRank != null ? `#${bestRank}` : '--'}</td>
                  </tr>
                  {expanded[prod.name] && (
                    <tr>
                      <td colSpan={8} style={{ padding: 0 }}>
                        <ProductDetail prod={prod} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </PanelCard>
  );
};

// --------------- Tab 3: Markets ---------------

const MarketDetail = ({ mkt }) => {
  const { t } = useTranslation();
  return (
  <div style={{ padding: '12px 16px 12px 36px', background: 'var(--color-surface-50)', borderBottom: '1px solid var(--color-surface-200)' }}>
    <Row gutter={[24, 12]}>
      {/* Currency and costs */}
      <Col xs={24} md={12}>
        <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>{t("market_research.currency_costs")}</Text>
        <Row gutter={16}>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.currency')}</Text>
            <div><Text strong>{mkt.currency_code || '--'}</Text></div>
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.exchange_rate')}</Text>
            <div><Text strong>{mkt.exchange_rate != null ? mkt.exchange_rate.toFixed(2) : '--'}</Text></div>
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.volatility')}</Text>
            <div><Text strong>{pct(mkt.exchange_rate_volatility)}</Text></div>
          </Col>
        </Row>
        <Row gutter={16} style={{ marginTop: 8 }}>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.tariff')}</Text>
            <div><Text strong>{pct(mkt.tariff_rate)}</Text></div>
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.tax_rate')}</Text>
            <div><Text strong>{pct(mkt.tax_rate)}</Text></div>
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.entry_cost')}</Text>
            <div><Text strong>{money(mkt.entry_cost_base)}</Text></div>
          </Col>
        </Row>
      </Col>

      {/* Infrastructure */}
      <Col xs={24} md={12}>
        <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>{t("market_research.infrastructure_regulation")}</Text>
        <Row gutter={16}>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.regulatory')}</Text>
            <Progress percent={(mkt.regulatory_difficulty ?? 0) * 10} size="small" format={() => `${mkt.regulatory_difficulty ?? '--'}/10`} />
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.infrastructure')}</Text>
            <Progress percent={(mkt.infrastructure_quality ?? 0) * 10} size="small" format={() => `${mkt.infrastructure_quality ?? '--'}/10`} strokeColor="#52c41a" />
          </Col>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.manufacturing')}</Text>
            <div>
              <Space size={4} wrap>
                {mkt.your_plant && <Tag color="green" style={{ margin: 0 }}>{t('market_research.your_plant')}</Tag>}
                {mkt.contract_mfg_available && <Tag style={{ margin: 0 }}>{t('market_research.contract_mfg')}</Tag>}
                {!mkt.manufacturing_available && !mkt.your_plant && <Tag color="red" style={{ margin: 0 }}>{t('market_research.unavailable')}</Tag>}
                {mkt.manufacturing_available && !mkt.your_plant && !mkt.contract_mfg_available && <Tag style={{ margin: 0 }}>{t('market_research.available')}</Tag>}
              </Space>
            </div>
          </Col>
        </Row>
      </Col>
    </Row>

    {/* Segment breakdown */}
    {mkt.segment_breakdown && mkt.segment_breakdown.length > 0 && (
      <div style={{ marginTop: 12 }}>
        <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 12, textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>{t("market_research.segment_breakdown")}</Text>
        {mkt.segment_breakdown.map((sb) => (
          <div key={sb.segment} style={{ marginBottom: 4 }}>
            <Row align="middle">
              <Col span={6}><Text style={{ fontSize: 12 }}>{sb.segment}</Text></Col>
              <Col span={14}><Progress percent={Math.round((sb.pct_of_market ?? 0) * 100)} size="small" format={(p) => `${p}%`} /></Col>
              <Col span={4}><Text type="secondary" style={{ fontSize: 11 }}>{sb.growth || ''}</Text></Col>
            </Row>
          </div>
        ))}
      </div>
    )}

    {mkt.competitive_intensity && (
      <div style={{ marginTop: 8 }}><Text type="secondary">{t("market_research.competition")}: </Text><Text>{mkt.competitive_intensity}</Text></div>
    )}

    {!mkt.your_presence && (
      <Alert
        type="warning"
        message={t("market_research.entry_barriers")}
        description={
          <Space direction="vertical" size={2}>
            <Text>{t('market_research.entry_cost')}: {money(mkt.entry_cost_base)}</Text>
            <Text>{t('market_research.regulatory_difficulty')}: {mkt.regulatory_difficulty ?? '--'}/10</Text>
            <Text>{t('market_research.tariff_rate_label')}: {pct(mkt.tariff_rate)}</Text>
          </Space>
        }
        showIcon={false}
        style={{ marginTop: 8 }}
      />
    )}

    {mkt.opportunity_summary && (
      <Alert type="info" message={t("market_research.opportunity")} description={mkt.opportunity_summary} showIcon={false} style={{ marginTop: 8 }} />
    )}
  </div>
  );
};

const MarketsTab = ({ gameId, teamId, round }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    if (!gameId || !teamId) return;
    setLoading(true);
    const params = round != null ? { round } : {};
    getResearchReport(gameId, teamId, 'markets', params)
      .then((res) => setData(res.data))
      .catch((err) => setError(err.response?.data?.detail || t('market_research.failed_load_markets')))
      .finally(() => setLoading(false));
  }, [gameId, teamId, round]);

  if (loading) return <LoadingSpinner tip={t("market_research.loading_markets")} />;
  if (error) return <Alert type="error" message={error} />;
  if (!data || !data.markets || data.markets.length === 0) {
    return <Empty description={t("market_research.no_market_data")} />;
  }

  const toggle = (key) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  const mkts = data.markets;

  return (
    <PanelCard headerColor="market" title={t("market_research.market_overview").toUpperCase()}>
      <div className="ds-data-table-wrapper">
        <table className="ds-data-table">
          <thead>
            <tr>
              <th style={{ width: 28 }}></th>
              <th>{t('market_research.market')}</th>
              <th>{t('market_research.status')}</th>
              <th>{t('market_research.entry_mode')}</th>
              <th className="text-right">{t('market_research.market_size')}</th>
              <th className="text-right">{t('market_research.growth')}</th>
              <th className="text-right">{t('market_research.your_share')}</th>
              <th>{t('market_research.competition_header')}</th>
              <th>{t('market_research.signals')}</th>
            </tr>
          </thead>
          <tbody>
            {mkts.map((mkt) => {
              const key = mkt.code || mkt.name;
              return (
                <React.Fragment key={key}>
                  <tr onClick={() => toggle(key)} style={{ cursor: 'pointer' }}>
                    <td><ExpandToggle expanded={!!expanded[key]} onClick={() => {}} /></td>
                    <td><Text strong>{mkt.name}</Text></td>
                    <td>
                      {mkt.your_presence
                        ? <Tag color="green" style={{ margin: 0 }}>{t('market_research.active')}</Tag>
                        : <Tag style={{ margin: 0 }}>{t('market_research.not_entered')}</Tag>}
                    </td>
                    <td>{mkt.your_entry_mode || '--'}</td>
                    <td className="text-right">{mkt.total_market_size?.toLocaleString() ?? '--'}</td>
                    <td className="text-right">{pct(mkt.growth_rate)}</td>
                    <td className="text-right">{mkt.your_presence ? pct(mkt.your_total_share) : '--'}</td>
                    <td>{mkt.competitive_intensity || '--'}</td>
                    <td>{mkt.opportunity_summary ? <Tag color="blue" style={{ margin: 0 }}>{t('market_research.opportunity')}</Tag> : ''}</td>
                  </tr>
                  {expanded[key] && (
                    <tr>
                      <td colSpan={9} style={{ padding: 0 }}>
                        <MarketDetail mkt={mkt} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </PanelCard>
  );
};

// --------------- Tab 4: Channels ---------------

const ChannelsTab = ({ gameId, teamId, round }) => {
  const { t } = useTranslation();
  const [market, setMarket] = useState('NA');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [markets, setMarkets] = useState([]);

  useEffect(() => {
    if (!gameId || !teamId) return;
    getResearchReport(gameId, teamId, 'markets')
      .then((res) => {
        const list = res.data?.markets || [];
        setMarkets(list.map((m) => ({ label: m.name, value: m.code })));
        if (list.length > 0 && !list.find((m) => m.code === market)) {
          setMarket(list[0].code);
        }
      })
      .catch(() => {});
  }, [gameId, teamId]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = useCallback(async () => {
    if (!gameId || !teamId || !market) return;
    setLoading(true);
    setError(null);
    try {
      const params = { market };
      if (round != null) params.round = round;
      const res = await getResearchReport(gameId, teamId, 'channels', params);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t('market_research.failed_load_channels'));
    } finally {
      setLoading(false);
    }
  }, [gameId, teamId, market, round]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ marginRight: 8 }}>{t("market_research.market_label")}:</Text>
        <Select
          value={market}
          onChange={setMarket}
          options={markets.length > 0 ? markets : []}
          style={{ width: '100%', maxWidth: 220 }}
        />
      </div>

      {loading && <LoadingSpinner tip={t("market_research.loading_channels")} />}
      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

      {!loading && data && (
        <>
          {data.is_present_in_market === false && (
            <Alert
              type="info" showIcon
              message={t("market_research.not_operating_in_market")}
              description={t("market_research.not_operating_desc")}
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Current strategy summary */}
          <PanelCard headerColor="strategic" title={t("market_research.your_distribution_strategy").toUpperCase()}>
            <Row gutter={16}>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.your_strategy')}</Text>
                <div>
                  <Text strong>
                    {data.your_distribution_strategy
                      ? data.your_distribution_strategy.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                      : data.is_present_in_market === false ? t('market_research.not_in_market') : '--'}
                  </Text>
                </div>
              </Col>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.sales_reps')}</Text>
                <div><Text strong>{data.your_sales_reps ?? '--'}</Text></div>
              </Col>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('market_research.reach_estimate')}</Text>
                <div><Text strong>{pct(data.your_reach_estimate)}</Text></div>
              </Col>
            </Row>
          </PanelCard>

          {/* Channel comparison table */}
          <PanelCard headerColor="market" title={t("market_research.channel_comparison").toUpperCase()}>
            {data.channel_comparison && data.channel_comparison.length > 0 ? (
              <div className="ds-data-table-wrapper">
                <table className="ds-data-table">
                  <thead>
                    <tr>
                      <th>{t('market_research.strategy')}</th>
                      <th className="text-right">{t('market_research.your_reach')}</th>
                      {!data.is_present_in_market && <th className="text-right">{t('market_research.if_entered')}</th>}
                      <th className="text-right">{t('market_research.margin_impact')}</th>
                      <th>{t('market_research.fit_budget')}</th>
                      <th>{t('market_research.fit_premium')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.channel_comparison.map((c, i) => {
                      const isCurrent = data.your_distribution_strategy === c.key;
                      return (
                        <tr key={c.key || i} className={isCurrent ? 'highlight-row' : ''}>
                          <td>
                            <Space>
                              <Text strong={isCurrent}>{c.strategy}</Text>
                              {isCurrent && <Tag color="blue" style={{ margin: 0 }}>{t('market_research.current')}</Tag>}
                            </Space>
                          </td>
                          <td className="text-right">{pct(c.reach)}</td>
                          {!data.is_present_in_market && (
                            <td className="text-right">
                              <Text type="secondary">{pct(c.theoretical_reach)}</Text>
                            </td>
                          )}
                          <td className="text-right">
                            {c.margin_impact != null ? (
                              <Text style={{ color: c.margin_impact >= 0 ? 'var(--color-positive)' : 'var(--color-negative)' }}>
                                {c.margin_impact >= 0 ? '+' : ''}{pct(c.margin_impact)}
                              </Text>
                            ) : '--'}
                          </td>
                          <td><Tag color={fitColor(c.fit_with_budget)} style={{ margin: 0 }}>{c.fit_with_budget || '--'}</Tag></td>
                          <td><Tag color={fitColor(c.fit_with_premium)} style={{ margin: 0 }}>{c.fit_with_premium || '--'}</Tag></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty description={t("market_research.no_channel_data")} />
            )}
          </PanelCard>
        </>
      )}
    </div>
  );
};

// --------------- Tab 5: Ask the Analyst ---------------

const AskAnalystTab = ({ gameId, teamId, currentRound }) => {
  const { t } = useTranslation();
  const [queries, setQueries] = useState([]);
  const [queryText, setQueryText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchQueries = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const res = await client.get(
        `/games/${gameId}/teams/${teamId}/research/queries/`
      );
      setQueries(res.data?.queries || []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [gameId, teamId]);

  useEffect(() => { fetchQueries(); }, [fetchQueries]);

  const handleSubmit = async () => {
    if (!queryText.trim()) return;
    if (queries.length >= MAX_QUERIES) {
      message.warning(t('market_research.query_limit_reached', { max: MAX_QUERIES }));
      return;
    }
    setSubmitting(true);
    try {
      const res = await client.post(
        `/games/${gameId}/teams/${teamId}/research/query/`,
        { query_text: queryText.trim() }
      );
      setQueries((prev) => [
        {
          query_text: queryText.trim(),
          response_text: res.data?.response || t('market_research.no_response_available'),
          queried_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      setQueryText('');
      message.success(t('market_research.query_submitted'));
    } catch (err) {
      const msg =
        err.response?.data?.error ||
        err.response?.data?.detail ||
        t('market_research.query_failed');
      message.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner tip={t("market_research.loading_queries")} />;

  const remaining = Math.max(0, MAX_QUERIES - queries.length);

  return (
    <div>
      <PanelCard headerColor="strategic" title={t("market_research.ai_analyst").toUpperCase()}>
        <Paragraph type="secondary">
          {t("market_research.ai_analyst_desc", { max: MAX_QUERIES })}
        </Paragraph>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <TextArea
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            placeholder={t("market_research.query_placeholder")}
            autoSize={{ minRows: 1, maxRows: 3 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            disabled={remaining <= 0}
            style={{ flex: 1 }}
          />
          <Button
            type="primary"
            onClick={handleSubmit}
            loading={submitting}
            disabled={!queryText.trim() || remaining <= 0}
          >
            {t("market_research.ask")}
          </Button>
        </div>
        <Text type="secondary">
          {t("market_research.queries_this_round")}: {queries.length} / {MAX_QUERIES}
          {remaining > 0 ? ` (${remaining} ${t("market_research.remaining")})` : ''}
        </Text>
      </PanelCard>

      <PanelCard headerColor="neutral" title={`${t("market_research.recent_queries")} — ${t("common.round")} ${currentRound}`.toUpperCase()}>
        {queries.length > 0 ? (
          <div className="ds-data-table-wrapper">
            {queries.map((q, i) => (
              <div key={i} style={{ padding: '12px 0', borderBottom: '1px solid var(--color-surface-200)' }}>
                <div style={{ marginBottom: 6 }}>
                  <Tag color="blue" style={{ marginRight: 6 }}>Q</Tag>
                  <Text strong>{q.query_text}</Text>
                </div>
                <div style={{ paddingLeft: 28 }}>
                  <Text style={{ fontSize: 13 }}>{q.response_text}</Text>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {new Date(q.queried_at).toLocaleString()}
                  </Text>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Empty description={t("market_research.no_queries")} />
        )}
      </PanelCard>
    </div>
  );
};

// --------------- Stakeholders Tab ---------------

const StakeholdersTab = ({ gameId, teamId, round }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    if (gameId && teamId && round != null) {
      getResearchReport(gameId, teamId, 'stakeholders', { round }).then(r => setData(r.data));
    }
  }, [gameId, teamId, round]);

  if (!data) return <div style={{ padding: 24, textAlign: 'center' }}><Text type="secondary">{t('market_research.loading_stakeholders')}</Text></div>;

  const toggleExpand = (key) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }));

  const satColor = (v) => v >= 0.7 ? '#52c41a' : v >= 0.5 ? '#faad14' : '#ff4d4f';
  const satLabel = (v) => v >= 0.7 ? t('market_research.strong') : v >= 0.5 ? t('market_research.moderate') : v >= 0.3 ? t('market_research.weak') : t('market_research.low');
  const gapColor = (status) => status === 'aligned' ? '#52c41a' : status === 'over' ? '#1677ff' : '#ff4d4f';

  return (
    <div>
      {(data.stakeholder_groups || []).map(grp => (
        <div key={grp.type} style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Text strong style={{ fontSize: 14 }}>{grp.label}</Text>
            <Tag color="blue">{grp.segments.length}</Tag>
          </div>
          <table className="ds-data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ width: 30 }}></th>
                <th>{t('market_research.segment')}</th>
                <th>{t('market_research.market')}</th>
                <th>{t('market_research.satisfaction')}</th>
                <th>{t('market_research.index_weight')}</th>
                <th>{t('market_research.trend')}</th>
              </tr>
            </thead>
            <tbody>
              {grp.segments.map(seg => {
                const key = `${grp.type}-${seg.name}`;
                const isExpanded = expanded[key];
                return (
                  <React.Fragment key={key}>
                    <tr onClick={() => toggleExpand(key)} style={{ cursor: 'pointer' }}>
                      <td style={{ fontSize: 10 }}>{isExpanded ? '▼' : '▶'}</td>
                      <td><Text strong style={{ fontSize: 12 }}>{seg.name}</Text></td>
                      <td><Text style={{ fontSize: 12 }}>{seg.market}</Text></td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 60, height: 6, background: '#f0f0f0', borderRadius: 3, overflow: 'hidden' }}>
                            <div style={{ width: `${(seg.satisfaction || 0) * 100}%`, height: '100%', background: satColor(seg.satisfaction), borderRadius: 3 }} />
                          </div>
                          <Text style={{ fontSize: 11, color: satColor(seg.satisfaction) }}>{satLabel(seg.satisfaction)}</Text>
                        </div>
                      </td>
                      <td><Text style={{ fontSize: 11 }}>{(seg.weight * 100).toFixed(1)}%</Text></td>
                      <td>
                        <div style={{ display: 'flex', gap: 2, alignItems: 'end' }}>
                          {(seg.trend || []).map((v, i) => (
                            <div key={i} style={{
                              width: 8, height: v != null ? Math.max(v * 30, 3) : 3,
                              background: v != null ? satColor(v) : '#e0e0e0',
                              borderRadius: 1,
                            }} />
                          ))}
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr>
                        <td colSpan={6} style={{ padding: '8px 16px', background: '#fafafa' }}>
                          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>{seg.description}</Text>
                          {seg.gaps && seg.gaps.length > 0 && (
                            <table className="ds-data-table" style={{ width: '100%', fontSize: 11 }}>
                              <thead>
                                <tr>
                                  <th>{t('market_research.feature')}</th>
                                  <th>{t('market_research.weight')}</th>
                                  <th>{t('market_research.ideal')}</th>
                                  <th>{t('market_research.actual')}</th>
                                  <th>{t('market_research.gap')}</th>
                                  <th>{t('market_research.status')}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {seg.gaps.map(g => (
                                  <tr key={g.feature_code}>
                                    <td>{g.feature}</td>
                                    <td>{(g.weight * 100).toFixed(0)}%</td>
                                    <td>{g.ideal.toFixed(1)}</td>
                                    <td>{g.actual.toFixed(1)}</td>
                                    <td style={{ color: gapColor(g.status), fontWeight: 600 }}>
                                      {g.gap > 0 ? '+' : ''}{g.gap.toFixed(1)}
                                    </td>
                                    <td>
                                      <span style={{ color: gapColor(g.status), fontSize: 10 }}>
                                        {g.status === 'aligned' ? `✓ ${t('market_research.aligned')}` : g.status === 'over' ? `↑ ${t('market_research.exceeds')}` : `↓ ${t('market_research.below')}`}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
};

// --------------- Main Page ---------------

const MarketResearchPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound } = useGame();
  const latestProcessed = Math.max((currentRound || 1) - 1, 0);
  const [viewRound, setViewRound] = useState(null);

  useEffect(() => {
    if (currentRound != null && viewRound === null) {
      setViewRound(latestProcessed);
    }
  }, [currentRound, latestProcessed, viewRound]);

  const roundOptions = [];
  for (let r = 0; r <= latestProcessed; r++) {
    roundOptions.push({ label: `${t('common.round')} ${r}`, value: r });
  }

  const tabItems = [
    {
      key: 'segments',
      label: t('market_research.segments'),
      children: <SegmentsTab gameId={gameId} teamId={teamId} round={viewRound} />,
    },
    {
      key: 'products',
      label: t('market_research.products'),
      children: <ProductsTab gameId={gameId} teamId={teamId} round={viewRound} />,
    },
    {
      key: 'markets',
      label: t('market_research.markets'),
      children: <MarketsTab gameId={gameId} teamId={teamId} round={viewRound} />,
    },
    {
      key: 'channels',
      label: t('market_research.channels'),
      children: <ChannelsTab gameId={gameId} teamId={teamId} round={viewRound} />,
    },
    {
      key: 'stakeholders',
      label: t('market_research.stakeholders'),
      children: <StakeholdersTab gameId={gameId} teamId={teamId} round={viewRound} />,
    },
    {
      key: 'analyst',
      label: t('market_research.ask_analyst'),
      children: (
        <AskAnalystTab
          gameId={gameId}
          teamId={teamId}
          currentRound={currentRound}
        />
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      <PageHeader title={t("market_research.title")} subtitle={t("market_research.subtitle")} />
      <Tabs
        className="ds-colored-tabs"
        defaultActiveKey="segments"
        items={tabItems}
        tabBarExtraContent={
          roundOptions.length > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>{t("market_research.viewing")}:</Text>
              <Select
                value={viewRound}
                onChange={setViewRound}
                options={roundOptions}
                size="small"
                style={{ width: 110 }}
              />
            </div>
          )
        }
      />
    </div>
  );
};

export default MarketResearchPage;
