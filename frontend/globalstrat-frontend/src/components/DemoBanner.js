import React from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';

const DemoBanner = () => {
  const { t } = useTranslation();
  const { user } = useAuth();

  if (!user?.is_demo) return null;

  return (
    <div style={{
      background: 'linear-gradient(90deg, #1E40AF, #3B82F6)',
      color: '#fff',
      textAlign: 'center',
      padding: '6px 16px',
      fontSize: 13,
      fontWeight: 600,
      letterSpacing: '0.5px',
      zIndex: 100,
    }}>
      {t('common.demo_mode')}
    </div>
  );
};

export default DemoBanner;
