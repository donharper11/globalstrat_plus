import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Card, Table, Tag, Space, Typography,
  Button, Tabs, Empty, Spin, message,
} from 'antd';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip, Legend,
} from 'recharts';
import { DownloadOutlined } from '@ant-design/icons';
import {
  getInstructorReasoningAllTeams,
  getInstructorReasoningComparison,
  getInstructorReasoningAggregate,
  exportReasoningCsv,
} from '../../api/reasoning';

const { Text } = Typography;

const BAND_COLORS = {
  strong: '#52c41a',
  developing: '#faad14',
  needs_attention: '#ff4d4f',
};

// The five behavioural labels an instructor reads beside a team's score.
// They were English constants, so a Chinese console printed them in English
// along with every column header and tab in this panel -- 27 strings in one
// component, none of them in the catalogue. The map now holds keys and the
// wording comes from the catalogue at render, which is also what lets A8 see
// that these keys exist.
const PATTERN_KEYS = {
  consistent: 'instructor.reasoning_pattern_consistent',
  reactive: 'instructor.reasoning_pattern_reactive',
  aggressive: 'instructor.reasoning_pattern_aggressive',
  conservative: 'instructor.reasoning_pattern_conservative',
  erratic: 'instructor.reasoning_pattern_erratic',
};

const patternLabel = (code, t) => (
  PATTERN_KEYS[code] ? t(PATTERN_KEYS[code]) : (code || '—'));

const TEAM_COLORS = [
  '#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16',
];

const ReasoningTeamTable = ({ gameId, round }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = round ? { round } : {};
      const res = await getInstructorReasoningAllTeams(gameId, params);
      setData(res.data);
    } catch (e) {
      console.error('Failed to load reasoning data:', e);
    }
    setLoading(false);
  }, [gameId, round]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <Spin />;
  if (!data || !data.teams || data.teams.length === 0) {
    return <Empty description={t('instructor.reasoning_empty_teams')} />;
  }

  const columns = [
    { title: t('common.team'), dataIndex: 'team_name', key: 'team_name', sorter: (a, b) => a.team_name.localeCompare(b.team_name) },
    {
      title: t('instructor.reasoning_col_deterministic'), dataIndex: 'reasoning_score_deterministic', key: 'det',
      sorter: (a, b) => a.reasoning_score_deterministic - b.reasoning_score_deterministic,
      render: v => <Text strong>{v.toFixed(1)}</Text>,
    },
    {
      title: t('instructor.coherence'), dataIndex: 'coherence_ext_score', key: 'coh',
      sorter: (a, b) => a.coherence_ext_score - b.coherence_ext_score,
      render: v => v.toFixed(1),
    },
    {
      title: t('instructor.reasoning_col_responsiveness'), dataIndex: 'responsiveness_score', key: 'resp',
      sorter: (a, b) => a.responsiveness_score - b.responsiveness_score,
      render: v => v.toFixed(1),
    },
    {
      title: t('instructor.reasoning_col_trajectory'), dataIndex: 'trajectory_score', key: 'traj',
      sorter: (a, b) => a.trajectory_score - b.trajectory_score,
      render: v => v.toFixed(1),
    },
    {
      title: t('instructor.reasoning_col_justification'), dataIndex: 'justification_score', key: 'just',
      render: v => v != null ? v.toFixed(1) : <Text type="secondary">-</Text>,
    },
    {
      title: t('instructor.reasoning_col_pattern'), dataIndex: 'trajectory_pattern', key: 'pattern',
      render: v => patternLabel(v, t),
    },
    {
      title: t('instructor.reasoning_col_band'), dataIndex: 'overall_band', key: 'band',
      render: v => <Tag color={BAND_COLORS[v]}>{v.replace('_', ' ')}</Tag>,
    },
  ];

  return (
    <Table
      dataSource={data.teams}
      columns={columns}
      rowKey="team_id"
      size="small"
      pagination={false}
      title={() => <Text type="secondary">{t('instructor.reasoning_round_label', { round: data.round_number })}</Text>}
    />
  );
};

const ReasoningComparison = ({ gameId, round }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const params = round ? { round } : {};
        const res = await getInstructorReasoningComparison(gameId, params);
        setData(res.data);
      } catch (e) { console.error(e); }
      setLoading(false);
    })();
  }, [gameId, round]);

  if (loading) return <Spin />;
  if (!data || !data.comparison || data.comparison.length === 0) {
    return <Empty description={t('instructor.reasoning_empty_comparison')} />;
  }

  // `dim.replace('_', ' ')` printed the STORAGE KEY on the chart -- a Chinese
  // instructor read "coherence ext" on the comparison radar, which is the
  // F-PL-01 class of string (a database column shown to a user) that the
  // Stage-5 check's A3 forbids in a catalogue sentence and cannot see here,
  // because this one never went through the catalogue. Seen on a zh-CN console
  // in the ten-round pass, on a tab no previous tour had opened.
  const DIMENSION_LABELS = {
    coherence_ext: 'instructor.coherence',
    responsiveness: 'instructor.reasoning_col_responsiveness',
    trajectory: 'instructor.reasoning_col_trajectory',
  };
  const radarData = Object.keys(DIMENSION_LABELS).map(dim => {
    const point = { dimension: t(DIMENSION_LABELS[dim]) };
    data.comparison.forEach(t => {
      point[t.team_name] = t.dimensions[dim] || 0;
    });
    return point;
  });

  return (
    <div style={{ width: '100%', height: 350 }}>
      <ResponsiveContainer>
        <RadarChart data={radarData}>
          <PolarGrid />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          {data.comparison.map((t, i) => (
            <Radar
              key={t.team_id}
              name={t.team_name}
              dataKey={t.team_name}
              stroke={TEAM_COLORS[i % TEAM_COLORS.length]}
              fill={TEAM_COLORS[i % TEAM_COLORS.length]}
              fillOpacity={0.15}
            />
          ))}
          <Legend />
          <Tooltip />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};

const ReasoningAggregate = ({ gameId }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await getInstructorReasoningAggregate(gameId);
        setData(res.data);
      } catch (e) { console.error(e); }
      setLoading(false);
    })();
  }, [gameId]);

  if (loading) return <Spin />;
  if (!data || !data.aggregates || data.aggregates.length === 0) {
    return <Empty description={t('instructor.reasoning_empty_aggregate')} />;
  }

  const columns = [
    {
      title: t('results.rank'), key: 'rank',
      render: (_, __, idx) => idx + 1,
    },
    { title: t('common.team'), dataIndex: 'team_name', key: 'team_name' },
    {
      title: t('instructor.reasoning_col_avg_score'), dataIndex: 'aggregate_reasoning_score', key: 'score',
      render: v => <Text strong>{v.toFixed(1)}</Text>,
    },
    { title: t('instructor.rounds'), dataIndex: 'rounds_evaluated', key: 'rounds' },
    {
      title: t('instructor.reasoning_col_dominant_pattern'), dataIndex: 'dominant_pattern', key: 'pattern',
      render: v => patternLabel(v, t),
    },
    {
      title: t('instructor.reasoning_col_consistency'), dataIndex: 'pattern_consistency', key: 'consistency',
      render: v => `${(v * 100).toFixed(0)}%`,
    },
    {
      title: t('market_research.trend'), dataIndex: 'score_trend', key: 'trend',
      render: v => {
        const colors = { improving: '#52c41a', stable: '#1677ff', declining: '#ff4d4f' };
        return <Tag color={colors[v] || '#999'}>{v}</Tag>;
      },
    },
  ];

  return (
    <Table
      dataSource={data.aggregates}
      columns={columns}
      rowKey="team_id"
      size="small"
      pagination={false}
    />
  );
};

const ReasoningAnalysisTab = ({ gameId }) => {
  const [selectedRound] = useState(null);
  const { t } = useTranslation();

  const handleExport = async () => {
    try {
      const res = await exportReasoningCsv(gameId);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `reasoning_scores_game_${gameId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      message.success('CSV exported');
    } catch (e) {
      message.error(t('instructor.export_failed', 'Export failed'));
    }
  };

  const tabItems = [
    {
      key: 'scores',
      label: t('instructor.reasoning_tab_team_scores'),
      children: <ReasoningTeamTable gameId={gameId} round={selectedRound} />,
    },
    {
      key: 'comparison',
      label: t('instructor.reasoning_tab_comparison'),
      children: <ReasoningComparison gameId={gameId} round={selectedRound} />,
    },
    {
      key: 'aggregate',
      label: t('instructor.reasoning_tab_competition'),
      children: <ReasoningAggregate gameId={gameId} />,
    },
  ];

  return (
    <Card
      title={t('instructor.reasoning_analysis')}
      extra={
        <Space>
          <Button icon={<DownloadOutlined />} size="small" onClick={handleExport}>
            {t('results_page.export_csv')}
          </Button>
        </Space>
      }
    >
      <Tabs items={tabItems} size="small" />
    </Card>
  );
};

export default ReasoningAnalysisTab;
