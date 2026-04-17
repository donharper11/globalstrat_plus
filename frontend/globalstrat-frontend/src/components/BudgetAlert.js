import React from 'react';
import { Alert } from 'antd';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const BudgetAlert = () => {
  const { t } = useTranslation();
  const { budgets } = useGame();

  if (!budgets || !budgets.over_budget) return null;

  const overage = (budgets.total_spent || 0) - (budgets.total_budget_available || 0);

  return (
    <Alert
      type="warning"
      showIcon
      banner
      message={t('budget.over_budget', { overage: fmt(overage), spent: fmt(budgets.total_spent), available: fmt(budgets.total_budget_available) })}
      style={{ marginBottom: 12 }}
    />
  );
};

export default BudgetAlert;
