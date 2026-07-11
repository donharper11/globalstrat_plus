import React, { useState, useEffect } from 'react';
import { Layout, Menu, Badge } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faTachometerAlt, faFlask, faCubes, faBullhorn, faBuilding, faGlobe,
  faDollarSign, faClipboardCheck, faChartBar, faTrophy,
  faGamepad, faGraduationCap,
  faNewspaper, faSearch, faEye, faWrench, faFileInvoiceDollar, faChartLine, faBell,
  faHome, faEdit, faIndustry, faTruck, faMoneyBillWave, faBoxesStacked,
} from '@fortawesome/free-solid-svg-icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import { useGame } from '../contexts/GameContext';
import { getDecisionSummary } from '../api/decisions';

const { Sider } = Layout;

const icon = (fa) => <FontAwesomeIcon icon={fa} style={{ width: 14, marginRight: 8 }} />;

const statusIcon = (status) => {
  if (status === 'configured') return <Badge status="success" />;
  if (status === 'partial') return <Badge status="warning" />;
  if (status === 'error') return <Badge status="error" />;
  return <Badge status="default" />;
};

const Sidebar = ({ collapsed, onNavigate }) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { gameId, teamId, currentRound, sidebarLabels: rawSidebarLabels } = useGame();
  // Only use API sidebar labels when in English — in zh-CN mode, t() provides the translation
  const sidebarLabels = i18n.language === 'zh-CN' ? null : rawSidebarLabels;
  const [categoryStatus, setCategoryStatus] = useState({});

  const go = (path) => {
    navigate(path);
    if (onNavigate) onNavigate();
  };

  const teamName = user?.team_name || '—';
  const homeMarketName = user?.home_market_name;
  const base = gameId && teamId ? `/games/${gameId}/teams/${teamId}` : '';

  // Fetch decision summary for sidebar status indicators
  useEffect(() => {
    if (!gameId || !teamId || !currentRound) return;
    getDecisionSummary(gameId, teamId, currentRound)
      .then(res => {
        const cats = res.data?.categories || {};
        const statuses = {};
        Object.entries(cats).forEach(([key, val]) => {
          statuses[key] = val.status || 'empty';
        });
        setCategoryStatus(statuses);
      })
      .catch(() => {});
  }, [gameId, teamId, currentRound]);

  const pathname = location.pathname;
  let selectedKey = '';
  if (pathname === '/' || pathname === '/dashboard') selectedKey = 'dashboard';
  else if (pathname.includes('/decisions/sourcing')) selectedKey = 'sourcing';
  else if (pathname.includes('/decisions/logistics')) selectedKey = 'logistics';
  else if (pathname.includes('/decisions/trade-finance')) selectedKey = 'trade-finance';
  else if (pathname.includes('/decisions/inventory')) selectedKey = 'inventory';
  else if (pathname.includes('/decisions/rd')) selectedKey = 'rd';
  else if (pathname.includes('/decisions/products')) selectedKey = 'products';
  else if (pathname.includes('/decisions/marketing')) selectedKey = 'marketing';
  else if (pathname.includes('/decisions/corporate-strategy')) selectedKey = 'corporate-strategy';
  else if (pathname.includes('/decisions/market-strategy')) selectedKey = 'market-strategy';
  else if (pathname.includes('/decisions/finance')) selectedKey = 'finance';
  else if (pathname.includes('/decisions/communications')) selectedKey = 'communications';
  else if (pathname.includes('/decisions/summary')) selectedKey = 'summary';
  else if (pathname.includes('/news')) selectedKey = 'news';
  else if (pathname.includes('/research')) selectedKey = 'research';
  else if (pathname.includes('/competitors')) selectedKey = 'competitors';
  else if (pathname.includes('/tools')) selectedKey = 'tools';
  else if (pathname.includes('/financial-reports')) selectedKey = 'financial-reports';
  else if (pathname.includes('/team-activity')) selectedKey = 'team-activity';
  else if (pathname.includes('/forecast')) selectedKey = 'forecast';
  else if (pathname.includes('/results')) selectedKey = 'results';
  else if (pathname.includes('/leaderboard')) selectedKey = 'leaderboard';
  else if (pathname.includes('/instructor')) selectedKey = 'instructor';

  const canLock = Object.values(categoryStatus).length > 0 &&
    !Object.values(categoryStatus).includes('error');

  const menuItems = [
    {
      key: 'dashboard',
      icon: icon(faTachometerAlt),
      label: t('nav.dashboard'),
      onClick: () => go('/'),
    },
    { type: 'divider' },
    {
      key: 'info-group',
      icon: icon(faNewspaper),
      label: t('nav.information'),
      children: [
        {
          key: 'financial-reports',
          icon: icon(faFileInvoiceDollar),
          label: sidebarLabels?.financial_reports || t('nav.financial_reports'),
          onClick: () => go(`${base}/financial-reports`),
        },
        {
          key: 'news',
          icon: icon(faNewspaper),
          label: sidebarLabels?.news_page || t('nav.industry_news'),
          onClick: () => go(`${base}/news`),
        },
        {
          key: 'research',
          icon: icon(faSearch),
          label: sidebarLabels?.research_page || t('nav.market_research'),
          onClick: () => go(`${base}/research`),
        },
        {
          key: 'competitors',
          icon: icon(faEye),
          label: sidebarLabels?.competitors_page || t('nav.competitive_intelligence'),
          onClick: () => go(`${base}/competitors`),
        },
        {
          key: 'tools',
          icon: icon(faWrench),
          label: sidebarLabels?.tools_page || t('nav.strategy_tools'),
          onClick: () => go(`${base}/tools`),
        },
      ],
    },
    { type: 'divider' },
    {
      key: 'decisions-group',
      icon: icon(faClipboardCheck),
      label: t('nav.decisions'),
      children: [
        {
          key: 'sourcing',
          icon: icon(faIndustry),
          label: <span>{sidebarLabels?.sourcing_page || 'Sourcing'} {statusIcon(categoryStatus.sourcing)}</span>,
          onClick: () => go(`${base}/decisions/sourcing`),
        },
        {
          key: 'logistics',
          icon: icon(faTruck),
          label: <span>{sidebarLabels?.logistics_page || 'Logistics'} {statusIcon(categoryStatus.logistics)}</span>,
          onClick: () => go(`${base}/decisions/logistics`),
        },
        {
          key: 'trade-finance',
          icon: icon(faMoneyBillWave),
          label: <span>{sidebarLabels?.trade_finance_page || 'Trade Finance'} {statusIcon(categoryStatus.trade_finance)}</span>,
          onClick: () => go(`${base}/decisions/trade-finance`),
        },
        {
          key: 'inventory',
          icon: icon(faBoxesStacked),
          label: <span>{sidebarLabels?.inventory_page || 'Inventory'} {statusIcon(categoryStatus.inventory)}</span>,
          onClick: () => go(`${base}/decisions/inventory`),
        },
        {
          key: 'rd',
          icon: icon(faFlask),
          label: (
            <span>{sidebarLabels?.platform_page || t('nav.rd_investment')} {statusIcon(categoryStatus.rd)}</span>
          ),
          onClick: () => go(`${base}/decisions/rd`),
        },
        {
          key: 'products',
          icon: icon(faCubes),
          label: (
            <span>{sidebarLabels?.product_page || t('nav.product_portfolio')} {statusIcon(categoryStatus.products)}</span>
          ),
          onClick: () => go(`${base}/decisions/products`),
        },
        {
          key: 'marketing',
          icon: icon(faBullhorn),
          label: (
            <span>{sidebarLabels?.marketing_page || t('nav.marketing_mix')} {statusIcon(categoryStatus.marketing)}</span>
          ),
          onClick: () => go(`${base}/decisions/marketing`),
        },
        {
          key: 'corporate-strategy',
          icon: icon(faBuilding),
          label: (
            <span>{sidebarLabels?.corporate_strategy || t('nav.corporate_strategy')} {statusIcon(categoryStatus.strategy)}</span>
          ),
          onClick: () => go(`${base}/decisions/corporate-strategy`),
        },
        {
          key: 'market-strategy',
          icon: icon(faGlobe),
          label: (
            <span>{sidebarLabels?.market_strategy || t('nav.market_strategy')} {statusIcon(categoryStatus.strategy)}</span>
          ),
          onClick: () => go(`${base}/decisions/market-strategy`),
        },
        {
          key: 'finance',
          icon: icon(faDollarSign),
          label: (
            <span>{sidebarLabels?.finance_page || t('nav.finance')} {statusIcon(categoryStatus.financing || categoryStatus.budget)}</span>
          ),
          onClick: () => go(`${base}/decisions/finance`),
        },
        {
          key: 'forecast',
          icon: icon(faChartLine),
          label: sidebarLabels?.forecast_page || t('nav.company_forecast'),
          onClick: () => go(`${base}/forecast`),
        },
        {
          key: 'communications',
          icon: icon(faEdit),
          label: t('nav.communications'),
          onClick: () => go(`${base}/decisions/communications`),
        },
        { type: 'divider' },
        {
          key: 'summary',
          icon: icon(faClipboardCheck),
          label: (
            <span>{t('nav.review_submit')} {canLock ? <Badge status="success" /> : <Badge status="default" />}</span>
          ),
          onClick: () => go(`${base}/decisions/summary`),
        },
      ],
    },
    { type: 'divider' },
    {
      key: 'results-group',
      icon: icon(faChartBar),
      label: t('nav.results'),
      children: [
        {
          key: 'leaderboard',
          icon: icon(faTrophy),
          label: t('nav.leaderboard'),
          onClick: () => go('/leaderboard'),
        },
        {
          key: 'team-activity',
          icon: icon(faBell),
          label: t('nav.team_activity'),
          onClick: () => go(`${base}/team-activity`),
        },
      ],
    },
  ];

  // Add instructor section if user has instructor/admin role
  const role = (user?.role || '').toLowerCase();
  if (role === 'instructor' || role === 'admin') {
    menuItems.push(
      { type: 'divider' },
      {
        key: 'instructor-group',
        icon: icon(faGraduationCap),
        label: t('nav.instructor'),
        children: [
          {
            key: 'instructor',
            icon: icon(faGamepad),
            label: t('nav.game_control'),
            onClick: () => go(gameId ? `/games/${gameId}/instructor` : '/'),
          },
        ],
      },
    );
  }

  return (
    <Sider
      trigger={null}
      collapsible
      collapsed={collapsed}
      width={250}
      collapsedWidth={64}
      className="ds-sidebar"
      style={{
        overflow: 'auto',
        height: 'calc(100vh - 56px)',
        position: 'sticky',
        top: 56,
        left: 0,
        background: 'var(--color-surface-800)',
      }}
    >
      {!collapsed && (
        <div className="ds-sidebar-header">
          <span className="ds-sidebar-meta" style={{ fontWeight: 600, fontSize: 13 }}>
            {teamName}
          </span>
          {homeMarketName && (
            <span className="ds-sidebar-meta" style={{ fontSize: 11, opacity: 0.85, display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
              <FontAwesomeIcon icon={faHome} style={{ width: 10 }} />
              {homeMarketName}
            </span>
          )}
          <span className="ds-sidebar-round">
            <span className="ds-sidebar-round-dot" />
            {t('common.round')} {currentRound || '—'}
          </span>
        </div>
      )}
      {collapsed && (
        <div style={{ padding: '12px 0', textAlign: 'center', borderBottom: '1px solid var(--color-surface-700)' }}>
          <span className="ds-sidebar-round" style={{ padding: '3px 6px', fontSize: 11 }}>
            R{currentRound || '—'}
          </span>
        </div>
      )}
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selectedKey]}
        defaultOpenKeys={collapsed ? [] : ['info-group', 'decisions-group', 'results-group', 'instructor-group']}
        items={menuItems}
        style={{ borderRight: 0 }}
      />
    </Sider>
  );
};

export default Sidebar;
