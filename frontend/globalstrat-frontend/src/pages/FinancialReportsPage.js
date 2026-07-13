import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Card, Select, Typography, Row, Col, Statistic, Table, Tabs, Progress, Empty, Tag, Alert, Space,
} from 'antd';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  LineChart, Line, AreaChart, Area,
} from 'recharts';
import { useGame } from '../contexts/GameContext';
import { getFinancialHistory } from '../api/cc15';
import { getInvestorRelations } from '../api/results';
import { getGovernmentRelations } from '../api/decisions';
import { getHedgePositions, getTradeFinance } from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader, MetricRow } from '../components/design-system';
import InvestorProfilePopover, { InvestorNameLink } from '../components/InvestorProfilePopover';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const abs = Math.abs(v);
  if (abs >= 1000000) return `$${(v / 1000000).toFixed(1)}M`;
  if (abs >= 1000) return `$${(v / 1000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
};

const pct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : '—';

const RatioRow = ({ label, value, suffix, thresholds, note }) => {
  // thresholds: [{min, color, label}] sorted ascending
  let color = '#888';
  let statusLabel = '';
  if (thresholds && value != null) {
    for (const t of thresholds) {
      if (value >= t.min) { color = t.color; statusLabel = t.label; }
    }
  }
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
      <Text style={{ fontSize: 12 }}>{label}</Text>
      <div style={{ textAlign: 'right' }}>
        <Text strong style={{ fontSize: 13 }}>
          {value != null ? `${typeof value === 'number' ? value.toFixed(1) : value}${suffix || ''}` : '—'}
        </Text>
        {statusLabel && <Tag color={color} style={{ marginLeft: 6, fontSize: 10 }}>{statusLabel}</Tag>}
        {note && <div><Text type="secondary" style={{ fontSize: 10 }}>{note}</Text></div>}
      </div>
    </div>
  );
};

const RatiosTab = ({ current, fmt, pct }) => {
  const { t } = useTranslation();
  const c = current;
  const grossMargin = c.gross_margin_pct ? c.gross_margin_pct * 100 : 0;
  const netMargin = c.net_margin_pct ? c.net_margin_pct * 100 : 0;
  const roe = c.roe ? c.roe * 100 : 0;
  const roa = c.total_assets > 0 ? (c.net_income / c.total_assets) * 100 : 0;
  const de = c.debt_to_equity || 0;

  // Liquidity
  const burnRate = c.net_income < 0 ? Math.abs(c.net_income) : 0;
  const cashRunway = burnRate > 0 ? c.cash_closing / burnRate : null; // null = profitable
  const cashRevPct = c.total_revenue > 0 ? (c.cash_closing / c.total_revenue) * 100 : 0;

  // Leverage
  const interestCoverage = c.interest_expense > 0 ? c.operating_income / c.interest_expense : null;

  // Efficiency
  const totalInvValue = (c.products || []).reduce((s, p) => s + (p.inventory_value || 0), 0);
  const totalSold = (c.products || []).reduce((s, p) => s + (p.units_sold || 0), 0);
  const totalUnsold = (c.products || []).reduce((s, p) => s + (p.units_unsold || 0), 0);
  const invTurnover = totalUnsold > 0 ? totalSold / totalUnsold : (totalSold > 0 ? null : 0);
  const rdPct = c.total_revenue > 0 ? (c.rd_expense / c.total_revenue) * 100 : 0;
  const mktgPct = c.total_revenue > 0 ? (c.marketing_expense / c.total_revenue) * 100 : 0;

  // Credit rating
  let creditScore = 0;
  if (de < 0.3) creditScore += 3; else if (de < 0.7) creditScore += 2; else if (de < 1.5) creditScore += 1;
  if (c.interest_expense > 0) {
    const cov = c.operating_income / c.interest_expense;
    if (cov > 10) creditScore += 3; else if (cov > 5) creditScore += 2; else if (cov > 2) creditScore += 1;
  } else creditScore += 3;
  if (cashRunway === null) creditScore += 3;
  else if (cashRunway > 8) creditScore += 3;
  else if (cashRunway > 4) creditScore += 2;
  else if (cashRunway > 2) creditScore += 1;
  if (netMargin > 15) creditScore += 3; else if (netMargin > 5) creditScore += 2; else if (netMargin > 0) creditScore += 1;

  const ratings = { 12: 'AAA', 11: 'AA+', 10: 'AA', 9: 'A+', 8: 'A', 7: 'BBB+', 6: 'BBB', 5: 'BB+', 4: 'BB', 3: 'B+', 2: 'B', 1: 'CCC', 0: 'D' };
  const riskLevels = { 12: 'VERY LOW', 11: 'VERY LOW', 10: 'LOW', 9: 'LOW', 8: 'LOW', 7: 'MODERATE', 6: 'MODERATE', 5: 'ELEVATED', 4: 'ELEVATED', 3: 'HIGH', 2: 'HIGH', 1: 'VERY HIGH', 0: 'DISTRESS' };
  const creditRating = ratings[Math.min(creditScore, 12)] || 'B';
  const distressRisk = riskLevels[Math.min(creditScore, 12)] || 'HIGH';

  // Warnings and strengths
  const warnings = [];
  const strengths = [];
  if (rdPct === 0 && c.total_revenue > 0) warnings.push(t('financial_reports.warn_zero_rd'));
  if (mktgPct === 0 && c.total_revenue > 0) warnings.push(t('financial_reports.warn_no_marketing'));
  if (cashRevPct > 200) warnings.push(t('financial_reports.warn_high_cash'));
  if (grossMargin > 50) strengths.push(t('financial_reports.strength_margins'));
  if (de < 0.5) strengths.push(t('financial_reports.strength_leverage'));
  if (cashRunway === null || (cashRunway && cashRunway > 8)) strengths.push(t('financial_reports.strength_cash'));

  const profitThresholds = [
    { min: -Infinity, color: 'red', label: t('financial_reports.negative') },
    { min: 0, color: 'orange', label: t('financial_reports.break_even') },
    { min: 10, color: 'blue', label: t('financial_reports.moderate') },
    { min: 20, color: 'green', label: t('financial_reports.strong') },
    { min: 40, color: 'green', label: t('financial_reports.excellent') },
  ];

  return (
    <div>
      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card size="small" title={t('financial_reports.profitability')} style={{ marginBottom: 12 }}>
            <RatioRow label={t('financial_reports.gross_margin')} value={grossMargin} suffix="%" thresholds={profitThresholds} />
            <RatioRow label={t('financial_reports.net_margin')} value={netMargin} suffix="%" thresholds={profitThresholds} />
            <RatioRow label={t('financial_reports.roe')} value={roe} suffix="%" thresholds={[
              { min: -Infinity, color: 'red', label: t('financial_reports.negative') }, { min: 0, color: 'orange', label: t('financial_reports.low') },
              { min: 10, color: 'blue', label: t('financial_reports.moderate') }, { min: 15, color: 'green', label: t('financial_reports.good') },
            ]} />
            <RatioRow label={t('financial_reports.roa')} value={roa} suffix="%" thresholds={[
              { min: -Infinity, color: 'red', label: t('financial_reports.negative') }, { min: 0, color: 'orange', label: t('financial_reports.low') },
              { min: 5, color: 'blue', label: t('financial_reports.moderate') }, { min: 10, color: 'green', label: t('financial_reports.good') },
            ]} />
          </Card>

          <Card size="small" title={t('financial_reports.leverage')} style={{ marginBottom: 12 }}>
            <RatioRow label={t('financial_reports.debt_to_equity')} value={de} thresholds={[
              { min: -Infinity, color: 'green', label: t('financial_reports.conservative') }, { min: 0.5, color: 'blue', label: t('financial_reports.moderate') },
              { min: 1.0, color: 'orange', label: t('financial_reports.leveraged') }, { min: 2.0, color: 'red', label: t('financial_reports.high') },
            ]} />
            <RatioRow
              label={t('financial_reports.interest_coverage')}
              value={interestCoverage != null ? interestCoverage : null}
              suffix="x"
              note={interestCoverage == null ? t('financial_reports.no_debt_no_concern') : undefined}
              thresholds={interestCoverage != null ? [
                { min: -Infinity, color: 'red', label: t('financial_reports.danger') }, { min: 2, color: 'orange', label: t('financial_reports.tight') },
                { min: 5, color: 'blue', label: t('financial_reports.comfortable') }, { min: 10, color: 'green', label: t('financial_reports.strong') },
              ] : []}
            />
          </Card>
        </Col>

        <Col xs={24} md={12}>
          <Card size="small" title={t('financial_reports.liquidity')} style={{ marginBottom: 12 }}>
            <RatioRow
              label={t('financial_reports.cash_runway')}
              value={cashRunway === null ? null : cashRunway}
              suffix={` ${t('financial_reports.rounds')}`}
              note={cashRunway === null ? t('financial_reports.profitable_no_burn') : undefined}
              thresholds={cashRunway != null ? [
                { min: -Infinity, color: 'red', label: t('financial_reports.critical') }, { min: 2, color: 'orange', label: t('financial_reports.tight') },
                { min: 4, color: 'blue', label: t('financial_reports.ok') }, { min: 8, color: 'green', label: t('financial_reports.strong') },
              ] : []}
            />
            <RatioRow label={t('financial_reports.cash_pct_revenue')} value={cashRevPct} suffix="%" note={cashRevPct > 200 ? t('financial_reports.consider_investing') : undefined} />
          </Card>

          <Card size="small" title={t('financial_reports.efficiency')} style={{ marginBottom: 12 }}>
            <RatioRow label={t('financial_reports.inventory_turnover')} value={invTurnover != null ? invTurnover : null} suffix="x"
              note={invTurnover == null && totalSold > 0 ? t('financial_reports.all_stock_sold') : t('financial_reports.target_8_12x')}
              thresholds={invTurnover != null ? [
                { min: -Infinity, color: 'red', label: t('financial_reports.low') }, { min: 4, color: 'orange', label: t('financial_reports.below_target') },
                { min: 8, color: 'green', label: t('financial_reports.healthy') }, { min: 12, color: 'blue', label: t('financial_reports.lean') },
              ] : []}
            />
            <RatioRow label={t('financial_reports.rd_pct_revenue')} value={rdPct} suffix="%" thresholds={[
              { min: -Infinity, color: 'orange', label: t('corporate_strategy.none') }, { min: 0.1, color: 'blue', label: t('financial_reports.low') },
              { min: 5, color: 'green', label: t('financial_reports.moderate') }, { min: 15, color: 'green', label: t('financial_reports.heavy') },
            ]} />
            <RatioRow label={t('financial_reports.marketing_pct_rev')} value={mktgPct} suffix="%" />
          </Card>

          <Card size="small" title={t('financial_reports.shareholder_value')} style={{ marginBottom: 12 }}>
            <RatioRow label={t('financial_reports.share_price')} value={c.share_price} suffix="" />
            <RatioRow label={t('financial_reports.shareholder_return')} value={c.shareholder_return_cumulative ? c.shareholder_return_cumulative * 100 : 0} suffix="%" />
          </Card>
        </Col>
      </Row>

      {/* Financial Health Summary */}
      <Card size="small" title={t('financial_reports.financial_health_summary')} style={{ marginTop: 4 }}>
        <Row gutter={16} style={{ marginBottom: 12 }}>
          <Col span={12}>
            <Text style={{ fontSize: 12 }}>{t('financial_reports.credit_rating')}: </Text>
            <Tag color={creditScore >= 8 ? 'green' : creditScore >= 5 ? 'blue' : creditScore >= 3 ? 'orange' : 'red'} style={{ fontSize: 14 }}>
              {creditRating}
            </Tag>
          </Col>
          <Col span={12}>
            <Text style={{ fontSize: 12 }}>{t('financial_reports.distress_risk')}: </Text>
            <Tag color={distressRisk === 'VERY LOW' || distressRisk === 'LOW' ? 'green' : distressRisk === 'MODERATE' ? 'blue' : 'red'}>
              {distressRisk}
            </Tag>
          </Col>
        </Row>
        {warnings.length > 0 && (
          <Alert type="warning" showIcon style={{ marginBottom: 8, fontSize: 11 }}
            message={<ul style={{ margin: 0, paddingLeft: 16 }}>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
          />
        )}
        {strengths.length > 0 && (
          <Alert type="success" showIcon style={{ fontSize: 11 }}
            message={<ul style={{ margin: 0, paddingLeft: 16 }}>{strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>}
          />
        )}
      </Card>
    </div>
  );
};

const ProductsTab = ({ current, rounds, fmt, pct }) => {
  const { t } = useTranslation();
  const products = current?.products || [];
  if (products.length === 0) {
    return <Empty description={t('financial_reports.no_product_data')} />;
  }

  // Total inventory summary
  const totalInvValue = products.reduce((s, p) => s + (p.inventory_value || 0), 0);
  const totalHoldingCost = products.reduce((s, p) => s + (p.inventory_holding_cost || 0), 0);
  const totalUnsold = products.reduce((s, p) => s + (p.units_unsold || 0), 0);

  return (
    <div>
      {/* Company-level inventory summary */}
      <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title={t('financial_reports.total_inventory_value')} value={fmt(totalInvValue)} valueStyle={{ fontSize: 16 }} />
          </Col>
          <Col span={6}>
            <Statistic title={t('financial_reports.holding_cost')} value={fmt(totalHoldingCost)} valueStyle={{ fontSize: 16 }} />
          </Col>
          <Col span={6}>
            <Statistic title={t('financial_reports.total_unsold_units')} value={totalUnsold.toLocaleString()} valueStyle={{ fontSize: 16 }} />
          </Col>
          <Col span={6}>
            <Statistic
              title={t('financial_reports.inventory_pct_assets')}
              value={current.total_assets > 0 ? ((totalInvValue / current.total_assets) * 100).toFixed(1) : '0'}
              suffix="%"
              valueStyle={{ fontSize: 16 }}
            />
          </Col>
        </Row>
      </Card>

      {/* Per-product cards */}
      {products.map((p, i) => {
        const unsoldPct = p.units_produced > 0 ? (p.units_unsold / p.units_produced * 100) : 0;
        const unsoldTag = unsoldPct > 15 ? 'error' : unsoldPct > 5 ? 'warning' : 'success';
        const soldOut = p.units_unsold === 0 && p.units_sold > 0;

        // Historical trend for this product across rounds
        const trend = rounds.map(r => {
          const rp = (r.products || []).find(
            x => x.product_name === p.product_name && x.market_code === p.market_code
          );
          return rp ? {
            round: r.round_number,
            produced: rp.units_produced,
            sold: rp.units_sold,
            unsold: rp.units_unsold,
            turnover: rp.inventory_turnover,
          } : null;
        }).filter(Boolean);

        return (
          <Card
            key={i}
            size="small"
            title={<span>{p.product_name} <Tag>{p.positioning}</Tag> <Text type="secondary">— {p.market_name}</Text></span>}
            style={{ marginBottom: 12 }}
          >
            <Row gutter={16}>
              <Col span={8}>
                <Text strong style={{ fontSize: 12 }}>{t('financial_reports.production_sales')}</Text>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  <div>{t('financial_reports.produced')}: {p.units_produced?.toLocaleString()}</div>
                  <div>{t('financial_reports.sold')}: {Math.round(p.units_sold)?.toLocaleString()}</div>
                  <div>
                    {t('financial_reports.unsold')}: {Math.round(p.units_unsold)?.toLocaleString()}
                    {p.units_unsold > 0 && (
                      <Tag color={unsoldTag} style={{ marginLeft: 4, fontSize: 10 }}>
                        {unsoldPct.toFixed(1)}% {t('financial_reports.unsold').toLowerCase()}
                      </Tag>
                    )}
                    {soldOut && <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>{t('financial_reports.all_sold')}</Tag>}
                  </div>
                </div>
              </Col>
              <Col span={8}>
                <Text strong style={{ fontSize: 12 }}>{t('financial_reports.revenue_margin')}</Text>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  <div>{t('financial_reports.price')}: {fmt(p.retail_price)}</div>
                  <div>{t('financial_reports.revenue')}: {fmt(p.revenue)}</div>
                  <div>{t('financial_reports.unit_cogs')}: {fmt(p.unit_cost)}</div>
                  <div>{t('financial_reports.total_cogs')}: {fmt(p.total_cogs)}</div>
                  <div>{t('financial_reports.gross_margin')}: {fmt(p.gross_margin)} ({(p.gross_margin_pct * 100).toFixed(1)}%)</div>
                </div>
              </Col>
              <Col span={8}>
                <Text strong style={{ fontSize: 12 }}>{t('financial_reports.inventory')}</Text>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  <div>{t('financial_reports.inventory_value')}: {fmt(p.inventory_value)}</div>
                  <div>{t('financial_reports.holding_cost')}: {fmt(p.inventory_holding_cost)}</div>
                  <div>
                    {t('financial_reports.turnover')}: {p.inventory_turnover != null ? `${p.inventory_turnover}x` : 'N/A'}
                    {p.inventory_turnover != null && (
                      <Text type={p.inventory_turnover >= 8 ? 'success' : p.inventory_turnover >= 4 ? 'warning' : 'danger'}
                        style={{ marginLeft: 4, fontSize: 10 }}>
                        {p.inventory_turnover >= 8 ? t('financial_reports.healthy') : p.inventory_turnover >= 4 ? t('financial_reports.moderate') : t('financial_reports.low')}
                      </Text>
                    )}
                  </div>
                </div>
              </Col>
            </Row>

            {/* Trend table */}
            {trend.length > 1 && (
              <Table
                size="small"
                style={{ marginTop: 8 }}
                pagination={false}
                dataSource={trend.map(t => ({ ...t, key: t.round }))}
                columns={[
                  { title: t('common.round'), dataIndex: 'round', key: 'r', width: 60, render: v => `R${v}` },
                  { title: t('financial_reports.produced'), dataIndex: 'produced', key: 'p', render: v => v?.toLocaleString() },
                  { title: t('financial_reports.sold'), dataIndex: 'sold', key: 's', render: v => Math.round(v)?.toLocaleString() },
                  { title: t('financial_reports.unsold'), dataIndex: 'unsold', key: 'u', render: v => Math.round(v)?.toLocaleString() },
                  { title: t('financial_reports.turnover'), dataIndex: 'turnover', key: 't', render: v => v != null ? `${v}x` : '—' },
                ]}
              />
            )}

            {/* Advice */}
            {p.units_unsold > 0 && unsoldPct > 10 && (
              <Alert
                type="warning" showIcon
                style={{ marginTop: 8, fontSize: 11 }}
                message={t('financial_reports.unsold_advice', { count: Math.round(p.units_unsold).toLocaleString() })}
              />
            )}
            {soldOut && (
              <Alert
                type="info" showIcon
                style={{ marginTop: 8, fontSize: 11 }}
                message={t('financial_reports.all_sold_advice')}
              />
            )}
          </Card>
        );
      })}
    </div>
  );
};

const InvestorRelationsTab = ({ gameId, teamId, round }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [activeFund, setActiveFund] = useState(null);

  useEffect(() => {
    if (gameId && teamId && round != null) {
      getInvestorRelations(gameId, teamId, { round }).then(r => setData(r.data)).catch(() => {});
    }
  }, [gameId, teamId, round]);

  if (!data) return <div style={{ padding: 24, textAlign: 'center' }}><Text type="secondary">{t('financial_reports.loading_investor_data')}</Text></div>;

  // Build a lookup from fund_code to full fund profile (with alignment)
  const fundProfileMap = {};
  (data.fund_profiles || []).forEach(fp => { fundProfileMap[fp.code] = fp; });

  const arrow = data.price_change >= 0 ? '\u25B2' : '\u25BC';
  const arrowColor = data.price_change >= 0 ? '#52c41a' : '#ff4d4f';
  const sentColor = data.sentiment_direction === 'buying' ? '#52c41a' : data.sentiment_direction === 'selling' ? '#ff4d4f' : '#faad14';

  const actionIcon = (action) => {
    if (action === 'buy') return <span style={{ color: '#52c41a' }}>{'\u25B2'} {t('financial_reports.action_buy')}</span>;
    if (action === 'sell') return <span style={{ color: '#ff4d4f' }}>{'\u25BC'} {t('financial_reports.action_sell')}</span>;
    return <span style={{ color: '#faad14' }}>{'\u2014'} {t('financial_reports.action_hold')}</span>;
  };

  const ratingColor = (r) => r === 'OVERWEIGHT' ? '#52c41a' : r === 'UNDERWEIGHT' ? '#ff4d4f' : '#faad14';

  const FUND_COLORS = { velocity: '#3B82F6', granite: '#8B5CF6', greenhorizon: '#10B981', market: '#CBD5E1' };

  return (
    <div>
      {/* Share Price Header */}
      <div style={{ display: 'flex', gap: 32, alignItems: 'baseline', marginBottom: 24, padding: '16px 0', borderBottom: '1px solid #f0f0f0' }}>
        <div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{t("financial_reports.share_price").toUpperCase()}</Text>
          <span style={{ fontSize: 32, fontWeight: 700 }}>${data.share_price.toFixed(2)}</span>
          <span style={{ color: arrowColor, fontSize: 16, marginLeft: 8, fontWeight: 600 }}>
            {arrow} {data.price_change >= 0 ? '+' : ''}{data.price_change_pct.toFixed(1)}%
          </span>
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{t("financial_reports.shares_outstanding")}</Text>
          <Text strong>{data.shares_outstanding.toLocaleString()}</Text>
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{t("financial_reports.market_cap")}</Text>
          <Text strong>${(data.market_cap / 1e6).toFixed(1)}M</Text>
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{t("financial_reports.book_value")}</Text>
          <Text strong>${data.book_value.toFixed(2)}</Text>
        </div>
        <div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{t("financial_reports.sentiment")}</Text>
          <Text strong style={{ color: sentColor }}>{data.sentiment_multiplier.toFixed(2)}x ({data.sentiment_label})</Text>
        </div>
      </div>

      {/* Shareholders Table */}
      <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t("financial_reports.your_shareholders").toUpperCase()}</Text>
      <table className="ds-data-table" style={{ width: '100%', marginBottom: 24 }}>
        <thead>
          <tr>
            <th>{t("financial_reports.investor")}</th>
            <th>{t("financial_reports.shares")}</th>
            <th>{t("financial_reports.holding")}</th>
            <th>{t("financial_reports.change")}</th>
            <th>{t("financial_reports.sentiment")}</th>
          </tr>
        </thead>
        <tbody>
          {data.shareholders.map(s => (
            <tr key={s.fund_code}>
              <td>
                <InvestorNameLink fund={fundProfileMap[s.fund_code] || s} activeFund={activeFund} setActiveFund={setActiveFund}>
                  <Text strong style={{ fontSize: 12 }}>{s.fund_name}</Text>
                </InvestorNameLink>
                <Text type="secondary" style={{ fontSize: 10, display: 'block' }}>({s.philosophy.charAt(0).toUpperCase() + s.philosophy.slice(1)} Fund)</Text>
              </td>
              <td>{s.shares_held.toLocaleString()}</td>
              <td>{s.holding_pct.toFixed(1)}%</td>
              <td>
                {s.share_change > 0 ? <span style={{ color: '#52c41a' }}>{'\u25B2'} +{s.share_change.toLocaleString()}</span> :
                 s.share_change < 0 ? <span style={{ color: '#ff4d4f' }}>{'\u25BC'} {s.share_change.toLocaleString()}</span> :
                 <span style={{ color: '#999' }}>{'\u2014'} 0</span>}
              </td>
              <td>{actionIcon(s.action)}</td>
            </tr>
          ))}
          <tr style={{ background: '#fafafa' }}>
            <td><Text type="secondary">{t('financial_reports.market_passive_label')}</Text></td>
            <td>{data.market_passive.shares.toLocaleString()}</td>
            <td>{data.market_passive.holding_pct.toFixed(1)}%</td>
            <td><span style={{ color: '#999' }}>{'\u2014'}</span></td>
            <td><span style={{ color: '#999' }}>{'\u2014'}</span></td>
          </tr>
        </tbody>
      </table>

      {/* What Investors Are Saying */}
      <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t("financial_reports.what_investors_saying").toUpperCase()}</Text>
      <div style={{ marginBottom: 24 }}>
        {data.shareholders.map(s => (
          <div key={s.fund_code} style={{ padding: '12px 16px', background: '#fafafa', borderRadius: 6, marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <InvestorNameLink fund={fundProfileMap[s.fund_code] || s} activeFund={activeFund} setActiveFund={setActiveFund}>
                <Text strong style={{ fontSize: 12 }}>{s.fund_name}</Text>
              </InvestorNameLink>
              <Tag color={ratingColor(s.rating)} style={{ fontSize: 10 }}>{s.rating}</Tag>
            </div>
            <Text style={{ fontSize: 12, fontStyle: 'italic' }}>"{s.trade_reason}"</Text>
          </div>
        ))}
      </div>

      {/* Charts */}
      <Row gutter={24}>
        <Col xs={24} md={12}>
          <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t("financial_reports.share_price_history").toUpperCase()}</Text>
          {data.price_trend && data.price_trend.length > 0 ? (
            <div style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data.price_trend}>
                  <XAxis dataKey="round" tick={{ fontSize: 10 }} label={{ value: t('common.round'), fontSize: 10, position: 'bottom' }} />
                  <YAxis tick={{ fontSize: 10 }} width={50} tickFormatter={v => `$${v}`} />
                  <Tooltip formatter={(v, name) => [`$${Number(v).toFixed(2)}`, name === 'price' ? t('financial_reports.share_price') : t('financial_reports.book_value')]} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Line type="monotone" dataKey="price" stroke="#3B82F6" strokeWidth={2} name={t('financial_reports.share_price')} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="book_value" stroke="#94A3B8" strokeWidth={1} strokeDasharray="4 4" name={t('financial_reports.book_value')} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <Text type="secondary">{t('financial_reports.no_price_history')}</Text>}
        </Col>
        <Col xs={24} md={12}>
          <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t("financial_reports.investor_holding_trend").toUpperCase()}</Text>
          {data.holding_trend && data.holding_trend.length > 0 ? (
            <div style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={data.holding_trend}>
                  <XAxis dataKey="round" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} width={40} tickFormatter={v => `${v}%`} />
                  <Tooltip formatter={v => `${Number(v).toFixed(1)}%`} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Area type="monotone" dataKey="velocity" stackId="1" fill={FUND_COLORS.velocity} stroke={FUND_COLORS.velocity} name="Velocity Capital" />
                  <Area type="monotone" dataKey="granite" stackId="1" fill={FUND_COLORS.granite} stroke={FUND_COLORS.granite} name="Granite Investments" />
                  <Area type="monotone" dataKey="greenhorizon" stackId="1" fill={FUND_COLORS.greenhorizon} stroke={FUND_COLORS.greenhorizon} name="GreenHorizon Partners" />
                  <Area type="monotone" dataKey="market" stackId="1" fill={FUND_COLORS.market} stroke={FUND_COLORS.market} name={t('financial_reports.market_passive_label')} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : <Text type="secondary">{t('financial_reports.no_holding_data')}</Text>}
        </Col>
      </Row>

      {/* CC-31G: Investor Profile Popover */}
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

// ── Government Relations Tab ──────────────────────────────────────

const STATUS_COLOR = {
  WELCOMED: '#52c41a', NEUTRAL: '#1677ff', MONITORED: '#faad14',
  WARNING: '#fa8c16', RESTRICTED: '#ff4d4f',
};
const STATUS_BG = {
  WELCOMED: '#f6ffed', NEUTRAL: '#e6f4ff', MONITORED: '#fffbe6',
  WARNING: '#fff7e6', RESTRICTED: '#fff2f0',
};

const GovernmentRelationsTab = ({ gameId, teamId }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (gameId && teamId) {
      getGovernmentRelations(gameId, teamId).then(r => setData(r.data)).catch(() => {});
    }
  }, [gameId, teamId]);

  if (!data) return <div style={{ padding: 24, textAlign: 'center' }}><Text type="secondary">{t('financial_reports.loading_gov_data')}</Text></div>;

  // Sort home market first
  const govs = [...(data.government_relations || [])].sort((a, b) => (b.is_home_market ? 1 : 0) - (a.is_home_market ? 1 : 0));
  if (govs.length === 0) return <Empty description={t('financial_reports.no_gov_data')} />;

  const fmt = (v) => {
    if (v == null) return '$0';
    const abs = Math.abs(v);
    if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
    return `$${v.toFixed(0)}`;
  };

  const actionLabel = (type) => {
    const labels = {
      INCENTIVE_GRANT: t('financial_reports.action_incentive'), PROCUREMENT_AWARD: t('financial_reports.action_contract'),
      TARIFF_ADJUSTMENT: t('financial_reports.action_tariff_change'), REGULATORY_TIGHTENING: t('financial_reports.action_regulation_tightened'),
      REGULATORY_RELAXATION: t('financial_reports.action_regulation_relaxed'), BILATERAL_SHIFT: t('financial_reports.action_policy_shift'),
      WARNING_ISSUED: t('financial_reports.action_warning'), ACCESS_RESTRICTION: t('financial_reports.action_restricted'), ACCESS_RESTORED: t('financial_reports.action_restored'),
    };
    return labels[type] || type;
  };
  const actionColor = (type) => {
    if (['INCENTIVE_GRANT', 'PROCUREMENT_AWARD', 'REGULATORY_RELAXATION', 'ACCESS_RESTORED'].includes(type)) return 'green';
    if (['WARNING_ISSUED', 'TARIFF_ADJUSTMENT', 'REGULATORY_TIGHTENING'].includes(type)) return 'orange';
    if (['ACCESS_RESTRICTION'].includes(type)) return 'red';
    return 'blue';
  };

  return (
    <div>
      {/* Cross-market summary cards */}
      <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t("financial_reports.government_status_overview").toUpperCase()}</Text>
      <Row gutter={[12, 12]} style={{ marginBottom: 24 }}>
        {govs.map(g => (
          <Col xs={12} sm={8} md={6} key={g.market_code}>
            <Card size="small" style={{ background: STATUS_BG[g.status] || '#fafafa', borderColor: STATUS_COLOR[g.status] || '#d9d9d9' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <span>
                  <Text strong style={{ fontSize: 12 }}>{g.market_code}</Text>
                  {g.is_home_market && <Tag color="blue" style={{ fontSize: 9, marginLeft: 4, padding: '0 4px' }}>{t('financial_reports.home_tag')}</Tag>}
                </span>
                <Tag color={STATUS_COLOR[g.status]} style={{ fontSize: 10, margin: 0 }}>{g.status}</Tag>
              </div>
              <Text type="secondary" style={{ fontSize: 10, display: 'block' }}>{g.government_name}</Text>
              {g.satisfaction != null && (
                <Progress
                  percent={Math.round(g.satisfaction * 100)}
                  size="small"
                  strokeColor={STATUS_COLOR[g.status]}
                  style={{ marginTop: 4 }}
                />
              )}
            </Card>
          </Col>
        ))}
      </Row>

      {/* Satisfaction trend chart */}
      {govs.some(g => g.recent_actions?.length > 0) && (
        <>
          <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t("financial_reports.satisfaction_levels").toUpperCase()}</Text>
          <div style={{ height: 200, marginBottom: 24 }}>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={govs.filter(g => g.satisfaction != null).map(g => ({ ...g, satisfaction_pct: Math.round(g.satisfaction * 100) }))} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} tickFormatter={v => `${v}%`} />
                <YAxis type="category" dataKey="market_code" tick={{ fontSize: 10 }} width={40} />
                <Tooltip formatter={v => `${Number(v).toFixed(0)}%`} />
                <Bar dataKey="satisfaction_pct" fill="#1677ff" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {/* Per-market detail cards */}
      <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t("financial_reports.market_details").toUpperCase()}</Text>
      {govs.map(g => (
        <Card
          key={g.market_code}
          size="small"
          style={{ marginBottom: 16, borderLeft: `4px solid ${STATUS_COLOR[g.status] || '#d9d9d9'}` }}
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>
                {g.government_name} — {g.market_name}
                {g.is_home_market && <Tag color="blue" style={{ marginLeft: 8, fontSize: 10 }}>{t('financial_reports.home_market_tag')}</Tag>}
              </span>
              <Tag color={STATUS_COLOR[g.status]}>{g.status}</Tag>
            </div>
          }
        >
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>{g.description}</Text>

          {/* Satisfaction & Policy Priorities */}
          <Row gutter={24}>
            <Col xs={24} md={12}>
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>{t('financial_reports.satisfaction').toUpperCase()}</Text>
              {g.satisfaction != null ? (
                <div style={{ marginBottom: 12 }}>
                  <Progress
                    percent={Math.round(g.satisfaction * 100)}
                    strokeColor={STATUS_COLOR[g.status]}
                    format={pct => `${(g.satisfaction * 100).toFixed(0)}%`}
                  />
                </div>
              ) : <Text type="secondary">{t('financial_reports.no_data_yet')}</Text>}

              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>{t('financial_reports.policy_priorities').toUpperCase()}</Text>
              {(g.policy_priorities || []).map((p, i) => {
                const myScore = g.objective_scores?.[p.objective];
                return (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #f5f5f5' }}>
                    <div style={{ flex: 1 }}>
                      <Text style={{ fontSize: 12 }}>{p.objective?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</Text>
                      <Text type="secondary" style={{ fontSize: 10, marginLeft: 8 }}>({(p.weight * 100).toFixed(0)}%)</Text>
                    </div>
                    <div style={{ width: 100 }}>
                      {myScore != null ? (
                        <Progress
                          percent={Math.round(myScore * 100)}
                          size="small"
                          strokeColor={myScore >= 0.7 ? '#52c41a' : myScore >= 0.4 ? '#faad14' : '#ff4d4f'}
                        />
                      ) : <Text type="secondary" style={{ fontSize: 10 }}>—</Text>}
                    </div>
                  </div>
                );
              })}
            </Col>

            <Col xs={24} md={12}>
              {/* Active Incentives */}
              {g.active_incentive && (
                <div style={{ marginBottom: 12 }}>
                  <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>{t('financial_reports.active_incentive').toUpperCase()}</Text>
                  <Card size="small" style={{ background: '#f6ffed', borderColor: '#b7eb8f' }}>
                    <Text style={{ fontSize: 12 }}>
                      {g.active_incentive.type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    </Text>
                    {g.active_incentive.value && (
                      <Text strong style={{ fontSize: 12, display: 'block' }}>{t('financial_reports.value_label')}: {fmt(g.active_incentive.value)}</Text>
                    )}
                    {g.active_incentive.rounds_remaining != null && (
                      <Text type="secondary" style={{ fontSize: 10 }}>{g.active_incentive.rounds_remaining} {t('financial_reports.rounds_remaining')}</Text>
                    )}
                  </Card>
                </div>
              )}

              {/* Active Restrictions */}
              {g.active_restriction && (
                <div style={{ marginBottom: 12 }}>
                  <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>{t('financial_reports.active_restriction').toUpperCase()}</Text>
                  <Card size="small" style={{ background: '#fff2f0', borderColor: '#ffccc7' }}>
                    <Text style={{ fontSize: 12 }}>{g.active_restriction.type?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</Text>
                    {g.active_restriction.reason && (
                      <Text type="secondary" style={{ fontSize: 10, display: 'block' }}>{g.active_restriction.reason}</Text>
                    )}
                  </Card>
                </div>
              )}

              {/* Procurement History */}
              {g.procurement_history?.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>{t('financial_reports.procurement_contracts').toUpperCase()}</Text>
                  {g.procurement_history.map((p, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f5f5f5' }}>
                      <Text style={{ fontSize: 12 }}>{t('common.round')} {p.round}</Text>
                      <Text strong style={{ fontSize: 12 }}>{fmt(p.parameters?.value)}</Text>
                    </div>
                  ))}
                </div>
              )}

              {/* Recent Actions / Warnings */}
              {g.recent_actions?.length > 0 && (
                <div>
                  <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>{t('financial_reports.recent_actions').toUpperCase()}</Text>
                  {g.recent_actions.map((a, i) => (
                    <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #f5f5f5' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Tag color={actionColor(a.action_type)} style={{ fontSize: 10 }}>{actionLabel(a.action_type)}</Tag>
                        {a.round != null && <Text type="secondary" style={{ fontSize: 10 }}>R{a.round}</Text>}
                      </div>
                      {a.narrative && <Text style={{ fontSize: 11, display: 'block', marginTop: 2 }}>{a.narrative}</Text>}
                    </div>
                  ))}
                </div>
              )}

              {!g.active_incentive && !g.active_restriction && !g.procurement_history?.length && !g.recent_actions?.length && (
                <Text type="secondary" style={{ fontSize: 12 }}>{t('financial_reports.no_gov_actions')}</Text>
              )}
            </Col>
          </Row>
        </Card>
      ))}
    </div>
  );
};

// Trade Finance & FX tab — the financial view of SC trade-finance decisions:
// the FX hedge lifecycle (open -> mark-to-market -> settle -> realized P&L) plus
// a summary of payment instruments and export-credit (Sinosure) coverage.
// Moved here from the Supply Chain dashboard (P&L belongs with the financials).
const TradeFinanceFXTab = ({ gameId, teamId, round }) => {
  const { t } = useTranslation();
  const [hedges, setHedges] = useState([]);
  const [tf, setTf] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!gameId || !teamId) return;
    let alive = true;
    setLoading(true);
    Promise.all([
      getHedgePositions(gameId, teamId).then(r => r.data).catch(() => []),
      round ? getTradeFinance(gameId, teamId, round).then(r => r.data).catch(() => ({})) : Promise.resolve({}),
    ]).then(([h, d]) => { if (alive) { setHedges(h || []); setTf(d || {}); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [gameId, teamId, round]);

  if (loading) return <LoadingSpinner />;
  const money = (n) => (n == null ? '—' : `$${Math.round(Number(n)).toLocaleString()}`);
  const signed = (n) => (
    <Text type={Number(n) > 0 ? 'success' : Number(n) < 0 ? 'danger' : undefined}>
      {Number(n) >= 0 ? '+' : ''}{Math.round(Number(n)).toLocaleString()}
    </Text>
  );
  const tfRows = tf.trade_finance || [];
  const sinosure = tf.sinosure || [];
  const instruments = [...new Set(tfRows.map(r => r.buyer_payment_instrument).filter(Boolean))];

  return (
    <div>
      <Title level={5} style={{ marginTop: 0 }}>Open FX hedge positions</Title>
      <Text type="secondary" style={{ fontSize: 12 }}>
        Hedges open against your foreign receivables at round-advance, mark to market each round, and settle
        at maturity — realized P&amp;L flows into net income. A short receivables hedge gains when the foreign
        currency weakens.
      </Text>
      {hedges.length === 0
        ? <Empty style={{ margin: '12px 0' }} description="No FX hedge positions yet — set a hedge ratio on the Trade Finance page and advance a round." />
        : (
          <Table rowKey="id" size="small" pagination={false} scroll={{ x: true }} style={{ marginTop: 8 }}
            dataSource={hedges}
            columns={[
              { title: 'Pair', dataIndex: 'currency_pair', render: (v) => <Text strong>{v}</Text> },
              { title: 'Notional', dataIndex: 'notional', render: money },
              { title: 'Locked rate', dataIndex: 'locked_rate', render: (v) => Number(v).toFixed(4) },
              { title: 'Mark-to-market', dataIndex: 'mtm_current', render: signed },
              { title: 'Realized P&L', dataIndex: 'realized_pnl', render: (v) => (v == null ? <Text type="secondary">—</Text> : signed(v)) },
              { title: 'Status', dataIndex: 'status', render: (v) => <Tag color={v === 'open' ? 'blue' : v === 'matured' ? 'green' : 'default'}>{v}</Tag> },
            ]} />
        )}

      <Title level={5} style={{ marginTop: 20 }}>Payment & export-credit posture</Title>
      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Card size="small" title="Buyer payment instruments">
            {instruments.length ? <Space wrap>{instruments.map(i => <Tag key={i}>{i.replace(/_/g, ' ')}</Tag>)}</Space>
              : <Text type="secondary">None set.</Text>}
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card size="small" title="Export-credit (Sinosure) coverage">
            {sinosure.length
              ? <Space direction="vertical" size={0}>{sinosure.map((s, i) => (
                  <Text key={i}>Market {s.market}: {s.coverage_pct}%</Text>))}</Space>
              : <Text type="secondary">No export-credit insurance set.</Text>}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

const FinancialReportsPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId } = useGame();
  const [data, setData] = useState(null);
  const [selectedRound, setSelectedRound] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const res = await getFinancialHistory(gameId, teamId);
      setData(res.data);
      const rounds = res.data?.rounds || [];
      if (rounds.length > 0) {
        setSelectedRound(rounds[rounds.length - 1].round_number);
      }
    } catch { setData(null); }
    finally { setLoading(false); }
  }, [gameId, teamId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <LoadingSpinner message={t("common.loading")} />;

  const rounds = data?.rounds || [];
  if (rounds.length === 0) {
    return (
      <div style={{ maxWidth: 1100, margin: '0 auto', width: '100%' }}>
        <PageHeader title={t("financial_reports.title")} subtitle={t("financial_reports.no_data")} />
        <Empty description={t("financial_reports.no_data_detail")} />
      </div>
    );
  }

  const roundOptions = rounds.map(r => ({ value: r.round_number, label: `${t('common.round')} ${r.round_number}` }));
  const current = rounds.find(r => r.round_number === selectedRound) || rounds[rounds.length - 1];

  // Income statement table
  const incomeData = rounds.map(r => ({
    key: r.round_number,
    round: `R${r.round_number}`,
    revenue: r.total_revenue,
    cogs: r.total_cogs,
    gross_profit: r.gross_profit,
    rd: r.rd_expense,
    marketing: r.marketing_expense,
    strategy: r.strategy_expense,
    admin: r.admin_overhead,
    net_income: r.net_income,
    margin: r.net_margin_pct,
  }));

  const incomeColumns = [
    { title: t('common.round'), dataIndex: 'round', key: 'round', width: 70 },
    { title: t('financial_reports.revenue'), dataIndex: 'revenue', key: 'revenue', render: fmt },
    { title: t('financial_reports.cogs'), dataIndex: 'cogs', key: 'cogs', render: fmt },
    { title: t('financial_reports.gross_profit'), dataIndex: 'gross_profit', key: 'gp', render: fmt },
    { title: t('financial_reports.rd_label'), dataIndex: 'rd', key: 'rd', render: fmt },
    { title: t('financial_reports.marketing_label'), dataIndex: 'marketing', key: 'mktg', render: fmt },
    { title: t('financial_reports.strategy_label'), dataIndex: 'strategy', key: 'strat', render: fmt },
    { title: t('financial_reports.admin'), dataIndex: 'admin', key: 'admin', render: fmt },
    { title: t('financial_reports.net_income'), dataIndex: 'net_income', key: 'ni', render: fmt },
    { title: t('financial_reports.margin'), dataIndex: 'margin', key: 'margin', render: pct },
  ];

  // Balance sheet table
  const balanceData = rounds.map(r => ({
    key: r.round_number,
    round: `R${r.round_number}`,
    cash: r.cash_closing,
    plant: r.plant_book_value,
    inventory: r.inventory_value,
    total_assets: r.total_assets,
    total_debt: r.total_debt,
    total_equity: r.total_equity,
    de_ratio: r.debt_to_equity,
  }));

  const balanceColumns = [
    { title: t('common.round'), dataIndex: 'round', key: 'round', width: 70 },
    { title: t('financial_reports.cash'), dataIndex: 'cash', key: 'cash', render: fmt },
    { title: t('financial_reports.plant_value'), dataIndex: 'plant', key: 'plant', render: fmt },
    { title: t('financial_reports.inventory'), dataIndex: 'inventory', key: 'inv', render: fmt },
    { title: t('financial_reports.total_assets'), dataIndex: 'total_assets', key: 'assets', render: fmt },
    { title: t('financial_reports.total_debt'), dataIndex: 'total_debt', key: 'debt', render: fmt },
    { title: t('financial_reports.total_equity'), dataIndex: 'total_equity', key: 'equity', render: fmt },
    { title: t('financial_reports.de_ratio'), dataIndex: 'de_ratio', key: 'de', render: v => v?.toFixed(2) || '—' },
  ];

  // Cash flow table
  const cashFlowData = rounds.map(r => ({
    key: r.round_number,
    round: `R${r.round_number}`,
    operating: r.operating_cash_flow,
    investing: r.investing_cash_flow,
    financing: r.financing_cash_flow,
    dividends: r.dividends_paid,
    opening: r.cash_opening,
    closing: r.cash_closing,
  }));

  const cashFlowColumns = [
    { title: t('common.round'), dataIndex: 'round', key: 'round', width: 70 },
    { title: t('financial_reports.operating_cf'), dataIndex: 'operating', key: 'op', render: fmt },
    { title: t('financial_reports.investing_cf'), dataIndex: 'investing', key: 'inv', render: fmt },
    { title: t('financial_reports.financing_cf'), dataIndex: 'financing', key: 'fin', render: fmt },
    { title: t('financial_reports.dividends'), dataIndex: 'dividends', key: 'div', render: fmt },
    { title: t('financial_reports.cash_opening'), dataIndex: 'opening', key: 'open', render: fmt },
    { title: t('financial_reports.cash_closing'), dataIndex: 'closing', key: 'close', render: fmt },
  ];

  // Revenue chart data
  const chartData = rounds.map(r => ({
    round: `R${r.round_number}`,
    Revenue: r.total_revenue,
    'Net Income': r.net_income,
    COGS: r.total_cogs,
  }));

  const grossMarginPct = current.gross_margin_pct ? current.gross_margin_pct * 100 : 0;
  const netMarginPct = current.net_margin_pct ? current.net_margin_pct * 100 : 0;

  const tabItems = [
    {
      key: 'income',
      label: t('financial_reports.income_statement'),
      children: (
        <Table dataSource={incomeData} columns={incomeColumns} pagination={false} size="small" scroll={{ x: 900 }} />
      ),
    },
    {
      key: 'balance',
      label: t('financial_reports.balance_sheet'),
      children: (
        <Table dataSource={balanceData} columns={balanceColumns} pagination={false} size="small" scroll={{ x: 800 }} />
      ),
    },
    {
      key: 'cashflow',
      label: t('financial_reports.cash_flow'),
      children: (
        <Table dataSource={cashFlowData} columns={cashFlowColumns} pagination={false} size="small" scroll={{ x: 700 }} />
      ),
    },
    {
      key: 'ratios',
      label: t('financial_reports.ratios'),
      children: <RatiosTab current={current} fmt={fmt} pct={pct} />,
    },
    {
      key: 'products',
      label: t('financial_reports.products'),
      children: <ProductsTab current={current} rounds={rounds} fmt={fmt} pct={pct} />,
    },
    {
      key: 'trade_finance',
      label: 'Trade Finance & FX',
      children: <TradeFinanceFXTab gameId={gameId} teamId={teamId} round={selectedRound} />,
    },
    {
      key: 'investors',
      label: t('financial_reports.investor_relations'),
      children: <InvestorRelationsTab gameId={gameId} teamId={teamId} round={selectedRound} />,
    },
    {
      key: 'government',
      label: t('financial_reports.government_relations'),
      children: <GovernmentRelationsTab gameId={gameId} teamId={teamId} />,
    },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      <PageHeader
        title={t("financial_reports.title")}
        subtitle={`${t("common.round")} ${selectedRound} · ${t("financial_reports.subtitle")}`}
        actions={<Select value={selectedRound} onChange={setSelectedRound} options={roundOptions} style={{ width: 140 }} />}
      />

      {/* Summary Cards */}
      <MetricRow metrics={[
        { label: `${t('financial_reports.revenue')} (R${selectedRound})`, value: fmt(current.total_revenue) },
        { label: `${t('financial_reports.cogs')} (R${selectedRound})`, value: fmt(current.total_cogs) },
        { label: t('financial_reports.operating_income'), value: fmt(current.operating_income) },
        { label: `${t('financial_reports.net_income')} (R${selectedRound})`, value: fmt(current.net_income), status: current.net_income >= 0 ? 'success' : 'danger' },
      ]} />

      {/* Tabs */}
      <PanelCard headerColor="financial" title={t("financial_reports.financial_statements").toUpperCase()}>
        <Tabs className="ds-colored-tabs" items={tabItems} />
      </PanelCard>

      {/* Revenue Trend Chart */}
      {rounds.length > 1 && (
        <PanelCard headerColor="financial" title={t("financial_reports.revenue_trend").toUpperCase()}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="round" />
              <YAxis tickFormatter={v => fmt(v)} />
              <Tooltip formatter={v => fmt(v)} />
              <Legend />
              <Bar dataKey="Revenue" fill="#1677ff" />
              <Bar dataKey="Net Income" fill="#52c41a" />
            </BarChart>
          </ResponsiveContainer>
        </PanelCard>
      )}

      {/* Revenue by Market */}
      {current.markets?.length > 0 && (
        <PanelCard headerColor="market" title={t('financial_reports.revenue_by_market').toUpperCase()}>
          <Row gutter={[16, 16]}>
            {current.markets.map(m => (
              <Col xs={24} md={6} key={m.market_code}>
                <Card size="small" title={m.market_name}>
                  <div>{t('financial_reports.revenue_home')}: {fmt(m.home_revenue)}</div>
                  <div>{t('financial_reports.profit')}: {fmt(m.market_profit)}</div>
                  <div>{t('financial_reports.market_share_label')}: {pct(m.market_share_pct)}</div>
                  {m.currency_code && m.currency_code !== 'USD' && (
                    <div style={{ marginTop: 8, padding: '6px 8px', background: '#f8fafc', borderRadius: 4, fontSize: 11 }}>
                      <div>
                        <Text type="secondary">{t('financial_reports.currency')}: </Text>
                        <Text>{m.currency_code} (1 {m.currency_code} = ${m.exchange_rate?.toFixed(4)} USD)</Text>
                      </div>
                      {m.exchange_rate_change_pct !== 0 && (
                        <div>
                          <Text type="secondary">{t('financial_reports.fx_change')}: </Text>
                          <Text style={{ color: m.exchange_rate_change_pct > 0 ? '#3f8600' : '#cf1322' }}>
                            {m.exchange_rate_change_pct > 0 ? '+' : ''}{(m.exchange_rate_change_pct * 100).toFixed(1)}%
                          </Text>
                        </div>
                      )}
                      {m.tariff_rate > 0 && (
                        <div>
                          <Text type="secondary">{t('financial_reports.tariff')}: </Text>
                          <Text>{(m.tariff_rate * 100).toFixed(1)}%</Text>
                        </div>
                      )}
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

export default FinancialReportsPage;
