import React from 'react';
import { Select, Typography } from 'antd';

const { Text } = Typography;

/**
 * Which round's submission history the drill-down is showing.
 *
 * Extracted alongside AuditEvidenceTable so that "can an instructor reach a
 * previous round's evidence?" is a question a test can ask. The options are the
 * rounds that have actually been reached — offering round 5 of a game on round
 * 3 would invite a fetch that can only fail.
 */
export default function AuditRoundSelect({ value, currentRound, onChange, label = 'Round' }) {
  const rounds = Math.max(0, Number(currentRound) || 0);
  return (
    <div style={{ marginBottom: 12 }}>
      <Text strong>{label}: </Text>
      <Select
        value={value}
        onChange={onChange}
        style={{ width: 120 }}
        aria-label={label}
        options={Array.from({ length: rounds }, (_, i) => ({
          value: i + 1,
          label: `${label} ${i + 1}`,
        }))}
      />
    </div>
  );
}
