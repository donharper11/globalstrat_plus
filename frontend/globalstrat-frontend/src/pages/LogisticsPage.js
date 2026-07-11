import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table, Select, InputNumber, Button, Alert, message, Tag, Tooltip, Space,
  Typography, Empty, Modal,
} from 'antd';
import {
  LockOutlined, SaveOutlined, ReloadOutlined, PlusOutlined, EditOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getLanes, getMarkets, getLogistics, saveLogistics } from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';
import { StateBadge, pageState } from '../components/sc/scState';

const { Text, Paragraph } = Typography;

const UNLOCK = { modal_mix: 3, incoterms: 4, insurance_coverage_pct: 4,
  customs_classification: 5, reverse_logistics: 5, volume_commitment_teu: 5 };
const INCOTERMS = ['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP'];
const CLASSIFICATIONS = [
  { value: 'processing_trade', label: 'Processing trade' },
  { value: 'general_trade', label: 'General trade' },
  { value: 'bonded_logistics', label: 'Bonded logistics' },
];
const MODES = ['sea', 'air', 'rail', 'road'];

const modeAvailable = (lane, mode) => { const e = lane.modes ? lane.modes[mode] : null; return !!e && e.available !== false; };
const laneLabel = (l) => `${l.origin_port} (${l.origin_country}) → ${l.destination_port} (${l.destination_country})`;

const canonical = (mix, inco, customs) => JSON.stringify({ mix, inco, customs });

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

const LogisticsPage = () => {
  const { gameId, teamId, scenarioId, currentRound, roundStatus } = useGame();
  const { locked } = useDecisions();
  const round = currentRound || 1;
  const editable = roundStatus === 'open' && !locked;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lanes, setLanes] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [mix, setMix] = useState({});        // laneId -> {sea,air,rail,road,volume_commitment_teu}
  const [inco, setInco] = useState({});      // marketId -> {incoterms, insurance_coverage_pct}
  const [customs, setCustoms] = useState({});// marketId -> {classification, reverse_logistics_capacity_pct, reverse_logistics_hub_market}
  const [serverErrors, setServerErrors] = useState([]);
  const [snap, setSnap] = useState(null);
  const [editLane, setEditLane] = useState(null); // laneId currently in the modal (null = closed)

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [laneRes, mktRes, logRes] = await Promise.all([
        getLanes(scenarioId), getMarkets(scenarioId), getLogistics(gameId, teamId, currentRound),
      ]);
      setLanes(laneRes.data || []); setMarkets(mktRes.data || []);
      const m = {};
      (logRes.data?.logistics || []).forEach((l) => { m[l.lane] = { sea: l.mode_sea_pct ?? 0, air: l.mode_air_pct ?? 0, rail: l.mode_rail_pct ?? 0, road: l.mode_road_pct ?? 0, volume_commitment_teu: l.volume_commitment_teu ?? null }; });
      setMix(m);
      const ic = {}; (logRes.data?.incoterms || []).forEach((x) => { ic[x.destination_market] = { incoterms: x.incoterms, insurance_coverage_pct: x.insurance_coverage_pct }; }); setInco(ic);
      const cu = {}; (logRes.data?.customs || []).forEach((x) => { cu[x.destination_market] = { classification: x.classification, reverse_logistics_capacity_pct: x.reverse_logistics_capacity_pct, reverse_logistics_hub_market: x.reverse_logistics_hub_market }; }); setCustoms(cu);
      setSnap(canonical(m, ic, cu));
    } catch { message.error('Unable to load your logistics.'); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  const laneById = useMemo(() => { const o = {}; lanes.forEach((l) => { o[l.id] = l; }); return o; }, [lanes]);
  const laneMix = (id) => mix[id] || { sea: 0, air: 0, rail: 0, road: 0, volume_commitment_teu: null };
  const setLaneMode = (id, mode, val) => setMix((p) => ({ ...p, [id]: { ...laneMix(id), [mode]: val ?? 0 } }));
  const modeSum = (id) => { const x = laneMix(id); return x.sea + x.air + x.rail + x.road; };
  const configuredLaneIds = Object.keys(mix).filter((id) => modeSum(id) > 0).map(Number);

  const validate = () => {
    const errs = [];
    configuredLaneIds.forEach((id) => { const s = modeSum(id); if (s !== 100) errs.push(`${laneById[id]?.lane_id || id}: shipping mix must total 100% (now ${s}%).`); });
    return errs;
  };

  const handleSave = async () => {
    setServerErrors([]);
    const errs = validate();
    if (errs.length) { errs.forEach((e) => message.error(e)); setServerErrors(errs); return false; }
    const logistics = configuredLaneIds.map((id) => {
      const x = laneMix(id);
      const o = { lane: id, mode_sea_pct: x.sea, mode_air_pct: x.air, mode_rail_pct: x.rail, mode_road_pct: x.road };
      if (round >= UNLOCK.volume_commitment_teu && x.volume_commitment_teu != null) o.volume_commitment_teu = x.volume_commitment_teu;
      return o;
    });
    const incoterms = round >= UNLOCK.incoterms ? Object.entries(inco).filter(([, v]) => v.incoterms).map(([mid, v]) => ({ destination_market: Number(mid), incoterms: v.incoterms, insurance_coverage_pct: v.insurance_coverage_pct ?? 110 })) : [];
    const customsList = round >= UNLOCK.customs_classification ? Object.entries(customs).filter(([, v]) => v.classification).map(([mid, v]) => ({ destination_market: Number(mid), classification: v.classification, reverse_logistics_capacity_pct: v.reverse_logistics_capacity_pct ?? 0, reverse_logistics_hub_market: v.reverse_logistics_hub_market ?? null })) : [];
    setSaving(true);
    try {
      await saveLogistics(gameId, teamId, currentRound, { logistics, incoterms, customs: customsList });
      message.success('Logistics saved.');
      await load();
      return true;
    } catch (err) {
      if (err.response?.status === 400) { setServerErrors(flattenErrors(err.response.data)); message.error('The server rejected this. See the notes above.'); }
      else if (err.response?.status === 403) message.error("This round isn't open for changes.");
      else message.error('Save failed.');
      return false;
    } finally { setSaving(false); }
  };
  const saveAndCloseModal = async () => { const ok = await handleSave(); if (ok) setEditLane(null); };
  const removeLane = (id) => setMix((p) => { const n = { ...p }; delete n[id]; return n; });

  if (loading) return <LoadingSpinner />;
  const dirty = snap !== null && canonical(mix, inco, customs) !== snap;
  const st = pageState({ locked, editable, dirty });

  // Configured lanes table
  const configuredRows = configuredLaneIds.map((id) => {
    const l = laneById[id]; const x = laneMix(id);
    return { id, label: l ? laneLabel(l) : `#${id}`, code: l?.lane_id,
      split: MODES.filter((m) => x[m] > 0).map((m) => `${m} ${x[m]}%`).join(' · '), sum: modeSum(id) };
  });
  const configuredColumns = [
    { title: 'Lane', key: 'l', render: (_, r) => <><Text strong>{r.label}</Text><br /><Text type="secondary" style={{ fontSize: 11 }}>{r.code}</Text></> },
    { title: 'How it ships', dataIndex: 'split' },
    { title: 'Total', dataIndex: 'sum', width: 90, render: (v) => <Tag color={v === 100 ? 'green' : 'red'}>{v}% {v !== 100 && '⚠'}</Tag> },
    { title: '', key: 'x', width: 130, render: (_, r) => (<Space>
      <Button size="small" icon={<EditOutlined />} disabled={!editable} onClick={() => setEditLane(r.id)}>Edit</Button>
      <Button size="small" type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => removeLane(r.id)} />
    </Space>) },
  ];

  // Lane picker options for the modal (exclude already-configured unless editing that one)
  const laneOptions = lanes
    .filter((l) => l.id === editLane || !configuredLaneIds.includes(l.id))
    .map((l) => ({ value: l.id, label: laneLabel(l) }));
  const el = editLane ? laneById[editLane] : null;
  const em = editLane ? laneMix(editLane) : null;
  const editSum = editLane ? modeSum(editLane) : 0;

  return (
    <div style={{ maxWidth: 1000, width: '100%' }}>
      <PageHeader
        title="Logistics"
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>Round {round} · Set how you ship on each route, and your terms and customs by market.</Text>}
        status={locked ? 'locked' : 'draft'}
        actions={<Space>
          <StateBadge state={st} />
          <Button icon={<ReloadOutlined />} onClick={load} disabled={saving}>Reload</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!editable} onClick={handleSave}>Save</Button>
        </Space>} />

      {!editable && <Alert type="info" showIcon style={{ marginBottom: 16 }} message={locked ? 'Your decisions are locked for this round.' : "This round isn't open for changes — you're viewing only."} />}
      {serverErrors.length > 0 && <Alert type="error" showIcon closable style={{ marginBottom: 16 }} onClose={() => setServerErrors([])} message="Please fix these" description={<ul style={{ margin: 0, paddingLeft: 18 }}>{serverErrors.map((e, i) => <li key={i}>{e}</li>)}</ul>} />}

      <PanelCard headerColor="decision" title={<Space>Shipping Routes {round < UNLOCK.modal_mix && lockTag(UNLOCK.modal_mix)}</Space>} style={{ marginBottom: 16 }}>
        <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 8 }} align="start">
          <Paragraph type="secondary" style={{ fontSize: 12, margin: 0, maxWidth: 620 }}>Pick a route and choose how much ships by sea, air, rail or road. Each route must total 100%.</Paragraph>
          <Button size="small" type="primary" icon={<PlusOutlined />} disabled={!editable || round < UNLOCK.modal_mix} onClick={() => setEditLane('new')}>Add route</Button>
        </Space>
        {configuredRows.length === 0
          ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No shipping routes set up yet — click “Add route”." />
          : <Table rowKey="id" size="small" pagination={false} columns={configuredColumns} dataSource={configuredRows} />}
      </PanelCard>

      <PanelCard headerColor="strategic" title={<Space>Shipping Terms by Market {round < UNLOCK.incoterms && lockTag(UNLOCK.incoterms)}</Space>} style={{ marginBottom: 16 }}>
        {markets.length === 0 ? <Empty description="No markets" /> : (
          <Table rowKey="id" size="small" pagination={false} dataSource={markets}
            columns={[
              { title: 'Market', key: 'm', render: (_, mk) => <><Text strong>{mk.name}</Text> <Tag>{mk.code}</Tag></> },
              { title: 'Incoterms', key: 'inc', render: (_, mk) => (<Select style={{ width: 120 }} allowClear placeholder="—" value={inco[mk.id]?.incoterms} disabled={!editable || round < UNLOCK.incoterms} options={INCOTERMS.map((i) => ({ value: i, label: i }))} onChange={(v) => setInco((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), incoterms: v } }))} />) },
              { title: 'Insurance %', key: 'ins', render: (_, mk) => (<InputNumber min={0} max={200} value={inco[mk.id]?.insurance_coverage_pct} disabled={!editable || round < UNLOCK.insurance_coverage_pct} onChange={(v) => setInco((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), insurance_coverage_pct: v } }))} />) },
            ]} />)}
      </PanelCard>

      <PanelCard headerColor="neutral" title={<Space>Customs &amp; Returns by Market {round < UNLOCK.customs_classification && lockTag(UNLOCK.customs_classification)}</Space>} style={{ marginBottom: 16 }}>
        {markets.length === 0 ? <Empty description="No markets" /> : (
          <Table rowKey="id" size="small" pagination={false} dataSource={markets}
            columns={[
              { title: 'Market', key: 'm', render: (_, mk) => <><Text strong>{mk.name}</Text> <Tag>{mk.code}</Tag></> },
              { title: 'Customs type', key: 'cls', render: (_, mk) => (<Select style={{ width: 160 }} allowClear placeholder="—" value={customs[mk.id]?.classification} disabled={!editable || round < UNLOCK.customs_classification} options={CLASSIFICATIONS} onChange={(v) => setCustoms((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), classification: v } }))} />) },
              { title: 'Returns capacity %', key: 'rl', render: (_, mk) => (<InputNumber min={0} max={100} value={customs[mk.id]?.reverse_logistics_capacity_pct} disabled={!editable || round < UNLOCK.reverse_logistics} onChange={(v) => setCustoms((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), reverse_logistics_capacity_pct: v } }))} />) },
              { title: 'Returns hub', key: 'hub', render: (_, mk) => (<Select style={{ width: 140 }} allowClear placeholder="—" value={customs[mk.id]?.reverse_logistics_hub_market} disabled={!editable || round < UNLOCK.reverse_logistics} options={markets.map((m2) => ({ value: m2.id, label: m2.code }))} onChange={(v) => setCustoms((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), reverse_logistics_hub_market: v } }))} />) },
            ]} />)}
      </PanelCard>

      {/* Add / edit route modal */}
      <Modal open={!!editLane} title={editLane === 'new' ? 'Add a shipping route' : 'Edit shipping route'} width={640}
        onCancel={() => setEditLane(null)}
        footer={[
          <Tag key="t" color={editSum === 100 ? 'green' : (editSum === 0 ? 'default' : 'red')} style={{ marginRight: 'auto' }}>{editSum}% of shipments</Tag>,
          <Button key="c" onClick={() => setEditLane(null)}>Close</Button>,
          <Button key="s" type="primary" loading={saving} disabled={!editable || editLane === 'new'} onClick={saveAndCloseModal}>Save &amp; close</Button>,
        ]}
        styles={{ footer: { display: 'flex', alignItems: 'center', gap: 8 } }}>
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4 }}><Text strong>Route (from → to)</Text></div>
          <Select style={{ width: '100%' }} showSearch optionFilterProp="label" placeholder="Choose a route"
            value={editLane === 'new' ? undefined : editLane} disabled={editLane !== 'new'} options={laneOptions}
            onChange={(v) => setEditLane(v)} />
        </div>
        {el && (
          <>
            <div style={{ marginBottom: 4 }}><Text strong>How does it ship?</Text> <Text type="secondary" style={{ fontSize: 12 }}>(must total 100%)</Text></div>
            <Space wrap size="large">
              {MODES.map((mode) => {
                const avail = modeAvailable(el, mode);
                return (
                  <div key={mode}>
                    <div style={{ fontSize: 12, textTransform: 'capitalize', color: avail ? undefined : '#bbb' }}>{mode}</div>
                    <Tooltip title={!avail ? 'Not available on this route' : ''}>
                      <InputNumber min={0} max={100} value={em[mode]} disabled={!editable || !avail} onChange={(v) => setLaneMode(editLane, mode, v)} />
                    </Tooltip>
                  </div>
                );
              })}
              <div>
                <div style={{ fontSize: 12 }}>Volume (TEU) {round < UNLOCK.volume_commitment_teu && lockTag(UNLOCK.volume_commitment_teu)}</div>
                <InputNumber min={0} value={em.volume_commitment_teu} disabled={!editable || round < UNLOCK.volume_commitment_teu} onChange={(v) => setMix((p) => ({ ...p, [editLane]: { ...laneMix(editLane), volume_commitment_teu: v } }))} />
              </div>
            </Space>
          </>
        )}
      </Modal>
    </div>
  );
};

export default LogisticsPage;
