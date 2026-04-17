import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Typography, Input, Button, Tag, Alert, Row, Col, Progress, Space, Collapse, Badge } from 'antd';
import { useGame } from '../contexts/GameContext';
import { getCommunicationAssignments, saveCommunicationDraft, submitCommunication, getCommunicationHistory } from '../api/decisions';
import { PageHeader, PanelCard } from '../components/design-system';
import LoadingSpinner from '../components/LoadingSpinner';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const AUDIENCE_ICONS = {
  BOARD: '\uD83D\uDCCB',
  EMPLOYEES: '\uD83D\uDC65',
  INVESTORS: '\uD83D\uDCCA',
  REGULATORS: '\u2696\uFE0F',
  PUBLIC: '\uD83D\uDCF0',
  PARTNER: '\uD83E\uDD1D',
};

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const ScoreBar = ({ label, score, feedback }) => {
  const pct = Math.round((score || 0) * 100);
  const color = pct >= 70 ? '#52c41a' : pct >= 50 ? '#faad14' : '#ff4d4f';
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
        <Text strong style={{ fontSize: 12 }}>{label}</Text>
        <Text style={{ fontSize: 12, color }}>{pct}%</Text>
      </div>
      <Progress percent={pct} showInfo={false} strokeColor={color} size="small" />
      {feedback && <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{feedback}</Text>}
    </div>
  );
};

const CommunicationEditor = ({ assignment, gameId, teamId, onSubmitted }) => {
  const { t } = useTranslation();
  const [content, setContent] = useState(assignment.draft_content || '');
  const [wordCount, setWordCount] = useState(assignment.draft_word_count || 0);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [evaluation, setEvaluation] = useState(assignment.evaluation || null);
  const [submitted, setSubmitted] = useState(assignment.status === 'submitted');
  const saveTimer = useRef(null);

  const updateContent = useCallback((text) => {
    setContent(text);
    const wc = text.trim() ? text.trim().split(/\s+/).length : 0;
    setWordCount(wc);

    // Auto-save draft after 1.5s of inactivity
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaving(true);
      try {
        await saveCommunicationDraft(gameId, teamId, assignment.id, text);
      } catch { /* ignore */ }
      setSaving(false);
    }, 1500);
  }, [gameId, teamId, assignment.id]);

  const handleSubmit = useCallback(async () => {
    if (wordCount === 0) return;
    setSubmitting(true);
    try {
      const res = await submitCommunication(gameId, teamId, assignment.id, content);
      setEvaluation(res.data.evaluation);
      setSubmitted(true);
      if (onSubmitted) onSubmitted();
    } catch (err) {
      const detail = err.response?.data?.detail || t("communications_page.submission_failed");
      alert(detail);
    }
    setSubmitting(false);
  }, [gameId, teamId, assignment.id, content, wordCount, onSubmitted]);

  const overLimit = wordCount > assignment.word_limit;

  if (submitted && evaluation) {
    return <EvaluationDisplay assignment={assignment} evaluation={evaluation} content={content} />;
  }

  return (
    <div>
      {/* Context/Prompt */}
      <Card size="small" style={{ marginBottom: 12, background: '#f8fafc' }}>
        <Text strong style={{ fontSize: 12 }}>{t("communications_page.assignment_brief")}</Text>
        <Paragraph style={{ marginTop: 8, fontSize: 13, whiteSpace: 'pre-line' }}>
          {assignment.prompt_text}
        </Paragraph>
      </Card>

      {/* Editor */}
      <Card size="small" style={{ marginBottom: 12 }} title={
        <Space>
          <Text strong style={{ fontSize: 12 }}>{t("communications_page.your_communication")}</Text>
          {saving && <Tag color="blue">{t("communications_page.saving")}</Tag>}
        </Space>
      }>
        <TextArea
          value={content}
          onChange={e => updateContent(e.target.value)}
          placeholder={t("communications_page.draft_placeholder")}
          autoSize={{ minRows: 8, maxRows: 20 }}
          disabled={submitted}
          style={{ fontSize: 13 }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <Text style={{ fontSize: 12, color: overLimit ? '#ff4d4f' : '#8c8c8c' }}>
            {t("communications_page.word_count")}: {wordCount} / {assignment.word_limit}
            {overLimit && ` (${t("communications_page.over_limit")})`}
          </Text>
          <Button
            type="primary"
            onClick={handleSubmit}
            loading={submitting}
            disabled={submitted || wordCount === 0 || overLimit}
          >
            {submitting ? t("communications_page.evaluating") : t("communications_page.submit_for_evaluation")}
          </Button>
        </div>
      </Card>

      {/* Evaluation criteria preview */}
      <Collapse ghost size="small" items={[{
        key: '1',
        label: <Text type="secondary" style={{ fontSize: 11 }}>{t("communications_page.evaluation_criteria")}</Text>,
        children: (
          <div style={{ fontSize: 11 }}>
            {(assignment.evaluation_criteria || []).map((c, i) => (
              <div key={i} style={{ marginBottom: 4 }}>
                <Text strong>{c.criterion.replace(/_/g, ' ')}</Text> (weight: {(c.weight * 100).toFixed(0)}%)
                <br />
                <Text type="secondary">{c.description}</Text>
              </div>
            ))}
          </div>
        ),
      }]} />
    </div>
  );
};

const EvaluationDisplay = ({ assignment, evaluation, content }) => {
  const { t } = useTranslation();
  const overallPct = Math.round((evaluation.overall_score || 0) * 100);

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12, borderLeft: '3px solid #1677ff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Text strong style={{ fontSize: 14 }}>{t("communications_page.evaluation")}: {assignment.name}</Text>
          <Tag color={overallPct >= 70 ? 'green' : overallPct >= 50 ? 'orange' : 'red'} style={{ fontSize: 14 }}>
            {t("communications_page.score")}: {overallPct}%
          </Tag>
        </div>

        {/* Per-criterion scores */}
        {Object.entries(evaluation.criteria_scores || {}).map(([key, val]) => (
          <ScoreBar
            key={key}
            label={key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            score={val.score}
            feedback={val.feedback}
          />
        ))}
      </Card>

      {/* Consistency flags */}
      {(evaluation.consistency_flags || []).length > 0 && (
        <Alert
          type="warning" showIcon
          style={{ marginBottom: 12 }}
          message={t("communications_page.consistency_flags")}
          description={
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {evaluation.consistency_flags.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          }
        />
      )}

      <Row gutter={[16, 12]}>
        <Col xs={24} md={12}>
          {(evaluation.strengths || []).length > 0 && (
            <Card size="small" style={{ background: '#f6ffed' }}>
              <Text strong style={{ fontSize: 11, color: '#52c41a' }}>{t("communications_page.strengths")}</Text>
              <ul style={{ margin: '4px 0 0', paddingLeft: 16, fontSize: 12 }}>
                {evaluation.strengths.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </Card>
          )}
        </Col>
        <Col xs={24} md={12}>
          {(evaluation.gaps || []).length > 0 && (
            <Card size="small" style={{ background: '#fff7e6' }}>
              <Text strong style={{ fontSize: 11, color: '#fa8c16' }}>{t("communications_page.gaps")}</Text>
              <ul style={{ margin: '4px 0 0', paddingLeft: 16, fontSize: 12 }}>
                {evaluation.gaps.map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </Card>
          )}
        </Col>
      </Row>

      {evaluation.overall_feedback && (
        <Card size="small" style={{ marginTop: 12, background: '#f8fafc' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>{evaluation.overall_feedback}</Text>
        </Card>
      )}

      {/* Original submission */}
      <Collapse ghost size="small" style={{ marginTop: 8 }} items={[{
        key: '1',
        label: <Text type="secondary" style={{ fontSize: 11 }}>{t("communications_page.view_submission")}</Text>,
        children: <Paragraph style={{ fontSize: 12, whiteSpace: 'pre-line' }}>{content}</Paragraph>,
      }]} />
    </div>
  );
};

const CommunicationsPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound } = useGame();
  const [loading, setLoading] = useState(true);
  const [assignments, setAssignments] = useState([]);
  const [history, setHistory] = useState([]);
  const [activeKey, setActiveKey] = useState(null);

  const loadData = useCallback(async () => {
    if (!gameId || !teamId) return;
    setLoading(true);
    try {
      const [assignRes, histRes] = await Promise.all([
        getCommunicationAssignments(gameId, teamId).catch(() => ({ data: { assignments: [] } })),
        getCommunicationHistory(gameId, teamId).catch(() => ({ data: { history: [] } })),
      ]);
      setAssignments(assignRes.data.assignments || []);
      setHistory(histRes.data.history || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId]);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return <LoadingSpinner message={t("communications_page.loading")} />;

  const activeAssignments = assignments.filter(a => a.status !== 'submitted');
  const submittedAssignments = assignments.filter(a => a.status === 'submitted');
  const pastHistory = history.filter(h => !assignments.find(a => a.code === h.assignment_code));

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', width: '100%' }}>
      <PageHeader
        title={t("communications_page.title")}
        subtitle={`${t("common.round")} ${currentRound} \u2014 ${t("communications_page.subtitle_desc")}`}
      />

      {assignments.length === 0 && history.length === 0 && (
        <Alert
          type="info"
          message={t("communications_page.no_assignments")}
          description={t("communications_page.no_assignments_desc")}
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Active assignments */}
      {activeAssignments.length > 0 && (
        <PanelCard headerColor="strategic" title={t("communications_page.active_assignments").toUpperCase()}>
          {activeAssignments.map(a => (
            <Card
              key={a.code}
              size="small"
              style={{ marginBottom: 12, borderLeft: a.is_mandatory ? '3px solid #ff4d4f' : '3px solid #1677ff' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Space>
                  <span style={{ fontSize: 16 }}>{AUDIENCE_ICONS[a.audience] || '\uD83D\uDCDD'}</span>
                  <Text strong>{a.name}</Text>
                  {a.is_mandatory && <Tag color="red">{t("communications_page.mandatory")}</Tag>}
                </Space>
                <Space>
                  <Tag>{a.audience_display}</Tag>
                  <Tag color="blue">{t("communications_page.max_words", { count: a.word_limit })}</Tag>
                </Space>
              </div>

              {activeKey === a.code ? (
                <CommunicationEditor
                  assignment={a}
                  gameId={gameId}
                  teamId={teamId}
                  onSubmitted={loadData}
                />
              ) : (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {a.status === 'draft' ? t('communications_page.draft_saved', { count: a.draft_word_count }) : t('communications_page.not_started')}
                  </Text>
                  <br />
                  <Button
                    type="link" size="small" style={{ paddingLeft: 0 }}
                    onClick={() => setActiveKey(a.code)}
                  >
                    {a.status === 'draft' ? t('communications_page.continue_editing') : t('communications_page.start_writing')}
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </PanelCard>
      )}

      {/* This round's submitted */}
      {submittedAssignments.length > 0 && (
        <PanelCard headerColor="financial" title={t("communications_page.submitted_this_round").toUpperCase()}>
          {submittedAssignments.map(a => (
            <Card key={a.code} size="small" style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Space>
                  <span style={{ fontSize: 16 }}>{AUDIENCE_ICONS[a.audience] || '\u2705'}</span>
                  <Text strong>{a.name}</Text>
                  <Tag color="green">{t("common.submitted")}</Tag>
                </Space>
                <Tag color={
                  (a.evaluation?.overall_score || 0) >= 0.7 ? 'green' :
                  (a.evaluation?.overall_score || 0) >= 0.5 ? 'orange' : 'red'
                }>
                  {t("communications_page.score")}: {Math.round((a.evaluation?.overall_score || 0) * 100)}%
                </Tag>
              </div>
              <EvaluationDisplay assignment={a} evaluation={a.evaluation} content={a.draft_content || ''} />
            </Card>
          ))}
        </PanelCard>
      )}

      {/* Past history */}
      {pastHistory.length > 0 && (
        <PanelCard headerColor="market" title={t("communications_page.communication_history").toUpperCase()}>
          {pastHistory.map((h, i) => (
            <Card key={i} size="small" style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Space>
                  <Text strong style={{ fontSize: 12 }}>{h.assignment_name}</Text>
                  <Tag>{t("common.round")} {h.round_number}</Tag>
                  <Tag>{h.audience}</Tag>
                </Space>
                <Space>
                  <Tag color={
                    (h.overall_score || 0) >= 0.7 ? 'green' :
                    (h.overall_score || 0) >= 0.5 ? 'orange' : 'red'
                  }>
                    {Math.round((h.overall_score || 0) * 100)}%
                  </Tag>
                  <Text type="secondary" style={{ fontSize: 10 }}>
                    +{h.coherence_contribution}% {t("communications_page.coherence")}
                  </Text>
                </Space>
              </div>
              <Collapse ghost size="small" items={[{
                key: '1',
                label: <Text type="secondary" style={{ fontSize: 11 }}>{t("communications_page.view_details")}</Text>,
                children: h.evaluation
                  ? <EvaluationDisplay assignment={{ name: h.assignment_name }} evaluation={h.evaluation} content={h.content} />
                  : <Text type="secondary">{t("communications_page.no_evaluation")}</Text>,
              }]} />
            </Card>
          ))}
        </PanelCard>
      )}
    </div>
  );
};

export default CommunicationsPage;
