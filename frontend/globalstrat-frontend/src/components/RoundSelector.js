import React from 'react';
import { useTranslation } from 'react-i18next';
import { Select, Typography } from 'antd';

const { Text } = Typography;

const RoundSelector = ({ currentRound, maxRound, minRound = 1, onChange }) => {
  const { t } = useTranslation();

  const options = [];
  for (let i = minRound; i <= maxRound; i++) {
    options.push({ value: i, label: `${t('common.round')} ${i}` });
  }

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <Text strong>{t('common.view_round')}</Text>
      <Select
        value={currentRound}
        onChange={onChange}
        options={options}
        style={{ width: 120 }}
      />
    </div>
  );
};

export default RoundSelector;
