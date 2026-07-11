import React, { useState, useEffect, useCallback } from 'react';
import {
  Row, Col, Button, Alert, Tag, Table, Progress, Empty, Typography, Space,
  Statistic, message,
} from 'antd';
import {
  ReloadOutlined, ArrowRightOutlined, WarningOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import {
  getSuppliers, getLanes, getComplianceRegimes, getSourcing, getLogistics,
  getTradeFinance, getInventory, getResilienceScore, getSCEvents,
} from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Text, Paragraph } = Typography;

const pretty = (c) => (c || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

// A card that always renders (honest empty state) and links to its edit page.
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

const SupplyChainDashboard = () => {
  const { gameId, teamId, scenarioId, currentRound } = useGame();
  const navigate = useNavigate();
  const round = currentRound || 1;
  const [loading, setLoading] = useState(true);
  const [d, setD] = useState(null);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    const safe = (p) => p.then((r) => r.data).catch(() => null);
    try {
      const [suppliers, lanes, regimes, sourcing, logistics, tf, inventory, resilience, events] = await Promise.all([
        safe(getSuppliers(scenarioId)), safe(getLanes(scenarioId)), safe(getComplianceRegimes(scenarioId)),
        safe(getSourcing(gameId, teamId, currentRound)), safe(getLogistics(gameId, teamId, currentRound)),
        safe(getTradeFinance(gameId, teamId, currentRound)), safe(getInventory(gameId, teamId, currentRound)),
        safe(getResilienceScore(gameId, teamId, currentRound)), safe(getSCEvents(gameId, teamId, currentRound)),
      ]);
      setD({ suppliers: suppliers || [], lanes: lanes || [], regimes: regimes || [],
        sourcing: sourcing || {}, logistics: logistics || {}, tf: tf || {},
        inventory: inventory || {}, resilience: resilience || {}, events: events || [] });
    } catch { message.error('Unable to load dashboard.'); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingSpinner />;
  if (!d) return <Alert type="warning" showIcon message="Dashboard data is unavailable for this team/round." />;

  const base = `/games/${gameId}/teams/${teamId}`;
  const go = (p) => navigate(`${base}${p}`);
  const supplierMap = {};
  d.suppliers.forEach((s) => { supplierMap[s.id] = s; });
  const allocations = d.sourcing.allocations || [];

  // 1. Supplier concentration by critical input category
  const byCat = {};
  allocations.forEach((a) => {
    (byCat[a.critical_input_category] = byCat[a.critical_input_category] || []).push(a);
  });
  const concentrationRows = Object.entries(byCat).map(([cat, allocs]) => {
    const maxPct = Math.max(...allocs.map((a) => a.allocation_pct || 0));
    return { cat, suppliers: allocs.length, maxPct,
      names: allocs.map((a) => (supplierMap[a.supplier]?.name) || `#${a.supplier}`) };
  });

  // 2. Geographic concentration by supplier country
  const byCountry = {};
  let totalWeight = 0;
  allocations.forEach((a) => {
    const c = supplierMap[a.supplier]?.country || '??';
    byCountry[c] = (byCountry[c] || 0) + (a.allocation_pct || 0);
    totalWeight += (a.allocation_pct || 0);
  });
  const geoRows = Object.entries(byCountry)
    .map(([c, w]) => ({ country: c, pct: totalWeight ? Math.round((w / totalWeight) * 100) : 0 }))
    .sort((x, y) => y.pct - x.pct);

  // 3. Lane exposure
  const laneMap = {};
  d.lanes.forEach((l) => { laneMap[l.id] = l; });
  const laneRows = (d.logistics.logistics || []).map((l) => ({
    lane: laneMap[l.lane]?.lane_id || `#${l.lane}`,
    split: ['sea', 'air', 'rail', 'road'].filter((m) => l[`mode_${m}_pct`] > 0)
      .map((m) => `${m} ${l[`mode_${m}_pct`]}%`).join(' · ') || '—',
  }));

  // 4. Compliance exposure — sourced suppliers with Xinjiang/forced-labor flags
  const flagged = allocations.map((a) => supplierMap[a.supplier]).filter(Boolean)
    .filter((s) => s.tier_2_3_profile?.risk_flags?.xinjiang_adjacent
      || s.tier_2_3_profile?.risk_flags?.forced_labor_exposure === 'high');
  const flaggedNames = [...new Set(flagged.map((s) => s.name))];

  // 5. Trade finance / FX posture
  const tfRows = d.tf.trade_finance || [];
  const sinosure = d.tf.sinosure || [];
  const fxHedges = d.tf.fx_hedges || [];

  // 6. Inventory buffer
  const invRows = d.inventory.inventory || [];

  // 7. SC events
  const events = d.events || [];

  // 8. Resilience score
  const score = d.resilience?.score;
  const scoreCalculated = score !== null && score !== undefined;

  return (
    <div style={{ maxWidth: 1200, width: '100%' }}>
      <PageHeader
        title="Supply Chain Dashboard"
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>Round {round} · A read-only summary of your supply-chain posture. Use the links to edit decisions.</Text>}
        actions={<Button icon={<ReloadOutlined />} onClick={load}>Reload</Button>}
      />

      <Row gutter={16}>
        {/* Resilience score */}
        <Col xs={24} md={8}>
          <SCCard title="Resilience Score" color="decision">
            {scoreCalculated ? (
              <Statistic title="Composite" value={score} />
            ) : (
              <Alert type="info" showIcon message="Not calculated yet"
                description="No ResilienceScoreHistory for this round. The engine computes this after round processing." />
            )}
          </SCCard>
        </Col>

        {/* Supplier concentration */}
        <Col xs={24} md={16}>
          <SCCard title="Supplier Concentration by Critical Input" color="strategic"
            onEdit={() => go('/decisions/sourcing')} editLabel="Manage sourcing"
            empty={concentrationRows.length === 0} emptyText="No sourcing allocations yet">
            <Table rowKey="cat" size="small" pagination={false} dataSource={concentrationRows}
              columns={[
                { title: 'Critical input', dataIndex: 'cat', render: (v) => <Text strong>{pretty(v)}</Text> },
                { title: 'Suppliers', dataIndex: 'suppliers' },
                { title: 'Top supplier share', dataIndex: 'maxPct',
                  render: (v) => <Space><Progress percent={v} size="small" style={{ width: 90 }} status={v >= 100 ? 'exception' : 'normal'} />{v >= 100 && <Tag color="red">single-source</Tag>}</Space> },
              ]} />
          </SCCard>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* Geographic concentration */}
        <Col xs={24} md={8}>
          <SCCard title="Geographic Concentration" color="strategic"
            onEdit={() => go('/decisions/sourcing')} editLabel="Manage sourcing"
            empty={geoRows.length === 0} emptyText="No sourcing allocations yet">
            {geoRows.map((r) => (
              <div key={r.country} style={{ marginBottom: 6 }}>
                <Space><Tag>{r.country}</Tag><Progress percent={r.pct} size="small" style={{ width: 120 }} /></Space>
              </div>
            ))}
          </SCCard>
        </Col>

        {/* Lane exposure */}
        <Col xs={24} md={16}>
          <SCCard title="Lane Exposure" color="neutral"
            onEdit={() => go('/decisions/logistics')} editLabel="Manage logistics"
            empty={laneRows.length === 0} emptyText="No logistics decisions yet">
            <Table rowKey="lane" size="small" pagination={false} dataSource={laneRows}
              columns={[{ title: 'Lane', dataIndex: 'lane', render: (v) => <Text strong>{v}</Text> },
                { title: 'Modal split', dataIndex: 'split' }]} />
          </SCCard>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* Compliance exposure */}
        <Col xs={24} md={12}>
          <SCCard title="Compliance Regime Exposure" color="decision">
            <Paragraph type="secondary" style={{ fontSize: 12 }}>Regimes active in this scenario:</Paragraph>
            <Space wrap>{d.regimes.map((r) => <Tag key={r.id}>{r.name}</Tag>)}</Space>
            {flaggedNames.length > 0 ? (
              <Alert style={{ marginTop: 12 }} type="warning" showIcon icon={<WarningOutlined />}
                message="Forced-labor / UFLPA exposure"
                description={`You are sourcing from flagged suppliers: ${flaggedNames.join(', ')}.`} />
            ) : (
              <Alert style={{ marginTop: 12 }} type="success" showIcon
                message={allocations.length ? 'No flagged suppliers in your current sourcing.' : 'No sourcing yet — no exposure computed.'} />
            )}
          </SCCard>
        </Col>

        {/* Trade finance / FX */}
        <Col xs={24} md={12}>
          <SCCard title="Trade Finance & FX Posture" color="strategic"
            onEdit={() => go('/decisions/trade-finance')} editLabel="Manage trade finance"
            empty={tfRows.length === 0 && sinosure.length === 0 && fxHedges.length === 0}
            emptyText="No trade finance or FX decisions yet">
            <Paragraph style={{ marginBottom: 4 }}><Text strong>Payment instruments:</Text> {tfRows.length}</Paragraph>
            <Space wrap>{[...new Set(tfRows.map((t) => t.buyer_payment_instrument).filter(Boolean))].map((i) => <Tag key={i}>{i}</Tag>)}</Space>
            <Paragraph style={{ margin: '8px 0 4px' }}><Text strong>Sinosure markets:</Text> {sinosure.length}</Paragraph>
            <Paragraph style={{ margin: '0 0 4px' }}><Text strong>FX hedges:</Text> {fxHedges.length}</Paragraph>
            <Space wrap>{fxHedges.map((h) => <Tag key={h.currency_pair}>{h.currency_pair} {h.hedge_ratio}%</Tag>)}</Space>
          </SCCard>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* Inventory buffer */}
        <Col xs={24} md={12}>
          <SCCard title="Inventory Buffer Summary" color="neutral"
            onEdit={() => go('/decisions/inventory')} editLabel="Manage inventory"
            empty={invRows.length === 0} emptyText="No inventory buffer decisions yet">
            <Table rowKey={(r) => `${r.product}-${r.market}`} size="small" pagination={false} dataSource={invRows}
              columns={[{ title: 'Buffer days', dataIndex: 'buffer_days' },
                { title: 'Safety trigger %', dataIndex: 'safety_stock_trigger_pct' }]} />
          </SCCard>
        </Col>

        {/* SC event log */}
        <Col xs={24} md={12}>
          <SCCard title="Supply-Chain Event Log" color="decision"
            empty={events.length === 0} emptyText="No supply-chain events this round">
            <Paragraph type="secondary" style={{ fontSize: 12 }}>{events.length} event(s) recorded this round.</Paragraph>
            {events.slice(0, 8).map((e) => (
              <div key={e.id}><Tag color={e.fired_by_instructor ? 'orange' : 'blue'}>event #{e.event_template}</Tag>
                {e.affects_all_teams ? ' market-wide' : ' team-specific'}</div>
            ))}
          </SCCard>
        </Col>
      </Row>
    </div>
  );
};

export default SupplyChainDashboard;
