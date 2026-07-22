import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBars, faSignOutAlt, faBell } from '@fortawesome/free-solid-svg-icons';
import { useAuth } from '../../AuthContext';
import { useGame } from '../../contexts/GameContext';
import { useDecisions } from '../../contexts/DecisionContext';

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const roundStatusText = (roundStatus, locked) => {
  if (locked) return 'LOCKED';
  if (roundStatus === 'closed') return 'ROUND CLOSED';
  if (roundStatus === 'processed') return 'RESULTS AVAILABLE';
  if (roundStatus === 'pending') return 'NOT OPEN YET';
  return 'DRAFT OPEN';
};

const GlobeLogo = () => (
  <svg className="ds-topbar-logo-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="globe-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#60A5FA" />
        <stop offset="100%" stopColor="#3B82F6" />
      </linearGradient>
    </defs>
    <circle cx="20" cy="20" r="18" fill="url(#globe-grad)" opacity="0.15" />
    <circle cx="20" cy="20" r="18" stroke="url(#globe-grad)" strokeWidth="2" fill="none" />
    <ellipse cx="20" cy="20" rx="9" ry="18" stroke="#60A5FA" strokeWidth="1.3" fill="none" />
    <path d="M2 14 Q20 17 38 14" stroke="#60A5FA" strokeWidth="1" fill="none" />
    <path d="M2 26 Q20 23 38 26" stroke="#60A5FA" strokeWidth="1" fill="none" />
    <text x="20" y="23" textAnchor="middle" fill="#93C5FD" fontFamily="Rajdhani, sans-serif" fontWeight="700" fontSize="12">GS</text>
  </svg>
);

function DSTopBar({ onToggle, isMobile }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { currentRound, totalRounds, roundStatus, budgets, team } = useGame();
  const { locked } = useDecisions();

  const rawName = user?.display_name || user?.username || '';
  // Strip any "(Team X)" suffix from display_name to avoid duplication
  const displayName = rawName.replace(/\s*\(.*?\)\s*$/, '').trim();
  const teamName = team?.name || '';
  const initials = useMemo(() => {
    if (!displayName) return '?';
    const parts = displayName.split(/[\s._-]+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return displayName.substring(0, 2).toUpperCase();
  }, [displayName]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="ds-topbar">
      {/* Toggle */}
      <button className="ds-topbar-action" onClick={onToggle} style={{ marginRight: 8 }}>
        <FontAwesomeIcon icon={faBars} />
      </button>

      {/* Logo — left-justified */}
      <div className="ds-topbar-logo" onClick={() => navigate('/')}>
        <GlobeLogo />
        {!isMobile && <span className="ds-topbar-logo-text">GlobalStrat</span>}
      </div>

      {!isMobile && (
        <>
          <div className="ds-topbar-divider" />
          <span className="ds-topbar-scenario">Consumer Electronics Sim</span>

          <div className="ds-topbar-divider" />
          <span className="ds-topbar-round">
            R{currentRound || '—'} of {totalRounds || '—'}
            <span className={`ds-topbar-status ${locked ? 'locked' : 'draft'}`}>
              {roundStatusText(roundStatus, locked)}
            </span>
          </span>

          {budgets && (
            <>
              <div className="ds-topbar-divider" />
              <div className="ds-topbar-section">
                {budgets.total_budget_available && (
                  <span className="ds-topbar-budget-chip" style={{
                    color: budgets.over_budget ? '#ef4444' : undefined,
                    fontWeight: budgets.over_budget ? 700 : undefined,
                  }}>
                    <strong>{t('topbar.budget_label')}</strong> {fmt(budgets.total_spent || 0)}/{fmt(budgets.total_budget_available)}
                    {budgets.over_budget && ` ${t('topbar.over')}`}
                  </span>
                )}
                <span className="ds-topbar-budget-chip">
                  <strong>{t('topbar.rd_label')}</strong> {fmt(budgets.rd_spent)}/{fmt(budgets.rd_allocated)}
                </span>
                <span className="ds-topbar-budget-chip">
                  <strong>{t('topbar.mktg_label')}</strong> {fmt(budgets.marketing_spent)}/{fmt(budgets.marketing_allocated)}
                </span>
                <span className="ds-topbar-budget-chip">
                  <strong>{t('topbar.strat_label')}</strong> {fmt(budgets.strategy_spent)}/{fmt(budgets.strategy_allocated)}
                </span>
              </div>
            </>
          )}
        </>
      )}

      {/* Right section */}
      <div className="ds-topbar-right">
        <button className="ds-topbar-action">
          <FontAwesomeIcon icon={faBell} />
        </button>
        <button className="ds-topbar-action" onClick={handleLogout} title={t('topbar.log_out')}>
          <FontAwesomeIcon icon={faSignOutAlt} />
        </button>
        {!isMobile && (
          <div className="ds-topbar-user">
            <div className="ds-topbar-avatar">{initials}</div>
            <span>{displayName}{teamName ? ` · ${teamName}` : ''}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export default DSTopBar;
