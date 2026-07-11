import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table, Select, InputNumber, Button, Alert, message, Tag, Tooltip, Space,
  Typography, Empty, Divider,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, LockOutlined, SaveOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import {
  getInstruments, getMarkets, getSegments, getTradeFinance, saveTradeFinance,
} from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Text, Paragraph } = Typography;

const UNLOCK = {
  buyer_payment_instrument: 4, lc_doc_prep_investment: 4,
  sinosure_coverage: 4, fx_hedging: 5,
};
const LC_DOC_PREP = [
  { value: 'minimal', label: 'Minimal' },
  { value: 'standard', label: 'Standard' },
  { value: 'diligent', label: 'Diligent' },
];

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
let seq = 1;

const TradeFinancePage = () => {
  const { gameId, teamId, scenarioId, currentRound, roundStatus } = useGame();
  const { locked } = useDecisions();
  const round = currentRound || 1;
  const editable = roundStatus === 'open' && !locked;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [instruments, setInstruments] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [segments, setSegments] = useState([]);
  const [tfRows, setTfRows] = useState([]);      // {key, segment, market, buyer_payment_instrument, lc_doc_prep_investment}
  const [sino, setSino] = useState({});          // marketId -> coverage_pct
  const [fx, setFx] = useState({});              // currency_pair -> {hedge_ratio, tenor_days}
  const [serverErrors, setServerErrors] = useState([]);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [insRes, mktRes, segRes, tfRes] = await Promise.all([
        getInstruments(scenarioId), getMarkets(scenarioId),
        getSegments(scenarioId, 'customer'), getTradeFinance(gameId, teamId, currentRound),
      ]);
      setInstruments(insRes.data || []);
      setMarkets(mktRes.data || []);
      setSegments(segRes.data || []);
      setTfRows((tfRes.data?.trade_finance || []).map((t) => ({
        key: `tf-${seq++}`, segment: t.segment, market: t.market,
        buyer_payment_instrument: t.buyer_payment_instrument || undefined,
        lc_doc_prep_investment: t.lc_doc_prep_investment || 'standard',
      })));
      const s = {}; (tfRes.data?.sinosure || []).forEach((x) => { s[x.market] = x.coverage_pct; }); setSino(s);
      const f = {}; (tfRes.data?.fx_hedges || []).forEach((x) => { f[x.currency_pair] = { hedge_ratio: x.hedge_ratio, tenor_days: x.tenor_days }; }); setFx(f);
    } catch { message.error('Unable to load trade finance data.'); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound]);
  useEffect(() => { load(); }, [load]);

  const fxInstrument = useMemo(
    () => instruments.find((i) => (i.currency_pairs_available || []).length > 0), [instruments]);
  const currencyPairs = fxInstrument?.currency_pairs_available || [];
  const tenorOptions = fxInstrument?.tenor_options_days || [30, 60, 90, 180];
  const instrumentOptions = instruments.map((i) => ({ value: i.instrument_id, label: i.display_name || i.instrument_id }));
  const marketLabel = (id) => { const m = markets.find((x) => x.id === id); return m ? `${m.name} (${m.code})` : id; };
  const segmentOptions = segments.map((s) => ({ value: s.id, label: `${s.name} · ${marketLabel(s.market_id)}` }));

  const addTf = () => setTfRows((p) => [...p, { key: `tf-${seq++}`, segment: null, market: null, buyer_payment_instrument: undefined, lc_doc_prep_investment: 'standard' }]);
  const updTf = (key, patch) => setTfRows((p) => p.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const delTf = (key) => setTfRows((p) => p.filter((r) => r.key !== key));

  const validate = () => {
    const errs = [];
    tfRows.forEach((r, i) => {
      if (r.buyer_payment_instrument && (!r.segment || !r.market))
        errs.push(`Trade finance row ${i + 1}: choose a segment and market.`);
    });
    return errs;
  };

  const handleSave = async () => {
    setServerErrors([]);
    const errs = validate();
    if (errs.length) { errs.forEach((e) => message.error(e)); setServerErrors(errs); return; }

    const trade_finance = round >= UNLOCK.buyer_payment_instrument
      ? tfRows.filter((r) => r.segment && r.market).map((r) => ({
        segment: r.segment, market: r.market,
        buyer_payment_instrument: r.buyer_payment_instrument || '',
        lc_doc_prep_investment: r.lc_doc_prep_investment || 'standard',
      })) : [];
    const sinosure = round >= UNLOCK.sinosure_coverage
      ? Object.entries(sino).filter(([, v]) => v != null).map(([mid, v]) => ({ market: Number(mid), coverage_pct: v })) : [];
    const fx_hedges = round >= UNLOCK.fx_hedging
      ? Object.entries(fx).filter(([, v]) => v && v.hedge_ratio != null).map(([pair, v]) => ({
        currency_pair: pair, hedge_ratio: v.hedge_ratio, tenor_days: v.tenor_days || 90,
      })) : [];

    setSaving(true);
    try {
      await saveTradeFinance(gameId, teamId, currentRound, { trade_finance, sinosure, fx_hedges });
      message.success('Trade finance decision saved.');
      await load();
    } catch (err) {
      if (err.response?.status === 400) { setServerErrors(flattenErrors(err.response.data)); message.error('The server rejected this submission.'); }
      else if (err.response?.status === 403) message.error('This round is not open for submissions.');
      else message.error('Save failed.');
    } finally { setSaving(false); }
  };

  if (loading) return <LoadingSpinner />;
  const tfLocked = round < UNLOCK.buyer_payment_instrument;

  return (
    <div style={{ maxWidth: 1100, width: '100%' }}>
      <PageHeader
        title="Trade Finance & FX"
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>Round {round} · Choose how overseas buyers pay you, manage credit risk, and hedge currency exposure.</Text>}
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

      <PanelCard headerColor="strategic" title="Trade Finance Instruments" style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          As a Chinese firm selling into overseas markets, your choice of payment instrument trades off getting paid safely against how much cash your buyer must tie up. Sinosure export-credit insurance and FX forwards manage political/commercial and currency risk on cross-border sales.
        </Paragraph>
        <Table rowKey="instrument_id" size="small" pagination={false} dataSource={instruments} scroll={{ x: true }}
          columns={[
            { title: 'Instrument', dataIndex: 'display_name', key: 'n', render: (v, r) => <Text strong>{v || r.instrument_id}</Text> },
            { title: 'Seller protection', dataIndex: 'seller_protection', key: 'sp' },
            { title: 'Buyer cash need', dataIndex: 'buyer_cash_requirement', key: 'bc' },
            { title: 'Available in', dataIndex: 'available_in_markets', key: 'am', render: (a) => (a || []).map((x) => <Tag key={x}>{x}</Tag>) },
          ]} />
      </PanelCard>

      <PanelCard headerColor="decision"
        title={<Space>Buyer Payment Instruments (by segment / market) {tfLocked && lockTag(UNLOCK.buyer_payment_instrument)}</Space>} style={{ marginBottom: 16 }}>
        {tfRows.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No payment instrument choices yet" /> : (
          <Table rowKey="key" size="small" pagination={false} dataSource={tfRows}
            columns={[
              { title: 'Customer segment', key: 'seg', width: 300, render: (_, r) => (
                <Select showSearch optionFilterProp="label" style={{ width: 280 }} placeholder="Select segment"
                  value={r.segment} disabled={!editable || tfLocked} options={segmentOptions}
                  onChange={(v) => { const seg = segments.find((s) => s.id === v); updTf(r.key, { segment: v, market: seg?.market_id ?? r.market }); }} /> ) },
              { title: 'Market', key: 'mkt', width: 180, render: (_, r) => (
                <Select style={{ width: 160 }} placeholder="Market" value={r.market} disabled={!editable || tfLocked}
                  options={markets.map((m) => ({ value: m.id, label: `${m.name} (${m.code})` }))}
                  onChange={(v) => updTf(r.key, { market: v })} /> ) },
              { title: 'Instrument', key: 'ins', width: 200, render: (_, r) => (
                <Select style={{ width: 180 }} placeholder="Instrument" value={r.buyer_payment_instrument} disabled={!editable || tfLocked}
                  options={instrumentOptions} onChange={(v) => updTf(r.key, { buyer_payment_instrument: v })} /> ) },
              { title: 'LC doc prep', key: 'lc', width: 140, render: (_, r) => (
                <Select style={{ width: 120 }} value={r.lc_doc_prep_investment} disabled={!editable || tfLocked}
                  options={LC_DOC_PREP} onChange={(v) => updTf(r.key, { lc_doc_prep_investment: v })} /> ) },
              { title: '', key: 'x', width: 40, render: (_, r) => <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => delTf(r.key)} /> },
            ]} />
        )}
        <Button icon={<PlusOutlined />} onClick={addTf} disabled={!editable || tfLocked} style={{ marginTop: 12 }}>Add payment choice</Button>
      </PanelCard>

      <Divider orientation="left">Risk Management</Divider>
      <PanelCard headerColor="neutral"
        title={<Space>Sinosure Export-Credit Coverage {round < UNLOCK.sinosure_coverage && lockTag(UNLOCK.sinosure_coverage)}</Space>} style={{ marginBottom: 16 }}>
        {markets.length === 0 ? <Empty description="No markets" /> : (
          <Table rowKey="id" size="small" pagination={false} dataSource={markets}
            columns={[
              { title: 'Market', key: 'm', render: (_, mk) => <><Text strong>{mk.name}</Text> <Tag>{mk.code}</Tag></> },
              { title: 'Coverage %', key: 'cov', render: (_, mk) => (
                <InputNumber min={0} max={100} value={sino[mk.id]} disabled={!editable || round < UNLOCK.sinosure_coverage}
                  onChange={(v) => setSino((p) => ({ ...p, [mk.id]: v }))} /> ) },
            ]} />
        )}
      </PanelCard>

      <PanelCard headerColor="strategic"
        title={<Space>FX Hedging {round < UNLOCK.fx_hedging && lockTag(UNLOCK.fx_hedging)}</Space>} style={{ marginBottom: 16 }}>
        {currencyPairs.length === 0 ? <Empty description="No FX pairs in this scenario" /> : (
          <Table rowKey="pair" size="small" pagination={false}
            dataSource={currencyPairs.map((p) => ({ pair: p }))}
            columns={[
              { title: 'Currency pair', dataIndex: 'pair', key: 'p', render: (v) => <Text strong>{v}</Text> },
              { title: 'Hedge ratio %', key: 'hr', render: (_, r) => (
                <InputNumber min={0} max={100} value={fx[r.pair]?.hedge_ratio} disabled={!editable || round < UNLOCK.fx_hedging}
                  onChange={(v) => setFx((p) => ({ ...p, [r.pair]: { ...(p[r.pair] || {}), hedge_ratio: v } }))} /> ) },
              { title: 'Tenor (days)', key: 'td', render: (_, r) => (
                <Select style={{ width: 110 }} allowClear placeholder="—" value={fx[r.pair]?.tenor_days} disabled={!editable || round < UNLOCK.fx_hedging}
                  options={tenorOptions.map((t) => ({ value: t, label: `${t}` }))}
                  onChange={(v) => setFx((p) => ({ ...p, [r.pair]: { ...(p[r.pair] || {}), tenor_days: v } }))} /> ) },
            ]} />
        )}
      </PanelCard>
    </div>
  );
};

export default TradeFinancePage;
