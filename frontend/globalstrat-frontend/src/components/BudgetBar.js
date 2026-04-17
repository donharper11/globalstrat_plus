import React from 'react';
import { Progress, Typography, Space } from 'antd';
import { useTranslation } from 'react-i18next';

const { Text } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const BudgetBar = ({ budgets }) => {
  const { t } = useTranslation();
  if (!budgets) return null;

  const categories = [
    { key: 'rd', label: t('budget.rd'), color: '#1E40AF', allocated: budgets.rd_allocated, spent: budgets.rd_spent },
    { key: 'marketing', label: t('budget.marketing'), color: '#059669', allocated: budgets.marketing_allocated, spent: budgets.marketing_spent },
    { key: 'strategy', label: t('budget.strategy'), color: '#7C3AED', allocated: budgets.strategy_allocated, spent: budgets.strategy_spent },
  ];

  return (
    <div style={{ padding: '8px 0' }}>
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        {categories.map(cat => {
          const allocated = Number(cat.allocated) || 0;
          const spent = Number(cat.spent) || 0;
          const pct = allocated > 0 ? Math.round((spent / allocated) * 100) : 0;
          return (
            <div key={cat.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text style={{ width: 70, fontSize: 12, color: '#64748B' }}>{cat.label}</Text>
              <Progress
                percent={pct}
                size="small"
                strokeColor={cat.color}
                style={{ flex: 1, marginBottom: 0 }}
                format={() => `${fmt(spent)} / ${fmt(allocated)}`}
              />
            </div>
          );
        })}
        {budgets.unallocated != null && (
          <Text type="secondary" style={{ fontSize: 11 }}>
            {t('budget.unallocated', { amount: fmt(budgets.unallocated) })}
          </Text>
        )}
      </Space>
    </div>
  );
};

export default BudgetBar;
