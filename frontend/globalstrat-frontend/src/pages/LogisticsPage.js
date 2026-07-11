import React, { useState, useEffect, useCallback } from 'react';
import {
  Table, Select, InputNumber, Button, Alert, message, Tag, Tooltip, Space,
  Typography, Empty, Divider,
} from 'antd';
import { LockOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getLanes, getMarkets, getLogistics, saveLogistics } from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';
import { StateBadge, pageState } from '../components/sc/scState';

const canonical = (mix, inco, customs) => JSON.stringify({ mix, inco, customs });

const { Text } = Typography;

const UNLOCK = {
  modal_mix: 3, incoterms: 4, insurance_coverage_pct: 4,
  customs_classification: 5, reverse_logistics: 5, volume_commitment_teu: 5,
};
const INCOTERMS = ['EXW', 'FCA', 'FOB', 'CFR', 'CIF', 'CPT', 'CIP', 'DAP', 'DPU', 'DDP'];
const CLASSIFICATIONS = [
  { value: 'processing_trade', label: 'Processing trade' },
  { value: 'general_trade', label: 'General trade' },
  { value: 'bonded_logistics', label: 'Bonded logistics' },
];
const MODES = ['sea', 'air', 'rail', 'road'];

const modeAvailable = (lane, mode) => {
  const e = lane.modes ? lane.modes[mode] : null;
  return !!e && e.available !== false;
};

const flattenErrors = (data) => {
  const out = [];
  const walk = (v, prefix) => {
    if (v == null) return;
    if (typeof v === 'string') { out.push(prefix ? `${prefix}: ${v}` : v); return; }
    if (Array.isArray(v)) { v.forEach((x) => walk(x, prefix)); return; }
    if (typeof v === 'object') {
      Object.entries(v).forEach(([k, val]) => {
        const label = k === 'non_field_errors' ? '' : k;
        walk(val, prefix ? `${prefix}.${label}` : label);
      });
    }
  };
  walk(data, '');
  return out.length ? out : ['Request failed.'];
};

const lockTag = (r) => (
  <Tooltip title={`Unlocks at round ${r}`}>
    <Tag icon={<LockOutlined />} style={{ marginLeft: 6 }}>Round {r}</Tag>
  </Tooltip>
);

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

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [laneRes, mktRes, logRes] = await Promise.all([
        getLanes(scenarioId), getMarkets(scenarioId),
        getLogistics(gameId, teamId, currentRound),
      ]);
      setLanes(laneRes.data || []);
      setMarkets(mktRes.data || []);
      const m = {};
      (logRes.data?.logistics || []).forEach((l) => {
        m[l.lane] = {
          sea: l.mode_sea_pct ?? 0, air: l.mode_air_pct ?? 0,
          rail: l.mode_rail_pct ?? 0, road: l.mode_road_pct ?? 0,
          volume_commitment_teu: l.volume_commitment_teu ?? null,
        };
      });
      setMix(m);
      const ic = {};
      (logRes.data?.incoterms || []).forEach((x) => {
        ic[x.destination_market] = { incoterms: x.incoterms, insurance_coverage_pct: x.insurance_coverage_pct };
      });
      setInco(ic);
      const cu = {};
      (logRes.data?.customs || []).forEach((x) => {
        cu[x.destination_market] = {
          classification: x.classification,
          reverse_logistics_capacity_pct: x.reverse_logistics_capacity_pct,
          reverse_logistics_hub_market: x.reverse_logistics_hub_market,
        };
      });
      setCustoms(cu);
      setSnap(canonical(m, ic, cu));
    } catch {
      message.error('Unable to load logistics data.');
    } finally {
      setLoading(false);
    }
  }, [gameId, teamId, scenarioId, currentRound]);

  useEffect(() => { load(); }, [load]);

  const laneMix = (laneId) => mix[laneId] || { sea: 0, air: 0, rail: 0, road: 0, volume_commitment_teu: null };
  const setLaneMode = (laneId, mode, val) =>
    setMix((prev) => ({ ...prev, [laneId]: { ...laneMix(laneId), [mode]: val ?? 0 } }));
  const modeSum = (laneId) => { const x = laneMix(laneId); return x.sea + x.air + x.rail + x.road; };

  const validate = () => {
    const errs = [];
    lanes.forEach((ln) => {
      const s = modeSum(ln.id);
      if (s > 0 && s !== 100) errs.push(`${ln.lane_id}: modal mix must sum to 100 (currently ${s}).`);
    });
    return errs;
  };

  const handleSave = async () => {
    setServerErrors([]);
    const errs = validate();
    if (errs.length) { errs.forEach((e) => message.error(e)); setServerErrors(errs); return; }

    const logistics = lanes.filter((ln) => modeSum(ln.id) > 0).map((ln) => {
      const x = laneMix(ln.id);
      const o = { lane: ln.id, mode_sea_pct: x.sea, mode_air_pct: x.air, mode_rail_pct: x.rail, mode_road_pct: x.road };
      if (round >= UNLOCK.volume_commitment_teu && x.volume_commitment_teu != null) o.volume_commitment_teu = x.volume_commitment_teu;
      return o;
    });
    const incoterms = round >= UNLOCK.incoterms
      ? Object.entries(inco).filter(([, v]) => v.incoterms).map(([mid, v]) => ({
        destination_market: Number(mid), incoterms: v.incoterms,
        insurance_coverage_pct: v.insurance_coverage_pct ?? 110,
      })) : [];
    const customsList = round >= UNLOCK.customs_classification
      ? Object.entries(customs).filter(([, v]) => v.classification).map(([mid, v]) => ({
        destination_market: Number(mid), classification: v.classification,
        reverse_logistics_capacity_pct: v.reverse_logistics_capacity_pct ?? 0,
        reverse_logistics_hub_market: v.reverse_logistics_hub_market ?? null,
      })) : [];

    setSaving(true);
    try {
      await saveLogistics(gameId, teamId, currentRound, { logistics, incoterms, customs: customsList });
      message.success('Logistics decision saved.');
      await load();
    } catch (err) {
      if (err.response?.status === 400) { setServerErrors(flattenErrors(err.response.data)); message.error('The server rejected this submission.'); }
      else if (err.response?.status === 403) message.error('This round is not open for submissions.');
      else message.error('Save failed.');
    } finally { setSaving(false); }
  };

  if (loading) return <LoadingSpinner />;

  const dirty = snap !== null && canonical(mix, inco, customs) !== snap;
  const st = pageState({ locked, editable, dirty });

  const modeCol = (mode) => ({
    title: mode.toUpperCase(), key: mode, width: 90,
    render: (_, ln) => {
      const avail = modeAvailable(ln, mode);
      return (
        <Tooltip title={!avail ? 'Mode not available on this lane' : ''}>
          <InputNumber
            min={0} max={100} value={laneMix(ln.id)[mode]}
            disabled={!editable || !avail || round < UNLOCK.modal_mix}
            onChange={(v) => setLaneMode(ln.id, mode, v)}
          />
        </Tooltip>
      );
    },
  });

  const laneColumns = [
    { title: 'Lane', dataIndex: 'lane_id', key: 'lane',
      render: (v, ln) => <><Text strong>{v}</Text><br /><Text type="secondary" style={{ fontSize: 11 }}>{ln.origin_country}→{ln.destination_country} · {ln.zone}</Text></> },
    ...MODES.map(modeCol),
    { title: 'Sum', key: 'sum', width: 70,
      render: (_, ln) => { const s = modeSum(ln.id); return <Tag color={s === 0 ? 'default' : (s === 100 ? 'green' : 'red')}>{s}</Tag>; } },
    { title: <>Volume TEU {round < UNLOCK.volume_commitment_teu && lockTag(UNLOCK.volume_commitment_teu)}</>, key: 'vol', width: 140,
      render: (_, ln) => (
        <InputNumber min={0} value={laneMix(ln.id).volume_commitment_teu}
          disabled={!editable || round < UNLOCK.volume_commitment_teu}
          onChange={(v) => setMix((prev) => ({ ...prev, [ln.id]: { ...laneMix(ln.id), volume_commitment_teu: v } }))} />
      ) },
  ];

  return (
    <div style={{ maxWidth: 1150, width: '100%' }}>
      <PageHeader
        title="Logistics & Distribution"
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>Round {round} · Set modal mix per lane, Incoterms and customs per market.</Text>}
        status={locked ? 'locked' : 'draft'}
        actions={<Space>
          <StateBadge state={st} />
          <Button icon={<ReloadOutlined />} onClick={load} disabled={saving}>Reload</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!editable} onClick={handleSave}>Save</Button>
        </Space>}
      />

      {!editable && <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message={locked ? 'Decisions are locked for this round.' : 'This round is not open for submissions — read-only.'} />}
      {serverErrors.length > 0 && <Alert type="error" showIcon closable style={{ marginBottom: 16 }}
        onClose={() => setServerErrors([])} message="Submission errors"
        description={<ul style={{ margin: 0, paddingLeft: 18 }}>{serverErrors.map((e, i) => <li key={i}>{e}</li>)}</ul>} />}

      <PanelCard headerColor="decision"
        title={<Space>Modal Mix by Lane {round < UNLOCK.modal_mix && lockTag(UNLOCK.modal_mix)}</Space>}
        style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>Each lane you use must have modes summing to 100%. Unavailable modes are disabled.</Text>
        <Table rowKey="id" size="small" pagination={false} columns={laneColumns} dataSource={lanes}
          scroll={{ x: true }} style={{ marginTop: 8 }} />
      </PanelCard>

      <Divider orientation="left">Incoterms & Insurance by Market</Divider>
      <PanelCard headerColor="strategic"
        title={<Space>Incoterms {round < UNLOCK.incoterms && lockTag(UNLOCK.incoterms)}</Space>} style={{ marginBottom: 16 }}>
        {markets.length === 0 ? <Empty description="No markets" /> : (
          <Table rowKey="id" size="small" pagination={false} dataSource={markets}
            columns={[
              { title: 'Market', key: 'm', render: (_, mk) => <><Text strong>{mk.name}</Text> <Tag>{mk.code}</Tag></> },
              { title: 'Incoterms', key: 'inc', render: (_, mk) => (
                <Select style={{ width: 120 }} allowClear placeholder="—"
                  value={inco[mk.id]?.incoterms} disabled={!editable || round < UNLOCK.incoterms}
                  options={INCOTERMS.map((i) => ({ value: i, label: i }))}
                  onChange={(v) => setInco((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), incoterms: v } }))} /> ) },
              { title: 'Insurance %', key: 'ins', render: (_, mk) => (
                <InputNumber min={0} max={200} value={inco[mk.id]?.insurance_coverage_pct}
                  disabled={!editable || round < UNLOCK.insurance_coverage_pct}
                  onChange={(v) => setInco((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), insurance_coverage_pct: v } }))} /> ) },
            ]} />
        )}
      </PanelCard>

      <PanelCard headerColor="neutral"
        title={<Space>Customs & Reverse Logistics {round < UNLOCK.customs_classification && lockTag(UNLOCK.customs_classification)}</Space>} style={{ marginBottom: 16 }}>
        {markets.length === 0 ? <Empty description="No markets" /> : (
          <Table rowKey="id" size="small" pagination={false} dataSource={markets}
            columns={[
              { title: 'Market', key: 'm', render: (_, mk) => <><Text strong>{mk.name}</Text> <Tag>{mk.code}</Tag></> },
              { title: 'Classification', key: 'cls', render: (_, mk) => (
                <Select style={{ width: 160 }} allowClear placeholder="—"
                  value={customs[mk.id]?.classification} disabled={!editable || round < UNLOCK.customs_classification}
                  options={CLASSIFICATIONS}
                  onChange={(v) => setCustoms((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), classification: v } }))} /> ) },
              { title: 'Reverse logistics %', key: 'rl', render: (_, mk) => (
                <InputNumber min={0} max={100} value={customs[mk.id]?.reverse_logistics_capacity_pct}
                  disabled={!editable || round < UNLOCK.reverse_logistics}
                  onChange={(v) => setCustoms((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), reverse_logistics_capacity_pct: v } }))} /> ) },
              { title: 'Hub market', key: 'hub', render: (_, mk) => (
                <Select style={{ width: 140 }} allowClear placeholder="—"
                  value={customs[mk.id]?.reverse_logistics_hub_market} disabled={!editable || round < UNLOCK.reverse_logistics}
                  options={markets.map((m2) => ({ value: m2.id, label: m2.code }))}
                  onChange={(v) => setCustoms((p) => ({ ...p, [mk.id]: { ...(p[mk.id] || {}), reverse_logistics_hub_market: v } }))} /> ) },
            ]} />
        )}
      </PanelCard>
    </div>
  );
};

export default LogisticsPage;
