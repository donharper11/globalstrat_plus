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
    } catch { message.error('Unable to load supply chain summary.'); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingSpinner />;
  if (!d) return <Alert type="warning" showIcon message="Supply chain summary is unavailable for this round." />;

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
        <Space size={6}>
          <Tag color={e.fired_by_instructor ? 'orange' : 'blue'}>Disruption</Tag>
          <Text>{e.affects_all_teams ? 'Affects everyone' : 'Affects your team'}</Text>
        </Space>
      ),
      children: <Paragraph style={{ margin: 0, fontSize: 13 }}>{e.resolution_data?.narrative || 'A supply-chain disruption occurred this round.'}</Paragraph>,
    })),
    ...compliance.slice(0, 12).map((e) => {
      const active = e.freeze_until_round >= currentRound || e.round_number === currentRound;
      return {
        key: `comp-${e.id}`,
        label: (
          <Space size={6} wrap>
            <Tag color={active ? 'red' : 'default'}>Compliance</Tag>
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
          Your supply chain at a glance: how healthy you are, what's threatening you, and where you're exposed.
        </Text>
        <Button size="small" icon={<ReloadOutlined />} onClick={load}>Refresh</Button>
      </Space>
      <StateLegend />

      <Row gutter={16}>
        {/* 1. Resilience + this-round disruption impact */}
        <Col xs={24} md={8}>
          <SCCard title={t('sc.dashboard.resilience_score')} color="decision">
            {scoreCalculated ? <Statistic title="This round" value={score} /> : (
              <Alert type="info" showIcon message={t('sc.dashboard.not_scored')}
                description="Your resilience score appears here once the round has been processed." />
            )}
            {scoreCalculated && disrupted && (
              <Alert style={{ marginTop: 12 }} type="warning" showIcon icon={<WarningOutlined />}
                message="Disruption impact this round"
                description={(
                  <Space direction="vertical" size={0} style={{ fontSize: 12 }}>
                    {cf !== undefined && cf < 1 && (
                      <Text>Production capacity: <Text strong>{Math.round(cf * 100)}%</Text> (input shortfall)</Text>
                    )}
                    {lostSales > 0 && <Text>Lost sales: <Text strong>{money(lostSales)}</Text></Text>}
                    {disruptionCost > 0 && <Text>Disruption costs: <Text strong>{money(disruptionCost)}</Text></Text>}
                  </Space>
                )} />
            )}
          </SCCard>
        </Col>

        {/* 2. Your exposure — consolidated sourcing/geography/buffer risk */}
        <Col xs={24} md={16}>
          <SCCard title="Your Exposure" color="strategic"
            onEdit={() => go('/decisions/sourcing')} editLabel="Edit sourcing"
            empty={allocations.length === 0 && invRows.length === 0}
            emptyText="Set your sourcing and inventory to see where you're exposed.">
            <Row gutter={[16, 12]}>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>Single-source risk</Text>
                <div style={{ marginTop: 4 }}>
                  {singleSourced.length
                    ? <Space wrap size={4}>{singleSourced.map((c) => <Tag color="red" key={c}>{pretty(c)}</Tag>)}</Space>
                    : <Tag color="green">{allocations.length ? 'None' : '—'}</Tag>}
                </div>
              </Col>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>Geographic concentration</Text>
                <div style={{ marginTop: 4 }}>
                  {topCountry
                    ? (
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Space><Tag color={topCountry.pct > 50 ? 'orange' : 'default'}>{topCountry.country}</Tag>
                          <Text strong>{topCountry.pct}%</Text>
                          {topCountry.pct > 50 && <Text type="secondary" style={{ fontSize: 11 }}>concentrated</Text>}</Space>
                        <Progress percent={topCountry.pct} size="small" showInfo={false} status={topCountry.pct > 50 ? 'exception' : 'normal'} style={{ width: 130 }} />
                      </Space>
                    ) : <Text type="secondary">—</Text>}
                </div>
              </Col>
              <Col xs={24} md={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>Buffer adequacy</Text>
                <div style={{ marginTop: 4 }}>
                  {bufferAvg != null
                    ? <Space><Text strong>{bufferAvg} days</Text><Tag color={thinBuffer ? 'orange' : 'green'}>{thinBuffer ? 'thin' : 'adequate'}</Tag>
                        <Button type="link" size="small" style={{ padding: 0 }} onClick={() => go('/decisions/inventory')}>edit</Button></Space>
                    : <Button type="link" size="small" style={{ padding: 0 }} onClick={() => go('/decisions/inventory')}>Set inventory buffers</Button>}
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
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>Rules that apply in this market:</Paragraph>
            <Space wrap>{d.regimes.map((r) => <Tag key={r.id}>{r.name}</Tag>)}</Space>
            {flaggedNames.length > 0 ? (
              <Alert style={{ marginTop: 12 }} type="warning" showIcon icon={<WarningOutlined />}
                message="Forced-labor risk in your supply chain"
                description={`Some suppliers you use carry forced-labor risk: ${flaggedNames.join(', ')}. This can get shipments held at the border.`} />
            ) : (
              <Alert style={{ marginTop: 12 }} type="success" showIcon
                message={allocations.length ? 'None of your current suppliers are flagged for forced-labor risk.' : 'Add suppliers to see your compliance risk here.'} />
            )}
          </SCCard>
        </Col>

        {/* 4. Disruptions & alerts — the live feed (collapsible, active-first) */}
        <Col xs={24} md={14}>
          <SCCard title="Disruptions & Alerts" color="strategic"
            empty={alertItems.length === 0}
            emptyText="No active disruptions or compliance actions. This updates each round.">
            <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
              {events.length} disruption(s) this round{activeCompliance.length ? ` · ${activeCompliance.length} active compliance action(s)` : ''}. Click to read details.
            </Paragraph>
            <Collapse size="small" items={alertItems} />
          </SCCard>
        </Col>
      </Row>
    </div>
  );
};

export default SupplyChainPanel;
