import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Typography, Tabs, Select, Button, Tag, Space, Row, Col, Alert, Statistic, InputNumber, Progress, Divider } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getStrategyContext, getComplianceContext, getMarketLocalization, getAllianceState, patchDecision } from '../api/decisions';
import { PageHeader, PanelCard } from '../components/design-system';
import LoadingSpinner from '../components/LoadingSpinner';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const DISTANCE_DOTS = { HOME: 0, LOW: 1, MEDIUM: 2, HIGH: 3, 'VERY HIGH': 4, VERY_HIGH: 4 };
const DISTANCE_COLORS = { HOME: '#1677ff', LOW: '#52c41a', MEDIUM: '#faad14', HIGH: '#fa8c16', 'VERY HIGH': '#ff4d4f', VERY_HIGH: '#ff4d4f' };

const multPctColor = (pct) => pct >= 90 ? '#52c41a' : pct >= 70 ? '#faad14' : '#ff4d4f';

const TalentLink = ({ children }) => {
  const { gameId, teamId } = useGame();
  const navigate = useNavigate();
  return (
    <a
      href={`/games/${gameId}/teams/${teamId}/decisions/corporate-strategy`}
      onClick={(e) => { e.preventDefault(); navigate(`/games/${gameId}/teams/${teamId}/decisions/corporate-strategy`); }}
    >
      {children}
    </a>
  );
};

const MarketOperationsSection = ({ market, complianceCtx, localizationData, loadLocalization, complianceInvestment, onComplianceChange, locked }) => {
  const { t } = useTranslation();
  const marketCode = market.code;
  const loc = localizationData[marketCode];

  // Load localization data on mount
  React.useEffect(() => { loadLocalization(marketCode); }, [marketCode, loadLocalization]);

  const compMarket = complianceCtx?.markets?.find(cm => cm.code === marketCode);
  const scaleFactor = complianceCtx?.scale_factor || 5000000;
  const isHome = loc?.distance?.level === 'HOME' || market.is_home_market;

  // Compute projected compliance from investment
  const currentLevel = compMarket?.compliance_level || 0;
  const cumulative = compMarket?.cumulative_investment || 0;
  const projectedLevel = complianceInvestment > 0
    ? 1 - Math.exp(-(cumulative + complianceInvestment) / scaleFactor)
    : currentLevel;
  const complianceGain = projectedLevel - currentLevel;

  return (
    <PanelCard headerColor="market" title={t('market_strategy.market_operations')}>
      {/* Card 1: Localization Overview */}
      <Card size="small" style={{ marginBottom: 12 }} title={
        <Space>
          <Text strong style={{ fontSize: 12 }}>{t('market_strategy.localization_overview')} — {market.name}</Text>
          {isHome && <Tag color="blue">HOME</Tag>}
        </Space>
      }>
        {isHome ? (
          <div>
            <Text style={{ display: 'block', marginBottom: 8 }}>
              {t('market_strategy.home_market_desc')}
            </Text>
            <div style={{ display: 'flex', gap: 24, marginBottom: 4 }}>
              {['rd', 'commercial', 'operations'].map(pool => {
                const level = loc?.effective_multipliers?.[pool] ?? loc?.global_talent_levels?.[pool] ?? '—';
                const label = pool === 'rd' ? t('market_strategy.rd') : pool === 'commercial' ? t('market_strategy.commercial') : t('market_strategy.ops');
                return (
                  <Text key={pool} strong style={{ fontSize: 12 }}>
                    {label} {typeof level === 'number' ? level.toFixed(1) : level}
                  </Text>
                );
              })}
            </div>
            <Text type="secondary" style={{ fontSize: 10, display: 'block' }}>
              {t('market_strategy.global_talent_hint')}
            </Text>
          </div>
        ) : (
          <div>
            {loc?.home_market && (
              <Text style={{ display: 'block', marginBottom: 4 }}>{t('common.home_market')}: {loc.home_market.name}</Text>
            )}
            <Space style={{ marginBottom: 8 }}>
              <Text>{t('market_strategy.cultural_distance')}: <Tag color={DISTANCE_COLORS[loc?.distance?.level] || '#8c8c8c'}>{loc?.distance?.level || '—'}</Tag></Text>
              {loc?.distance?.level && loc.distance.level !== 'UNKNOWN' && (
                <span>
                  {Array.from({ length: 4 }, (_, i) => (
                    <span key={i} style={{ fontSize: 14, color: i < (DISTANCE_DOTS[loc?.distance?.level] || 0) ? DISTANCE_COLORS[loc?.distance?.level] : '#d9d9d9' }}>●</span>
                  ))}
                </span>
              )}
            </Space>
            {loc?.rounds_present != null && loc.rounds_present > 0 && (
              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>{t('market_strategy.rounds_present')}: {loc.rounds_present}</Text>
            )}

            {/* Talent pool effectiveness table */}
            <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse', marginBottom: 8 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e8e8e8' }}>
                  <th style={{ textAlign: 'left', padding: '4px 8px' }}>{t('market_strategy.talent_pool')}</th>
                  <th style={{ textAlign: 'center', padding: '4px 8px' }}>{t('market_strategy.effective_level')}</th>
                </tr>
              </thead>
              <tbody>
                {['rd', 'commercial', 'operations'].map(pool => {
                  const mult = loc?.effective_multipliers?.[pool];
                  const globalLevel = loc?.global_talent_levels?.[pool];
                  const label = pool === 'rd' ? t('market_strategy.rd') : pool === 'commercial' ? t('market_strategy.commercial') : t('market_strategy.operations');
                  if (mult == null) {
                    return (
                      <tr key={pool} style={{ borderBottom: '1px solid #f0f0f0' }}>
                        <td style={{ padding: '4px 8px' }}>{label}</td>
                        <td style={{ textAlign: 'center', padding: '4px 8px', color: '#bfbfbf' }}>{t('common.loading')}</td>
                      </tr>
                    );
                  }
                  const pct = globalLevel > 0 ? Math.round((mult / globalLevel) * 100) : 100;
                  return (
                    <tr key={pool} style={{ borderBottom: '1px solid #f0f0f0' }}>
                      <td style={{ padding: '4px 8px' }}>{label}</td>
                      <td style={{ textAlign: 'center', padding: '4px 8px', color: multPctColor(pct) }}>
                        {mult.toFixed(2)} {globalLevel > 0 ? `(${pct}% ${t('market_strategy.of_global', { level: globalLevel.toFixed(1) })})` : ''}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {loc?.trust_multiplier != null && (
              <Text style={{ display: 'block', fontSize: 11 }}>
                {t('market_strategy.origin_trust')}: <span style={{ color: loc.trust_multiplier >= 0.9 ? '#52c41a' : loc.trust_multiplier >= 0.7 ? '#faad14' : '#ff4d4f' }}>
                  {loc.trust_multiplier.toFixed(2)}
                </span>
              </Text>
            )}
            {loc?.distance?.repatriation_cost_pct != null && loc.distance.repatriation_cost_pct > 0 && (
              <Text type="secondary" style={{ display: 'block', fontSize: 11 }}>
                {t('market_strategy.repatriation_cost')}: {(loc.distance.repatriation_cost_pct * 100).toFixed(0)}%
              </Text>
            )}
            <Text type="secondary" style={{ display: 'block', fontSize: 10, marginTop: 8 }}>
              {t('market_strategy.adjust_staff_hint')}
            </Text>
          </div>
        )}
      </Card>

      {/* Card 2: Compliance & Localization Investment — foreign markets only */}
      {!isHome && (
        <Card size="small" style={{ marginBottom: 12 }} title={<Text strong style={{ fontSize: 12 }}>{t('market_strategy.compliance_investment')} — {market.name}</Text>}>
          <div>
            <div style={{ marginBottom: 8 }}>
              <Text style={{ fontSize: 11 }}>{t('market_strategy.compliance_level')}:</Text>
              <Progress
                percent={Math.round(currentLevel * 100)}
                size="small"
                strokeColor={currentLevel >= 0.7 ? '#52c41a' : currentLevel >= 0.4 ? '#faad14' : '#ff4d4f'}
                style={{ marginBottom: 4 }}
              />
              <Text type="secondary" style={{ fontSize: 10 }}>{t('market_strategy.cumulative_investment')}: {fmt(cumulative)}</Text>
            </div>
            <div style={{ marginBottom: 8 }}>
              <Text style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>{t('market_strategy.this_rounds_investment')}:</Text>
              <InputNumber
                size="small" prefix="$" min={0} step={100000}
                value={complianceInvestment}
                disabled={locked}
                onChange={v => onComplianceChange(marketCode, v)}
                style={{ width: 180 }}
              />
            </div>
            {complianceInvestment > 0 && (
              <Card size="small" style={{ background: '#f8fafc', border: '1px dashed #d9d9d9' }}>
                <Text strong style={{ fontSize: 11 }}>{t('market_strategy.impact_preview')}:</Text>
                <div style={{ fontSize: 11, marginTop: 4 }}>
                  <div>{t('market_strategy.compliance_level')}: {(currentLevel * 100).toFixed(0)}% &rarr; {(projectedLevel * 100).toFixed(0)}% (+{(complianceGain * 100).toFixed(1)}%)</div>
                  {compMarket?.next_1m_compliance_gain && (
                    <div>{t('market_strategy.next_marginal_gain')}: +{(compMarket.next_1m_compliance_gain * 100).toFixed(1)}%</div>
                  )}
                </div>
              </Card>
            )}
            <Text type="secondary" style={{ fontSize: 10, display: 'block', marginTop: 8 }}>
              {t('market_strategy.compliance_desc')}
            </Text>
          </div>
        </Card>
      )}

      {/* Card 3: Stakeholder Impact Summary */}
      {!isHome && compMarket && (
        <Card size="small" title={<Text strong style={{ fontSize: 12 }}>{t('market_strategy.stakeholder_impact')} — {market.name}</Text>}>
          <div style={{ fontSize: 11 }}>
            <Text strong style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>{t('market_strategy.regulators')}:</Text>
            <Progress
              percent={Math.round(Math.min((currentLevel * 7 + (loc?.trust_multiplier || 1) * 3), 10) * 10)}
              size="small"
              strokeColor="#1677ff"
              style={{ marginBottom: 4 }}
            />
            <div style={{ paddingLeft: 8, marginBottom: 8 }}>
              <div>{t('market_strategy.compliance_label')}: +{(currentLevel * 3).toFixed(1)} ({(currentLevel * 100).toFixed(0)}% {t('market_strategy.level')})</div>
              {loc?.trust_multiplier != null && loc.trust_multiplier < 1 && (
                <div style={{ color: '#ff4d4f' }}>{t('market_strategy.origin_trust_label')}: {((1 - loc.trust_multiplier) * -3).toFixed(1)} ({t('market_strategy.distance_penalty')})</div>
              )}
            </div>

            <Text strong style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>{t('market_strategy.channel_partners')}:</Text>
            <div style={{ paddingLeft: 8 }}>
              <div>{t('market_strategy.compliance_investment')}: {currentLevel >= 0.5 ? t('market_strategy.positive_signal') : t('market_strategy.needs_improvement')}</div>
            </div>
          </div>
        </Card>
      )}
    </PanelCard>
  );
};

// CC-32D: Alliance Partner Health Card
const STATUS_CONFIG_KEYS = {
  HEALTHY: { color: '#52c41a', labelKey: 'market_strategy.status_healthy', icon: '✓' },
  STRAINED: { color: '#faad14', labelKey: 'market_strategy.status_strained', icon: '⚠' },
  RENEGOTIATING: { color: '#fa8c16', labelKey: 'market_strategy.status_renegotiating', icon: '⚠' },
  DISSOLVING: { color: '#ff4d4f', labelKey: 'market_strategy.status_dissolving', icon: '✕' },
  DISSOLVED: { color: '#8c8c8c', labelKey: 'market_strategy.status_dissolved', icon: '✕' },
};

const AllianceHealthCard = ({ alliances, dissolved, marketCode }) => {
  const { t } = useTranslation();
  const marketAlliances = alliances.filter(a => a.market_code === marketCode);
  const marketDissolved = dissolved.filter(d => d.market_code === marketCode);

  if (marketAlliances.length === 0 && marketDissolved.length === 0) return null;

  return (
    <PanelCard headerColor="market" title={`${t('market_strategy.partnership_health')} — ${marketAlliances[0]?.market_name || marketCode}`}>
      {marketAlliances.map(a => {
        const cfg = STATUS_CONFIG_KEYS[a.status] || STATUS_CONFIG_KEYS.HEALTHY;
        const satPct = Math.round(a.satisfaction * 100);
        const deliveryPct = Math.round(a.benefit_delivery_pct * 100);

        // Find weakest feature for advice
        const featureEntries = Object.entries(a.feature_satisfaction || {});
        featureEntries.sort((x, y) => x[1] - y[1]);
        const weakest = featureEntries[0];

        return (
          <Card key={a.id} size="small" style={{ marginBottom: 12, borderLeft: `3px solid ${cfg.color}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong style={{ fontSize: 12 }}>{a.partner_name} ({a.partner_type.replace('_', ' ')})</Text>
              <Space>
                <Tag color={cfg.color === '#52c41a' ? 'green' : cfg.color === '#faad14' ? 'gold' : cfg.color === '#fa8c16' ? 'orange' : cfg.color === '#ff4d4f' ? 'red' : 'default'}>
                  {cfg.icon} {t(cfg.labelKey)}
                </Tag>
                <Text style={{ fontSize: 12 }}>{t('dashboard.satisfaction')}: {satPct}%</Text>
              </Space>
            </div>

            <Progress
              percent={satPct}
              size="small"
              strokeColor={satPct >= 70 ? '#52c41a' : satPct >= 50 ? '#faad14' : '#ff4d4f'}
              style={{ marginBottom: 8 }}
            />

            {/* Feature breakdown — show if not healthy or if expanded */}
            {a.status !== 'HEALTHY' && a.preferences && (
              <div style={{ fontSize: 11, marginBottom: 8 }}>
                <Text type="secondary" style={{ fontSize: 10, display: 'block', marginBottom: 4 }}>{t('market_strategy.what_they_care_about')}</Text>
                {a.preferences.map(p => {
                  const score = a.feature_satisfaction?.[p.feature] ?? 0.5;
                  const scorePct = Math.round(score * 100);
                  return (
                    <div key={p.feature} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                      <Text style={{ fontSize: 11 }}>{p.description} ({Math.round(p.weight * 100)}%)</Text>
                      <Text style={{ fontSize: 11, color: scorePct >= 70 ? '#52c41a' : scorePct >= 50 ? '#faad14' : '#ff4d4f' }}>
                        {scorePct}%
                      </Text>
                    </div>
                  );
                })}
              </div>
            )}

            <Text style={{ fontSize: 11 }}>{t('market_strategy.benefit_delivery')}: {deliveryPct}%</Text>

            {a.rounds_below_renegotiation > 0 && a.status === 'STRAINED' && (
              <div style={{ marginTop: 4, fontSize: 11, color: '#faad14' }}>
                {t('market_strategy.rounds_below_threshold', { count: a.rounds_below_renegotiation, remaining: a.patience_rounds - a.rounds_below_renegotiation })}
              </div>
            )}

            {weakest && weakest[1] < 0.5 && a.status !== 'HEALTHY' && (
              <div style={{ marginTop: 4, fontSize: 11, color: '#8c8c8c' }}>
                {t('market_strategy.biggest_gap')}: {weakest[0].replace(/_/g, ' ')} — {t('market_strategy.improve_hint')}
              </div>
            )}
          </Card>
        );
      })}

      {/* Renegotiation alerts */}
      {marketAlliances.filter(a => a.status === 'RENEGOTIATING').map(a => (
        <Alert
          key={`reneg-${a.id}`}
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${t('market_strategy.partnership_renegotiation')} — ${a.partner_name}`}
          description={
            <div style={{ fontSize: 12 }}>
              {(a.renegotiation_demands || []).map((d, i) => (
                <div key={i} style={{ marginBottom: 4 }}>
                  <Text strong>{i + 1}. {d.description}</Text>
                  <div style={{ paddingLeft: 16, color: '#8c8c8c' }}>{d.requirement}</div>
                </div>
              ))}
              <div style={{ marginTop: 8, fontStyle: 'italic' }}>
                {t('market_strategy.benefits_frozen')}
              </div>
            </div>
          }
        />
      ))}

      {/* Dissolution notifications */}
      {marketDissolved.map(d => (
        <Alert
          key={`dissolved-${d.partner_name}`}
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${t('market_strategy.partnership_dissolved')} — ${d.partner_name}`}
          description={
            <div style={{ fontSize: 12 }}>
              <div>{t('market_strategy.dissolution_impact')}:</div>
              <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                <li>{t('market_strategy.dissolution_trust_shield')}</li>
                <li>{t('market_strategy.dissolution_compliance')}</li>
                <li>{t('market_strategy.dissolution_channel')}</li>
                <li>{t('market_strategy.dissolution_competitor')}</li>
              </ul>
              <div style={{ fontStyle: 'italic' }}>{t('market_strategy.dissolution_new_partner')}</div>
            </div>
          }
        />
      ))}
    </PanelCard>
  );
};


const MarketStrategyPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { draft, locked } = useDecisions();
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [marketEntries, setMarketEntries] = useState([]);
  const [plantDecisions, setPlantDecisions] = useState([]);
  const [partnerships, setPartnerships] = useState([]);
  const [complianceCtx, setComplianceCtx] = useState(null);
  const [localizationData, setLocalizationData] = useState({});
  const [allianceData, setAllianceData] = useState({ alliances: [], dissolved: [] });
  const [complianceInvestments, setComplianceInvestments] = useState({});
  const saveTimer = useRef(null);

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const [res, compRes, allianceRes] = await Promise.all([
        getStrategyContext(gameId, teamId),
        getComplianceContext(gameId, teamId).catch(() => null),
        getAllianceState(gameId, teamId).catch(() => null),
      ]);
      setContext(res.data);
      if (compRes?.data) {
        setComplianceCtx(compRes.data);
        // Initialize compliance investments from draft
        const inv = {};
        (compRes.data.markets || []).forEach(m => {
          inv[m.code] = draft?.compliance_investments?.[m.code] || 0;
        });
        setComplianceInvestments(inv);
      }
      if (allianceRes?.data) {
        setAllianceData(allianceRes.data);
      }
      if (draft?.market_entries) setMarketEntries(draft.market_entries);
      if (draft?.plant_decisions) setPlantDecisions(draft.plant_decisions);
      if (draft?.partnerships) setPartnerships(draft.partnerships);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId, draft]);

  useEffect(() => { loadContext(); }, [loadContext]);

  const autoSave = useCallback((section, data) => {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!gameId || !teamId || !currentRound || locked) return;
      setSaving(true);
      try {
        await patchDecision(gameId, teamId, currentRound, section, data);
        refreshBudgets();
      } catch { /* ignore */ }
      setSaving(false);
    }, 2000);
  }, [gameId, teamId, currentRound, locked, refreshBudgets]);

  const loadLocalization = useCallback(async (marketCode) => {
    if (!gameId || !teamId || localizationData[marketCode]) return;
    try {
      const res = await getMarketLocalization(gameId, teamId, marketCode);
      setLocalizationData(prev => ({ ...prev, [marketCode]: res.data }));
    } catch (err) {
      console.error(`Failed to load localization for ${marketCode}:`, err);
    }
  }, [gameId, teamId, localizationData]);

  const handleComplianceChange = useCallback((marketCode, value) => {
    setComplianceInvestments(prev => {
      const next = { ...prev, [marketCode]: value || 0 };
      autoSave('compliance_investments', { compliance_investments: next });
      return next;
    });
  }, [autoSave]);

  if (loading) return <LoadingSpinner />;
  if (!context) return <Alert message={t('market_strategy.unable_to_load')} type="error" />;

  const markets = context.markets || [];
  const entryModes = context.entry_modes || [];
  const strategyOptions = context.strategy_options || [];
  const existingPartnerships = context.partnerships || [];
  const plants = context.plants || [];

  const renderMarketContent = (m) => {
    const hasPresence = m.entry_status === 'active';
    const plant = plants.find(p => p.market_id === m.id);
    const marketPartnerships = existingPartnerships.filter(p => p.market_id === m.id);

    if (!hasPresence) {
      // Market entry section
      return (
        <PanelCard headerColor="decision" title={t('market_strategy.enter_market', { market: m.name.toUpperCase() })}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
            {t('market_strategy.choose_entry_mode', { market: m.name })}:
          </Text>
          {entryModes.map(em => {
            const isSelected = marketEntries.some(e => e.market === m.id && e.entry_mode === em.id);
            return (
              <Card
                key={em.id}
                size="small"
                hoverable={!locked}
                style={{ marginBottom: 8, borderColor: isSelected ? '#1677ff' : undefined }}
                onClick={() => {
                  if (locked) return;
                  const newEntry = {
                    market: m.id,
                    entry_mode: em.id,
                    action: 'enter',
                    initial_investment: Number(em.capital_requirement || 0),
                  };
                  const updated = [...marketEntries.filter(e => e.market !== m.id), newEntry];
                  setMarketEntries(updated);
                  autoSave('market-entry', { market_entries: updated });
                }}
              >
                <Row>
                  <Col flex="auto">
                    <Text strong>{em.name}</Text>
                    {isSelected && <Tag color="blue" style={{ marginLeft: 8 }}>{t('market_strategy.selected')}</Tag>}
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {fmt(em.capital_requirement)} — {em.setup_rounds === 0 ? t('market_strategy.immediate') : t('market_strategy.round_setup', { rounds: em.setup_rounds })}
                    </Text>
                  </Col>
                  <Col>
                    <Space>
                      <Tag>{t('market_strategy.control')}: {em.control_level}/10</Tag>
                      <Tag>{t('market_strategy.risk')}: {em.risk_level}/10</Tag>
                    </Space>
                  </Col>
                </Row>
                {/* CC-31B: Entry mode consequences */}
                <div style={{ marginTop: 6, fontSize: 11 }}>
                  {(em.name || '').toLowerCase().includes('joint venture') && (
                    <>
                      <Text type="warning" style={{ fontSize: 11 }}>{t('market_strategy.ip_exposure_jv')}</Text>
                      <br />
                      <Text style={{ fontSize: 11, color: '#52c41a' }}>{t('market_strategy.trust_shield_jv')}</Text>
                    </>
                  )}
                  {(em.name || '').toLowerCase().includes('licens') && (
                    <>
                      <Text type="warning" style={{ fontSize: 11 }}>{t('market_strategy.ip_exposure_license')}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>{t('market_strategy.trust_shield_none')}</Text>
                    </>
                  )}
                  {(em.name || '').toLowerCase().includes('subsidiar') && (
                    <>
                      <Text style={{ fontSize: 11, color: '#52c41a' }}>{t('market_strategy.ip_exposure_subsidiary')}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>{t('market_strategy.trust_shield_subsidiary')}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 10 }}>{t('market_strategy.subsidiary_hint')}</Text>
                    </>
                  )}
                  {(em.name || '').toLowerCase().includes('export') && (
                    <>
                      <Text style={{ fontSize: 11, color: '#52c41a' }}>{t('market_strategy.ip_exposure_export')}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>{t('market_strategy.trust_shield_export')}</Text>
                    </>
                  )}
                  {(em.name || '').toLowerCase().includes('acquisition') && (
                    <>
                      <Text style={{ fontSize: 11, color: '#52c41a' }}>{t('market_strategy.ip_exposure_acquisition')}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>{t('market_strategy.trust_shield_acquisition')}</Text>
                    </>
                  )}
                </div>
                {isSelected && (
                  <Card size="small" style={{ marginTop: 8, background: '#f8fafc', border: '1px dashed #d9d9d9' }}>
                    <Text strong style={{ fontSize: 12 }}>{t('market_strategy.entry_impact')}</Text>
                    <Row gutter={16} style={{ marginTop: 4 }}>
                      <Col span={12}>
                        <div style={{ fontSize: 12 }}>
                          <div>{t('market_strategy.initial_investment')}: {fmt(em.capital_requirement)}</div>
                          <div>{t('market_strategy.setup_time')}: {em.setup_rounds === 0 ? t('market_strategy.immediate_active') : `${em.setup_rounds} round${em.setup_rounds > 1 ? 's' : ''}`}</div>
                          {m.tariff_rate > 0 && <div>{t('market_strategy.tariff_applies', { pct: (m.tariff_rate * 100).toFixed(0) })}</div>}
                        </div>
                      </Col>
                      <Col span={12}>
                        <div style={{ fontSize: 12 }}>
                          <div>{t('market_strategy.market_size')}: {m.total_consumers?.toLocaleString() || '—'} {t('market_strategy.consumers')}</div>
                          <div>{t('market_strategy.growth')}: {m.growth_rate ? `${(m.growth_rate * 100).toFixed(0)}%` : '—'}</div>
                          {m.total_consumers > 0 && (
                            <div>{t('market_strategy.share_estimate', { revenue: fmt(m.total_consumers * 0.05 * (m.avg_price || 300)) })}</div>
                          )}
                        </div>
                      </Col>
                    </Row>
                  </Card>
                )}
              </Card>
            );
          })}
        </PanelCard>
      );
    }

    // Active market sections
    return (
      <>
        {/* Market Entry Status */}
        <PanelCard headerColor="market" title={t('market_strategy.market_entry')}>
          <Space>
            <Tag color="green">{t('market_strategy.active')}</Tag>
            <Text>{t('market_strategy.entry_mode')}: {m.entry_mode || 'Export'}</Text>
          </Space>
          {/* CC-31B: IP exposure for JV/licensing */}
          {(m.entry_mode || '').toLowerCase().includes('joint venture') && (
            <div style={{ marginTop: 8, padding: '6px 8px', background: '#fff7e6', borderRadius: 4, fontSize: 11 }}>
              <Text type="warning">{t('market_strategy.ip_exposure_jv')}</Text>
              <br />
              <Text style={{ fontSize: 11, color: '#52c41a' }}>{t('market_strategy.trust_shield_jv_active')}</Text>
            </div>
          )}
          {(m.entry_mode || '').toLowerCase().includes('licens') && (
            <div style={{ marginTop: 8, padding: '6px 8px', background: '#fff1f0', borderRadius: 4, fontSize: 11 }}>
              <Text type="danger">{t('market_strategy.ip_exposure_license')}</Text>
            </div>
          )}
          {!locked && (
            <div style={{ marginTop: 8 }}>
              <Button
                size="small"
                danger
                onClick={() => {
                  const updated = [...marketEntries.filter(e => e.market !== m.id),
                    { market: m.id, action: 'exit', entry_mode: entryModes[0]?.id, initial_investment: 0 }];
                  setMarketEntries(updated);
                  autoSave('market-entry', { market_entries: updated });
                }}
              >
                {t('market_strategy.exit_market')}
              </Button>
            </div>
          )}
        </PanelCard>

        {/* Production Capacity */}
        {m.allows_manufacturing && (
          <PanelCard headerColor="strategic" title={t('market_strategy.production_capacity')}>
            {plant ? (
              <div>
                <Row gutter={[16, 8]}>
                  <Col xs={12}>
                    <Statistic
                      title={t('market_strategy.own_plant')}
                      value={plant.status === 'operational' ? `${plant.capacity_units} ${t('market_strategy.units')}` : t('market_strategy.under_construction')}
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Col>
                  <Col xs={12}>
                    <Tag color={plant.status === 'operational' ? 'green' : 'orange'}>
                      {plant.status}
                    </Tag>
                  </Col>
                </Row>
              </div>
            ) : (
              <div>
                <Text type="secondary">{t('market_strategy.no_plant')} — </Text>
                {!locked && (
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => {
                      const pd = [...plantDecisions, { market: m.id, action: 'build', capacity_units: 0, contract_mfg_volume: 0 }];
                      setPlantDecisions(pd);
                      autoSave('plants', { plant_decisions: pd });
                    }}
                  >
                    {t('market_strategy.build_plant')} — {fmt(m.plant_build_cost)}, {t('market_strategy.build_plant_detail', { rounds: m.plant_build_rounds || 2, units: m.plant_capacity_units || 50000 })}
                  </Button>
                )}
              </div>
            )}
            {m.contract_mfg_available && (
              <div style={{ marginTop: 8, padding: '6px 8px', background: '#f8fafc', borderRadius: 4, fontSize: 11 }}>
                <Text type="secondary">
                  {t('market_strategy.contract_mfg_desc', { units: m.contract_mfg_capacity_cap || 30000, premium: Math.round((Number(m.contract_mfg_cost_multiplier || 1.25) - 1) * 100) })}
                </Text>
              </div>
            )}
          </PanelCard>
        )}

        {/* Partnerships */}
        <PanelCard headerColor="decision" title={t('market_strategy.partnerships')}>
          {marketPartnerships.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              {marketPartnerships.map(p => (
                <Tag key={p.id} color="blue" style={{ marginBottom: 4 }}>
                  {p.strategy_option_name} — {fmt(p.annual_investment)}/round
                </Tag>
              ))}
            </div>
          )}
          {!locked && (
            <Space wrap>
              {strategyOptions.map(so => (
                <Button
                  key={so.id}
                  size="small"
                  onClick={() => {
                    const updated = [...partnerships, {
                      market: m.id,
                      strategy_option: so.id,
                      annual_investment: Number(so.capital_cost_base || 0),
                      action: 'establish',
                    }];
                    setPartnerships(updated);
                    autoSave('partnerships', { partnerships: updated });
                  }}
                >
                  + {so.name} — {fmt(so.capital_cost_base)} + {fmt(so.recurring_cost_per_round)}/round
                </Button>
              ))}
            </Space>
          )}
        </PanelCard>

        {/* CC-32D: Alliance Partner Health */}
        <AllianceHealthCard
          alliances={allianceData.alliances || []}
          dissolved={allianceData.dissolved || []}
          marketCode={m.code}
        />

        {/* Market Operations — CC-31B */}
        <MarketOperationsSection
          market={m}
          complianceCtx={complianceCtx}
          localizationData={localizationData}
          loadLocalization={loadLocalization}
          complianceInvestment={complianceInvestments[m.code] || 0}
          onComplianceChange={handleComplianceChange}
          locked={locked}
        />
      </>
    );
  };

  const tabItems = markets.map(m => {
    const hasPresence = m.entry_status === 'active';
    return {
      key: String(m.id),
      label: (
        <span>
          {m.name} {hasPresence ? <Tag color="green" style={{ fontSize: 10, marginLeft: 4 }}>{t('market_strategy.active')}</Tag> : <Tag style={{ fontSize: 10, marginLeft: 4 }}>{t('market_strategy.not_entered')}</Tag>}
        </span>
      ),
      children: renderMarketContent(m),
    };
  });

  return (
    <div>
      <PageHeader
        title={t('market_strategy.title')}
        subtitle={`${t('common.round')} ${currentRound} · ${t('market_strategy.subtitle')}`}
        status={locked ? 'locked' : 'draft'}
        actions={saving ? <Tag color="processing">{t('market_strategy.saving')}</Tag> : null}
      />

      <Tabs className="ds-colored-tabs" items={tabItems} />
    </div>
  );
};

export default MarketStrategyPage;
