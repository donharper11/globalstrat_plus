import React from 'react';
import { Alert, Button } from 'antd';
import { useTranslation } from 'react-i18next';
import { useDecisions } from '../contexts/DecisionContext';

/**
 * "Your last change was not saved."
 *
 * R17 ruled that a contended save must refuse fast AND tell the student: the
 * interface must show the edit was not saved, and retry it. A student losing
 * an edit silently while the status bar reads "Saved" is the defect, not the
 * refusal.
 *
 * It renders beside BudgetAlert, inside the student shell's Content and inside
 * DecisionProvider, for a specific reason: the autosave spans every decision
 * screen, so the notice has to outlive a navigation between them. The obvious
 * home would have been GameStatusBar, which owns the Saving/Saved indicator --
 * but that component is exported and never imported anywhere, so anything put
 * there would render to nobody. That is finding F3's shape exactly, and it is
 * why this is a mounted component rather than a line added to that one.
 *
 * A transient `message` toast was deliberately not used: it disappears, and
 * the condition it describes does not. The notice stands until the edit is
 * actually saved.
 */
const DecisionSaveAlert = () => {
  const { t } = useTranslation();
  const { saveError, saving, retrySave } = useDecisions();

  if (!saveError) return null;

  // A lifecycle conflict is an operator action, not a mistake by the team, and
  // it clears by itself. A validation refusal will not clear on a timer -- the
  // team has to change something -- so it names what the server objected to.
  const body = {
    lifecycle: 'decision_save.lifecycle_conflict',
    network: 'decision_save.network_failed',
    validation: 'decision_save.refused',
  }[saveError.kind] || 'decision_save.refused';

  return (
    <Alert
      type="error"
      showIcon
      style={{ marginBottom: 12 }}
      message={t('decision_save.not_saved_title')}
      description={(
        <div>
          <div style={{ marginBottom: 8 }}>{t(body)}</div>
          {saveError.messages.length > 0 && (
            <ul style={{ margin: '0 0 8px', paddingLeft: 18 }}>
              {saveError.messages.map((msg, i) => <li key={i}>{msg}</li>)}
            </ul>
          )}
          {saveError.retrying && (
            <div style={{ marginBottom: 8 }}>{t('decision_save.retrying')}</div>
          )}
          <Button size="small" onClick={retrySave} loading={saving}>
            {t('decision_save.retry_now')}
          </Button>
        </div>
      )}
    />
  );
};

export default DecisionSaveAlert;
