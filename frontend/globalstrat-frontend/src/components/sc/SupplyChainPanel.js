import React, { useState, useEffect, useCallback } from 'react';
import {
  Row, Col, Button, Alert, Tag, Progress, Empty, Typography, Space,
  Statistic, message, Collapse,
} from 'antd';
import { ReloadOutlined, ArrowRightOutlined, WarningOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGame } from '../../contexts/GameContext';
import {
  getSuppliers, getComplianceRegimes, getSourcing, getInventory,
  getResilienceScore, getSCEvents, getComplianceEvents,
} from '../../api/sc';
import LoadingSpinner from '../LoadingSpinner';
import { PanelCard } from '../design-system';
import { StateLegend } from './scState';

const { Text, Paragraph } = Typography;

const pretty = (c) => (c || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

const SEV_COLOR = { critical: 'red', high: 'volcano', medium: 'gold', low: 'blue' };

// Reusable KPI card: always renders (honest empty state) and links to its decision page.
const SCCard = ({ title, color = 'strategic', onEdit, editLabel, empty, emptyText, children }) => (
  <PanelCard headerColor={color} title={title} style={{ marginBottom: 16, height: '100%' }}>
    {empty ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyText} /> : children}
    {onEdit && (
      <Button type="link" style={{ paddingLeft: 0, marginTop: 8 }} onClick={onEdit}>
        {editLabel} <ArrowRightOutlined />
      </Button>
    )}
  </PanelCard>
);

// Supply-chain panel — a focused risk/status view (CC-15 / redesign): how healthy
// am I, what's threatening me now, and where am I exposed. Decision echoes and
// trade-finance P&L live on their own pages, not here.
const SupplyChainPanel = () => {
  const { t } = useTranslation();
  const { gameId, teamId, scenarioId, currentRound } = useGame();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [d, setD] = useState(null);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    const safe = (p) => p.then((r) => r.data).catch(() => null);
    try {
      const [suppliers, regimes, sourcing, inventory, resilience, events, compliance] = await Promise.all([
        safe(getSuppliers(scenarioId)), safe(getComplianceRegimes(scenarioId)),
        safe(getSourcing(gameId, teamId, currentRound)), safe(getInventory(gameId, teamId, currentRound)),
        safe(getResilienceScore(gameId, teamId, currentRound)), safe(getSCEvents(gameId, teamId, currentRound)),
        safe(getComplianceEvents(gameId, teamId)),
      ]);
      setD({ suppliers: suppliers || [], regimes: regimes || [], sourcing: sourcing || {},
        inventory: inventory || {}, resilience: resilience || {}, events: events || [],
        compliance: compliance || [] });
    } catch { message.error(t('sc.dashboard.load_error')); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound, t]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingSpinner />;
  if (!d) return <Alert type="warning" showIcon message={t('sc.dashboard.unavailable')} />;

  const base = `/games/${gameId}/teams/${teamId}`;
  const go = (p) => navigate(`${base}${p}`);
  const money = (n) => `$${Math.round(n).toLocaleString()}`;

  const supplierMap = {};
  d.suppliers.forEach((s) => { supplierMap[s.id] = s; });
  const allocations = d.sourcing.allocations || [];

  // --- Exposure: single-source, geographic concentration, buffer adequacy ---
  const byCat = {};
  allocations.forEach((a) => { (byCat[a.critical_input_category] = byCat[a.critical_input_category] || []).push(a); });
  const singleSourced = Object.entries(byCat)
    .filter(([, allocs]) => allocs.length === 1 || Math.max(...allocs.map((a) => a.allocation_pct || 0)) >= 100)
    .map(([cat]) => cat);

  const byCountry = {}; let totalWeight = 0;
  allocations.forEach((a) => {
    const c = supplierMap[a.supplier]?.country || '??';
    byCountry[c] = (byCountry[c] || 0) + (a.allocation_pct || 0); totalWeight += (a.allocation_pct || 0);
  });
  const geoRows = Object.entries(byCountry)
    .map(([c, w]) => ({ country: c, pct: totalWeight ? Math.round((w / totalWeight) * 100) : 0 }))
    .sort((x, y) => y.pct - x.pct);
  const topCountry = geoRows[0];

  const invRows = d.inventory.inventory || [];
  const bufferAvg = invRows.length
    ? Math.round(invRows.reduce((s, r) => s + (Number(r.buffer_days) || 0), 0) / invRows.length) : null;
  const thinBuffer = bufferAvg != null && bufferAvg < 30;

  const flagged = allocations.map((a) => supplierMap[a.supplier]).filter(Boolean)
    .filter((s) => s.tier_2_3_profile?.risk_flags?.xinjiang_adjacent
      || s.tier_2_3_profile?.risk_flags?.forced_labor_exposure === 'high');
  const flaggedNames = [...new Set(flagged.map((s) => s.name))];

  // --- Resilience + disruption impact ---
  const score = d.resilience?.score;
  const scoreCalculated = score !== null && score !== undefined;
  const impact = d.resilience?.disruption_impact || {};
  const cf = impact.capacity_factor;
  const lostSales = Number(impact.lost_revenue || 0);
  const disruptionCost = Number(impact.disruption_cost || 0);
  const disrupted = (cf !== undefined && cf < 1) || lostSales > 0 || disruptionCost > 0;

  // --- Disruptions & alerts feed (collapsible so it never becomes a long scroll) ---
  const events = d.events || [];
  const compliance = (d.compliance || []).slice().sort((a, b) => (b.round_number || 0) - (a.round_number || 0));
  const activeCompliance = compliance.filter((e) => e.freeze_until_round >= currentRound || e.round_number === currentRound);
  const alertItems = [
    ...events.map((e) => ({
      key: `sc-${e.id}`,
      label: (
        <Space size={6} wrap>
          <Tag color={SEV_COLOR[e.severity] || 'blue'}>{e.severity ? pretty(e.severity) : t('sc.dashboard.disruption')}</Tag>
          <Text strong>{e.event_name || t('sc.dashboard.sc_disruption')}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {e.fired_by_instructor ? t('sc.dashboard.injected') : '· '}{e.affects_all_teams ? t('sc.dashboard.affects_everyone') : t('sc.dashboard.affects_team')}
          </Text>
        </Space>
      ),
      children: <Paragraph style={{ margin: 0, fontSize: 13 }}>{e.narrative || t('sc.dashboard.disruption_occurred')}</Paragraph>,
    })),
    ...compliance.slice(0, 12).map((e) => {
      const active = e.freeze_until_round >= currentRound || e.round_number === currentRound;
      return {
        key: `comp-${e.id}`,
        label: (
          <Space size={6} wrap>
            <Tag color={active ? 'red' : 'default'}>{t('sc.dashboard.compliance')}</Tag>
            <Text strong>{e.regime_name}</Text>
            <Text type="secondary">R{e.round_number}{e.market_code ? ` · ${e.market_code}` : ''} · {money(Number(e.cost_usd))}
              {e.freeze_until_round >= currentRound ? ` · frozen thru R${e.freeze_until_round}` : ''}</Text>
          </Space>
        ),
        children: <Paragraph style={{ margin: 0, fontSize: 13 }}>{e.narrative || `${e.regime_name} enforcement.`}</Paragraph>,
      };
    }),
  ];

  return (
    <div style={{ maxWidth: 1200, width: '100%' }}>
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {t('sc.dashboard.summary')}
        </Text>
        <Button size="small" icon={<ReloadOutlined />} onClick={load}>{t('sc.dashboard.refresh')}</Button>
      </Space>
      <StateLegend />

      <Row gutter={16}>
        {/* 1. Resilience + this-round disruption impact */}
        <Col xs={24} md={8}>
          <SCCard title={t('sc.dashboard.resilience_score')} color="decision">
            {scoreCalculated ? <Statistic title={t('sc.dashboard.this_round')} value={score} /> : (
              <Alert type="info" showIcon message={t('sc.dashboard.not_scored')}
                description={t('sc.dashboard.score_help')} />
            )}
            {scoreCalculated && disrupted && (
              <Alert style={{ marginTop: 12 }} type="warning" showIcon icon={<WarningOutlined />}
                message={t('sc.dashboard.impact_this_round')}
                description={(
                  <Space direction="vertical" size={0} style={{ fontSize: 12 }}>
                    {cf !== undefined && cf < 1 && (
                      <Text>{t('sc.dashboard.production_capacity')}: <Text strong>{Math.round(cf * 100)}%</Text> {t('sc.dashboard.input_shortfall')}</Text>
                    )}
                    {lostSales > 0 && <Text>{t('sc.dashboard.lost_sales')}: <Text strong>{money(lostSales)}</Text></Text>}
                    {disruptionCost > 0 && <Text>{t('sc.dashboard.disruption_costs')}: <Text strong>{money(disruptionCost)}</Text></Text>}
                  </Space>
                )} />
            )}
          </SCCard>
        </Col>

        {/* 2. Your exposure — consolidated sourcing/geography/buffer risk */}
        <Col xs={24} md={16}>
          <SCCard title={t('sc.dashboard.your_exposure')} color="strategic"
            onEdit={() => go('/decisions/sourcing')} editLabel={t('sc.dashboard.edit_sourcing')}
            empty={allocations.length === 0 && invRows.length === 0}
            emptyText={t('sc.dashboard.exposure_empty')}>
            <Row gutter={[16, 12]}>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('sc.dashboard.single_source_risk')}</Text>
                <div style={{ marginTop: 4 }}>
                  {singleSourced.length
                    ? <Space wrap size={4}>{singleSourced.map((c) => <Tag color="red" key={c}>{pretty(c)}</Tag>)}</Space>
                    : <Tag color="green">{allocations.length ? t('sc.common.none') : '—'}</Tag>}
                </div>
              </Col>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('sc.dashboard.geo_concentration')}</Text>
                <div style={{ marginTop: 4 }}>
                  {topCountry
                    ? (
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Space><Tag color={topCountry.pct > 50 ? 'orange' : 'default'}>{topCountry.country}</Tag>
                          <Text strong>{topCountry.pct}%</Text>
                          {topCountry.pct > 50 && <Text type="secondary" style={{ fontSize: 11 }}>{t('sc.dashboard.concentrated')}</Text>}</Space>
                        <Progress percent={topCountry.pct} size="small" showInfo={false} status={topCountry.pct > 50 ? 'exception' : 'normal'} style={{ width: 130 }} />
                      </Space>
                    ) : <Text type="secondary">—</Text>}
                </div>
              </Col>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('sc.dashboard.buffer_adequacy')}</Text>
                <div style={{ marginTop: 4 }}>
                  {bufferAvg != null
                    ? <Space><Text strong>{t('sc.dashboard.days', { count: bufferAvg })}</Text><Tag color={thinBuffer ? 'orange' : 'green'}>{thinBuffer ? t('sc.dashboard.thin') : t('sc.dashboard.adequate')}</Tag>
                        <Button type="link" size="small" style={{ padding: 0 }} onClick={() => go('/decisions/inventory')}>{t('sc.common.edit')}</Button></Space>
                    : <Button type="link" size="small" style={{ padding: 0 }} onClick={() => go('/decisions/inventory')}>{t('sc.dashboard.set_buffers')}</Button>}
                </div>
              </Col>
            </Row>
          </SCCard>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 3. Compliance exposure */}
        <Col xs={24} md={10}>
          <SCCard title={t('sc.dashboard.compliance_risk')} color="decision">
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>{t('sc.dashboard.rules_apply')}</Paragraph>
            <Space wrap>{d.regimes.map((r) => <Tag key={r.id}>{r.name}</Tag>)}</Space>
            {flaggedNames.length > 0 ? (
              <Alert style={{ marginTop: 12 }} type="warning" showIcon icon={<WarningOutlined />}
                message={t('sc.dashboard.forced_labor_risk')}
                description={t('sc.dashboard.flagged_suppliers', { suppliers: flaggedNames.join(', ') })} />
            ) : (
              <Alert style={{ marginTop: 12 }} type="success" showIcon
                message={allocations.length ? t('sc.dashboard.no_flagged') : t('sc.dashboard.add_for_risk')} />
            )}
          </SCCard>
        </Col>

        {/* 4. Disruptions & alerts — the live feed (collapsible, active-first) */}
        <Col xs={24} md={14}>
          <SCCard title={t('sc.dashboard.disruptions_alerts')} color="strategic"
            empty={alertItems.length === 0}
            emptyText={t('sc.dashboard.no_alerts')}>
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
              {t('sc.dashboard.alert_summary', { disruptions: events.length, compliance: activeCompliance.length })}
            </Paragraph>
            <Collapse size="small" items={alertItems} />
          </SCCard>
        </Col>
      </Row>
    </div>
  );
};

export default SupplyChainPanel;
