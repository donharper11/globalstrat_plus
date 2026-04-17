import React, { useState } from 'react';
import { useNavigate, Navigate, useLocation } from 'react-router-dom';
import { Form, Input, Button, Typography, Alert, Divider } from 'antd';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faUser, faLock } from '@fortawesome/free-solid-svg-icons';
import { useTranslation } from 'react-i18next';
import { login as apiLogin } from '../api/auth';
import { useAuth } from '../AuthContext';
import LanguageSwitcher from '../components/LanguageSwitcher';

const { Title, Text } = Typography;

const DEMO_ACCOUNTS = [
  { labelKey: 'login.team_1', username: 'demo_student1', password: 'demo1' },
  { labelKey: 'login.team_2', username: 'demo_student2', password: 'demo2' },
  { labelKey: 'login.team_3', username: 'demo_student3', password: 'demo3' },
  { labelKey: 'login.team_4', username: 'demo_student4', password: 'demo4' },
  { labelKey: 'login.team_5', username: 'demo_student5', password: 'demo5' },
];

const LoginPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(null);
  const [error, setError] = useState(null);

  const isDemo = location.pathname === '/demo';

  if (user && !user.requires_section_selection) {
    return <Navigate to="/" replace />;
  }

  const doLogin = async (username, password) => {
    const response = await apiLogin(username, password);
    const data = response.data;
    if (data.access) {
      localStorage.setItem('access_token', data.access);
    }
    // Mark demo users
    if (username.startsWith('demo_')) {
      data.is_demo = true;
    }
    login(data);
    return data;
  };

  const onFinish = async (values) => {
    setError(null);
    setLoading(true);
    try {
      await doLogin(values.username, values.password);
      navigate('/');
    } catch (err) {
      const data = err.response?.data;
      setError(data?.error || data?.detail || t('login.login_failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (account) => {
    setError(null);
    setDemoLoading(account.username);
    try {
      const data = await doLogin(account.username, account.password);
      if (account.isInstructor) {
        navigate('/instructor/dashboard');
      } else {
        navigate('/');
      }
    } catch (err) {
      const data = err.response?.data;
      setError(data?.error || data?.detail || t('login.demo_login_failed'));
    } finally {
      setDemoLoading(null);
    }
  };

  return (
    <div style={{
      position: 'relative',
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh',
    }}>
      {/* Background image */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 0,
        backgroundImage: 'url(/images/login-page.png)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }} />
      {/* Navy overlay */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 1,
        background: 'rgba(30, 58, 95, 0.6)',
      }} />

      {/* Login card */}
      <div style={{
        position: 'relative', zIndex: 2,
        maxWidth: isDemo ? 520 : 420, width: '100%',
        background: 'rgba(255, 255, 255, 0.97)',
        border: '1px solid #E2E8F0', padding: 40,
        backdropFilter: 'blur(4px)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={3} style={{ marginBottom: 4, color: '#1E40AF' }}>{t('login.title')}</Title>
          <Text type="secondary">{t('login.subtitle')}</Text>
        </div>

        {error && (
          <Alert
            message={error}
            type="error"
            showIcon
            closable
            onClose={() => setError(null)}
            style={{ marginBottom: 16 }}
          />
        )}

        {isDemo && (
          <>
            <div style={{
              background: '#EFF6FF', border: '1px solid #BFDBFE',
              borderRadius: 6, padding: '12px 16px', marginBottom: 20,
              textAlign: 'center',
            }}>
              <Text strong style={{ color: '#1E40AF' }}>
                {t('login.demo_mode')}
              </Text>
            </div>

            <div style={{ display: 'grid', gap: 8 }}>
              {DEMO_ACCOUNTS.map((account) => (
                <Button
                  key={account.username}
                  block
                  size="large"
                  type={account.isInstructor ? 'primary' : 'default'}
                  loading={demoLoading === account.username}
                  disabled={demoLoading && demoLoading !== account.username}
                  onClick={() => handleDemoLogin(account)}
                  style={{
                    textAlign: 'left',
                    height: 'auto',
                    padding: '10px 16px',
                    ...(account.isInstructor ? {} : { borderColor: '#D1D5DB' }),
                  }}
                >
                  <div style={{ lineHeight: 1.4 }}>
                    <div>{t(account.labelKey)}</div>
                    <div style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 400 }}>
                      {account.username} / {account.password}
                    </div>
                  </div>
                </Button>
              ))}
            </div>

            <Divider style={{ margin: '24px 0 16px' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>{t('login.or_sign_in')}</Text>
            </Divider>
          </>
        )}

        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="username"
            label={t('login.username')}
            rules={[{ required: true, message: t('login.username_required') }]}
          >
            <Input
              prefix={<FontAwesomeIcon icon={faUser} style={{ color: '#94A3B8' }} />}
              placeholder={t('login.username_placeholder')}
              size="large"
              autoFocus={!isDemo}
            />
          </Form.Item>
          <Form.Item
            name="password"
            label={t('login.password')}
          >
            <Input.Password
              prefix={<FontAwesomeIcon icon={faLock} style={{ color: '#94A3B8' }} />}
              placeholder={t('login.password_placeholder')}
              size="large"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={loading}>
              {t('login.log_in')}
            </Button>
          </Form.Item>
        </Form>

        <div style={{
          textAlign: 'center',
          marginTop: 10,
          lineHeight: 1.6,
        }}>
          <div style={{ fontFamily: 'Inter, sans-serif', fontWeight: 400, fontSize: 13, color: '#8A8A8A' }}>
            Clarity. Capability. Camdani.
          </div>
          <div style={{ fontFamily: 'Inter, sans-serif', fontWeight: 300, fontSize: 12, color: '#A0A0A0' }}>
            Built for Real Work, Not Just Coursework
          </div>
        </div>

        {!isDemo && (
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <Button type="link" onClick={() => navigate('/demo')} style={{ color: '#6B7280', fontSize: 13 }}>
              {t('login.try_demo')}
            </Button>
          </div>
        )}

        <div style={{ textAlign: 'center', marginTop: 12 }}>
          <LanguageSwitcher style={{ color: '#94A3B8', fontSize: 12 }} />
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
