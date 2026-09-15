import React from 'react';
import { useTranslation } from 'react-i18next';
import { Alert } from 'antd';

/**
 * What the price band did to a team's own prices when the round closed.
 *
 * Ruling 2 makes this disclosure mandatory: it is the half of the rule that
 * answers dispute 2, "our decision was recorded differently from what we
 * entered". The engine records the submitted value, the applied value and the
 * rule; `price_band.adjustment_notice` turns that record into one bilingual
 * sentence per adjustment. Both are already correct -- the defect this
 * component exists to close (F3) was that the sentence had no screen a student
 * could reach.
 *
 * Deliberately a shared component rather than markup repeated per surface:
 * CRV2-12's standard is that a rule is worded in one place and reused, and
 * three surfaces describing one adjustment three ways is the defect being
 * avoided. The sentences themselves are the server's and are NOT rewritten
 * here.
 */
const PriceAdjustmentNotice = ({ adjustments, style }) => {
  const { t } = useTranslation();
  const rows = adjustments || [];
  if (rows.length === 0) return null;

  return (
    <Alert
      type="warning"
      showIcon
      style={{ marginBottom: 16, ...style }}
      message={t('results_page.price_adjustments')}
      description={(
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {rows.map((a, i) => (
            <li key={`${a.product_name || ''}-${a.market || ''}-${i}`}>
              {a.message}
            </li>
          ))}
        </ul>
      )}
    />
  );
};

export default PriceAdjustmentNotice;
