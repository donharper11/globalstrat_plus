import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, Button, Typography, Space } from 'antd';
import { getTeamChanges } from '../api/decisions';

const { Text } = Typography;

const POLL_INTERVAL = 30000;

const TeamActivityBanner = ({ gameId, teamId, currentRound, currentUserId }) => {
  const { t } = useTranslation();
  const [changes, setChanges] = useState([]);
  const [dismissed, setDismissed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const lastChangeIds = useRef(new Set());
  const timerRef = useRef(null);

  const relativeTime = useCallback((timestamp) => {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now - then;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t('common.just_now');
    if (diffMin < 60) return `${diffMin} ${t('common.min_ago')}`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}${t('common.hours_ago')}`;
    return `${Math.floor(diffHr / 24)}${t('common.days_ago')}`;
  }, [t]);

  const fetchChanges = useCallback(async () => {
    if (!gameId || !teamId || !currentRound || !currentUserId) return;
    try {
      const res = await getTeamChanges(gameId, teamId, {
        exclude_user: currentUserId,
        round_number: currentRound,
      });
      const data = res.data?.changes || res.data?.results || [];
      setChanges(data);

      // Check if there are new changes since last dismiss
      const newIds = new Set(data.map(c => c.id));
      const hasNew = data.some(c => !lastChangeIds.current.has(c.id));
      if (hasNew && dismissed) {
        setDismissed(false);
      }
      lastChangeIds.current = newIds;
    } catch {
      // ignore fetch errors silently
    }
  }, [gameId, teamId, currentRound, currentUserId, dismissed]);

  useEffect(() => {
    fetchChanges();
    timerRef.current = setInterval(fetchChanges, POLL_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, [fetchChanges]);

  const handleDismiss = () => {
    setDismissed(true);
    lastChangeIds.current = new Set(changes.map(c => c.id));
  };

  if (dismissed || changes.length === 0) return null;

  const visible = expanded ? changes : changes.slice(0, 3);

  const description = (
    <div>
      <Space direction="vertical" size={2} style={{ width: '100%' }}>
        {visible.map((change, idx) => (
          <div key={change.id || idx}>
            <Text strong style={{ fontSize: 12 }}>
              {change.user_name || change.username || t('common.teammate')}
            </Text>
            <Text style={{ fontSize: 12 }}> {t('common.updated')} {change.decision_type || change.field_name || 'a decision'}</Text>
            <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
              {relativeTime(change.created_at || change.timestamp)}
            </Text>
          </div>
        ))}
      </Space>
      <div style={{ marginTop: 8 }}>
        <Space>
          {changes.length > 3 && (
            <Button type="link" size="small" onClick={() => setExpanded(!expanded)} style={{ padding: 0 }}>
              {expanded ? t('common.show_less') : `${t('common.view_all')} (${changes.length})`}
            </Button>
          )}
          <Button type="link" size="small" onClick={handleDismiss} style={{ padding: 0 }}>
            {t('common.dismiss')}
          </Button>
        </Space>
      </div>
    </div>
  );

  return (
    <Alert
      message={`${changes.length} ${changes.length !== 1 ? t('common.changes_by_teammates') : t('common.change_by_teammates')}`}
      description={description}
      type="info"
      showIcon
      style={{ marginBottom: 16 }}
      closable
      onClose={handleDismiss}
    />
  );
};

export default TeamActivityBanner;
