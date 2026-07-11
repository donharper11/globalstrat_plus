import React from 'react';
import { Tag, Space, Tooltip } from 'antd';
import {
  CheckCircleOutlined, EditOutlined, LockOutlined, EyeOutlined, MinusCircleOutlined,
} from '@ant-design/icons';

// CC-23A: one shared operational-state vocabulary used across the SC dashboard
// and every SC decision page, so the same state concept always looks the same.
export const SC_STATE = {
  current: { color: 'green', icon: <CheckCircleOutlined />, label: 'Current (saved)',
    help: 'Matches the last saved decision for this round.' },
  draft: { color: 'gold', icon: <EditOutlined />, label: 'Draft — unsaved',
    help: 'You have edits on screen that have not been saved yet.' },
  locked: { color: 'default', icon: <LockOutlined />, label: 'Locked',
    help: 'Locked for this round — not editable by students.' },
  readonly: { color: 'default', icon: <EyeOutlined />, label: 'Read-only',
    help: 'This round is not open for submissions.' },
  unavailable: { color: 'blue', icon: <MinusCircleOutlined />, label: 'Not available',
    help: 'This operational state is not generated yet (pending engine/state bundle).' },
};

export const StateBadge = ({ state, text }) => {
  const s = SC_STATE[state] || SC_STATE.unavailable;
  return (
    <Tooltip title={s.help}>
      <Tag color={s.color} icon={s.icon} style={{ margin: 0 }}>{text || s.label}</Tag>
    </Tooltip>
  );
};

// Compute a decision page's overall state from its edit context.
export const pageState = ({ locked, editable, dirty }) => {
  if (locked) return 'locked';
  if (!editable) return 'readonly';
  return dirty ? 'draft' : 'current';
};

export const StateLegend = () => (
  <Space wrap size={4} style={{ marginBottom: 12 }}>
    <span style={{ fontSize: 12, color: '#888' }}>State legend:</span>
    {['current', 'draft', 'locked', 'readonly', 'unavailable'].map((k) => (
      <Tag key={k} color={SC_STATE[k].color} icon={SC_STATE[k].icon}>{SC_STATE[k].label}</Tag>
    ))}
  </Space>
);
