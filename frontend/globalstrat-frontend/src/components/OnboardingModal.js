import React, { useState, useEffect } from 'react';
import { Modal, Button, Typography, Space, Divider } from 'antd';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../AuthContext';
import { useGame } from '../contexts/GameContext';
import { getOnboardingData, completeOnboarding } from '../api/auth';

const { Title, Text, Paragraph } = Typography;

const NAVY = '#1E3A5F';
const NAVY_LIGHT = '#F0F4F8';

const SCREEN_IMAGES = [
  { src: '/images/welcome.png', alt: 'Your Global Challenge' },
  { src: '/images/key-things.png', alt: 'What You Must Navigate' },
  { src: '/images/how-each-round-works.png', alt: 'How to Build Your Global Strategy' },
  { src: '/images/starting-position.png', alt: 'How You\'re Scored' },
  { src: '/images/navigation.png', alt: 'Your Starting Position' },
  null, // Screen 6 uses onboarding.png as background
];

const fmt = (v) => {
  if (v == null) return '$0';
  const n = Number(v);
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};

const Dot = ({ active }) => (
  <span style={{
    display: 'inline-block',
    width: active ? 24 : 8,
    height: 8,
    borderRadius: 4,
    background: active ? NAVY : '#CBD5E1',
    margin: '0 3px',
    transition: 'all 0.3s ease',
  }} />
);

const ScreenImage = ({ src, alt }) => (
  <div style={{ textAlign: 'center', marginBottom: 16 }}>
    <img
      src={src}
      alt={alt}
      loading="lazy"
      style={{
        maxWidth: 400, width: '100%', height: 'auto',
        borderRadius: 4, objectFit: 'cover',
      }}
    />
  </div>
);

const ScreenTitle = ({ title }) => (
  <Title level={3} style={{
    fontFamily: "'Rajdhani', 'Exo 2', sans-serif",
    color: NAVY, margin: '0 0 12px', fontWeight: 700, textAlign: 'center',
  }}>
    {title}
  </Title>
);

const ForceCard = ({ label, text, color }) => (
  <div style={{
    padding: '12px 16px', marginBottom: 8,
    borderLeft: `3px solid ${color}`, background: NAVY_LIGHT,
  }}>
    <Text strong style={{ fontSize: 13, color, display: 'block', marginBottom: 4 }}>{label}</Text>
    <Text style={{ fontSize: 13, lineHeight: 1.5 }}>{text}</Text>
  </div>
);

const InfoCard = ({ label, value, color }) => (
  <div style={{
    background: NAVY_LIGHT, padding: '12px 16px',
    borderLeft: `3px solid ${color || NAVY}`,
    marginBottom: 8,
  }}>
    <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>{label}</Text>
    <Text strong style={{ fontSize: 16 }}>{value}</Text>
  </div>
);

const OnboardingModal = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { gameId, teamId } = useGame();
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!user || !gameId || !teamId) return;
    if (user.role === 'instructor' || user.role === 'admin') return;
    if (user.onboarding_completed) return;
    const demoDismissKey = `gs_onboarding_dismissed_${user.user_id}_${gameId}_${teamId}`;
    if (user.is_demo && sessionStorage.getItem(demoDismissKey) === '1') return;

    getOnboardingData(gameId, teamId)
      .then(res => {
        setData(res.data);
        setVisible(true);
      })
      .catch(() => {});
  }, [user, gameId, teamId]);

  if (!visible || !data) return null;

  const handleDismiss = async () => {
    setVisible(false);
    if (user.is_demo) {
      sessionStorage.setItem(`gs_onboarding_dismissed_${user.user_id}_${gameId}_${teamId}`, '1');
      return;
    }
    try {
      await completeOnboarding(user.user_id, user.section_id);
      const stored = localStorage.getItem('gs_user');
      if (stored) {
        const parsed = JSON.parse(stored);
        parsed.onboarding_completed = true;
        localStorage.setItem('gs_user', JSON.stringify(parsed));
      }
    } catch { /* best effort */ }
  };

  const totalSteps = 6;
  const isLast = step === totalSteps - 1;
  const isFirst = step === 0;

  const deadlineStr = data.deadline
    ? new Date(data.deadline).toLocaleString(undefined, {
        weekday: 'short', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : 'TBD';

  const screens = [
    // Screen 1: Your Global Challenge
    <div key="challenge">
      <ScreenImage {...SCREEN_IMAGES[0]} />
      <ScreenTitle title={t('onboarding.s1_title')} />
      <Paragraph style={{ fontSize: 15, textAlign: 'center', lineHeight: 1.7 }}>
        {t('onboarding.s1_intro', {
          team: data.team_name,
          industry: data.industry,
          home_market: data.home_market_name || t('common.home_market'),
        })}
      </Paragraph>
      <Paragraph style={{ fontSize: 15, textAlign: 'center', lineHeight: 1.7 }}>
        {t('onboarding.s1_mission')}
      </Paragraph>
      <Paragraph style={{ fontSize: 15, textAlign: 'center', lineHeight: 1.7, color: '#475569' }}>
        {t('onboarding.s1_origin')}
      </Paragraph>
    </div>,

    // Screen 2: What You Must Navigate
    <div key="forces">
      <ScreenImage {...SCREEN_IMAGES[1]} />
      <ScreenTitle title={t('onboarding.s2_title')} />
      <Paragraph style={{ fontSize: 14, textAlign: 'center', marginBottom: 16 }}>
        {t('onboarding.s2_intro')}
      </Paragraph>
      <div style={{ maxWidth: 480, margin: '0 auto' }}>
        <ForceCard
          label={t('onboarding.s2_origin_trust_label')}
          text={t('onboarding.s2_origin_trust', { home_market: data.home_market_name || t('common.home_market') })}
          color="#DC2626"
        />
        <ForceCard
          label={t('onboarding.s2_cultural_distance_label')}
          text={t('onboarding.s2_cultural_distance')}
          color="#D97706"
        />
        <ForceCard
          label={t('onboarding.s2_tech_sovereignty_label')}
          text={t('onboarding.s2_tech_sovereignty')}
          color="#2563EB"
        />
        <ForceCard
          label={t('onboarding.s2_gov_policy_label')}
          text={t('onboarding.s2_gov_policy')}
          color="#16A34A"
        />
        <ForceCard
          label={t('onboarding.s2_competitive_label')}
          text={t('onboarding.s2_competitive')}
          color="#8B5CF6"
        />
      </div>
    </div>,

    // Screen 3: How to Build Your Global Strategy
    <div key="layers">
      <ScreenImage {...SCREEN_IMAGES[2]} />
      <ScreenTitle title={t('onboarding.s3_title')} />
      <Paragraph style={{ fontSize: 14, textAlign: 'center', marginBottom: 16 }}>
        {t('onboarding.s3_intro')}
      </Paragraph>
      <div style={{ maxWidth: 480, margin: '0 auto' }}>
        {[
          { num: 1, label: t('onboarding.s3_layer1_label'), text: t('onboarding.s3_layer1'), color: '#2563EB' },
          { num: 2, label: t('onboarding.s3_layer2_label'), text: t('onboarding.s3_layer2'), color: '#16A34A' },
          { num: 3, label: t('onboarding.s3_layer3_label'), text: t('onboarding.s3_layer3'), color: '#D97706' },
        ].map(({ num, label, text, color }) => (
          <div key={num} style={{
            display: 'flex', alignItems: 'flex-start', gap: 14,
            padding: '14px 16px', marginBottom: 8,
            background: NAVY_LIGHT, borderLeft: `3px solid ${color}`,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: color, color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700, fontSize: 13, flexShrink: 0, marginTop: 2,
            }}>{num}</div>
            <div>
              <Text strong style={{ fontSize: 13, color, display: 'block', marginBottom: 2 }}>{label}</Text>
              <Text style={{ fontSize: 13, lineHeight: 1.5 }}>{text}</Text>
            </div>
          </div>
        ))}
      </div>
      <Paragraph style={{ fontSize: 14, textAlign: 'center', marginTop: 16, color: '#475569', fontStyle: 'italic' }}>
        {t('onboarding.s3_read_first')}
      </Paragraph>
    </div>,

    // Screen 4: How You're Scored
    <div key="scoring">
      <ScreenImage {...SCREEN_IMAGES[3]} />
      <ScreenTitle title={t('onboarding.s4_title')} />
      <Paragraph style={{ fontSize: 14, textAlign: 'center', marginBottom: 16 }}>
        {t('onboarding.s4_intro')}
      </Paragraph>
      <div style={{ maxWidth: 480, margin: '0 auto' }}>
        {[
          { label: t('onboarding.s4_customers_label'), text: t('onboarding.s4_customers'), color: '#2563EB' },
          { label: t('onboarding.s4_investors_label'), text: t('onboarding.s4_investors'), color: '#16A34A' },
          { label: t('onboarding.s4_regulators_label'), text: t('onboarding.s4_regulators'), color: '#D97706' },
          { label: t('onboarding.s4_partners_label'), text: t('onboarding.s4_partners'), color: '#8B5CF6' },
        ].map(({ label, text, color }) => (
          <div key={label} style={{
            padding: '12px 16px', marginBottom: 8,
            borderLeft: `3px solid ${color}`, background: NAVY_LIGHT,
          }}>
            <Text strong style={{ fontSize: 13, color, display: 'block', marginBottom: 2 }}>{label}</Text>
            <Text style={{ fontSize: 13, lineHeight: 1.5 }}>{text}</Text>
          </div>
        ))}
      </div>
      <Paragraph style={{ fontSize: 14, textAlign: 'center', marginTop: 16, color: '#475569' }}>
        {t('onboarding.s4_coherence')}
      </Paragraph>
    </div>,

    // Screen 5: Your Starting Position
    <div key="position">
      <ScreenImage {...SCREEN_IMAGES[4]} />
      <ScreenTitle title={t('onboarding.s5_title')} />
      <Paragraph style={{ fontSize: 15, textAlign: 'center', lineHeight: 1.7 }}>
        {t('onboarding.s5_inherited', { team: data.team_name })}
      </Paragraph>
      <div style={{ marginTop: 16 }}>
        <InfoCard label={t('onboarding.s5_products')} value={t('onboarding.s5_products_value', { count: data.product_count, platform: data.platform_name || 'Gen 1' })} color="#2563EB" />
        <InfoCard label={t('onboarding.s5_cash')} value={fmt(data.cash_on_hand)} color="#16A34A" />
        <InfoCard label={t('onboarding.s5_market')} value={data.home_market_name || '—'} color="#D97706" />
        <InfoCard label={t('onboarding.s5_talent')} value={t('onboarding.s5_talent_value', { count: data.talent_count || 0 })} color="#8B5CF6" />
      </div>
      <div style={{ marginTop: 20, maxWidth: 440, margin: '20px auto 0' }}>
        <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>{t('onboarding.s5_first_decisions')}</Text>
        {[
          t('onboarding.s5_step1'),
          t('onboarding.s5_step2'),
          t('onboarding.s5_step3'),
        ].map((text, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 10,
            padding: '6px 0',
          }}>
            <Text strong style={{ color: NAVY, fontSize: 14, flexShrink: 0 }}>{i + 1}.</Text>
            <Text style={{ fontSize: 14, lineHeight: 1.5 }}>{text}</Text>
          </div>
        ))}
      </div>
    </div>,

    // Screen 6: Ready to Begin
    <div key="ready" style={{
      position: 'relative', padding: '32px 20px', textAlign: 'center',
      backgroundImage: 'url(/images/onboarding.png)',
      backgroundSize: 'cover', backgroundPosition: 'center',
      borderRadius: 4, overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(255,255,255,0.88)',
        borderRadius: 4,
      }} />
      <div style={{ position: 'relative' }}>
        <ScreenTitle title={t('onboarding.s6_title')} />
        <Paragraph style={{ fontSize: 16, lineHeight: 1.7 }}>
          {t('onboarding.s6_deadline', { round: data.current_round, deadline: deadlineStr })}
        </Paragraph>
        <Paragraph style={{ fontSize: 15, lineHeight: 1.7, color: '#475569', fontStyle: 'italic' }}>
          {t('onboarding.s6_no_single_strategy')}
        </Paragraph>
        <Divider />
        <Text type="secondary" style={{ fontSize: 13 }}>{t('onboarding.s6_good_luck', { team: data.team_name })}</Text>
      </div>
    </div>,
  ];

  return (
    <Modal
      open={visible}
      title={null}
      footer={null}
      closable
      onCancel={handleDismiss}
      width={640}
      centered
      styles={{
        body: {
          padding: '32px 32px 20px',
          minHeight: 420,
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      <div style={{ flex: 1, overflowY: 'auto', maxHeight: '60vh' }}>{screens[step]}</div>

      {/* Progress dots */}
      <div style={{ textAlign: 'center', margin: '16px 0 12px' }}>
        {Array.from({ length: totalSteps }, (_, i) => (
          <Dot key={i} active={i === step} />
        ))}
      </div>

      {/* Navigation buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button type="text" size="small" onClick={handleDismiss} style={{ color: '#94A3B8' }}>
          {t('onboarding.skip')}
        </Button>
        <Space>
          {!isFirst && (
            <Button onClick={() => setStep(s => s - 1)}>{t('onboarding.back')}</Button>
          )}
          {isLast ? (
            <Button
              type="primary" size="large" onClick={handleDismiss}
              style={{ background: NAVY, borderColor: NAVY, fontWeight: 600, padding: '0 32px' }}
            >
              {t('onboarding.begin')}
            </Button>
          ) : (
            <Button type="primary" onClick={() => setStep(s => s + 1)}
              style={{ background: NAVY, borderColor: NAVY }}
            >
              {t('onboarding.next')}
            </Button>
          )}
        </Space>
      </div>
    </Modal>
  );
};

export default OnboardingModal;
