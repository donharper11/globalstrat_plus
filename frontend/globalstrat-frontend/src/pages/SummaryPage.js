import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Typography, Button, Tag, Space, Modal, Input, Alert, List } from 'antd';
import { CheckCircleOutlined, WarningOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
import { getDecisionSummary, lockDecisions, patchDecision } from '../api/decisions';
import BudgetBar from '../components/BudgetBar';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Title, Text } = Typography;
const { TextArea } = Input;

const statusIcon = (status) => {
  if (status === 'configured') return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />;
  if (status === 'partial') return <WarningOutlined style={{ color: '#faad14', fontSize: 18 }} />;
  if (status === 'error') return <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />;
  return <WarningOutlined style={{ color: '#d9d9d9', fontSize: 18 }} />;
};

const SummaryPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { gameId, teamId, currentRound } = useGame();
  const { locked, setLocked } = useDecisions();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showConfirm, setShowConfirm] = useState(false);
  const [lockError, setLockError] = useState(null);
  const [teamNotes, setTeamNotes] = useState('');
  const [lockLoading, setLockLoading] = useState(false);

  const base = gameId && teamId ? `/games/${gameId}/teams/${teamId}` : '';

  const loadSummary = useCallback(async () => {
    if (!gameId || !teamId || !currentRound) { setLoading(false); return; }
    try {
      const res = await getDecisionSummary(gameId, teamId, currentRound);
      setSummary(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId, currentRound]);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  const categories = summary?.categories || {};
  const canLock = summary?.can_lock && !locked;
  const blockers = summary?.lock_blockers || [];
  const budgetSummary = summary?.budget_summary || {};

  const categoryList = [
    { key: 'budget', label: t('summary_page.budget_allocation'), path: `${base}/decisions/finance` },
    { key: 'rd', label: t('summary_page.rd_investment'), path: `${base}/decisions/rd` },
    { key: 'products', label: t('summary_page.product_portfolio'), path: `${base}/decisions/products` },
    { key: 'marketing', label: t('summary_page.marketing_mix'), path: `${base}/decisions/marketing` },
    { key: 'strategy', label: t('summary_page.strategy_mix'), path: `${base}/decisions/strategy` },
    { key: 'financing', label: t('summary_page.financing'), path: `${base}/decisions/finance` },
  ];

  const handleLock = async () => {
    setLockLoading(true);
    setLockError(null);
    try {
      // Save team notes first
      if (teamNotes) {
        await patchDecision(gameId, teamId, currentRound, 'budget', { team_notes: teamNotes });
      }
      await lockDecisions(gameId, teamId, currentRound);
      setLocked(true);
      setShowConfirm(false);
      loadSummary();
    } catch (err) {
      const data = err.response?.data;
      setLockError(data?.errors || data?.detail || t("summary_page.lock_failed_detail"));
    } finally {
      setLockLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <PageHeader
        title={t("summary_page.title")}
        subtitle={`${t("common.round")} ${currentRound} · ${t("summary_page.subtitle")}`}
        status={locked ? 'locked' : 'draft'}
      />

      {locked && (
        <Alert
          message={t("summary_page.decisions_locked")}
          description={t("summary_page.decisions_locked_desc", { round: currentRound })}
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Checklist */}
      <PanelCard headerColor="decision" title={t("summary_page.decision_checklist").toUpperCase()} style={{ marginBottom: 16 }}>
        <List
          dataSource={categoryList}
          renderItem={item => {
            const cat = categories[item.key] || {};
            return (
              <List.Item
                actions={[
                  <Tag color={
                    cat.status === 'configured' ? 'green' :
                    cat.status === 'partial' ? 'orange' :
                    cat.status === 'error' ? 'red' : 'default'
                  }>
                    {cat.status || 'empty'}
                  </Tag>
                ]}
              >
                <List.Item.Meta
                  avatar={statusIcon(cat.status)}
                  title={
                    <Button type="link" onClick={() => navigate(item.path)} style={{ padding: 0 }}>
                      {item.label}
                    </Button>
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      {(cat.warnings || []).map((w, i) => (
                        <Text key={i} type="warning" style={{ fontSize: 12 }}>{w}</Text>
                      ))}
                      {(cat.errors || []).map((e, i) => (
                        <Text key={i} type="danger" style={{ fontSize: 12 }}>{e}</Text>
                      ))}
                      {cat.configured_count != null && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {cat.configured_count} / {cat.total_required} {t("summary_page.configured")}
                        </Text>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            );
          }}
        />
      </PanelCard>

      {/* Budget Summary */}
      <PanelCard headerColor="financial" title={t("summary_page.budget_summary").toUpperCase()} style={{ marginBottom: 16 }}>
        <BudgetBar budgets={budgetSummary} />
      </PanelCard>

      {/* Team Notes */}
      <PanelCard headerColor="neutral" title={t("summary_page.team_notes").toUpperCase()} style={{ marginBottom: 16 }}>
        <TextArea
          rows={4}
          value={teamNotes}
          onChange={e => setTeamNotes(e.target.value)}
          disabled={locked}
          placeholder={t("summary_page.team_notes_placeholder")}
          maxLength={2000}
          showCount
        />
      </PanelCard>

      {/* Lock blockers */}
      {blockers.length > 0 && (
        <Alert
          message={t("summary_page.cannot_submit")}
          description={
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {blockers.map((b, i) => <li key={i}>{b}</li>)}
            </ul>
          }
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Lock button */}
      {!locked && (
        <Button
          type="primary"
          size="large"
          disabled={!canLock}
          onClick={() => setShowConfirm(true)}
          block
        >
          {t("summary_page.lock_submit_round", { round: currentRound })}
        </Button>
      )}

      {/* Confirm modal */}
      <Modal
        title={t("summary_page.confirm_submission")}
        open={showConfirm}
        onCancel={() => { setShowConfirm(false); setLockError(null); }}
        onOk={handleLock}
        okText={t("summary_page.lock_decisions")}
        okButtonProps={{ danger: true, loading: lockLoading }}
      >
        <Text>
          {t("summary_page.lock_confirm_text", { round: currentRound })}
        </Text>
        {lockError && (
          <Alert
            message={t("summary_page.lock_failed")}
            description={Array.isArray(lockError) ? lockError.join('; ') : lockError}
            type="error"
            showIcon
            style={{ marginTop: 12 }}
          />
        )}
      </Modal>
    </div>
  );
};

export default SummaryPage;
