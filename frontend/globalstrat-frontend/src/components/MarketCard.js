import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Tag, Typography, Space } from 'antd';

const { Text } = Typography;

const MarketCard = ({ market, presence, onClick }) => {
  const { t } = useTranslation();

  if (!market) return null;
  const statusColor = presence ? 'green' : 'default';
  const statusText = presence ? t('common.active') : t('market_strategy.not_entered');

  return (
    <Card
      size="small"
      hoverable={!!onClick}
      onClick={onClick}
      style={{ marginBottom: 8 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Text strong>{market.name}</Text>
          <Tag color={statusColor} style={{ marginLeft: 8 }}>{statusText}</Tag>
        </div>
      </div>
      <Space size={16} style={{ marginTop: 8 }}>
        <Text type="secondary" style={{ fontSize: 11 }}>
          {t('market_strategy.growth')} {((Number(market.base_growth_rate) || 0) * 100).toFixed(0)}%
        </Text>
        <Text type="secondary" style={{ fontSize: 11 }}>
          {t('market_strategy.tariff')} {((Number(market.tariff_rate) || 0) * 100).toFixed(0)}%
        </Text>
        <Text type="secondary" style={{ fontSize: 11 }}>
          {t('market_strategy.tax')} {((Number(market.tax_rate) || 0) * 100).toFixed(0)}%
        </Text>
        <Text type="secondary" style={{ fontSize: 11 }}>
          {t('market_strategy.regulatory')} {market.regulatory_difficulty}/10
        </Text>
      </Space>
    </Card>
  );
};

export default MarketCard;
