import React from 'react';
import { useTranslation } from 'react-i18next';
import { Alert } from 'antd';

/**
 * Why a team that sold nothing was placed below every firm that competed.
 *
 * R35 (owner, 2026-09-17) makes this disclosure mandatory on the team's own
 * screen. Under R32 the standings place a commercially inactive firm below
 * every firm that competed, whatever its score, so a team can hold a HIGHER
 * performance index than the team above it and still finish below it. R34
 * recorded that firing as an audit event and CRV2-08's instructor drill-down
 * surfaces it to an instructor; this is the half the team itself reads.
 *
 * The sentence is the SERVER'S, rendered there from the stored audit payload,
 * and is NOT rewritten here. A screen that restated the ranking rule in its own
 * words would be a second place the rule is worded — the defect CRV2-12's
 * standard exists to prevent, and the same reason `PriceAdjustmentNotice`
 * passes its sentences straight through.
 */
const InactivityDemotionNotice = ({ notices, style }) => {
  const { t } = useTranslation();
  const rows = notices || [];
  if (rows.length === 0) return null;

  return (
    <Alert
      type="warning"
      showIcon
      style={{ marginBottom: 16, ...style }}
      message={t('results_page.inactivity_demotion')}
      description={(
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {rows.map((n, i) => (
            <li key={`${n.rule || 'demotion'}-${i}`}>
              {n.message}
            </li>
          ))}
        </ul>
      )}
    />
  );
};

export default InactivityDemotionNotice;
