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

const PATTERN_LABELS = {
  consistent: 'Consistent Executor',
  reactive: 'Reactive Adjuster',
  aggressive: 'Aggressive Expander',
  conservative: 'Conservative Optimizer',
  erratic: 'Erratic',
};

const TEAM_COLORS = [
  '#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16',
];

const ReasoningTeamTable = ({ gameId, round }) => {
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
    return <Empty description="No reasoning analysis data available" />;
  }

  const columns = [
    { title: 'Team', dataIndex: 'team_name', key: 'team_name', sorter: (a, b) => a.team_name.localeCompare(b.team_name) },
    {
      title: 'Deterministic', dataIndex: 'reasoning_score_deterministic', key: 'det',
      sorter: (a, b) => a.reasoning_score_deterministic - b.reasoning_score_deterministic,
      render: v => <Text strong>{v.toFixed(1)}</Text>,
    },
    {
      title: 'Coherence', dataIndex: 'coherence_ext_score', key: 'coh',
      sorter: (a, b) => a.coherence_ext_score - b.coherence_ext_score,
      render: v => v.toFixed(1),
    },
    {
      title: 'Responsiveness', dataIndex: 'responsiveness_score', key: 'resp',
      sorter: (a, b) => a.responsiveness_score - b.responsiveness_score,
      render: v => v.toFixed(1),
    },
    {
      title: 'Trajectory', dataIndex: 'trajectory_score', key: 'traj',
      sorter: (a, b) => a.trajectory_score - b.trajectory_score,
      render: v => v.toFixed(1),
    },
    {
      title: 'Justification', dataIndex: 'justification_score', key: 'just',
      render: v => v != null ? v.toFixed(1) : <Text type="secondary">-</Text>,
    },
    {
      title: 'Pattern', dataIndex: 'trajectory_pattern', key: 'pattern',
      render: v => PATTERN_LABELS[v] || v,
    },
    {
      title: 'Band', dataIndex: 'overall_band', key: 'band',
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
      title={() => <Text type="secondary">Round {data.round_number}</Text>}
    />
  );
};

const ReasoningComparison = ({ gameId, round }) => {
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
    return <Empty description="No comparison data" />;
  }

  const radarData = ['coherence_ext', 'responsiveness', 'trajectory'].map(dim => {
    const point = { dimension: dim.replace('_', ' ') };
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
    return <Empty description="No aggregate data" />;
  }

  const columns = [
    {
      title: 'Rank', key: 'rank',
      render: (_, __, idx) => idx + 1,
    },
    { title: 'Team', dataIndex: 'team_name', key: 'team_name' },
    {
      title: 'Avg Score', dataIndex: 'aggregate_reasoning_score', key: 'score',
      render: v => <Text strong>{v.toFixed(1)}</Text>,
    },
    { title: 'Rounds', dataIndex: 'rounds_evaluated', key: 'rounds' },
    {
      title: 'Dominant Pattern', dataIndex: 'dominant_pattern', key: 'pattern',
      render: v => PATTERN_LABELS[v] || v,
    },
    {
      title: 'Consistency', dataIndex: 'pattern_consistency', key: 'consistency',
      render: v => `${(v * 100).toFixed(0)}%`,
    },
    {
      title: 'Trend', dataIndex: 'score_trend', key: 'trend',
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
      label: 'Team Scores',
      children: <ReasoningTeamTable gameId={gameId} round={selectedRound} />,
    },
    {
      key: 'comparison',
      label: 'Comparison',
      children: <ReasoningComparison gameId={gameId} round={selectedRound} />,
    },
    {
      key: 'aggregate',
      label: 'Competition Summary',
      children: <ReasoningAggregate gameId={gameId} />,
    },
  ];

  return (
    <Card
      title="Reasoning Analysis"
      extra={
        <Space>
          <Button icon={<DownloadOutlined />} size="small" onClick={handleExport}>
            Export CSV
          </Button>
        </Space>
      }
    >
      <Tabs items={tabItems} size="small" />
    </Card>
  );
};

export default ReasoningAnalysisTab;
