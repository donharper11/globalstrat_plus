import React, { useState, useEffect, useCallback } from 'react';
import {
  Table, Select, InputNumber, Input, Button, Alert, message, Tag, Tooltip,
  Space, Typography, Empty, Divider,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, LockOutlined, SaveOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getInventory, saveInventory, getMarkets } from '../api/sc';
import { getProductContext } from '../api/decisions';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const UNLOCK = { buffer_days: 3, safety_stock_trigger_pct: 3, contingency_plans: 5 };

const flattenErrors = (data) => {
  const out = [];
  const walk = (v, prefix) => {
    if (v == null) return;
    if (typeof v === 'string') { out.push(prefix ? `${prefix}: ${v}` : v); return; }
    if (Array.isArray(v)) { v.forEach((x) => walk(x, prefix)); return; }
    if (typeof v === 'object') Object.entries(v).forEach(([k, val]) => {
      const label = k === 'non_field_errors' ? '' : k;
      walk(val, prefix ? `${prefix}.${label}` : label);
    });
  };
  walk(data, '');
  return out.length ? out : ['Request failed.'];
};
const lockTag = (r) => (
  <Tooltip title={`Unlocks at round ${r}`}>
    <Tag icon={<LockOutlined />} style={{ marginLeft: 6 }}>Round {r}</Tag>
  </Tooltip>
);
const linesToList = (s) => (s || '').split('\n').map((x) => x.trim()).filter(Boolean);
const listToLines = (l) => (Array.isArray(l) ? l : []).map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join('\n');
let seq = 1;

const InventoryPage = () => {
  const { gameId, teamId, scenarioId, currentRound, roundStatus } = useGame();
  const { locked } = useDecisions();
  const round = currentRound || 1;
  const editable = roundStatus === 'open' && !locked;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [products, setProducts] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [rows, setRows] = useState([]);   // {key, product, market, buffer_days, safety_stock_trigger_pct}
  const [playbook, setPlaybook] = useState('');
  const [altRules, setAltRules] = useState('');
  const [modeTriggers, setModeTriggers] = useState('');
  const [serverErrors, setServerErrors] = useState([]);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [prodRes, mktRes, invRes] = await Promise.all([
        getProductContext(gameId, teamId), getMarkets(scenarioId),
        getInventory(gameId, teamId, currentRound),
      ]);
      setProducts(prodRes.data?.products || []);
      setMarkets(mktRes.data || []);
      setRows((invRes.data?.inventory || []).map((it) => ({
        key: `inv-${seq++}`, product: it.product, market: it.market,
        buffer_days: it.buffer_days ?? 30, safety_stock_trigger_pct: it.safety_stock_trigger_pct ?? 20,
      })));
      const cp = invRes.data?.contingency;
      setPlaybook(cp?.disruption_response_playbook || '');
      setAltRules(listToLines(cp?.alt_supplier_activation_rules));
      setModeTriggers(listToLines(cp?.mode_switch_triggers));
    } catch { message.error('Unable to load inventory data.'); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  const addRow = () => setRows((p) => [...p, { key: `inv-${seq++}`, product: null, market: null, buffer_days: 30, safety_stock_trigger_pct: 20 }]);
  const updRow = (key, patch) => setRows((p) => p.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const delRow = (key) => setRows((p) => p.filter((r) => r.key !== key));

  const validate = () => {
    const errs = [];
    rows.forEach((r, i) => { if ((r.product && !r.market) || (!r.product && r.market)) errs.push(`Inventory row ${i + 1}: choose both a product and a market.`); });
    return errs;
  };

  const handleSave = async () => {
    setServerErrors([]);
    const errs = validate();
    if (errs.length) { errs.forEach((e) => message.error(e)); setServerErrors(errs); return; }

    const inventory = round >= UNLOCK.buffer_days
      ? rows.filter((r) => r.product && r.market).map((r) => ({
        product: r.product, market: r.market,
        buffer_days: r.buffer_days ?? 30, safety_stock_trigger_pct: r.safety_stock_trigger_pct ?? 20,
      })) : [];
    const payload = { inventory };
    if (round >= UNLOCK.contingency_plans && (playbook || altRules || modeTriggers)) {
      payload.contingency = {
        disruption_response_playbook: playbook,
        alt_supplier_activation_rules: linesToList(altRules),
        mode_switch_triggers: linesToList(modeTriggers),
      };
    }

    setSaving(true);
    try {
      await saveInventory(gameId, teamId, currentRound, payload);
      message.success('Inventory decision saved.');
      await load();
    } catch (err) {
      if (err.response?.status === 400) { setServerErrors(flattenErrors(err.response.data)); message.error('The server rejected this submission.'); }
      else if (err.response?.status === 403) message.error('This round is not open for submissions.');
      else message.error('Save failed.');
    } finally { setSaving(false); }
  };

  if (loading) return <LoadingSpinner />;
  const invLocked = round < UNLOCK.buffer_days;
  const cpLocked = round < UNLOCK.contingency_plans;

  return (
    <div style={{ maxWidth: 1050, width: '100%' }}>
      <PageHeader
        title="Inventory & Resilience"
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>Round {round} · Set buffer inventory by product/market and prepare disruption contingencies.</Text>}
        status={locked ? 'locked' : 'draft'}
        actions={<Space>
          <Button icon={<ReloadOutlined />} onClick={load} disabled={saving}>Reload</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!editable} onClick={handleSave}>Save</Button>
        </Space>} />

      {!editable && <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message={locked ? 'Decisions are locked for this round.' : 'This round is not open for submissions — read-only.'} />}
      {serverErrors.length > 0 && <Alert type="error" showIcon closable style={{ marginBottom: 16 }}
        onClose={() => setServerErrors([])} message="Submission errors"
        description={<ul style={{ margin: 0, paddingLeft: 18 }}>{serverErrors.map((e, i) => <li key={i}>{e}</li>)}</ul>} />}

      <PanelCard headerColor="decision"
        title={<Space>Buffer Inventory (by product / market) {invLocked && lockTag(UNLOCK.buffer_days)}</Space>} style={{ marginBottom: 16 }}>
        {rows.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No buffer settings yet" /> : (
          <Table rowKey="key" size="small" pagination={false} dataSource={rows}
            columns={[
              { title: 'Product', key: 'p', width: 240, render: (_, r) => (
                <Select style={{ width: 220 }} placeholder="Select product" value={r.product} disabled={!editable || invLocked}
                  options={products.map((p) => ({ value: p.id, label: p.name }))}
                  onChange={(v) => updRow(r.key, { product: v })} /> ) },
              { title: 'Market', key: 'm', width: 200, render: (_, r) => (
                <Select style={{ width: 180 }} placeholder="Select market" value={r.market} disabled={!editable || invLocked}
                  options={markets.map((m) => ({ value: m.id, label: `${m.name} (${m.code})` }))}
                  onChange={(v) => updRow(r.key, { market: v })} /> ) },
              { title: 'Buffer days', key: 'bd', width: 130, render: (_, r) => (
                <InputNumber min={0} value={r.buffer_days} disabled={!editable || invLocked}
                  onChange={(v) => updRow(r.key, { buffer_days: v ?? 0 })} /> ) },
              { title: 'Safety stock trigger %', key: 'ss', width: 170, render: (_, r) => (
                <InputNumber min={0} max={100} value={r.safety_stock_trigger_pct} disabled={!editable || invLocked}
                  onChange={(v) => updRow(r.key, { safety_stock_trigger_pct: v ?? 0 })} /> ) },
              { title: '', key: 'x', width: 40, render: (_, r) => <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => delRow(r.key)} /> },
            ]} />
        )}
        <Button icon={<PlusOutlined />} onClick={addRow} disabled={!editable || invLocked} style={{ marginTop: 12 }}>Add buffer setting</Button>
      </PanelCard>

      <Divider orientation="left">Contingency Planning</Divider>
      <PanelCard headerColor="neutral"
        title={<Space>Disruption Contingency Plan {cpLocked && lockTag(UNLOCK.contingency_plans)}</Space>} style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          Describe how your team responds to supply disruptions. One rule/trigger per line.
        </Paragraph>
        <div style={{ marginBottom: 12 }}>
          <Text strong>Response playbook</Text>
          <TextArea rows={3} maxLength={500} value={playbook} disabled={!editable || cpLocked}
            placeholder="e.g. On a tier-1 outage, shift volume to the backup supplier and switch premium SKUs to air freight."
            onChange={(e) => setPlaybook(e.target.value)} />
        </div>
        <Space align="start" style={{ width: '100%' }} wrap>
          <div style={{ minWidth: 320 }}>
            <Text strong>Alternative-supplier activation rules</Text>
            <TextArea rows={4} value={altRules} disabled={!editable || cpLocked}
              placeholder={'if delay > 7d then activate samsung_foundry_korea\nif capacity < 60% then split to smic_china'}
              onChange={(e) => setAltRules(e.target.value)} />
          </div>
          <div style={{ minWidth: 320 }}>
            <Text strong>Mode-switch triggers</Text>
            <TextArea rows={4} value={modeTriggers} disabled={!editable || cpLocked}
              placeholder={'if sea lead time > 40d then move 30% to air\nif Red Sea disruption then reroute via Cape'}
              onChange={(e) => setModeTriggers(e.target.value)} />
          </div>
        </Space>
      </PanelCard>
    </div>
  );
};

export default InventoryPage;
