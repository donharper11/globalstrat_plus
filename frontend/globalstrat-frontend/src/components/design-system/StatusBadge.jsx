import React from 'react';
import { useTranslation } from 'react-i18next';

const styleConfigs = {
  active: { bg: '#DCFCE7', color: '#166534' },
  draft: { bg: '#DBEAFE', color: '#1E40AF' },
  locked: { bg: '#F3E8FF', color: '#6B21A8' },
  developing: { bg: '#FEF3C7', color: '#92400E' },
  retired: { bg: '#F1F5F9', color: '#64748B' },
  distress: { bg: '#FEE2E2', color: '#991B1B' },
  budget: { bg: '#E0F2FE', color: '#0369A1' },
  mainstream: { bg: '#F0FDF4', color: '#15803D' },
  premium: { bg: '#FDF4FF', color: '#7E22CE' },
  ultra_premium: { bg: '#FDF4FF', color: '#7E22CE' },
  open: { bg: '#DBEAFE', color: '#1E40AF' },
  pending: { bg: '#FEF3C7', color: '#92400E' },
  processed: { bg: '#DCFCE7', color: '#166534' },
  operational: { bg: '#DCFCE7', color: '#166534' },
};

const textKeys = {
  active: 'common.active',
  draft: 'common.in_progress',
  locked: 'common.locked',
  developing: 'common.developing',
  retired: 'common.retired',
  distress: 'common.distress',
  budget: 'common.budget_tier',
  mainstream: 'common.mainstream',
  premium: 'common.premium',
  ultra_premium: 'common.ultra_premium',
  open: 'common.open',
  pending: 'common.pending',
  processed: 'common.processed',
  operational: 'common.operational',
};

function StatusBadge({ status, label }) {
  const { t } = useTranslation();
  const style = styleConfigs[status] || { bg: '#F1F5F9', color: '#64748B' };
  const text = textKeys[status] ? t(textKeys[status]) : (status || '—');
  return (
    <span className="status-badge" style={{ background: style.bg, color: style.color }}>
      {label || text}
    </span>
  );
}

export default StatusBadge;
