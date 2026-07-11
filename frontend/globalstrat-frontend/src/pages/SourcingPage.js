import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table, Select, InputNumber, Input, Button, Alert, message, Tag, Tooltip,
  Space, Typography, Empty, Divider,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, LockOutlined, SaveOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getSuppliers, getSourcing, saveSourcing } from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';
import { StateBadge, pageState } from '../components/sc/scState';

const canonical = (ms, tv, rs) => JSON.stringify({
  ms: ms || null, tv: tv || null,
  rows: (rs || []).map((r) => ({ c: r.critical_input_category, s: r.supplier,
    p: r.allocation_pct, pt: r.payment_terms, v: r.volume_commitment_units })),
});

const { Text } = Typography;

// CC-2 §8 baseline unlock schedule (server is authoritative and may apply
// per-class overrides; this drives the client-side disabled/explained state).
const UNLOCK = {
  multiSupplier: 3,
  multi_sourcing_strategy: 3,
  payment_terms: 4,
  tier_2_3_visibility_investment: 5,
  volume_commitments: 5,
};

// CC-2 enumerations (authoritative option sets).
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

const prettyCategory = (c) =>
  (c || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

// Flatten a DRF error body ({field: [...], non_field_errors: [...], nested})
// into a flat list of human-readable strings for display.
const flattenErrors = (data) => {
  const out = [];
  const walk = (val, prefix) => {
    if (val == null) return;
    if (typeof val === 'string') { out.push(prefix ? `${prefix}: ${val}` : val); return; }
    if (Array.isArray(val)) { val.forEach((v) => walk(v, prefix)); return; }
    if (typeof val === 'object') {
      Object.entries(val).forEach(([k, v]) => {
        const label = k === 'non_field_errors' ? '' : k;
        walk(v, prefix ? `${prefix}.${label}` : label);
      });
    }
  };
  walk(data, '');
  return out.length ? out : ['Request failed. Please review your inputs.'];
};

let rowSeq = 1;
const newRow = (category) => ({
  key: `row-${rowSeq++}`,
  critical_input_category: category,
  supplier: null,
  allocation_pct: 0,
  payment_terms: '',
  volume_commitment_units: 0,
});

const SourcingPage = () => {
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

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [supRes, srcRes] = await Promise.all([
        getSuppliers(scenarioId),
        getSourcing(gameId, teamId, currentRound),
      ]);
      setSuppliers(supRes.data || []);
      const decision = srcRes.data?.decision || null;
      const allocations = srcRes.data?.allocations || [];
      const ms = decision?.multi_sourcing_strategy || undefined;
      const tv = decision?.tier_2_3_visibility_investment || undefined;
      const loadedRows = allocations.map((a) => ({
        key: `row-${rowSeq++}`,
        critical_input_category: a.critical_input_category,
        supplier: a.supplier,
        allocation_pct: a.allocation_pct ?? 0,
        payment_terms: a.payment_terms || '',
        volume_commitment_units: a.volume_commitment_units ?? 0,
      }));
      setMultiSourcing(ms);
      setTierVisibility(tv);
      setRows(loadedRows);
      setSnap(canonical(ms, tv, loadedRows));
    } catch (err) {
      message.error('Unable to load sourcing data.');
    } finally {
      setLoading(false);
    }
  }, [gameId, teamId, scenarioId, currentRound]);

  useEffect(() => { load(); }, [load]);

  // Critical-input categories = distinct supplier specializations in scenario,
  // plus any category already present on an existing allocation.
  const categories = useMemo(() => {
    const set = new Set();
    suppliers.forEach((s) => (s.specialization || []).forEach((sp) => set.add(sp)));
    rows.forEach((r) => r.critical_input_category && set.add(r.critical_input_category));
    return Array.from(set).sort();
  }, [suppliers, rows]);

  const suppliersForCategory = useCallback(
    (cat) => suppliers.filter((s) => (s.specialization || []).includes(cat)),
    [suppliers],
  );

  const categoryTotal = useCallback(
    (cat) => rows.filter((r) => r.critical_input_category === cat)
      .reduce((sum, r) => sum + (Number(r.allocation_pct) || 0), 0),
    [rows],
  );

  const updateRow = (key, patch) =>
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const removeRow = (key) => setRows((prev) => prev.filter((r) => r.key !== key));
  const addRow = (cat) => setRows((prev) => [...prev, newRow(cat)]);

  // Client-side validation: every category that has allocations must sum to 100,
  // and every allocation row must name a supplier.
  const validate = () => {
    const errs = [];
    const cats = new Set(rows.map((r) => r.critical_input_category));
    cats.forEach((cat) => {
      const catRows = rows.filter((r) => r.critical_input_category === cat);
      if (catRows.some((r) => !r.supplier)) {
        errs.push(`${prettyCategory(cat)}: every allocation must select a supplier.`);
      }
      const total = catRows.reduce((s, r) => s + (Number(r.allocation_pct) || 0), 0);
      if (total !== 100) {
        errs.push(`${prettyCategory(cat)}: allocations must sum to 100% (currently ${total}%).`);
      }
    });
    return errs;
  };

  const handleSave = async () => {
    setServerErrors([]);
    const errs = validate();
    if (errs.length) { errs.forEach((e) => message.error(e)); setServerErrors(errs); return; }

    const payload = {
      allocations: rows.map((r) => {
        const o = {
          critical_input_category: r.critical_input_category,
          supplier: r.supplier,
          allocation_pct: Number(r.allocation_pct) || 0,
        };
        if (round >= UNLOCK.payment_terms && r.payment_terms) o.payment_terms = r.payment_terms;
        if (round >= UNLOCK.volume_commitments && r.volume_commitment_units) {
          o.volume_commitment_units = Number(r.volume_commitment_units) || 0;
        }
        return o;
      }),
    };
    if (round >= UNLOCK.multi_sourcing_strategy && multiSourcing) {
      payload.multi_sourcing_strategy = multiSourcing;
    }
    if (round >= UNLOCK.tier_2_3_visibility_investment && tierVisibility) {
      payload.tier_2_3_visibility_investment = tierVisibility;
    }

    setSaving(true);
    try {
      await saveSourcing(gameId, teamId, currentRound, payload);
      message.success('Sourcing decision saved.');
      await load();
    } catch (err) {
      if (err.response?.status === 400) {
        const list = flattenErrors(err.response.data);
        setServerErrors(list);
        message.error('The server rejected this submission.');
      } else if (err.response?.status === 403) {
        message.error('This round is not open for submissions.');
      } else {
        message.error('Save failed. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  const dirty = snap !== null && canonical(multiSourcing, tierVisibility, rows) !== snap;
  const st = pageState({ locked, editable, dirty });

  const lockTag = (unlockRound) => (
    <Tooltip title={`Unlocks at round ${unlockRound}`}>
      <Tag icon={<LockOutlined />} color="default" style={{ marginLeft: 8 }}>
        Round {unlockRound}
      </Tag>
    </Tooltip>
  );

  const supplierColumns = [
    { title: 'Supplier', dataIndex: 'name', key: 'name',
      render: (v, s) => <><Text strong>{v}</Text> <Tag>{s.country}</Tag></> },
    { title: 'Specialization', dataIndex: 'specialization', key: 'spec',
      render: (arr) => (arr || []).map((s) => <Tag key={s}>{prettyCategory(s)}</Tag>) },
    { title: 'Unit price', dataIndex: 'base_unit_price_usd', key: 'price',
      render: (v) => `$${v}` },
    { title: 'Quality', dataIndex: 'quality_rating', key: 'quality' },
    { title: 'Reliability', dataIndex: 'reliability_rating', key: 'rel' },
    { title: 'Lead time (d)', dataIndex: 'lead_time_days_baseline', key: 'lead' },
  ];

  const allocationTable = (cat) => {
    const catRows = rows.filter((r) => r.critical_input_category === cat);
    const total = categoryTotal(cat);
    const options = suppliersForCategory(cat).map((s) => ({ value: s.id, label: `${s.name} (${s.country})` }));
    const canAddMore = editable && (round >= UNLOCK.multiSupplier || catRows.length < 1);
    const columns = [
      { title: 'Supplier', key: 'supplier', width: 260,
        render: (_, r) => (
          <Select
            style={{ width: 240 }} placeholder="Select supplier"
            value={r.supplier} disabled={!editable} options={options}
            onChange={(v) => updateRow(r.key, { supplier: v })}
          />
        ) },
      { title: 'Allocation %', key: 'pct', width: 130,
        render: (_, r) => (
          <InputNumber
            min={0} max={100} value={r.allocation_pct} disabled={!editable}
            onChange={(v) => updateRow(r.key, { allocation_pct: v ?? 0 })}
          />
        ) },
      { title: <>Payment terms {round < UNLOCK.payment_terms && lockTag(UNLOCK.payment_terms)}</>,
        key: 'pay', width: 200,
        render: (_, r) => (
          <Input
            style={{ width: 170 }} placeholder="e.g. letter_of_credit"
            value={r.payment_terms}
            disabled={!editable || round < UNLOCK.payment_terms}
            onChange={(e) => updateRow(r.key, { payment_terms: e.target.value })}
          />
        ) },
      { title: <>Volume commit {round < UNLOCK.volume_commitments && lockTag(UNLOCK.volume_commitments)}</>,
        key: 'vol', width: 160,
        render: (_, r) => (
          <InputNumber
            min={0} value={r.volume_commitment_units}
            disabled={!editable || round < UNLOCK.volume_commitments}
            onChange={(v) => updateRow(r.key, { volume_commitment_units: v ?? 0 })}
          />
        ) },
      { title: '', key: 'actions', width: 48,
        render: (_, r) => (
          <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable}
            onClick={() => removeRow(r.key)} />
        ) },
    ];
    return (
      <PanelCard
        key={cat}
        headerColor={total === 100 ? 'strategic' : 'decision'}
        title={
          <Space>
            {prettyCategory(cat)}
            <Tag color={total === 100 ? 'green' : (total === 0 ? 'default' : 'red')}>
              {total}% allocated
            </Tag>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        {catRows.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No suppliers allocated" />
        ) : (
          <Table
            rowKey="key" size="small" pagination={false}
            columns={columns} dataSource={catRows}
          />
        )}
        <Tooltip title={!canAddMore && round < UNLOCK.multiSupplier
          ? `Multi-supplier allocation unlocks at round ${UNLOCK.multiSupplier}` : ''}>
          <Button
            icon={<PlusOutlined />} onClick={() => addRow(cat)} disabled={!canAddMore}
            style={{ marginTop: 12 }}
          >
            Add supplier
          </Button>
        </Tooltip>
      </PanelCard>
    );
  };

  return (
    <div style={{ maxWidth: 1100, width: '100%' }}>
      <PageHeader
        title="Sourcing & Suppliers"
        subtitle={
          <Text type="secondary" style={{ fontSize: 12 }}>
            Round {round} &middot; Allocate critical inputs across suppliers and set your sourcing strategy.
          </Text>
        }
        status={locked ? 'locked' : 'draft'}
        actions={
          <Space>
            <StateBadge state={st} />
            <Button icon={<ReloadOutlined />} onClick={load} disabled={saving}>Reload</Button>
            <Button type="primary" icon={<SaveOutlined />} loading={saving}
              disabled={!editable} onClick={handleSave}>
              Save
            </Button>
          </Space>
        }
      />

      {!editable && (
        <Alert
          type="info" showIcon style={{ marginBottom: 16 }}
          message={locked ? 'Decisions are locked for this round.'
            : 'This round is not open for submissions — the page is read-only.'}
        />
      )}

      {serverErrors.length > 0 && (
        <Alert
          type="error" showIcon closable style={{ marginBottom: 16 }}
          onClose={() => setServerErrors([])}
          message="Submission errors"
          description={<ul style={{ margin: 0, paddingLeft: 18 }}>
            {serverErrors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>}
        />
      )}

      <PanelCard headerColor="neutral" title="Sourcing Strategy" style={{ marginBottom: 16 }}>
        <Space size="large" wrap>
          <div>
            <div style={{ marginBottom: 4 }}>
              <Text strong>Multi-sourcing strategy</Text>
              {round < UNLOCK.multi_sourcing_strategy && lockTag(UNLOCK.multi_sourcing_strategy)}
            </div>
            <Select
              style={{ width: 240 }} placeholder="Select strategy" allowClear
              value={multiSourcing} options={MULTI_SOURCING_OPTIONS}
              disabled={!editable || round < UNLOCK.multi_sourcing_strategy}
              onChange={setMultiSourcing}
            />
          </div>
          <div>
            <div style={{ marginBottom: 4 }}>
              <Text strong>Tier-2/3 visibility investment</Text>
              {round < UNLOCK.tier_2_3_visibility_investment && lockTag(UNLOCK.tier_2_3_visibility_investment)}
            </div>
            <Select
              style={{ width: 240 }} placeholder="Select level" allowClear
              value={tierVisibility} options={TIER_VISIBILITY_OPTIONS}
              disabled={!editable || round < UNLOCK.tier_2_3_visibility_investment}
              onChange={setTierVisibility}
            />
          </div>
        </Space>
      </PanelCard>

      <PanelCard headerColor="strategic" title="Supplier Options" style={{ marginBottom: 16 }}>
        <Table
          rowKey="id" size="small" pagination={false}
          columns={supplierColumns} dataSource={suppliers}
          scroll={{ x: true }}
        />
      </PanelCard>

      <Divider orientation="left">Allocations by Critical Input</Divider>
      {categories.length === 0
        ? <Empty description="No supplier categories in this scenario" />
        : categories.map((cat) => allocationTable(cat))}
    </div>
  );
};

export default SourcingPage;
