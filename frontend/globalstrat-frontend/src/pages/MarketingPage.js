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
  const saveTimer = useRef(null);

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const res = await getMarketingContext(gameId, teamId);
      setContext(res.data);
      const existing = draft?.marketing_decisions || [];
      const productMarkets = res.data?.product_markets || [];
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
            retail_price: Number(ex?.retail_price || 0),
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
            production_source_market: ex?.production_source_market || null,
            demand_estimate: Number(ex?.demand_estimate || 0),
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

  const autoSave = useCallback(() => {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!gameId || !teamId || !currentRound || locked) return;
      setSaving(true);
      try {
        const payload = decisions.filter(d => d.retail_price > 0 || d.production_volume > 0).map(d => ({
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
        }));
        await patchDecision(gameId, teamId, currentRound, 'marketing', { marketing_decisions: payload });
        refreshBudgets();
      } catch { /* ignore */ }
      setSaving(false);
    }, 2000);
  }, [gameId, teamId, currentRound, locked, decisions, refreshBudgets]);

  const updateDecision = (idx, field, value) => {
    setDecisions(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
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
      return next;
    });
    autoSave();
  };

  const toggleChannel = (idx, channelKey) => {
    setDecisions(prev => {
      const next = [...prev];
      const d = { ...next[idx] };
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
      return next;
    });
    autoSave();
  };

  const updateChannelReps = (idx, channelKey, reps) => {
    setDecisions(prev => {
      const next = [...prev];
      const d = { ...next[idx] };
      const detail = { ...(d.distribution_channel_detail || {}) };
      detail[channelKey] = reps || 0;
      d.distribution_channel_detail = detail;
      d.sales_team_count = Object.values(detail).reduce((s, v) => s + (v || 0), 0);
      next[idx] = d;
      return next;
    });
    autoSave();
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
      next[idx] = { ...d, campaign_focus_feature_ids: ids };
      return next;
    });
    autoSave();
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

    return (
      <div key={`${d.team_product}-${d.market}`}>
        {/* PRICING — single inline row */}
        <PanelCard title={t('marketing.pricing').toUpperCase()} headerColor="decision">
          <Row gutter={12} align="middle">
            <Col flex="60px"><Text strong style={{ fontSize: 11, textTransform: 'uppercase', color: '#888' }}>{t('marketing.price')}</Text></Col>
            <Col flex="160px">
              <InputNumber
                size="small" prefix="$" min={0} step={10}
                value={d.retail_price} disabled={locked}
                onChange={v => updateDecision(d._idx, 'retail_price', v || 0)}
                style={{ width: '100%' }}
              />
              {prev && <Text style={prevHint()}>{t('marketing.last')}: ${prev.retail_price}</Text>}
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
                size="small" min={0} step={1000}
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
                size="small" min={0} step={1000}
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
                size="small" prefix="$" min={0} step={10000}
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
                    {fmt(d.retail_price)} x {(d.production_volume || 0).toLocaleString()} units
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
