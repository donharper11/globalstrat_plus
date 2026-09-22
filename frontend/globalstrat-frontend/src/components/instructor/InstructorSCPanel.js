import React, { useState, useEffect, useCallback } from 'react';
import {
  Table, Tag, Select, Button, Space, Typography, Alert, message,
  Card, Descriptions, InputNumber, Tooltip, Empty,
} from 'antd';
import { ThunderboltOutlined, ReloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
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

// The reason recorded with a weight override. The audit trail is English
// whatever the operator reads (R44), so this is not a t() key.
const OVERRIDE_REASON = 'Set from instructor SC panel';

const WEIGHT_NAMES = [
  'multi_sourcing', 'geographic_diversity', 'buffer_inventory_adequacy',
  'modal_flexibility', 'tier_2_visibility', 'supplier_financial_health',
];

// One literal key per weight, so the string gate can see every key (W-CE-17).
const weightLabel = (name, t) => {
  switch (name) {
    case 'multi_sourcing': return t('instructor.sc_weight_multi_sourcing');
    case 'geographic_diversity': return t('instructor.sc_weight_geographic_diversity');
    case 'buffer_inventory_adequacy': return t('instructor.sc_weight_buffer_inventory');
    case 'modal_flexibility': return t('instructor.sc_weight_modal_flexibility');
    case 'tier_2_visibility': return t('instructor.sc_weight_tier2_visibility');
    case 'supplier_financial_health': return t('instructor.sc_weight_supplier_financial_health');
    default: return name;
  }
};

const severityLabel = (severity, t) => {
  switch (severity) {
    case 'low': return t('instructor.severity_low');
    case 'medium': return t('instructor.severity_medium');
    case 'high': return t('instructor.severity_high');
    case 'critical': return t('instructor.severity_critical');
    default: return severity || '';
  }
};

/**
 * CC-16 Instructor Supply-Chain Panel.
 * Per-team SC decision viewing + resilience audit, live event injection, and
 * class resilience-weight overrides. Self-contained: fetches its own data from
 * the real instructor SC endpoints.
 *
 * Every word a person reads comes from the catalogue (W-CE-17, 2026-09-22):
 * the panel was English by construction, whatever language the console was in.
 */
const InstructorSCPanel = ({ gameId }) => {
  const { t } = useTranslation();
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
      setError(e?.response?.data?.detail || t('instructor.sc_load_failed'));
    } finally {
      setLoading(false);
    }
  }, [gameId, t]);

  useEffect(() => { load(); }, [load]);

  const handleInject = async () => {
    if (!selectedEvent) return;
    setInjecting(true);
    try {
      const { data } = await injectSCEvent(gameId, selectedEvent);
      message.success(data.message || t('instructor.sc_event_injected'));
      setSelectedEvent(null);
      await load();
    } catch (e) {
      message.error(e?.response?.data?.error || e?.response?.data?.detail || t('instructor.sc_injection_failed'));
    } finally {
      setInjecting(false);
    }
  };

  const handleSaveWeight = async () => {
    if (!weightDraft.name || weightDraft.value == null) return;
    try {
      await saveResilienceWeightOverride(gameId, {
        weight_name: weightDraft.name, override_value: weightDraft.value,
        reason: OVERRIDE_REASON,
      });
      message.success(t('instructor.sc_weights_saved'));
      setWeightDraft({ name: null, value: null });
      await load();
    } catch (e) {
      const d = e?.response?.data;
      message.error(typeof d === 'string' ? d : (d?.detail || JSON.stringify(d) || t('instructor.sc_save_failed')));
    }
  };

  if (error) {
    return <Alert type="error" showIcon message={error} action={<Button onClick={load}>{t('instructor.retry')}</Button>} />;
  }

  const weights = panel?.effective_resilience_weights || {};

  const columns = [
    { title: t('instructor.team'), dataIndex: 'team_name', key: 'team_name', fixed: 'left',
      render: (v) => <Text strong>{v}</Text> },
    { title: t('instructor.sc_resilience'), key: 'score', width: 120,
      render: (_, r) => (r.resilience
        ? <Tag color={scoreColor(r.resilience.score)}>{r.resilience.score.toFixed(1)}</Tag>
        : <Text type="secondary">{t('instructor.sc_not_scored')}</Text>) },
    { title: t('instructor.sc_sourcing_strategy'), dataIndex: 'multi_sourcing_strategy', key: 'strat',
      render: (v) => v ? <Tag>{v.replace(/_/g, ' ')}</Tag> : <Text type="secondary">—</Text> },
    { title: t('instructor.sc_single_source_risk'), dataIndex: 'single_source_flags', key: 'ssf',
      render: (flags) => (flags && flags.length
        ? <Text type="danger">{flags.map(formatRiskFlag).join(', ')}</Text>
        : <Tag color="green">{t('instructor.sc_none')}</Tag>) },
    { title: t('instructor.sc_buffer_days'), dataIndex: 'buffer_days_avg', key: 'buf',
      render: (v) => v == null ? <Text type="secondary">—</Text> : v },
    { title: t('instructor.sc_contingency'), dataIndex: 'has_contingency', key: 'cont',
      render: (v) => v ? <Tag color="green">{t('instructor.sc_ready')}</Tag> : <Tag>{t('instructor.sc_none')}</Tag> },
    { title: t('instructor.sc_compliance'), dataIndex: 'compliance_events', key: 'comp', width: 200,
      render: (evs) => (evs && evs.length)
        ? <Space direction="vertical" size={0}>
            {evs.map((e, i) => (
              <Text key={i} type="danger" style={{ fontSize: 12 }}>
                {t('instructor.sc_frozen_through', {
                  regime: e.regime, market: e.market ? ` (${e.market})` : '', round: e.freeze_until_round,
                })}
              </Text>
            ))}
          </Space>
        : <Tag color="green">{t('instructor.sc_clear')}</Tag> },
    { title: t('instructor.sc_disruption_impact'), key: 'impact', width: 170,
      render: (_, r) => {
        const i = r.resilience?.disruption_impact;
        if (!i || (i.capacity_factor == null)) return <Text type="secondary">—</Text>;
        const cf = i.capacity_factor;
        return (
          <Space direction="vertical" size={0}>
            <Text type={cf < 1 ? 'danger' : undefined}>{t('instructor.sc_capacity_pct', { pct: (cf * 100).toFixed(0) })}</Text>
            {i.lost_revenue > 0 && <Text type="danger">{t('instructor.sc_lost_revenue', { amount: money(i.lost_revenue) })}</Text>}
          </Space>
        );
      } },
  ];

  const expanded = (r) => {
    const comps = r.resilience?.components || {};
    return (
      <Space direction="vertical" style={{ width: '100%' }}>
        <Descriptions size="small" column={3} bordered
          title={t('instructor.sc_components_title')}>
          {WEIGHT_NAMES.map((k) => (
            <Descriptions.Item key={k} label={weightLabel(k, t)}>
              {comps[k] == null ? '—' : (comps[k]).toFixed(2)}
              {weights[k] != null && <Text type="secondary"> ×{Number(weights[k]).toFixed(2)}</Text>}
            </Descriptions.Item>
          ))}
        </Descriptions>
        <Table size="small" pagination={false} rowKey={(a, i) => `${a.category}-${a.supplier}-${i}`}
          dataSource={r.sourcing || []}
          locale={{ emptyText: t('instructor.sc_no_allocations') }}
          columns={[
            { title: t('instructor.sc_input'), dataIndex: 'category' },
            { title: t('instructor.sc_supplier'), dataIndex: 'supplier' },
            { title: t('instructor.sc_country'), dataIndex: 'country' },
            { title: t('instructor.sc_allocation_pct'), dataIndex: 'allocation_pct' },
            { title: t('instructor.status'), dataIndex: 'disrupted',
              render: (d) => d ? <Tag color="red">{t('instructor.sc_disrupted')}</Tag> : <Tag color="green">{t('instructor.sc_ok')}</Tag> },
          ]} />
      </Space>
    );
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card size="small" title={<Space><ThunderboltOutlined />{t('instructor.sc_inject_title')}</Space>}
        extra={<Button icon={<ReloadOutlined />} onClick={load} loading={loading} size="small">{t('instructor.refresh')}</Button>}>
        <Space wrap>
          <Select
            style={{ minWidth: 380 }} placeholder={t('instructor.sc_pick_disruption')}
            value={selectedEvent} onChange={setSelectedEvent} loading={loading}
            options={catalog.map((e) => ({
              value: e.id,
              label: `${e.name} (${severityLabel(e.severity, t)})`,
              title: e.effect_summary,
            }))}
            optionRender={(o) => (
              <div>
                <div>{o.data.label}</div>
                <Text type="secondary" style={{ fontSize: 12 }}>{o.data.title}</Text>
              </div>
            )}
          />
          <Tooltip title={t('instructor.sc_inject_tooltip')}>
            <Button type="primary" onClick={handleInject} disabled={!selectedEvent} loading={injecting}>
              {t('instructor.sc_inject')}
            </Button>
          </Tooltip>
        </Space>
        {panel?.round_number != null && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">{t('instructor.sc_injects_onto_round', { round: panel.round_number })}</Text>
          </div>
        )}
      </Card>

      {panel?.pending_injections?.length > 0 && (
        <Alert type="info" showIcon
          message={t('instructor.sc_injections_queued', { count: panel.pending_injections.length })}
          description={
            <Space direction="vertical" size={0}>
              {panel.pending_injections.map((p, i) => (
                <Text key={i}>
                  {t('instructor.sc_injection_row', {
                    event: p.event, severity: severityLabel(p.severity, t), round: p.fires_on_round,
                  })}
                </Text>
              ))}
            </Space>
          } />
      )}

      {panel?.active_disruptions?.length > 0 && (
        <Alert type="warning" showIcon
          message={t('instructor.sc_disruptions_active', { count: panel.active_disruptions.length })}
          description={
            <Space direction="vertical" size={0}>
              {panel.active_disruptions.map((d, i) => (
                <Text key={i}>
                  {d.type === 'supplier'
                    ? t('instructor.sc_supplier_disruption', {
                      name: d.name, country: d.country,
                      pct: (d.capacity_multiplier * 100).toFixed(0),
                      rounds: d.recovery_rounds_remaining,
                    })
                    : t('instructor.sc_lane_disruption', {
                      name: d.name, disruption: d.disruption, rate: d.rate_modifier,
                    })}
                </Text>
              ))}
            </Space>
          } />
      )}

      <Card size="small" title={<Space><Title level={5} style={{ margin: 0 }}>{t('instructor.sc_audit_title')}</Title>
        {panel?.round_number != null && <Tag>{t('instructor.sc_round_tag', { round: panel.round_number })}</Tag>}</Space>}>
        {panel?.teams?.filter(row => row?.team_id || row?.team_name).length
          ? <Table rowKey="team_id" size="small" loading={loading} scroll={{ x: 900 }}
              dataSource={panel.teams.filter(row => row?.team_id || row?.team_name)} columns={columns} pagination={false}
              expandable={{ expandedRowRender: expanded }} />
          : <Empty description={t('instructor.sc_no_teams')} />}
      </Card>

      <Card size="small" title={t('instructor.sc_overrides_title')}
        extra={<Text type="secondary">{t('instructor.sc_weights_sum_hint')}</Text>}>
        <Space wrap align="end">
          <Select style={{ minWidth: 200 }} placeholder={t('instructor.weight')} value={weightDraft.name}
            onChange={(v) => setWeightDraft((d) => ({ ...d, name: v }))}
            options={WEIGHT_NAMES.map((k) => ({
              value: k,
              label: weights[k] != null
                ? t('instructor.sc_weight_now', { label: weightLabel(k, t), value: Number(weights[k]).toFixed(2) })
                : weightLabel(k, t),
            }))} />
          <InputNumber min={0} max={1} step={0.05} placeholder={t('instructor.sc_value')} value={weightDraft.value}
            onChange={(v) => setWeightDraft((d) => ({ ...d, value: v }))} />
          <Button onClick={handleSaveWeight} disabled={!weightDraft.name || weightDraft.value == null}>
            {t('instructor.sc_save_override')}
          </Button>
        </Space>
        {overrides.length > 0 && (
          <div style={{ marginTop: 12 }}>
            {overrides.map((o) => (
              <Tag key={o.id || o.weight_name} color="blue">
                {weightLabel(o.weight_name, t)}: {Number(o.override_value).toFixed(2)}
              </Tag>
            ))}
          </div>
        )}
      </Card>
    </Space>
  );
};

export default InstructorSCPanel;
