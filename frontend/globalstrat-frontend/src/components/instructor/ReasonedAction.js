import React, { useState } from 'react';
import { Button, Input, Modal, Typography } from 'antd';

const { Paragraph } = Typography;

// The server's own minimum (`OperatorAction.require_reason`). Enforced here
// too so that the instructor is asked before the request is sent: a refused
// attempt is itself written to the permanent operator record.
export const MINIMUM_REASON_LENGTH = 10;

/**
 * A button for an operator action the server will not run without a written
 * reason: reset, archive, delete. It replaces a yes/no Popconfirm, which had
 * nowhere to write one.
 */
const ReasonedAction = ({
  t, label, title, description, okText, onConfirm, buttonProps = {},
}) => {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const trimmed = reason.trim();

  const close = () => { setOpen(false); setReason(''); };

  return (
    <>
      <Button {...buttonProps} onClick={() => setOpen(true)}>{label}</Button>
      <Modal
        title={title}
        open={open}
        onCancel={close}
        okText={okText}
        cancelText={t('common.cancel')}
        confirmLoading={busy}
        okButtonProps={{
          danger: !!buttonProps.danger,
          disabled: trimmed.length < MINIMUM_REASON_LENGTH,
        }}
        onOk={async () => {
          setBusy(true);
          try {
            await onConfirm(trimmed);
          } finally {
            setBusy(false);
            close();
          }
        }}
      >
        <Paragraph>{description}</Paragraph>
        <Paragraph type="secondary">{t('instructor.reason_audit_note')}</Paragraph>
        <Input.TextArea
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={t('instructor.reason_placeholder', { count: MINIMUM_REASON_LENGTH })}
        />
      </Modal>
    </>
  );
};

export default ReasonedAction;
