import React from 'react';
import { Tag, Space, Tooltip } from 'antd';
import {
  CheckCircleOutlined, EditOutlined, LockOutlined, EyeOutlined, MinusCircleOutlined,
} from '@ant-design/icons';

// CC-23A: one shared operational-state vocabulary used across the SC dashboard
// and every SC decision page, so the same state concept always looks the same.
export const SC_STATE = {
  current: { color: 'green', icon: <CheckCircleOutlined />, label: 'Saved',
    help: 'This matches what you last saved.' },
  draft: { color: 'gold', icon: <EditOutlined />, label: 'Unsaved changes',
    help: "You've made changes that aren't saved yet." },
  locked: { color: 'default', icon: <LockOutlined />, label: 'Locked',
    help: "This is locked for the round and can't be changed." },
  readonly: { color: 'default', icon: <EyeOutlined />, label: 'View only',
    help: "This round isn't open for changes right now." },
  unavailable: { color: 'blue', icon: <MinusCircleOutlined />, label: 'Not yet',
    help: 'This updates automatically as the simulation runs each round.' },
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
