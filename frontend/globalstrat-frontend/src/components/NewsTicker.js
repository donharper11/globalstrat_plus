import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { getTickerItems } from '../api/cc15';
import './NewsTicker.css';

/**
 * Route map: ticker item type → page path suffix.
 */
const ROUTE_MAP = {
  currency: 'financial-reports',
  event: 'news',
  market: 'research',
  alert: 'decisions/summary',
  competitive: 'competitors',
  investor: 'financial-reports',
};

const NewsTicker = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound } = useGame();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [isPaused, setIsPaused] = useState(false);
  const contentRef = useRef(null);

  useEffect(() => {
    if (!gameId || !teamId || !currentRound || currentRound < 1) return;
    let cancelled = false;
    getTickerItems(gameId, teamId)
      .then((res) => {
        if (!cancelled) setItems(res.data.items || []);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      });
    return () => { cancelled = true; };
  }, [gameId, teamId, currentRound]);

  const handleClick = useCallback((item) => {
    const suffix = ROUTE_MAP[item.type] || 'news';
    navigate(`/games/${gameId}/teams/${teamId}/${suffix}`);
  }, [gameId, teamId, navigate]);

  // Adjust scroll duration based on item count
  const scrollDuration = Math.max(30, items.length * 8);

  if (items.length === 0) return null;

  return (
    <div
      className="news-ticker"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onTouchStart={() => setIsPaused((p) => !p)}
    >
      <div className="ticker-label">{t('topbar.live')}</div>
      <div className="ticker-track">
        <div
          ref={contentRef}
          className={`ticker-content ${isPaused ? 'paused' : ''}`}
          style={{ animationDuration: `${scrollDuration}s` }}
        >
          {[...items, ...items].map((item, i) => (
            <span
              key={i}
              className={`ticker-item priority-${item.priority}`}
              onClick={() => handleClick(item)}
            >
              <span className="ticker-icon">{item.icon}</span>
              <span className="ticker-text">{item.text}</span>
              <span className="ticker-separator">{'\u2502'}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default NewsTicker;
