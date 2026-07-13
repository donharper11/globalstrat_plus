import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table, Select, InputNumber, Input, Button, Alert, message, Tag, Tooltip,
  Space, Typography, Empty, Modal,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, LockOutlined, SaveOutlined, ReloadOutlined,
  EditOutlined, ShopOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getSuppliers, getSourcing, saveSourcing } from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';
import { StateBadge, pageState } from '../components/sc/scState';

const { Text, Paragraph } = Typography;

const canonical = (ms, tv, rs) => JSON.stringify({
  ms: ms || null, tv: tv || null,
  rows: (rs || []).map((r) => ({ c: r.critical_input_category, s: r.supplier,
    p: r.allocation_pct, pt: r.payment_terms, v: r.volume_commitment_units })),
});

// CC-2 §8 unlock schedule (server is authoritative; this drives disabled state).
const UNLOCK = { multiSupplier: 3, multi_sourcing_strategy: 3, payment_terms: 4,
  tier_2_3_visibility_investment: 5, volume_commitments: 5 };
const MULTI_SOURCING_OPTIONS = [
  { value: 'single_source', label: 'Single source' },
  { value: 'primary_backup', label: 'Primary + backup' },
  { value: 'balanced_split', label: 'Balanced split' },
  { value: 'geographic_diversity', label: 'Geographic diversity' },
];
const TIER_VISIBILITY_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'basic', label: 'Basic' },
  { value: 'comprehensive', label: 'Comprehensive' },
];

const prettyCategory = (c) => (c || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

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
  return out.length ? out : ['Something went wrong. Please check your inputs.'];
};

const lockTag = (r) => (
  <Tooltip title={`Unlocks in round ${r}`}>
    <Tag icon={<LockOutlined />} style={{ marginLeft: 6 }}>Round {r}</Tag>
  </Tooltip>
);

let rowSeq = 1;
const newRow = (category) => ({ key: `row-${rowSeq++}`, critical_input_category: category,
  supplier: null, allocation_pct: 0, payment_terms: '', volume_commitment_units: 0 });

const SourcingPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, scenarioId, currentRound, roundStatus } = useGame();
  const { locked } = useDecisions();
  const round = currentRound || 1;
  const editable = roundStatus === 'open' && !locked;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [suppliers, setSuppliers] = useState([]);
  const [rows, setRows] = useState([]);
  const [multiSourcing, setMultiSourcing] = useState(undefined);
  const [tierVisibility, setTierVisibility] = useState(undefined);
  const [snap, setSnap] = useState(null);
  const [serverErrors, setServerErrors] = useState([]);
  const [editCat, setEditCat] = useState(null);   // category open in the edit modal
  const [catalogOpen, setCatalogOpen] = useState(false);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [supRes, srcRes] = await Promise.all([
        getSuppliers(scenarioId), getSourcing(gameId, teamId, currentRound),
      ]);
      setSuppliers(supRes.data || []);
      const decision = srcRes.data?.decision || null;
      const ms = decision?.multi_sourcing_strategy || undefined;
      const tv = decision?.tier_2_3_visibility_investment || undefined;
      const loadedRows = (srcRes.data?.allocations || []).map((a) => ({
        key: `row-${rowSeq++}`, critical_input_category: a.critical_input_category,
        supplier: a.supplier, allocation_pct: a.allocation_pct ?? 0,
        payment_terms: a.payment_terms || '', volume_commitment_units: a.volume_commitment_units ?? 0,
      }));
      setMultiSourcing(ms); setTierVisibility(tv); setRows(loadedRows);
      setSnap(canonical(ms, tv, loadedRows));
    } catch { message.error(t('sc.sourcing.load_error')); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  const categories = useMemo(() => {
    const set = new Set();
    suppliers.forEach((s) => (s.specialization || []).forEach((sp) => set.add(sp)));
    rows.forEach((r) => r.critical_input_category && set.add(r.critical_input_category));
    return Array.from(set).sort();
  }, [suppliers, rows]);

  const suppliersForCategory = useCallback(
    (cat) => suppliers.filter((s) => (s.specialization || []).includes(cat)), [suppliers]);
  const catRows = useCallback((cat) => rows.filter((r) => r.critical_input_category === cat), [rows]);
  const catTotal = useCallback((cat) => catRows(cat).reduce((s, r) => s + (Number(r.allocation_pct) || 0), 0), [catRows]);
  const supplierName = (id) => suppliers.find((s) => s.id === id)?.name;

  const updateRow = (key, patch) => setRows((p) => p.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const removeRow = (key) => setRows((p) => p.filter((r) => r.key !== key));
  const addRow = (cat) => setRows((p) => [...p, newRow(cat)]);

  const validate = () => {
    const errs = [];
    new Set(rows.map((r) => r.critical_input_category)).forEach((cat) => {
      const cr = rows.filter((r) => r.critical_input_category === cat);
      if (cr.some((r) => !r.supplier)) errs.push(`${prettyCategory(cat)}: every row needs a supplier.`);
      const total = cr.reduce((s, r) => s + (Number(r.allocation_pct) || 0), 0);
      if (total !== 100) errs.push(`${prettyCategory(cat)}: split must total 100% (now ${total}%).`);
    });
    return errs;
  };

  // Returns true on success. Persists strategy + all allocations, then reloads.
  const handleSave = async () => {
    setServerErrors([]);
    const errs = validate();
    if (errs.length) { errs.forEach((e) => message.error(e)); setServerErrors(errs); return false; }

    const payload = {
      allocations: rows.map((r) => {
        const o = { critical_input_category: r.critical_input_category, supplier: r.supplier,
          allocation_pct: Number(r.allocation_pct) || 0 };
        if (round >= UNLOCK.payment_terms && r.payment_terms) o.payment_terms = r.payment_terms;
        if (round >= UNLOCK.volume_commitments && r.volume_commitment_units) o.volume_commitment_units = Number(r.volume_commitment_units) || 0;
        return o;
      }),
    };
    if (round >= UNLOCK.multi_sourcing_strategy && multiSourcing) payload.multi_sourcing_strategy = multiSourcing;
    if (round >= UNLOCK.tier_2_3_visibility_investment && tierVisibility) payload.tier_2_3_visibility_investment = tierVisibility;

    setSaving(true);
    try {
      await saveSourcing(gameId, teamId, currentRound, payload);
      message.success(t('sc.sourcing.saved_toast'));
      await load();
      return true;
    } catch (err) {
      if (err.response?.status === 400) { setServerErrors(flattenErrors(err.response.data)); message.error('The server rejected this. See the notes above.'); }
      else if (err.response?.status === 403) message.error("This round isn't open for changes.");
      else message.error('Save failed. Please try again.');
      return false;
    } finally { setSaving(false); }
  };

  const saveAndCloseModal = async () => { const ok = await handleSave(); if (ok) setEditCat(null); };

  if (loading) return <LoadingSpinner />;

  const dirty = snap !== null && canonical(multiSourcing, tierVisibility, rows) !== snap;
  const st = pageState({ locked, editable, dirty });

  // ── Critical-inputs summary table ──
  const summary = categories.map((cat) => {
    const cr = catRows(cat); const total = catTotal(cat);
    return { cat, count: cr.length, total,
      names: cr.map((r) => supplierName(r.supplier) || '—').filter(Boolean) };
  });
  const summaryColumns = [
    { title: 'Critical input', dataIndex: 'cat', render: (v) => <Text strong>{prettyCategory(v)}</Text> },
    { title: 'Suppliers used', key: 'sup', render: (_, r) => (r.count === 0
      ? <Text type="secondary">— none —</Text>
      : <Space wrap size={4}>{r.names.map((n, i) => <Tag key={i}>{n}</Tag>)}</Space>) },
    { title: 'Split', dataIndex: 'total', width: 120, render: (v, r) => (r.count === 0
      ? <Tag>not set</Tag>
      : <Tag color={v === 100 ? 'green' : 'red'}>{v}% {v !== 100 && '⚠'}</Tag>) },
    { title: '', key: 'edit', width: 90, render: (_, r) => (
      <Button size="small" icon={<EditOutlined />} disabled={!editable} onClick={() => setEditCat(r.cat)}>
        {r.count ? 'Edit' : 'Set up'}
      </Button>) },
  ];

  // ── Edit modal for one category ──
  const editRows = editCat ? catRows(editCat) : [];
  const editOptions = editCat ? suppliersForCategory(editCat).map((s) => ({ value: s.id, label: `${s.name} (${s.country})` })) : [];
  const editTotal = editCat ? catTotal(editCat) : 0;
  const canAddMore = editable && (round >= UNLOCK.multiSupplier || editRows.length < 1);
  const editColumns = [
    { title: 'Supplier', key: 's', render: (_, r) => (
      <Select style={{ width: 260 }} placeholder="Choose a supplier" value={r.supplier}
        disabled={!editable} options={editOptions} onChange={(v) => updateRow(r.key, { supplier: v })} showSearch optionFilterProp="label" />) },
    { title: 'Share %', key: 'p', width: 110, render: (_, r) => (
      <InputNumber min={0} max={100} value={r.allocation_pct} disabled={!editable}
        onChange={(v) => updateRow(r.key, { allocation_pct: v ?? 0 })} />) },
    { title: <>Payment {round < UNLOCK.payment_terms && lockTag(UNLOCK.payment_terms)}</>, key: 'pt', width: 180, render: (_, r) => (
      <Input style={{ width: 150 }} placeholder="e.g. letter_of_credit" value={r.payment_terms}
        disabled={!editable || round < UNLOCK.payment_terms} onChange={(e) => updateRow(r.key, { payment_terms: e.target.value })} />) },
    { title: <>Volume {round < UNLOCK.volume_commitments && lockTag(UNLOCK.volume_commitments)}</>, key: 'v', width: 130, render: (_, r) => (
      <InputNumber min={0} value={r.volume_commitment_units} disabled={!editable || round < UNLOCK.volume_commitments}
        onChange={(v) => updateRow(r.key, { volume_commitment_units: v ?? 0 })} />) },
    { title: '', key: 'x', width: 40, render: (_, r) => (
      <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => removeRow(r.key)} />) },
  ];

  return (
    <div style={{ maxWidth: 1000, width: '100%' }}>
      <PageHeader
        title={t('sc.sourcing.title')}
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>{t('sc.common.round')} {round} · {t('sc.sourcing.subtitle')}</Text>}
        status={locked ? 'locked' : 'draft'}
        actions={<Space>
          <StateBadge state={st} />
          <Button icon={<ShopOutlined />} onClick={() => setCatalogOpen(true)}>Browse suppliers</Button>
          <Button icon={<ReloadOutlined />} onClick={load} disabled={saving}>Reload</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!editable} onClick={handleSave}>Save</Button>
        </Space>} />

      {!editable && <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message={locked ? t('sc.common.locked_notice') : t('sc.common.readonly_notice')} />}
      {serverErrors.length > 0 && <Alert type="error" showIcon closable style={{ marginBottom: 16 }}
        onClose={() => setServerErrors([])} message={t('sc.common.fix_these')}
        description={<ul style={{ margin: 0, paddingLeft: 18 }}>{serverErrors.map((e, i) => <li key={i}>{e}</li>)}</ul>} />}

      <PanelCard headerColor="neutral" title={t('sc.sourcing.approach')} style={{ marginBottom: 16 }}>
        <Space size="large" wrap>
          <div>
            <div style={{ marginBottom: 4 }}><Text strong>{t('sc.sourcing.multi_strategy')}</Text>{round < UNLOCK.multi_sourcing_strategy && lockTag(UNLOCK.multi_sourcing_strategy)}</div>
            <Select style={{ width: 240 }} placeholder="Choose an approach" allowClear value={multiSourcing}
              options={MULTI_SOURCING_OPTIONS} disabled={!editable || round < UNLOCK.multi_sourcing_strategy} onChange={setMultiSourcing} />
          </div>
          <div>
            <div style={{ marginBottom: 4 }}><Text strong>{t('sc.sourcing.visibility')}</Text>{round < UNLOCK.tier_2_3_visibility_investment && lockTag(UNLOCK.tier_2_3_visibility_investment)}</div>
            <Select style={{ width: 240 }} placeholder="Choose a level" allowClear value={tierVisibility}
              options={TIER_VISIBILITY_OPTIONS} disabled={!editable || round < UNLOCK.tier_2_3_visibility_investment} onChange={setTierVisibility} />
          </div>
        </Space>
      </PanelCard>

      <PanelCard headerColor="decision" title={t('sc.sourcing.critical_inputs')} style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>{t('sc.sourcing.critical_inputs_help')}</Paragraph>
        {categories.length === 0
          ? <Empty description="No supplier categories in this scenario" />
          : <Table rowKey="cat" size="small" pagination={false} columns={summaryColumns} dataSource={summary} />}
      </PanelCard>

      {/* Per-category edit modal — Save persists everything, closes, and refreshes */}
      <Modal
        open={!!editCat}
        title={editCat ? `Suppliers for ${prettyCategory(editCat)}` : ''}
        width={820}
        onCancel={() => setEditCat(null)}
        footer={[
          <Tag key="t" color={editTotal === 100 ? 'green' : (editTotal === 0 ? 'default' : 'red')} style={{ marginRight: 'auto' }}>{editTotal}% allocated</Tag>,
          <Button key="c" onClick={() => setEditCat(null)}>Close</Button>,
          <Button key="s" type="primary" loading={saving} disabled={!editable} onClick={saveAndCloseModal}>Save &amp; close</Button>,
        ]}
        styles={{ footer: { display: 'flex', alignItems: 'center', gap: 8 } }}
      >
        {editRows.length === 0
          ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No suppliers chosen yet" />
          : <Table rowKey="key" size="small" pagination={false} columns={editColumns} dataSource={editRows} />}
        <Tooltip title={!canAddMore && round < UNLOCK.multiSupplier ? `Using more than one supplier unlocks in round ${UNLOCK.multiSupplier}` : ''}>
          <Button icon={<PlusOutlined />} onClick={() => addRow(editCat)} disabled={!canAddMore} style={{ marginTop: 12 }}>Add supplier</Button>
        </Tooltip>
      </Modal>

      {/* Supplier catalog modal */}
      <Modal open={catalogOpen} title={t('sc.sourcing.supplier_catalog')} width={960} footer={<Button onClick={() => setCatalogOpen(false)}>Close</Button>} onCancel={() => setCatalogOpen(false)}>
        <Table rowKey="id" size="small" pagination={{ pageSize: 10 }} dataSource={suppliers} scroll={{ x: true }}
          columns={[
            { title: 'Supplier', dataIndex: 'name', render: (v, s) => <><Text strong>{v}</Text> <Tag>{s.country}</Tag></> },
            { title: 'Makes', dataIndex: 'specialization', render: (a) => (a || []).map((s) => <Tag key={s}>{prettyCategory(s)}</Tag>) },
            { title: 'Unit price', dataIndex: 'base_unit_price_usd', render: (v) => `$${v}` },
            { title: 'Quality', dataIndex: 'quality_rating' },
            { title: 'Reliability', dataIndex: 'reliability_rating' },
            { title: 'Lead time (days)', dataIndex: 'lead_time_days_baseline' },
          ]} />
      </Modal>
    </div>
  );
};

export default SourcingPage;
