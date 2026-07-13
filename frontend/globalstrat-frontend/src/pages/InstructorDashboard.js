import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Typography, Row, Col, Table, Tag, Button, Statistic,
  Modal, InputNumber, Empty, Alert, Tabs, Space, Select, Badge,
  Input, Descriptions, Collapse, message, Popconfirm, Radio, Tooltip,
} from 'antd';
import { LockOutlined, HomeOutlined, ReloadOutlined, RocketOutlined, CheckCircleOutlined, LogoutOutlined, EditOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import {
  getInstructorDashboard, advanceRound, injectEvent,
  extendDeadline, getResearchQueries,
  getInstructorAlerts, acknowledgeAlert,
  getEventTemplates, getTeamBriefings, getTeamDecisions,
  getCourses, createCourse, deleteCourse,
  getSections, createSection, deleteSection,
  getRoster, uploadRoster, addStudent, removeEnrollment,
  getTeamManagement, generateTeams, assignStudents,
  seedRubric, calculateGrades, getGradingRubrics, getGradingCategories,
  updateGradingCategory, createGradingCategory, deleteGradingCategory,
  getComponentLabels,
  exportTeamGradesCsv, exportStudentGradesCsv,
  getTeamConfig, updateTeamConfig, randomizeHomeMarkets,
  getScenarios, getScenarioDetail, createGame,
  getGames, getGameTeams,
  getRoundSchedule, updateRoundSchedule,
  activateGame, pauseGame, resumeGame, resetGame, archiveGame, deleteGame,
  updateEnrollment,
} from '../api/instructor';
import LoadingSpinner from '../components/LoadingSpinner';
import { PageHeader, PanelCard } from '../components/design-system';
import InstructorSCPanel from '../components/instructor/InstructorSCPanel';

const { Text } = Typography;
const { TextArea } = Input;

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const InstructorDashboard = () => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [gameId, setGameId] = useState(user?.game_id || null);

  const handleLogout = () => {
    logout();
    navigate('/instructor/login');
  };
  const [dashboard, setDashboard] = useState(null);
  const [queries, setQueries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [advanceModalOpen, setAdvanceModalOpen] = useState(false);
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [extendModalOpen, setExtendModalOpen] = useState(false);
  const [extendHours, setExtendHours] = useState(24);
  const [selectedEventTemplate, setSelectedEventTemplate] = useState(null);
  const [selectedMarket, setSelectedMarket] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertSevFilter, setAlertSevFilter] = useState('all');
  const [alertTeamFilter, setAlertTeamFilter] = useState('all');
  const [alertRoundFilter, setAlertRoundFilter] = useState('all');
  // Event templates & markets for dropdown
  const [eventTemplates, setEventTemplates] = useState([]);
  const [marketOptions, setMarketOptions] = useState([]);
  // Briefings
  const [briefings, setBriefings] = useState([]);
  const [briefingRound, setBriefingRound] = useState('all');
  const [briefingTeam, setBriefingTeam] = useState('all');
  // Team drill-down
  const [drillTeam, setDrillTeam] = useState(null);
  const [drillRound, setDrillRound] = useState(null);
  const [drillData, setDrillData] = useState(null);
  const [drillLoading, setDrillLoading] = useState(false);
  // Course/Roster management
  const [courses, setCourses] = useState([]);
  const [sections, setSections] = useState([]);
  const [selectedCourse, setSelectedCourse] = useState(null);
  const [selectedSection, setSelectedSection] = useState(null);
  const [roster, setRoster] = useState([]);
  const [teamMgmt, setTeamMgmt] = useState(null);
  const [newCourseName, setNewCourseName] = useState('');
  const [newCourseCode, setNewCourseCode] = useState('');
  const [newSectionName, setNewSectionName] = useState('');
  const [newSectionCode, setNewSectionCode] = useState('');
  const [csvText, setCsvText] = useState('');
  // Grading
  const [rubrics, setRubrics] = useState([]);
  const [gradingCategories, setGradingCategories] = useState([]);
  const [rubricModalOpen, setRubricModalOpen] = useState(false);
  const [editCategories, setEditCategories] = useState([]);
  const [rubricSaving, setRubricSaving] = useState(false);
  const [gradingCourse, setGradingCourse] = useState(null);
  const [gradingSections, setGradingSections] = useState([]);
  const [gradingSection, setGradingSection] = useState(null);
  const [gradeResults, setGradeResults] = useState([]);
  const [componentOptions, setComponentOptions] = useState([]);
  // Team Configuration (home market assignment)
  const [teamConfigData, setTeamConfigData] = useState(null);
  const [teamConfigLoading, setTeamConfigLoading] = useState(false);
  const [teamConfigMode, setTeamConfigMode] = useState('instructor');
  const [teamConfigEdits, setTeamConfigEdits] = useState({});
  const [teamNameEdits, setTeamNameEdits] = useState({});
  const [teamConfigSaving, setTeamConfigSaving] = useState(false);
  const [teamConfigOpen, setTeamConfigOpen] = useState(false);

  // Game Creation state
  const [createStep, setCreateStep] = useState(0); // 0=scenario, 1=config, 2=confirm
  const [scenarios, setScenarios] = useState([]);
  const [scenariosLoading, setScenariosLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [scenarioDetail, setScenarioDetail] = useState(null);
  const [createNumTeams, setCreateNumTeams] = useState(4);
  const [createGameName, setCreateGameName] = useState('');
  const [createHomeMarkets, setCreateHomeMarkets] = useState({});
  const [createMarketMode, setCreateMarketMode] = useState('profile'); // profile, instructor, random
  const [createLoading, setCreateLoading] = useState(false);
  const [showCreateGame, setShowCreateGame] = useState(false);
  const [createdGameTeams, setCreatedGameTeams] = useState([]); // teams from game creation response
  const [pickerTeam, setPickerTeam] = useState(null); // selected team in student assignment picker
  // Round schedule state
  const [roundSchedule, setRoundSchedule] = useState(null); // { rounds: [...], game_name, ... }
  const [roundScheduleEdits, setRoundScheduleEdits] = useState({}); // { roundId: { deadline: '...' } }
  const [roundScheduleSaving, setRoundScheduleSaving] = useState(false);
  // Quick schedule inputs
  const [quickStartDate, setQuickStartDate] = useState('');
  const [quickDurationHours, setQuickDurationHours] = useState(48);
  const [quickGapHours, setQuickGapHours] = useState(0);
  // Game status tracking
  const [gameStatus, setGameStatus] = useState('setup');
  const [activatingGame, setActivatingGame] = useState(false);
  // Add student form
  const [addStudentName, setAddStudentName] = useState('');
  const [addStudentEmail, setAddStudentEmail] = useState('');
  const [addStudentId, setAddStudentId] = useState('');
  // Edit student
  const [editingEnrollment, setEditingEnrollment] = useState(null); // enrollment_id being edited
  const [editStudentName, setEditStudentName] = useState('');
  const [editStudentEmail, setEditStudentEmail] = useState('');
  const [editStudentId, setEditStudentId] = useState('');

  const loadAlerts = useCallback(async () => {
    if (!gameId) return;
    setAlertsLoading(true);
    try {
      const params = {};
      if (alertSevFilter !== 'all') params.severity = alertSevFilter;
      if (alertTeamFilter !== 'all') params.team_id = alertTeamFilter;
      if (alertRoundFilter !== 'all') params.round_number = alertRoundFilter;
      const res = await getInstructorAlerts(gameId, params);
      setAlerts(res.data?.alerts || res.data || []);
    } catch { /* empty */ }
    setAlertsLoading(false);
  }, [gameId, alertSevFilter, alertTeamFilter, alertRoundFilter]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  const loadData = useCallback(async () => {
    if (!gameId) return;
    setLoading(true);
    try {
      const [resDash, resQ, resEvt, resBrief] = await Promise.all([
        getInstructorDashboard(gameId),
        getResearchQueries(gameId),
        getEventTemplates(gameId).catch(() => ({ data: {} })),
        getTeamBriefings(gameId).catch(() => ({ data: {} })),
      ]);
      setDashboard(resDash.data);
      setQueries(resQ.data?.queries || []);
      setEventTemplates(resEvt.data?.event_templates || []);
      setMarketOptions(resEvt.data?.markets || []);
      setBriefings(resBrief.data?.briefings || []);
    } catch { /* empty */ }
    setLoading(false);
  }, [gameId]);

  useEffect(() => { loadData(); }, [loadData]);

  // Load courses
  const loadCourses = useCallback(async () => {
    try { const res = await getCourses(); setCourses(res.data || []); } catch { /* empty */ }
  }, []);
  useEffect(() => { loadCourses(); }, [loadCourses]);

  // Load team config (home market assignments)
  const loadTeamConfig = useCallback(async () => {
    if (!gameId) return;
    setTeamConfigLoading(true);
    try {
      const res = await getTeamConfig(gameId);
      setTeamConfigData(res.data);
      setTeamConfigEdits({});
    } catch { /* empty */ }
    setTeamConfigLoading(false);
  }, [gameId]);

  // Load available scenarios for game creation
  const loadScenarios = useCallback(async () => {
    setScenariosLoading(true);
    try {
      const res = await getScenarios();
      setScenarios(res.data?.scenarios || []);
    } catch { /* empty */ }
    setScenariosLoading(false);
  }, []);

  const handleSelectScenario = async (scenario) => {
    setSelectedScenario(scenario);
    try {
      const res = await getScenarioDetail(scenario.id);
      setScenarioDetail(res.data);
      setCreateGameName(`${scenario.name} Game`);
      setCreateHomeMarkets({});
      setCreateMarketMode('profile');
    } catch { /* empty */ }
    setCreateStep(1);
  };

  const handleCreateGame = async () => {
    if (!selectedScenario) return;
    setCreateLoading(true);
    try {
      const homeMarketCodes = createMarketMode === 'instructor' && scenarioDetail
        ? Array.from({ length: createNumTeams }, (_, i) =>
            createHomeMarkets[i] || scenarioDetail.markets[i % scenarioDetail.markets.length]?.code
          )
        : undefined;
      const res = await createGame({
        scenario_id: selectedScenario.id,
        num_teams: createNumTeams,
        name: createGameName || undefined,
        home_markets: homeMarketCodes,
        section_id: selectedSection || undefined,
      });
      message.success(`Game "${res.data.game_name}" created with ${res.data.num_teams} teams!`);
      setGameId(res.data.game_id);
      setGameStatus(res.data.status || 'setup');
      setCreatedGameTeams(res.data.teams || []);
      // Load round schedule for the new game
      loadRoundScheduleData(res.data.game_id);
    } catch (err) {
      message.error(err.response?.data?.error || 'Failed to create game');
    }
    setCreateLoading(false);
  };

  // Instructor header bar (plain JSX, not a component — avoids remount)
  const instructorHeader = (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '12px 0', marginBottom: 16, borderBottom: '2px solid #1E40AF',
    }}>
      <div>
        <Typography.Title level={4} style={{ margin: 0, color: '#1E40AF' }}>
          {t('instructor.portal_title')}
        </Typography.Title>
        {user && <Text type="secondary">{user.display_name || user.username}</Text>}
      </div>
      <Space>
        {gameId && (
          <Button size="small" onClick={() => { setGameId(null); setDashboard(null); }}>
            {t('instructor.switch_game')}
          </Button>
        )}
        <Button icon={<LogoutOutlined />} onClick={handleLogout}>{t('instructor.log_out')}</Button>
      </Space>
    </div>
  );

  if (loading && gameId) return <>{instructorHeader}<LoadingSpinner /></>;

  // Extract game data (may be null if no game selected)
  const hasGame = !!dashboard;
  const teams = dashboard?.teams || [];
  const rs = dashboard?.round_status || {};
  const events = dashboard?.events_this_round || [];

  const handleAdvance = async () => {
    setActionLoading(true);
    try {
      const force = rs.teams_pending > 0;
      await advanceRound(gameId, force);
      setAdvanceModalOpen(false);
      loadData();
    } catch (err) {
      Modal.error({ title: t('instructor.error'), content: err.response?.data?.error || t('instructor.failed_advance_round') });
    }
    setActionLoading(false);
  };

  const handleExtend = async () => {
    setActionLoading(true);
    try {
      await extendDeadline(gameId, { hours: extendHours });
      setExtendModalOpen(false);
      loadData();
    } catch { /* empty */ }
    setActionLoading(false);
  };

  const handleInjectEvent = async () => {
    if (!selectedEventTemplate) return;
    setActionLoading(true);
    try {
      await injectEvent(gameId, selectedEventTemplate, selectedMarket);
      setEventModalOpen(false);
      setSelectedEventTemplate(null);
      setSelectedMarket(null);
      loadData();
      message.success('Event injected');
    } catch (err) {
      message.error(err.response?.data?.error || 'Failed to inject event');
    }
    setActionLoading(false);
  };

  const exportAllTeams = () => {
    const headers = ['Team', 'Index', 'Cash', 'Revenue', 'Coherence', 'Status', 'Markets'];
    const rows = teams.map(t => [
      t.team_name, t.performance_index, t.cash_on_hand, t.total_revenue,
      t.coherence_score ?? '', t.decision_status, (t.markets_entered || []).join(';'),
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `game_${gameId}_teams.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const statusColor = { locked: 'green', draft: 'orange', empty: 'red' };
  const severityConfig = {
    critical: { color: 'red', label: t('instructor.critical') },
    concern: { color: 'gold', label: t('instructor.concern') },
    watch: { color: 'blue', label: t('instructor.watch') },
    info: { color: 'default', label: t('instructor.info') },
  };
  const teamNames = (teams || []).map(t => ({ value: t.team_id, label: t.team_name }));
  const roundOptions = [...new Set((alerts || []).map(a => a.round_number).filter(Boolean))].sort((a, b) => a - b);

  // --- Team drill-down ---
  const openDrill = async (teamId, round) => {
    setDrillTeam(teamId);
    setDrillRound(round || dashboard?.current_round);
    setDrillLoading(true);
    try {
      const res = await getTeamDecisions(gameId, teamId, round || dashboard.current_round);
      setDrillData(res.data);
    } catch { setDrillData(null); }
    setDrillLoading(false);
  };

  // ============ HELPERS FOR TABS ============

  const loadRoundScheduleData = async (gId) => {
    try {
      const res = await getRoundSchedule(gId);
      setRoundSchedule(res.data);
      setRoundScheduleEdits({});
    } catch (err) { console.error('loadRoundSchedule failed:', err); }
  };

  const handleSaveRoundSchedule = async () => {
    if (!gameId || Object.keys(roundScheduleEdits).length === 0) return;
    setRoundScheduleSaving(true);
    try {
      const rounds = Object.entries(roundScheduleEdits).map(([roundId, edits]) => ({
        round_id: parseInt(roundId, 10),
        ...edits,
      }));
      await updateRoundSchedule(gameId, rounds);
      message.success('Round schedule saved');
      await loadRoundScheduleData(gameId);
    } catch (err) {
      message.error('Failed to save schedule');
      console.error(err);
    } finally { setRoundScheduleSaving(false); }
  };

  // ============ TABS ============

  const gameControlTab = !gameId ? null : (
    <div>
      {/* Status summary */}
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}><Card><Statistic title={t('instructor.game')} value={createGameName || dashboard?.game_name || t('instructor.game')} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title={t('instructor.current_round')} value={dashboard?.current_round ?? 0} suffix={`${t('instructor.of')} ${roundSchedule?.total_rounds || '—'}`} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title={t('instructor.status')} value={gameStatus || dashboard?.status || 'setup'} valueStyle={{ color: gameStatus === 'active' ? '#52c41a' : gameStatus === 'paused' ? '#faad14' : gameStatus === 'archived' ? '#8c8c8c' : '#1890ff' }} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title={t('instructor.teams')} value={createdGameTeams.length || rs.total_teams || 0} suffix={hasGame ? `(${rs.teams_locked || 0} ${t('instructor.locked')})` : undefined} /></Card></Col>
      </Row>

      {/* Lifecycle controls */}
      <Card title={t('instructor.game_lifecycle')} style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <Space wrap>
            {gameStatus === 'setup' && (
              <Popconfirm title={t('instructor.activate_confirm')} onConfirm={async () => {
                try {
                  const res = await activateGame(gameId);
                  setGameStatus(res.data?.status || 'active');
                  loadRoundScheduleData(gameId);
                  loadData();
                  message.success('Game activated — Round 1 is open');
                } catch (err) { message.error(err.response?.data?.error || 'Failed to activate'); }
              }}>
                <Button type="primary">{t('instructor.activate_game')}</Button>
              </Popconfirm>
            )}
            {gameStatus === 'active' && (
              <>
                <Button type="primary" onClick={() => setAdvanceModalOpen(true)}>{t('instructor.advance_round')}</Button>
                <Button onClick={() => setExtendModalOpen(true)}>{t('instructor.extend_deadline')}</Button>
                <Popconfirm title={t('instructor.pause_confirm')} onConfirm={async () => {
                  try {
                    const res = await pauseGame(gameId);
                    setGameStatus(res.data?.status || 'paused');
                    message.success('Game paused');
                  } catch (err) { message.error(err.response?.data?.error || 'Failed to pause'); }
                }}>
                  <Button>{t('instructor.pause_game')}</Button>
                </Popconfirm>
              </>
            )}
            {gameStatus === 'paused' && (
              <>
                <Popconfirm title={t('instructor.resume_confirm')} onConfirm={async () => {
                  try {
                    const res = await resumeGame(gameId);
                    setGameStatus(res.data?.status || 'active');
                    message.success('Game resumed');
                  } catch (err) { message.error(err.response?.data?.error || 'Failed to resume'); }
                }}>
                  <Button type="primary">{t('instructor.resume_game')}</Button>
                </Popconfirm>
                <Button onClick={() => setExtendModalOpen(true)}>{t('instructor.extend_deadline')}</Button>
              </>
            )}
            {(gameStatus === 'active' || gameStatus === 'paused') && (
              <Popconfirm title={t('instructor.reset_confirm')} okText={t('instructor.reset')} okType="danger" onConfirm={async () => {
                try {
                  const res = await resetGame(gameId);
                  setGameStatus(res.data?.status || 'setup');
                  setDashboard(null);
                  loadRoundScheduleData(gameId);
                  message.success('Game reset to setup');
                } catch (err) { message.error(err.response?.data?.error || 'Failed to reset'); }
              }}>
                <Button danger>{t('instructor.reset_to_setup')}</Button>
              </Popconfirm>
            )}
            {gameStatus !== 'archived' && (
              <Popconfirm title={t('instructor.archive_confirm')} okText={t('instructor.archive')} onConfirm={async () => {
                try {
                  await archiveGame(gameId);
                  setGameStatus('archived');
                  message.success('Game archived. You can now create a new game for this section.');
                } catch (err) { message.error(err.response?.data?.error || 'Failed to archive'); }
              }}>
                <Button>{t('instructor.archive_game')}</Button>
              </Popconfirm>
            )}
            <Popconfirm title={t('instructor.delete_confirm')} okText={t('instructor.delete_forever')} okType="danger" onConfirm={async () => {
              try {
                await deleteGame(gameId);
                setGameId(null);
                setGameStatus(null);
                setDashboard(null);
                setRoundSchedule(null);
                setCreatedGameTeams([]);
                message.success('Game deleted. You can now create a new game.');
              } catch (err) { message.error(err.response?.data?.error || 'Failed to delete'); }
            }}>
              <Button danger type="primary">{t('instructor.delete_game')}</Button>
            </Popconfirm>
          </Space>
          {hasGame && rs.deadline && (
            <Text type="secondary">{t('instructor.current_deadline')}: {new Date(rs.deadline).toLocaleString()}</Text>
          )}
        </div>
        {hasGame && (
          <div style={{ marginTop: 12 }}>
            <Text>{t('instructor.teams_locked_status', { locked: rs.teams_locked || 0, total: rs.total_teams || 0 })}
              {rs.teams_pending > 0 && ` ${t('instructor.teams_pending_status', { count: rs.teams_pending })}`}
            </Text>
          </div>
        )}
      </Card>

      {/* Round schedule */}
      {roundSchedule && (
        <Card title={t('instructor.round_schedule')} style={{ marginTop: 16 }}
          extra={
            <Space>
              <Button size="small" onClick={() => loadRoundScheduleData(gameId)}>{t('instructor.refresh')}</Button>
              <Button type="primary" size="small" loading={roundScheduleSaving}
                disabled={Object.keys(roundScheduleEdits).length === 0}
                onClick={handleSaveRoundSchedule}>
                {t('instructor.save_schedule')}
              </Button>
            </Space>
          }
        >
          <Table
            size="small" pagination={false}
            dataSource={(roundSchedule.rounds || []).filter(r => r.round_number > 0)}
            rowKey="round_id"
            columns={[
              { title: t('instructor.round'), dataIndex: 'round_number', width: 80, render: v => <Tag>{`${t('instructor.round')} ${v}`}</Tag> },
              { title: t('instructor.status'), dataIndex: 'status', width: 100,
                render: v => <Tag color={v === 'open' ? 'green' : v === 'processed' ? 'blue' : v === 'closed' ? 'orange' : 'default'}>{v}</Tag>,
              },
              {
                title: t('instructor.deadline'), key: 'deadline',
                render: (_, record) => {
                  const editVal = roundScheduleEdits[record.round_id]?.deadline;
                  const currentVal = editVal || record.deadline;
                  const inputVal = currentVal ? new Date(currentVal).toISOString().slice(0, 16) : '';
                  return (
                    <Input
                      type="datetime-local" value={inputVal} style={{ width: 240 }}
                      onChange={e => {
                        const val = e.target.value;
                        if (val) {
                          setRoundScheduleEdits(prev => ({
                            ...prev,
                            [record.round_id]: { ...prev[record.round_id], deadline: new Date(val).toISOString() },
                          }));
                        }
                      }}
                      onBlur={async (e) => {
                        const val = e.target.value;
                        if (val && gameId) {
                          try {
                            await updateRoundSchedule(gameId, [{ round_id: record.round_id, deadline: new Date(val).toISOString() }]);
                            await loadRoundScheduleData(gameId);
                          } catch { /* Save button still available */ }
                        }
                      }}
                    />
                  );
                },
              },
            ]}
          />
          {/* Quick schedule */}
          <Card size="small" title={t('instructor.quick_schedule')} style={{ marginTop: 16 }}>
            <Row gutter={16} align="middle">
              <Col><Text strong>{t('instructor.round1_starts')}</Text></Col>
              <Col>
                <Input type="datetime-local" value={quickStartDate}
                  onChange={e => setQuickStartDate(e.target.value)} style={{ width: 220 }} />
              </Col>
              <Col><Text strong>{t('instructor.hours_per_round')}</Text></Col>
              <Col>
                <InputNumber min={1} max={720} value={quickDurationHours}
                  onChange={v => setQuickDurationHours(v)} style={{ width: 100 }} />
              </Col>
              <Col><Text strong>{t('instructor.gap_hours')}</Text></Col>
              <Col>
                <InputNumber min={0} max={168} value={quickGapHours}
                  onChange={v => setQuickGapHours(v)} style={{ width: 100 }} />
              </Col>
              <Col>
                <Button type="primary" disabled={!quickStartDate} onClick={async () => {
                  let current = new Date(quickStartDate);
                  const edits = {};
                  const playableRounds = (roundSchedule?.rounds || []).filter(r => r.round_number > 0);
                  for (const r of playableRounds) {
                    const deadline = new Date(current.getTime() + quickDurationHours * 3600000);
                    edits[r.round_id] = { deadline: deadline.toISOString() };
                    current = new Date(deadline.getTime() + quickGapHours * 3600000);
                  }
                  try {
                    const rounds = Object.entries(edits).map(([roundId, e]) => ({
                      round_id: parseInt(roundId, 10), ...e,
                    }));
                    await updateRoundSchedule(gameId, rounds);
                    await loadRoundScheduleData(gameId);
                    message.success(`Schedule saved for ${playableRounds.length} rounds.`);
                  } catch {
                    setRoundScheduleEdits(prev => ({ ...prev, ...edits }));
                    message.warning('Schedule generated but failed to save. Click "Save Schedule" to retry.');
                  }
                }}>
                  {t('instructor.generate_save')}
                </Button>
              </Col>
            </Row>
          </Card>
        </Card>
      )}

      {/* Team Configuration — Home Market Assignment */}
      <div style={{ marginTop: 16 }}>
        <PanelCard
          title={<Space><HomeOutlined /> {t('instructor.team_configuration')}</Space>}
          headerColor="strategic"
          actions={
            <Button size="small" type="link" style={{ color: '#fff' }}
              onClick={() => { if (!teamConfigOpen) { loadTeamConfig(); } setTeamConfigOpen(!teamConfigOpen); }}>
              {teamConfigOpen ? t('instructor.collapse') : t('instructor.expand')}
            </Button>
          }
        >
          {!teamConfigOpen ? (
            <Text type="secondary">
              {t('instructor.team_config_hint')}
            </Text>
          ) : teamConfigLoading ? <LoadingSpinner /> : !teamConfigData ? (
              <Empty description={t('instructor.unable_load_team_config')} />
            ) : (() => {
              const { teams: cfgTeams, available_markets: markets, locked } = teamConfigData;
              const getMarketForTeam = (teamId) => {
                if (teamConfigEdits[teamId] !== undefined) return teamConfigEdits[teamId];
                const t = cfgTeams.find(t => t.team_id === teamId);
                return t?.home_market_code || null;
              };
              const setMarketForTeam = (teamId, code) => {
                setTeamConfigEdits(prev => ({ ...prev, [teamId]: code }));
                if (teamConfigMode !== 'instructor') setTeamConfigMode('instructor');
              };
              const hasEdits = Object.keys(teamConfigEdits).length > 0 || Object.keys(teamNameEdits).length > 0;

              const handleSave = async () => {
                setTeamConfigSaving(true);
                try {
                  const payload = cfgTeams.map(t => ({
                    team_id: t.team_id,
                    home_market_code: getMarketForTeam(t.team_id),
                    ...(teamNameEdits[t.team_id] !== undefined ? { team_name: teamNameEdits[t.team_id] } : {}),
                  }));
                  await updateTeamConfig(gameId, { teams: payload });
                  message.success(t('instructor.team_config_saved'));
                  setTeamNameEdits({});
                  setTeamConfigEdits({});
                  loadTeamConfig();
                } catch (err) {
                  message.error(err.response?.data?.error || 'Failed to save');
                }
                setTeamConfigSaving(false);
              };

              const handleRandomize = async () => {
                try {
                  const res = await randomizeHomeMarkets(gameId);
                  const preview = res.data?.preview || [];
                  const edits = {};
                  preview.forEach(p => { edits[p.team_id] = p.home_market_code; });
                  setTeamConfigEdits(edits);
                  message.info('Random assignment previewed — click Save to apply');
                } catch (err) {
                  message.error(err.response?.data?.error || 'Failed to randomize');
                }
              };

              const handleAllSame = (code) => {
                const edits = {};
                cfgTeams.forEach(t => { edits[t.team_id] = code; });
                setTeamConfigEdits(edits);
              };

              const marketTooltip = (m) => {
                if (!m) return '';
                const volLabel = m.exchange_rate_volatility > 0.08 ? 'volatile' : m.exchange_rate_volatility > 0.04 ? 'moderate' : 'stable';
                return `${m.name}\nGrowth: ${(m.base_growth_rate * 100).toFixed(1)}% | Tariff: ${(m.tariff_rate * 100).toFixed(1)}% | Tax: ${(m.tax_rate * 100).toFixed(0)}%\nRegulatory: ${m.regulatory_difficulty} | Infrastructure: ${m.infrastructure_quality}\nCurrency: ${m.currency_code || '—'} (${volLabel})\nEntry Cost: $${Number(m.entry_cost_base).toLocaleString()}`;
              };

              return (
                <div>
                  {locked && (
                    <Alert type="warning" showIcon icon={<LockOutlined />} style={{ marginBottom: 12 }}
                      message={t('instructor.config_locked')}
                      description={t('instructor.config_locked_desc')}
                    />
                  )}

                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ display: 'block', marginBottom: 8 }}>{t('instructor.assignment_mode')}</Text>
                    <Space wrap>
                      <Radio.Group value={teamConfigMode} onChange={e => {
                        const mode = e.target.value;
                        setTeamConfigMode(mode);
                        if (mode === 'random') handleRandomize();
                      }} disabled={locked}>
                        <Radio.Button value="instructor">{t('instructor.instructor_assigns')}</Radio.Button>
                        <Radio.Button value="random">{t('instructor.random')}</Radio.Button>
                        <Radio.Button value="same">{t('instructor.all_same')}</Radio.Button>
                      </Radio.Group>
                      {teamConfigMode === 'random' && !locked && (
                        <Button icon={<ReloadOutlined />} size="small" onClick={handleRandomize}>
                          {t('instructor.re_randomize')}
                        </Button>
                      )}
                      {teamConfigMode === 'same' && (
                        <Select placeholder={t('instructor.select_market_all_teams')} style={{ width: 200 }}
                          disabled={locked}
                          value={getMarketForTeam(cfgTeams[0]?.team_id)}
                          onChange={handleAllSame}
                          options={markets.map(m => ({ value: m.code, label: m.name }))}
                        />
                      )}
                    </Space>
                  </div>

                  <Table
                    dataSource={cfgTeams} rowKey="team_id" pagination={false} size="small"
                    columns={[
                      {
                        title: t('instructor.company_name'), dataIndex: 'team_name', width: 200,
                        render: (v, record) => locked ? (
                          <Text>{v}</Text>
                        ) : (
                          <input
                            type="text"
                            defaultValue={teamNameEdits[record.team_id] !== undefined ? teamNameEdits[record.team_id] : v}
                            onBlur={e => {
                              const newName = e.target.value.trim();
                              if (newName && newName !== v) {
                                setTeamNameEdits(prev => ({ ...prev, [record.team_id]: newName }));
                              } else if (newName === v) {
                                setTeamNameEdits(prev => { const n = { ...prev }; delete n[record.team_id]; return n; });
                              }
                            }}
                            style={{
                              width: '100%', border: '1px solid #d9d9d9', borderRadius: 4,
                              padding: '4px 8px', fontSize: 13,
                            }}
                          />
                        ),
                      },
                      {
                        title: t('instructor.home_market'), key: 'home_market', width: 240,
                        render: (_, record) => locked ? (
                          <Space>
                            <Tooltip title={t('instructor.locked_tooltip')}>
                              <LockOutlined style={{ color: '#999' }} />
                            </Tooltip>
                            <Text>{record.home_market_name || 'Not set'}</Text>
                          </Space>
                        ) : (
                          <Select
                            value={getMarketForTeam(record.team_id)}
                            onChange={v => setMarketForTeam(record.team_id, v)}
                            placeholder={t('instructor.select_market')}
                            style={{ width: 220 }}
                            allowClear
                            options={markets.map(m => ({
                              value: m.code,
                              label: (
                                <Tooltip title={marketTooltip(m)} placement="right">
                                  <span>{m.name}</span>
                                </Tooltip>
                              ),
                            }))}
                          />
                        ),
                      },
                      {
                        title: t('instructor.starter_profile'), dataIndex: 'starter_profile_name', width: 180,
                        render: (v) => <Text type="secondary">{v || '—'}</Text>,
                      },
                    ]}
                  />

                  {/* Quick Preview */}
                  {markets.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <Text strong style={{ display: 'block', marginBottom: 8 }}>{t('instructor.quick_preview')}</Text>
                      <Row gutter={[12, 12]}>
                        {markets.map(m => (
                          <Col xs={24} sm={12} md={8} key={m.id}>
                            <Tooltip title={marketTooltip(m)}>
                              <Card size="small" hoverable style={{ cursor: 'default' }}>
                                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                                  <HomeOutlined style={{ marginRight: 6 }} />
                                  <Text strong>{m.name}</Text>
                                  <Tag style={{ marginLeft: 8, fontSize: 10 }}>{m.code.toUpperCase()}</Tag>
                                </div>
                                <Text style={{ fontSize: 12, display: 'block' }}>{t('instructor.growth')}: {(m.base_growth_rate * 100).toFixed(1)}%</Text>
                                <Text style={{ fontSize: 12, display: 'block' }}>{t('instructor.tariff')}: {(m.tariff_rate * 100).toFixed(1)}% | {t('instructor.tax')}: {(m.tax_rate * 100).toFixed(0)}%</Text>
                                <Text style={{ fontSize: 12, display: 'block' }}>{t('instructor.currency')}: {m.currency_code || '—'}</Text>
                                <Text style={{ fontSize: 12, display: 'block' }}>{t('instructor.entry_cost')}: ${Number(m.entry_cost_base).toLocaleString()}</Text>
                              </Card>
                            </Tooltip>
                          </Col>
                        ))}
                      </Row>
                    </div>
                  )}

                  {/* Info */}
                  <Alert
                    type="info"
                    style={{ marginTop: 16 }}
                    message={t('instructor.home_market_info')}
                  />

                  {/* Save Button */}
                  {!locked && (
                    <div style={{ marginTop: 16 }}>
                      <Space>
                        <Button type="primary" disabled={!hasEdits} loading={teamConfigSaving}
                          onClick={handleSave}>
                          {t('instructor.save_configuration')}
                        </Button>
                        <Button onClick={loadTeamConfig} disabled={teamConfigLoading}>{t('instructor.refresh')}</Button>
                      </Space>
                    </div>
                  )}
                </div>
              );
            })()
          }
        </PanelCard>
      </div>
    </div>
  );

  const teamOverviewTab = !hasGame ? null : (
    <Card>
      <Table
        dataSource={teams} rowKey="team_id" pagination={false} size="small"
        columns={[
          { title: t('instructor.team'), dataIndex: 'team_name' },
          { title: t('instructor.members'), dataIndex: 'members', render: v => v?.length || 0 },
          { title: t('instructor.index'), dataIndex: 'performance_index', render: v => v?.toFixed(2) },
          { title: t('instructor.cash'), dataIndex: 'cash_on_hand', render: fmt },
          { title: t('instructor.revenue'), dataIndex: 'total_revenue', render: fmt },
          { title: t('instructor.distress'), dataIndex: 'is_in_distress', render: v => v ? <Tag color="red">{t('instructor.yes')}</Tag> : t('instructor.no') },
          { title: t('instructor.decision'), dataIndex: 'decision_status', render: v => <Tag color={statusColor[v] || 'default'}>{v}</Tag> },
          { title: t('instructor.coherence'), dataIndex: 'coherence_score', render: v => v != null ? v.toFixed(1) : '—' },
          { title: t('instructor.markets'), dataIndex: 'markets_entered', render: v => (v || []).join(', ') },
          {
            title: t('instructor.actions'), key: 'actions', width: 100,
            render: (_, r) => (
              <Button type="link" size="small" onClick={() => openDrill(r.team_id)}>
                {t('instructor.view_decisions')}
              </Button>
            ),
          },
        ]}
        expandable={{
          expandedRowRender: (record) => (
            <div><Text strong>{t('instructor.members')}: </Text><Text>{(record.members || []).join(', ') || t('instructor.no_members')}</Text></div>
          ),
        }}
      />
    </Card>
  );

  const eventManagerTab = !hasGame ? null : (
    <div>
      <Card title={t('instructor.events_this_round')}>
        {(events || []).length === 0 ? <Empty description={t('instructor.no_events_this_round')} /> : (
          (events || []).map((ev, i) => (
            <Tag key={i} color={ev.severity === 'high' || ev.severity === 'critical' ? 'red' : ev.severity === 'medium' ? 'orange' : 'blue'}>
              {ev.name} ({ev.market})
            </Tag>
          ))
        )}
      </Card>
      <Card title={t('instructor.inject_event')} style={{ marginTop: 16 }}>
        <Button type="primary" onClick={() => setEventModalOpen(true)}>{t('instructor.inject_event')}</Button>
      </Card>
    </div>
  );

  const researchMonitorTab = !hasGame ? null : (
    <Card title={t('instructor.research_queries')}>
      {queries.length === 0 ? <Empty description={t('instructor.no_research_queries')} /> : (
        <Table dataSource={queries} rowKey={(r, i) => `${r.team_name}-${i}`}
          columns={[
            { title: t('instructor.team'), dataIndex: 'team_name' },
            { title: t('instructor.round'), dataIndex: 'round_number' },
            { title: t('instructor.query'), dataIndex: 'query_text', ellipsis: true },
            { title: t('instructor.timestamp'), dataIndex: 'timestamp', render: v => new Date(v).toLocaleString() },
          ]}
          pagination={{ pageSize: 20 }} size="small"
        />
      )}
    </Card>
  );

  // --- Grading Tab (enhanced) ---
  const handleGradingCourseChange = async (courseId) => {
    setGradingCourse(courseId);
    setGradingSection(null);
    setGradingSections([]);
    setRubrics([]);
    setGradingCategories([]);
    if (!courseId) return;
    // Load sections
    try {
      const secRes = await getSections(courseId);
      setGradingSections(secRes.data || []);
    } catch { /* empty */ }
    // Load rubric (independent — don't block sections)
    try {
      const rubRes = await getGradingRubrics(courseId);
      setRubrics(rubRes.data || []);
      if (rubRes.data?.length > 0) {
        const catRes = await getGradingCategories(rubRes.data[0].rubric_id);
        setGradingCategories(catRes.data || []);
      }
    } catch { /* empty */ }
  };

  const loadGrading = async () => {
    if (!gradingCourse) return;
    try {
      const res = await getGradingRubrics(gradingCourse);
      setRubrics(res.data || []);
      if (res.data?.length > 0) {
        const catRes = await getGradingCategories(res.data[0].rubric_id);
        setGradingCategories(catRes.data || []);
      }
    } catch { /* empty */ }
  };

  const openRubricEditor = async () => {
    setEditCategories(gradingCategories.map(c => ({ ...c })));
    if (componentOptions.length === 0) {
      try {
        const res = await getComponentLabels();
        // Filter to active components only (exclude legacy zeros)
        const active = ['performance_index', 'coherence_score', 'communication_quality',
          'stakeholder_satisfaction', 'financial_stewardship', 'total_score'];
        setComponentOptions((res.data || []).filter(c => active.includes(c.key)));
      } catch { /* empty */ }
    }
    setRubricModalOpen(true);
  };

  const handleRubricSave = async () => {
    const totalWeight = editCategories.reduce((s, c) => s + Number(c.weight || 0), 0);
    if (Math.abs(totalWeight - 100) > 0.01) {
      message.warning(`Weights must sum to 100% (currently ${totalWeight.toFixed(1)}%)`);
      return;
    }
    setRubricSaving(true);
    try {
      const rubricId = rubrics[0]?.rubric_id;
      // Delete removed categories
      const editIds = new Set(editCategories.filter(c => c.category_id).map(c => c.category_id));
      for (const orig of gradingCategories) {
        if (orig.category_id && !editIds.has(orig.category_id)) {
          await deleteGradingCategory(orig.category_id);
        }
      }
      // Update existing + create new
      for (const cat of editCategories) {
        if (cat.category_id) {
          await updateGradingCategory(cat.category_id, {
            category_name: cat.category_name,
            weight: cat.weight,
            description: cat.description,
          });
        } else {
          await createGradingCategory({
            rubric: rubricId,
            category_name: cat.category_name,
            weight: cat.weight,
            sort_order: cat.sort_order || editCategories.indexOf(cat) + 1,
            description: cat.description,
          });
        }
      }
      message.success('Rubric updated');
      setRubricModalOpen(false);
      loadGrading();
    } catch { message.error('Failed to save rubric'); }
    setRubricSaving(false);
  };

  const updateEditCategory = (idx, field, value) => {
    setEditCategories(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const addEditCategory = () => {
    setEditCategories(prev => [...prev, {
      category_name: '',
      weight: 0,
      sort_order: prev.length + 1,
      description: '',
      _isNew: true,
    }]);
  };

  const removeEditCategory = (idx) => {
    setEditCategories(prev => prev.filter((_, i) => i !== idx));
  };

  const selectedGradingSection = gradingSections.find(s => s.section_id === gradingSection);
  const gradingInstanceId = selectedGradingSection?.simulation_status?.instance_id || null;

  const gradingTab = (
    <div>
      {/* Course / Section selector */}
      <Card title={t('instructor.select_course_section')} style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder={t('instructor.select_course')}
            value={gradingCourse}
            onChange={handleGradingCourseChange}
            style={{ width: 300 }}
            allowClear
            options={courses.map(c => ({ value: c.course_id, label: `${c.course_code} — ${c.course_name}` }))}
          />
          <Select
            placeholder={t('instructor.select_section')}
            value={gradingSection}
            onChange={setGradingSection}
            style={{ width: 240 }}
            allowClear
            disabled={!gradingCourse}
            options={gradingSections.map(s => ({ value: s.section_id, label: `${s.section_code}${s.section_name ? ' — ' + s.section_name : ''}` }))}
          />
        </Space>
      </Card>

      <Card title={t('instructor.team_performance')}>
        <Table dataSource={teams} rowKey="team_id" pagination={false} size="small"
          columns={[
            { title: t('instructor.team'), dataIndex: 'team_name' },
            { title: t('instructor.performance_index'), dataIndex: 'performance_index', render: v => v?.toFixed(2) },
            { title: t('instructor.coherence'), dataIndex: 'coherence_score', render: v => v != null ? v.toFixed(1) : '—' },
            { title: t('instructor.revenue'), dataIndex: 'total_revenue', render: fmt },
            { title: t('instructor.cash'), dataIndex: 'cash_on_hand', render: fmt },
          ]}
        />
      </Card>

      <Card title={t('instructor.grading_rubric')} style={{ marginTop: 16 }}>
        {!gradingCourse ? (
          <Text type="secondary">{t('instructor.select_course_for_rubric')}</Text>
        ) : rubrics.length === 0 ? (
          <div>
            <Text type="secondary">{t('instructor.no_rubric')}</Text>
            <Button type="primary" style={{ marginLeft: 12 }} onClick={async () => {
              try {
                await seedRubric(gradingCourse);
                message.success('Default rubric created');
                loadGrading();
              } catch { message.error('Failed to seed rubric'); }
            }}>
              {t('instructor.create_default_rubric')}
            </Button>
          </div>
        ) : (
          <>
            <Space>
              <Text strong>{rubrics[0]?.rubric_name || 'Rubric'}</Text>
              <Button size="small" icon={<EditOutlined />} onClick={openRubricEditor}>
                {t('instructor.edit_rubric')}
              </Button>
            </Space>
            {gradingCategories.length > 0 && (
              <Table dataSource={gradingCategories} rowKey={r => r.category_id || r.id} pagination={false} size="small" style={{ marginTop: 8 }}
                columns={[
                  { title: t('instructor.category'), dataIndex: 'category_name' },
                  { title: t('instructor.weight'), dataIndex: 'weight', render: v => `${Number(v).toFixed(0)}%` },
                  { title: t('instructor.description'), dataIndex: 'description', ellipsis: true },
                ]}
              />
            )}
            <Tooltip title={!gradingSection ? 'Select a section first' : !gradingInstanceId ? 'No simulation linked to this section' : ''}>
              <Button
                style={{ marginTop: 8 }}
                disabled={!gradingInstanceId}
                onClick={async () => {
                  try {
                    const res = await calculateGrades(gradingInstanceId, gradingCourse);
                    setGradeResults(res.data || []);
                    message.success('Grades calculated');
                  } catch { message.error('Failed to calculate grades'); }
                }}
              >
                {t('instructor.calculate_grades')}
              </Button>
            </Tooltip>
          </>
        )}
      </Card>

      {gradeResults.length > 0 && (
        <Card title={t('instructor.team_grades')} style={{ marginTop: 16 }}>
          <Table
            dataSource={gradeResults}
            rowKey="team_id"
            pagination={false}
            size="small"
            columns={[
              { title: t('instructor.team'), dataIndex: 'team_name', width: 140 },
              ...(gradeResults[0]?.categories || []).map(cat => ({
                title: `${cat.category_name} (${Number(cat.weight).toFixed(0)}%)`,
                key: cat.category_name,
                width: 140,
                render: (_, record) => {
                  const c = record.categories?.find(x => x.category_name === cat.category_name);
                  return c ? c.final_score.toFixed(1) : '—';
                },
              })),
              {
                title: t('instructor.raw'),
                dataIndex: 'raw_overall',
                width: 80,
                render: v => v?.toFixed(1),
              },
              {
                title: t('instructor.final_grade'),
                dataIndex: 'overall',
                width: 100,
                render: v => <Text strong>{v?.toFixed(1)}</Text>,
              },
            ]}
          />
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            {t('instructor.grade_stretch_note')}
          </Text>
        </Card>
      )}

      <Card title={t('instructor.export')} style={{ marginTop: 16 }}>
        <Space>
          <Button onClick={exportAllTeams}>{t('instructor.export_team_summary')}</Button>
          <Button disabled={!gradingInstanceId} onClick={async () => {
            try {
              const res = await exportTeamGradesCsv(gradingInstanceId);
              const url = URL.createObjectURL(res.data);
              const a = document.createElement('a'); a.href = url; a.download = 'team_grades.csv'; a.click();
              URL.revokeObjectURL(url);
            } catch { message.error('No grades to export — calculate grades first'); }
          }}>{t('instructor.export_team_grades')}</Button>
          <Button disabled={!gradingInstanceId} onClick={async () => {
            try {
              const res = await exportStudentGradesCsv(gradingInstanceId);
              const url = URL.createObjectURL(res.data);
              const a = document.createElement('a'); a.href = url; a.download = 'student_grades.csv'; a.click();
              URL.revokeObjectURL(url);
            } catch { message.error('No student grades to export'); }
          }}>{t('instructor.export_student_grades')}</Button>
        </Space>
      </Card>

      {/* Rubric Editor Modal */}
      <Modal
        title={t('instructor.edit_grading_rubric')}
        open={rubricModalOpen}
        onCancel={() => setRubricModalOpen(false)}
        onOk={handleRubricSave}
        confirmLoading={rubricSaving}
        okText={t('instructor.save')}
        width={640}
      >
        <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
          {t('instructor.rubric_editor_help')}
        </Text>
        {componentOptions.length > 0 && (
          <Text type="secondary" style={{ display: 'block', marginBottom: 16, fontSize: 12 }}>
            Available metrics: {componentOptions.map(c => c.label).join(', ')}
          </Text>
        )}
        {editCategories.map((cat, idx) => (
          <Card key={cat.category_id || `new-${idx}`} size="small" style={{ marginBottom: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Space>
                  <Input
                    value={cat.category_name}
                    onChange={e => updateEditCategory(idx, 'category_name', e.target.value)}
                    style={{ width: 280 }}
                    placeholder="Category name (e.g. Strategic Coherence)"
                  />
                  <InputNumber
                    value={Number(cat.weight)}
                    onChange={v => updateEditCategory(idx, 'weight', v)}
                    min={0} max={100} step={5}
                    addonAfter="%"
                    style={{ width: 120 }}
                  />
                </Space>
                {editCategories.length > 1 && (
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeEditCategory(idx)} />
                )}
              </Space>
              <Input
                value={cat.description || ''}
                onChange={e => updateEditCategory(idx, 'description', e.target.value)}
                placeholder="Description"
                size="small"
              />
            </Space>
          </Card>
        ))}
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Button type="dashed" icon={<PlusOutlined />} onClick={addEditCategory}>
            {t('instructor.add_category')}
          </Button>
          <Text type={Math.abs(editCategories.reduce((s, c) => s + Number(c.weight || 0), 0) - 100) < 0.01 ? 'success' : 'danger'}>
            Total: {editCategories.reduce((s, c) => s + Number(c.weight || 0), 0).toFixed(0)}%
          </Text>
        </Space>
      </Modal>
    </div>
  );

  const handleAcknowledge = async (alertId) => {
    try { await acknowledgeAlert(gameId, alertId); loadAlerts(); } catch { /* empty */ }
  };

  const aiCoachTab = !hasGame ? null : (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select value={alertSevFilter} onChange={setAlertSevFilter} style={{ width: 140 }}
            options={[{ value: 'all', label: t('instructor.all_severities') }, { value: 'critical', label: t('instructor.critical') }, { value: 'concern', label: t('instructor.concern') }, { value: 'watch', label: t('instructor.watch') }, { value: 'info', label: t('instructor.info') }]}
          />
          <Select value={alertTeamFilter} onChange={setAlertTeamFilter} style={{ width: 180 }}
            options={[{ value: 'all', label: t('instructor.all_teams') }, ...teamNames]}
          />
          <Select value={alertRoundFilter} onChange={setAlertRoundFilter} style={{ width: 140 }}
            options={[{ value: 'all', label: t('instructor.all_rounds') }, ...roundOptions.map(r => ({ value: r, label: `${t('instructor.round')} ${r}` }))]}
          />
          <Button onClick={loadAlerts} loading={alertsLoading}>{t('instructor.refresh')}</Button>
        </Space>
      </Card>
      {alertsLoading ? <LoadingSpinner /> : (alerts || []).length === 0 ? <Empty description={t('instructor.no_alerts')} /> : (
        <Row gutter={[16, 16]}>
          {alerts.map((alert) => {
            const sev = severityConfig[alert.severity] || severityConfig.info;
            return (
              <Col xs={24} md={12} key={alert.id}>
                <Badge.Ribbon text={sev.label} color={sev.color}>
                  <Card size="small"
                    title={<Space><Text strong>{alert.team_name || 'Unknown'}</Text>{alert.round_number && <Tag>R{alert.round_number}</Tag>}</Space>}
                    actions={[
                      alert.acknowledged ? <Text key="ack" type="secondary">{t('instructor.acknowledged')}</Text> :
                        <Button key="ack" type="link" size="small" onClick={() => handleAcknowledge(alert.id)}>{t('instructor.acknowledge')}</Button>,
                    ]}
                  >
                    <Text strong>{alert.title || alert.alert_type}</Text><br />
                    <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>{alert.detail || alert.message}</Text>
                    {alert.teaching_note && (
                      <div style={{ marginTop: 8, padding: 8, background: '#f5f5f5', borderRadius: 4 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          <Text strong style={{ fontSize: 12 }}>{t('instructor.teaching_note')}:</Text> {alert.teaching_note}
                        </Text>
                      </div>
                    )}
                  </Card>
                </Badge.Ribbon>
              </Col>
            );
          })}
        </Row>
      )}
    </div>
  );

  // --- Briefings Tab ---
  const briefingRounds = [...new Set(briefings.map(b => b.round_number))].sort((a, b) => b - a);
  const briefingTeams = [...new Set(briefings.map(b => b.team_name))].sort();
  const filteredBriefings = briefings.filter(b => {
    if (briefingRound !== 'all' && b.round_number !== briefingRound) return false;
    if (briefingTeam !== 'all' && b.team_name !== briefingTeam) return false;
    return true;
  });

  const briefingsTab = !hasGame ? null : (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select value={briefingRound} onChange={setBriefingRound} style={{ width: 140 }}
            options={[{ value: 'all', label: t('instructor.all_rounds') }, ...briefingRounds.map(r => ({ value: r, label: `${t('instructor.round')} ${r}` }))]}
          />
          <Select value={briefingTeam} onChange={setBriefingTeam} style={{ width: 180 }}
            options={[{ value: 'all', label: t('instructor.all_teams') }, ...briefingTeams.map(tm => ({ value: tm, label: tm }))]}
          />
        </Space>
      </Card>
      {filteredBriefings.length === 0 ? <Empty description={t('instructor.no_briefings')} /> : (
        <Collapse
          items={filteredBriefings.map(b => ({
            key: b.id,
            label: <Space><Tag color="blue">{b.team_name}</Tag><Tag>{t('instructor.round')} {b.round_number}</Tag><Text type="secondary">{b.generated_at ? new Date(b.generated_at).toLocaleString() : ''}</Text></Space>,
            children: (
              <div>
                <Card size="small" title={t('instructor.executive_summary')} style={{ marginBottom: 8 }}>
                  <Text>{b.executive_summary}</Text>
                </Card>
                {b.risk_alerts && (Array.isArray(b.risk_alerts) ? b.risk_alerts : []).length > 0 && (
                  <Card size="small" title={t('instructor.risk_alerts')} style={{ marginBottom: 8 }}>
                    {(Array.isArray(b.risk_alerts) ? b.risk_alerts : []).map((r, i) => (
                      <Tag key={i} color={r.severity === 'critical' ? 'red' : r.severity === 'warning' ? 'orange' : 'blue'} style={{ marginBottom: 4 }}>
                        {r.title || r.message || JSON.stringify(r)}
                      </Tag>
                    ))}
                  </Card>
                )}
                {b.strategic_recommendations && (
                  <Card size="small" title={t('instructor.strategic_recommendations')}>
                    {Array.isArray(b.strategic_recommendations) ? b.strategic_recommendations.map((r, i) => (
                      <div key={i} style={{ marginBottom: 8 }}>
                        <Tag color={r.priority === 'high' ? 'red' : r.priority === 'medium' ? 'orange' : 'blue'}>{r.priority}</Tag>
                        <Text strong>{r.title || r.category}</Text>
                        <Text style={{ display: 'block', marginTop: 2 }}>{r.recommendation || r.detail}</Text>
                      </div>
                    )) : <Text>{JSON.stringify(b.strategic_recommendations)}</Text>}
                  </Card>
                )}
              </div>
            ),
          }))}
        />
      )}
    </div>
  );

  // --- Course & Section Management ---
  const loadSections = async (courseId) => {
    setSelectedCourse(courseId);
    setSelectedSection(null);
    setRoster([]);
    setTeamMgmt(null);
    try { const res = await getSections(courseId); setSections(res.data || []); } catch { /* empty */ }
  };

  const loadRoster = async (sectionId) => {
    setSelectedSection(sectionId);
    try {
      const [rosterRes, teamRes, gamesRes] = await Promise.all([
        getRoster(sectionId),
        getTeamManagement(sectionId).catch(() => ({ data: null })),
        getGames({ section_id: sectionId }).catch(() => ({ data: { games: [] } })),
      ]);
      setRoster(rosterRes.data || []);
      setTeamMgmt(teamRes.data);

      // Auto-load existing game for this section
      const sectionGames = gamesRes.data?.games || [];
      if (sectionGames.length > 0) {
        const game = sectionGames[0]; // most recent
        setGameId(game.game_id);
        setGameStatus(game.status);
        setCreateGameName(game.game_name);

        // Load teams and round schedule for this game
        try {
          const [teamsRes, schedRes] = await Promise.all([
            getGameTeams(game.game_id),
            getRoundSchedule(game.game_id).catch(() => ({ data: null })),
          ]);
          setCreatedGameTeams(teamsRes.data?.teams || []);
          setRoundSchedule(schedRes.data);
          setRoundScheduleEdits({});
        } catch {
          setCreatedGameTeams([]);
        }

        // Try loading full dashboard (works for active games)
        if (game.status === 'active' || game.status === 'paused') {
          try {
            const dashRes = await getInstructorDashboard(game.game_id);
            setDashboard(dashRes.data);
          } catch { /* setup games won't have dashboard data */ }
        }
      } else {
        // No game for this section — reset game state
        setGameId(null);
        setGameStatus('setup');
        setCreatedGameTeams([]);
        setRoundSchedule(null);
        setDashboard(null);
      }
    } catch (err) { console.error('loadRoster failed:', err); }
    // Also load scenarios if not already loaded
    if (scenarios.length === 0) loadScenarios();
  };

  const selectedCourseObj = courses.find(c => c.course_id === selectedCourse);
  const selectedSectionObj = sections.find(s => s.section_id === selectedSection);

  const courseRosterTab = (
    <div>
      {/* ── Step 1: Courses ── */}
      <Card title={t('instructor.my_courses')} style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, padding: 12, background: '#FAFAFA', borderRadius: 6 }}>
          <Text strong style={{ whiteSpace: 'nowrap' }}>{t('instructor.new_course')}:</Text>
          <Input placeholder={t('instructor.course_code_placeholder')} value={newCourseCode}
            onChange={e => setNewCourseCode(e.target.value)} style={{ width: 160 }} />
          <Input placeholder={t('instructor.course_name_placeholder')} value={newCourseName}
            onChange={e => setNewCourseName(e.target.value)} style={{ width: 240 }} />
          <Button type="primary" disabled={!newCourseName} onClick={async () => {
            try {
              await createCourse({ course_code: newCourseCode, course_name: newCourseName, is_active: true });
              setNewCourseCode(''); setNewCourseName('');
              loadCourses();
              message.success('Course created');
            } catch { message.error('Failed to create course'); }
          }}>{t('instructor.create')}</Button>
        </div>
        {courses.length === 0 ? (
          <Empty description={t('instructor.no_courses')} />
        ) : (
          <Row gutter={[12, 12]}>
            {courses.map(c => (
              <Col xs={24} sm={12} md={8} lg={6} key={c.course_id}>
                <Card
                  size="small" hoverable
                  onClick={() => loadSections(c.course_id)}
                  style={{
                    borderColor: selectedCourse === c.course_id ? '#1E40AF' : undefined,
                    borderWidth: selectedCourse === c.course_id ? 2 : 1,
                    background: selectedCourse === c.course_id ? '#EFF6FF' : undefined,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <Text strong>{c.course_code || '—'}</Text>
                      <Text style={{ display: 'block', fontSize: 13 }}>{c.course_name}</Text>
                    </div>
                    <Popconfirm title={t('instructor.delete_course_confirm')} onConfirm={async (e) => {
                      e?.stopPropagation();
                      await deleteCourse(c.course_id);
                      if (selectedCourse === c.course_id) { setSelectedCourse(null); setSections([]); setSelectedSection(null); }
                      loadCourses();
                    }}>
                      <Button type="text" size="small" danger onClick={e => e.stopPropagation()}>{t('instructor.delete')}</Button>
                    </Popconfirm>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Card>

      {/* ── Step 2: Sections (visible after course selected) ── */}
      {selectedCourse && (
        <Card
          title={`${t('instructor.sections')} — ${selectedCourseObj?.course_code || ''} ${selectedCourseObj?.course_name || ''}`}
          style={{ marginBottom: 16 }}
        >
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, padding: 12, background: '#FAFAFA', borderRadius: 6 }}>
            <Text strong style={{ whiteSpace: 'nowrap' }}>{t('instructor.new_section')}:</Text>
            <Input placeholder={t('instructor.section_code')} value={newSectionCode}
              onChange={e => setNewSectionCode(e.target.value)} style={{ width: 120 }} />
            <Input placeholder={t('instructor.section_name')} value={newSectionName}
              onChange={e => setNewSectionName(e.target.value)} style={{ width: 200 }} />
            <Button type="primary" disabled={!newSectionName} onClick={async () => {
              try {
                await createSection({ course: selectedCourse, section_code: newSectionCode, section_name: newSectionName, is_active: true });
                setNewSectionCode(''); setNewSectionName('');
                loadSections(selectedCourse);
                message.success('Section created');
              } catch { message.error('Failed to create section'); }
            }}>{t('instructor.create')}</Button>
          </div>
          {sections.length === 0 ? (
            <Empty description={t('instructor.no_sections')} />
          ) : (
            <Row gutter={[12, 12]}>
              {sections.map(s => (
                <Col xs={24} sm={12} md={8} lg={6} key={s.section_id}>
                  <Card
                    size="small" hoverable
                    onClick={() => loadRoster(s.section_id)}
                    style={{
                      borderColor: selectedSection === s.section_id ? '#1E40AF' : undefined,
                      borderWidth: selectedSection === s.section_id ? 2 : 1,
                      background: selectedSection === s.section_id ? '#EFF6FF' : undefined,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <Text strong>{s.section_code || '—'}</Text>
                        <Text style={{ display: 'block', fontSize: 13 }}>{s.section_name}</Text>
                      </div>
                      <Popconfirm title={t('instructor.delete_section_confirm')} onConfirm={async (e) => {
                        e?.stopPropagation();
                        await deleteSection(s.section_id);
                        if (selectedSection === s.section_id) { setSelectedSection(null); setRoster([]); }
                        loadSections(selectedCourse);
                      }}>
                        <Button type="text" size="small" danger onClick={e => e.stopPropagation()}>{t('instructor.delete')}</Button>
                      </Popconfirm>
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </Card>
      )}

      {/* ── Step 3: Section Management (visible after section selected) ── */}
      {selectedSection && (
        <div>
          <Typography.Title level={5} style={{ color: '#1E40AF', marginBottom: 16 }}>
            {t('instructor.managing')}: {selectedCourseObj?.course_code} — {selectedSectionObj?.section_name}
          </Typography.Title>

          {/* ── Game Status Banner (always visible at top when game exists) ── */}
          {gameId && (
            <Card size="small" style={{ marginBottom: 16, borderLeft: `4px solid ${
              gameStatus === 'active' ? '#52c41a' : gameStatus === 'paused' ? '#faad14' : '#1890ff'
            }` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text strong style={{ fontSize: 15 }}>{createGameName || 'Game'}</Text>
                  <Tag color={gameStatus === 'active' ? 'green' : gameStatus === 'paused' ? 'orange' : gameStatus === 'archived' ? 'default' : 'blue'}
                    style={{ marginLeft: 8 }}>{gameStatus}</Tag>
                  <Text type="secondary" style={{ marginLeft: 8 }}>
                    {createdGameTeams.length} teams &middot; {roster.filter(r => r.team_id && createdGameTeams.some(t => t.team_id === r.team_id)).length}/{roster.length} students assigned
                  </Text>
                </div>
                <Space>
                  {gameStatus === 'setup' && (
                    <Popconfirm
                      title={t('instructor.activate_game_question')}
                      description={t('instructor.activate_game_desc')}
                      onConfirm={async () => {
                        setActivatingGame(true);
                        try {
                          const res = await activateGame(gameId);
                          setGameStatus(res.data.status);
                          message.success('Game activated! Round 1 is now open.');
                          loadRoundScheduleData(gameId);
                        } catch (err) {
                          message.error(err.response?.data?.error || 'Failed to activate');
                        }
                        setActivatingGame(false);
                      }}
                    >
                      <Button type="primary" icon={<RocketOutlined />} loading={activatingGame}>
                        {t('instructor.activate_game')}
                      </Button>
                    </Popconfirm>
                  )}
                  {gameStatus === 'active' && (
                    <Button onClick={async () => {
                      try {
                        const res = await pauseGame(gameId);
                        setGameStatus(res.data.status);
                        message.info('Game paused');
                      } catch (err) { message.error(err.response?.data?.error || 'Failed to pause'); }
                    }}>{t('instructor.pause_game')}</Button>
                  )}
                  {gameStatus === 'paused' && (
                    <Button type="primary" onClick={async () => {
                      try {
                        const res = await resumeGame(gameId);
                        setGameStatus(res.data.status);
                        message.success('Game resumed');
                      } catch (err) { message.error(err.response?.data?.error || 'Failed to resume'); }
                    }}>{t('instructor.resume_game')}</Button>
                  )}
                  {(gameStatus === 'active' || gameStatus === 'paused') && (
                    <Popconfirm
                      title={t('instructor.reset_game_question')}
                      description={t('instructor.reset_game_desc')}
                      onConfirm={async () => {
                        try {
                          const res = await resetGame(gameId);
                          setGameStatus(res.data.status);
                          message.success('Game reset to setup');
                          loadRoundScheduleData(gameId);
                        } catch (err) { message.error(err.response?.data?.error || 'Failed to reset'); }
                      }}
                    >
                      <Button danger>{t('instructor.reset_to_setup')}</Button>
                    </Popconfirm>
                  )}
                </Space>
              </div>
            </Card>
          )}

          {/* ── 3b: Scenario & Game Configuration (FIRST when no game exists) ── */}
          {!gameId && (
          <Card
            title={<span style={{ color: '#D97706' }}>{t('instructor.step1_create_game')}</span>}
            style={{ marginBottom: 16, borderLeft: '4px solid #D97706' }}
          >
              <>
                <Row gutter={[16, 16]}>
                  <Col xs={24} md={8}>
                    <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('instructor.scenario')}</Text>
                    <Select
                      value={selectedScenario?.id}
                      onChange={(val) => {
                        const s = scenarios.find(sc => sc.id === val);
                        if (s) handleSelectScenario(s);
                      }}
                      placeholder={t('instructor.select_scenario')}
                      style={{ width: '100%' }}
                      loading={scenariosLoading}
                      options={scenarios.map(s => ({
                        value: s.id,
                        label: `${s.name} — ${s.industry_label}`,
                      }))}
                    />
                    {selectedScenario && (
                      <div style={{ marginTop: 8, padding: 8, background: '#F8FAFC', borderRadius: 4, fontSize: 12 }}>
                        <Text type="secondary">{selectedScenario.description?.substring(0, 200)}</Text>
                        <div style={{ marginTop: 4 }}>
                          <Tag>{selectedScenario.market_count} {t('instructor.markets')}</Tag>
                          <Tag>{selectedScenario.num_rounds} {t('instructor.rounds')}</Tag>
                          <Tag>{t('instructor.starting_cash')}: ${(selectedScenario.starting_cash / 1e6).toFixed(0)}M</Tag>
                        </div>
                      </div>
                    )}
                  </Col>
                  <Col xs={24} md={8}>
                    <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('instructor.game_name')}</Text>
                    <Input value={createGameName} onChange={e => setCreateGameName(e.target.value)}
                      placeholder="e.g. Spring 2026 Simulation" />
                  </Col>
                  <Col xs={24} md={8}>
                    <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('instructor.number_of_teams')}</Text>
                    <InputNumber min={2} max={16} value={createNumTeams}
                      onChange={v => setCreateNumTeams(v)} style={{ width: '100%' }} />
                  </Col>
                </Row>

                <div style={{ marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
                  <Button
                    type="primary" loading={createLoading}
                    disabled={!selectedScenario}
                    onClick={handleCreateGame}
                  >
                    {t('instructor.create_game_teams')}
                  </Button>
                  {!selectedScenario && <Text type="secondary" style={{ marginLeft: 12 }}>{t('instructor.select_scenario_first')}</Text>}
                </div>
              </>
          </Card>
          )}

          {/* ── 3a: Roster ── */}
          <Card title={`${t('instructor.student_roster')} (${roster.length} ${t('instructor.enrolled')})`} style={{ marginBottom: 16 }}>
            {/* Add single student form */}
            <div style={{ padding: 12, background: '#F8FAFC', borderRadius: 6, marginBottom: 16 }}>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>{t('instructor.add_student')}</Text>
              <Row gutter={8} align="middle">
                <Col flex="auto">
                  <Input placeholder={t('instructor.display_name')} value={addStudentName}
                    onChange={e => setAddStudentName(e.target.value)} size="small" />
                </Col>
                <Col flex="auto">
                  <Input placeholder={t('instructor.email')} value={addStudentEmail}
                    onChange={e => setAddStudentEmail(e.target.value)} size="small" />
                </Col>
                <Col flex="120px">
                  <Input placeholder={t('instructor.student_id')} value={addStudentId}
                    onChange={e => setAddStudentId(e.target.value)} size="small" />
                </Col>
                <Col>
                  <Button type="primary" size="small" disabled={!addStudentName.trim() && !addStudentEmail.trim()}
                    onClick={async () => {
                      try {
                        await addStudent(selectedSection, {
                          display_name: addStudentName.trim(),
                          email: addStudentEmail.trim(),
                          student_id: addStudentId.trim(),
                        });
                        message.success('Student added');
                        setAddStudentName(''); setAddStudentEmail(''); setAddStudentId('');
                        loadRoster(selectedSection);
                      } catch (err) { message.error(err.response?.data?.error || 'Failed to add student'); }
                    }}>{t('instructor.add')}</Button>
                </Col>
              </Row>
            </div>

            {/* Bulk upload */}
            <Collapse size="small" style={{ marginBottom: 16 }}
              items={[{
                key: 'bulk',
                label: t('instructor.bulk_upload_csv'),
                children: (
                  <Row gutter={16}>
                    <Col xs={24} md={12}>
                      <Text type="secondary" style={{ display: 'block', marginBottom: 8, fontSize: 12 }}>
                        CSV format: student_id, display_name, email (header row required)
                      </Text>
                      <input
                        type="file" accept=".csv,.txt"
                        style={{ marginBottom: 12 }}
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          const text = await file.text();
                          try {
                            const res = await uploadRoster(selectedSection, text);
                            message.success(`Created ${res.data?.created || 0} students from ${file.name}`);
                            loadRoster(selectedSection);
                          } catch (err) { message.error(err.response?.data?.error || 'Upload failed'); }
                          e.target.value = '';
                        }}
                      />
                    </Col>
                    <Col xs={24} md={12}>
                      <TextArea rows={3}
                        placeholder={"student_id,display_name,email\n12345,John Doe,john@university.edu"}
                        value={csvText} onChange={e => setCsvText(e.target.value)}
                      />
                      <Button type="primary" size="small" style={{ marginTop: 8 }} disabled={!csvText.trim()} onClick={async () => {
                        try {
                          const res = await uploadRoster(selectedSection, csvText);
                          message.success(`Created ${res.data?.created || 0} students`);
                          setCsvText('');
                          loadRoster(selectedSection);
                        } catch (err) { message.error(err.response?.data?.error || 'Upload failed'); }
                      }}>{t('instructor.upload_pasted_text')}</Button>
                    </Col>
                  </Row>
                ),
              }]}
            />

            {/* Student table with edit/delete */}
            {roster.length === 0 ? (
              <Empty description={t('instructor.no_students')} />
            ) : (
              <Table dataSource={roster} rowKey="enrollment_id" size="small"
                pagination={roster.length > 15 ? { pageSize: 15, size: 'small' } : false}
                tableLayout="fixed"
                columns={[
                  {
                    title: t('instructor.name'), dataIndex: 'display_name', width: '25%', ellipsis: true,
                    render: (val, r) => editingEnrollment === r.enrollment_id
                      ? <Input size="small" value={editStudentName} onChange={e => setEditStudentName(e.target.value)} />
                      : val || <Text type="secondary">—</Text>,
                  },
                  {
                    title: t('instructor.email'), dataIndex: 'email', width: '25%', ellipsis: true,
                    render: (val, r) => editingEnrollment === r.enrollment_id
                      ? <Input size="small" value={editStudentEmail} onChange={e => setEditStudentEmail(e.target.value)} />
                      : <Text style={{ fontSize: 12 }}>{val || '—'}</Text>,
                  },
                  {
                    title: t('instructor.id'), dataIndex: 'student_id', width: 80,
                    render: (val, r) => editingEnrollment === r.enrollment_id
                      ? <Input size="small" value={editStudentId} onChange={e => setEditStudentId(e.target.value)} />
                      : <Text style={{ fontSize: 12, whiteSpace: 'nowrap' }}>{val || '—'}</Text>,
                  },
                  {
                    title: t('instructor.team'), dataIndex: 'team_name', width: 100, ellipsis: true,
                    render: v => v || <Tag color="orange" style={{ fontSize: 11 }}>{t('instructor.unassigned')}</Tag>,
                  },
                  {
                    title: '', key: 'actions', width: 90,
                    render: (_, r) => editingEnrollment === r.enrollment_id ? (
                      <Space size={0}>
                        <Button type="link" size="small" style={{ padding: '0 4px' }} onClick={async () => {
                          try {
                            await updateEnrollment(r.enrollment_id, {
                              display_name: editStudentName,
                              email: editStudentEmail,
                              student_id: editStudentId,
                            });
                            message.success('Student updated');
                            setEditingEnrollment(null);
                            loadRoster(selectedSection);
                          } catch (err) { message.error('Failed to update'); }
                        }}>{t('instructor.save')}</Button>
                        <Button type="text" size="small" style={{ padding: '0 4px' }} onClick={() => setEditingEnrollment(null)}>✕</Button>
                      </Space>
                    ) : (
                      <Space size={0}>
                        <Button type="text" size="small" style={{ padding: '0 4px', fontSize: 12 }} onClick={() => {
                          setEditingEnrollment(r.enrollment_id);
                          setEditStudentName(r.display_name || '');
                          setEditStudentEmail(r.email || '');
                          setEditStudentId(r.student_id || '');
                        }}>{t('instructor.edit')}</Button>
                        <Popconfirm title={t('instructor.remove_student_confirm')} onConfirm={() => {
                          removeEnrollment(r.enrollment_id).then(() => loadRoster(selectedSection));
                        }}>
                          <Button type="text" size="small" danger style={{ padding: '0 4px', fontSize: 12 }}>{t('instructor.del')}</Button>
                        </Popconfirm>
                      </Space>
                    ),
                  },
                ]}
              />
            )}
          </Card>

          {/* ── 3b: Game Configuration summary (only when game exists — creation form is above) ── */}
          {gameId && (
          <Card
            title={<span>{t('instructor.step1_config')} <Tag color="green">{t('instructor.complete')}</Tag></span>}
            size="small" style={{ marginBottom: 16 }}
          >
            <Alert type="success" showIcon
              message={`Game: ${createGameName || selectedScenario?.name || 'Game'}`}
              description={
                <span>
                  {createdGameTeams.length} teams &middot; Status: <Tag color={
                    gameStatus === 'active' ? 'green' : gameStatus === 'paused' ? 'orange' : gameStatus === 'archived' ? 'default' : 'blue'
                  }>{gameStatus}</Tag>
                </span>
              }
            />
          </Card>
          )}

          {/* ── 3c: Assign Students to Teams (only after game created) ── */}
          {createdGameTeams.length > 0 && (
            <Card
              title={t('instructor.step2_assign_students')}
              style={{ marginBottom: 16 }}
            >
              {/* Team summary */}
              <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
                {createdGameTeams.map(tm => {
                  const assignedStudents = roster.filter(r => r.team_id === tm.team_id);
                  return (
                    <Col xs={24} sm={12} md={8} lg={6} key={tm.team_id}>
                      <Card size="small" title={tm.team_name}
                        style={{ borderLeft: `3px solid ${assignedStudents.length > 0 ? '#52c41a' : '#faad14'}` }}>
                        {assignedStudents.length === 0
                          ? <Text type="secondary">{t('instructor.no_students_assigned')}</Text>
                          : assignedStudents.map((s, i) => (
                              <Tag key={i} style={{ marginBottom: 4 }}>{s.display_name || s.username || `User ${s.user_id}`}</Tag>
                            ))
                        }
                        <div style={{ marginTop: 4 }}>
                          <Text type="secondary" style={{ fontSize: 11 }}>{assignedStudents.length} student(s)</Text>
                        </div>
                      </Card>
                    </Col>
                  );
                })}
              </Row>

              {/* Team picker: select team, pick students, save */}
              {(() => {
                // Only consider students assigned if their team_id matches a game team
                const gameTeamIdSet = new Set(createdGameTeams.map(tm => tm.team_id));
                const isAssignedToGame = (r) => r.team_id && gameTeamIdSet.has(r.team_id);
                const unassigned = roster.filter(r => !isAssignedToGame(r));
                const assignedCount = roster.filter(r => isAssignedToGame(r)).length;
                return (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <Text strong>
                        {t('instructor.assign_students')} ({assignedCount} / {roster.length} {t('instructor.assigned')})
                      </Text>
                      {unassigned.length > 0 && (
                        <Tag color="orange">{unassigned.length} {t('instructor.unassigned')}</Tag>
                      )}
                    </div>

                    <Row gutter={16}>
                      {/* Left: Team picker */}
                      <Col xs={24} md={10}>
                        <Card size="small" title={t('instructor.select_team_pick_students')} style={{ minHeight: 300 }}>
                          <Select
                            value={pickerTeam || undefined}
                            onChange={v => setPickerTeam(v)}
                            placeholder={t('instructor.select_team')}
                            style={{ width: '100%', marginBottom: 12 }}
                            options={createdGameTeams.map(tm => {
                              const count = roster.filter(r => r.team_id === tm.team_id).length;
                              return {
                                value: tm.team_id,
                                label: `${tm.team_name} (${tm.home_market || '—'}) — ${count} student(s)`,
                              };
                            })}
                          />
                          {pickerTeam && (
                            <div>
                              <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                                {t('instructor.pick_from_unassigned')}:
                              </Text>
                              <Select
                                mode="multiple"
                                placeholder={t('instructor.search_select_students')}
                                style={{ width: '100%' }}
                                value={[]}
                                onChange={async (userIds) => {
                                  if (userIds.length === 0) return;
                                  try {
                                    const assignments = userIds.map(uid => ({ user_id: uid, team_id: pickerTeam }));
                                    await assignStudents(assignments);
                                    message.success(`${userIds.length} student(s) assigned`);
                                    loadRoster(selectedSection);
                                  } catch { message.error('Failed to assign students'); }
                                }}
                                filterOption={(input, option) =>
                                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                                }
                                options={unassigned.map(r => ({
                                  value: r.user_id,
                                  label: r.display_name || r.username || `User ${r.user_id}`,
                                }))}
                              />
                              {/* Current members of selected team */}
                              <div style={{ marginTop: 12 }}>
                                <Text strong style={{ fontSize: 12 }}>{t('instructor.current_members')}:</Text>
                                {roster.filter(r => r.team_id === pickerTeam).length === 0
                                  ? <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>{t('instructor.none_yet')}</Text>
                                  : roster.filter(r => r.team_id === pickerTeam).map(r => (
                                      <div key={r.enrollment_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 0' }}>
                                        <Text style={{ fontSize: 12 }}>{r.display_name || r.username}</Text>
                                        <Button type="text" size="small" danger onClick={async () => {
                                          try {
                                            await assignStudents([{ user_id: r.user_id, team_id: null }]);
                                            loadRoster(selectedSection);
                                          } catch { message.error('Failed to unassign'); }
                                        }}>{t('instructor.remove')}</Button>
                                      </div>
                                    ))
                                }
                              </div>
                            </div>
                          )}
                        </Card>
                      </Col>

                      {/* Right: Unassigned pool */}
                      <Col xs={24} md={14}>
                        <Card size="small" title={`${t('instructor.unassigned_students')} (${unassigned.length})`} style={{ minHeight: 300 }}>
                          {unassigned.length === 0 ? (
                            <Alert type="success" message={t('instructor.all_students_assigned')} />
                          ) : (
                            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                              {unassigned.map(r => (
                                <div key={r.enrollment_id} style={{
                                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                  padding: '4px 8px', borderBottom: '1px solid #f5f5f5',
                                }}>
                                  <div>
                                    <Text style={{ fontSize: 13 }}>{r.display_name || r.username || `User ${r.user_id}`}</Text>
                                    {r.email && <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>{r.email}</Text>}
                                  </div>
                                  {pickerTeam && (
                                    <Button type="link" size="small" onClick={async () => {
                                      try {
                                        await assignStudents([{ user_id: r.user_id, team_id: pickerTeam }]);
                                        loadRoster(selectedSection);
                                      } catch { message.error('Failed to assign'); }
                                    }}>
                                      → {createdGameTeams.find(t => t.team_id === pickerTeam)?.team_name}
                                    </Button>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </Card>
                      </Col>
                    </Row>
                  </div>
                );
              })()}
            </Card>
          )}

          {/* ── Pointer to Game Control tab ── */}
          {gameId && (
            <Alert type="info" showIcon style={{ marginBottom: 16 }}
              message={t('instructor.game_control_tab_hint')}
            />
          )}
        </div>
      )}
    </div>
  );

  // ============ TAB ITEMS ============
  // Always-available tabs come first; game-specific tabs only when a game is active

  const tabItems = [
    // --- Always available ---
    { key: 'courses', label: t('instructor.courses_sections'), children: courseRosterTab },
    // --- Game Control: visible once a game exists (any status) ---
    ...(gameId ? [
      { key: 'control', label: t('instructor.game_control'), children: gameControlTab },
    ] : []),
    { key: 'grading', label: t('instructor.grading_export'), children: gradingTab },
    // --- Game-specific (only when game is active/paused with dashboard data) ---
    ...(hasGame ? [
      { key: 'teams', label: t('instructor.team_overview'), children: teamOverviewTab },
      { key: 'supply_chain', label: t('instructor.supply_chain', 'Supply Chain'), children: <InstructorSCPanel gameId={gameId} /> },
      { key: 'events', label: t('instructor.event_manager'), children: eventManagerTab },
      { key: 'briefings', label: t('instructor.briefings'), children: briefingsTab },
      { key: 'research', label: t('instructor.research_monitor'), children: researchMonitorTab },
      { key: 'alerts', label: <span>{t('instructor.ai_coach')} {alerts.filter(a => !a.acknowledged).length > 0 && <Badge count={alerts.filter(a => !a.acknowledged).length} size="small" style={{ marginLeft: 4 }} />}</span>, children: aiCoachTab },
    ] : []),
  ];

  return (
    <div>
      {instructorHeader}
      <Tabs className="ds-colored-tabs" items={tabItems} defaultActiveKey="courses" onTabClick={(key) => {
        if (key === 'grading') loadGrading();
        if (key === 'control' && gameId && roundSchedule === null) loadRoundScheduleData(gameId);
      }} />

      {/* Game-specific modals (only render when game is active) */}
      {hasGame && <>
      {/* Advance Round Modal */}
      <Modal title={t('instructor.advance_round')} open={advanceModalOpen} onOk={handleAdvance} onCancel={() => setAdvanceModalOpen(false)} confirmLoading={actionLoading}>
        <Text>
          {rs.teams_pending > 0
            ? t('instructor.advance_pending', { count: rs.teams_pending })
            : t('instructor.advance_ready')}
        </Text>
      </Modal>

      {/* Extend Deadline Modal */}
      <Modal title={t('instructor.extend_deadline')} open={extendModalOpen} onOk={handleExtend} onCancel={() => setExtendModalOpen(false)} confirmLoading={actionLoading}>
        <Text>{t('instructor.extend_deadline_by')}:</Text>
        <InputNumber min={1} max={168} value={extendHours} onChange={setExtendHours} addonAfter="hours" style={{ width: '100%', marginTop: 8 }} />
      </Modal>

      {/* Inject Event Modal — now with dropdowns */}
      <Modal title={t('instructor.inject_event')} open={eventModalOpen} onOk={handleInjectEvent} onCancel={() => { setEventModalOpen(false); setSelectedEventTemplate(null); setSelectedMarket(null); }} confirmLoading={actionLoading}
        okButtonProps={{ disabled: !selectedEventTemplate }}>
        <div style={{ marginBottom: 12 }}>
          <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('instructor.event_template')}:</Text>
          <Select
            value={selectedEventTemplate} onChange={setSelectedEventTemplate}
            placeholder={t('instructor.select_event_template')} style={{ width: '100%' }}
            showSearch optionFilterProp="label"
            options={eventTemplates.map(t => ({
              value: t.id,
              label: `${t.name} (${t.severity})`,
              title: t.description,
            }))}
          />
        </div>
        <div>
          <Text strong style={{ display: 'block', marginBottom: 4 }}>{t('instructor.target_market')}:</Text>
          <Select
            value={selectedMarket} onChange={setSelectedMarket}
            placeholder={t('instructor.all_markets')} style={{ width: '100%' }} allowClear
            options={marketOptions.map(m => ({ value: m.id, label: m.name }))}
          />
        </div>
        {selectedEventTemplate && (
          <Alert type="info" style={{ marginTop: 12 }}
            message={eventTemplates.find(t => t.id === selectedEventTemplate)?.description || ''}
          />
        )}
      </Modal>

      {/* Team Decisions Drill-Down Modal */}
      <Modal title={`${t('instructor.team_decisions')} — ${teams.find(tm => tm.team_id === drillTeam)?.team_name || ''}`}
        open={!!drillTeam} onCancel={() => { setDrillTeam(null); setDrillData(null); }}
        width={800} footer={null}>
        <div style={{ marginBottom: 12 }}>
          <Text strong>{t('instructor.round')}: </Text>
          <Select value={drillRound} onChange={r => openDrill(drillTeam, r)} style={{ width: 120 }}
            options={Array.from({ length: dashboard?.current_round || 0 }, (_, i) => ({ value: i + 1, label: `${t('instructor.round')} ${i + 1}` }))}
          />
        </div>
        {drillLoading ? <LoadingSpinner /> : !drillData ? <Empty description={t('instructor.no_submission_data')} /> : (
          <div>
            <Tag color={drillData.status === 'locked' ? 'green' : 'orange'}>{drillData.status}</Tag>
            {drillData.locked_at && <Text type="secondary" style={{ marginLeft: 8 }}>{t('instructor.locked')}: {new Date(drillData.locked_at).toLocaleString()}</Text>}

            {drillData.budget && (
              <Descriptions title={t('instructor.budget_allocation')} size="small" bordered column={{ xs: 1, sm: 2, md: 3 }} style={{ marginTop: 12 }}>
                <Descriptions.Item label={t('instructor.rd')}>{fmt(drillData.budget.rd_budget)}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.marketing')}>{fmt(drillData.budget.marketing_budget)}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.strategy')}>{fmt(drillData.budget.strategy_budget)}</Descriptions.Item>
              </Descriptions>
            )}

            {drillData.rd?.investments?.length > 0 && (
              <Card size="small" title={t('instructor.rd_investments')} style={{ marginTop: 12 }}>
                <Table dataSource={drillData.rd.investments} rowKey={(_, i) => i} size="small" pagination={false}
                  columns={[
                    { title: t('instructor.feature'), dataIndex: 'feature' },
                    { title: t('instructor.amount'), dataIndex: 'amount', render: fmt },
                    { title: t('instructor.method'), dataIndex: 'method' },
                  ]}
                />
              </Card>
            )}

            {drillData.marketing?.length > 0 && (
              <Card size="small" title={t('instructor.marketing_decisions')} style={{ marginTop: 12 }}>
                <Table dataSource={drillData.marketing} rowKey={(_, i) => i} size="small" pagination={false}
                  columns={[
                    { title: t('instructor.product'), dataIndex: 'product' },
                    { title: t('instructor.market'), dataIndex: 'market' },
                    { title: t('instructor.price'), dataIndex: 'retail_price', render: v => `$${v}` },
                    { title: t('instructor.volume'), dataIndex: 'production_volume', render: v => v?.toLocaleString() },
                    { title: t('instructor.promo'), dataIndex: 'promotion_budget', render: fmt },
                    { title: t('instructor.reps'), dataIndex: 'sales_team_count' },
                  ]}
                />
              </Card>
            )}

            {drillData.financing && (
              <Descriptions title={t('instructor.financing')} size="small" bordered column={4} style={{ marginTop: 12 }}>
                <Descriptions.Item label={t('instructor.new_debt')}>{fmt(drillData.financing.new_debt)}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.repayment')}>{fmt(drillData.financing.debt_repayment)}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.new_equity')}>{fmt(drillData.financing.new_equity)}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.dividend_per_share')}>${drillData.financing.dividend_per_share}</Descriptions.Item>
              </Descriptions>
            )}

            {drillData.esg && (
              <Descriptions title={t('instructor.esg')} size="small" bordered column={2} style={{ marginTop: 12 }}>
                <Descriptions.Item label={t('instructor.environmental')}>{fmt(drillData.esg.environmental_investment)}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.social')}>{fmt(drillData.esg.social_investment)}</Descriptions.Item>
              </Descriptions>
            )}

            {drillData.talent && (
              <Descriptions title={t('instructor.talent')} size="small" bordered column={{ xs: 1, sm: 2, md: 3 }} style={{ marginTop: 12 }}>
                <Descriptions.Item label={t('instructor.rd_hc')}>{drillData.talent.rd_headcount}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.commercial_hc')}>{drillData.talent.commercial_headcount}</Descriptions.Item>
                <Descriptions.Item label={t('instructor.operations_hc')}>{drillData.talent.operations_headcount}</Descriptions.Item>
              </Descriptions>
            )}
          </div>
        )}
      </Modal>
      </>}
    </div>
  );
};

export default InstructorDashboard;
