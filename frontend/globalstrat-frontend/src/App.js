import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider, Layout, Drawer } from 'antd';
import { AuthProvider } from './AuthContext';
import { GameProvider } from './contexts/GameContext';
import { DecisionProvider } from './contexts/DecisionContext';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import { DSTopBar } from './components/design-system';
import BudgetAlert from './components/BudgetAlert';
import DemoBanner from './components/DemoBanner';
import NewsTicker from './components/NewsTicker';
import themeConfig from './theme/themeConfig';

import './components/design-system/theme.css';
import './components/design-system/design-system.css';

import LoginPage from './pages/LoginPage';
import InstructorLoginPage from './pages/InstructorLoginPage';
import GameDashboard from './pages/GameDashboard';
import RDPage from './pages/RDPage';
import ProductsPage from './pages/ProductsPage';
import MarketingPage from './pages/MarketingPage';
import CorporateStrategyPage from './pages/CorporateStrategyPage';
import MarketStrategyPage from './pages/MarketStrategyPage';
import SourcingPage from './pages/SourcingPage';
import LogisticsPage from './pages/LogisticsPage';
import TradeFinancePage from './pages/TradeFinancePage';
import FinancePage from './pages/FinancePage';
import SummaryPage from './pages/SummaryPage';
import LeaderboardPage from './pages/LeaderboardPage';
import InstructorDashboard from './pages/InstructorDashboard';
import IndustryNewsPage from './pages/IndustryNewsPage';
import MarketResearchPage from './pages/MarketResearchPage';
import CompetitiveIntelPage from './pages/CompetitiveIntelPage';
import StrategyToolsPage from './pages/StrategyToolsPage';
import FinancialReportsPage from './pages/FinancialReportsPage';
import CompanyForecastPage from './pages/CompanyForecastPage';
import TeamActivityPage from './pages/TeamActivityPage';
import CommunicationsPage from './pages/CommunicationsPage';

const { Content } = Layout;

const P = ({ children }) => <ProtectedRoute>{children}</ProtectedRoute>;
const InstructorP = ({ children }) => <ProtectedRoute redirectTo="/instructor/login" requiredRole={['instructor', 'admin']}>{children}</ProtectedRoute>;

const MOBILE_BREAKPOINT = 768;

function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < MOBILE_BREAKPOINT);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleResize = useCallback(() => {
    const mobile = window.innerWidth < MOBILE_BREAKPOINT;
    setIsMobile(mobile);
    if (!mobile) setDrawerOpen(false);
  }, []);

  useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [handleResize]);

  const handleToggle = () => {
    if (isMobile) {
      setDrawerOpen(!drawerOpen);
    } else {
      setCollapsed(!collapsed);
    }
  };

  const handleDrawerClose = () => setDrawerOpen(false);

  return (
    <ConfigProvider theme={themeConfig}>
      <Router>
        <AuthProvider>
          <Routes>
            {/* Student login */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/demo" element={<LoginPage />} />

            {/* Instructor login + dashboard — completely separate layout */}
            <Route path="/instructor/login" element={<InstructorLoginPage />} />
            <Route
              path="/instructor/*"
              element={
                <InstructorP>
                  <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
                    <DemoBanner />
                    <Content style={{ padding: '0 24px 24px' }}>
                      <InstructorDashboard />
                    </Content>
                  </Layout>
                </InstructorP>
              }
            />

            {/* Student game-playing layout */}
            <Route
              path="*"
              element={
                <P>
                  <GameProvider>
                    <DecisionProvider>
                      <Layout style={{ minHeight: '100vh' }}>
                        <DSTopBar onToggle={handleToggle} isMobile={isMobile} />
                        <DemoBanner />
                        <NewsTicker />
                        <Layout style={{ marginTop: 0 }}>
                          {isMobile ? (
                            <Drawer
                              placement="left"
                              open={drawerOpen}
                              onClose={handleDrawerClose}
                              width={260}
                              styles={{ body: { padding: 0, background: 'var(--color-surface-800)' }, header: { display: 'none' } }}
                              className="mobile-sidebar-drawer"
                            >
                              <Sidebar collapsed={false} onNavigate={handleDrawerClose} />
                            </Drawer>
                          ) : (
                            <Sidebar collapsed={collapsed} />
                          )}
                          <Content className="ds-content-area">
                            <BudgetAlert />
                            <Routes>
                              <Route path="/" element={<GameDashboard />} />
                              {/* Information pages */}
                              <Route path="/games/:gameId/teams/:teamId/news" element={<IndustryNewsPage />} />
                              <Route path="/games/:gameId/teams/:teamId/research" element={<MarketResearchPage />} />
                              <Route path="/games/:gameId/teams/:teamId/competitors" element={<CompetitiveIntelPage />} />
                              <Route path="/games/:gameId/teams/:teamId/tools" element={<StrategyToolsPage />} />
                              <Route path="/games/:gameId/teams/:teamId/financial-reports" element={<FinancialReportsPage />} />
                              <Route path="/games/:gameId/teams/:teamId/team-activity" element={<TeamActivityPage />} />
                              {/* Analysis */}
                              <Route path="/games/:gameId/teams/:teamId/forecast" element={<CompanyForecastPage />} />
                              {/* Decisions */}
                              <Route path="/games/:gameId/teams/:teamId/decisions/sourcing" element={<SourcingPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/logistics" element={<LogisticsPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/trade-finance" element={<TradeFinancePage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/rd" element={<RDPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/products" element={<ProductsPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/marketing" element={<MarketingPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/corporate-strategy" element={<CorporateStrategyPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/market-strategy" element={<MarketStrategyPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/finance" element={<FinancePage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/communications" element={<CommunicationsPage />} />
                              <Route path="/games/:gameId/teams/:teamId/decisions/summary" element={<SummaryPage />} />
                              <Route path="/games/:gameId/leaderboard" element={<LeaderboardPage />} />
                              <Route path="/leaderboard" element={<LeaderboardPage />} />
                            </Routes>
                          </Content>
                        </Layout>
                      </Layout>
                    </DecisionProvider>
                  </GameProvider>
                </P>
              }
            />
          </Routes>
        </AuthProvider>
      </Router>
    </ConfigProvider>
  );
}

export default App;
