import React, { useState, useEffect, useCallback } from 'react';
import { Typography, Timeline, Card, Tag, Alert } from 'antd';
import { useTranslation } from 'react-i18next';
import { useGame } from '../contexts/GameContext';
import { useAuth } from '../AuthContext';
import { getTeamChanges } from '../api/decisions';
import LoadingSpinner from '../components/LoadingSpinner';
import { PageHeader } from '../components/design-system';

const { Text } = Typography;

const formatTimestamp = (timestamp) => {
  if (!timestamp) return '';
  const d = new Date(timestamp);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const TeamActivityPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound } = useGame();
  const { user } = useAuth();
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const currentUserId = user?.user_id;

  const fetchChanges = useCallback(async () => {
    if (!gameId || !teamId || !currentRound) { setLoading(false); return; }
    try {
      const res = await getTeamChanges(gameId, teamId, {
        round_number: currentRound,
      });
      setChanges(res.data?.changes || res.data?.results || []);
      setError(null);
    } catch {
      setError(t('common.unable_load_activity'));
    }
    setLoading(false);
  }, [gameId, teamId, currentRound]);

  useEffect(() => {
    fetchChanges();
  }, [fetchChanges]);

  if (loading) return <LoadingSpinner />;
  if (error) return <Alert message={error} type="error" />;

  // Group changes by user
  const grouped = {};
  changes.forEach((change) => {
    const userName = change.user_name || change.username || t('common.unknown');
    const userId = change.user_id || change.user;
    const key = userId || userName;
    if (!grouped[key]) {
      grouped[key] = { userName, userId, changes: [] };
    }
    grouped[key].changes.push(change);
  });

  const userGroups = Object.values(grouped);

  return (
    <div>
      <PageHeader
        title={t('common.team_activity')}
        subtitle={t('common.round_change_log', { round: currentRound })}
      />

      {changes.length === 0 && (
        <Card>
          <Text type="secondary">{t('common.no_changes_yet')}</Text>
        </Card>
      )}

      {userGroups.map((group) => {
        const isCurrentUser = String(group.userId) === String(currentUserId);
        return (
          <Card
            key={group.userId || group.userName}
            title={
              <span>
                {group.userName}
                {isCurrentUser && (
                  <Tag color="blue" style={{ marginLeft: 8 }}>{t('common.you')}</Tag>
                )}
              </span>
            }
            size="small"
            style={{
              marginBottom: 16,
              borderLeft: isCurrentUser ? '3px solid #1677ff' : '3px solid #d9d9d9',
            }}
          >
            <Timeline
              items={group.changes.map((change, idx) => ({
                key: change.id || idx,
                color: isCurrentUser ? 'blue' : 'gray',
                children: (
                  <div>
                    <Text style={{ fontSize: 13 }}>
                      {change.decision_type || change.field_name || t('common.decision_update')}
                    </Text>
                    {change.description && (
                      <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
                        {change.description}
                      </Text>
                    )}
                    <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                      {formatTimestamp(change.created_at || change.timestamp)}
                    </Text>
                  </div>
                ),
              }))}
            />
          </Card>
        );
      })}
    </div>
  );
};

export default TeamActivityPage;
