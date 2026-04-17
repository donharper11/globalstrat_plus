import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Typography, Collapse, InputNumber, Select, Button, Tag, Space, Row, Col, Checkbox, Alert, Statistic } from 'antd';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getStrategyContext, patchDecision } from '../api/decisions';
import LoadingSpinner from '../components/LoadingSpinner';
import { PageHeader } from '../components/design-system';
// eslint-disable-next-line no-unused-vars
import WarningBanner from '../components/WarningBanner';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const StrategyPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { draft, locked } = useDecisions();
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Decision state
  const [marketEntries, setMarketEntries] = useState([]);
  const [financing, setFinancing] = useState({ new_debt: 0, debt_repayment: 0, new_equity: 0, dividend_per_share: 0 });
  const [plantDecisions, setPlantDecisions] = useState([]);
  const [partnerships, setPartnerships] = useState([]);
  const [esg, setEsg] = useState({ environmental_investment: 0, social_investment: 0, governance_commitments: [] });
  const saveTimer = useRef(null);

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const res = await getStrategyContext(gameId, teamId);
      setContext(res.data);
      // Init from draft
      if (draft?.market_entries) setMarketEntries(draft.market_entries);
      if (draft?.financing) setFinancing(draft.financing);
      if (draft?.plant_decisions) setPlantDecisions(draft.plant_decisions);
      if (draft?.partnerships) setPartnerships(draft.partnerships);
      if (draft?.esg) setEsg(draft.esg);
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

  if (loading) return <LoadingSpinner />;
  if (!context) return <Alert message={t("strategy_page.unable_to_load")} type="error" />;

  const markets = context.markets || [];
  const entryModes = context.entry_modes || [];
  const strategyOptions = context.strategy_options || [];
  const financial = context.financial || {};
  const existingPartnerships = context.partnerships || [];
  const plants = context.plants || [];

  const items = [
    {
      key: 'entry',
      label: t('strategy_page.market_entry_exit'),
      children: (
        <Row gutter={[16, 16]}>
          {markets.map(m => {
            const hasPresence = m.entry_status === 'active';
            // eslint-disable-next-line no-unused-vars
            const _entry = marketEntries.find(e => e.market === m.id);
            return (
              <Col xs={24} md={8} key={m.id}>
                <Card size="small" title={m.name}>
                  <Tag color={hasPresence ? 'green' : 'default'}>
                    {hasPresence ? `${t('strategy_page.active')} (${m.entry_mode || t('strategy_page.export')})` : t('strategy_page.not_entered')}
                  </Tag>
                  {!hasPresence && !locked && (
                    <div style={{ marginTop: 12 }}>
                      <Select
                        placeholder={t("strategy_page.select_entry_mode")}
                        style={{ width: '100%', marginBottom: 8 }}
                        onChange={v => {
                          const mode = entryModes.find(em => em.id === v);
                          const newEntry = { market: m.id, entry_mode: v, action: 'enter', initial_investment: Number(mode?.capital_requirement || 0) };
                          const updated = [...marketEntries.filter(e => e.market !== m.id), newEntry];
                          setMarketEntries(updated);
                          autoSave('market-entry', { market_entries: updated });
                        }}
                      >
                        {entryModes.map(em => (
                          <Select.Option key={em.id} value={em.id}>
                            {em.name} ({fmt(em.capital_requirement)})
                          </Select.Option>
                        ))}
                      </Select>
                    </div>
                  )}
                  {hasPresence && !locked && (
                    <Button
                      size="small"
                      danger
                      style={{ marginTop: 8 }}
                      onClick={() => {
                        const updated = [...marketEntries.filter(e => e.market !== m.id),
                          { market: m.id, action: 'exit', entry_mode: null, initial_investment: 0 }];
                        setMarketEntries(updated);
                        autoSave('market-entry', { market_entries: updated });
                      }}
                    >
                      {t("strategy_page.exit_market")}
                    </Button>
                  )}
                </Card>
              </Col>
            );
          })}
        </Row>
      ),
    },
    {
      key: 'financing',
      label: t('strategy_page.financing_capital'),
      children: (
        <div>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={6}>
              <Statistic title={t("strategy_page.cash")} value={fmt(financial.cash_on_hand)} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title={t("strategy_page.debt")} value={fmt(financial.total_debt)} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title={t("strategy_page.equity")} value={fmt(financial.total_equity)} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title={t("strategy_page.de_ratio")} value={
                financial.total_equity > 0
                  ? (Number(financial.total_debt) / Number(financial.total_equity)).toFixed(2)
                  : 'N/A'
              } />
            </Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={12} md={6}>
              <Text>{t("strategy_page.raise_debt")}</Text>
              <InputNumber
                prefix="$" min={0} step={100000}
                value={financing.new_debt} disabled={locked}
                onChange={v => {
                  const f = { ...financing, new_debt: v || 0 };
                  setFinancing(f);
                  autoSave('financing', { financing: f });
                }}
                style={{ width: '100%' }}
              />
            </Col>
            <Col xs={12} md={6}>
              <Text>{t("strategy_page.repay_debt")}</Text>
              <InputNumber
                prefix="$" min={0} max={Number(financial.total_debt) || 0} step={100000}
                value={financing.debt_repayment} disabled={locked}
                onChange={v => {
                  const f = { ...financing, debt_repayment: v || 0 };
                  setFinancing(f);
                  autoSave('financing', { financing: f });
                }}
                style={{ width: '100%' }}
              />
            </Col>
            <Col xs={12} md={6}>
              <Text>{t("strategy_page.issue_equity")}</Text>
              <InputNumber
                prefix="$" min={0} step={100000}
                value={financing.new_equity} disabled={locked}
                onChange={v => {
                  const f = { ...financing, new_equity: v || 0 };
                  setFinancing(f);
                  autoSave('financing', { financing: f });
                }}
                style={{ width: '100%' }}
              />
            </Col>
            <Col xs={12} md={6}>
              <Text>{t("strategy_page.dividend_share")}</Text>
              <InputNumber
                prefix="$" min={0} step={0.1}
                value={financing.dividend_per_share} disabled={locked}
                onChange={v => {
                  const f = { ...financing, dividend_per_share: v || 0 };
                  setFinancing(f);
                  autoSave('financing', { financing: f });
                }}
                style={{ width: '100%' }}
              />
            </Col>
          </Row>
        </div>
      ),
    },
    {
      key: 'capacity',
      label: t('strategy_page.production_capacity'),
      children: (
        <Row gutter={[16, 16]}>
          {markets.filter(m => m.allows_manufacturing).map(m => {
            const plant = plants.find(p => p.market_id === m.id);
            return (
              <Col xs={24} md={8} key={m.id}>
                <Card size="small" title={m.name}>
                  {plant ? (
                    <div>
                      <Tag color={plant.status === 'operational' ? 'green' : 'orange'}>{plant.status}</Tag>
                      <Text style={{ display: 'block', marginTop: 8 }}>{t("strategy_page.capacity")}: {plant.capacity_units} {t("strategy_page.units")}</Text>
                    </div>
                  ) : (
                    <div>
                      <Text type="secondary">{t("strategy_page.no_plant")}</Text>
                      {!locked && (
                        <Button
                          size="small"
                          type="primary"
                          style={{ marginTop: 8 }}
                          onClick={() => {
                            const pd = [...plantDecisions, { market: m.id, action: 'build', capacity_units: 0, contract_mfg_volume: 0 }];
                            setPlantDecisions(pd);
                            autoSave('plants', { plant_decisions: pd });
                          }}
                        >
                          {t("strategy_page.build_plant")}
                        </Button>
                      )}
                    </div>
                  )}
                  {m.contract_mfg_available && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>{t("strategy_page.contract_mfg_available")}</Text>
                    </div>
                  )}
                </Card>
              </Col>
            );
          })}
        </Row>
      ),
    },
    {
      key: 'partnerships',
      label: t('strategy_page.partnerships_alliances'),
      children: (
        <div>
          {existingPartnerships.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>{t("strategy_page.active_partnerships")}</Text>
              {existingPartnerships.map(p => (
                <Card key={p.id} size="small" style={{ marginTop: 8 }}>
                  <Space>
                    <Text>{p.strategy_option_name}</Text>
                    <Tag>{p.market_name}</Tag>
                    <Text type="secondary">{fmt(p.annual_investment)}/round</Text>
                  </Space>
                </Card>
              ))}
            </div>
          )}
          {!locked && (
            <Card size="small" title={t("strategy_page.establish_new")}>
              <Row gutter={[16, 16]}>
                {markets.filter(m => m.entry_status === 'active').map(m => (
                  <Col xs={24} md={8} key={m.id}>
                    <Text strong style={{ display: 'block', marginBottom: 8 }}>{m.name}</Text>
                    {strategyOptions.map(so => (
                      <Button
                        key={so.id}
                        size="small"
                        style={{ marginBottom: 4, marginRight: 4 }}
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
                        {so.name} ({fmt(so.capital_cost_base)})
                      </Button>
                    ))}
                  </Col>
                ))}
              </Row>
            </Card>
          )}
        </div>
      ),
    },
    {
      key: 'ma',
      label: t('strategy_page.ma'),
      children: (
        <Card>
          <Text type="secondary">{t("strategy_page.ma_desc")}</Text>
        </Card>
      ),
    },
    {
      key: 'esg',
      label: t('strategy_page.esg'),
      children: (
        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <Card size="small" title={t("strategy_page.environmental")}>
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
          <Col xs={24} md={8}>
            <Card size="small" title={t("strategy_page.social_programs")}>
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
          <Col xs={24} md={8}>
            <Card size="small" title={t("strategy_page.governance")}>
              <Checkbox.Group
                value={esg.governance_commitments}
                disabled={locked}
                onChange={v => {
                  const e = { ...esg, governance_commitments: v };
                  setEsg(e);
                  autoSave('esg', { esg: e });
                }}
              >
                <Space direction="vertical">
                  <Checkbox value="board_diversity">{t("strategy_page.board_diversity_commitment")}</Checkbox>
                  <Checkbox value="supply_chain_audit">{t("strategy_page.supply_chain_audit")}</Checkbox>
                  <Checkbox value="carbon_reporting">{t("strategy_page.carbon_reporting")}</Checkbox>
                  <Checkbox value="fair_labor">{t("strategy_page.fair_labor")}</Checkbox>
                </Space>
              </Checkbox.Group>
            </Card>
          </Col>
        </Row>
      ),
    },
    {
      key: 'research',
      label: t('strategy_page.research_console'),
      children: (
        <Card>
          <Text type="secondary">{t("strategy_page.research_coming_soon")}</Text>
          <div style={{ marginTop: 16 }}>
            {(context.markets || []).map(m => (
              m.market_outlook_narrative && (
                <Card key={m.id} size="small" style={{ marginBottom: 8 }}>
                  <Text strong>{m.name}</Text>
                  <br />
                  <Text type="secondary">{m.market_outlook_narrative}</Text>
                </Card>
              )
            ))}
          </div>
        </Card>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={t("strategy_page.title")}
        subtitle={t("strategy_page.subtitle")}
        actions={saving ? <Tag color="processing">{t("strategy_page.saving")}</Tag> : null}
      />
      <Collapse defaultActiveKey={['entry', 'financing']} items={items} />
    </div>
  );
};

export default StrategyPage;
