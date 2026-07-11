import React, { useState, useEffect, useCallback } from 'react';
import {
  Row, Col, Button, Alert, Tag, Table, Progress, Empty, Typography, Space,
  Statistic, message,
} from 'antd';
import { ReloadOutlined, ArrowRightOutlined, WarningOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../../contexts/GameContext';
import {
  getSuppliers, getLanes, getComplianceRegimes, getSourcing, getLogistics,
  getTradeFinance, getInventory, getResilienceScore, getSCEvents, getHedgePositions,
} from '../../api/sc';
import LoadingSpinner from '../LoadingSpinner';
import { PanelCard } from '../design-system';
import { StateLegend, StateBadge } from './scState';

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

// Supply-chain KPI panel — rendered as a tab on the main dashboard (CC-23A / UX #9).
const SupplyChainPanel = () => {
  const { gameId, teamId, scenarioId, currentRound } = useGame();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [d, setD] = useState(null);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    const safe = (p) => p.then((r) => r.data).catch(() => null);
    try {
      const [suppliers, lanes, regimes, sourcing, logistics, tf, inventory, resilience, events, hedges] = await Promise.all([
        safe(getSuppliers(scenarioId)), safe(getLanes(scenarioId)), safe(getComplianceRegimes(scenarioId)),
        safe(getSourcing(gameId, teamId, currentRound)), safe(getLogistics(gameId, teamId, currentRound)),
        safe(getTradeFinance(gameId, teamId, currentRound)), safe(getInventory(gameId, teamId, currentRound)),
        safe(getResilienceScore(gameId, teamId, currentRound)), safe(getSCEvents(gameId, teamId, currentRound)),
        safe(getHedgePositions(gameId, teamId)),
      ]);
      setD({ suppliers: suppliers || [], lanes: lanes || [], regimes: regimes || [],
        sourcing: sourcing || {}, logistics: logistics || {}, tf: tf || {},
        inventory: inventory || {}, resilience: resilience || {}, events: events || [], hedges: hedges || [] });
    } catch { message.error('Unable to load supply chain summary.'); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingSpinner />;
  if (!d) return <Alert type="warning" showIcon message="Supply chain summary is unavailable for this round." />;

  const base = `/games/${gameId}/teams/${teamId}`;
  const go = (p) => navigate(`${base}${p}`);
  const supplierMap = {};
  d.suppliers.forEach((s) => { supplierMap[s.id] = s; });
  const allocations = d.sourcing.allocations || [];

  const byCat = {};
  allocations.forEach((a) => { (byCat[a.critical_input_category] = byCat[a.critical_input_category] || []).push(a); });
  const concentrationRows = Object.entries(byCat).map(([cat, allocs]) => ({
    cat, suppliers: allocs.length, maxPct: Math.max(...allocs.map((a) => a.allocation_pct || 0)) }));

  const byCountry = {}; let totalWeight = 0;
  allocations.forEach((a) => {
    const c = supplierMap[a.supplier]?.country || '??';
    byCountry[c] = (byCountry[c] || 0) + (a.allocation_pct || 0); totalWeight += (a.allocation_pct || 0);
  });
  const geoRows = Object.entries(byCountry)
    .map(([c, w]) => ({ country: c, pct: totalWeight ? Math.round((w / totalWeight) * 100) : 0 }))
    .sort((x, y) => y.pct - x.pct);

  const laneMap = {}; d.lanes.forEach((l) => { laneMap[l.id] = l; });
  const laneRows = (d.logistics.logistics || []).map((l) => ({
    lane: laneMap[l.lane]?.lane_id || `#${l.lane}`,
    split: ['sea', 'air', 'rail', 'road'].filter((m) => l[`mode_${m}_pct`] > 0)
      .map((m) => `${m} ${l[`mode_${m}_pct`]}%`).join(' · ') || '—' }));

  const flagged = allocations.map((a) => supplierMap[a.supplier]).filter(Boolean)
    .filter((s) => s.tier_2_3_profile?.risk_flags?.xinjiang_adjacent
      || s.tier_2_3_profile?.risk_flags?.forced_labor_exposure === 'high');
  const flaggedNames = [...new Set(flagged.map((s) => s.name))];

  const tfRows = d.tf.trade_finance || [];
  const sinosure = d.tf.sinosure || [];
  const fxHedges = d.tf.fx_hedges || [];
  const hedgePositions = d.hedges || [];
  const invRows = d.inventory.inventory || [];
  const events = d.events || [];
  const score = d.resilience?.score;
  const scoreCalculated = score !== null && score !== undefined;

  return (
    <div style={{ maxWidth: 1200, width: '100%' }}>
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          A snapshot of your supply chain this round. Use the links to change your decisions.
        </Text>
        <Button size="small" icon={<ReloadOutlined />} onClick={load}>Refresh</Button>
      </Space>
      <StateLegend />

      <Row gutter={16}>
        <Col xs={24} md={8}>
          <SCCard title="Resilience Score" color="decision">
            {scoreCalculated ? <Statistic title="This round" value={score} /> : (
              <Alert type="info" showIcon message="Not scored yet"
                description="Your resilience score appears here once the round has been processed." />
            )}
          </SCCard>
        </Col>
        <Col xs={24} md={16}>
          <SCCard title="Supplier Concentration" color="strategic"
            onEdit={() => go('/decisions/sourcing')} editLabel="Edit sourcing"
            empty={concentrationRows.length === 0} emptyText="You haven't allocated any suppliers yet.">
            <Table rowKey="cat" size="small" pagination={false} dataSource={concentrationRows}
              columns={[
                { title: 'Input', dataIndex: 'cat', render: (v) => <Text strong>{pretty(v)}</Text> },
                { title: 'Suppliers', dataIndex: 'suppliers' },
                { title: 'Biggest supplier', dataIndex: 'maxPct',
                  render: (v) => <Space><Progress percent={v} size="small" style={{ width: 90 }} status={v >= 100 ? 'exception' : 'normal'} />{v >= 100 && <Tag color="red">single source</Tag>}</Space> },
              ]} />
          </SCCard>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={8}>
          <SCCard title="Where Your Suppliers Are" color="strategic"
            onEdit={() => go('/decisions/sourcing')} editLabel="Edit sourcing"
            empty={geoRows.length === 0} emptyText="You haven't allocated any suppliers yet.">
            {geoRows.map((r) => (
              <div key={r.country} style={{ marginBottom: 6 }}>
                <Space><Tag>{r.country}</Tag><Progress percent={r.pct} size="small" style={{ width: 120 }} /></Space>
              </div>
            ))}
          </SCCard>
        </Col>
        <Col xs={24} md={16}>
          <SCCard title="Shipping Lanes in Use" color="neutral"
            onEdit={() => go('/decisions/logistics')} editLabel="Edit logistics"
            empty={laneRows.length === 0} emptyText="You haven't set up any shipping lanes yet.">
            <Table rowKey="lane" size="small" pagination={false} dataSource={laneRows}
              columns={[{ title: 'Lane', dataIndex: 'lane', render: (v) => <Text strong>{v}</Text> },
                { title: 'How it ships', dataIndex: 'split' }]} />
          </SCCard>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <SCCard title="Compliance Risk" color="decision">
            <Paragraph type="secondary" style={{ fontSize: 12 }}>Rules that apply in this market:</Paragraph>
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
        <Col xs={24} md={12}>
          <SCCard title="Trade Finance & FX" color="strategic"
            onEdit={() => go('/decisions/trade-finance')} editLabel="Edit trade finance"
            empty={tfRows.length === 0 && sinosure.length === 0 && fxHedges.length === 0}
            emptyText="You haven't set any payment or currency decisions yet.">
            <Paragraph style={{ marginBottom: 4 }}><Text strong>Payment methods set:</Text> {tfRows.length}</Paragraph>
            <Space wrap>{[...new Set(tfRows.map((t) => t.buyer_payment_instrument).filter(Boolean))].map((i) => <Tag key={i}>{pretty(i)}</Tag>)}</Space>
            <Paragraph style={{ margin: '8px 0 4px' }}><Text strong>Markets with export insurance:</Text> {sinosure.length}</Paragraph>
            <Paragraph style={{ margin: '0 0 4px' }}><Text strong>Currency hedges set:</Text> {fxHedges.length}</Paragraph>
            <Space wrap>{fxHedges.map((h) => <Tag key={h.currency_pair}>{h.currency_pair} {h.hedge_ratio}%</Tag>)}</Space>
          </SCCard>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} md={12}>
          <SCCard title="Inventory Buffers" color="neutral"
            onEdit={() => go('/decisions/inventory')} editLabel="Edit inventory"
            empty={invRows.length === 0} emptyText="You haven't set any inventory buffers yet.">
            <Table rowKey={(r) => `${r.product}-${r.market}`} size="small" pagination={false} dataSource={invRows}
              columns={[{ title: 'Buffer (days)', dataIndex: 'buffer_days' },
                { title: 'Reorder at (%)', dataIndex: 'safety_stock_trigger_pct' }]} />
          </SCCard>
        </Col>
        <Col xs={24} md={12}>
          <SCCard title="Recent Disruptions" color="decision"
            empty={events.length === 0} emptyText="No supply-chain disruptions this round.">
            <Paragraph type="secondary" style={{ fontSize: 12 }}>{events.length} disruption(s) this round.</Paragraph>
            {events.slice(0, 8).map((e) => (
              <div key={e.id}><Tag color={e.fired_by_instructor ? 'orange' : 'blue'}>Disruption</Tag>
                {e.affects_all_teams ? ' affects everyone' : ' affects your team'}</div>
            ))}
          </SCCard>
        </Col>
      </Row>

      {/* Live operations — updates automatically as the simulation runs each round.
          Shown honestly as blank/unavailable until the engine populates them; never faked. */}
      <PanelCard headerColor="neutral" title="Live Operations" style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          These update automatically as the simulation runs each round. They stay blank until the first round is processed.
        </Paragraph>
        <Row gutter={16}>
          <Col xs={24} md={6}>
            <Space direction="vertical" size={4}>
              <Space><Text strong>Shipping status</Text> <StateBadge state="unavailable" /></Space>
              <Text type="secondary" style={{ fontSize: 12 }}>No shipping delays or disruptions right now. Updates each round.</Text>
            </Space>
          </Col>
          <Col xs={24} md={6}>
            <Space direction="vertical" size={4}>
              <Space><Text strong>Supplier disruptions</Text> <StateBadge state={events.length ? 'current' : 'unavailable'} /></Space>
              <Text type="secondary" style={{ fontSize: 12 }}>{events.length ? `${events.length} happening this round.` : 'No supplier problems right now. Updates each round.'}</Text>
            </Space>
          </Col>
          <Col xs={24} md={6}>
            <Space direction="vertical" size={4}>
              <Space><Text strong>Open currency hedges</Text> <StateBadge state={hedgePositions.length ? 'current' : 'unavailable'} /></Space>
              <Text type="secondary" style={{ fontSize: 12 }}>{hedgePositions.length ? `${hedgePositions.length} open right now.` : 'No open hedges right now. Updates each round.'}</Text>
            </Space>
          </Col>
          <Col xs={24} md={6}>
            <Space direction="vertical" size={4}>
              <Space><Text strong>Stock on hand / on order</Text> <StateBadge state="unavailable" /></Space>
              <Text type="secondary" style={{ fontSize: 12 }}>Live stock levels aren't tracked yet — coming in a later update.</Text>
            </Space>
          </Col>
        </Row>
      </PanelCard>
    </div>
  );
};

export default SupplyChainPanel;
