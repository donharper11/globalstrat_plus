import React from 'react';
import { useTranslation } from 'react-i18next';
import { Spin } from 'antd';

const LoadingSpinner = ({ tip, message, fullPage = false }) => {
  const { t } = useTranslation();
  const label = tip || message || t('common.loading');
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label}
      style={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 16,
        minHeight: fullPage ? '100vh' : 300,
        padding: 24,
        color: '#475569',
        textAlign: 'center',
      }}
    >
      <Spin size="large" />
      <span>{label}</span>
    </div>
  );
};

export default LoadingSpinner;
