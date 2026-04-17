import React from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from 'antd';

const LanguageSwitcher = ({ style }) => {
  const { i18n } = useTranslation();

  const toggle = () => {
    const newLang = i18n.language?.startsWith('zh') ? 'en' : 'zh-CN';
    i18n.changeLanguage(newLang);
    localStorage.setItem('gs_language', newLang);
    // Persist to backend (best effort)
    const token = localStorage.getItem('access_token');
    if (token) {
      const apiUrl = process.env.REACT_APP_API_URL || '';
      fetch(`${apiUrl}/user/preferences/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ language: newLang }),
      }).catch(() => {});
    }
  };

  return (
    <Button
      type="text"
      size="small"
      onClick={toggle}
      style={{
        color: '#94A3B8',
        fontSize: 13,
        fontWeight: 500,
        padding: '2px 8px',
        ...style,
      }}
    >
      {i18n.language?.startsWith('zh') ? 'EN' : '中文'}
    </Button>
  );
};

export default LanguageSwitcher;
