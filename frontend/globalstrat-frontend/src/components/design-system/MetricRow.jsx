import React from 'react';
import MetricCard from './MetricCard';

function MetricRow({ metrics }) {
  return (
    <div className="ds-metric-row">
      {metrics.map((m, i) => (
        <MetricCard key={i} {...m} />
      ))}
    </div>
  );
}

export default MetricRow;
