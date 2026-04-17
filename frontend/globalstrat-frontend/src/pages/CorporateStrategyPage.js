import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Typography, InputNumber, Row, Col, Checkbox, Space, Tag, Alert, Select, Progress, Tabs, Button, Descriptions, Divider, Empty, Collapse, Tooltip, Table, Modal } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { useAuth } from '../AuthContext';
import { getStrategyContext, getTalentContext, getTalentAllocationContext, getGovernanceContext, patchDecision, getOrgStructureContext, switchOrgStructure } from '../api/decisions';
import { PanelCard, PageHeader } from '../components/design-system';
import LoadingSpinner from '../components/LoadingSpinner';
import TeamActivityBanner from '../components/TeamActivityBanner';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const getSalaryOptions = (t) => [
  { level: 1, label: `${t('corporate_strategy.salary_below_market')} ($60K/${t('common.yr')})`, quarterly: 15000 },
  { level: 2, label: `${t('corporate_strategy.salary_market_rate')} ($90K/${t('common.yr')})`, quarterly: 22500 },
  { level: 3, label: `${t('corporate_strategy.salary_above_market')} ($120K/${t('common.yr')})`, quarterly: 30000 },
  { level: 4, label: `${t('corporate_strategy.salary_premium')} ($160K/${t('common.yr')})`, quarterly: 40000 },
  { level: 5, label: `${t('corporate_strategy.salary_top_market')} ($220K/${t('common.yr')})`, quarterly: 55000 },
];

const POOL_CONFIG = {
  rd: { labelKey: 'corporate_strategy.rd_team', optimalRange: [48, 72] },
  commercial: { labelKey: 'corporate_strategy.sales_marketing_team', optimalRange: [32, 48] },
  operations: { labelKey: 'corporate_strategy.operations_team', optimalRange: [40, 60] },
};

const prevStyle = { fontSize: 9, fontStyle: 'italic', color: '#8c8c8c', display: 'block' };

const DISTANCE_COLORS = { LOW: '#52c41a', MEDIUM: '#faad14', HIGH: '#fa8c16', 'VERY HIGH': '#ff4d4f', HOME: '#1677ff' };
const getDistanceLabels = (t) => ({ LOW: t('corporate_strategy.dist_low'), MEDIUM: t('corporate_strategy.dist_med'), HIGH: t('corporate_strategy.dist_high'), 'VERY HIGH': t('corporate_strategy.dist_very_high'), HOME: t('corporate_strategy.dist_home') });

const multColor = (v) => v >= 4.0 ? '#52c41a' : v >= 3.0 ? '#faad14' : '#ff4d4f';

const StaffAllocationSection = ({ poolKey, headcount, markets, allocations, locked, onAllocChange }) => {
  const { t } = useTranslation();
  const DISTANCE_LABELS = getDistanceLabels(t);
  const total = Object.values(allocations).reduce((s, v) => s + (v || 0), 0);
  const hqCount = (allocations.hq || 0);
  const balanced = total === headcount;
  const remaining = headcount - total;

  const summaryText = markets.length > 0
    ? `HQ: ${hqCount}` + markets.map(m => ` | ${m.code}: ${allocations[m.code] || 0}`).join('')
    : t('corporate_strategy.not_configured');

  return (
    <Collapse
      ghost
      size="small"
      style={{ marginTop: 4 }}
      items={[{
        key: '1',
        label: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
            <Text type="secondary">{t('corporate_strategy.staff_allocation')}</Text>
            <span style={{ fontSize: 10, color: balanced ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
              {total} {t('corporate_strategy.of')} {headcount} {balanced ? '✓' : '⚠'}
            </span>
            <Text type="secondary" style={{ fontSize: 10 }}>{summaryText}</Text>
          </div>
        ),
        children: (
          <div>
            {!balanced && (
              <Alert
                type="warning" showIcon
                message={`${t('corporate_strategy.allocate_all_staff', { count: headcount })} ${Math.abs(remaining)} ${remaining > 0 ? t('corporate_strategy.unassigned') : t('corporate_strategy.over_assigned')}.`}
                style={{ marginBottom: 8, fontSize: 11 }}
                banner
              />
            )}
            <Row gutter={8} align="top" style={{ flexWrap: 'wrap' }}>
              {/* HQ allocation */}
              <Col style={{ textAlign: 'center', minWidth: 80, marginBottom: 8 }}>
                <Text style={{ fontSize: 10, display: 'block', fontWeight: 600 }}>HQ</Text>
                <InputNumber
                  size="small" min={0} max={headcount}
                  value={hqCount} disabled={locked}
                  onChange={v => onAllocChange({ ...allocations, hq: v || 0 })}
                  style={{ width: 64 }}
                />
                {headcount > 0 && (
                  <Progress
                    percent={Math.round((hqCount / headcount) * 100)}
                    showInfo={false} size="small"
                    strokeColor="#1E3A5F"
                    style={{ width: 64, margin: '2px auto 0' }}
                  />
                )}
              </Col>
              {/* Market allocations */}
              {markets.map(m => {
                const isHome = m.is_home_market;
                const isActive = m.code !== undefined;
                const val = allocations[m.code] || 0;
                return (
                  <Col key={m.code} style={{ textAlign: 'center', minWidth: 80, marginBottom: 8 }}>
                    <Text style={{ fontSize: 10, display: 'block', fontWeight: 600 }}>
                      {isHome && '🏠 '}{m.code}
                    </Text>
                    {!isHome && m.distance_level && (
                      <Text style={{ fontSize: 9, color: DISTANCE_COLORS[m.distance_level] || '#8c8c8c', display: 'block' }}>
                        {DISTANCE_LABELS[m.distance_level] || m.distance_level}
                      </Text>
                    )}
                    <Tooltip title={!isActive ? t('corporate_strategy.enter_market_first') : ''}>
                      <InputNumber
                        size="small" min={0} max={headcount}
                        value={val} disabled={locked || !isActive}
                        onChange={v => onAllocChange({ ...allocations, [m.code]: v || 0 })}
                        style={{ width: 64, opacity: isActive ? 1 : 0.4 }}
                      />
                    </Tooltip>
                    {headcount > 0 && (
                      <Progress
                        percent={Math.round((val / headcount) * 100)}
                        showInfo={false} size="small"
                        strokeColor="#52c41a"
                        style={{ width: 64, margin: '2px auto 0' }}
                      />
                    )}
                  </Col>
                );
              })}
            </Row>
            {/* Effective multipliers row */}
            {markets.length > 0 && (
              <div style={{ marginTop: 4, fontSize: 10, color: '#595959' }}>
                <Text type="secondary" style={{ fontSize: 10 }}>{t('market_strategy.effective_multiplier')}: </Text>
                {markets.map(m => {
                  const mult = m.is_home_market
                    ? m.base_effectiveness || 1.0
                    : (m[`effective_${poolKey}_multiplier`] || m.base_effectiveness || 1.0);
                  const label = m.is_home_market ? `${m.code}: ${mult.toFixed(1)} (home)` : `${m.code}: ${mult.toFixed(1)}`;
                  return (
                    <span key={m.code} style={{ marginRight: 12, color: multColor(mult) }}>{label}</span>
                  );
                })}
              </div>
            )}
          </div>
        ),
      }]}
    />
  );
};

const TalentPoolCard = ({ pool, poolKey, talent, locked, onChange, prev, markets, allocations, onAllocChange }) => {
  const { t } = useTranslation();
  const SALARY_OPTIONS = getSalaryOptions(t);
  const config = POOL_CONFIG[poolKey];
  const salaryOpt = SALARY_OPTIONS.find(s => s.level === talent.salary_level) || SALARY_OPTIONS[2];
  const salaryCost = talent.headcount * salaryOpt.quarterly;
  const trainingCost = talent.training_budget || 0;

  const turnoverColor = talent.turnover_rate < 0.10 ? '#52c41a' : talent.turnover_rate < 0.20 ? '#faad14' : '#ff4d4f';
  const levelPct = (talent.current_level / 10) * 100;
  const hcInRange = talent.headcount >= config.optimalRange[0] && talent.headcount <= config.optimalRange[1];

  const delta = talent.current_level - 3;
  let effectPct;
  if (poolKey === 'rd') effectPct = (delta * 5).toFixed(0);
  else if (poolKey === 'commercial') effectPct = (delta * 8).toFixed(0);
  else effectPct = (delta * 4).toFixed(0);

  const titleContent = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <span>{t(config.labelKey)}</span>
      <Progress percent={levelPct} showInfo={false} strokeColor="#1677ff" size="small" style={{ width: 80, margin: 0 }} />
      <Text type="secondary" style={{ fontSize: 10, whiteSpace: 'nowrap' }}>{talent.current_level.toFixed(1)}/10</Text>
      <Tag style={{ margin: 0 }} color={turnoverColor === '#52c41a' ? 'success' : turnoverColor === '#faad14' ? 'warning' : 'error'}>
        {(talent.turnover_rate * 100).toFixed(0)}% {t('corporate_strategy.turnover')}
      </Tag>
    </div>
  );

  return (
    <Card
      size="small"
      title={titleContent}
      extra={<Text type="secondary" style={{ fontSize: 10 }}>{fmt(salaryCost)} + {fmt(trainingCost)} {t('corporate_strategy.training_investment').toLowerCase()} | {Number(effectPct) >= 0 ? '+' : ''}{effectPct}%</Text>}
      style={{ marginBottom: 8 }}
      styles={{ body: { paddingTop: 8, paddingBottom: 8 } }}
    >
      <Row gutter={12} align="top">
        <Col flex="140px">
          <Text style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>{t('corporate_strategy.headcount')}</Text>
          <InputNumber
            size="small" min={0} max={200} step={5}
            value={talent.headcount} disabled={locked}
            onChange={v => onChange({ ...talent, headcount: v || 0 })}
            style={{ width: '100%' }}
          />
          <Text type={hcInRange ? 'secondary' : 'warning'} style={{ fontSize: 10 }}>
            {t('corporate_strategy.optimal')}: {config.optimalRange[0]}-{config.optimalRange[1]}
          </Text>
          {prev && prev.headcount > 0 && <Text style={prevStyle}>{t('corporate_strategy.last')}: {prev.headcount}</Text>}
        </Col>
        <Col flex="180px">
          <Text style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>{t('corporate_strategy.salary_level')}</Text>
          <Select
            size="small"
            value={talent.salary_level} disabled={locked}
            onChange={v => onChange({ ...talent, salary_level: v })}
            style={{ width: '100%' }}
          >
            {SALARY_OPTIONS.map(s => (
              <Select.Option key={s.level} value={s.level}>{s.label}</Select.Option>
            ))}
          </Select>
          {prev && <Text style={prevStyle}>{t('corporate_strategy.last')}: {SALARY_OPTIONS.find(s => s.level === prev.salary_level)?.label || `Level ${prev.salary_level}`}</Text>}
        </Col>
        <Col flex="160px">
          <Text style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>{t('corporate_strategy.training_investment')}</Text>
          <InputNumber
            size="small" prefix="$" min={0} step={50000}
            value={talent.training_budget} disabled={locked}
            onChange={v => onChange({ ...talent, training_budget: v || 0 })}
            style={{ width: '100%' }}
          />
          {prev && prev.cumulative_training > 0 && <Text style={prevStyle}>{t('corporate_strategy.cumulative')}: {fmt(prev.cumulative_training)}</Text>}
        </Col>
      </Row>
      {markets && markets.length > 0 && (
        <StaffAllocationSection
          poolKey={poolKey}
          headcount={talent.headcount}
          markets={markets}
          allocations={allocations || {}}
          locked={locked}
          onAllocChange={onAllocChange}
        />
      )}
    </Card>
  );
};

const AcquisitionTargetCard = ({ target, locked, onAcquire, pendingAcquire }) => {
  const { t } = useTranslation();
  const isAvailable = target.available;
  const isAcquiredBySelf = target.acquired_by_self;

  return (
    <Card
      size="small"
      style={{
        marginBottom: 12,
        borderColor: isAcquiredBySelf ? '#52c41a' : isAvailable ? '#1677ff' : '#d9d9d9',
        opacity: (!isAvailable && !isAcquiredBySelf) ? 0.7 : 1,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
        <div>
          <Text strong>{target.target_name}</Text>
          <Tag style={{ marginLeft: 8 }} color="blue">{target.market_name}</Tag>
          {isAcquiredBySelf && <Tag color="green">{t('corporate_strategy.acquired')}</Tag>}
          {target.acquired_by_team && !isAcquiredBySelf && <Tag color="red">{t('corporate_strategy.acquired_by', { team: target.acquired_by_team })}</Tag>}
        </div>
        <Text strong style={{ fontSize: 16, color: '#1677ff' }}>{fmt(target.base_acquisition_cost)}</Text>
      </div>

      <Text type="secondary" style={{ display: 'block', margin: '8px 0', fontSize: 12 }}>
        {target.description}
      </Text>

      <Row gutter={16} style={{ marginTop: 8 }}>
        <Col span={12}>
          <Text style={{ fontSize: 12, fontWeight: 600 }}>{t('corporate_strategy.you_get')}</Text>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            <div>{(target.market_share_gained * 100).toFixed(0)}% {t('corporate_strategy.market_share_after_integration')}</div>
            {target.includes_plant && <div>{t('corporate_strategy.plant')}: {target.plant_capacity.toLocaleString()} {t('corporate_strategy.unit_capacity_immediate')}</div>}
            {target.includes_distribution && <div>{t('corporate_strategy.distribution_reach')}: +{(target.distribution_reach_bonus * 100).toFixed(0)}%</div>}
            {target.talent_bonus && Object.entries(target.talent_bonus).map(([pool, bonus]) => (
              <div key={pool}>{pool.charAt(0).toUpperCase() + pool.slice(1)} {t('corporate_strategy.talent_label')}: +{bonus} {t('corporate_strategy.level')}</div>
            ))}
          </div>
        </Col>
        <Col span={12}>
          <Text style={{ fontSize: 12, fontWeight: 600 }}>{t('corporate_strategy.integration')}</Text>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            <div>{target.integration_rounds} {t('corporate_strategy.rounds_to_integrate')}</div>
            <div>{fmt(target.integration_cost_per_round)}/{t('common.round').toLowerCase()} {t('corporate_strategy.integration_cost_label')}</div>
            <div>{t('corporate_strategy.total_cost_label')}: {fmt(target.base_acquisition_cost + target.integration_cost_per_round * target.integration_rounds)}</div>
          </div>
        </Col>
      </Row>

      {target.locked_reasons.length > 0 && !isAcquiredBySelf && (
        <div style={{ marginTop: 8 }}>
          <Text style={{ fontSize: 11 }}>{t('corporate_strategy.requirements')}</Text>
          {target.locked_reasons.map((reason, i) => (
            <Tag key={i} color="default" style={{ fontSize: 11, marginTop: 4 }}>{reason}</Tag>
          ))}
        </div>
      )}

      {isAvailable && !isAcquiredBySelf && (
        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <Text type="warning" style={{ fontSize: 11, marginRight: 12 }}>
            {t('corporate_strategy.first_team_warning')}
          </Text>
          <Button
            type="primary"
            size="small"
            disabled={locked || pendingAcquire}
            onClick={() => onAcquire(target.id)}
          >
            {pendingAcquire ? t('corporate_strategy.queued_acquisition') : `${t('corporate_strategy.acquire')} — ${fmt(target.base_acquisition_cost)}`}
          </Button>
        </div>
      )}
    </Card>
  );
};

const MnATab = ({ context, locked, autoSave, draft }) => {
  const { t } = useTranslation();
  const targets = context.acquisition_targets || [];
  const teamAcquisitions = context.team_acquisitions || [];

  // Track which target is queued in the current draft
  const draftAcquisitions = draft?.acquisitions || [];
  const pendingTargetIds = new Set(draftAcquisitions.map(a => a.acquisition_target));

  const handleAcquire = (targetId) => {
    const newAcquisitions = [...draftAcquisitions, { acquisition_target: targetId }];
    autoSave('acquisitions', { acquisitions: newAcquisitions });
  };

  return (
    <PanelCard headerColor="decision" title={t('corporate_strategy.mergers_acquisitions')}>
      <Title level={5} style={{ marginBottom: 12 }}>{t('corporate_strategy.available_targets')}</Title>
      {targets.length === 0 ? (
        <Empty description={t('corporate_strategy.no_targets')} />
      ) : (
        targets.map(t => (
          <AcquisitionTargetCard
            key={t.id}
            target={t}
            locked={locked}
            onAcquire={handleAcquire}
            pendingAcquire={pendingTargetIds.has(t.id)}
          />
        ))
      )}

      {teamAcquisitions.length > 0 && (
        <>
          <Divider />
          <Title level={5} style={{ marginBottom: 12 }}>{t('corporate_strategy.your_acquisitions')}</Title>
          {teamAcquisitions.map(acq => (
            <Card key={acq.id} size="small" style={{ marginBottom: 8, borderColor: acq.integration_complete ? '#52c41a' : '#faad14' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text strong>{acq.target_name}</Text>
                  <Tag style={{ marginLeft: 8 }}>{acq.market_name}</Tag>
                  {acq.integration_complete ? (
                    <Tag color="success">{t('corporate_strategy.integration_complete')}</Tag>
                  ) : (
                    <Tag color="warning">{t('corporate_strategy.rounds_remaining', { count: acq.integration_rounds_remaining })}</Tag>
                  )}
                </div>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('corporate_strategy.acquired_round', { round: acq.acquired_round })}</Text>
              </div>
              <Row gutter={16} style={{ marginTop: 8, fontSize: 12 }}>
                <Col span={8}>{t('corporate_strategy.cost_paid')}: {fmt(acq.total_cost_paid)}</Col>
                {acq.includes_plant && <Col span={8}>{t('corporate_strategy.plant_label')}: {acq.plant_capacity.toLocaleString()} {t('corporate_strategy.units_label')}</Col>}
                <Col span={8}>
                  {t('corporate_strategy.share_boost')}: {(acq.market_share_gained * 100).toFixed(0)}%
                  {!acq.integration_complete && <Text type="secondary"> ({t('corporate_strategy.pending_integration')})</Text>}
                </Col>
              </Row>
              {!acq.integration_complete && (
                <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
                  {t('corporate_strategy.integration_cost_round', { cost: fmt(acq.integration_cost_per_round) })}
                </Text>
              )}
            </Card>
          ))}
        </>
      )}
    </PanelCard>
  );
};

const ModifierTag = ({ value, label, positive }) => {
  const pct = Math.round((value - 1) * 100);
  if (pct === 0) return null;
  const color = (positive ? pct > 0 : pct < 0) ? '#52c41a' : pct === 0 ? '#8c8c8c' : '#ff4d4f';
  const prefix = pct > 0 ? '+' : '';
  return <span style={{ fontSize: 11, color, marginRight: 10 }}>{label}: {prefix}{pct}%</span>;
};

const OrgStructureTab = ({ orgCtx, locked, gameId, teamId, onRefresh }) => {
  const { t } = useTranslation();
  const [switchTarget, setSwitchTarget] = useState(null);
  const [switching, setSwitching] = useState(false);

  if (!orgCtx || !orgCtx.structures || orgCtx.structures.length === 0) {
    return <PanelCard headerColor="strategic" title={t('corporate_strategy.org_structure')}><Empty description={t('corporate_strategy.no_org_structures')} /></PanelCard>;
  }

  const { structures, current_structure, active_markets, transitioning, transition_rounds_remaining, transitioning_from } = orgCtx;

  const handleSwitch = async (structure) => {
    setSwitching(true);
    try {
      await switchOrgStructure(gameId, teamId, structure.id);
      onRefresh();
      setSwitchTarget(null);
    } catch (err) {
      Modal.error({
        title: t('corporate_strategy.switch_failed'),
        content: err.response?.data?.error || t('corporate_strategy.unable_switch'),
      });
    }
    setSwitching(false);
  };

  // Cost comparison table data
  const costColumns = [
    { title: t('corporate_strategy.structure'), dataIndex: 'name', key: 'name', render: (v, r) => <Text strong={r.is_current}>{v}{r.is_current ? ` (${t('corporate_strategy.selected').toLowerCase()})` : ''}</Text> },
    { title: t('corporate_strategy.base'), dataIndex: 'base_overhead_per_round', key: 'base', render: v => fmt(v) },
    { title: `${t('corporate_strategy.coord')} (${active_markets} mkt)`, dataIndex: 'coordination_cost', key: 'coord', render: v => fmt(v) },
    { title: t('corporate_strategy.overext'), dataIndex: 'overextension_cost', key: 'overext', render: v => v > 0 ? <Text type="danger">{fmt(v)}</Text> : '$0' },
    { title: t('corporate_strategy.total_per_round'), dataIndex: 'total_cost_per_round', key: 'total', render: (v, r) => <Text strong type={r.is_current ? undefined : 'secondary'}>{fmt(v)}</Text> },
  ];

  return (
    <PanelCard headerColor="strategic" title={t('corporate_strategy.org_structure')} actions={current_structure ? <Text type="secondary">{t('corporate_strategy.selected')}: {current_structure.name}</Text> : null}>
      {transitioning && (
        <Alert
          type="warning" showIcon
          style={{ marginBottom: 12 }}
          message={t('corporate_strategy.transitioning_message', { from: transitioning_from || t('corporate_strategy.previous_structure'), rounds: transition_rounds_remaining })}
        />
      )}

      {structures.map(s => {
        const isCurrent = s.is_current;
        return (
          <Card
            key={s.id}
            size="small"
            style={{
              marginBottom: 12,
              borderLeft: isCurrent ? '3px solid #1677ff' : '3px solid #d9d9d9',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 14 }}>{s.name}</Text>
                  {isCurrent && <Tag color="blue">{t('corporate_strategy.selected')}</Tag>}
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {fmt(s.base_overhead_per_round)} + {fmt(s.per_market_coordination_cost)}/mkt
                  </Text>
                </div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                  {s.description}
                </Text>
                <div style={{ marginBottom: 4 }}>
                  <ModifierTag value={s.hq_talent_effectiveness_modifier} label={t('corporate_strategy.hq_talent')} positive />
                  <ModifierTag value={s.local_talent_effectiveness_modifier} label={t('corporate_strategy.local_talent')} positive />
                  <ModifierTag value={s.innovation_modifier} label={t('corporate_strategy.innovation')} positive />
                  <ModifierTag value={s.coordination_efficiency} label={t('corporate_strategy.coordination')} positive />
                  <ModifierTag value={s.decision_speed_modifier} label={t('corporate_strategy.speed')} positive />
                </div>
                <div style={{ fontSize: 11 }}>
                  <Text type="secondary">{t('corporate_strategy.optimal_markets', { min: s.optimal_market_range_min, max: s.optimal_market_range_max })}</Text>
                  {s.overextension_markets > 0 ? (
                    <Text type="danger" style={{ marginLeft: 8 }}>
                      {t('corporate_strategy.overextension_warning', { active: active_markets, over: s.overextension_markets, cost: fmt(s.overextension_cost), penalty: (s.overextension_effectiveness_penalty * s.overextension_markets * 100).toFixed(0) })}
                    </Text>
                  ) : (
                    s.within_optimal_range && <Text style={{ marginLeft: 8, color: '#52c41a', fontSize: 11 }}>{t('corporate_strategy.within_optimal', { count: active_markets })}</Text>
                  )}
                </div>
              </div>
              <div style={{ textAlign: 'right', minWidth: 160 }}>
                <Text strong style={{ fontSize: 14, display: 'block' }}>{fmt(s.total_cost_per_round)}/round</Text>
                {!isCurrent && (
                  <Button
                    type={s.within_optimal_range ? 'primary' : 'default'}
                    size="small"
                    disabled={locked || transitioning || switching}
                    onClick={() => setSwitchTarget(s)}
                    style={{ marginTop: 8 }}
                  >
                    {t('corporate_strategy.switch')} — {s.transition_cost > 0 ? fmt(s.transition_cost) : t('corporate_strategy.free')}
                  </Button>
                )}
                {!isCurrent && s.transition_disruption_rounds > 0 && (
                  <Text type="secondary" style={{ fontSize: 10, display: 'block', marginTop: 4 }}>
                    {s.transition_disruption_rounds} {t('corporate_strategy.rounds_disruption')}
                  </Text>
                )}
              </div>
            </div>
          </Card>
        );
      })}

      {/* Cost Comparison Table */}
      <Card size="small" style={{ marginTop: 8, background: '#f8fafc', border: '1px solid #d9e4f0' }}>
        <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>{t('corporate_strategy.cost_comparison')} ({active_markets} {t('corporate_strategy.active_markets')})</Text>
        <Table
          dataSource={structures}
          columns={costColumns}
          pagination={false}
          size="small"
          rowKey="id"
          rowClassName={r => r.is_current ? 'ant-table-row-selected' : ''}
          style={{ fontSize: 11 }}
        />
      </Card>

      {/* Transition Confirmation Modal */}
      <Modal
        title={t('corporate_strategy.switch_to', { name: switchTarget?.name }) + '?'}
        open={!!switchTarget}
        onCancel={() => setSwitchTarget(null)}
        footer={[
          <Button key="keep" onClick={() => setSwitchTarget(null)}>
            {current_structure?.name || t('corporate_strategy.selected')}
          </Button>,
          <Button
            key="switch" type="primary"
            loading={switching}
            onClick={() => handleSwitch(switchTarget)}
          >
            {t('corporate_strategy.switch_to', { name: switchTarget?.name })} {switchTarget?.transition_cost > 0 ? `— ${fmt(switchTarget.transition_cost)}` : ''}
          </Button>,
        ]}
      >
        {switchTarget && (
          <div>
            {switchTarget.transition_cost > 0 && (
              <p><strong>{t('corporate_strategy.one_time_cost')}</strong> {fmt(switchTarget.transition_cost)}</p>
            )}
            {switchTarget.transition_disruption_rounds > 0 && (
              <p><strong>{t('corporate_strategy.disruption')}:</strong> {switchTarget.transition_disruption_rounds} round{switchTarget.transition_disruption_rounds !== 1 ? 's' : ''}</p>
            )}
            <p><strong>{t('corporate_strategy.after_transition')}</strong></p>
            <ul style={{ fontSize: 13 }}>
              {switchTarget.hq_talent_effectiveness_modifier !== 1.0 && (
                <li>{t('corporate_strategy.hq_talent')}: {switchTarget.hq_talent_effectiveness_modifier > 1 ? '+' : ''}{Math.round((switchTarget.hq_talent_effectiveness_modifier - 1) * 100)}%</li>
              )}
              {switchTarget.local_talent_effectiveness_modifier !== 1.0 && (
                <li>{t('corporate_strategy.local_talent')}: {switchTarget.local_talent_effectiveness_modifier > 1 ? '+' : ''}{Math.round((switchTarget.local_talent_effectiveness_modifier - 1) * 100)}%</li>
              )}
              {switchTarget.innovation_modifier !== 1.0 && (
                <li>{t('corporate_strategy.innovation')}: {switchTarget.innovation_modifier > 1 ? '+' : ''}{Math.round((switchTarget.innovation_modifier - 1) * 100)}%</li>
              )}
              {switchTarget.coordination_efficiency !== 1.0 && (
                <li>{t('corporate_strategy.coordination')}: {switchTarget.coordination_efficiency > 1 ? '+' : ''}{Math.round((switchTarget.coordination_efficiency - 1) * 100)}%</li>
              )}
              {switchTarget.decision_speed_modifier !== 1.0 && (
                <li>{t('corporate_strategy.speed')}: {switchTarget.decision_speed_modifier > 1 ? '+' : ''}{Math.round((switchTarget.decision_speed_modifier - 1) * 100)}%</li>
              )}
            </ul>
            <p style={{ fontSize: 12, color: '#595959', fontStyle: 'italic' }}>
              {t('corporate_strategy.transition_warning')}
            </p>
          </div>
        )}
      </Modal>
    </PanelCard>
  );
};

const CorporateStrategyPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const navigate = useNavigate();
  const { draft, locked } = useDecisions();
  const { user } = useAuth();
  const [context, setContext] = useState(null);
  const [talentCtx, setTalentCtx] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [allocCtx, setAllocCtx] = useState(null);
  const [allocations, setAllocations] = useState({ rd: {}, commercial: {}, operations: {} });
  const [esg, setEsg] = useState({ environmental_investment: 0, social_investment: 0, governance_commitments: [] });
  const [govCtx, setGovCtx] = useState(null);
  const [orgCtx, setOrgCtx] = useState(null);
  const [revokeTarget, setRevokeTarget] = useState(null);
  const [talent, setTalent] = useState({
    rd: { headcount: 50, salary_level: 3, training_budget: 0, current_level: 3.0, turnover_rate: 0.08 },
    commercial: { headcount: 30, salary_level: 3, training_budget: 0, current_level: 3.0, turnover_rate: 0.08 },
    operations: { headcount: 40, salary_level: 3, training_budget: 0, current_level: 3.0, turnover_rate: 0.08 },
  });
  const saveTimer = useRef(null);

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const [stratRes, talentRes, allocRes, orgRes] = await Promise.all([
        getStrategyContext(gameId, teamId),
        getTalentContext(gameId, teamId).catch(() => null),
        getTalentAllocationContext(gameId, teamId).catch(() => null),
        getOrgStructureContext(gameId, teamId).catch(() => null),
      ]);
      setContext(stratRes.data);
      if (allocRes?.data) {
        setAllocCtx(allocRes.data);
        const da = allocRes.data.draft_allocations || {};
        setAllocations({
          rd: { hq: da.rd?.hq_count || 0, ...(da.rd?.market_allocation || {}) },
          commercial: { hq: da.commercial?.hq_count || 0, ...(da.commercial?.market_allocation || {}) },
          operations: { hq: da.operations?.hq_count || 0, ...(da.operations?.market_allocation || {}) },
        });
      }
      if (orgRes?.data) setOrgCtx(orgRes.data);
      if (talentRes?.data) {
        setTalentCtx(talentRes.data);
        const pools = talentRes.data.pools || {};
        const d = talentRes.data.draft;
        setTalent({
          rd: {
            headcount: d?.rd_headcount ?? pools.rd?.headcount ?? 50,
            salary_level: d?.rd_salary_level ?? pools.rd?.salary_level ?? 3,
            training_budget: d?.rd_training_budget ?? 0,
            current_level: pools.rd?.talent_level ?? 3.0,
            turnover_rate: pools.rd?.turnover_rate ?? 0.08,
          },
          commercial: {
            headcount: d?.commercial_headcount ?? pools.commercial?.headcount ?? 30,
            salary_level: d?.commercial_salary_level ?? pools.commercial?.salary_level ?? 3,
            training_budget: d?.commercial_training_budget ?? 0,
            current_level: pools.commercial?.talent_level ?? 3.0,
            turnover_rate: pools.commercial?.turnover_rate ?? 0.08,
          },
          operations: {
            headcount: d?.operations_headcount ?? pools.operations?.headcount ?? 40,
            salary_level: d?.operations_salary_level ?? pools.operations?.salary_level ?? 3,
            training_budget: d?.operations_training_budget ?? 0,
            current_level: pools.operations?.talent_level ?? 3.0,
            turnover_rate: pools.operations?.turnover_rate ?? 0.08,
          },
        });
      }
      if (draft?.esg) setEsg(draft.esg);
      // CC-31J: Load governance context
      try {
        const govRes = await getGovernanceContext(gameId, teamId);
        if (govRes?.data) setGovCtx(govRes.data);
      } catch { /* ignore — old scenarios without governance types */ }
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

  const handleAllocChange = useCallback((poolKey, newAlloc) => {
    setAllocations(prev => {
      const next = { ...prev, [poolKey]: newAlloc };
      // Auto-save allocations
      const payload = {};
      ['rd', 'commercial', 'operations'].forEach(k => {
        const a = next[k] || {};
        const { hq, ...marketAlloc } = a;
        payload[k] = { hq_count: hq || 0, market_allocation: marketAlloc };
      });
      autoSave('talent_allocations', { talent_allocations: payload });
      return next;
    });
  }, [autoSave]);

  const handleTalentChange = useCallback((poolKey, poolData) => {
    setTalent(prev => {
      const next = { ...prev, [poolKey]: poolData };
      autoSave('talent', {
        talent: {
          rd_headcount: next.rd.headcount,
          rd_salary_level: next.rd.salary_level,
          rd_training_budget: next.rd.training_budget,
          commercial_headcount: next.commercial.headcount,
          commercial_salary_level: next.commercial.salary_level,
          commercial_training_budget: next.commercial.training_budget,
          operations_headcount: next.operations.headcount,
          operations_salary_level: next.operations.salary_level,
          operations_training_budget: next.operations.training_budget,
        },
      });
      return next;
    });
  }, [autoSave]);

  if (loading) return <LoadingSpinner />;
  if (!context) return <Alert message={t('corporate_strategy.unable_to_load')} type="error" />;

  const markets = context.markets || [];
  // Total talent cost
  const SALARY_OPTIONS = getSalaryOptions(t);
  const totalTalentCost = ['rd', 'commercial', 'operations'].reduce((sum, key) => {
    const p = talent[key];
    const sal = SALARY_OPTIONS.find(s => s.level === p.salary_level)?.quarterly || 30000;
    return sum + p.headcount * sal + (p.training_budget || 0);
  }, 0);

  const tabItems = [
    {
      key: 'talent',
      label: t('corporate_strategy.talent_workforce'),
      children: (
        <PanelCard headerColor="strategic" title={t('corporate_strategy.workforce_management')} actions={<Text type="secondary">{t('corporate_strategy.total_cost')}: {fmt(totalTalentCost)}{t('common.per_round')}</Text>}>
          {Object.entries(POOL_CONFIG).map(([key]) => (
            <TalentPoolCard
              key={key}
              poolKey={key}
              pool={POOL_CONFIG[key]}
              talent={talent[key]}
              locked={locked}
              onChange={data => handleTalentChange(key, data)}
              prev={talentCtx?.pools?.[key]}
              markets={allocCtx?.markets || []}
              allocations={allocations[key]}
              onAllocChange={alloc => handleAllocChange(key, alloc)}
            />
          ))}

          {/* Market Deployment Effectiveness Summary */}
          {allocCtx?.markets && allocCtx.markets.length > 0 && (
            <Card
              size="small"
              style={{ marginTop: 8, background: '#f8fafc', border: '1px solid #d9e4f0' }}
            >
              <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>{t('corporate_strategy.market_deployment_effectiveness')}</Text>
              <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #e8e8e8' }}>
                    <th style={{ textAlign: 'left', padding: '4px 8px', fontWeight: 600 }}></th>
                    {allocCtx.markets.map(m => (
                      <th key={m.code} style={{ textAlign: 'center', padding: '4px 8px', fontWeight: 600 }}>
                        {m.is_home_market && '🏠 '}{m.code}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { key: 'rd', label: t('corporate_strategy.label_rd'), multKey: 'effective_rd_multiplier' },
                    { key: 'commercial', label: t('corporate_strategy.label_comm'), multKey: 'effective_commercial_multiplier' },
                    { key: 'operations', label: t('corporate_strategy.label_ops'), multKey: 'effective_operations_multiplier' },
                  ].map(row => (
                    <tr key={row.key} style={{ borderBottom: '1px solid #f0f0f0' }}>
                      <td style={{ padding: '4px 8px', fontWeight: 600 }}>{row.label}</td>
                      {allocCtx.markets.map(m => {
                        const globalLevel = talent[row.key]?.current_level || 3.0;
                        const mult = m.is_home_market
                          ? globalLevel
                          : globalLevel * (m[row.multKey] || m.base_effectiveness || 1.0);
                        const display = m.is_home_market
                          ? `${globalLevel.toFixed(1)} (home)`
                          : mult.toFixed(1);
                        return (
                          <td key={m.code} style={{ textAlign: 'center', padding: '4px 8px', color: multColor(mult) }}>
                            {display}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
              <Text type="secondary" style={{ fontSize: 10, display: 'block', marginTop: 8 }}>
                {t('corporate_strategy.effectiveness_hint')}
                {' '}{t('corporate_strategy.allocate_staff_hint')}
              </Text>
            </Card>
          )}
        </PanelCard>
      ),
    },
    {
      key: 'ma',
      label: t('corporate_strategy.ma'),
      children: <MnATab context={context} locked={locked} autoSave={autoSave} draft={draft} />,
    },
    {
      key: 'esg',
      label: t('corporate_strategy.esg'),
      children: (() => {
        const commitments = govCtx?.commitment_types || [];
        const teamState = govCtx?.team_state || {};
        const warnings = govCtx?.interaction_warnings || {};
        const activeCommitments = esg.governance_commitments || [];
        const hasGovTypes = commitments.length > 0;

        // Calculate governance cost & quality
        let govCost = 0;
        let govQualityBoost = 0;
        const activeDetails = [];
        let interactionCost = 0;

        if (hasGovTypes) {
          // NEW: per-commitment calculations
          for (const ct of commitments) {
            if (activeCommitments.includes(ct.code)) {
              govCost += ct.ongoing_cost_per_round;
              const gqBoost = (ct.benefits || []).filter(b => b.target === 'governance_quality').reduce((s, b) => s + (b.boost || 0), 0);
              govQualityBoost += gqBoost;
              activeDetails.push(ct);
            }
          }
          if (activeCommitments.includes('anti_corruption') && warnings.anti_corruption?.active) {
            const jvCount = (warnings.anti_corruption.message.match(/,/g) || []).length + 1;
            interactionCost += 100000 * jvCount;
          }
        } else {
          // LEGACY: count-based (no cost, simple quality tiers)
          govQualityBoost = activeCommitments.length * 0.8;
        }

        const govQualityLevel = hasGovTypes
          ? Math.min(Math.round(govQualityBoost * 10.6), 10)
          : (activeCommitments.length >= 4 ? 9 : activeCommitments.length >= 3 ? 7 : activeCommitments.length >= 2 ? 5 : activeCommitments.length >= 1 ? 3 : 0);
        const govLabel = govQualityLevel >= 8 ? t('corporate_strategy.gov_leading') : govQualityLevel >= 6 ? t('dashboard.strong') : govQualityLevel >= 4 ? t('corporate_strategy.gov_established') : govQualityLevel >= 2 ? t('corporate_strategy.gov_developing') : govQualityLevel >= 1 ? t('corporate_strategy.basic') : t('corporate_strategy.none');
        const totalEsgCost = (esg.environmental_investment || 0) + (esg.social_investment || 0) + govCost + interactionCost;

        const handleCommitmentToggle = (code, checked) => {
          if (!checked && activeCommitments.includes(code)) {
            // Unchecking — check if this was previously active (needs revocation warning)
            const state = teamState[code];
            if (state?.is_active) {
              const ct = commitments.find(c => c.code === code);
              setRevokeTarget({ code, ct, state });
              return;
            }
          }
          const next = checked
            ? [...activeCommitments, code]
            : activeCommitments.filter(c => c !== code);
          const e = { ...esg, governance_commitments: next };
          setEsg(e);
          autoSave('esg', { esg: e });
        };

        const confirmRevoke = () => {
          if (!revokeTarget) return;
          const next = activeCommitments.filter(c => c !== revokeTarget.code);
          const e = { ...esg, governance_commitments: next };
          setEsg(e);
          autoSave('esg', { esg: e });
          setRevokeTarget(null);
        };

        return (
          <PanelCard headerColor="strategic" title={t('corporate_strategy.esg_commitments')}>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card size="small" title={t('corporate_strategy.environmental')}>
                  <InputNumber
                    prefix="$" min={0} step={50000}
                    value={esg.environmental_investment} disabled={locked}
                    onChange={v => {
                      const e = { ...esg, environmental_investment: v || 0 };
                      setEsg(e);
                      autoSave('esg', { esg: e });
                    }}
                    style={{ width: '100%' }}
                  />
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card size="small" title={t('corporate_strategy.social_programs')}>
                  <InputNumber
                    prefix="$" min={0} step={50000}
                    value={esg.social_investment} disabled={locked}
                    onChange={v => {
                      const e = { ...esg, social_investment: v || 0 };
                      setEsg(e);
                      autoSave('esg', { esg: e });
                    }}
                    style={{ width: '100%' }}
                  />
                </Card>
              </Col>
            </Row>

            {/* Governance Commitment Cards */}
            <div style={{ marginTop: 16 }}>
              <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 12 }}>{t('corporate_strategy.governance_commitments')}</Text>
              {hasGovTypes ? commitments.map(ct => {
                const isChecked = activeCommitments.includes(ct.code);
                const state = teamState[ct.code];
                const warning = warnings[ct.code];
                const hasPenalty = (state?.penalty_rounds_remaining || 0) > 0;
                const gqBoost = (ct.benefits || []).filter(b => b.target === 'governance_quality').reduce((s, b) => s + (b.boost || 0), 0);

                return (
                  <Card
                    key={ct.code} size="small"
                    style={{ marginBottom: 8, borderLeft: isChecked ? '3px solid #1677ff' : '3px solid #d9d9d9' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Checkbox
                        checked={isChecked} disabled={locked}
                        onChange={e => handleCommitmentToggle(ct.code, e.target.checked)}
                      >
                        <Text strong>{ct.name}</Text>
                      </Checkbox>
                      <Tag>{fmt(ct.ongoing_cost_per_round)}/round</Tag>
                    </div>
                    <div style={{ marginLeft: 24, marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>{ct.description}</Text>
                      <Collapse ghost size="small" items={[{
                        key: '1',
                        label: <Text type="secondary" style={{ fontSize: 10 }}>{t('corporate_strategy.details')}</Text>,
                        children: (
                          <div style={{ fontSize: 11 }}>
                            <div style={{ marginBottom: 4 }}>
                              <Text strong style={{ fontSize: 11 }}>{t('corporate_strategy.benefits')}:</Text>
                              {(ct.benefits || []).map((b, i) => (
                                <div key={i} style={{ marginLeft: 8 }}>{'\u2022'} {b.target.replace(/_/g, ' ')}: +{b.boost}{b.markets ? ` (${b.markets.join(', ').toUpperCase()})` : ''}</div>
                              ))}
                            </div>
                            {(ct.revocation_penalty?.duration_rounds || 0) > 0 && (
                              <Alert
                                type="warning" showIcon
                                style={{ marginTop: 4, fontSize: 10 }}
                                message={`Revoking triggers a ${ct.revocation_penalty.duration_rounds}-round investor confidence penalty (${ct.revocation_penalty.investor_confidence_drop ? (ct.revocation_penalty.investor_confidence_drop * 100).toFixed(0) + '%' : ''}).`}
                              />
                            )}
                            {ct.amplifier && (
                              <div style={{ marginTop: 4, color: '#1677ff' }}>
                                {'\u2726'} Amplifier: {ct.amplifier.description}
                              </div>
                            )}
                          </div>
                        ),
                      }]} />
                      {isChecked && warning?.active && (
                        <Alert
                          type="warning" showIcon
                          style={{ marginTop: 4, fontSize: 11 }}
                          message={warning.message}
                        />
                      )}
                      {hasPenalty && (
                        <Alert
                          type="error" showIcon
                          style={{ marginTop: 4, fontSize: 11 }}
                          message={`Revocation penalty active: ${state.penalty_rounds_remaining} round${state.penalty_rounds_remaining === 1 ? '' : 's'} remaining`}
                        />
                      )}
                    </div>
                  </Card>
                );
              }) : (
                <Checkbox.Group
                  value={activeCommitments} disabled={locked}
                  onChange={v => { const e = { ...esg, governance_commitments: v }; setEsg(e); autoSave('esg', { esg: e }); }}
                >
                  <Space direction="vertical">
                    <Checkbox value="board_diversity">{t('corporate_strategy.board_diversity')}</Checkbox>
                    <Checkbox value="pay_transparency">{t('corporate_strategy.pay_transparency')}</Checkbox>
                    <Checkbox value="anti_corruption">{t('corporate_strategy.anti_corruption')}</Checkbox>
                    <Checkbox value="supply_chain_audit">{t('corporate_strategy.supply_chain_audit')}</Checkbox>
                    <Checkbox value="public_esg_reporting">{t('corporate_strategy.public_esg_reporting')}</Checkbox>
                  </Space>
                </Checkbox.Group>
              )}
            </div>

            {/* Revocation Confirmation Modal */}
            <Modal
              title={t('corporate_strategy.revoke_title', { name: revokeTarget?.ct?.name })}
              open={!!revokeTarget}
              onCancel={() => setRevokeTarget(null)}
              footer={[
                <Button key="keep" onClick={() => setRevokeTarget(null)}>{t('corporate_strategy.keep_commitment')}</Button>,
                <Button key="revoke" danger onClick={confirmRevoke}>{t('corporate_strategy.revoke_understand')}</Button>,
              ]}
            >
              {revokeTarget?.ct && (
                <div>
                  <p>{t('corporate_strategy.revoke_warning', { name: revokeTarget.ct.name, round: revokeTarget.state?.activated_round || '?' })}</p>
                  <ul style={{ fontSize: 13 }}>
                    <li>{revokeTarget.ct.revocation_penalty?.duration_rounds || 2}-round investor confidence penalty ({((revokeTarget.ct.revocation_penalty?.investor_confidence_drop || 0) * 100).toFixed(0)}%)</li>
                    {revokeTarget.ct.revocation_penalty?.regulator_penalty && (
                      <li>Regulator satisfaction drop ({((revokeTarget.ct.revocation_penalty.regulator_penalty) * 100).toFixed(0)}%)</li>
                    )}
                    {revokeTarget.ct.revocation_penalty?.talent_turnover_spike && (
                      <li>Turnover spike +{((revokeTarget.ct.revocation_penalty.talent_turnover_spike) * 100).toFixed(0)}%</li>
                    )}
                    {revokeTarget.ct.revocation_penalty?.news_headline && (
                      <li>News: &ldquo;{revokeTarget.ct.revocation_penalty.news_headline}&rdquo;</li>
                    )}
                  </ul>
                  <p>{t('corporate_strategy.revoke_savings', { cost: fmt(revokeTarget.ct.ongoing_cost_per_round) })}</p>
                </div>
              )}
            </Modal>

            {/* Warnings */}
            {(() => {
              const totalInv = Number(esg.environmental_investment || 0) + Number(esg.social_investment || 0);
              if (activeCommitments.length === 0) return null;
              if (totalInv === 0) return (
                <Alert
                  type="warning" showIcon
                  style={{ marginTop: 12, fontSize: 12 }}
                  message={t('corporate_strategy.gov_without_investment')}
                  description={t('corporate_strategy.gov_without_investment_desc')}
                />
              );
              if (totalInv < 500000) return (
                <Alert
                  type="info" showIcon
                  style={{ marginTop: 12, fontSize: 12 }}
                  message={t('corporate_strategy.low_esg_investment')}
                  description={t('corporate_strategy.low_esg_investment_desc')}
                />
              );
              return null;
            })()}

            {/* ESG Impact Preview */}
            <Card size="small" style={{ marginTop: 16, background: '#f8fafc', border: '1px dashed #d9d9d9' }}>
              <Text strong style={{ fontSize: 12 }}>{t('corporate_strategy.esg_impact_preview')}</Text>
              <Row gutter={[16, 8]} style={{ marginTop: 8 }}>
                <Col xs={24} md={8}>
                  <Text type="secondary" style={{ fontSize: 11 }}>{t('corporate_strategy.environmental_label')}</Text>
                  <div style={{ fontSize: 12 }}>
                    {t('corporate_strategy.investment')}: {fmt(esg.environmental_investment)}
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {t('corporate_strategy.sustainability_level')}: {esg.environmental_investment >= 2000000 ? t('dashboard.high') : esg.environmental_investment >= 500000 ? t('dashboard.moderate') : esg.environmental_investment > 0 ? t('corporate_strategy.basic') : t('corporate_strategy.none')}
                    </Text>
                  </div>
                </Col>
                <Col xs={24} md={8}>
                  <Text type="secondary" style={{ fontSize: 11 }}>{t('corporate_strategy.social_label')}</Text>
                  <div style={{ fontSize: 12 }}>
                    {t('corporate_strategy.investment')}: {fmt(esg.social_investment)}
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {t('corporate_strategy.social_label')}: {esg.social_investment >= 1000000 ? t('dashboard.high') : esg.social_investment >= 300000 ? t('dashboard.moderate') : esg.social_investment > 0 ? t('corporate_strategy.basic') : t('corporate_strategy.none')}
                    </Text>
                  </div>
                </Col>
                <Col xs={24} md={8}>
                  <Text type="secondary" style={{ fontSize: 11 }}>{t('corporate_strategy.governance_label')}</Text>
                  <div style={{ fontSize: 12 }}>
                    {t('corporate_strategy.commitments_selected', { count: activeCommitments.length })}
                    {hasGovTypes && activeDetails.map(ct => (
                      <div key={ct.code} style={{ fontSize: 10, color: '#595959' }}>
                        {ct.name}: {fmt(ct.ongoing_cost_per_round)}/round
                      </div>
                    ))}
                    {interactionCost > 0 && (
                      <div style={{ fontSize: 10, color: '#fa8c16' }}>{t('corporate_strategy.interaction_costs')}: +{fmt(interactionCost)}{t('common.per_round')}</div>
                    )}
                    <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                      {t('corporate_strategy.governance_quality')}: {govLabel} ({govQualityLevel}/10)
                    </Text>
                    {activeCommitments.includes('public_esg_reporting') && (esg.environmental_investment + esg.social_investment) >= 1000000 && (
                      <Text style={{ fontSize: 10, color: '#1677ff', display: 'block' }}>
                        {'\u2726'} {t('corporate_strategy.esg_amplifier_active')}
                      </Text>
                    )}
                  </div>
                </Col>
              </Row>
              <div style={{ marginTop: 8, borderTop: '1px solid #e8e8e8', paddingTop: 8 }}>
                <Text strong style={{ fontSize: 12 }}>
                  {t('corporate_strategy.total_esg_cost')}: {fmt(totalEsgCost)}{t('common.per_round')}
                </Text>
                {govCost > 0 && (
                  <Text type="secondary" style={{ fontSize: 10, marginLeft: 12 }}>
                    (Investment: {fmt((esg.environmental_investment || 0) + (esg.social_investment || 0))} + Governance: {fmt(govCost + interactionCost)})
                  </Text>
                )}
              </div>
            </Card>
          </PanelCard>
        );
      })(),
    },
    {
      key: 'org',
      label: t('corporate_strategy.organization'),
      children: (
        <OrgStructureTab
          orgCtx={orgCtx}
          locked={locked}
          gameId={gameId}
          teamId={teamId}
          onRefresh={loadContext}
        />
      ),
    },
  ];

  return (
    <div>
      <TeamActivityBanner gameId={gameId} teamId={teamId} currentRound={currentRound} currentUserId={user?.user_id} />
      <PageHeader
        title={t('corporate_strategy.title')}
        subtitle={`${t('common.round')} ${currentRound} · ${t('corporate_strategy.subtitle')}`}
        status={locked ? 'locked' : 'draft'}
        actions={saving ? <Tag color="processing">{t('corporate_strategy.saving')}</Tag> : null}
      />

      <Tabs className="ds-colored-tabs" defaultActiveKey="talent" items={tabItems} />
    </div>
  );
};

export default CorporateStrategyPage;
