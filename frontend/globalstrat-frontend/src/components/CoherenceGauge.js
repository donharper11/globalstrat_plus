import React from 'react';

const CoherenceGauge = ({ score = 0, size = 120 }) => {
  const color = score >= 70 ? '#4CAF50' : score >= 40 ? '#FF9800' : '#F44336';
  return (
    <div style={{ position: 'relative', width: size, height: size, display: 'inline-block' }}>
      <svg viewBox="0 0 36 36" style={{ width: '100%', height: '100%' }}>
        <path
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none" stroke="#eee" strokeWidth="3"
        />
        <path
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${score}, 100`}
          strokeLinecap="round"
        />
      </svg>
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%, -50%)', textAlign: 'center',
      }}>
        <span style={{ fontSize: size * 0.2, fontWeight: 'bold', color }}>{Math.round(score)}</span>
      </div>
    </div>
  );
};

export default CoherenceGauge;
