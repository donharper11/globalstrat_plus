import React, { useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import './InvestorProfilePopover.css';

const FUND_TYPE_COLORS = {
  growth: '#3B82F6',
  value: '#1E40AF',
  esg: '#0F766E',
};

const scoreColor = (score) => {
  if (score >= 0.7) return 'score-good';
  if (score >= 0.4) return 'score-fair';
  return 'score-poor';
};

const alignBarColor = (score) => {
  if (score >= 0.7) return '#16A34A';
  if (score >= 0.4) return '#D97706';
  return '#DC2626';
};

/**
 * Popover card showing an AI investor fund's strategy, preferences,
 * alignment score, biggest gap, and quick-win suggestion.
 */
const InvestorProfilePopover = ({ fund, onClose, anchorRect }) => {
  const { t } = useTranslation();
  const ref = useRef(null);
  const navigate = useNavigate();

  // Close on click outside
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  // Position relative to anchor
  useEffect(() => {
    if (!ref.current || !anchorRect) return;
    const el = ref.current;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let top = anchorRect.bottom + 6;
    let left = anchorRect.left;

    // Prevent right overflow
    if (left + 400 > vw) left = vw - 416;
    if (left < 8) left = 8;

    // If overflows bottom, show above
    if (top + el.offsetHeight > vh - 16) {
      top = anchorRect.top - el.offsetHeight - 6;
    }

    el.style.top = `${top}px`;
    el.style.left = `${left}px`;
  }, [anchorRect]);

  if (!fund) return null;

  const alignment = fund.alignment || {};
  const likes = (fund.preferences || []);
  const dislikes = fund.dislikes || [];
  const philosophy = fund.philosophy || '';
  const badgeColor = FUND_TYPE_COLORS[philosophy] || '#475569';

  return (
    <div className="investor-popover" ref={ref}>
      {/* Header */}
      <div className="popover-header">
        <div className="popover-header-left">
          <h3 className="popover-fund-name">{fund.name}</h3>
          <span className="fund-type-badge" style={{ background: badgeColor }}>
            {fund.fund_type}
          </span>
        </div>
        <button className="popover-close" onClick={onClose}>&times;</button>
      </div>

      {/* Strategy */}
      <p className="strategy-summary">{fund.strategy_summary}</p>

      {/* Two columns: Likes / Dislikes */}
      <div className="preferences-columns">
        <div className="pref-col likes-col">
          <h4 className="pref-heading">{t("investor_popover.what_they_look_for")}</h4>
          {likes.map(pref => {
            const featureScore = alignment.feature_scores?.[pref.feature_code];
            return (
              <div key={pref.feature_code} className="pref-row">
                <span className="pref-label">{pref.feature}</span>
                {featureScore != null && (
                  <span className={`pref-score ${scoreColor(featureScore)}`}>
                    {Math.round(featureScore * 100)}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
        <div className="pref-col dislikes-col">
          <h4 className="pref-heading">{t("investor_popover.what_they_avoid")}</h4>
          {dislikes.map((item, i) => (
            <div key={i} className="pref-row">
              <span className="pref-label dislike-label">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Alignment Score */}
      {alignment.score != null && (
        <div className="alignment-section">
          <div className="alignment-bar-row">
            <span className="alignment-label">{t("investor_popover.your_alignment")}:</span>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{
                  width: `${Math.round(alignment.score * 100)}%`,
                  background: alignBarColor(alignment.score),
                }}
              />
            </div>
            <span className={`alignment-pct ${scoreColor(alignment.score)}`}>
              {Math.round(alignment.score * 100)}%
            </span>
          </div>

          {alignment.biggest_gap && (
            <div className="biggest-gap">
              {t("investor_popover.biggest_gap")}: <strong>{alignment.biggest_gap.label}</strong>{' '}
              ({Math.round(alignment.biggest_gap.score * 100)}%)
            </div>
          )}

          {alignment.quick_win && (
            <div className="quick-win">
              <strong>{t("investor_popover.quick_win")}:</strong> {alignment.quick_win.action}
              <button
                className="quick-win-link"
                onClick={(e) => {
                  e.stopPropagation();
                  onClose();
                  navigate(`/${alignment.quick_win.page}`);
                }}
              >
                &rarr; {t("investor_popover.go_to_page")}
              </button>
              <span className="quick-win-impact">{alignment.quick_win.impact}</span>
            </div>
          )}
        </div>
      )}

      {/* Current Position */}
      <div className="current-position">
        <span>{(fund.shares_held || 0).toLocaleString()} shares ({fund.holding_pct || 0}%)</span>
        <span className={`sentiment-tag sentiment-${(fund.action || 'hold').toLowerCase()}`}>
          {fund.action === 'buy' ? '\u25B2 BUY' : fund.action === 'sell' ? '\u25BC SELL' : '\u2014 HOLD'}
        </span>
      </div>
    </div>
  );
};

/**
 * Clickable investor fund name that opens the popover.
 */
export const InvestorNameLink = ({ fund, activeFund, setActiveFund, children }) => {
  const handleClick = (e) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setActiveFund(activeFund?.name === fund.name ? null : { ...fund, _anchorRect: rect });
  };

  return (
    <span className="investor-name-clickable" onClick={handleClick}>
      {children || fund.name || fund.fund_name}
    </span>
  );
};

/**
 * Compact summary of all three funds for the Dashboard.
 */
export const InvestorSummaryCard = ({ fundProfiles, onFundClick, onClose }) => {
  const { t } = useTranslation();
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (!fundProfiles || fundProfiles.length === 0) return null;

  return (
    <div className="investor-summary-card" ref={ref}>
      <div className="summary-header">
        <h4 className="summary-title">{t("investor_popover.ai_investor_summary").toUpperCase()}</h4>
        <button className="popover-close" onClick={onClose}>&times;</button>
      </div>
      {fundProfiles.map(f => {
        const actionIcon = f.action === 'buy' ? '\u25B2' : f.action === 'sell' ? '\u25BC' : '\u2014';
        const actionLabel = (f.action || 'hold').toUpperCase();
        const actionColor = f.action === 'buy' ? '#16A34A' : f.action === 'sell' ? '#DC2626' : '#D97706';
        const alignScore = f.alignment?.score != null ? Math.round(f.alignment.score * 100) : '—';
        return (
          <div key={f.code} className="summary-row">
            <span className="investor-name-clickable" onClick={(e) => onFundClick(f, e)}>
              {f.name}
            </span>
            <span className="summary-action" style={{ color: actionColor }}>
              {actionIcon} {actionLabel}
            </span>
            <span className={`summary-align ${scoreColor(f.alignment?.score || 0)}`}>
              {alignScore}% align
            </span>
          </div>
        );
      })}
      <div className="summary-footer">{t("investor_popover.click_fund_profile")}</div>
    </div>
  );
};

export default InvestorProfilePopover;
