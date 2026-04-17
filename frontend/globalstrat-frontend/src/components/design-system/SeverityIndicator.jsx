import React from 'react';

const statusColors = {
  positive: 'var(--color-positive)',
  warning: 'var(--color-warning)',
  negative: 'var(--color-negative)',
};

function SeverityIndicator({ value, thresholds = { good: 0.5, warning: 0.3 }, label = '', displayValue = '' }) {
  let status = 'positive';
  if (value < thresholds.warning) status = 'negative';
  else if (value < thresholds.good) status = 'warning';

  return (
    <div className="severity-row">
      {label && <span className="severity-label">{label}</span>}
      <div className="severity-indicator">
        <div
          className="severity-bar"
          style={{ width: `${Math.min(Math.max(value * 100, 2), 100)}%`, background: statusColors[status] }}
        />
      </div>
      {displayValue && <span className="severity-value">{displayValue}</span>}
    </div>
  );
}

export default SeverityIndicator;
