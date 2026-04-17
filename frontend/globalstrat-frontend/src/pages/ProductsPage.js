import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Typography, Button, Tag, Modal, Form, Input, Select, Radio,
  Space, Alert, Table, Checkbox, Descriptions, Tooltip,
} from 'antd';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faEdit } from '@fortawesome/free-solid-svg-icons';
import { useGame } from '../contexts/GameContext';
import { useDecisions } from '../contexts/DecisionContext';
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

const ProductsPage = () => {
  const { t } = useTranslation();
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { draft, locked } = useDecisions();
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editProduct, setEditProduct] = useState(null);
  const [editForm] = Form.useForm();
  const [createForm] = Form.useForm();

  const loadContext = useCallback(async () => {
    if (!gameId || !teamId) { setLoading(false); return; }
    try {
      const res = await getProductContext(gameId, teamId);
      setContext(res.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [gameId, teamId]);

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
      loadContext();
      refreshBudgets();
    } catch { /* ignore */ }
  };

  // ── Edit (open modal) ──
  const openEdit = (product) => {
    setEditProduct(product);
    const activeMarketIds = (product.markets || [])
      .filter(m => m.is_active)
      .map(m => m.market_id);
    editForm.setFieldsValue({
      name: product.name,
      platform: product.platform_id,
      positioning: product.positioning,
      markets: activeMarketIds,
    });
  };

  // ── Save edits ──
  const handleEditSave = async (values) => {
    if (!gameId || !teamId || !currentRound || !editProduct) return;
    try {
      // Product creates for modifications — we update by sending the full list
      // with this product's changes applied
      const existingCreates = draft?.product_creates || [];
      const existingRetires = draft?.product_retires || [];

      // Check if this is a pending create (not yet persisted)
      const pendingIdx = existingCreates.findIndex(
        c => c.product_name === editProduct.name && c.team_platform === editProduct.platform_id
      );

      if (pendingIdx >= 0) {
        // Update the pending create
        const updated = [...existingCreates];
        updated[pendingIdx] = {
          ...updated[pendingIdx],
          team_platform: values.platform,
          product_name: values.name,
          positioning: values.positioning,
          target_market_ids: values.markets,
        };
        await patchDecision(gameId, teamId, currentRound, 'products', {
          product_creates: updated,
        });
      } else {
        // For existing products, we re-submit with updated fields
        await patchDecision(gameId, teamId, currentRound, 'products', {
          product_creates: [...existingCreates, {
            team_platform: values.platform,
            product_name: values.name,
            positioning: values.positioning,
            target_market_ids: values.markets,
            existing_product_id: editProduct.id,
          }],
          product_retires: existingRetires,
        });
      }
      setEditProduct(null);
      editForm.resetFields();
      loadContext();
      refreshBudgets();
    } catch { /* ignore */ }
  };

  // ── Retire ──
  const handleRetire = async (timing) => {
    if (!gameId || !teamId || !currentRound || !editProduct) return;
    try {
      const existing = draft?.product_retires || [];
      await patchDecision(gameId, teamId, currentRound, 'product-retires', {
        product_retires: [...existing, {
          team_product: editProduct.id,
          timing,
        }],
      });
      setEditProduct(null);
      editForm.resetFields();
      loadContext();
    } catch { /* ignore */ }
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
      width: 50,
      align: 'center',
      render: (_, r) => (
        !locked && r.status === 'active' ? (
          <Tooltip title={t("products_page.edit_product")}>
            <Button
              type="text" size="small"
              icon={<FontAwesomeIcon icon={faEdit} style={{ color: '#1677ff' }} />}
              onClick={(e) => { e.stopPropagation(); openEdit(r); }}
            />
          </Tooltip>
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
            onClick: () => { if (!locked && record.status === 'active') openEdit(record); },
            style: {
              cursor: (!locked && record.status === 'active') ? 'pointer' : 'default',
              opacity: record.status === 'retired' ? 0.5 : 1,
            },
          })}
        />
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>{t("products_page.click_to_edit")}</Text>
        </div>
      </PanelCard>

      {/* ── Create Modal ── */}
      <Modal
        title={t("products_page.create_new_product")}
        open={showCreate}
        onCancel={() => { setShowCreate(false); createForm.resetFields(); }}
        onOk={() => createForm.submit()}
        okText={t("products_page.create")}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label={t("products_page.product_name")} rules={[{ required: true }]}>
            <Input placeholder="e.g. Nexus Pro" />
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

      {/* ── Edit / Retire Modal ── */}
      <Modal
        title={`${editProduct?.name || ''}`}
        open={!!editProduct}
        onCancel={() => { setEditProduct(null); editForm.resetFields(); }}
        width={640}
        footer={[
          <Button key="cancel" onClick={() => { setEditProduct(null); editForm.resetFields(); }}>
            {t("common.cancel")}
          </Button>,
          <Tooltip title={t("products_page.retire_immediate_tooltip")}>
            <Button key="retire-now" danger onClick={() => handleRetire('immediate')}>
              {t("products_page.retire_immediately")}
            </Button>
          </Tooltip>,
          <Tooltip title={t("products_page.retire_eor_tooltip")}>
            <Button key="retire-eor" onClick={() => handleRetire('end_of_round')}>
              {t("products_page.retire_end_of_round")}
            </Button>
          </Tooltip>,
          <Button key="save" type="primary" onClick={() => editForm.submit()}>
            {t("products_page.save_changes")}
          </Button>,
        ]}
      >
        {editProduct && (
          <>
            <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
              <Descriptions.Item label={t("products_page.col_est_unit_cost")}>
                ${editProduct.est_unit_cost?.toFixed(0) || '—'}
              </Descriptions.Item>
              <Descriptions.Item label={t("products_page.features")}>
                <Space wrap>
                  {(editProduct.feature_levels || []).map(f => (
                    <Tag key={f.feature_code}>
                      {f.feature_name}: {f.current_level.toFixed(1)}
                    </Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            </Descriptions>

            <Form form={editForm} layout="vertical" onFinish={handleEditSave}>
              <Form.Item name="name" label={t("products_page.product_name")} rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item name="platform" label={t("products_page.base_platform")} rules={[{ required: true }]}>
                <Select>
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
              <Form.Item name="markets" label={t("products_page.active_markets")} rules={[{ required: true }]}>
                <Checkbox.Group>
                  <Space direction="vertical">
                    {markets.map(m => (
                      <Checkbox key={m.id} value={m.id}>{m.name}</Checkbox>
                    ))}
                  </Space>
                </Checkbox.Group>
              </Form.Item>
            </Form>
          </>
        )}
      </Modal>
    </div>
  );
};

export default ProductsPage;
