import React from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from 'antd';
import { setLanguagePreference } from '../api/auth';

/**
 * EN / 中文. Changes the interface language for this session and, when the
 * person is signed in, records it as their preference through the existing
 * `PUT /api/user/preferences/` route, which writes the enrolment's language
 * -- the language the team is spoken to in (R43) and the one Phase 2 writes
 * narratives in. Before sign-in there is no one to record it for, so the
 * sign-in itself sends the choice (AuthContext.login).
 *
 * Rendered on the login pages and, since W-CE-11, in the student top bar and
 * the instructor console header: a student could only change language by
 * signing out.
 */
const LanguageSwitcher = ({ style }) => {
  const { i18n } = useTranslation();

  const toggle = () => {
    const newLang = i18n.language?.startsWith('zh') ? 'en' : 'zh-CN';
    i18n.changeLanguage(newLang);
    localStorage.setItem('gs_language', newLang);
    if (localStorage.getItem('access_token')) {
      setLanguagePreference(newLang).catch(() => {});
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
