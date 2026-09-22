import React, { useState } from 'react';
import { Button, Modal, Typography, message } from 'antd';

import { advanceRound } from '../../api/instructor';
import { serverReason } from '../../pages/bilingualServerReason';
import ReasonedAction from './ReasonedAction';

const { Paragraph } = Typography;

/**
 * The Game Lifecycle card's "Advance Round": the legacy one-step route that
 * processes the current round and opens the next.
 *
 * While any team is still pending, that route resolves the round with
 * whatever those teams had, so the server treats it as an override and
 * refuses it without a written reason (`reason_required`). Until 2026-09-22
 * (W-CE-24) the modal here had only Cancel and OK, sent `force: true` with no
 * reason, and was refused on every click: the one button on the card that
 * said "advance" could not advance a round with pending teams at all. With
 * teams pending it is now the same reasoned confirmation as reset, archive
 * and delete; with every team locked it stays a plain confirmation, because
 * the server asks for no reason then.
 *
 * A refusal is shown in the server's own words (bilingual, with its
 * guidance) rather than "Failed to advance round".
 */
export default function AdvanceRoundControl({
  t, gameId, gameName, teamsPending, onAdvanced,
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = Number(teamsPending) > 0;

  const advance = async (force, reason) => {
    setBusy(true);
    try {
      const res = await advanceRound(gameId, force, reason);
      message.success(res?.data?.message || t('instructor.rc_done'));
      onAdvanced?.();
    } catch (err) {
      Modal.error({
        title: t('instructor.error'),
        content: serverReason(err) || t('instructor.failed_advance_round'),
      });
    } finally {
      setBusy(false);
    }
  };

  if (pending) {
    return (
      <ReasonedAction t={t}
        label={t('instructor.advance_round')}
        title={t('instructor.advance_round_named', { game: gameName })}
        description={t('instructor.advance_pending', { count: teamsPending })}
        okText={t('instructor.advance_now')}
        buttonProps={{ type: 'primary' }}
        onConfirm={(reason) => advance(true, reason)} />
    );
  }

  return (
    <>
      <Button type="primary" onClick={() => setConfirmOpen(true)}>
        {t('instructor.advance_round')}
      </Button>
      <Modal
        title={t('instructor.advance_round_named', { game: gameName })}
        open={confirmOpen}
        okText={t('instructor.advance_now')}
        cancelText={t('common.cancel')}
        confirmLoading={busy}
        onCancel={() => setConfirmOpen(false)}
        onOk={async () => {
          await advance(false, '');
          setConfirmOpen(false);
        }}
      >
        <Paragraph>{t('instructor.advance_ready')}</Paragraph>
      </Modal>
    </>
  );
}
