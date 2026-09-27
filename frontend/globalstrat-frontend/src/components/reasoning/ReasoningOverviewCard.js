import React from 'react';
import { Card, Tag, Typography, Space, Row, Col, Progress } from 'antd';
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

const { Text, Title } = Typography;

const BAND_CONFIG = {
  strong: { color: '#52c41a', icon: <CheckCircleOutlined />, bg: '#f6ffed' },
  developing: { color: '#faad14', icon: <ExclamationCircleOutlined />, bg: '#fffbe6' },
  needs_attention: { color: '#ff4d4f', icon: <WarningOutlined />, bg: '#fff2f0' },
};

const BAND_LABELS = {
  strong: 'Strong',
  developing: 'Developing',
  needs_attention: 'Needs Attention',
};

const BAND_LABELS_ZH = {
  strong: '优秀',
  developing: '发展中',
  needs_attention: '需改进',
};

const PATTERN_LABELS = {
  consistent: 'Consistent Executor',
  reactive: 'Reactive Adjuster',
  aggressive: 'Aggressive Expander',
  conservative: 'Conservative Optimizer',
  erratic: 'Erratic',
};

const ReasoningOverviewCard = ({ data, language = 'en' }) => {
  const { t } = useTranslation();

  if (!data || !data.available) {
    return null;
  }

  const bandLabels = language === 'zh-CN' ? BAND_LABELS_ZH : BAND_LABELS;
  const bandInfo = BAND_CONFIG[data.overall_band] || BAND_CONFIG.developing;
  const bandLabel = bandLabels[data.overall_band] || data.overall_band;

  return (
    <Card
      size="small"
      title={
        <Space>
          {bandInfo.icon}
          <span>{t('Strategic Reasoning', 'Strategic Reasoning')}</span>
        </Space>
      }
      style={{ borderLeft: `3px solid ${bandInfo.color}` }}
    >
      <Row gutter={16} align="middle">
        <Col span={8} style={{ textAlign: 'center' }}>
          <Tag
            color={bandInfo.color}
            style={{ fontSize: 14, padding: '4px 16px' }}
          >
            {bandLabel}
          </Tag>
          {data.trajectory_pattern && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                {PATTERN_LABELS[data.trajectory_pattern] || data.trajectory_pattern}
              </Text>
            </div>
          )}
        </Col>
        <Col span={16}>
          {data.dimensions && Object.entries(data.dimensions).map(([key, dim]) => {
            const dimBand = BAND_CONFIG[dim.band] || BAND_CONFIG.developing;
            const dimLabel = {
              coherence_ext: 'Strategic Coherence',
              responsiveness: 'Event Responsiveness',
              trajectory: 'Strategic Trajectory',
              justification: 'Reasoning Depth',
            }[key] || key;

            return (
              <div key={key} style={{ marginBottom: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                  <Text style={{ fontSize: 12 }}>{dimLabel}</Text>
                  <Tag color={dimBand.color} style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}>
                    {bandLabels[dim.band] || dim.band}
                  </Tag>
                </div>
              </div>
            );
          })}
        </Col>
      </Row>
    </Card>
  );
};

export default ReasoningOverviewCard;
