import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';
import { Typography, Empty } from 'antd';

const { Text } = Typography;

const BAND_VALUES = {
  strong: 3,
  developing: 2,
  needs_attention: 1,
};

const BAND_COLORS = {
  3: '#52c41a',
  2: '#faad14',
  1: '#ff4d4f',
};

const BAND_LABELS = {
  3: 'Strong',
  2: 'Developing',
  1: 'Needs Attention',
};

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload || !payload[0]) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: '#fff', border: '1px solid #d9d9d9',
      padding: '6px 10px', borderRadius: 4, fontSize: 12,
    }}>
      <div>Round {d.round}</div>
      <div style={{ color: BAND_COLORS[d.value] || '#999' }}>
        {BAND_LABELS[d.value] || 'N/A'}
      </div>
      {d.pattern && (
        <div style={{ color: '#999', fontSize: 11 }}>{d.pattern}</div>
      )}
    </div>
  );
};

const ReasoningTrendChart = ({ history = [], height = 60 }) => {
  if (!history || history.length < 2) {
    return null;
  }

  const data = history.map(h => ({
    round: `R${h.round_number}`,
    value: BAND_VALUES[h.overall_band] || 2,
    pattern: h.trajectory_pattern,
  }));

  const latestColor = BAND_COLORS[data[data.length - 1]?.value] || '#1677ff';

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="reasoningTrend" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={latestColor} stopOpacity={0.3} />
              <stop offset="100%" stopColor={latestColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="round" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis domain={[0.5, 3.5]} hide />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={latestColor}
            strokeWidth={2}
            fill="url(#reasoningTrend)"
            dot={{ r: 3, fill: latestColor }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ReasoningTrendChart;
