import React from 'react';
import { useTranslation } from 'react-i18next';
import { Spin } from 'antd';

const LoadingSpinner = ({ tip }) => {
  const { t } = useTranslation();
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
      <Spin size="large" tip={tip || t('common.loading')} />
    </div>
  );
};

export default LoadingSpinner;
