import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import { Form, Input, Button, Typography, Alert, Card } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { login as apiLogin } from '../api/auth';
import { useAuth } from '../AuthContext';

const { Title, Text } = Typography;

const InstructorLoginPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Already logged in as instructor — go to dashboard
  if (user && ['instructor', 'admin'].includes((user.role || '').toLowerCase())) {
    return <Navigate to="/instructor" replace />;
  }

  const onFinish = async (values) => {
    setError(null);
    setLoading(true);
    try {
      const response = await apiLogin(values.username, values.password);
      const data = response.data;
      const role = (data.role || '').toLowerCase();

      if (!['instructor', 'admin'].includes(role)) {
        setError(t('instructor.instructors_only'));
        setLoading(false);
        return;
      }

      if (data.access) {
        localStorage.setItem('access_token', data.access);
      }
      login(data);
      navigate('/instructor');
    } catch (err) {
      const data = err.response?.data;
      setError(data?.error || data?.detail || t('instructor.login_failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%)',
    }}>
      <Card style={{
        maxWidth: 440, width: '100%',
        borderRadius: 8,
        boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={3} style={{ marginBottom: 4, color: '#1E40AF' }}>{t('instructor.brand')}</Title>
          <Text style={{ fontSize: 16, color: '#64748b' }}>{t('instructor.portal')}</Text>
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

        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="username"
            label={t('instructor.username')}
            rules={[{ required: true, message: t('instructor.username_required') }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: '#94A3B8' }} />}
              placeholder={t('instructor.username_placeholder')}
              size="large"
              autoFocus
            />
          </Form.Item>
          <Form.Item
            name="password"
            label={t('instructor.password')}
            rules={[{ required: true, message: t('instructor.password_required') }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#94A3B8' }} />}
              placeholder={t('instructor.password')}
              size="large"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={loading}
              style={{ background: '#1E40AF', borderColor: '#1E40AF', height: 48 }}>
              {t('instructor.sign_in')}
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: 'center', marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('instructor.students_use')} <a href="/login">{t('instructor.student_login')}</a>
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default InstructorLoginPage;
