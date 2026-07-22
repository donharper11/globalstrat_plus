import React, { useState, useEffect, useCallback } from 'react';
import {
  Table, Tag, Select, Button, Space, Typography, Alert, message,
  Card, Descriptions, InputNumber, Tooltip, Empty,
} from 'antd';
import { ThunderboltOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  getInstructorSCPanel, getInstructorSCEventCatalog, injectSCEvent,
  getResilienceWeightOverrides, saveResilienceWeightOverride,
} from '../../api/sc';

const { Text, Title } = Typography;

const scoreColor = (s) => (s == null ? 'default' : s >= 60 ? 'green' : s >= 30 ? 'gold' : 'red');
const money = (n) => (n == null ? '—' : `$${Math.round(Number(n)).toLocaleString()}`);
const RISK_COMPONENTS = [
  'semiconductor', 'power_management', 'display', 'battery', 'final_assembly',
  'pcb', 'enclosure', 'camera_module', 'memory', 'processor', 'chips',
];

const formatRiskFlag = (flag) => {
  const raw = String(flag || '');
  if (raw.includes(',')) return raw.replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
  let remaining = raw.toLowerCase().replace(/[\s_-]+/g, '');
  const parts = [];
  while (remaining.length) {
    let match = null;
    for (const component of RISK_COMPONENTS) {
      const compact = component.replace(/_/g, '');
      if (remaining.startsWith(compact)) {
        match = component;
        break;
      }
    }
    if (!match) break;
    parts.push(match.replace(/_/g, ' '));
    remaining = remaining.slice(match.replace(/_/g, '').length);
  }
  if (parts.length) return parts.join(', ');
  return raw.replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
};

const normalizePanel = (panel) => ({
  ...panel,
  teams: (panel?.teams || []).map(team => ({
    ...team,
    single_source_flags: (team.single_source_flags || []).map(formatRiskFlag),
  })),
});

const WEIGHT_LABELS = {
  multi_sourcing: 'Multi-sourcing',
  geographic_diversity: 'Geographic diversity',
  buffer_inventory_adequacy: 'Buffer inventory',
  modal_flexibility: 'Modal flexibility',
  tier_2_visibility: 'Tier-2 visibility',
  supplier_financial_health: 'Supplier fin. health',
};

/**
 * CC-16 Instructor Supply-Chain Panel.
 * Per-team SC decision viewing + resilience audit, live event injection, and
 * class resilience-weight overrides. Self-contained: fetches its own data from
 * the real instructor SC endpoints.
 */
const InstructorSCPanel = ({ gameId }) => {
  const [panel, setPanel] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [overrides, setOverrides] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [injecting, setInjecting] = useState(false);
  const [weightDraft, setWeightDraft] = useState({ name: null, value: null });
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    try {
      const [p, c, o] = await Promise.all([
        getInstructorSCPanel(gameId),
        getInstructorSCEventCatalog(gameId),
        getResilienceWeightOverrides(gameId).catch(() => ({ data: [] })),
      ]);
      setPanel(normalizePanel(p.data));
      setCatalog(c.data.events || []);
      setOverrides(o.data || []);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load the supply-chain panel.');
    } finally {
      setLoading(false);
    }
  }, [gameId]);

  useEffect(() => { load(); }, [load]);

  const handleInject = async () => {
    if (!selectedEvent) return;
    setInjecting(true);
    try {
      const { data } = await injectSCEvent(gameId, selectedEvent);
      message.success(data.message || 'Event injected.');
      setSelectedEvent(null);
      await load();
    } catch (e) {
      message.error(e?.response?.data?.detail || 'Injection failed.');
    } finally {
      setInjecting(false);
    }
  };

  const handleSaveWeight = async () => {
    if (!weightDraft.name || weightDraft.value == null) return;
    try {
      await saveResilienceWeightOverride(gameId, {
        weight_name: weightDraft.name, override_value: weightDraft.value,
        reason: 'Set from instructor SC panel',
      });
      message.success('Resilience weight override saved.');
      setWeightDraft({ name: null, value: null });
      await load();
    } catch (e) {
      const d = e?.response?.data;
      message.error(typeof d === 'string' ? d : (d?.detail || JSON.stringify(d) || 'Save failed.'));
    }
  };

  if (error) {
    return <Alert type="error" showIcon message={error} action={<Button onClick={load}>Retry</Button>} />;
  }

  const weights = panel?.effective_resilience_weights || {};

  const columns = [
    { title: 'Team', dataIndex: 'team_name', key: 'team_name', fixed: 'left',
      render: (v) => <Text strong>{v}</Text> },
    { title: 'Resilience', key: 'score', width: 120,
      render: (_, r) => (r.resilience
        ? <Tag color={scoreColor(r.resilience.score)}>{r.resilience.score.toFixed(1)}</Tag>
        : <Text type="secondary">not scored</Text>) },
    { title: 'Sourcing strategy', dataIndex: 'multi_sourcing_strategy', key: 'strat',
      render: (v) => v ? <Tag>{v.replace(/_/g, ' ')}</Tag> : <Text type="secondary">—</Text> },
    { title: 'Single-source risk', dataIndex: 'single_source_flags', key: 'ssf',
      render: (flags) => (flags && flags.length
        ? <Text type="danger">{flags.map(formatRiskFlag).join(', ')}</Text>
        : <Tag color="green">none</Tag>) },
    { title: 'Buffer (days)', dataIndex: 'buffer_days_avg', key: 'buf',
      render: (v) => v == null ? <Text type="secondary">—</Text> : v },
    { title: 'Contingency', dataIndex: 'has_contingency', key: 'cont',
      render: (v) => v ? <Tag color="green">ready</Tag> : <Tag>none</Tag> },
    { title: 'Compliance', dataIndex: 'compliance_events', key: 'comp', width: 200,
      render: (evs) => (evs && evs.length)
        ? <Space direction="vertical" size={0}>
            {evs.map((e, i) => (
              <Text key={i} type="danger" style={{ fontSize: 12 }}>
                {e.regime}{e.market ? ` (${e.market})` : ''} — frozen thru R{e.freeze_until_round}
              </Text>
            ))}
          </Space>
        : <Tag color="green">clear</Tag> },
    { title: 'Disruption impact', key: 'impact', width: 170,
      render: (_, r) => {
        const i = r.resilience?.disruption_impact;
        if (!i || (i.capacity_factor == null)) return <Text type="secondary">—</Text>;
        const cf = i.capacity_factor;
        return (
          <Space direction="vertical" size={0}>
            <Text type={cf < 1 ? 'danger' : undefined}>capacity {(cf * 100).toFixed(0)}%</Text>
            {i.lost_revenue > 0 && <Text type="danger">lost {money(i.lost_revenue)}</Text>}
          </Space>
        );
      } },
  ];

  const expanded = (r) => {
    const comps = r.resilience?.components || {};
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Descriptions size="small" column={3} bordered
          title="Resilience components (weighted)">
          {Object.keys(WEIGHT_LABELS).map((k) => (
            <Descriptions.Item key={k} label={WEIGHT_LABELS[k]}>
              {comps[k] == null ? '—' : (comps[k]).toFixed(2)}
              {weights[k] != null && <Text type="secondary"> ×{Number(weights[k]).toFixed(2)}</Text>}
            </Descriptions.Item>
          ))}
        </Descriptions>
        <Table size="small" pagination={false} rowKey={(a, i) => `${a.category}-${a.supplier}-${i}`}
          dataSource={r.sourcing || []}
          locale={{ emptyText: 'No sourcing allocations this round.' }}
          columns={[
            { title: 'Input', dataIndex: 'category' },
            { title: 'Supplier', dataIndex: 'supplier' },
            { title: 'Country', dataIndex: 'country' },
            { title: 'Allocation %', dataIndex: 'allocation_pct' },
            { title: 'Status', dataIndex: 'disrupted',
              render: (d) => d ? <Tag color="red">disrupted</Tag> : <Tag color="green">ok</Tag> },
          ]} />
      </Space>
    );
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card size="small" title={<Space><ThunderboltOutlined />Inject supply-chain event</Space>}
        extra={<Button icon={<ReloadOutlined />} onClick={load} loading={loading} size="small">Refresh</Button>}>
        <Space wrap>
          <Select
            style={{ minWidth: 380 }} placeholder="Pick a supply-chain disruption to inject"
            value={selectedEvent} onChange={setSelectedEvent} loading={loading}
            options={catalog.map((e) => ({
              value: e.id,
              label: `${e.name} (${e.severity})`,
              title: e.effect_summary,
            }))}
            optionRender={(o) => (
              <div>
                <div>{o.data.label}</div>
                <Text type="secondary" style={{ fontSize: 12 }}>{o.data.title}</Text>
              </div>
            )}
          />
          <Tooltip title="Queues the event onto the current open round; it fires (real supplier/lane disruption) when you advance the round.">
            <Button type="primary" onClick={handleInject} disabled={!selectedEvent} loading={injecting}>
              Inject
            </Button>
          </Tooltip>
        </Space>
        {panel?.round_number != null && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">Injects onto round {panel.round_number} (fires on next advance).</Text>
          </div>
        )}
      </Card>

      {panel?.pending_injections?.length > 0 && (
        <Alert type="info" showIcon
          message={`${panel.pending_injections.length} injection(s) queued — fire on next round advance`}
          description={
            <Space direction="vertical" size={0}>
              {panel.pending_injections.map((p, i) => (
                <Text key={i}>{p.event} ({p.severity}) — fires when round {p.fires_on_round} is advanced</Text>
              ))}
            </Space>
          } />
      )}

      {panel?.active_disruptions?.length > 0 && (
        <Alert type="warning" showIcon
          message={`${panel.active_disruptions.length} disruption(s) active this round`}
          description={
            <Space direction="vertical" size={0}>
              {panel.active_disruptions.map((d, i) => (
                <Text key={i}>
                  {d.type === 'supplier'
                    ? `Supplier ${d.name} (${d.country}) — capacity ${(d.capacity_multiplier * 100).toFixed(0)}%, ${d.recovery_rounds_remaining} recovery round(s) left`
                    : `Lane ${d.name} — ${d.disruption} (freight ×${d.rate_modifier})`}
                </Text>
              ))}
            </Space>
          } />
      )}

      <Card size="small" title={<Space><Title level={5} style={{ margin: 0 }}>Per-team supply-chain audit</Title>
        {panel?.round_number != null && <Tag>round {panel.round_number}</Tag>}</Space>}>
        {panel?.teams?.filter(t => t?.team_id || t?.team_name).length
          ? <Table rowKey="team_id" size="small" loading={loading} scroll={{ x: 900 }}
              dataSource={panel.teams.filter(t => t?.team_id || t?.team_name)} columns={columns} pagination={false}
              expandable={{ expandedRowRender: expanded }} />
          : <Empty description="No teams / no SC data yet." />}
      </Card>

      <Card size="small" title="Class resilience-weight overrides"
        extra={<Text type="secondary">the 6 weights must sum to 1.0</Text>}>
        <Space wrap align="end">
          <Select style={{ minWidth: 200 }} placeholder="Weight" value={weightDraft.name}
            onChange={(v) => setWeightDraft((d) => ({ ...d, name: v }))}
            options={Object.keys(WEIGHT_LABELS).map((k) => ({
              value: k, label: `${WEIGHT_LABELS[k]}${weights[k] != null ? ` (now ${Number(weights[k]).toFixed(2)})` : ''}`,
            }))} />
          <InputNumber min={0} max={1} step={0.05} placeholder="value" value={weightDraft.value}
            onChange={(v) => setWeightDraft((d) => ({ ...d, value: v }))} />
          <Button onClick={handleSaveWeight} disabled={!weightDraft.name || weightDraft.value == null}>
            Save override
          </Button>
        </Space>
        {overrides.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {overrides.map((o) => (
              <Tag key={o.id || o.weight_name} color="blue">
                {WEIGHT_LABELS[o.weight_name] || o.weight_name}: {Number(o.override_value).toFixed(2)}
              </Tag>
            ))}
          </div>
        )}
      </Card>
    </Space>
  );
};

export default InstructorSCPanel;
