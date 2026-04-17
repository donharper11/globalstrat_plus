import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Card, Typography, InputNumber, Row, Col, Tag, Statistic, Alert, Progress, Divider, Tabs } from 'antd';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { useAuth } from '../AuthContext';
import { getFinanceContext, patchDecision, getTaxStructureContext, setTaxStructure } from '../api/decisions';
import { PanelCard, PageHeader, MetricRow } from '../components/design-system';
import BudgetBar from '../components/BudgetBar';
import LoadingSpinner from '../components/LoadingSpinner';
import WarningBanner from '../components/WarningBanner';
import TeamActivityBanner from '../components/TeamActivityBanner';

const { Title, Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const ratioColor = (val, greenMax, yellowMax) => {
  const n = Number(val);
  if (n <= greenMax) return 'green';
  if (n <= yellowMax) return 'orange';
  return 'red';
};

const FinancePage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { draft, locked } = useDecisions();
  const { user } = useAuth();
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [budgetAllocation, setBudgetAllocation] = useState({
    rd_budget: 0, marketing_budget: 0, strategy_budget: 0,
  });
  const [financing, setFinancing] = useState({
    new_debt: 0, debt_repayment: 0, new_equity: 0, dividend_per_share: 0,
  });
  const saveTimer = useRef(null);
  const [taxData, setTaxData] = useState(null);
  const [selectedStructure, setSelectedStructure] = useState('direct');
  const [taxSaving, setTaxSaving] = useState(false);

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const res = await getFinanceContext(gameId, teamId);
      setContext(res.data);
      const ba = draft?.budget_allocation || res.data?.budget_status || {};
      setBudgetAllocation({
        rd_budget: Number(ba.rd_budget || ba.rd_allocated || 0),
        marketing_budget: Number(ba.marketing_budget || ba.marketing_allocated || 0),
        strategy_budget: Number(ba.strategy_budget || ba.strategy_allocated || 0),
      });
      const fd = draft?.financing || res.data?.capital?.financing_draft || {};
      setFinancing({
        new_debt: Number(fd.new_debt || 0),
        debt_repayment: Number(fd.debt_repayment || 0),
        new_equity: Number(fd.new_equity || 0),
        dividend_per_share: Number(fd.dividend_per_share || 0),
      });
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId, draft]);

  useEffect(() => { loadContext(); }, [loadContext]);

  useEffect(() => {
    if (!gameId || !teamId) return;
    getTaxStructureContext(gameId, teamId)
      .then(res => {
        setTaxData(res.data);
        setSelectedStructure(res.data?.current?.code || 'direct');
      })
      .catch(() => {});
  }, [gameId, teamId]);

  const autoSaveBudget = useCallback(() => {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!gameId || !teamId || !currentRound || locked) return;
      setSaving(true);
      try {
        await patchDecision(gameId, teamId, currentRound, 'budget', {
          budget_allocation: budgetAllocation,
        });
        refreshBudgets();
      } catch { /* ignore */ }
      setSaving(false);
    }, 2000);
  }, [gameId, teamId, currentRound, locked, budgetAllocation, refreshBudgets]);

  const autoSaveFinancing = useCallback(() => {
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      if (!gameId || !teamId || !currentRound || locked) return;
      setSaving(true);
      try {
        await patchDecision(gameId, teamId, currentRound, 'financing', {
          financing,
        });
        refreshBudgets();
      } catch { /* ignore */ }
      setSaving(false);
    }, 2000);
  }, [gameId, teamId, currentRound, locked, financing, refreshBudgets]);

  const updateBudget = (field, value) => {
    setBudgetAllocation(prev => ({ ...prev, [field]: value || 0 }));
    autoSaveBudget();
  };

  const updateFinancing = (field, value) => {
    setFinancing(prev => ({ ...prev, [field]: value || 0 }));
    autoSaveFinancing();
  };

  const handleTaxChange = async (code) => {
    if (locked || !gameId || !teamId) return;
    setTaxSaving(true);
    try {
      await setTaxStructure(gameId, teamId, code);
      setSelectedStructure(code);
      // Reload to get updated state
      const res = await getTaxStructureContext(gameId, teamId);
      setTaxData(res.data);
    } catch { /* ignore */ }
    setTaxSaving(false);
  };

  // Computed impact previews
  const impacts = useMemo(() => {
    if (!context) return {};
    const fin = context.financial || {};
    const cap = context.capital || {};
    const cash = Number(fin.cash_on_hand || 0);
    const debt = Number(fin.total_debt || 0);
    const equity = Number(fin.total_equity || 0);
    const shares = Number(fin.shares_outstanding || 1000000);
    const rate = Number(cap.interest_rate || 0.06);
    const maxDE = Number(cap.max_de_ratio || 2.0);
    const sharePrice = Number(cap.share_price || 0);
    const lastNetIncome = Number(cap.last_net_income || 0);

    // Debt impact
    const newTotalDebt = debt + financing.new_debt - financing.debt_repayment;
    const newDE = equity > 0 ? newTotalDebt / equity : 0;
    const newInterest = newTotalDebt * rate;
    const oldInterest = debt * rate;

    // Equity impact
    const newSharesIssued = sharePrice > 0 ? Math.round(financing.new_equity / sharePrice) : 0;
    const totalShares = shares + newSharesIssued;
    const dilutionPct = newSharesIssued > 0 ? newSharesIssued / totalShares : 0;
    const oldEPS = lastNetIncome / shares;
    const newEPS = lastNetIncome / totalShares;

    // Dividend impact
    const totalDividend = financing.dividend_per_share * totalShares;
    const payoutRatio = lastNetIncome > 0 ? totalDividend / lastNetIncome : 0;
    const cashAfterDividend = cash + financing.new_debt - financing.debt_repayment + financing.new_equity - totalDividend;

    // Investor reactions
    const debtGrowthReaction = financing.new_debt > 0 && newDE < 1.5 ? 'positive' : financing.new_debt > 0 ? 'negative' : 'neutral';
    const debtConservativeReaction = newDE > 0.8 ? 'negative' : 'neutral';
    const equityGrowthReaction = dilutionPct > 0.25 ? 'negative' : dilutionPct > 0 ? 'cautious' : 'neutral';
    const equityConservativeReaction = financing.new_equity > 0 ? 'positive' : 'neutral';
    const divGrowthReaction = payoutRatio > 0.30 ? 'negative' : 'neutral';
    const divConservativeReaction = payoutRatio > 0.10 ? 'positive' : 'neutral';

    return {
      newTotalDebt, newDE, newInterest, oldInterest, maxDE,
      newSharesIssued, totalShares, dilutionPct, oldEPS, newEPS,
      totalDividend, payoutRatio, cashAfterDividend,
      debtGrowthReaction, debtConservativeReaction,
      equityGrowthReaction, equityConservativeReaction,
      divGrowthReaction, divConservativeReaction,
      availableCredit: Number(cap.available_credit || 0),
      sharePrice, lastNetIncome,
    };
  }, [context, financing]);

  if (loading) return <LoadingSpinner />;
  if (!context) return <Alert message={t('finance.unable_to_load')} type="error" />;

  const financial = context.financial || {};
  const budgetStatus = context.budget_status || {};
  const ratios = context.key_ratios || {};
  const cap = context.capital || {};

  const totalAllocated = budgetAllocation.rd_budget + budgetAllocation.marketing_budget +
    budgetAllocation.strategy_budget;
  const cashAvailable = Number(financial.cash_on_hand || 0);

  const reactionTag = (reaction) => {
    if (reaction === 'positive') return <Tag color="green">{t('finance.favorable')}</Tag>;
    if (reaction === 'negative') return <Tag color="red">{t('finance.negative')}</Tag>;
    if (reaction === 'cautious') return <Tag color="orange">{t('finance.cautious')}</Tag>;
    return <Tag>{t('finance.neutral')}</Tag>;
  };

  const BudgetTab = () => {
    const { t } = useTranslation();
    return (
    <div>
      <PanelCard headerColor="financial" title={t('finance.current_budget_status')}>
        {budgetStatus.total_budget_available && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: '#f0f9ff', borderRadius: 6, border: '1px solid #bae0ff' }}>
            <Row gutter={[16, 12]}>
              <Col xs={24} sm={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('finance.available_budget')}</Text>
                <div><Text strong style={{ fontSize: 18 }}>{fmt(budgetStatus.total_budget_available)}</Text></div>
                <Text type="secondary" style={{ fontSize: 10 }}>{t('finance.base')} {fmt(budgetStatus.budget_base)} + 20% {t('finance.of_profit')} {fmt(budgetStatus.profit_share)}</Text>
              </Col>
              <Col xs={12} sm={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('finance.total_spent')}</Text>
                <div><Text strong style={{ fontSize: 18, color: budgetStatus.over_budget ? '#ef4444' : undefined }}>{fmt(budgetStatus.total_spent || 0)}</Text></div>
              </Col>
              <Col xs={12} sm={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('finance.remaining')}</Text>
                <div><Text strong style={{ fontSize: 18, color: (budgetStatus.remaining || 0) < 0 ? '#ef4444' : '#10b981' }}>{fmt(budgetStatus.remaining || budgetStatus.total_budget_available)}</Text></div>
              </Col>
            </Row>
          </div>
        )}
        <BudgetBar budgets={budgetStatus} />
      </PanelCard>

      <PanelCard headerColor="decision" title={t('finance.budget_allocation').toUpperCase()}>
        {totalAllocated > cashAvailable && (
          <WarningBanner message={t('finance.exceeds_cash', { allocated: fmt(totalAllocated), cash: fmt(cashAvailable) })} type="error" />
        )}
        <Row gutter={[16, 16]}>
          {[
            { key: 'rd_budget', label: t('finance.rd_budget') },
            { key: 'marketing_budget', label: t('finance.marketing_budget') },
            { key: 'strategy_budget', label: t('finance.strategy_budget') },
          ].map(b => (
            <Col xs={12} md={6} key={b.key}>
              <Text style={{ display: 'block', marginBottom: 4 }}>{b.label}</Text>
              <InputNumber
                prefix="$" min={0} step={100000}
                value={budgetAllocation[b.key]} disabled={locked}
                onChange={v => updateBudget(b.key, v)}
                style={{ width: '100%' }}
              />
            </Col>
          ))}
        </Row>
        <div style={{ marginTop: 12 }}>
          <Text type="secondary">
            {t('finance.total_allocated')}: {fmt(totalAllocated)} | {t('finance.unallocated')}: {fmt(cashAvailable - totalAllocated)}
          </Text>
          {budgetAllocation.rd_budget === 0 && <WarningBanner message={t('finance.rd_budget_zero')} style={{ marginTop: 8 }} />}
          {budgetAllocation.marketing_budget === 0 && <WarningBanner message={t('finance.marketing_budget_zero')} style={{ marginTop: 8 }} />}
        </div>
      </PanelCard>
    </div>
  );
  };

  const CapitalTab = () => {
    const { t } = useTranslation();
    return (
    <div>
      {/* Raise Debt */}
      <PanelCard headerColor="financial" title={t('finance.raise_debt')}>
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary">{t('finance.available_credit')}: </Text>
          <Text strong>{fmt(impacts.availableCredit)}</Text>
          <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
            {t('finance.based_on_equity_limit', { ratio: cap.max_de_ratio, max: fmt(Number(financial.total_equity || 0) * (cap.max_de_ratio || 2)), debt: fmt(financial.total_debt) })}
          </Text>
        </div>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Text style={{ display: 'block', marginBottom: 4 }}>{t('finance.loan_amount')}</Text>
            <InputNumber
              prefix="$" min={0} step={1000000}
              value={financing.new_debt} disabled={locked}
              onChange={v => updateFinancing('new_debt', v)}
              style={{ width: '100%' }}
            />
          </Col>
        </Row>
        {financing.new_debt > 0 && (
          <Card size="small" style={{ marginTop: 12, background: '#f8fafc' }} title={t('finance.loan_impact_preview')}>
            <Row gutter={[16, 8]}>
              <Col span={12}><Text type="secondary">{t('finance.new_total_debt')}:</Text></Col>
              <Col span={12}><Text strong>{fmt(impacts.newTotalDebt)}</Text></Col>
              <Col span={12}><Text type="secondary">{t('finance.interest_per_round')}:</Text></Col>
              <Col span={12}><Text strong>{fmt(impacts.newInterest)}</Text> <Text type="secondary">(was {fmt(impacts.oldInterest)})</Text></Col>
              <Col span={12}><Text type="secondary">{t('finance.new_de_ratio')}:</Text></Col>
              <Col span={12}>
                <Tag color={ratioColor(impacts.newDE, 1.0, 2.0)}>
                  {impacts.newDE.toFixed(2)}
                </Tag>
                <Text type="secondary">(was {Number(ratios.debt_to_equity || 0).toFixed(2)})</Text>
              </Col>
            </Row>
            <Divider style={{ margin: '8px 0' }} />
            <div><Text type="secondary">{t('finance.growth_investors')}: </Text>{reactionTag(impacts.debtGrowthReaction)}</div>
            <div><Text type="secondary">{t('finance.conservative_investors')}: </Text>{reactionTag(impacts.debtConservativeReaction)}</div>
          </Card>
        )}
      </PanelCard>

      {/* Repay Debt */}
      <PanelCard headerColor="financial" title={t('finance.repay_debt_title')}>
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary">{t('finance.outstanding_debt')}: </Text>
          <Text strong>{fmt(financial.total_debt)}</Text>
        </div>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Text style={{ display: 'block', marginBottom: 4 }}>{t('finance.repayment_amount')}</Text>
            <InputNumber
              prefix="$" min={0} max={Number(financial.total_debt || 0)} step={1000000}
              value={financing.debt_repayment} disabled={locked}
              onChange={v => updateFinancing('debt_repayment', v)}
              style={{ width: '100%' }}
            />
          </Col>
          {financing.debt_repayment > 0 && (
            <Col xs={24} md={16}>
              <div style={{ padding: '8px 12px', background: '#f8fafc', borderRadius: 4, marginTop: 4 }}>
                <div>
                  <Text type="secondary">{t('finance.interest_saved')}: </Text>
                  <Text strong style={{ color: '#3f8600' }}>{fmt(financing.debt_repayment * (cap.interest_rate || 0.06))}</Text>
                </div>
                <div>
                  <Text type="secondary">{t('finance.de_after_repayment')}: </Text>
                  <Tag color={ratioColor(impacts.newDE, 1.0, 2.0)}>{impacts.newDE.toFixed(2)}</Tag>
                </div>
              </div>
            </Col>
          )}
        </Row>
      </PanelCard>

      {/* Issue New Shares */}
      <PanelCard headerColor="financial" title={t('finance.issue_new_shares')}>
        <Row gutter={[16, 4]} style={{ marginBottom: 12 }}>
          <Col span={8}><Text type="secondary">{t('finance.current_shares')}:</Text><br /><Text>{Number(financial.shares_outstanding || 0).toLocaleString()}</Text></Col>
          <Col span={8}><Text type="secondary">{t('finance.share_price')}:</Text><br /><Text>${Number(impacts.sharePrice || 0).toFixed(2)}</Text></Col>
          <Col span={8}><Text type="secondary">{t('finance.market_cap')}:</Text><br /><Text>{fmt((financial.shares_outstanding || 0) * (impacts.sharePrice || 0))}</Text></Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Text style={{ display: 'block', marginBottom: 4 }}>{t('finance.amount_to_raise')}</Text>
            <InputNumber
              prefix="$" min={0} step={1000000}
              value={financing.new_equity} disabled={locked}
              onChange={v => updateFinancing('new_equity', v)}
              style={{ width: '100%' }}
            />
          </Col>
        </Row>
        {financing.new_equity > 0 && (
          <Card size="small" style={{ marginTop: 12, background: '#f8fafc' }} title={t('finance.equity_impact_preview')}>
            <Row gutter={[16, 8]}>
              <Col span={12}><Text type="secondary">{t('finance.new_shares_issued')}:</Text></Col>
              <Col span={12}><Text strong>~{impacts.newSharesIssued.toLocaleString()}</Text></Col>
              <Col span={12}><Text type="secondary">{t('finance.total_shares')}:</Text></Col>
              <Col span={12}><Text>{impacts.totalShares.toLocaleString()}</Text></Col>
              <Col span={12}><Text type="secondary">{t('finance.dilution')}:</Text></Col>
              <Col span={12}><Tag color={impacts.dilutionPct > 0.2 ? 'red' : 'orange'}>{(impacts.dilutionPct * 100).toFixed(1)}%</Tag></Col>
              <Col span={12}><Text type="secondary">{t('finance.new_eps')}:</Text></Col>
              <Col span={12}><Text>${impacts.newEPS.toFixed(2)} <Text type="secondary">(was ${impacts.oldEPS.toFixed(2)})</Text></Text></Col>
            </Row>
            <Divider style={{ margin: '8px 0' }} />
            <div><Text type="secondary">{t('finance.growth_investors')}: </Text>{reactionTag(impacts.equityGrowthReaction)}</div>
            <div><Text type="secondary">{t('finance.conservative_investors')}: </Text>{reactionTag(impacts.equityConservativeReaction)}</div>
          </Card>
        )}
      </PanelCard>

      {/* Dividend Policy */}
      <PanelCard headerColor="financial" title={t('finance.dividend_policy_title')}>
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary">{t('finance.last_net_income')}: </Text>
          <Text strong>{fmt(impacts.lastNetIncome)}</Text>
        </div>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Text style={{ display: 'block', marginBottom: 4 }}>{t('finance.dividend_per_share')}</Text>
            <InputNumber
              prefix="$" min={0} step={0.50}
              value={financing.dividend_per_share} disabled={locked}
              onChange={v => updateFinancing('dividend_per_share', v)}
              style={{ width: '100%' }}
            />
          </Col>
        </Row>
        {financing.dividend_per_share > 0 && (
          <Card size="small" style={{ marginTop: 12, background: '#f8fafc' }} title={t('finance.dividend_impact_preview')}>
            <Row gutter={[16, 8]}>
              <Col span={12}><Text type="secondary">{t('finance.total_payout')}:</Text></Col>
              <Col span={12}><Text strong>{fmt(impacts.totalDividend)}</Text></Col>
              <Col span={12}><Text type="secondary">{t('finance.payout_ratio')}:</Text></Col>
              <Col span={12}>
                <Tag color={impacts.payoutRatio > 0.5 ? 'red' : impacts.payoutRatio > 0.3 ? 'orange' : 'green'}>
                  {(impacts.payoutRatio * 100).toFixed(1)}% {t('finance.of_net_income')}
                </Tag>
              </Col>
              <Col span={12}><Text type="secondary">{t('finance.cash_after_dividend')}:</Text></Col>
              <Col span={12}>
                <Text strong style={{ color: impacts.cashAfterDividend >= 0 ? '#3f8600' : '#cf1322' }}>
                  {fmt(impacts.cashAfterDividend)}
                </Text>
              </Col>
            </Row>
            <Divider style={{ margin: '8px 0' }} />
            <div><Text type="secondary">{t('finance.growth_investors')}: </Text>{reactionTag(impacts.divGrowthReaction)}</div>
            <div><Text type="secondary">{t('finance.conservative_investors')}: </Text>{reactionTag(impacts.divConservativeReaction)}</div>
          </Card>
        )}
      </PanelCard>
    </div>
  );
  };

  const TaxTab = () => {
    const { t } = useTranslation();
    if (!taxData) return <Text type="secondary">{t('finance.loading_tax')}</Text>;
    const structures = taxData.structures || [];
    const current = taxData.current || {};
    const foreignRevenue = taxData.foreign_revenue || 0;
    const foreignTaxPaid = taxData.foreign_tax_paid || 0;
    const repatriationCosts = taxData.repatriation_costs || 0;
    const roundsRemaining = taxData.rounds_remaining || 8;

    return (
      <div>
        <PanelCard headerColor="financial" title={t('finance.tax_structure_title')}>
          <div style={{ marginBottom: 12, padding: '8px 12px', background: '#f0f9ff', borderRadius: 6, border: '1px solid #bae0ff' }}>
            <Row gutter={[16, 8]}>
              <Col xs={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('finance.foreign_revenue')}</Text>
                <div><Text strong>{fmt(foreignRevenue)}</Text></div>
              </Col>
              <Col xs={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('finance.foreign_tax_paid')}</Text>
                <div><Text strong>{fmt(foreignTaxPaid)}</Text></div>
              </Col>
              <Col xs={8}>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('finance.repatriation_costs')}</Text>
                <div><Text strong>{fmt(repatriationCosts)}</Text></div>
              </Col>
            </Row>
          </div>
          {taxSaving && <Tag color="processing" style={{ marginBottom: 8 }}>{t('finance.saving')}</Tag>}

          {structures.map(s => {
            const isSelected = selectedStructure === s.code;
            const isCurrent = current.code === s.code;
            const switchCost = !isCurrent && s.setup_cost > 0 ? s.setup_cost : 0;
            const hasConflict = s.anti_corruption_conflict && taxData.has_anti_corruption;

            // Estimate impact based on current foreign revenue
            const estTaxSavings = foreignTaxPaid * (s.effective_tax_reduction_pct / (taxData.avg_foreign_tax_rate || 0.25));
            const estRepatSavings = repatriationCosts * s.repatriation_cost_reduction_pct;
            const estNetBenefit = estTaxSavings + estRepatSavings - s.annual_maintenance_cost;
            const estAuditCost = s.audit_probability_per_round > 0
              ? (estTaxSavings * 3 * s.audit_penalty_multiplier * s.audit_probability_per_round)
              : 0;

            return (
              <Card
                key={s.code}
                size="small"
                style={{
                  marginBottom: 8,
                  border: isSelected ? '2px solid #1E40AF' : '1px solid #e2e8f0',
                  background: isSelected ? '#f8fafc' : '#fff',
                  cursor: locked ? 'default' : 'pointer',
                }}
                onClick={() => !locked && handleTaxChange(s.code)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{
                      display: 'inline-block', width: 16, height: 16, borderRadius: '50%',
                      border: isSelected ? '5px solid #1E40AF' : '2px solid #cbd5e1',
                      background: isSelected ? '#fff' : 'transparent',
                    }} />
                    <Text strong style={{ fontSize: 14 }}>{s.name}</Text>
                    {isCurrent && <Tag color="blue">{t('finance.current')}</Tag>}
                  </div>
                  {switchCost > 0 && !isCurrent && (
                    <Tag color="orange">Setup: {fmt(switchCost)}</Tag>
                  )}
                </div>

                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                  {s.description}
                </Text>

                <Row gutter={[12, 4]} style={{ fontSize: 12 }}>
                  <Col xs={12}>
                    <Text type="secondary">{t('finance.tax_benefit')}: </Text>
                    <Text strong>{s.effective_tax_reduction_pct > 0 ? `-${(s.effective_tax_reduction_pct * 100).toFixed(0)}% ${t('finance.effective_rate')}` : t('corporate_strategy.none')}</Text>
                  </Col>
                  <Col xs={12}>
                    <Text type="secondary">{t('finance.repatriation')}: </Text>
                    <Text strong>{s.repatriation_cost_reduction_pct > 0 ? `-${(s.repatriation_cost_reduction_pct * 100).toFixed(0)}%` : t('finance.no_improvement')}</Text>
                  </Col>
                  <Col xs={12}>
                    <Text type="secondary">{t('finance.audit_risk')}: </Text>
                    <Text strong style={{ color: s.audit_probability_per_round > 0.10 ? '#DC2626' : s.audit_probability_per_round > 0 ? '#D97706' : '#16A34A' }}>
                      {s.audit_probability_per_round > 0 ? `${(s.audit_probability_per_round * 100).toFixed(0)}%/${t('common.round').toLowerCase()} (${s.audit_penalty_multiplier}x ${t('finance.penalty')})` : t('corporate_strategy.none')}
                    </Text>
                  </Col>
                  <Col xs={12}>
                    <Text type="secondary">{t('finance.cost')}: </Text>
                    <Text strong>{s.annual_maintenance_cost > 0 ? `${fmt(s.annual_maintenance_cost)}/${t('common.round').toLowerCase()}` : `$0/${t('common.round').toLowerCase()}`}</Text>
                  </Col>
                </Row>

                {/* Investor/Regulator reactions */}
                <div style={{ marginTop: 6, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {s.value_investor_modifier !== 0 && (
                    <Tag color={s.value_investor_modifier > 0 ? 'green' : 'red'} style={{ fontSize: 10 }}>
                      Granite: {s.value_investor_modifier > 0 ? '+' : ''}{(s.value_investor_modifier * 100).toFixed(0)}%
                    </Tag>
                  )}
                  {s.esg_investor_modifier !== 0 && (
                    <Tag color={s.esg_investor_modifier > 0 ? 'green' : 'red'} style={{ fontSize: 10 }}>
                      GreenHorizon: {s.esg_investor_modifier > 0 ? '+' : ''}{(s.esg_investor_modifier * 100).toFixed(0)}%
                    </Tag>
                  )}
                  {s.regulator_modifier !== 0 && (
                    <Tag color={s.regulator_modifier > 0 ? 'green' : 'red'} style={{ fontSize: 10 }}>
                      Regulators: {s.regulator_modifier > 0 ? '+' : ''}{(s.regulator_modifier * 100).toFixed(0)}%
                    </Tag>
                  )}
                </div>

                {/* Hypocrisy warning */}
                {hasConflict && (
                  <Alert
                    type="error" showIcon banner
                    style={{ marginTop: 8, fontSize: 11 }}
                    message={t('finance.conflict_anti_corruption')}
                    description={t('finance.conflict_anti_corruption_desc')}
                  />
                )}

                {/* Impact preview for non-direct structures when selected */}
                {isSelected && s.code !== 'direct' && foreignRevenue > 0 && (
                  <Card size="small" style={{ marginTop: 8, background: '#f1f5f9' }} title={<Text style={{ fontSize: 12 }}>{t('finance.estimated_impact')}</Text>}>
                    <Row gutter={[12, 4]} style={{ fontSize: 12 }}>
                      <Col span={14}><Text type="secondary">{t('finance.tax_savings')}:</Text></Col>
                      <Col span={10}><Text strong style={{ color: '#16A34A' }}>{fmt(estTaxSavings)}/{t('common.round').toLowerCase()}</Text></Col>
                      <Col span={14}><Text type="secondary">{t('finance.repatriation_savings')}:</Text></Col>
                      <Col span={10}><Text strong style={{ color: '#16A34A' }}>{fmt(estRepatSavings)}/{t('common.round').toLowerCase()}</Text></Col>
                      <Col span={14}><Text type="secondary">{t('finance.maintenance_cost')}:</Text></Col>
                      <Col span={10}><Text strong style={{ color: '#DC2626' }}>-{fmt(s.annual_maintenance_cost)}/{t('common.round').toLowerCase()}</Text></Col>
                      <Col span={14}><Text type="secondary">{t('finance.net_benefit')}:</Text></Col>
                      <Col span={10}>
                        <Text strong style={{ color: estNetBenefit >= 0 ? '#16A34A' : '#DC2626' }}>
                          {estNetBenefit >= 0 ? '+' : ''}{fmt(estNetBenefit)}/round
                        </Text>
                      </Col>
                    </Row>
                    {s.audit_probability_per_round > 0 && (
                      <div style={{ marginTop: 6, fontSize: 11 }}>
                        <Text type="secondary">
                          {(s.audit_probability_per_round * 100).toFixed(0)}% audit risk/round — expected audit cost ~{fmt(estAuditCost)} per audit.
                          {roundsRemaining > 0 && ` Expected value over ${roundsRemaining} remaining rounds: `}
                          {roundsRemaining > 0 && (
                            <Text strong style={{ color: (estNetBenefit * roundsRemaining - estAuditCost) > 0 ? '#16A34A' : '#DC2626' }}>
                              {(estNetBenefit * roundsRemaining - estAuditCost) > 0 ? 'net positive' : 'net negative if audited'}
                            </Text>
                          )}
                        </Text>
                      </div>
                    )}
                  </Card>
                )}
              </Card>
            );
          })}
        </PanelCard>

        {/* Audit History */}
        {current.times_audited > 0 && (
          <PanelCard headerColor="neutral" title={t('finance.audit_history').toUpperCase()}>
            <Row gutter={[16, 8]}>
              <Col span={12}>
                <Text type="secondary">{t('finance.times_audited')}:</Text>{' '}
                <Text strong>{current.times_audited}</Text>
                {current.last_audit_round != null && (
                  <Text type="secondary"> ({t('finance.last')}: {t('common.round')} {current.last_audit_round})</Text>
                )}
              </Col>
              <Col span={12}>
                <Text type="secondary">{t('finance.total_penalties_paid')}:</Text>{' '}
                <Text strong style={{ color: '#DC2626' }}>{fmt(current.cumulative_audit_penalties)}</Text>
              </Col>
            </Row>
            {current.cumulative_tax_savings > 0 && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary">{t('finance.cumulative_tax_savings')}:</Text>{' '}
                <Text strong style={{ color: '#16A34A' }}>{fmt(current.cumulative_tax_savings)}</Text>
              </div>
            )}
          </PanelCard>
        )}
      </div>
    );
  };

  const tabItems = [
    {
      key: 'budget',
      label: t('finance.budget_allocation'),
      children: <BudgetTab />,
    },
    {
      key: 'tax',
      label: t('finance.tax_structure'),
      children: <TaxTab />,
    },
    {
      key: 'capital',
      label: t('finance.capital_management'),
      children: <CapitalTab />,
    },
  ];

  return (
    <div>
      <TeamActivityBanner gameId={gameId} teamId={teamId} currentRound={currentRound} currentUserId={user?.user_id} />
      <PageHeader
        title={t('finance.title')}
        subtitle={`${t('common.round')} ${currentRound} · ${t('finance.capital_management')} & ${t('finance.budget_allocation')}`}
        status={locked ? 'locked' : 'draft'}
        actions={saving ? <Tag color="processing">{t('finance.saving')}</Tag> : null}
      />

      {/* Financial Position Summary */}
      <MetricRow metrics={[
        { label: t('finance.cash_on_hand').toUpperCase(), value: fmt(financial.cash_on_hand), size: 'large' },
        { label: t('finance.total_debt').toUpperCase(), value: fmt(financial.total_debt), size: 'large' },
        { label: t('finance.total_equity').toUpperCase(), value: fmt(financial.total_equity), size: 'large' },
        { label: t('finance.debt_equity').toUpperCase(), value: Number(ratios.debt_to_equity || 0).toFixed(2), size: 'large',
          status: Number(ratios.debt_to_equity || 0) < 1 ? 'positive' : Number(ratios.debt_to_equity || 0) < 2 ? 'warning' : 'negative' },
      ]} />

      <Tabs className="ds-colored-tabs" items={tabItems} defaultActiveKey="budget" />
    </div>
  );
};

export default FinancePage;
