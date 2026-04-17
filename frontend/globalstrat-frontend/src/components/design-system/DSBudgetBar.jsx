import React from 'react';
import { useTranslation } from 'react-i18next';

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

function DSBudgetBar({ budgets }) {
  const { t } = useTranslation();

  const CATEGORIES = [
    { key: 'rd', label: t('topbar.rd_label'), color: 'var(--color-header-strategic)' },
    { key: 'marketing', label: t('topbar.mktg_label'), color: 'var(--color-header-decision)' },
    { key: 'strategy', label: t('topbar.strat_label'), color: 'var(--color-header-market)' },
  ];

  if (!budgets) return null;

  return (
    <div className="ds-budget-bar">
      {CATEGORIES.map(cat => {
        const allocated = Number(budgets[`${cat.key}_allocated`] || 0);
        const spent = Number(budgets[`${cat.key}_spent`] || 0);
        const pct = allocated > 0 ? Math.min((spent / allocated) * 100, 100) : 0;
        const over = spent > allocated;

        return (
          <div className="ds-budget-item" key={cat.key}>
            <div className="ds-budget-item-label">{cat.label}</div>
            <div className="ds-budget-item-bar">
              <div
                className="ds-budget-item-fill"
                style={{
                  width: `${pct}%`,
                  background: over ? 'var(--color-negative)' : cat.color,
                }}
              />
            </div>
            <div className="ds-budget-item-text">
              {fmt(spent)} / {fmt(allocated)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default DSBudgetBar;
