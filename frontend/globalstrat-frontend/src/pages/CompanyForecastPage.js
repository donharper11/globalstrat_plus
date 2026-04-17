import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Card, Typography, Row, Col, Statistic, Table, Button, Input, message, Empty, Divider, Tag, Slider,
} from 'antd';
import { useGame } from '../contexts/GameContext';
import { getForecast, getForecastScenarios, saveForecastScenario } from '../api/cc15';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Title, Text, Paragraph } = Typography;

const fmt = (v) => {
  if (v == null) return '$0';
  const abs = Math.abs(v);
  if (abs >= 1000000) return `${v < 0 ? '-' : ''}$${(Math.abs(v) / 1000000).toFixed(1)}M`;
  if (abs >= 1000) return `${v < 0 ? '-' : ''}$${(Math.abs(v) / 1000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
};

const CompanyForecastPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound } = useGame();
  const [forecast, setForecast] = useState(null);
  const [scenarios, setScenarios] = useState([]);
  const [scenarioName, setScenarioName] = useState('');
  const [savingScenario, setSavingScenario] = useState(false);
  const [loading, setLoading] = useState(true);
  const [fxAdjustments, setFxAdjustments] = useState({});

  const fetchForecast = useCallback(async () => {
    if (!gameId || !teamId) return;
    try {
      const [fRes, sRes] = await Promise.all([
        getForecast(gameId, teamId),
        getForecastScenarios(gameId, teamId, currentRound),
      ]);
      setForecast(fRes.data);
      setScenarios(sRes.data?.scenarios || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [gameId, teamId, currentRound]);

  useEffect(() => { fetchForecast(); }, [fetchForecast]);

  const handleSaveScenario = async () => {
    if (!scenarioName.trim() || !forecast) return;
    setSavingScenario(true);
    try {
      await saveForecastScenario(gameId, teamId, {
        name: scenarioName.trim(),
        parameters: { revenue_lines: forecast.revenue_lines },
        projected_results: {
          total_revenue: forecast.total_revenue,
          costs: forecast.costs,
          net_income: forecast.projected_net_income,
          cash: forecast.projected_cash,
        },
      });
      setScenarioName('');
      message.success(t('forecast_page.scenario_saved'));
      // Refresh scenarios
      const sRes = await getForecastScenarios(gameId, teamId, currentRound);
      setScenarios(sRes.data?.scenarios || []);
    } catch {
      message.error(t('forecast_page.scenario_save_failed'));
    } finally {
      setSavingScenario(false);
    }
  };

  if (loading) return <LoadingSpinner message={t("forecast_page.loading")} />;

  if (!forecast?.has_draft) {
    return (
      <div style={{ maxWidth: 900, margin: '0 auto', width: '100%' }}>
        <PageHeader
          title={t("forecast_page.title")}
          subtitle={`${t("common.round")} ${currentRound} · ${t("forecast_page.subtitle")}`}
        />
        <Empty description={t("forecast_page.no_draft")} />
      </div>
    );
  }

  const costs = forecast.costs || {};

  const revenueColumns = [
    { title: t('forecast_page.col_product'), dataIndex: 'product', key: 'product' },
    { title: t('forecast_page.col_market'), dataIndex: 'market', key: 'market' },
    { title: t('forecast_page.col_price'), dataIndex: 'price', key: 'price', render: v => `$${v?.toLocaleString()}` },
    { title: t('forecast_page.col_est_units'), dataIndex: 'units', key: 'units', render: v => v?.toLocaleString() },
    { title: t('forecast_page.col_revenue'), dataIndex: 'revenue', key: 'revenue', render: v => fmt(v) },
  ];

  // Currency scenario: find unique non-USD currencies
  const currencyMarkets = {};
  (forecast.revenue_lines || []).forEach(line => {
    if (line.currency_code && line.currency_code !== 'USD') {
      if (!currencyMarkets[line.currency_code]) {
        currencyMarkets[line.currency_code] = { rate: line.exchange_rate, lines: [] };
      }
      currencyMarkets[line.currency_code].lines.push(line);
    }
  });
  const hasFxMarkets = Object.keys(currencyMarkets).length > 0;

  // Compute FX impact on revenue
  let fxRevenueImpact = 0;
  if (hasFxMarkets) {
    Object.entries(currencyMarkets).forEach(([code, info]) => {
      const adj = fxAdjustments[code] || 0; // percentage adjustment
      info.lines.forEach(line => {
        // Revenue is priced in local currency, converted at FX rate
        // Impact = revenue * (adj%) since revenue scales with FX
        fxRevenueImpact += line.revenue * (adj / 100);
      });
    });
  }

  const costItems = [
    { key: 'cogs', label: t('forecast_page.cogs_estimated'), value: costs.cogs },
    { key: 'rd', label: t('forecast_page.rd'), value: costs.rd },
    { key: 'marketing', label: t('forecast_page.marketing_distribution'), value: costs.marketing },
    { key: 'strategy', label: t('forecast_page.strategy'), value: costs.strategy },
    { key: 'admin', label: t('forecast_page.admin_overhead'), value: costs.admin },
    { key: 'entry', label: t('forecast_page.market_entry_costs'), value: costs.entry_costs },
    { key: 'interest', label: t('forecast_page.interest'), value: costs.interest },
    { key: 'tax', label: t('forecast_page.tax'), value: costs.tax },
  ];

  const totalCosts = Object.values(costs).reduce((s, v) => s + (v || 0), 0);

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', width: '100%' }}>
      <PageHeader
        title={t("forecast_page.title")}
        subtitle={`${t("common.round")} ${currentRound} · ${t("forecast_page.subtitle")}`}
      />

      {/* Revenue Projection */}
      <PanelCard headerColor="financial" title={t("forecast_page.revenue_projection").toUpperCase()} style={{ marginBottom: 16 }}>
        <Table
          dataSource={forecast.revenue_lines}
          columns={revenueColumns}
          rowKey={(r, i) => i}
          pagination={false}
          size="small"
          summary={() => (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={4}>
                <Text strong>{t("forecast_page.total_projected_revenue")}</Text>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={4}>
                <Text strong>{fmt(forecast.total_revenue)}</Text>
              </Table.Summary.Cell>
            </Table.Summary.Row>
          )}
        />
      </PanelCard>

      {/* Currency Scenarios */}
      {hasFxMarkets && (
        <PanelCard headerColor="market" title={t("forecast_page.currency_scenarios").toUpperCase()} style={{ marginBottom: 16 }}>
          {Object.entries(currencyMarkets).map(([code, info]) => {
            const adj = fxAdjustments[code] || 0;
            const baseRate = info.rate;
            const adjustedRate = (baseRate * (1 + adj / 100)).toFixed(4);
            const lineImpact = info.lines.reduce((s, l) => s + l.revenue * (adj / 100), 0);
            return (
              <div key={code} style={{ marginBottom: 16 }}>
                <Row align="middle" gutter={16}>
                  <Col flex="120px">
                    <Text strong>{code} rate:</Text>
                  </Col>
                  <Col flex="auto">
                    <Slider
                      min={-20} max={20} step={1}
                      value={adj}
                      onChange={v => setFxAdjustments(prev => ({ ...prev, [code]: v }))}
                      marks={{ '-20': '-20%', 0: 'current', 20: '+20%' }}
                      tooltip={{ formatter: v => `${v > 0 ? '+' : ''}${v}%` }}
                    />
                  </Col>
                  <Col flex="140px" style={{ textAlign: 'right' }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {baseRate.toFixed(4)} → {adjustedRate}
                    </Text>
                  </Col>
                </Row>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {t("forecast_page.impact_on_revenue")}:{' '}
                  <Text style={{ color: lineImpact > 0 ? '#3f8600' : lineImpact < 0 ? '#cf1322' : undefined }}>
                    {lineImpact >= 0 ? '+' : ''}{fmt(lineImpact)}
                  </Text>
                </Text>
              </div>
            );
          })}
          {fxRevenueImpact !== 0 && Object.keys(currencyMarkets).length > 1 && (
            <Divider style={{ margin: '8px 0' }} />
          )}
          {fxRevenueImpact !== 0 && (
            <Text strong>
              {t("forecast_page.total_fx_impact")}:{' '}
              <Text style={{ color: fxRevenueImpact > 0 ? '#3f8600' : '#cf1322' }}>
                {fxRevenueImpact >= 0 ? '+' : ''}{fmt(fxRevenueImpact)}
              </Text>
            </Text>
          )}
        </PanelCard>
      )}

      {/* Cost Projection */}
      <PanelCard headerColor="financial" title={t("forecast_page.cost_projection").toUpperCase()} style={{ marginBottom: 16 }}>
        {costItems.map(item => (
          item.value > 0 && (
            <div key={item.key} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <Text>{item.label}</Text>
              <Text>{fmt(item.value)}</Text>
            </div>
          )
        ))}
        <Divider style={{ margin: '8px 0' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Text strong>{t("forecast_page.total_costs").toUpperCase()}</Text>
          <Text strong>{fmt(totalCosts)}</Text>
        </div>
      </PanelCard>

      {/* Projected P&L */}
      <PanelCard headerColor="results" title={fxRevenueImpact !== 0 ? t('forecast_page.projected_pl_fx').toUpperCase() : t('forecast_page.projected_pl').toUpperCase()} style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}>
            <Statistic title={t("forecast_page.revenue")} value={fmt(forecast.total_revenue + fxRevenueImpact)} />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title={t("forecast_page.gross_profit")}
              value={fmt(forecast.gross_profit + fxRevenueImpact)}
              valueStyle={{ color: (forecast.gross_profit + fxRevenueImpact) >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title={t("forecast_page.operating_income")}
              value={fmt(forecast.operating_income + fxRevenueImpact)}
              valueStyle={{ color: (forecast.operating_income + fxRevenueImpact) >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Col>
          <Col xs={12} md={6}>
            <Statistic
              title={t("forecast_page.net_income")}
              value={fmt(forecast.projected_net_income + fxRevenueImpact * 0.79)}
              valueStyle={{ color: (forecast.projected_net_income + fxRevenueImpact * 0.79) >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Col>
        </Row>
        <Divider />
        <Row gutter={[16, 16]}>
          <Col xs={12} md={8}>
            <Statistic title={t("forecast_page.current_cash")} value={fmt(forecast.current_cash)} />
          </Col>
          <Col xs={12} md={8}>
            <Statistic
              title={t("forecast_page.projected_ending_cash")}
              value={fmt(forecast.projected_cash)}
              valueStyle={{ color: forecast.projected_cash >= 0 ? '#3f8600' : '#cf1322' }}
            />
          </Col>
          <Col xs={12} md={8}>
            <Statistic
              title={t("forecast_page.net_margin")}
              value={forecast.total_revenue > 0 ? ((forecast.projected_net_income / forecast.total_revenue) * 100).toFixed(1) : '—'}
              suffix="%"
            />
          </Col>
        </Row>
      </PanelCard>

      {/* Save Scenario */}
      <PanelCard headerColor="neutral" title={t("forecast_page.scenario_comparison").toUpperCase()} style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          <Input
            value={scenarioName}
            onChange={e => setScenarioName(e.target.value)}
            placeholder={t("forecast_page.scenario_placeholder")}
            style={{ flex: 1 }}
          />
          <Button
            type="primary"
            onClick={handleSaveScenario}
            loading={savingScenario}
            disabled={!scenarioName.trim()}
          >
            {t("forecast_page.save_scenario")}
          </Button>
        </div>

        {scenarios.length > 0 ? (
          scenarios.map(s => (
            <Card key={s.id} size="small" style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong>{s.name}</Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {new Date(s.created_at).toLocaleString()}
                </Text>
              </div>
              <div style={{ marginTop: 8 }}>
                <Tag>{t('forecast_page.col_revenue')}: {fmt(s.projected_results?.total_revenue)}</Tag>
                <Tag color={s.projected_results?.net_income >= 0 ? 'green' : 'red'}>
                  {t('forecast_page.net_income')}: {fmt(s.projected_results?.net_income)}
                </Tag>
                <Tag>{t('forecast_page.cash')}: {fmt(s.projected_results?.cash)}</Tag>
              </div>
            </Card>
          ))
        ) : (
          <Text type="secondary">{t("forecast_page.no_scenarios")}</Text>
        )}
      </PanelCard>
    </div>
  );
};

export default CompanyForecastPage;
