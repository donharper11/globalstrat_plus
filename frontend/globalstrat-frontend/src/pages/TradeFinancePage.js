import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Table, Select, InputNumber, Button, Alert, message, Tag, Tooltip, Space,
  Typography, Empty, Divider,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, LockOutlined, SaveOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import {
  getInstruments, getMarkets, getSegments, getTradeFinance, saveTradeFinance,
  getHedgePositions,
} from '../api/sc';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';
import { StateBadge, pageState } from '../components/sc/scState';

const canonical = (tf, sino, fx) => JSON.stringify({
  tf: (tf || []).map((r) => ({ seg: r.segment, mkt: r.market,
    inst: r.buyer_payment_instrument, lc: r.lc_doc_prep_investment })),
  sino, fx,
});

const { Text, Paragraph } = Typography;

const UNLOCK = {
  buyer_payment_instrument: 4, lc_doc_prep_investment: 4,
  sinosure_coverage: 4, fx_hedging: 5,
};
const flattenErrors = (data, fallback) => {
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
  return out.length ? out : [fallback];
};
const lockTag = (r, t) => (
  <Tooltip title={t('sc.common.unlocks_in_round', { round: r })}>
    <Tag icon={<LockOutlined />} style={{ marginLeft: 6 }}>{t('sc.common.round')} {r}</Tag>
  </Tooltip>
);
let seq = 1;

const TradeFinancePage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, scenarioId, currentRound, roundStatus } = useGame();
  const { locked } = useDecisions();
  const round = currentRound || 1;
  const editable = roundStatus === 'open' && !locked;
  const lcDocPrep = ['minimal', 'standard', 'diligent']
    .map((value) => ({ value, label: t(`sc.trade_finance.${value}`) }));

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [instruments, setInstruments] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [segments, setSegments] = useState([]);
  const [tfRows, setTfRows] = useState([]);      // {key, segment, market, buyer_payment_instrument, lc_doc_prep_investment}
  const [sino, setSino] = useState({});          // marketId -> coverage_pct
  const [fx, setFx] = useState({});              // currency_pair -> {hedge_ratio, tenor_days}
  const [serverErrors, setServerErrors] = useState([]);
  const [snap, setSnap] = useState(null);
  const [hedgePositions, setHedgePositions] = useState([]);

  const load = useCallback(async () => {
    if (!gameId || !teamId || !scenarioId || !currentRound) { setLoading(false); return; }
    setLoading(true);
    try {
      const [insRes, mktRes, segRes, tfRes, hpRes] = await Promise.all([
        getInstruments(scenarioId), getMarkets(scenarioId),
        getSegments(scenarioId, 'customer'), getTradeFinance(gameId, teamId, currentRound),
        getHedgePositions(gameId, teamId).catch(() => ({ data: [] })),
      ]);
      setHedgePositions(hpRes.data || []);
      setInstruments(insRes.data || []);
      setMarkets(mktRes.data || []);
      setSegments(segRes.data || []);
      const loadedTf = (tfRes.data?.trade_finance || []).map((t) => ({
        key: `tf-${seq++}`, segment: t.segment, market: t.market,
        buyer_payment_instrument: t.buyer_payment_instrument || undefined,
        lc_doc_prep_investment: t.lc_doc_prep_investment || 'standard',
      }));
      setTfRows(loadedTf);
      const s = {}; (tfRes.data?.sinosure || []).forEach((x) => { s[x.market] = x.coverage_pct; }); setSino(s);
      const f = {}; (tfRes.data?.fx_hedges || []).forEach((x) => { f[x.currency_pair] = { hedge_ratio: x.hedge_ratio, tenor_days: x.tenor_days }; }); setFx(f);
      setSnap(canonical(loadedTf, s, f));
    } catch { message.error(t('sc.trade_finance.load_error')); } finally { setLoading(false); }
  }, [gameId, teamId, scenarioId, currentRound, t]);
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
        errs.push(t('sc.trade_finance.validation_row', { row: i + 1 }));
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
      message.success(t('sc.trade_finance.saved_toast'));
      await load();
    } catch (err) {
      if (err.response?.status === 400) { setServerErrors(flattenErrors(err.response.data, t('sc.common.input_error'))); message.error(t('sc.common.server_rejected')); }
      else if (err.response?.status === 403) message.error(t('sc.common.readonly_notice'));
      else message.error(t('sc.common.save_failed'));
    } finally { setSaving(false); }
  };

  if (loading) return <LoadingSpinner />;
  const tfLocked = round < UNLOCK.buyer_payment_instrument;
  const dirty = snap !== null && canonical(tfRows, sino, fx) !== snap;
  const st = pageState({ locked, editable, dirty });

  return (
    <div style={{ maxWidth: 1100, width: '100%' }}>
      <PageHeader
        title={t('sc.trade_finance.title')}
        subtitle={<Text type="secondary" style={{ fontSize: 12 }}>{t('sc.common.round')} {round} · {t('sc.trade_finance.subtitle')}</Text>}
        status={locked ? 'locked' : 'draft'}
        actions={<Space>
          <StateBadge state={st} />
          <Button icon={<ReloadOutlined />} onClick={load} disabled={saving}>{t('sc.common.reload')}</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} disabled={!editable} onClick={handleSave}>{t('sc.common.save')}</Button>
        </Space>} />

      {!editable && <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message={locked ? t('sc.common.locked_notice') : t('sc.common.readonly_notice')} />}
      {serverErrors.length > 0 && <Alert type="error" showIcon closable style={{ marginBottom: 16 }}
        onClose={() => setServerErrors([])} message={t('sc.trade_finance.submission_errors')}
        description={<ul style={{ margin: 0, paddingLeft: 18 }}>{serverErrors.map((e, i) => <li key={i}>{e}</li>)}</ul>} />}

      <PanelCard headerColor="strategic" title={t('sc.trade_finance.instruments')} style={{ marginBottom: 16 }}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          {t('sc.trade_finance.instruments_help')}
        </Paragraph>
        <Table rowKey="instrument_id" size="small" pagination={false} dataSource={instruments} scroll={{ x: true }}
          columns={[
            { title: t('sc.trade_finance.instrument'), dataIndex: 'display_name', key: 'n', render: (v, r) => <Text strong>{v || r.instrument_id}</Text> },
            { title: t('sc.trade_finance.seller_protection'), dataIndex: 'seller_protection', key: 'sp' },
            { title: t('sc.trade_finance.buyer_cash'), dataIndex: 'buyer_cash_requirement', key: 'bc' },
            { title: t('sc.trade_finance.available_in'), dataIndex: 'available_in_markets', key: 'am', render: (a) => (a || []).map((x) => <Tag key={x}>{x}</Tag>) },
          ]} />
      </PanelCard>

      <PanelCard headerColor="decision"
        title={<Space>{t('sc.trade_finance.buyer_instruments')} {tfLocked && lockTag(UNLOCK.buyer_payment_instrument, t)}</Space>} style={{ marginBottom: 16 }}>
        {tfRows.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('sc.trade_finance.no_payment_choices')} /> : (
          <Table rowKey="key" size="small" pagination={false} dataSource={tfRows}
            columns={[
              { title: t('sc.trade_finance.customer_segment'), key: 'seg', width: 300, render: (_, r) => (
                <Select showSearch optionFilterProp="label" style={{ width: 280 }} placeholder={t('sc.trade_finance.select_segment')}
                  value={r.segment} disabled={!editable || tfLocked} options={segmentOptions}
                  onChange={(v) => { const seg = segments.find((s) => s.id === v); updTf(r.key, { segment: v, market: seg?.market_id ?? r.market }); }} /> ) },
              { title: t('sc.trade_finance.market'), key: 'mkt', width: 180, render: (_, r) => (
                <Select style={{ width: 160 }} placeholder={t('sc.trade_finance.market')} value={r.market} disabled={!editable || tfLocked}
                  options={markets.map((m) => ({ value: m.id, label: `${m.name} (${m.code})` }))}
                  onChange={(v) => updTf(r.key, { market: v })} /> ) },
              { title: t('sc.trade_finance.instrument'), key: 'ins', width: 200, render: (_, r) => (
                <Select style={{ width: 180 }} placeholder={t('sc.trade_finance.instrument')} value={r.buyer_payment_instrument} disabled={!editable || tfLocked}
                  options={instrumentOptions} onChange={(v) => updTf(r.key, { buyer_payment_instrument: v })} /> ) },
              { title: t('sc.trade_finance.lc_prep'), key: 'lc', width: 140, render: (_, r) => (
                <Select style={{ width: 120 }} value={r.lc_doc_prep_investment} disabled={!editable || tfLocked}
                  options={lcDocPrep} onChange={(v) => updTf(r.key, { lc_doc_prep_investment: v })} /> ) },
              { title: '', key: 'x', width: 40, render: (_, r) => <Button type="text" danger icon={<DeleteOutlined />} disabled={!editable} onClick={() => delTf(r.key)} /> },
            ]} />
        )}
        <Button icon={<PlusOutlined />} onClick={addTf} disabled={!editable || tfLocked} style={{ marginTop: 12 }}>{t('sc.trade_finance.add_payment')}</Button>
      </PanelCard>

      <Divider orientation="left">{t('sc.trade_finance.risk_management')}</Divider>
      <PanelCard headerColor="neutral"
        title={<Space>{t('sc.trade_finance.sinosure')} {round < UNLOCK.sinosure_coverage && lockTag(UNLOCK.sinosure_coverage, t)}</Space>} style={{ marginBottom: 16 }}>
        {markets.length === 0 ? <Empty description={t('sc.logistics.no_markets')} /> : (
          <Table rowKey="id" size="small" pagination={false} dataSource={markets}
            columns={[
              { title: t('sc.trade_finance.market'), key: 'm', render: (_, mk) => <><Text strong>{mk.name}</Text> <Tag>{mk.code}</Tag></> },
              { title: t('sc.trade_finance.coverage_pct'), key: 'cov', render: (_, mk) => (
                <InputNumber min={0} max={100} value={sino[mk.id]} disabled={!editable || round < UNLOCK.sinosure_coverage}
                  onChange={(v) => setSino((p) => ({ ...p, [mk.id]: v }))} /> ) },
            ]} />
        )}
      </PanelCard>

      <PanelCard headerColor="strategic"
        title={<Space>{t('sc.trade_finance.fx_hedging')} {round < UNLOCK.fx_hedging && lockTag(UNLOCK.fx_hedging, t)}</Space>} style={{ marginBottom: 16 }}>
        {currencyPairs.length === 0 ? <Empty description={t('sc.trade_finance.no_fx_pairs')} /> : (
          <Table rowKey="pair" size="small" pagination={false}
            dataSource={currencyPairs.map((p) => ({ pair: p }))}
            columns={[
              { title: t('sc.trade_finance.currency_pair'), dataIndex: 'pair', key: 'p', render: (v) => <Text strong>{v}</Text> },
              { title: t('sc.trade_finance.hedge_ratio'), key: 'hr', render: (_, r) => (
                <InputNumber min={0} max={100} value={fx[r.pair]?.hedge_ratio} disabled={!editable || round < UNLOCK.fx_hedging}
                  onChange={(v) => setFx((p) => ({ ...p, [r.pair]: { ...(p[r.pair] || {}), hedge_ratio: v } }))} /> ) },
              { title: t('sc.trade_finance.tenor_days'), key: 'td', render: (_, r) => (
                <Select style={{ width: 110 }} allowClear placeholder="—" value={fx[r.pair]?.tenor_days} disabled={!editable || round < UNLOCK.fx_hedging}
                  options={tenorOptions.map((t) => ({ value: t, label: `${t}` }))}
                  onChange={(v) => setFx((p) => ({ ...p, [r.pair]: { ...(p[r.pair] || {}), tenor_days: v } }))} /> ) },
            ]} />
        )}
      </PanelCard>

      <PanelCard headerColor="neutral" title={t('sc.trade_finance.hedge_positions')} style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          {t('sc.trade_finance.hedge_help')}
        </Text>
        {hedgePositions.length === 0
          ? <Empty description={t('sc.trade_finance.no_positions')} />
          : (
            <Table rowKey="id" size="small" pagination={false} dataSource={hedgePositions} scroll={{ x: true }}
              columns={[
                { title: t('sc.trade_finance.pair'), dataIndex: 'currency_pair', key: 'cp', render: (v) => <Text strong>{v}</Text> },
                { title: t('sc.trade_finance.notional'), dataIndex: 'notional', key: 'n', render: (v) => `$${Math.round(Number(v)).toLocaleString()}` },
                { title: t('sc.trade_finance.locked_rate'), dataIndex: 'locked_rate', key: 'lr', render: (v) => Number(v).toFixed(4) },
                { title: t('sc.trade_finance.mark_to_market'), dataIndex: 'mtm_current', key: 'mtm', render: (v) => (
                  <Text type={Number(v) > 0 ? 'success' : Number(v) < 0 ? 'danger' : undefined}>
                    {Number(v) >= 0 ? '+' : ''}{Math.round(Number(v)).toLocaleString()}
                  </Text>) },
                { title: t('sc.trade_finance.realized_pnl'), dataIndex: 'realized_pnl', key: 'rp', render: (v) => (
                  v == null ? <Text type="secondary">—</Text>
                    : <Text type={Number(v) > 0 ? 'success' : Number(v) < 0 ? 'danger' : undefined}>
                        {Number(v) >= 0 ? '+' : ''}{Math.round(Number(v)).toLocaleString()}
                      </Text>) },
                { title: t('sc.trade_finance.status'), dataIndex: 'status', key: 'st', render: (v) => (
                  <Tag color={v === 'open' ? 'blue' : v === 'matured' ? 'green' : 'default'}>{v}</Tag>) },
              ]} />
          )}
      </PanelCard>
    </div>
  );
};

export default TradeFinancePage;
