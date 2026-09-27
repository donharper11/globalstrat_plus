import React from 'react';
import { Collapse, Tag, Typography } from 'antd';

const { Text, Paragraph } = Typography;

const BAND_COLORS = {
  strong: '#52c41a',
  developing: '#faad14',
  needs_attention: '#ff4d4f',
};

const DIMENSION_LABELS = {
  coherence_ext: { en: 'Strategic Coherence', zh: '战略一致性' },
  responsiveness: { en: 'Event Responsiveness', zh: '事件响应' },
  trajectory: { en: 'Strategic Trajectory', zh: '战略轨迹' },
  justification: { en: 'Reasoning Depth', zh: '推理深度' },
};

const BAND_LABELS = {
  strong: { en: 'Strong', zh: '优秀' },
  developing: { en: 'Developing', zh: '发展中' },
  needs_attention: { en: 'Needs Attention', zh: '需改进' },
};

const ReasoningDimensionFeedback = ({ dimensions, narrative, language = 'en' }) => {
  const lang = language === 'zh-CN' ? 'zh' : 'en';

  if (!dimensions) return null;

  const items = Object.entries(dimensions).map(([key, dim]) => {
    const label = DIMENSION_LABELS[key]?.[lang] || key;
    const bandLabel = BAND_LABELS[dim.band]?.[lang] || dim.band;
    const bandColor = BAND_COLORS[dim.band] || '#999';

    return {
      key,
      label: (
        <span style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
          <span>{label}</span>
          <Tag color={bandColor} style={{ marginLeft: 8, fontSize: 11 }}>
            {bandLabel}
          </Tag>
        </span>
      ),
      children: (
        <div>
          <Paragraph style={{ margin: 0 }}>{dim.feedback}</Paragraph>
          {dim.pattern && (
            <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
              Pattern: {dim.pattern}
            </Text>
          )}
          {dim.depth && (
            <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
              Depth: {dim.depth.replace('_', ' ')}
            </Text>
          )}
        </div>
      ),
    };
  });

  return (
    <div>
      <Collapse items={items} size="small" />
      {narrative && (
        <div style={{
          marginTop: 12, padding: 12, background: '#fafafa',
          borderRadius: 6, border: '1px solid #f0f0f0',
        }}>
          <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            {lang === 'zh' ? '详细反馈' : 'Detailed Feedback'}
          </Text>
          <Paragraph style={{ margin: 0, fontSize: 13, whiteSpace: 'pre-wrap' }}>
            {narrative}
          </Paragraph>
        </div>
      )}
    </div>
  );
};

export default ReasoningDimensionFeedback;
