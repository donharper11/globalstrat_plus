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
      // Same default as api/client.js. This read `|| ''`, so a build without
      // REACT_APP_API_URL set -- which is the default build -- sent the PUT to
      // /user/preferences/ instead of /api/user/preferences/ and got a 404
      // into a silent catch. The language changed on screen and was never
      // stored, so it reverted on the next sign-in or a second device.
      const apiUrl = process.env.REACT_APP_API_URL || '/api';
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
