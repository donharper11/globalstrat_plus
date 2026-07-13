import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table, Select, InputNumber, Button, Alert, message, Tag, Tooltip,
  Space, Typography, Empty, Divider,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, LockOutlined, SaveOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getInventory, saveInventory, getMarkets, getSuppliers, getLanes } from '../api/sc';
import { getProductContext } from '../api/decisions';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';
import { StateBadge, pageState } from '../components/sc/scState';

const { Text, Paragraph } = Typography;
const UNLOCK = { buffer_days: 3, safety_stock_trigger_pct: 3, contingency_plans: 5 };

const SUPPLIER_TRIGGERS = [
  { value: 'disruption', label: 'Is disrupted' },
  { value: 'delay', label: 'Delayed beyond (days)' },
  { value: 'capacity_drop', label: 'Loses capacity beyond (%)' },
];
const LANE_TRIGGERS = [
  { value: 'lead_time_exceeds', label: 'Sea lead time exceeds (days)' },
  { value: 'event', label: 'A disruption hits' },
];
const EVENT_TYPES = [
  { value: 'any', label: 'Any disruption' },
  { value: 'red_sea', label: 'Red Sea disruption' },
  { value: 'panama', label: 'Panama Canal drought' },
  { value: 'typhoon', label: 'Typhoon season' },
];
const MODES = ['sea', 'air', 'rail', 'road'];
const modeAvailable = (lane, mode) => { const e = lane?.modes ? lane.modes[mode] : null; return !!e && e.available !== false; };
const prettyCategory = (c) => (c || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());
const laneLabel = (l) => `${l.origin_port} (${l.origin_country}) → ${l.destination_port} (${l.destination_country})`;

const canonical = (rows, alt, modeR) => JSON.stringify({
  rows: (rows || []).map((r) => ({ p: r.product, m: r.market, b: r.buffer_days, s: r.safety_stock_trigger_pct })),
  alt: (alt || []).map((r) => ({ c: r.input_category, t: r.trigger, th: r.threshold, b: r.backup_supplier_id, s: r.shift_pct })),
  mode: (modeR || []).map((r) => ({ l: r.lane_id, t: r.trigger, th: r.threshold_days, e: r.event_type, f: r.from_mode, to: r.to_mode, s: r.shift_pct })),
});

const flattenErrors = (data) => {
  const out = [];
  const walk = (v, prefix) => {
    if (v == null) return;
    if (typeof v === 'string') { out.push(prefix ? `${prefix}: ${v}` : v); return; }
    if (Array.isArray(v)) { v.forEach((x) => walk(x, prefix)); return; }
    if (typeof v === 'object') Object.entries(v).forEach(([k, val]) => { const label = k === 'non_field_errors' ? '' : k; walk(val, prefix ? `${prefix}.${label}` : label); });
  };
  walk(data, '');
  return out.length ? out : ['Something went wrong.'];
};
const lockTag = (r) => (<Tooltip title={`Unlocks in round ${r}`}><Tag icon={<LockOutlined />} style={{ marginLeft: 6 }}>Round {r}</Tag></Tooltip>);
let seq = 1;

const InventoryPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, scenarioId, currentRound, roundStatus } = useGame();
  const { locked } = useDecisions();
  const round = currentRound || 1;
  const editable = roundStatus === 'open' && !locked;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [products, setProducts] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [lanes, setLanes] = useState([]);
  const [rows, setRows] = useState([]);        // buffer inventory
  const [altRules, setAltRules] = useState([]); // structured alt-supplier rules
  const [modeRules, setModeRules] = useState([]); // structured mode-switch rules
  const [serverErrors, setServerErrors] = useState([]);
  const [snap, setSnap] = useState(null);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [prodRes, mktRes, supRes, laneRes, invRes] = await Promise.all([
        getProductContext(gameId, teamId), getMarkets(scenarioId), getSuppliers(scenarioId),
        getLanes(scenarioId), getInventory(gameId, teamId, currentRound),
      ]);
      setProducts(prodRes.data?.products || []); setMarkets(mktRes.data || []);
      setSuppliers(supRes.data || []); setLanes(laneRes.data || []);
      const loadedRows = (invRes.data?.inventory || []).map((it) => ({
        key: `inv-${seq++}`, product: it.product, market: it.market,
        buffer_days: it.buffer_days ?? 30, safety_stock_trigger_pct: it.safety_stock_trigger_pct ?? 20 }));
      setRows(loadedRows);
      const cp = invRes.data?.contingency;
      const alt = (cp?.alt_supplier_activation_rules || []).filter((r) => r && typeof r === 'object')
        .map((r) => ({ key: `alt-${seq++}`, input_category: r.input_category, trigger: r.trigger || 'disruption',
          threshold: r.threshold, backup_supplier_id: r.backup_supplier_id, shift_pct: r.shift_pct ?? 50 }));
      const mr = (cp?.mode_switch_triggers || []).filter((r) => r && typeof r === 'object')
        .map((r) => ({ key: `mr-${seq++}`, lane_id: r.lane_id, trigger: r.trigger || 'event', threshold_days: r.threshold_days,
          event_type: r.event_type || 'any', from_mode: r.from_mode || 'sea', to_mode: r.to_mode || 'air', shift_pct: r.shift_pct ?? 30 }));
      setAltRules(alt); setModeRules(mr);
      setSnap(canonical(loadedRows, alt, mr));
    } catch { message.error(t('sc.inventory.load_error')); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  const categories = useMemo(() => {
    const s = new Set(); suppliers.forEach((x) => (x.specialization || []).forEach((sp) => s.add(sp))); return Array.from(s).sort();
  }, [suppliers]);
  const suppliersFor = (cat) => suppliers.filter((s) => (s.specialization || []).includes(cat));
  const laneById = useMemo(() => { const o = {}; lanes.forEach((l) => { o[l.id] = l; }); return o; }, [lanes]);

  const addRow = () => setRows((p) => [...p, { key: `inv-${seq++}`, product: null, market: null, buffer_days: 30, safety_stock_trigger_pct: 20 }]);
  const updRow = (key, patch) => setRows((p) => p.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const delRow = (key) => setRows((p) => p.filter((r) => r.key !== key));
  const addAlt = () => setAltRules((p) => [...p, { key: `alt-${seq++}`, input_category: null, trigger: 'disruption', threshold: 7, backup_supplier_id: null, shift_pct: 50 }]);
  const updAlt = (key, patch) => setAltRules((p) => p.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const delAlt = (key) => setAltRules((p) => p.filter((r) => r.key !== key));
  const addMode = () => setModeRules((p) => [...p, { key: `mr-${seq++}`, lane_id: null, trigger: 'event', threshold_days: 40, event_type: 'any', from_mode: 'sea', to_mode: 'air', shift_pct: 30 }]);
  const updMode = (key, patch) => setModeRules((p) => p.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const delMode = (key) => setModeRules((p) => p.filter((r) => r.key !== key));

  const validate = () => {
    const errs = [];
    rows.forEach((r, i) => { if ((r.product && !r.market) || (!r.product && r.market)) errs.push(`Buffer row ${i + 1}: choose both a product and a market.`); });
    altRules.forEach((r, i) => { if (!r.input_category || !r.backup_supplier_id) errs.push(`Backup rule ${i + 1}: choose an input and a backup supplier.`); });
    modeRules.forEach((r, i) => { if (!r.lane_id || !r.from_mode || !r.to_mode) errs.push(`Mode-switch rule ${i + 1}: choose a route and both modes.`); });
    return errs;
  };

  const handleSave = async () => {
    setServerErrors([]);
    const errs = validate();
    if (errs.length) { errs.forEach((e) => message.error(e)); setServerErrors(errs); return; }

    const inventory = round >= UNLOCK.buffer_days
      ? rows.filter((r) => r.product && r.market).map((r) => ({ product: r.product, market: r.market, buffer_days: r.buffer_days ?? 30, safety_stock_trigger_pct: r.safety_stock_trigger_pct ?? 20 }))
      : [];
    const payload = { inventory };
    if (round >= UNLOCK.contingency_plans && (altRules.length || modeRules.length)) {
      payload.contingency = {
        alt_supplier_activation_rules: altRules.filter((r) => r.input_category && r.backup_supplier_id).map((r) => {
          const o = { input_category: r.input_category, trigger: r.trigger, backup_supplier_id: r.backup_supplier_id, shift_pct: r.shift_pct ?? 50 };
          if (r.trigger !== 'disruption') o.threshold = r.threshold ?? 0;
          return o;
        }),
        mode_switch_triggers: modeRules.filter((r) => r.lane_id && r.from_mode && r.to_mode).map((r) => {
          const o = { lane_id: r.lane_id, trigger: r.trigger, from_mode: r.from_mode, to_mode: r.to_mode, shift_pct: r.shift_pct ?? 30 };
          if (r.trigger === 'lead_time_exceeds') o.threshold_days = r.threshold_days ?? 0; else o.event_type = r.event_type || 'any';
          return o;
        }),
      };
    }

    setSaving(true);
    try {
      await saveInventory(gameId, teamId, currentRound, payload);
      message.success(t('sc.inventory.saved_toast'));
      await load();
    } catch (err) {
      if (err.response?.status === 400) { setServerErrors(flattenErrors(err.response.data)); message.error('The server rejected this. See the notes above.'); }
      else if (err.response?.status === 403) message.error("This round isn't open for changes.");
      else message.error('Save failed.');
    } finally { setSaving(false); }
  };

  if (loading) return <LoadingSpinner />;
  const invLocked = round < UNLOCK.buffer_days;
  const cpLocked = round < UNLOCK.contingency_plans;
  const dis = (extra) => !editable || cpLocked || extra;
  const dirty = snap !== null && canonical(rows, altRules, modeRules) !== snap;
  const st = pageState({ locked, editable, dirty });

  return (
    <div style={{ maxWidth: 1080, width: '100%' }}>
      <PageHeader
        title={t('sc.inventory.title')}
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>{t('sc.common.round')} {round} · {t('sc.inventory.subtitle')}</Text>}
        status={locked ? 'locked' : 'draft'}
        actions={<Space>
          <StateBadge state={st} />
          <Button icon={<ReloadOutlined />} onClick={load} disabled={saving}>Reload</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!editable} onClick={handleSave}>Save</Button>
        </Space>} />

      {!editable && <Alert type="info" showIcon style={{ marginBottom: 16 }} message={locked ? t('sc.common.locked_notice') : t('sc.common.readonly_notice')} />}
      {serverErrors.length > 0 && <Alert type="error" showIcon closable style={{ marginBottom: 16 }} onClose={() => setServerErrors([])} message="Please fix these" description={<ul style={{ margin: 0, paddingLeft: 18 }}>{serverErrors.map((e, i) => <li key={i}>{e}</li>)}</ul>} />}

      <PanelCard headerColor="decision" title={<Space>Inventory Buffers {invLocked && lockTag(UNLOCK.buffer_days)}</Space>} style={{ marginBottom: 16 }}>
        {rows.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No buffers set yet" /> : (
          <Table rowKey="key" size="small" pagination={false} dataSource={rows}
            columns={[
              { title: 'Product', key: 'p', width: 240, render: (_, r) => (<Select style={{ width: 220 }} placeholder="Product" value={r.product} disabled={!editable || invLocked} options={products.map((p) => ({ value: p.id, label: p.name }))} onChange={(v) => updRow(r.key, { product: v })} />) },
              { title: 'Market', key: 'm', width: 200, render: (_, r) => (<Select style={{ width: 180 }} placeholder="Market" value={r.market} disabled={!editable || invLocked} options={markets.map((m) => ({ value: m.id, label: `${m.name} (${m.code})` }))} onChange={(v) => updRow(r.key, { market: v })} />) },
              { title: 'Buffer (days)', key: 'bd', width: 130, render: (_, r) => (<InputNumber min={0} value={r.buffer_days} disabled={!editable || invLocked} onChange={(v) => updRow(r.key, { buffer_days: v ?? 0 })} />) },
              { title: 'Reorder at (%)', key: 'ss', width: 140, render: (_, r) => (<InputNumber min={0} max={100} value={r.safety_stock_trigger_pct} disabled={!editable || invLocked} onChange={(v) => updRow(r.key, { safety_stock_trigger_pct: v ?? 0 })} />) },
              { title: '', key: 'x', width: 40, render: (_, r) => <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => delRow(r.key)} /> },
            ]} />
        )}
        <Button icon={<PlusOutlined />} onClick={addRow} disabled={!editable || invLocked} style={{ marginTop: 12 }}>Add buffer</Button>
      </PanelCard>

      <Divider orientation="left">Backup Plans (fire automatically during disruptions)</Divider>

      <PanelCard headerColor="neutral" title={<Space>Backup Supplier Rules {cpLocked && lockTag(UNLOCK.contingency_plans)}</Space>} style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>“If my supplier for an input is hit, automatically shift part of that input to a backup supplier.” These run by themselves when a disruption strikes.</Paragraph>
        {altRules.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No backup supplier rules yet" /> : (
          <Table rowKey="key" size="small" pagination={false} dataSource={altRules}
            columns={[
              { title: 'Input', key: 'c', width: 170, render: (_, r) => (<Select style={{ width: 150 }} placeholder="Input" value={r.input_category} disabled={dis(false)} options={categories.map((c) => ({ value: c, label: prettyCategory(c) }))} onChange={(v) => updAlt(r.key, { input_category: v, backup_supplier_id: null })} />) },
              { title: 'When it', key: 't', width: 190, render: (_, r) => (<Select style={{ width: 170 }} value={r.trigger} disabled={dis(false)} options={SUPPLIER_TRIGGERS} onChange={(v) => updAlt(r.key, { trigger: v })} />) },
              { title: 'Amount', key: 'th', width: 100, render: (_, r) => (r.trigger === 'disruption' ? <Text type="secondary">—</Text> : <InputNumber min={0} value={r.threshold} disabled={dis(false)} onChange={(v) => updAlt(r.key, { threshold: v ?? 0 })} />) },
              { title: 'Shift to backup', key: 'b', width: 220, render: (_, r) => (<Select style={{ width: 200 }} placeholder="Backup supplier" value={r.backup_supplier_id} disabled={dis(!r.input_category)} showSearch optionFilterProp="label" options={suppliersFor(r.input_category).map((s) => ({ value: s.id, label: `${s.name} (${s.country})` }))} onChange={(v) => updAlt(r.key, { backup_supplier_id: v })} />) },
              { title: 'Shift %', key: 's', width: 90, render: (_, r) => (<InputNumber min={0} max={100} value={r.shift_pct} disabled={dis(false)} onChange={(v) => updAlt(r.key, { shift_pct: v ?? 0 })} />) },
              { title: '', key: 'x', width: 40, render: (_, r) => <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => delAlt(r.key)} /> },
            ]} />
        )}
        <Button icon={<PlusOutlined />} onClick={addAlt} disabled={dis(false)} style={{ marginTop: 12 }}>Add backup rule</Button>
      </PanelCard>

      <PanelCard headerColor="neutral" title={<Space>Mode-Switch Rules {cpLocked && lockTag(UNLOCK.contingency_plans)}</Space>} style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>“If a route gets slow or disrupted, automatically move part of its shipments to a faster mode.”</Paragraph>
        {modeRules.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No mode-switch rules yet" /> : (
          <Table rowKey="key" size="small" pagination={false} dataSource={modeRules} scroll={{ x: true }}
            columns={[
              { title: 'Route', key: 'l', width: 250, render: (_, r) => (<Select style={{ width: 230 }} showSearch optionFilterProp="label" placeholder="Route" value={r.lane_id} disabled={dis(false)} options={lanes.map((l) => ({ value: l.id, label: laneLabel(l) }))} onChange={(v) => updMode(r.key, { lane_id: v })} />) },
              { title: 'When', key: 't', width: 210, render: (_, r) => (<Select style={{ width: 190 }} value={r.trigger} disabled={dis(false)} options={LANE_TRIGGERS} onChange={(v) => updMode(r.key, { trigger: v })} />) },
              { title: 'Detail', key: 'th', width: 180, render: (_, r) => (r.trigger === 'lead_time_exceeds'
                ? <InputNumber min={0} value={r.threshold_days} disabled={dis(false)} onChange={(v) => updMode(r.key, { threshold_days: v ?? 0 })} />
                : <Select style={{ width: 160 }} value={r.event_type} disabled={dis(false)} options={EVENT_TYPES} onChange={(v) => updMode(r.key, { event_type: v })} />) },
              { title: 'From → To', key: 'ft', width: 200, render: (_, r) => { const lane = laneById[r.lane_id]; const opts = MODES.map((m) => ({ value: m, label: m, disabled: lane ? !modeAvailable(lane, m) : false })); return (<Space>
                <Select style={{ width: 80 }} value={r.from_mode} disabled={dis(false)} options={opts} onChange={(v) => updMode(r.key, { from_mode: v })} />
                <Text type="secondary">→</Text>
                <Select style={{ width: 80 }} value={r.to_mode} disabled={dis(false)} options={opts} onChange={(v) => updMode(r.key, { to_mode: v })} />
              </Space>); } },
              { title: 'Shift %', key: 's', width: 90, render: (_, r) => (<InputNumber min={0} max={100} value={r.shift_pct} disabled={dis(false)} onChange={(v) => updMode(r.key, { shift_pct: v ?? 0 })} />) },
              { title: '', key: 'x', width: 40, render: (_, r) => <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => delMode(r.key)} /> },
            ]} />
        )}
        <Button icon={<PlusOutlined />} onClick={addMode} disabled={dis(false)} style={{ marginTop: 12 }}>Add mode-switch rule</Button>
      </PanelCard>
    </div>
  );
};

export default InventoryPage;
