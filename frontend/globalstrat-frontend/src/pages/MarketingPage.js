import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Typography, Tabs, InputNumber, Select, Slider, Tag, Space, Row, Col, Progress, Alert, Checkbox, Statistic } from 'antd';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { useAuth } from '../AuthContext';
import { getMarketingContext, patchDecision } from '../api/decisions';
import LoadingSpinner from '../components/LoadingSpinner';
import TeamActivityBanner from '../components/TeamActivityBanner';
import { PanelCard, PageHeader } from '../components/design-system';
import useUnsavedChangesGuard from '../hooks/useUnsavedChangesGuard';
import { isRowEngaged, blankPriceMessageKey } from './marketingPricingRules';
import { DECISION_INPUT_LIMITS } from '../decisionInputLimits';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const getDistributionChannels = (t) => [
  { key: 'mass_retail', label: t('marketing.ch_mass_retail'), description: t('marketing.ch_mass_retail_desc'), reach: t('marketing.reach_high'), margin: t('marketing.margin_low') },
  { key: 'selective_retail', label: t('marketing.ch_selective_retail'), description: t('marketing.ch_selective_retail_desc'), reach: t('marketing.reach_medium'), margin: t('marketing.margin_medium') },
  { key: 'exclusive_retail', label: t('marketing.ch_exclusive_retail'), description: t('marketing.ch_exclusive_retail_desc'), reach: t('marketing.reach_low'), margin: t('marketing.margin_high') },
  { key: 'direct_online', label: t('marketing.ch_direct_online'), description: t('marketing.ch_direct_online_desc'), reach: t('marketing.reach_medium'), margin: t('marketing.margin_high') },
];

const MarketingPage = () => {
  const { t } = useTranslation();
  const DISTRIBUTION_CHANNELS = getDistributionChannels(t);
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { draft, locked } = useDecisions();
  const { user } = useAuth();
  const [context, setContext] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  // R17: a refused save must tell the student, show the edit was NOT saved,
  // and retry. Previously every failure was swallowed while the screen went on
  // claiming "Your entry is saved".
  const [saveError, setSaveError] = useState(null);
  const saveTimer = useRef(null);
  const saveVersion = useRef(0);
  const retryTimer = useRef(null);
  const lastDecisions = useRef(null);
  const retried = useRef(false);

  useUnsavedChangesGuard(dirty, t('common.unsaved_changes_prompt'));

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const res = await getMarketingContext(gameId, teamId);
      setContext(res.data);
      const existing = draft?.marketing_decisions || [];
      const productMarkets = res.data?.product_markets || [];
      const capacityRows = res.data?.production_capacity || [];
      // The API requires a production source market on every row it stores, so
      // a fresh row that defaults it to null cannot be saved at all (F7). It
      // defaults to where the product is sold when the team has capacity
      // there, else to the first plant they have; production volume still
      // starts at 0, so this commits nothing and the team can change it.
      const defaultSourceMarket = (marketId) => {
        if (capacityRows.some(c => c.market_id === marketId)) return marketId;
        return capacityRows.length ? capacityRows[0].market_id : null;
      };
      const decs = [];
      productMarkets.forEach(pm => {
        (pm.markets || []).forEach(m => {
          const ex = existing.find(e => e.team_product === pm.product_id && e.market === m.market_id);
          decs.push({
            team_product: pm.product_id,
            product_name: pm.product_name,
            positioning: pm.positioning,
            market: m.market_id,
            market_name: m.market__name || m.market_name,
            // null, not 0: an absent price is a distinct state the server
            // alerts on and fills at the band floor when the round closes.
            retail_price: (ex?.retail_price === null || ex?.retail_price === undefined)
              ? null : Number(ex.retail_price),
            promotion_budget: Number(ex?.promotion_budget || 0),
            campaign_focus_feature_ids: ex?.campaign_focus_feature_ids || [],
            channel_digital_pct: Number(ex?.channel_digital_pct || 0.34),
            channel_traditional_pct: Number(ex?.channel_traditional_pct || 0.33),
            channel_trade_pct: Number(ex?.channel_trade_pct || 0.33),
            distribution_strategy: ex?.distribution_strategy || 'mass_retail',
            distribution_investment: Number(ex?.distribution_investment || 0),
            sales_team_count: Number(ex?.sales_team_count || 0),
            distribution_channel_detail: ex?.distribution_channel_detail || {},
            production_volume: Number(ex?.production_volume || 0),
            production_source_market: ex?.production_source_market
              ?? defaultSourceMarket(m.market_id),
            demand_estimate: Number(ex?.demand_estimate || 0),
            // `persisted` means the server already holds this row, so it must
            // keep being sent even once every number on it is cleared --
            // otherwise clearing a price deletes the decision instead of
            // submitting a blank one (F2). `touched` is the same guarantee for
            // a row the team has started filling in this session.
            persisted: !!ex,
            touched: false,
          });
        });
      });
      setDecisions(decs);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId, draft]);

  useEffect(() => { loadContext(); }, [loadContext]);

  const repCost = Number(context?.sales_rep_cost_per_round || 100000);
  const totalSpend = decisions.reduce((s, d) => s + d.promotion_budget + (d.sales_team_count * repCost), 0);
  const mktgBudget = Number(context?.marketing_budget_remaining || 0) + totalSpend;

  // Built in one place, so what is sent and what is retried cannot drift apart.
  const buildPayload = useCallback((nextDecisions) => nextDecisions
    // R15 forbids sending a product-market the team never marketed: the floor
    // must never reach it, and a fabricated floor-priced row would take share
    // from every rival and then sell nothing. But a row the team HAS engaged
    // with must always be sent, even with no price and no spend at all, or
    // "submitted blank" never reaches the server (R15/R24) and clearing the
    // price of an otherwise-empty row silently deletes the decision (F2).
    .filter(isRowEngaged)
    .map(d => ({
      team_product: d.team_product,
      market: d.market,
      retail_price: d.retail_price,
      promotion_budget: d.promotion_budget,
      campaign_focus_feature_ids: d.campaign_focus_feature_ids,
      channel_digital_pct: d.channel_digital_pct,
      channel_traditional_pct: d.channel_traditional_pct,
      channel_trade_pct: d.channel_trade_pct,
      distribution_strategy: d.distribution_strategy,
      distribution_investment: d.sales_team_count * repCost,
      sales_team_count: d.sales_team_count,
      distribution_channel_detail: d.distribution_channel_detail,
      production_volume: d.production_volume,
      production_source_market: d.production_source_market,
      demand_estimate: d.demand_estimate,
    })), [repCost]);

  const sendSave = useCallback(async (nextDecisions) => {
    await patchDecision(gameId, teamId, currentRound, 'marketing',
      { marketing_decisions: buildPayload(nextDecisions) });
  }, [gameId, teamId, currentRound, buildPayload]);

  /** The server's own sentences, never its field names. */
  const describeFailure = useCallback((err) => {
    const data = err?.response?.data;
    if (!data) return [t('marketing.save_failed_generic')];
    if (typeof data === 'string') return [data];
    if (data.detail) return [String(data.detail)];
    const out = [];
    const walk = (value) => {
      if (Array.isArray(value)) value.forEach(walk);
      else if (value && typeof value === 'object') Object.values(value).forEach(walk);
      else if (value != null) out.push(String(value));
    };
    walk(data);
    return out.length ? out : [t('marketing.save_failed_generic')];
  }, [t]);

  const retrySave = useCallback(async () => {
    if (!lastDecisions.current || locked) return;
    setSaving(true);
    try {
      await sendSave(lastDecisions.current);
      setDirty(false);
      setSaveError(null);
      refreshBudgets();
    } catch (err) {
      setSaveError(describeFailure(err));
    }
    setSaving(false);
  }, [sendSave, refreshBudgets, describeFailure, locked]);

  const autoSave = useCallback((nextDecisions) => {
    const version = ++saveVersion.current;
    setDirty(true);
    lastDecisions.current = nextDecisions;
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!gameId || !teamId || !currentRound || locked) return;
      setSaving(true);
      try {
        await sendSave(nextDecisions);
        if (version === saveVersion.current) {
          setDirty(false);
          setSaveError(null);
        }
        refreshBudgets();
      } catch (err) {
        // R17. The edit stays marked unsaved, the student is told what the
        // server said, and it is retried once automatically; the notice also
        // carries a Retry control, because a refusal the team can fix (a
        // missing campaign focus, say) will not succeed on a timer.
        setSaveError(describeFailure(err));
        if (!retried.current) {
          retried.current = true;
          clearTimeout(retryTimer.current);
          retryTimer.current = setTimeout(() => { retrySave(); }, 5000);
        }
      }
      setSaving(false);
    }, 2000);
  }, [gameId, teamId, currentRound, locked, refreshBudgets, sendSave,
      describeFailure, retrySave]);

  useEffect(() => () => {
    clearTimeout(saveTimer.current);
    clearTimeout(retryTimer.current);
  }, []);

  const updateDecision = (idx, field, value) => {
    setDecisions(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value, touched: true };
      if (field === 'channel_digital_pct' || field === 'channel_traditional_pct' || field === 'channel_trade_pct') {
        const d = next[idx];
        const total = d.channel_digital_pct + d.channel_traditional_pct + d.channel_trade_pct;
        if (Math.abs(total - 1) > 0.01 && total > 0) {
          const scale = 1 / total;
          next[idx].channel_digital_pct = Math.round(d.channel_digital_pct * scale * 100) / 100;
          next[idx].channel_traditional_pct = Math.round(d.channel_traditional_pct * scale * 100) / 100;
          next[idx].channel_trade_pct = 1 - next[idx].channel_digital_pct - next[idx].channel_traditional_pct;
        }
      }
      autoSave(next);
      return next;
    });
  };

  const toggleChannel = (idx, channelKey) => {
    setDecisions(prev => {
      const next = [...prev];
      const d = { ...next[idx], touched: true };
      const detail = { ...(d.distribution_channel_detail || {}) };
      if (detail[channelKey] != null) {
        delete detail[channelKey];
      } else {
        detail[channelKey] = 0;
      }
      d.distribution_channel_detail = detail;
      // Derive distribution_strategy from selected channels
      const selected = Object.keys(detail);
      if (selected.length === 0) {
        d.distribution_strategy = 'mass_retail';
      } else if (selected.length === 1) {
        d.distribution_strategy = selected[0];
      } else {
        d.distribution_strategy = 'hybrid';
      }
      // Sum sales_team_count from channel reps
      d.sales_team_count = Object.values(detail).reduce((s, v) => s + (v || 0), 0);
      next[idx] = d;
      autoSave(next);
      return next;
    });
  };

  const updateChannelReps = (idx, channelKey, reps) => {
    setDecisions(prev => {
      const next = [...prev];
      const d = { ...next[idx], touched: true };
      const detail = { ...(d.distribution_channel_detail || {}) };
      detail[channelKey] = reps || 0;
      d.distribution_channel_detail = detail;
      d.sales_team_count = Object.values(detail).reduce((s, v) => s + (v || 0), 0);
      next[idx] = d;
      autoSave(next);
      return next;
    });
  };

  const toggleCampaignFeature = (idx, featureId) => {
    setDecisions(prev => {
      const next = [...prev];
      const d = next[idx];
      const ids = [...(d.campaign_focus_feature_ids || [])];
      const i = ids.indexOf(featureId);
      if (i >= 0) {
        ids.splice(i, 1);
      } else if (ids.length < 3) {
        ids.push(featureId);
      }
      next[idx] = { ...d, campaign_focus_feature_ids: ids, touched: true };
      autoSave(next);
      return next;
    });
  };

  if (loading) return <LoadingSpinner />;
  if (!context) return <Alert message={t('marketing.unable_to_load')} type="error" />;

  // Group decisions by market
  const marketGroups = {};
  decisions.forEach((d, idx) => {
    if (!marketGroups[d.market_name]) marketGroups[d.market_name] = [];
    marketGroups[d.market_name].push({ ...d, _idx: idx });
  });

  const capacity = context.production_capacity || [];
  const features = context.features || [];

  const getCapacityInfo = (sourceMarketId) => {
    if (!sourceMarketId) return null;
    return capacity.find(c => c.market_id === sourceMarketId);
  };

  const getAllocatedUnits = (sourceMarketId, excludeIdx) => {
    return decisions.reduce((sum, d, i) => {
      if (i !== excludeIdx && d.production_source_market === sourceMarketId) {
        return sum + (d.production_volume || 0);
      }
      return sum;
    }, 0);
  };

  // Determine which channels are active for a decision (from detail or fallback to strategy)
  const getActiveChannels = (d) => {
    const detail = d.distribution_channel_detail || {};
    if (Object.keys(detail).length > 0) return detail;
    // Fallback: if no detail set, derive from legacy distribution_strategy
    if (d.distribution_strategy && d.distribution_strategy !== 'hybrid') {
      return { [d.distribution_strategy]: d.sales_team_count || 0 };
    }
    return {};
  };

  // Previous round decision lookup helper
  const prevHint = (style) => ({ fontSize: 9, fontStyle: 'italic', color: '#8c8c8c', display: 'block', ...style });

  const renderProductCard = (d) => {
    const configured = d.retail_price > 0 && d.production_volume > 0;
    const partial = d.retail_price > 0 || d.production_volume > 0;
    const borderColor = configured ? '#52c41a' : partial ? '#faad14' : '#d9d9d9';
    const capInfo = getCapacityInfo(d.production_source_market);
    const allocated = d.production_source_market ? getAllocatedUnits(d.production_source_market, d._idx) : 0;
    const activeChannels = getActiveChannels(d);
    const totalReps = Object.values(activeChannels).reduce((s, v) => s + (v || 0), 0);

    // Previous round data for this product-market
    const prevKey = `${d.team_product}_${d.market}`;
    const prev = context.prev_round_decisions?.[prevKey];
    // Stage 5 price band. min/max come from the server's one calculator; this
    // only decides which of those server-supplied numbers to show, so the
    // screen cannot state a different range from the one enforced.
    const band = context.price_bands?.[prevKey];
    const priceEntered = d.retail_price > 0;
    const priceOutOfBand = !!band && priceEntered
      && (d.retail_price < band.min || d.retail_price > band.max);
    const priceBlank = !!band && !priceEntered;

    return (
      <div key={`${d.team_product}-${d.market}`}>
        {/* PRICING — single inline row */}
        <PanelCard title={t('marketing.pricing').toUpperCase()} headerColor="decision">
          <Row gutter={12} align="middle">
            <Col flex="60px"><Text strong style={{ fontSize: 11, textTransform: 'uppercase', color: '#888' }}>{t('marketing.price')}</Text></Col>
            <Col flex="160px">
              <InputNumber
                size="small" prefix="$" min={0} max={DECISION_INPUT_LIMITS.retail_price} step={10}
                value={d.retail_price} disabled={locked}
                onChange={v => updateDecision(d._idx, 'retail_price', v ?? null)}
                style={{ width: '100%' }}
              />
              {prev && <Text style={prevHint()}>{t('marketing.last')}: ${prev.retail_price}</Text>}
              {band && (
                <Text style={prevHint({ color: (priceOutOfBand || priceBlank) ? '#cf1322' : '#8c8c8c' })}>
                  {t('marketing.price_band_range', {
                    min: Math.round(band.min).toLocaleString(),
                    max: Math.round(band.max).toLocaleString(),
                  })}
                </Text>
              )}
              {priceOutOfBand && (
                <Text style={prevHint({ color: '#cf1322' })}>
                  {/* The standing wording says "Your entry is saved", which is
                      false while a save is outstanding. */}
                  {saveError
                    ? t('marketing.price_out_of_band_unsaved')
                    : t('marketing.price_out_of_band')}
                </Text>
              )}
              {priceBlank && (
                <Text style={prevHint({ color: '#cf1322' })}>
                  {/* Which outcome a blank price gets depends on the anchor, and
                      the server already says which one applies. The floor
                      reaches only a product that sold here last round (R15);
                      with a positioning-reference anchor `blank_price()`
                      returns None and the product is simply not for sale
                      (R24). Promising a floor that will never arrive is worse
                      than saying nothing. */}
                  {blankPriceMessageKey(band) === 'marketing.price_blank'
                    ? t('marketing.price_blank', { floor: Math.round(band.min).toLocaleString() })
                    : t('marketing.price_blank_not_for_sale')}
                </Text>
              )}
            </Col>
            <Col>
              <Tag color={d.positioning === 'premium' ? 'purple' : d.positioning === 'budget' ? 'green' : 'blue'}>
                {d.positioning}
              </Tag>
            </Col>
          </Row>
        </PanelCard>

        {/* PRODUCTION — compact row with inline capacity info */}
        <PanelCard title={t('marketing.production').toUpperCase()} headerColor="decision">
          <Row gutter={12} align="top">
            <Col flex="60px" style={{ paddingTop: 14 }}><Text strong style={{ fontSize: 11, textTransform: 'uppercase', color: '#888' }}>{t('marketing.prod')}</Text></Col>
            <Col flex="1">
              <Text style={{ fontSize: 10, color: '#888', display: 'block', marginBottom: 2 }}>{t('marketing.production_volume')}</Text>
              <InputNumber
                size="small" min={0} max={DECISION_INPUT_LIMITS.production_volume} step={1000}
                value={d.production_volume} disabled={locked}
                onChange={v => updateDecision(d._idx, 'production_volume', v || 0)}
                style={{ width: '100%' }}
                addonAfter="units"
              />
              {prev && <Text style={prevHint()}>{t('marketing.last')}: {prev.production_volume.toLocaleString()}</Text>}
            </Col>
            <Col flex="1">
              <Text style={{ fontSize: 10, color: '#888', display: 'block', marginBottom: 2 }}>{t('marketing.source_market')}</Text>
              <Select
                size="small"
                value={d.production_source_market} disabled={locked}
                onChange={v => updateDecision(d._idx, 'production_source_market', v)}
                style={{ width: '100%' }}
                placeholder={t('marketing.select_source')}
                allowClear
              >
                {capacity.map(c => (
                  <Select.Option key={c.market_id} value={c.market_id}>{c.market_name}</Select.Option>
                ))}
              </Select>
            </Col>
            <Col flex="1">
              <Text style={{ fontSize: 10, color: '#888', display: 'block', marginBottom: 2 }}>{t('marketing.demand_estimate')}</Text>
              <InputNumber
                size="small" min={0} max={DECISION_INPUT_LIMITS.demand_estimate} step={1000}
                value={d.demand_estimate} disabled={locked}
                onChange={v => updateDecision(d._idx, 'demand_estimate', v || 0)}
                style={{ width: '100%' }}
                addonAfter="units"
              />
            </Col>
            <Col flex="1" style={{ textAlign: 'right', paddingTop: 14 }}>
              {capInfo && (
                <Text type="secondary" style={{ fontSize: 10 }}>
                  {t('marketing.capacity')}: {(capInfo.own_capacity || 0) + (capInfo.contract_mfg_capacity || 0)} {t('marketing.units')}
                  {allocated > 0 && ` (${allocated} alloc.)`}
                </Text>
              )}
            </Col>
          </Row>
          {d.production_volume > 0 && capInfo && d.production_volume > (capInfo.own_capacity || 0) && (
            <Tag color="warning" style={{ marginTop: 4, fontSize: 10 }}>{t('marketing.exceeds_capacity', { premium: Math.round((Number(capInfo.contract_mfg_cost_multiplier || 1.25) - 1) * 100) })}</Tag>
          )}
        </PanelCard>

        {/* PROMOTION — budget + campaign focus + channel sliders in one card */}
        <PanelCard title={t('marketing.promotion').toUpperCase()} headerColor="decision">
          <Row gutter={12} align="top">
            <Col flex="60px" style={{ paddingTop: 4 }}><Text strong style={{ fontSize: 11, textTransform: 'uppercase', color: '#888' }}>{t('marketing.promo')}</Text></Col>
            <Col flex="160px">
              <InputNumber
                size="small" prefix="$" min={0} max={DECISION_INPUT_LIMITS.promotion_budget} step={10000}
                value={d.promotion_budget} disabled={locked}
                onChange={v => updateDecision(d._idx, 'promotion_budget', v || 0)}
                style={{ width: '100%' }}
              />
              {prev && <Text style={prevHint()}>{t('marketing.last')}: {fmt(prev.promotion_budget)}</Text>}
            </Col>
            <Col flex="auto">
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                <Text type="secondary" style={{ fontSize: 10, marginRight: 4 }}>{t('marketing.focus')}:</Text>
                {features.map(f => {
                  const selected = (d.campaign_focus_feature_ids || []).includes(f.id);
                  return (
                    <Tag
                      key={f.id}
                      color={selected ? 'blue' : undefined}
                      style={{
                        cursor: locked ? 'default' : 'pointer',
                        fontSize: 10, lineHeight: '18px', padding: '0 4px', margin: '0 2px',
                        opacity: !selected && (d.campaign_focus_feature_ids || []).length >= 3 ? 0.4 : 1,
                      }}
                      onClick={() => !locked && toggleCampaignFeature(d._idx, f.id)}
                    >
                      {selected ? '✓ ' : ''}{f.name}
                    </Tag>
                  );
                })}
              </div>
            </Col>
          </Row>
          <Row gutter={12} style={{ marginTop: 4 }}>
            <Col flex="60px" />
            <Col flex="1">
              <Text type="secondary" style={{ fontSize: 10 }}>{t('marketing.digital')} {Math.round(d.channel_digital_pct * 100)}%</Text>
              <Slider
                min={0} max={100} value={Math.round(d.channel_digital_pct * 100)}
                disabled={locked}
                onChange={v => updateDecision(d._idx, 'channel_digital_pct', v / 100)}
                style={{ margin: '0 0 2px' }}
              />
            </Col>
            <Col flex="1">
              <Text type="secondary" style={{ fontSize: 10 }}>{t('marketing.traditional')} {Math.round(d.channel_traditional_pct * 100)}%</Text>
              <Slider
                min={0} max={100} value={Math.round(d.channel_traditional_pct * 100)}
                disabled={locked}
                onChange={v => updateDecision(d._idx, 'channel_traditional_pct', v / 100)}
                style={{ margin: '0 0 2px' }}
              />
            </Col>
            <Col flex="1">
              <Text type="secondary" style={{ fontSize: 10 }}>{t('marketing.trade')} {Math.round(d.channel_trade_pct * 100)}%</Text>
              <Slider
                min={0} max={100} value={Math.round(d.channel_trade_pct * 100)}
                disabled={locked}
                onChange={v => updateDecision(d._idx, 'channel_trade_pct', v / 100)}
                style={{ margin: '0 0 2px' }}
              />
            </Col>
          </Row>
        </PanelCard>

        {/* DISTRIBUTION — 4 channels in a single row, compact */}
        <PanelCard title={t('marketing.distribution').toUpperCase()} headerColor="decision">
          <Row gutter={12} align="top">
            <Col flex="60px" style={{ paddingTop: 4 }}>
              <Text strong style={{ fontSize: 11, textTransform: 'uppercase', color: '#888' }}>{t('marketing.dist')}</Text>
              {totalReps > 0 && <Text type="secondary" style={{ display: 'block', fontSize: 10 }}>{fmt(totalReps * repCost)}</Text>}
              {prev && prev.sales_team_count > 0 && <Text style={prevHint({ marginTop: 2 })}>{t('marketing.last')}: {prev.sales_team_count} {t('marketing.reps')}</Text>}
            </Col>
            <Col flex="auto">
              <Row gutter={[8, 8]}>
                {DISTRIBUTION_CHANNELS.map(ch => {
                  const isActive = activeChannels[ch.key] != null;
                  const reps = activeChannels[ch.key] || 0;
                  return (
                    <Col xs={12} md={6} key={ch.key}>
                      <div
                        style={{
                          border: isActive ? '2px solid #1677ff' : '1px solid #d9d9d9',
                          background: isActive ? '#f0f5ff' : '#fafafa',
                          borderRadius: 6, padding: '6px 8px',
                        }}
                      >
                        <Checkbox
                          checked={isActive}
                          disabled={locked}
                          onChange={() => toggleChannel(d._idx, ch.key)}
                        >
                          <Text strong style={{ fontSize: 11 }}>{ch.label}</Text>
                        </Checkbox>
                        <div style={{ marginLeft: 22, marginTop: 2 }}>
                          <Tag color="blue" style={{ fontSize: 9, padding: '0 3px', margin: 0 }}>{ch.reach}</Tag>
                          <Tag color="green" style={{ fontSize: 9, padding: '0 3px', margin: '0 0 0 2px' }}>{ch.margin}</Tag>
                          {isActive && (
                            <InputNumber
                              min={0} max={20} step={1}
                              value={reps} disabled={locked}
                              onChange={v => updateChannelReps(d._idx, ch.key, v || 0)}
                              size="small"
                              style={{ width: 60, marginLeft: 6 }}
                              placeholder={t('marketing.reps')}
                            />
                          )}
                        </div>
                      </div>
                    </Col>
                  );
                })}
              </Row>
            </Col>
          </Row>
        </PanelCard>

        {/* PROJECTED IMPACT — revenue preview computed from current inputs */}
        {(() => {
          const prevKey = `${d.team_product}_${d.market}`;
          const prevData = context.prev_round_sales?.[prevKey];
          const lastSales = prevData?.units_sold || 0;
          const maxRevenue = d.retail_price * d.production_volume;
          const distributionCost = totalReps * repCost;
          const totalMarketingCost = d.promotion_budget + distributionCost;
          const productionExceedsLastSales = lastSales > 0 && d.production_volume > 2 * lastSales;

          return (
            <PanelCard title={t('marketing.projected_impact')} headerColor="results">
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic
                    title={<Text style={{ fontSize: 10 }}>{t('marketing.max_revenue')}</Text>}
                    value={maxRevenue}
                    valueStyle={{ fontSize: 14 }}
                    formatter={() => fmt(maxRevenue)}
                  />
                  <Text type="secondary" style={{ fontSize: 9 }}>
                    {fmt(d.retail_price || 0)} x {(d.production_volume || 0).toLocaleString()} units
                  </Text>
                </Col>
                <Col span={6}>
                  <Statistic
                    title={<Text style={{ fontSize: 10 }}>{t('marketing.last_round_sales')}</Text>}
                    value={lastSales}
                    valueStyle={{ fontSize: 14 }}
                    formatter={() => lastSales > 0 ? Number(lastSales).toLocaleString() + ' units' : '--'}
                  />
                  {prevData && prevData.units_produced > 0 && (
                    <div style={{ fontSize: 9, color: '#888' }}>
                      <div>{t('marketing.produced')}: {prevData.units_produced.toLocaleString()} | {t('marketing.unsold')}: {Math.round(prevData.units_unsold || 0).toLocaleString()}</div>
                      {prevData.units_unsold > 0 && (
                        <div>{t('marketing.carry_over')}: {Math.round(prevData.units_unsold).toLocaleString()} {t('marketing.units')}</div>
                      )}
                    </div>
                  )}
                  {!prevData && <Text type="secondary" style={{ fontSize: 9 }}>{t('marketing.no_prior_data')}</Text>}
                </Col>
                <Col span={6}>
                  <Statistic
                    title={<Text style={{ fontSize: 10 }}>{t('marketing.total_mktg_cost')}</Text>}
                    value={totalMarketingCost}
                    valueStyle={{ fontSize: 14 }}
                    formatter={() => fmt(totalMarketingCost)}
                  />
                  <Text type="secondary" style={{ fontSize: 9 }}>
                    {t('marketing.promo')} {fmt(d.promotion_budget)} + {t('marketing.dist')} {fmt(distributionCost)}
                  </Text>
                </Col>
                <Col span={6}>
                  {maxRevenue > 0 && totalMarketingCost > 0 && (
                    <Statistic
                      title={<Text style={{ fontSize: 10 }}>{t('marketing.mktg_pct_rev')}</Text>}
                      value={Math.round((totalMarketingCost / maxRevenue) * 100)}
                      suffix="%"
                      valueStyle={{ fontSize: 14, color: (totalMarketingCost / maxRevenue) > 0.5 ? '#cf1322' : undefined }}
                    />
                  )}
                </Col>
              </Row>
              {productionExceedsLastSales && (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginTop: 8, padding: '4px 8px', fontSize: 11 }}
                  message={
                    <Text style={{ fontSize: 11 }}>
                      {t('marketing.production_warning', { production: d.production_volume.toLocaleString(), sales: Math.round(lastSales).toLocaleString() })}
                    </Text>
                  }
                />
              )}
            </PanelCard>
          );
        })()}
      </div>
    );
  };

  // Build market tabs, each containing product tabs
  const marketTabItems = Object.entries(marketGroups).map(([mktName, items]) => ({
    key: mktName,
    label: `${mktName} (${items.length})`,
    children: items.length === 1 ? (
      renderProductCard(items[0])
    ) : (
      <Tabs
        type="card"
        items={items.map(d => ({
          key: String(d.team_product),
          label: (
            <span>
              {d.product_name}
              <Tag
                color={d.positioning === 'premium' ? 'purple' : d.positioning === 'budget' ? 'green' : 'blue'}
                style={{ fontSize: 10, marginLeft: 6 }}
              >
                {d.positioning}
              </Tag>
            </span>
          ),
          children: renderProductCard(d),
        }))}
      />
    ),
  }));

  return (
    <div>
      <TeamActivityBanner gameId={gameId} teamId={teamId} currentRound={currentRound} currentUserId={user?.user_id} />
      <PageHeader title={t('marketing.title')} subtitle={`${t('common.round')} ${currentRound}`} status={locked ? 'locked' : 'draft'} />
      {saving && <Tag color="processing">{t('marketing.saving')}</Tag>}

      {/* R17: a refused save is announced by the shared DecisionSaveAlert,
          which the axios interceptor feeds for every decision write and
          which carries the server's own sentences and the retry. This page
          used to repeat it with a banner of its own, so one refusal was
          shown twice (W-CE-04); `saveError` now only marks the entries as
          unsaved where they are edited. */}

      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Text strong>{t('marketing.marketing_budget')}:</Text>
          <Progress
            percent={mktgBudget > 0 ? Math.round((totalSpend / mktgBudget) * 100) : 0}
            style={{ flex: 1 }}
            format={() => `${fmt(totalSpend)} / ${fmt(mktgBudget)}`}
            status={totalSpend > mktgBudget ? 'exception' : 'active'}
          />
        </div>
      </Card>

      <Tabs items={marketTabItems} />
    </div>
  );
};

export default MarketingPage;
