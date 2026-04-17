import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Card, Tabs, Typography, Select, Input, Button, InputNumber, Slider,
  Row, Col, Tag, message, Table, Progress, Space, Alert, Descriptions,
} from 'antd';
import client from '../api/client';
import { getResearchReport } from '../api/decisions';
import { useGame } from '../contexts/GameContext';
import LoadingSpinner from '../components/LoadingSpinner';
import { PageHeader, PanelCard } from '../components/design-system';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FORCE_KEYS = ['new_entrants', 'supplier_power', 'buyer_power', 'substitutes', 'rivalry'];
const FORCE_LABEL_KEYS = {
  new_entrants: 'strategy_tools.force_new_entrants',
  supplier_power: 'strategy_tools.force_supplier_power',
  buyer_power: 'strategy_tools.force_buyer_power',
  substitutes: 'strategy_tools.force_substitutes',
  rivalry: 'strategy_tools.force_rivalry',
};

const PESTLE_KEYS = ['political', 'economic', 'social', 'technological', 'legal', 'environmental'];
const PESTLE_LABEL_KEYS = {
  political: 'strategy_tools.pestle_political',
  economic: 'strategy_tools.pestle_economic',
  social: 'strategy_tools.pestle_social',
  technological: 'strategy_tools.pestle_technological',
  legal: 'strategy_tools.pestle_legal',
  environmental: 'strategy_tools.pestle_environmental',
};

const SWOT_KEYS = ['strengths', 'weaknesses', 'opportunities', 'threats'];
const SWOT_LABEL_KEYS = {
  strengths: 'strategy_tools.swot_strengths',
  weaknesses: 'strategy_tools.swot_weaknesses',
  opportunities: 'strategy_tools.swot_opportunities',
  threats: 'strategy_tools.swot_threats',
};
const SWOT_COLORS = {
  strengths: '#52c41a',
  weaknesses: '#ff4d4f',
  opportunities: '#1677ff',
  threats: '#fa8c16',
};

const POSTURE_TAG_COLORS = {
  DIFFERENTIATION: 'purple',
  'MARKET PENETRATION': 'green',
  'VERTICAL INTEGRATION': 'orange',
  'BALANCED APPROACH': 'blue',
};

const ENTRY_CRITERIA = [
  { key: 'total_market_size', labelKey: 'strategy_tools.entry_market_size' },
  { key: 'growth_rate', labelKey: 'strategy_tools.entry_growth' },
  { key: 'entry_cost_base', labelKey: 'strategy_tools.entry_cost' },
  { key: 'tariff_rate', labelKey: 'strategy_tools.entry_tariff' },
  { key: 'regulatory_difficulty', labelKey: 'strategy_tools.entry_regulatory' },
  { key: 'competitive_intensity_num', labelKey: 'strategy_tools.entry_competitive' },
  { key: 'exchange_rate_volatility', labelKey: 'strategy_tools.entry_currency_risk' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function initForces() {
  const forces = {};
  const notes = {};
  FORCE_KEYS.forEach((k) => {
    forces[k] = 5;
    notes[k] = '';
  });
  return { forces, notes };
}

function initPestle() {
  const ratings = {};
  const notes = {};
  PESTLE_KEYS.forEach((k) => {
    ratings[k] = 5;
    notes[k] = '';
  });
  return { ratings, notes };
}

function initSwot() {
  const items = {};
  SWOT_KEYS.forEach((k) => {
    items[k] = '';
  });
  return items;
}

function initWeights() {
  const w = {};
  ENTRY_CRITERIA.forEach((c) => {
    w[c.key] = 3;
  });
  return w;
}

function computePorterOutput(forces) {
  const vals = FORCE_KEYS.map((k) => forces[k] || 5);
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const attractiveness = Math.round((10 - avg) * 10) / 10;

  const recommendations = [];
  if ((forces.rivalry || 0) >= 7 && (forces.buyer_power || 0) >= 6) {
    recommendations.push('High rivalry combined with strong buyer power creates margin pressure. Consider a differentiation strategy to escape pure price competition.');
  }
  if ((forces.supplier_power || 0) >= 6) {
    recommendations.push('Elevated supplier dependency detected. Evaluate vertical integration or diversifying your supplier base.');
  }
  if ((forces.new_entrants || 0) <= 3) {
    recommendations.push('High barriers to entry provide a positive competitive shield. Leverage incumbency advantages.');
  }
  if ((forces.substitutes || 0) >= 7) {
    recommendations.push('High substitution threat indicates fragile customer loyalty. Invest in brand differentiation and switching costs.');
  }

  let posture = 'BALANCED APPROACH';
  if ((forces.buyer_power || 0) >= 7 && (forces.rivalry || 0) >= 7) {
    posture = 'DIFFERENTIATION';
  } else if ((forces.new_entrants || 0) <= 4 && (forces.rivalry || 0) <= 5) {
    posture = 'MARKET PENETRATION';
  } else if ((forces.supplier_power || 0) >= 7) {
    posture = 'VERTICAL INTEGRATION';
  }

  return { attractiveness, posture, recommendations };
}

function computePestleOutput(ratings) {
  const riskScores = {};
  PESTLE_KEYS.forEach((k) => {
    riskScores[k] = ratings[k] || 5;
  });
  const vals = Object.values(riskScores);
  const overallRisk = Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10;

  const mitigations = [];
  if ((ratings.political || 0) >= 7) mitigations.push('High political risk: consider government relations investment and scenario planning for regulatory changes.');
  if ((ratings.economic || 0) >= 7) mitigations.push('Significant economic risk: hedge currency exposure and diversify market revenue sources.');
  if ((ratings.social || 0) >= 7) mitigations.push('Social risk elevated: invest in local market research and culturally adapted products.');
  if ((ratings.technological || 0) >= 7) mitigations.push('Technology risk: accelerate R&D investment to stay ahead of disruption.');
  if ((ratings.legal || 0) >= 7) mitigations.push('Legal risk: engage compliance counsel and monitor regulatory pipeline.');
  if ((ratings.environmental || 0) >= 7) mitigations.push('ESG / environmental risk: integrate sustainability into operations to reduce exposure.');

  let assessment = 'LOW';
  if (overallRisk >= 7) assessment = 'HIGH';
  else if (overallRisk >= 4.5) assessment = 'MODERATE';

  return { riskScores, overallRisk, assessment, mitigations };
}

function extractCompetitorCount(intensityStr) {
  if (!intensityStr) return 0;
  const m = String(intensityStr).match(/(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SavedAnalysesList({ analyses, currentRound, onLoad }) {
  const { t } = useTranslation();
  if (!analyses || analyses.length === 0) {
    return <Text type="secondary">{t("strategy_tools.no_saved_analyses")}</Text>;
  }
  return (
    <Card title={t("strategy_tools.compare_previous")} size="small" style={{ marginTop: 24 }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        {analyses.map((a) => (
          <Card
            key={a.id}
            size="small"
            hoverable
            onClick={() => onLoad(a)}
            style={{ cursor: 'pointer' }}
          >
            <Row justify="space-between" align="middle">
              <Col>
                <Space>
                  <Tag color={a.round_number === currentRound ? 'green' : 'default'}>
                    {t('common.round')} {a.round_number}
                  </Tag>
                  {a.market_name && <Tag color="blue">{a.market_name}</Tag>}
                </Space>
              </Col>
              <Col>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {new Date(a.updated_at).toLocaleDateString()}
                </Text>
              </Col>
            </Row>
          </Card>
        ))}
      </Space>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Tab 1: Porter's Five Forces
// ---------------------------------------------------------------------------

function PorterTab({ gameId, teamId, currentRound }) {
  const { t } = useTranslation();
  const [forces, setForces] = useState(initForces().forces);
  const [notes, setNotes] = useState(initForces().notes);
  const [market, setMarket] = useState(null);
  const [marketsData, setMarketsData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedList, setSavedList] = useState([]);

  const fetchMarkets = useCallback(async () => {
    if (!gameId || !teamId) return;
    setLoading(true);
    try {
      const res = await getResearchReport(gameId, teamId, 'markets');
      setMarketsData(res.data?.markets || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId]);

  const fetchSaved = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const params = { framework: 'porters' };
      if (market) params.market = market;
      const res = await client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/`, { params });
      setSavedList(res.data?.analyses || []);
    } catch { /* ignore */ }
  }, [gameId, teamId, market]);

  const loadCurrentRound = useCallback(async () => {
    if (!gameId || !teamId || !market) return;
    try {
      const res = await client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        params: { framework: 'porters', market },
      });
      const current = (res.data?.analyses || []).find((a) => a.round_number === currentRound);
      if (current?.analysis_data) {
        setForces(current.analysis_data.forces || initForces().forces);
        setNotes(current.analysis_data.notes || initForces().notes);
      }
    } catch { /* ignore */ }
  }, [gameId, teamId, market, currentRound]);

  useEffect(() => { fetchMarkets(); }, [fetchMarkets]);
  useEffect(() => { fetchSaved(); }, [fetchSaved]);
  useEffect(() => { loadCurrentRound(); }, [loadCurrentRound]);

  const selectedMarketData = useMemo(
    () => marketsData.find((m) => m.code === market),
    [marketsData, market],
  );

  const output = useMemo(() => computePorterOutput(forces), [forces]);

  const referenceData = useMemo(() => {
    const md = selectedMarketData;
    if (!md) return {};
    const competitorCount = extractCompetitorCount(md.competitive_intensity);
    return {
      new_entrants: [
        `${t('strategy_tools.ref_entry_cost')}: $${(md.entry_cost_base / 1000000).toFixed(1)}M`,
        `${t('strategy_tools.ref_regulatory_difficulty')}: ${md.regulatory_difficulty}/10`,
        `${t('strategy_tools.ref_competitors_present')}: ${competitorCount}`,
        `${t('strategy_tools.ref_growth_rate')}: ${(md.growth_rate * 100).toFixed(1)}%`,
      ],
      supplier_power: [
        `${t('strategy_tools.ref_contract_mfg')}: ${md.contract_mfg_available ? t('strategy_tools.ref_yes') : t('strategy_tools.ref_no')}`,
        `${t('strategy_tools.ref_team_has_plant')}: ${md.your_plant ? t('strategy_tools.ref_yes') : t('strategy_tools.ref_no')}`,
        t('strategy_tools.ref_ops_talent_varies'),
      ],
      buyer_power: [
        ...(md.segment_breakdown || []).map(
          (s) => `${s.segment}: ${(s.pct_of_market * 100).toFixed(0)}% ${t('strategy_tools.ref_of_market')}, ${t('strategy_tools.ref_growth')}: ${s.growth}`,
        ),
        `${t('strategy_tools.ref_market_concentration')}: ${competitorCount} ${t('strategy_tools.ref_competitors')}`,
      ],
      substitutes: [t('strategy_tools.ref_product_defensibility')],
      rivalry: [
        `${t('strategy_tools.ref_competitors_present')}: ${competitorCount}`,
        `${t('strategy_tools.ref_competitive_intensity')}: ${md.competitive_intensity}`,
      ],
    };
  }, [selectedMarketData]);

  const handleSave = async () => {
    if (!market) { message.warning(t('strategy_tools.select_market_first')); return; }
    setSaving(true);
    try {
      await client.post(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        framework_type: 'porters',
        market,
        round_number: currentRound,
        analysis_data: {
          forces,
          notes,
          output: {
            attractiveness: output.attractiveness,
            posture: output.posture,
            recommendations: output.recommendations,
          },
        },
      });
      message.success(t('strategy_tools.porter_saved'));
      fetchSaved();
    } catch {
      message.error(t('strategy_tools.save_failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleLoad = (analysis) => {
    if (analysis.analysis_data) {
      setForces(analysis.analysis_data.forces || initForces().forces);
      setNotes(analysis.analysis_data.notes || initForces().notes);
    }
    if (analysis.market) setMarket(analysis.market);
  };

  if (loading) return <LoadingSpinner tip={t("strategy_tools.loading_market_data")} />;

  const marketOptions = marketsData.map((m) => ({ value: m.code, label: m.name }));

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Select
        placeholder={t("strategy_tools.select_market")}
        value={market}
        onChange={(v) => {
          setMarket(v);
          setForces(initForces().forces);
          setNotes(initForces().notes);
        }}
        options={marketOptions}
        style={{ width: '100%', maxWidth: 300 }}
      />

      {market && (
        <>
          {FORCE_KEYS.map((key) => (
            <Card key={key} size="small" title={t(FORCE_LABEL_KEYS[key])}>
              <Row gutter={24}>
                <Col xs={24} md={14}>
                  <Text strong>{t("strategy_tools.your_rating")}</Text>
                  <Slider
                    min={1}
                    max={10}
                    value={forces[key]}
                    onChange={(v) => setForces((prev) => ({ ...prev, [key]: v }))}
                    marks={{ 1: '1', 5: '5', 10: '10' }}
                  />
                  <TextArea
                    value={notes[key]}
                    onChange={(e) => setNotes((prev) => ({ ...prev, [key]: e.target.value }))}
                    placeholder={t("strategy_tools.notes_placeholder")}
                    autoSize={{ minRows: 2, maxRows: 4 }}
                    style={{ marginTop: 8 }}
                  />
                </Col>
                <Col xs={24} md={10}>
                  <Card
                    size="small"
                    type="inner"
                    title={t("strategy_tools.reference_data")}
                    style={{ background: '#fafafa' }}
                  >
                    {(referenceData[key] || []).map((line, i) => (
                      <div key={i}><Text type="secondary">{line}</Text></div>
                    ))}
                    {(!referenceData[key] || referenceData[key].length === 0) && (
                      <Text type="secondary">{t("strategy_tools.select_market_ref")}</Text>
                    )}
                  </Card>
                </Col>
              </Row>
            </Card>
          ))}

          {/* Output */}
          <PanelCard headerColor="strategic" title={t("strategy_tools.porter_output").toUpperCase()}>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label={t("strategy_tools.overall_attractiveness")}>
                <Progress
                  percent={Math.round(output.attractiveness * 10)}
                  format={() => `${output.attractiveness} / 10`}
                  status={output.attractiveness >= 6 ? 'success' : output.attractiveness >= 4 ? 'normal' : 'exception'}
                />
              </Descriptions.Item>
              <Descriptions.Item label={t("strategy_tools.strategic_posture")}>
                <Tag color={POSTURE_TAG_COLORS[output.posture] || 'blue'}>{output.posture}</Tag>
              </Descriptions.Item>
            </Descriptions>

            <Title level={5} style={{ marginTop: 16 }}>{t("strategy_tools.force_breakdown")}</Title>
            {FORCE_KEYS.map((key) => (
              <div key={key} style={{ marginBottom: 8 }}>
                <Text>{t(FORCE_LABEL_KEYS[key])}</Text>
                <Progress percent={forces[key] * 10} size="small" format={() => `${forces[key]}/10`} />
              </div>
            ))}

            {output.recommendations.length > 0 && (
              <>
                <Title level={5} style={{ marginTop: 16 }}>{t("strategy_tools.recommendations")}</Title>
                {output.recommendations.map((r, i) => (
                  <Alert key={i} message={r} type="info" showIcon style={{ marginBottom: 8 }} />
                ))}
              </>
            )}
          </PanelCard>

          <Button type="primary" onClick={handleSave} loading={saving} size="large">
            {t("strategy_tools.save_porter")}
          </Button>
        </>
      )}

      <SavedAnalysesList analyses={savedList} currentRound={currentRound} onLoad={handleLoad} />
    </Space>
  );
}

// ---------------------------------------------------------------------------
// Tab 2: PESTLE Analysis
// ---------------------------------------------------------------------------

function PestleTab({ gameId, teamId, currentRound }) {
  const { t } = useTranslation();
  const [ratings, setRatings] = useState(initPestle().ratings);
  const [notes, setNotes] = useState(initPestle().notes);
  const [market, setMarket] = useState(null);
  const [marketsData, setMarketsData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedList, setSavedList] = useState([]);

  const fetchMarkets = useCallback(async () => {
    if (!gameId || !teamId) return;
    setLoading(true);
    try {
      const res = await getResearchReport(gameId, teamId, 'markets');
      setMarketsData(res.data?.markets || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId]);

  const fetchSaved = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const params = { framework: 'pestle' };
      if (market) params.market = market;
      const res = await client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/`, { params });
      setSavedList(res.data?.analyses || []);
    } catch { /* ignore */ }
  }, [gameId, teamId, market]);

  const loadCurrentRound = useCallback(async () => {
    if (!gameId || !teamId || !market) return;
    try {
      const res = await client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        params: { framework: 'pestle', market },
      });
      const current = (res.data?.analyses || []).find((a) => a.round_number === currentRound);
      if (current?.analysis_data) {
        setRatings(current.analysis_data.ratings || initPestle().ratings);
        setNotes(current.analysis_data.notes || initPestle().notes);
      }
    } catch { /* ignore */ }
  }, [gameId, teamId, market, currentRound]);

  useEffect(() => { fetchMarkets(); }, [fetchMarkets]);
  useEffect(() => { fetchSaved(); }, [fetchSaved]);
  useEffect(() => { loadCurrentRound(); }, [loadCurrentRound]);

  const selectedMarketData = useMemo(
    () => marketsData.find((m) => m.code === market),
    [marketsData, market],
  );

  const output = useMemo(() => computePestleOutput(ratings), [ratings]);

  const referenceData = useMemo(() => {
    const md = selectedMarketData;
    if (!md) return {};
    return {
      political: [
        `${t('strategy_tools.ref_regulatory_difficulty')}: ${md.regulatory_difficulty}/10`,
        `${t('strategy_tools.ref_tariff_rate')}: ${(md.tariff_rate * 100).toFixed(1)}%`,
      ],
      economic: [
        `${t('strategy_tools.ref_growth_rate')}: ${(md.growth_rate * 100).toFixed(1)}%`,
        `${t('strategy_tools.ref_exchange_rate')}: ${md.exchange_rate}`,
        `${t('strategy_tools.ref_exchange_rate_volatility')}: ${md.exchange_rate_volatility}`,
      ],
      social: [
        ...(md.segment_breakdown || []).map(
          (s) => `${s.segment}: ${(s.pct_of_market * 100).toFixed(0)}% ${t('strategy_tools.ref_of_market')}, ${t('strategy_tools.ref_growth')}: ${s.growth}`,
        ),
      ],
      technological: [t('strategy_tools.ref_tech_ceiling')],
      legal: [`${t('strategy_tools.ref_tax_rate')}: ${md.tax_rate ? (md.tax_rate * 100).toFixed(1) + '%' : 'N/A'}`],
      environmental: [t('strategy_tools.ref_esg_relevance')],
    };
  }, [selectedMarketData]);

  const handleSave = async () => {
    if (!market) { message.warning(t('strategy_tools.select_market_first')); return; }
    setSaving(true);
    try {
      await client.post(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        framework_type: 'pestle',
        market,
        round_number: currentRound,
        analysis_data: {
          ratings,
          notes,
          output: {
            riskScores: output.riskScores,
            overallRisk: output.overallRisk,
            assessment: output.assessment,
            mitigations: output.mitigations,
          },
        },
      });
      message.success(t('strategy_tools.pestle_saved'));
      fetchSaved();
    } catch {
      message.error(t('strategy_tools.save_failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleLoad = (analysis) => {
    if (analysis.analysis_data) {
      setRatings(analysis.analysis_data.ratings || initPestle().ratings);
      setNotes(analysis.analysis_data.notes || initPestle().notes);
    }
    if (analysis.market) setMarket(analysis.market);
  };

  if (loading) return <LoadingSpinner tip={t("strategy_tools.loading_market_data")} />;

  const marketOptions = marketsData.map((m) => ({ value: m.code, label: m.name }));

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Select
        placeholder={t("strategy_tools.select_market")}
        value={market}
        onChange={(v) => {
          setMarket(v);
          setRatings(initPestle().ratings);
          setNotes(initPestle().notes);
        }}
        options={marketOptions}
        style={{ width: '100%', maxWidth: 300 }}
      />

      {market && (
        <>
          {PESTLE_KEYS.map((key) => (
            <Card key={key} size="small" title={t(PESTLE_LABEL_KEYS[key])}>
              <Row gutter={24}>
                <Col xs={24} md={14}>
                  <Text strong>{t("strategy_tools.impact_rating")}</Text>
                  <Slider
                    min={1}
                    max={10}
                    value={ratings[key]}
                    onChange={(v) => setRatings((prev) => ({ ...prev, [key]: v }))}
                    marks={{ 1: '1', 5: '5', 10: '10' }}
                  />
                  <TextArea
                    value={notes[key]}
                    onChange={(e) => setNotes((prev) => ({ ...prev, [key]: e.target.value }))}
                    placeholder={t("strategy_tools.notes_short")}
                    autoSize={{ minRows: 2, maxRows: 4 }}
                    style={{ marginTop: 8 }}
                  />
                </Col>
                <Col xs={24} md={10}>
                  <Card
                    size="small"
                    type="inner"
                    title={t("strategy_tools.reference_data")}
                    style={{ background: '#fafafa' }}
                  >
                    {(referenceData[key] || []).map((line, i) => (
                      <div key={i}><Text type="secondary">{line}</Text></div>
                    ))}
                  </Card>
                </Col>
              </Row>
            </Card>
          ))}

          {/* Output */}
          <PanelCard headerColor="strategic" title={t("strategy_tools.pestle_output").toUpperCase()}>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label={t("strategy_tools.overall_risk_score")}>
                <Progress
                  percent={Math.round(output.overallRisk * 10)}
                  format={() => `${output.overallRisk} / 10`}
                  status={output.overallRisk <= 4 ? 'success' : output.overallRisk <= 6.5 ? 'normal' : 'exception'}
                />
              </Descriptions.Item>
              <Descriptions.Item label={t("strategy_tools.risk_assessment")}>
                <Tag color={output.assessment === 'LOW' ? 'green' : output.assessment === 'MODERATE' ? 'orange' : 'red'}>
                  {output.assessment}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            <Title level={5} style={{ marginTop: 16 }}>{t("strategy_tools.risk_by_dimension")}</Title>
            {PESTLE_KEYS.map((key) => (
              <div key={key} style={{ marginBottom: 8 }}>
                <Text>{t(PESTLE_LABEL_KEYS[key])}</Text>
                <Progress
                  percent={ratings[key] * 10}
                  size="small"
                  format={() => `${ratings[key]}/10`}
                  status={ratings[key] <= 4 ? 'success' : ratings[key] <= 6 ? 'normal' : 'exception'}
                />
              </div>
            ))}

            {output.mitigations.length > 0 && (
              <>
                <Title level={5} style={{ marginTop: 16 }}>{t("strategy_tools.recommended_mitigations")}</Title>
                {output.mitigations.map((m, i) => (
                  <Alert key={i} message={m} type="warning" showIcon style={{ marginBottom: 8 }} />
                ))}
              </>
            )}
          </PanelCard>

          <Button type="primary" onClick={handleSave} loading={saving} size="large">
            {t("strategy_tools.save_pestle")}
          </Button>
        </>
      )}

      <SavedAnalysesList analyses={savedList} currentRound={currentRound} onLoad={handleLoad} />
    </Space>
  );
}

// ---------------------------------------------------------------------------
// Tab 3: SWOT Analysis
// ---------------------------------------------------------------------------

function SwotTab({ gameId, teamId, currentRound }) {
  const { t } = useTranslation();
  const [items, setItems] = useState(initSwot());
  const [marketsData, setMarketsData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedList, setSavedList] = useState([]);
  const [suggestions, setSuggestions] = useState({
    strengths: [],
    weaknesses: [],
    opportunities: [],
    threats: [],
  });

  const fetchData = useCallback(async () => {
    if (!gameId || !teamId) return;
    setLoading(true);
    try {
      const res = await getResearchReport(gameId, teamId, 'markets');
      const markets = res.data?.markets || [];
      setMarketsData(markets);

      const s = { strengths: [], weaknesses: [], opportunities: [], threats: [] };

      markets.forEach((m) => {
        // Strengths from segment fit
        (m.segment_breakdown || []).forEach((seg) => {
          if (seg.pct_of_market > 0.5) {
            s.strengths.push(t('strategy_tools.swot_strong_fit', { segment: seg.segment, market: m.name }));
          }
        });
        if (m.your_plant) {
          s.strengths.push(t('strategy_tools.swot_own_mfg', { market: m.name }));
        }

        // Weaknesses
        if (m.your_presence && !m.your_plant && !m.contract_mfg_available) {
          s.weaknesses.push(t('strategy_tools.swot_contract_mfg_dep', { market: m.name }));
        }

        // Opportunities
        if (!m.your_presence) {
          s.opportunities.push(t('strategy_tools.swot_untapped', { market: m.name }));
        }
        if (m.growth_rate > 0.05) {
          s.opportunities.push(t('strategy_tools.swot_high_growth', { market: m.name, rate: (m.growth_rate * 100).toFixed(1) }));
        }

        // Threats
        const compCount = extractCompetitorCount(m.competitive_intensity);
        if (compCount >= 4) {
          s.threats.push(t('strategy_tools.swot_high_rivalry', { market: m.name, count: compCount }));
        }
        if (m.exchange_rate_volatility > 0.05) {
          s.threats.push(t('strategy_tools.swot_currency_volatility', { market: m.name }));
        }
      });

      // Generic weaknesses
      s.weaknesses.push(t('strategy_tools.swot_contract_mfg_generic'));

      // Deduplicate
      Object.keys(s).forEach((k) => {
        s[k] = [...new Set(s[k])];
      });

      setSuggestions(s);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId]);

  const fetchSaved = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const res = await client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        params: { framework: 'swot' },
      });
      setSavedList(res.data?.analyses || []);
      const current = (res.data?.analyses || []).find((a) => a.round_number === currentRound);
      if (current?.analysis_data?.items) {
        setItems(current.analysis_data.items);
      }
    } catch { /* ignore */ }
  }, [gameId, teamId, currentRound]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchSaved(); }, [fetchSaved]);

  const addSuggestion = (quadrant, text) => {
    setItems((prev) => {
      const existing = prev[quadrant] || '';
      if (existing.includes(text)) return prev;
      const separator = existing.trim() ? '\n' : '';
      return { ...prev, [quadrant]: existing + separator + text };
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await client.post(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        framework_type: 'swot',
        round_number: currentRound,
        analysis_data: { items },
      });
      message.success(t('strategy_tools.swot_saved'));
      fetchSaved();
    } catch {
      message.error(t('strategy_tools.save_failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleLoad = (analysis) => {
    if (analysis.analysis_data?.items) {
      setItems(analysis.analysis_data.items);
    }
  };

  if (loading) return <LoadingSpinner tip={t("strategy_tools.loading_data")} />;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <PanelCard headerColor="strategic" title={t("strategy_tools.swot_analysis").toUpperCase()}>
        <Row gutter={[16, 16]}>
          {SWOT_KEYS.map((key) => (
            <Col xs={24} md={12} key={key}>
              <Card
                size="small"
                title={
                  <span style={{ color: SWOT_COLORS[key] }}>{t(SWOT_LABEL_KEYS[key])}</span>
                }
                style={{ borderTop: `3px solid ${SWOT_COLORS[key]}`, minHeight: 320 }}
              >
                <TextArea
                  value={items[key]}
                  onChange={(e) => setItems((prev) => ({ ...prev, [key]: e.target.value }))}
                  placeholder={t("strategy_tools.swot_placeholder", { quadrant: t(SWOT_LABEL_KEYS[key]).toLowerCase() })}
                  autoSize={{ minRows: 6, maxRows: 12 }}
                  style={{ marginBottom: 12 }}
                />
                {suggestions[key]?.length > 0 && (
                  <>
                    <Text type="secondary" style={{ fontSize: 12 }}>{t("strategy_tools.suggested_click")}:</Text>
                    <div style={{ marginTop: 4 }}>
                      {suggestions[key].map((s, i) => (
                        <Tag
                          key={i}
                          style={{ cursor: 'pointer', marginBottom: 4 }}
                          onClick={() => addSuggestion(key, s)}
                        >
                          + {s}
                        </Tag>
                      ))}
                    </div>
                  </>
                )}
              </Card>
            </Col>
          ))}
        </Row>
      </PanelCard>

      <Button type="primary" onClick={handleSave} loading={saving} size="large">
        {t("strategy_tools.save_swot")}
      </Button>

      <SavedAnalysesList analyses={savedList} currentRound={currentRound} onLoad={handleLoad} />
    </Space>
  );
}

// ---------------------------------------------------------------------------
// Tab 4: Market Entry Matrix
// ---------------------------------------------------------------------------

function EntryMatrixTab({ gameId, teamId, currentRound }) {
  const { t } = useTranslation();
  const [marketsData, setMarketsData] = useState([]);
  const [weights, setWeights] = useState(initWeights());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedList, setSavedList] = useState([]);

  const fetchData = useCallback(async () => {
    if (!gameId || !teamId) return;
    setLoading(true);
    try {
      const [matrixRes, marketsRes] = await Promise.all([
        client.get(`/games/${gameId}/teams/${teamId}/tools/entry-matrix-data/`),
        getResearchReport(gameId, teamId, 'markets'),
      ]);

      const matrixMarkets = matrixRes.data?.markets || [];
      const reportMarkets = marketsRes.data?.markets || [];

      // Merge data: matrix has base fields, report has richer data
      const merged = matrixMarkets.map((mm) => {
        const rm = reportMarkets.find((r) => r.code === mm.code) || {};
        return {
          ...mm,
          total_market_size: rm.total_market_size || 0,
          growth_rate: rm.growth_rate ?? mm.base_growth_rate ?? 0,
          exchange_rate_volatility: rm.exchange_rate_volatility ?? 0,
          competitive_intensity: rm.competitive_intensity || '',
          competitive_intensity_num: extractCompetitorCount(rm.competitive_intensity),
        };
      });

      setMarketsData(merged);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId]);

  const fetchSaved = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const res = await client.get(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        params: { framework: 'entry_matrix' },
      });
      setSavedList(res.data?.analyses || []);
      const current = (res.data?.analyses || []).find((a) => a.round_number === currentRound);
      if (current?.analysis_data?.weights) {
        setWeights(current.analysis_data.weights);
      }
    } catch { /* ignore */ }
  }, [gameId, teamId, currentRound]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchSaved(); }, [fetchSaved]);

  // Compute weighted scores
  const scoredMarkets = useMemo(() => {
    if (marketsData.length === 0) return [];

    // Normalize each criterion to 0-1 scale
    const criteriaValues = {};
    ENTRY_CRITERIA.forEach((c) => {
      const vals = marketsData.map((m) => parseFloat(m[c.key]) || 0);
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      criteriaValues[c.key] = { min, max, range: max - min || 1 };
    });

    // For entry_cost, tariff, regulatory_difficulty, competitive_intensity, currency_risk — higher is worse
    const invertedCriteria = ['entry_cost_base', 'tariff_rate', 'regulatory_difficulty', 'competitive_intensity_num', 'exchange_rate_volatility'];

    return marketsData.map((m) => {
      let totalWeightedScore = 0;
      let totalWeight = 0;

      ENTRY_CRITERIA.forEach((c) => {
        const raw = parseFloat(m[c.key]) || 0;
        const cv = criteriaValues[c.key];
        let normalized = (raw - cv.min) / cv.range;
        if (invertedCriteria.includes(c.key)) {
          normalized = 1 - normalized;
        }
        const w = weights[c.key] || 3;
        totalWeightedScore += normalized * w;
        totalWeight += w;
      });

      const score = totalWeight > 0 ? Math.round((totalWeightedScore / totalWeight) * 100) / 10 : 0;

      return { ...m, weighted_score: score };
    }).sort((a, b) => b.weighted_score - a.weighted_score);
  }, [marketsData, weights]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await client.post(`/games/${gameId}/teams/${teamId}/tools/analysis/`, {
        framework_type: 'entry_matrix',
        round_number: currentRound,
        analysis_data: {
          weights,
          scores: scoredMarkets.map((m) => ({ code: m.code, name: m.name, score: m.weighted_score })),
        },
      });
      message.success(t('strategy_tools.entry_matrix_saved'));
      fetchSaved();
    } catch {
      message.error(t('strategy_tools.save_failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleLoad = (analysis) => {
    if (analysis.analysis_data?.weights) {
      setWeights(analysis.analysis_data.weights);
    }
  };

  if (loading) return <LoadingSpinner tip={t("strategy_tools.loading_matrix")} />;

  const columns = [
    {
      title: t('strategy_tools.market'),
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: 140,
      render: (text) => <Text strong>{text}</Text>,
    },
    ...ENTRY_CRITERIA.map((c) => ({
      title: (
        <Space direction="vertical" size={0} align="center">
          <Text style={{ fontSize: 12 }}>{t(c.labelKey)}</Text>
          <InputNumber
            min={1}
            max={5}
            value={weights[c.key]}
            onChange={(v) => setWeights((prev) => ({ ...prev, [c.key]: v }))}
            size="small"
            style={{ width: 56 }}
          />
        </Space>
      ),
      dataIndex: c.key,
      key: c.key,
      width: 130,
      render: (val) => {
        if (c.key === 'total_market_size') return val ? val.toLocaleString() : '-';
        if (c.key === 'growth_rate') return `${((val || 0) * 100).toFixed(1)}%`;
        if (c.key === 'entry_cost_base') return val ? `$${(val / 1000000).toFixed(1)}M` : '-';
        if (c.key === 'tariff_rate') return `${((val || 0) * 100).toFixed(1)}%`;
        if (c.key === 'regulatory_difficulty') return `${val || 0}/10`;
        if (c.key === 'exchange_rate_volatility') return val ? val.toFixed(3) : '-';
        return val ?? '-';
      },
    })),
    {
      title: t('strategy_tools.score'),
      dataIndex: 'weighted_score',
      key: 'weighted_score',
      width: 100,
      fixed: 'right',
      sorter: (a, b) => a.weighted_score - b.weighted_score,
      defaultSortOrder: 'descend',
      render: (val) => (
        <Tag color={val >= 7 ? 'green' : val >= 4 ? 'blue' : 'red'}>
          {val.toFixed(1)}
        </Tag>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Alert
        message={t("strategy_tools.weights_hint")}
        type="info"
        showIcon
      />

      <Table
        dataSource={scoredMarkets}
        columns={columns}
        rowKey="code"
        pagination={false}
        size="small"
        scroll={{ x: 1100 }}
      />

      {/* Ranking display */}
      {scoredMarkets.length > 0 && (
        <PanelCard headerColor="market" title={t("strategy_tools.market_entry_matrix").toUpperCase()}>
          {scoredMarkets.map((m, idx) => (
            <div key={m.code} style={{ marginBottom: 8 }}>
              <Row align="middle" gutter={12}>
                <Col flex="30px">
                  <Text strong>#{idx + 1}</Text>
                </Col>
                <Col flex="120px">
                  <Text>{m.name}</Text>
                </Col>
                <Col flex="auto">
                  <Progress
                    percent={Math.round(m.weighted_score * 10)}
                    format={() => m.weighted_score.toFixed(1)}
                    status={m.weighted_score >= 7 ? 'success' : m.weighted_score >= 4 ? 'normal' : 'exception'}
                  />
                </Col>
              </Row>
            </div>
          ))}
        </PanelCard>
      )}

      <Button type="primary" onClick={handleSave} loading={saving} size="large">
        {t("strategy_tools.save_entry_matrix")}
      </Button>

      <SavedAnalysesList analyses={savedList} currentRound={currentRound} onLoad={handleLoad} />
    </Space>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

const StrategyToolsPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound } = useGame();

  if (!gameId || !teamId) {
    return <LoadingSpinner tip={t("strategy_tools.loading")} />;
  }

  const tabItems = [
    {
      key: 'porters',
      label: t('strategy_tools.porters'),
      children: <PorterTab gameId={gameId} teamId={teamId} currentRound={currentRound} />,
    },
    {
      key: 'pestle',
      label: t('strategy_tools.pestle'),
      children: <PestleTab gameId={gameId} teamId={teamId} currentRound={currentRound} />,
    },
    {
      key: 'swot',
      label: t('strategy_tools.swot'),
      children: <SwotTab gameId={gameId} teamId={teamId} currentRound={currentRound} />,
    },
    {
      key: 'entry_matrix',
      label: t('strategy_tools.entry_matrix'),
      children: <EntryMatrixTab gameId={gameId} teamId={teamId} currentRound={currentRound} />,
    },
  ];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      <PageHeader
        title={t("strategy_tools.title")}
        subtitle={t("strategy_tools.subtitle")}
      />
      <Tabs className="ds-colored-tabs" items={tabItems} size="large" />
    </div>
  );
};

export default StrategyToolsPage;
