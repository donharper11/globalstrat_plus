import React, { useMemo } from 'react';
import { Layout, Button, Tooltip } from 'antd';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBars, faHome, faSignOutAlt } from '@fortawesome/free-solid-svg-icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import LanguageSwitcher from './LanguageSwitcher';

const { Header } = Layout;

const TopBar = ({ collapsed, onToggle, isMobile }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const displayName = user?.display_name || user?.username || '';
  const initials = useMemo(() => {
    if (!displayName) return '?';
    const parts = displayName.split(/[\s._-]+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return displayName.substring(0, 2).toUpperCase();
  }, [displayName]);

  return (
    <Header className="enterprise-topbar">
      <div className="topbar-left">
        <Button
          type="text"
          className="topbar-toggle"
          icon={<FontAwesomeIcon icon={faBars} />}
          onClick={onToggle}
        />
        {!isMobile && (
          <span style={{ fontSize: 14, fontWeight: 500, color: '#0F172A' }}>
            {t('topbar.title')}
          </span>
        )}
      </div>
      <div className="topbar-right">
        <LanguageSwitcher style={{ color: '#64748B' }} />
        <Tooltip title={t('topbar.dashboard')}>
          <Button
            type="text"
            className="topbar-action"
            icon={<FontAwesomeIcon icon={faHome} />}
            onClick={() => navigate('/')}
          />
        </Tooltip>
        <Tooltip title={t('topbar.log_out')}>
          <Button
            type="text"
            className="topbar-action"
            icon={<FontAwesomeIcon icon={faSignOutAlt} />}
            onClick={handleLogout}
          />
        </Tooltip>
        {!isMobile && (
          <div className="topbar-user">
            <div className="topbar-user-avatar">{initials}</div>
            <span className="topbar-user-name">{displayName}</span>
          </div>
        )}
      </div>
    </Header>
  );
};

export default TopBar;
