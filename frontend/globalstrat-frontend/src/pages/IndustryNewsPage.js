import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, Select, Tag, Typography, Row, Col, Statistic, Empty } from 'antd';
import { useGame } from '../contexts/GameContext';
import { getIndustryNews } from '../api/cc15';
import LoadingSpinner from '../components/LoadingSpinner';
import { PanelCard, PageHeader } from '../components/design-system';

const { Text, Paragraph } = Typography;

const severityColor = (s) => {
  if (s === 'critical') return 'red';
  if (s === 'high') return 'orange';
  if (s === 'medium') return 'gold';
  return 'green';
};

const IndustryNewsPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound } = useGame();
  const [selectedRound, setSelectedRound] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const roundOptions = [];
  for (let i = (currentRound || 1); i >= 0; i--) {
    roundOptions.push({ value: i, label: `${t('common.round')} ${i}` });
  }

  const fetchNews = useCallback(async (rnd) => {
    if (!gameId || !teamId) return;
    setLoading(true);
    try {
      const res = await getIndustryNews(gameId, teamId, rnd);
      setData(res.data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [gameId, teamId]);

  useEffect(() => {
    if (currentRound != null && selectedRound == null) {
      setSelectedRound(currentRound);
    }
  }, [currentRound, selectedRound]);

  useEffect(() => {
    if (selectedRound != null) fetchNews(selectedRound);
  }, [selectedRound, fetchNews]);

  if (loading) return <LoadingSpinner message={t("common.loading")} />;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', width: '100%' }}>
      <PageHeader
        title={t("industry_news.title")}
        subtitle={data?.headline || `${t('common.round')} ${selectedRound} ${t('industry_news.market_report')}`}
        actions={<Select value={selectedRound} onChange={setSelectedRound} options={roundOptions} style={{ width: 140 }} />}
      />

      {/* Events */}
      {data?.events?.length > 0 && (
        <PanelCard headerColor="market" title={t("industry_news.events").toUpperCase()}>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            {data.events.map((ev, i) => (
              <Col xs={24} md={12} key={i}>
                <Card size="small">
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <Text strong>{ev.name}</Text>
                    <Tag color={severityColor(ev.severity)}>{ev.severity}</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <Tag>{ev.category}</Tag>
                    <Tag>{ev.market}</Tag>
                  </div>
                  <Paragraph style={{ margin: 0, fontSize: 13 }}>{ev.narrative}</Paragraph>
                </Card>
              </Col>
            ))}
          </Row>
        </PanelCard>
      )}

      {/* Currency Alerts */}
      {data?.market_outlooks?.some(m => Math.abs(m.exchange_rate_change_pct || 0) > 0.01 && (m.currency_code || m.market_code) !== (data.home_currency_code || 'USD')) && (
        <PanelCard headerColor="financial" title={t("industry_news.currency_alerts").toUpperCase()}>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            {data.market_outlooks.filter(m => Math.abs(m.exchange_rate_change_pct || 0) > 0.01 && (m.currency_code || m.market_code) !== (data.home_currency_code || 'USD')).map((m, i) => {
              const pctChg = (m.exchange_rate_change_pct * 100).toFixed(1);
              const weakened = m.exchange_rate_change_pct < 0;
              const homeCurrency = data.home_currency_code || 'USD';
              return (
                <Col xs={24} md={12} key={i}>
                  <Card size="small" style={{ borderLeft: `3px solid ${weakened ? '#cf1322' : '#3f8600'}` }}>
                    <Text strong>{t('industry_news.currency_alert')} — {m.market}</Text>
                    <Paragraph style={{ margin: '8px 0 0', fontSize: 13 }}>
                      {weakened
                        ? t('industry_news.currency_weakened', { currency: m.currency_code || m.market_code, pct: Math.abs(pctChg), homeCurrency })
                        : t('industry_news.currency_strengthened', { currency: m.currency_code || m.market_code, pct: Math.abs(pctChg), homeCurrency })}
                    </Paragraph>
                  </Card>
                </Col>
              );
            })}
          </Row>
        </PanelCard>
      )}

      {/* Market Outlook */}
      <PanelCard headerColor="market" title={t("industry_news.market_outlook").toUpperCase()}>
        {data?.market_outlooks?.length > 0 ? (
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            {data.market_outlooks.map((mkt, i) => (
              <Col xs={24} md={8} key={i}>
                <Card
                  size="small"
                  title={
                    <span>
                      {mkt.market}
                      <Tag style={{ marginLeft: 8 }}>{mkt.market_code}</Tag>
                    </span>
                  }
                >
                  <Row gutter={16}>
                    <Col span={8}>
                      <Statistic
                        title={t("industry_news.growth")}
                        value={(mkt.growth_rate * 100).toFixed(1)}
                        suffix="%"
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title={t("industry_news.tariff")}
                        value={(mkt.tariff_rate * 100).toFixed(1)}
                        suffix="%"
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title={`${t('industry_news.fx')} (${mkt.currency_code || ''})`}
                        value={mkt.exchange_rate.toFixed(4)}
                        valueStyle={{ fontSize: 14, color: (mkt.exchange_rate_change_pct || 0) < -0.01 ? '#cf1322' : (mkt.exchange_rate_change_pct || 0) > 0.01 ? '#3f8600' : undefined }}
                        suffix={mkt.exchange_rate_change_pct ? `(${(mkt.exchange_rate_change_pct * 100) > 0 ? '+' : ''}${(mkt.exchange_rate_change_pct * 100).toFixed(1)}%)` : ''}
                      />
                    </Col>
                  </Row>
                  {mkt.narrative && (
                    <Paragraph style={{ marginTop: 12, fontSize: 13 }}>
                      {mkt.narrative}
                    </Paragraph>
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        ) : (
          <Empty description={t("industry_news.no_market_outlook")} />
        )}
      </PanelCard>

      {/* Intelligence Briefs */}
      {data?.intelligence_briefs?.length > 0 && (
        <PanelCard headerColor="strategic" title={t("industry_news.intelligence_briefs").toUpperCase()}>
          <Row gutter={[16, 16]}>
            {data.intelligence_briefs.map((brief, i) => (
              <Col xs={24} md={12} key={i}>
                <Card size="small">
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <Text strong>{brief.market}</Text>
                    <Tag color={brief.level === 'detailed' ? 'blue' : brief.level === 'standard' ? 'cyan' : 'default'}>
                      {brief.level}
                    </Tag>
                  </div>
                  <Paragraph style={{ margin: 0, fontSize: 13 }}>{brief.content}</Paragraph>
                </Card>
              </Col>
            ))}
          </Row>
        </PanelCard>
      )}
    </div>
  );
};

export default IndustryNewsPage;
