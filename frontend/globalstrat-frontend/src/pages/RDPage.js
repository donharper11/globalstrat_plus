import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Typography, Button, Tag, Alert, Table, Row, Col, Input,
  Tooltip, Radio, Modal, Divider, Slider, Progress, message,
} from 'antd';
import {
  PlusOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getRDContext, patchDecision } from '../api/decisions';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

// ══════════════════════════════════════════════════════════════════
// Create Platform Modal
// ══════════════════════════════════════════════════════════════════
const CreatePlatformModal = ({ open, onClose, onCreated, context, gameId, teamId, currentRound, rdBudget }) => {
  const { t } = useTranslation();
  const generations = context?.available_generations || [];
  const [selectedGenId, setSelectedGenId] = useState(null);
  const [platformName, setPlatformName] = useState('');
  const [featureLevels, setFeatureLevels] = useState({});
  const [method, setMethod] = useState('in_house');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      const gen1 = generations.find(g => g.generation_order === 1);
      setSelectedGenId(gen1?.id || null);
      setPlatformName('');
      setFeatureLevels({});
      setMethod('in_house');
    }
  }, [open, generations]);

  const selectedGen = generations.find(g => g.id === selectedGenId);
  const genFeatures = selectedGen?.features || [];

  const getFeatureCost = (featureId, level) => {
    const feat = genFeatures.find(f => f.feature_id === featureId);
    if (!feat || !level || level <= 0) return 0;
    const entry = feat.cost_schedule?.find(e => e.level === level);
    return entry ? entry.cumulative_cost : 0;
  };

  const featureCostTotal = Object.entries(featureLevels).reduce((sum, [fid, lvl]) => {
    return sum + getFeatureCost(Number(fid), lvl);
  }, 0);

  const methodMultiplier = method === 'license' ? 2.5 : method === 'partnership' ? 1.6 : 1;
  const adjustedFeatureCost = featureCostTotal * methodMultiplier;

  // Always show base cost — every generation has a development cost
  const baseCost = method === 'license'
    ? (selectedGen?.license_cost || 0)
    : (selectedGen?.development_cost || 0);
  const totalCost = baseCost + adjustedFeatureCost;
  const overBudget = totalCost > rdBudget;

  const activeFeatureCount = Object.values(featureLevels).filter(v => v > 0).length;

  const missingFields = [];
  if (!platformName.trim()) missingFields.push(t('rd.platform_name'));
  if (!selectedGenId) missingFields.push(t('rd.technology_base'));
  if (saving) missingFields.push('Saving...');
  if (selectedGen?.prerequisites_met === false && selectedGen?.generation_order !== 1) missingFields.push(t('rd.prerequisites_not_met'));
  const canCreate = missingFields.length === 0;

  const handleCreate = async () => {
    if (!canCreate) return;
    setSaving(true);
    try {
      const feats = {};
      Object.entries(featureLevels).forEach(([fid, lvl]) => {
        if (lvl > 0) feats[fid] = lvl;
      });
      await patchDecision(gameId, teamId, currentRound, 'platforms', {
        platform_developments: [{
          platform_generation: selectedGenId,
          method,
          committed_cost: totalCost,
          platform_name: platformName.trim(),
          feature_levels: feats,
        }],
      });
      message.success(t('rd.platform_created'));
      await onCreated();
      onClose();
    } catch (err) {
      message.error(t('rd.create_failed'));
    }
    setSaving(false);
  };

  const handleFeatureLevel = (featureId, level) => {
    setFeatureLevels(prev => {
      const next = { ...prev };
      if (level <= 0) delete next[featureId];
      else next[featureId] = level;
      return next;
    });
  };

  const timeDesc = method === 'license' ? t('rd.immediate')
    : method === 'partnership' ? `${Math.max(1, (selectedGen?.development_rounds || 2) - 1)} ${t('rd.round_unit')}`
    : `${selectedGen?.development_rounds || 1} ${t('rd.round_unit')}`;

  return (
    <Modal
      title={t('rd.create_platform')}
      open={open}
      onCancel={onClose}
      width={700}
      footer={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 11, color: '#ff4d4f' }}>
            {!canCreate && missingFields.length > 0 && `${t('rd.required')}: ${missingFields.join(', ')}`}
          </div>
          <div>
            <Button key="cancel" onClick={onClose} style={{ marginRight: 8 }}>{t('common.cancel')}</Button>
            <Button key="create" type="primary" disabled={!canCreate} loading={saving} onClick={handleCreate}>
              {t('rd.create_platform_btn')}
            </Button>
          </div>
        </div>
      }
    >
      {/* Platform Name */}
      <div style={{ marginBottom: 16 }}>
        <Text strong>{t('rd.platform_name')}</Text>
        <Input
          placeholder={t('rd.platform_name_placeholder')}
          value={platformName}
          onChange={e => setPlatformName(e.target.value)}
          style={{ marginTop: 4 }}
        />
      </div>

      {/* Technology Base */}
      <div style={{ marginBottom: 16 }}>
        <Text strong>{t('rd.technology_base')}</Text>
        <Radio.Group
          value={selectedGenId}
          onChange={e => { setSelectedGenId(e.target.value); setFeatureLevels({}); }}
          style={{ display: 'block', marginTop: 4 }}
        >
          {generations.map(g => {
            const disabled = g.generation_order > 1 && !g.prerequisites_met;
            return (
              <div key={g.id} style={{ marginBottom: 8 }}>
                <Radio value={g.id} disabled={disabled}>
                  <Text strong={!disabled} type={disabled ? 'secondary' : undefined}>
                    {g.name}
                  </Text>
                  <Text type="secondary" style={{ marginLeft: 8, fontSize: 11 }}>
                    {t('rd.base')}: {fmt(g.development_cost)}
                  </Text>
                </Radio>
                {disabled && g.prerequisites?.length > 0 && (
                  <div style={{ marginLeft: 24, fontSize: 11 }}>
                    {g.prerequisites.map((p, i) => (
                      <div key={i} style={{ color: p.met ? '#52c41a' : '#999' }}>
                        {p.met ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />} {p.requirement} — {p.detail}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </Radio.Group>
      </div>

      <Divider style={{ margin: '12px 0' }} />

      {/* Feature Configuration */}
      {selectedGen && (
        <div style={{ marginBottom: 16 }}>
          <Text strong>{t('rd.feature_configuration')}</Text>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
            {t('rd.feature_limit_hint')}
            {activeFeatureCount >= 5 && <Tag color="orange" style={{ marginLeft: 8 }}>{t('rd.feature_limit_reached')}</Tag>}
          </Text>
          {genFeatures.map(feat => {
            const level = featureLevels[feat.feature_id] || 0;
            const cost = getFeatureCost(feat.feature_id, level);
            const disabled = level === 0 && activeFeatureCount >= 5;
            return (
              <div key={feat.feature_id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 0', borderBottom: '1px solid #f5f5f5',
                opacity: disabled ? 0.5 : 1,
              }}>
                <div style={{ width: 130, fontSize: 12, fontWeight: level > 0 ? 600 : 400 }}>
                  {feat.name}
                </div>
                <div style={{ flex: 1 }}>
                  <Slider
                    min={0} max={feat.ceiling} value={level} disabled={disabled}
                    onChange={val => handleFeatureLevel(feat.feature_id, val)}
                    marks={{ 0: '0', [feat.ceiling]: String(feat.ceiling) }}
                    style={{ margin: '4px 0' }}
                  />
                </div>
                <div style={{ width: 40, textAlign: 'center', fontWeight: 600, fontSize: 14 }}>
                  {level}
                </div>
                <div style={{ width: 80, textAlign: 'right', fontSize: 11, color: cost > 0 ? '#1890ff' : '#999' }}>
                  {cost > 0 ? fmt(cost * methodMultiplier) : '—'}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Divider style={{ margin: '12px 0' }} />

      {/* Development Method */}
      <div style={{ marginBottom: 16 }}>
        <Text strong>{t('rd.development_method')}</Text>
        <Radio.Group value={method} onChange={e => setMethod(e.target.value)} style={{ display: 'block', marginTop: 4 }}>
          <Radio value="in_house">{t('rd.in_house_desc', { rounds: selectedGen?.development_rounds || 1 })}</Radio>
          <Radio value="license">{t('rd.license_desc')}</Radio>
          {method === 'license' && (
            <div style={{ marginLeft: 24, marginBottom: 4 }}>
              <Text type="warning" style={{ fontSize: 11 }}>
                ⚠ {t('rd.license_warning')}
              </Text>
            </div>
          )}
          <Radio value="partnership">{t('rd.partnership_desc', { rounds: Math.max(1, (selectedGen?.development_rounds || 2) - 1) })}</Radio>
        </Radio.Group>
      </div>

      <Divider style={{ margin: '12px 0' }} />

      {/* Cost Summary */}
      <Card size="small" style={{ background: overBudget ? '#fff2f0' : '#f6ffed' }}>
        <Row gutter={16}>
          <Col span={14}>
            <div style={{ fontSize: 12 }}>
              {t('rd.generation_base_cost')}: <Text strong>{fmt(baseCost)}</Text>
            </div>
            {Object.entries(featureLevels).filter(([, v]) => v > 0).map(([fid, lvl]) => {
              const feat = genFeatures.find(f => f.feature_id === Number(fid));
              const cost = getFeatureCost(Number(fid), lvl) * methodMultiplier;
              return (
                <div key={fid} style={{ fontSize: 11, color: '#666' }}>
                  {feat?.name} → {t('rd.level')} {lvl}: {fmt(cost)}
                </div>
              );
            })}
            <Divider style={{ margin: '4px 0' }} />
            <div style={{ fontSize: 13 }}>
              {t('rd.total')}: <Text strong style={{ fontSize: 15 }}>{fmt(totalCost)}</Text>
            </div>
            <div style={{ fontSize: 12, marginTop: 2 }}>{t('rd.ready')}: <Text>{timeDesc}</Text></div>
          </Col>
          <Col span={10} style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 12 }}>{t('rd.rd_budget')}: {fmt(rdBudget)}</div>
            {overBudget ? (
              <div style={{ color: '#ff4d4f', fontWeight: 600, fontSize: 13 }}>
                {t('rd.over_budget')}: {fmt(totalCost - rdBudget)}
              </div>
            ) : (
              <div style={{ color: '#52c41a', fontSize: 12 }}>{t('rd.remaining')}: {fmt(rdBudget - totalCost)}</div>
            )}
          </Col>
        </Row>
      </Card>
    </Modal>
  );
};


// ══════════════════════════════════════════════════════════════════
// Main R&D Page — Platform Table
// ══════════════════════════════════════════════════════════════════
const RDPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { locked } = useDecisions();
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [expandedRowKeys, setExpandedRowKeys] = useState([]);

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const res = await getRDContext(gameId, teamId);
      setContext(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId]);

  useEffect(() => { loadContext(); }, [loadContext]);

  if (loading) return <LoadingSpinner />;
  if (!context) return <Alert message={t('rd.unable_to_load')} type="error" />;

  const rdBudget = Number(context?.rd_budget || 0);
  const ownedPlatforms = context.owned_platforms || [];
  const platformDevDecisions = context.platform_dev_decisions || [];

  // Helper: compute technology sovereignty stats for a platform
  const computeSovereignty = (features) => {
    const total = features.length;
    if (total === 0) return { total: 0, inHouse: 0, licensed: 0, partnership: 0, grandfathered: 0, pct: 100 };
    const hasMethodData = features.some(f => f.development_method);
    const inHouse = features.filter(f => {
      if (!hasMethodData) return true; // default all to in-house if no method data
      return f.development_method === 'in_house';
    }).length;
    const licensed = features.filter(f => f.development_method === 'license').length;
    const partnership = features.filter(f => f.development_method === 'partnership').length;
    const grandfathered = features.filter(f => f.development_method === 'grandfathered' || f.inherited).length;
    const pct = total > 0 ? Math.round((inHouse / total) * 100) : 100;
    return { total, inHouse, licensed, partnership, grandfathered, pct, hasMethodData };
  };

  // Build table rows: owned platforms + pending creations
  const tableData = [
    ...ownedPlatforms.map(p => {
      const features = p.features || [];
      const sovereignty = computeSovereignty(features);
      return {
        key: `owned-${p.id}`,
        name: p.platform_name || p.generation_name,
        status: p.status,
        generation_order: p.generation_order,
        features,
        featureCount: features.length,
        totalCost: null, // existing platform — no "added cost"
        isOwned: true,
        sovereignty,
        raw: p,
      };
    }),
    ...platformDevDecisions.map(pd => ({
      key: `pending-${pd.id}`,
      name: pd.platform_name || pd.generation_name,
      status: 'pending',
      generation_order: null,
      features: [],
      featureCount: Object.keys(pd.feature_levels || {}).length,
      totalCost: pd.committed_cost,
      isOwned: false,
      raw: pd,
    })),
  ];

  // Gather feature names from the first active platform for column headers
  const activePlatform = ownedPlatforms.find(p => p.status === 'active');
  const featureList = activePlatform?.features || [];

  // Table columns: Platform name | each feature level | added cost
  const columns = [
    {
      title: t('rd.platform'),
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name, row) => (
        <span>
          <Text strong style={{ fontSize: 12 }}>{name}</Text>
          {' '}
          <Tag
            color={row.status === 'active' ? 'green' : row.status === 'in_development' ? 'blue' : 'orange'}
            style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px' }}
          >
            {row.status}
          </Tag>
        </span>
      ),
    },
    {
      title: <span style={{ fontSize: 10 }}>{t('rd.sovereignty')}</span>,
      key: 'sovereignty',
      width: 160,
      render: (_, row) => {
        if (!row.isOwned || !row.sovereignty || row.sovereignty.total === 0) {
          return <Text type="secondary" style={{ fontSize: 11 }}>—</Text>;
        }
        const { pct } = row.sovereignty;
        const color = pct >= 75 ? '#52c41a' : pct >= 50 ? '#faad14' : '#ff4d4f';
        return (
          <div style={{ lineHeight: 1.3 }}>
            <Progress
              percent={pct}
              size="small"
              strokeColor={color}
              style={{ width: 100 }}
              format={p => <span style={{ fontSize: 10 }}>{p}%</span>}
            />
            <div style={{ fontSize: 10, color: '#666' }}>
              {row.sovereignty.total} {t('rd.features_active')} | {pct}% {t('rd.in_house_label')}
            </div>
            {pct < 50 && (
              <Tooltip title={t('rd.sovereignty_warning')}>
                <Tag color="red" style={{ fontSize: 9, lineHeight: '14px', padding: '0 3px', marginTop: 2 }}>
                  {t('rd.sanctions_risk')}
                </Tag>
              </Tooltip>
            )}
          </div>
        );
      },
    },
    ...featureList.map(f => ({
      title: <span style={{ fontSize: 10, whiteSpace: 'nowrap' }}>{f.name}</span>,
      key: `f-${f.feature_id}`,
      width: 70,
      align: 'center',
      render: (_, row) => {
        if (!row.isOwned) {
          // Pending creation — show from feature_levels JSON
          const lvl = row.raw?.feature_levels?.[String(f.feature_id)];
          return lvl ? <Text style={{ fontSize: 12 }}>{lvl}</Text> : <Text type="secondary">—</Text>;
        }
        const feat = (row.features || []).find(rf => rf.feature_id === f.feature_id);
        if (!feat) return <Text type="secondary">—</Text>;
        return (
          <Tooltip title={`${Math.floor(feat.current_level)} / ${Math.floor(feat.ceiling)}`}>
            <Text style={{ fontSize: 12, fontWeight: 600 }}>
              {Math.floor(feat.current_level)}
              <span style={{ color: '#999', fontWeight: 400 }}>/{Math.floor(feat.ceiling)}</span>
            </Text>
          </Tooltip>
        );
      },
    })),
    {
      title: <span style={{ fontSize: 10 }}>{t('rd.added_cost')}</span>,
      key: 'cost',
      width: 90,
      align: 'right',
      render: (_, row) => {
        if (row.totalCost != null) return <Text style={{ fontSize: 12 }}>{fmt(row.totalCost)}</Text>;
        return <Text type="secondary" style={{ fontSize: 11 }}>—</Text>;
      },
    },
  ];

  // Expanded row: read-only detail view (mirrors Create modal layout but disabled)
  const expandedRowRender = (row) => {
    if (!row.isOwned) {
      // Pending platform creation detail
      const pd = row.raw;
      return (
        <div style={{ padding: '8px 16px' }}>
          <Text strong>{t('rd.pending_platform')}: {pd.platform_name}</Text>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            {t('rd.generation')}: {pd.generation_name} | {t('rd.method')}: {pd.method} | {t('rd.cost')}: {fmt(pd.committed_cost)}
          </div>
          {Object.keys(pd.feature_levels || {}).length > 0 && (
            <div style={{ marginTop: 8 }}>
              <Text strong style={{ fontSize: 12 }}>{t('rd.configured_features')}:</Text>
              {Object.entries(pd.feature_levels).map(([fid, lvl]) => {
                const feat = featureList.find(f => f.feature_id === Number(fid));
                return (
                  <Tag key={fid} style={{ margin: '2px 4px' }}>
                    {feat?.name || `${t('rd.feature')} ${fid}`}: {t('rd.level')} {lvl}
                  </Tag>
                );
              })}
            </div>
          )}
        </div>
      );
    }

    // Owned platform detail
    const p = row.raw;
    if (p.status === 'in_development') {
      return (
        <div style={{ padding: '8px 16px' }}>
          <Text strong>{p.platform_name || p.generation_name}</Text>
          <Tag color="blue" style={{ marginLeft: 8 }}>{t('rd.in_development')}</Tag>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            {t('rd.method')}: {p.development_method} | {t('rd.completes_round', { round: p.completion_round })}
          </div>
        </div>
      );
    }

    // Active platform — show all features with levels, ceilings, cost schedules (read-only)
    const features = p.features || [];

    // Technology Sovereignty calculation
    const sov = computeSovereignty(features);
    const totalFeatures = sov.total;
    const inHouseCount = sov.inHouse;
    const licenseCount = sov.licensed;
    const partnershipCount = sov.partnership;
    const grandfatheredCount = sov.grandfathered;
    const hasMethodData = sov.hasMethodData;
    const sovereigntyPct = sov.pct;
    const sovereigntyColor = sovereigntyPct >= 75 ? '#52c41a' : sovereigntyPct >= 50 ? '#faad14' : '#ff4d4f';

    return (
      <div style={{ padding: '8px 16px' }}>
        <Text strong>{p.platform_name || p.generation_name}</Text>
        <Tag color="green" style={{ marginLeft: 8 }}>{t('rd.active')}</Tag>

        {/* Technology Sovereignty */}
        {totalFeatures > 0 && (
          <div style={{ margin: '8px 0', padding: '8px 12px', background: '#fafafa', borderRadius: 4, border: '1px solid #f0f0f0' }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              {t('rd.features_active')}: <Text strong>{totalFeatures}</Text>
              {' | '}{t('rd.sovereignty')}:{' '}
              <Progress
                percent={sovereigntyPct}
                size="small"
                strokeColor={sovereigntyColor}
                style={{ display: 'inline-block', width: 120, marginLeft: 4, marginRight: 4 }}
                format={pct => `${pct}% ${t('rd.in_house_label')}`}
              />
            </div>
            <div style={{ fontSize: 11, color: '#666' }}>
              {hasMethodData ? (
                <>
                  {inHouseCount > 0 && <div>{inHouseCount} {t('rd.developed_in_house')}</div>}
                  {licenseCount > 0 && <div>{licenseCount} {t('rd.licensed_vulnerable')}</div>}
                  {partnershipCount > 0 && <div>{partnershipCount} {t('rd.from_partnership')}</div>}
                  {grandfatheredCount > 0 && <div>{grandfatheredCount} {t('rd.from_previous_gen')}</div>}
                </>
              ) : (
                <div>{totalFeatures} {t('rd.developed_in_house')}</div>
              )}
            </div>
            {sovereigntyPct < 50 && (
              <div style={{ marginTop: 4 }}>
                <Tag color="red" style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>
                  {t('rd.sovereignty_full_warning')}
                </Tag>
              </div>
            )}
          </div>
        )}

        <div style={{ marginTop: 8 }}>
          {features.map(f => {
            const current = Math.floor(f.current_level);
            const ceiling = Math.floor(f.ceiling);
            const pct = ceiling > 0 ? Math.round((current / ceiling) * 100) : 0;
            const nextCost = (f.cost_schedule || []).find(e => e.level === current + 1);
            return (
              <div key={f.feature_id} style={{
                display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
                padding: '4px 0', borderBottom: '1px solid #f5f5f5',
              }}>
                <div style={{ minWidth: 100, flex: '1 1 130px', fontSize: 12, fontWeight: 600 }}>{f.name}</div>
                <div style={{ width: 60, fontSize: 14, fontWeight: 700 }}>
                  {current} <span style={{ color: '#999', fontWeight: 400, fontSize: 11 }}>/ {ceiling}</span>
                </div>
                <div style={{ flex: 1, maxWidth: 200 }}>
                  <div style={{ background: '#f0f0f0', borderRadius: 4, height: 8 }}>
                    <div style={{
                      background: pct >= 100 ? '#52c41a' : '#1890ff',
                      borderRadius: 4, height: 8,
                      width: `${Math.min(pct, 100)}%`,
                    }} />
                  </div>
                </div>
                <div style={{ width: 100, fontSize: 11, color: '#666', textAlign: 'right' }}>
                  {current < ceiling && nextCost
                    ? <span>{t('rd.next_level')}: {fmt(nextCost.incremental_cost)}</span>
                    : current >= ceiling
                      ? <Tag color="green" style={{ fontSize: 10 }}>{t('rd.maxed')}</Tag>
                      : null
                  }
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div style={{ maxWidth: 1100, width: '100%' }}>
      {/* Header */}
      <PageHeader
        title={t('rd.title')}
        subtitle={
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('common.round')} {currentRound} &middot; {t('rd.rd_budget')}: <Text strong>{fmt(rdBudget)}</Text>
            <span style={{ marginLeft: 8, color: '#999' }}>{context.budget_source}</span>
          </Text>
        }
        status={locked ? 'locked' : 'draft'}
        actions={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={locked}
            onClick={() => setShowCreateModal(true)}
          >
            {t('rd.create_platform')}
          </Button>
        }
      />

      {/* Your Platform */}
      <PanelCard headerColor="strategic" title={t('rd.your_platform')} style={{ marginBottom: 16 }}>
        <Table
          dataSource={tableData.filter(r => r.isOwned)}
          columns={columns}
          pagination={false}
          size="small"
          expandable={{
            expandedRowRender,
            expandedRowKeys,
            onExpand: (expanded, record) => {
              setExpandedRowKeys(expanded ? [record.key] : []);
            },
          }}
          onRow={(record) => ({
            style: { cursor: 'pointer' },
            onClick: () => {
              setExpandedRowKeys(prev =>
                prev.includes(record.key) ? [] : [record.key]
              );
            },
          })}
          locale={{ emptyText: t('rd.no_platforms_yet') }}
        />
      </PanelCard>

      {/* Investment Slots (pending platform developments) */}
      <PanelCard headerColor="decision" title={t('rd.investment_slots').toUpperCase()} style={{ marginBottom: 16 }}>
        <Table
          dataSource={tableData.filter(r => !r.isOwned)}
          columns={columns}
          pagination={false}
          size="small"
          expandable={{
            expandedRowRender,
            expandedRowKeys,
            onExpand: (expanded, record) => {
              setExpandedRowKeys(expanded ? [record.key] : []);
            },
          }}
          onRow={(record) => ({
            style: { cursor: 'pointer' },
            onClick: () => {
              setExpandedRowKeys(prev =>
                prev.includes(record.key) ? [] : [record.key]
              );
            },
          })}
          locale={{ emptyText: t('rd.no_pending_investments') }}
        />
      </PanelCard>

      {/* Platform Upgrade — shown when an active platform exists with upgradeable features */}
      {activePlatform && activePlatform.features?.some(f => Math.floor(f.current_level) < Math.floor(f.ceiling)) && (
        <PanelCard headerColor="strategic" title={t('rd.platform_upgrade')} style={{ marginBottom: 16 }}>
          <div style={{ padding: '8px 0' }}>
            {activePlatform.features
              .filter(f => Math.floor(f.current_level) < Math.floor(f.ceiling))
              .map(f => {
                const current = Math.floor(f.current_level);
                const ceiling = Math.floor(f.ceiling);
                const pct = ceiling > 0 ? Math.round((current / ceiling) * 100) : 0;
                const nextCost = (f.cost_schedule || []).find(e => e.level === current + 1);
                return (
                  <div key={f.feature_id} style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '4px 0', borderBottom: '1px solid #f5f5f5',
                  }}>
                    <div style={{ width: 130, fontSize: 12, fontWeight: 600 }}>{f.name}</div>
                    <div style={{ width: 60, fontSize: 14, fontWeight: 700 }}>
                      {current} <span style={{ color: '#999', fontWeight: 400, fontSize: 11 }}>/ {ceiling}</span>
                    </div>
                    <div style={{ flex: 1, maxWidth: 200 }}>
                      <div style={{ background: '#f0f0f0', borderRadius: 4, height: 8 }}>
                        <div style={{
                          background: '#1890ff',
                          borderRadius: 4, height: 8,
                          width: `${Math.min(pct, 100)}%`,
                        }} />
                      </div>
                    </div>
                    <div style={{ width: 100, fontSize: 11, color: '#666', textAlign: 'right' }}>
                      {nextCost ? <span>{t('rd.next_level')}: {fmt(nextCost.incremental_cost)}</span> : null}
                    </div>
                  </div>
                );
              })}
          </div>
        </PanelCard>
      )}

      {/* Locked capabilities */}
      {locked && (
        <PanelCard headerColor="neutral" title={t('rd.decisions_locked')} style={{ marginBottom: 16 }}>
          <Alert
            message={t('rd.decisions_locked_message')}
            description={t('rd.decisions_locked_description')}
            type="info"
            showIcon
          />
        </PanelCard>
      )}

      {/* Create Modal */}
      <CreatePlatformModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={async () => { await loadContext(); refreshBudgets(); }}
        context={context}
        gameId={gameId}
        teamId={teamId}
        currentRound={currentRound}
        rdBudget={rdBudget}
      />
    </div>
  );
};

export default RDPage;
