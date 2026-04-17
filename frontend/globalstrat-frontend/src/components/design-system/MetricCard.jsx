import React from 'react';

const statusColors = {
  positive: 'var(--color-positive)',
  negative: 'var(--color-negative)',
  warning: 'var(--color-warning)',
  neutral: 'var(--color-text-primary)',
};

function MetricCard({ label, value, unit = '', trend = null, trendLabel = '', size = 'medium', status = 'neutral' }) {
  const color = statusColors[status] || statusColors.neutral;

  return (
    <div className="ds-metric-card">
      <div className="ds-metric-label">{label}</div>
      <div className={`ds-metric-value metric-${size}`} style={{ color }}>
        {unit === '$' && '$'}{value}{unit === '%' && '%'}
      </div>
      {trend !== null && (
        <div className={`ds-metric-trend ${trend >= 0 ? 'trend-up' : 'trend-down'}`}>
          {trend >= 0 ? '▲' : '▼'} {Math.abs(trend)}{unit === '%' ? 'pp' : ''} {trendLabel}
        </div>
      )}
    </div>
  );
}

export default MetricCard;
