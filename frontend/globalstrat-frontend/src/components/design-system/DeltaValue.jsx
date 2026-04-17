import React from 'react';

function DeltaValue({ current, previous, format = 'number', precision = 0 }) {
  const delta = current - (previous || 0);
  const pctChange = previous ? ((delta / Math.abs(previous)) * 100) : 0;
  const isPositive = delta > 0;
  const isNegative = delta < 0;

  const formatValue = (v) => {
    if (v == null) return '—';
    if (format === 'currency') {
      const n = Number(v);
      if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
      if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
      return `$${n.toFixed(0)}`;
    }
    if (format === 'percent') return `${Number(v).toFixed(precision)}%`;
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: precision });
  };

  return (
    <span className="delta-value">
      <span className="delta-current">{formatValue(current)}</span>
      {previous !== undefined && previous !== null && delta !== 0 && (
        <span className={`delta-change ${isPositive ? 'positive' : isNegative ? 'negative' : 'neutral'}`}>
          {isPositive ? '▲' : isNegative ? '▼' : '–'}
          {Math.abs(pctChange).toFixed(1)}%
        </span>
      )}
    </span>
  );
}

export default DeltaValue;
