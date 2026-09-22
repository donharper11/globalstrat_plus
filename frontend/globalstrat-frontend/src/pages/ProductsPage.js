import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Typography, Button, Tag, Modal, Form, Input, Select, Radio,
  Space, Alert, Table, Descriptions, Tooltip,
} from 'antd';
import { useGame } from '../contexts/GameContext';
import { useDecisions, describeRefusal } from '../contexts/DecisionContext';
import { reportUnpublishedFailure } from '../api/saveFailures';
import { getProductContext, patchDecision } from '../api/decisions';
import LoadingSpinner from '../components/LoadingSpinner';
import WarningBanner from '../components/WarningBanner';
import { PanelCard, PageHeader, StatusBadge } from '../components/design-system';

const { Title, Text } = Typography;

const positionColors = {
  budget: 'green', mainstream: 'blue', premium: 'purple', ultra_premium: 'gold',
};

const positionLabelKeys = {
  budget: 'products_page.pos_budget', mainstream: 'products_page.pos_mainstream', premium: 'products_page.pos_premium', ultra_premium: 'products_page.pos_ultra_premium',
};

/** "Not saved", with the server's sentences, inside a modal. */
const RefusalNotice = ({ sentences }) => {
  const { t } = useTranslation();
  return (
    <Alert
      type="error"
      showIcon
      style={{ marginBottom: 12 }}
      message={t('decision_save.not_saved_title')}
      description={sentences.length
        ? <ul style={{ margin: 0, paddingLeft: 18 }}>{sentences.map((msg, i) => <li key={i}>{msg}</li>)}</ul>
        : t('decision_save.network_failed')}
    />
  );
};

const ProductsPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { draft, locked, loadDraft } = useDecisions();
  const [context, setContext] = useState(null);
  // The server's own sentences for a refused create or retire, shown
  // inside the open modal: the shared notice sits behind it.
  const [refusal, setRefusal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  // R48 item 9: products are fixed once created. The product open in the
  // modal can be retired; there is no edit path (the one there was sent an
  // id of the product to change, which the server drops, so it never once
  // succeeded).
  const [retireProduct, setRetireProduct] = useState(null);
  const [createForm] = Form.useForm();

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const res = await getProductContext(gameId, teamId);
      setContext(res.data);
    } catch { /* a read; the page shows it could not load */ }
    setLoading(false);
  }, [gameId, teamId]);

  /**
   * After a save lands. Every save below re-sends the WHOLE section built
   * from `draft`, so the draft must be re-read before the next one, or a
   * second product created in one sitting is sent as [second] and replaces
   * the first (2026-09-21).
   */
  const afterSave = useCallback(async () => {
    setRefusal(null);
    await Promise.all([loadDraft(), loadContext()]);
    refreshBudgets();
  }, [loadDraft, loadContext, refreshBudgets]);

  const onRefused = useCallback((err) => {
    // Announced to the shared notice by the interceptor; this covers a
    // failure that never became a request, and shows the sentences here.
    reportUnpublishedFailure(err);
    setRefusal(describeRefusal(err?.response?.data));
  }, []);

  useEffect(() => { loadContext(); }, [loadContext]);

  // ── Create ──
  const handleCreate = async (values) => {
    if (!gameId || !teamId || !currentRound) return;
    try {
      const existing = draft?.product_creates || [];
      await patchDecision(gameId, teamId, currentRound, 'products', {
        product_creates: [...existing, {
          team_platform: values.platform,
          product_name: values.name,
          positioning: values.positioning,
          target_market_ids: values.markets,
        }],
      });
      setShowCreate(false);
      createForm.resetFields();
      await afterSave();
    } catch (err) {
      onRefused(err);
    }
  };

  // ── Retire (open modal) ──
  const openRetire = (product) => {
    setRefusal(null);
    setRetireProduct(product);
  };

  const closeRetire = () => { setRetireProduct(null); setRefusal(null); };

  // ── Retire ──
  const handleRetire = async (timing) => {
    if (!gameId || !teamId || !currentRound || !retireProduct) return;
    try {
      const existing = draft?.product_retires || [];
      await patchDecision(gameId, teamId, currentRound, 'product-retires', {
        product_retires: [...existing, {
          team_product: retireProduct.id,
          timing,
        }],
      });
      setRetireProduct(null);
      await afterSave();
    } catch (err) {
      onRefused(err);
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!context) return <Alert message={t("products_page.unable_to_load")} type="error" />;

  const products = context.products || [];
  const platforms = context.active_platforms || [];
  const markets = context.active_markets || [];
  const maxTotal = context.max_products_total || 6;
  const currentCount = context.active_product_count || products.length;

  // Build feature columns dynamically from all products' feature levels
  const featureSet = new Set();
  products.forEach(p => {
    (p.feature_levels || []).forEach(f => featureSet.add(f.feature_code));
  });
  const featureCodes = [...featureSet].sort();

  // Build a lookup: product_id → { feature_code: level }
  const featureLookup = {};
  products.forEach(p => {
    const map = {};
    (p.feature_levels || []).forEach(f => { map[f.feature_code] = f.current_level; });
    featureLookup[p.id] = map;
  });

  // Feature name lookup
  const featureNameMap = {};
  products.forEach(p => {
    (p.feature_levels || []).forEach(f => { featureNameMap[f.feature_code] = f.feature_name; });
  });

  const columns = [
    {
      title: t('products_page.col_product'),
      dataIndex: 'name',
      fixed: 'left',
      width: 150,
      render: (name, r) => (
        <div>
          <Text strong>{name}</Text>
          {r.status === 'retired' && <StatusBadge status="retired" />}
        </div>
      ),
    },
    {
      title: t('products_page.col_positioning'),
      dataIndex: 'positioning',
      width: 110,
      render: v => <StatusBadge status={v} label={t(positionLabelKeys[v]) || v} />,
    },
    {
      title: t('products_page.col_platform'),
      dataIndex: 'platform_name',
      width: 100,
      render: v => <Tag>{v}</Tag>,
    },
    ...featureCodes.map(code => ({
      title: (featureNameMap[code] || code).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      key: code,
      width: 80,
      align: 'center',
      render: (_, r) => {
        const lvl = featureLookup[r.id]?.[code];
        return lvl != null ? (
          <Text style={{ fontWeight: 500 }}>{lvl.toFixed(1)}</Text>
        ) : '—';
      },
    })),
    {
      title: t('products_page.col_est_unit_cost'),
      dataIndex: 'est_unit_cost',
      width: 100,
      align: 'right',
      render: v => v != null ? `$${Number(v).toFixed(0)}` : '—',
      sorter: (a, b) => (a.est_unit_cost || 0) - (b.est_unit_cost || 0),
    },
    {
      title: t('products_page.col_retail_price'),
      key: 'retail_price',
      width: 110,
      align: 'right',
      render: (_, r) => {
        const prices = r.retail_prices || {};
        const vals = Object.values(prices);
        if (vals.length === 0) return <Text type="secondary">{t("products_page.not_set")}</Text>;
        if (vals.length === 1) return `$${Number(vals[0]).toFixed(0)}`;
        const min = Math.min(...vals);
        const max = Math.max(...vals);
        return min === max ? `$${min.toFixed(0)}` : `$${min.toFixed(0)}–$${max.toFixed(0)}`;
      },
    },
    {
      title: '',
      key: 'actions',
      width: 90,
      align: 'center',
      render: (_, r) => (
        !locked && r.status === 'active' ? (
          <Button
            type="link" size="small" danger
            onClick={(e) => { e.stopPropagation(); openRetire(r); }}
          >
            {t("products_page.retire_product")}
          </Button>
        ) : null
      ),
    },
  ];

  // Expandable row: show markets/regions
  const expandedRowRender = (record) => {
    const activeMarkets = (record.markets || []).filter(m => m.is_active);
    const inactiveMarkets = (record.markets || []).filter(m => !m.is_active);
    const prices = record.retail_prices || {};
    return (
      <div style={{ padding: '4px 0' }}>
        <Space wrap>
          <Text type="secondary" style={{ fontSize: 12 }}>{t("products_page.markets")}:</Text>
          {activeMarkets.map(m => (
            <Tag key={m.market_id} color="blue">
              {m.market__name || m.market_name}
              {prices[m.market_id] != null && ` · $${Number(prices[m.market_id]).toFixed(0)}`}
            </Tag>
          ))}
          {inactiveMarkets.map(m => (
            <Tag key={m.market_id} color="default" style={{ textDecoration: 'line-through' }}>
              {m.market__name || m.market_name}
            </Tag>
          ))}
          {activeMarkets.length === 0 && <Text type="secondary">{t("products_page.no_active_markets")}</Text>}
        </Space>
      </div>
    );
  };

  return (
    <div>
      <PageHeader
        title={t("products_page.title")}
        subtitle={`${t("common.round")} ${currentRound} · ${currentCount} / ${maxTotal} ${t("products_page.products_label")}`}
        status={locked ? 'locked' : 'draft'}
        actions={
          <Button
            type="primary"
            disabled={locked || currentCount >= maxTotal}
            onClick={() => setShowCreate(true)}
          >
            {t("products_page.create_new_product")}
          </Button>
        }
      />

      {currentCount >= maxTotal - 1 && (
        <WarningBanner message={t("products_page.product_approaching_max", { current: currentCount, max: maxTotal })} />
      )}

      <PanelCard headerColor="decision" title={t("products_page.your_products").toUpperCase()}>
        <Table
          dataSource={products}
          rowKey="id"
          columns={columns}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
          expandable={{
            expandedRowRender,
            defaultExpandAllRows: true,
          }}
          onRow={(record) => ({
            style: { opacity: record.status === 'retired' ? 0.5 : 1 },
          })}
        />
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>{t("products_page.fixed_once_created")}</Text>
        </div>
      </PanelCard>

      {/* ── Create Modal ── */}
      <Modal
        title={t("products_page.create_new_product")}
        open={showCreate}
        onCancel={() => { setShowCreate(false); createForm.resetFields(); setRefusal(null); }}
        onOk={() => createForm.submit()}
        okText={t("products_page.create")}
      >
        {refusal && <RefusalNotice sentences={refusal} />}
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label={t("products_page.product_name")} rules={[{ required: true }]}>
            <Input placeholder={t('products_page.name_placeholder')} />
          </Form.Item>
          <Form.Item name="platform" label={t("products_page.parent_platform")} rules={[{ required: true }]}>
            <Select placeholder={t("products_page.select_platform")}>
              {platforms.map(pl => (
                <Select.Option key={pl.id} value={pl.id}>{pl.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="positioning" label={t("products_page.positioning")} rules={[{ required: true }]}>
            <Radio.Group>
              <Radio.Button value="budget">{t('products_page.pos_budget')}</Radio.Button>
              <Radio.Button value="mainstream">{t('products_page.pos_mainstream')}</Radio.Button>
              <Radio.Button value="premium">{t('products_page.pos_premium')}</Radio.Button>
              <Radio.Button value="ultra_premium">{t('products_page.pos_ultra_premium')}</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="markets" label={t("products_page.target_markets")} rules={[{ required: true }]}>
            <Select mode="multiple" placeholder={t("products_page.select_markets")}>
              {markets.map(m => (
                <Select.Option key={m.id} value={m.id}>{m.name}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Retire Modal ── */}
      <Modal
        title={`${retireProduct?.name || ''}`}
        open={!!retireProduct}
        onCancel={closeRetire}
        width={640}
        footer={[
          <Button key="cancel" onClick={closeRetire}>
            {t("common.cancel")}
          </Button>,
          <Tooltip key="retire-now" title={t("products_page.retire_immediate_tooltip")}>
            <Button danger onClick={() => handleRetire('immediate')}>
              {t("products_page.retire_immediately")}
            </Button>
          </Tooltip>,
          <Tooltip key="retire-eor" title={t("products_page.retire_eor_tooltip")}>
            <Button onClick={() => handleRetire('end_of_round')}>
              {t("products_page.retire_end_of_round")}
            </Button>
          </Tooltip>,
        ]}
      >
        {refusal && <RefusalNotice sentences={refusal} />}
        {retireProduct && (
          <Descriptions size="small" column={2}>
            <Descriptions.Item label={t("products_page.col_platform")}>
              {retireProduct.platform_name}
            </Descriptions.Item>
            <Descriptions.Item label={t("products_page.col_est_unit_cost")}>
              ${retireProduct.est_unit_cost?.toFixed(0) || '—'}
            </Descriptions.Item>
            <Descriptions.Item label={t("products_page.active_markets")}>
              <Space wrap>
                {(retireProduct.markets || []).filter(m => m.is_active).map(m => (
                  <Tag key={m.market_id}>{m.market__name || m.market_name}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label={t("products_page.features")} span={2}>
              <Space wrap>
                {(retireProduct.feature_levels || []).map(f => (
                  <Tag key={f.feature_code}>
                    {f.feature_name}: {f.current_level.toFixed(1)}
                  </Tag>
                ))}
              </Space>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default ProductsPage;
