import React from 'react';
import { Tag, Space, Tooltip } from 'antd';
import {
  CheckCircleOutlined, EditOutlined, LockOutlined, EyeOutlined, MinusCircleOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

// CC-23A: one shared operational-state vocabulary used across the SC dashboard
// and every SC decision page, so the same state concept always looks the same.
// CC-23 (i18n): labels/help live in the `sc.state.*` translation namespace
// (EN + ZH); this module keeps only the language-neutral colour/icon + the
// translation key for each state.
export const SC_STATE = {
  current: { color: 'green', icon: <CheckCircleOutlined />, key: 'saved' },
  draft: { color: 'gold', icon: <EditOutlined />, key: 'unsaved' },
  locked: { color: 'default', icon: <LockOutlined />, key: 'locked' },
  readonly: { color: 'default', icon: <EyeOutlined />, key: 'view_only' },
  unavailable: { color: 'blue', icon: <MinusCircleOutlined />, key: 'not_yet' },
};

export const StateBadge = ({ state, text }) => {
  const { t } = useTranslation();
  const s = SC_STATE[state] || SC_STATE.unavailable;
  return (
    <Tooltip title={t(`sc.state.${s.key}.help`)}>
      <Tag color={s.color} icon={s.icon} style={{ margin: 0 }}>
        {text || t(`sc.state.${s.key}.label`)}
      </Tag>
    </Tooltip>
  );
};

// Compute a decision page's overall state from its edit context.
export const pageState = ({ locked, editable, dirty }) => {
  if (locked) return 'locked';
  if (!editable) return 'readonly';
  return dirty ? 'draft' : 'current';
};

export const StateLegend = () => {
  const { t } = useTranslation();
  return (
    <Space wrap size={4} style={{ marginBottom: 12 }}>
      <span style={{ fontSize: 12, color: '#888' }}>{t('sc.state.legend')}</span>
      {['current', 'draft', 'locked', 'readonly', 'unavailable'].map((k) => (
        <Tag key={k} color={SC_STATE[k].color} icon={SC_STATE[k].icon}>
          {t(`sc.state.${SC_STATE[k].key}.label`)}
        </Tag>
      ))}
    </Space>
  );
};
